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
import faulthandler
import gc
import json
import math
import os
import queue
import re
import select
import shutil
import subprocess
import socket
import sys
import threading
import time
import traceback
import unicodedata
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
APP_VER = "8.0-dev"
MIN_PTS = 51                 # minimum accepté par la commande scan
POINTS_CHOICES = [101, 145, 290, 500, 1000, 3000, 5000, 10000, 30000]
SEG_CHOICES = [None, 145, 290, 450]     # points max par commande scan (None = auto)
RBW_LIST = [0.3, 1, 3, 10, 30, 100, 300, 600, 850]
WF_ROWS = 150                # profondeur du waterfall
WF_MAX_COLS = 3000           # colonnes max du waterfall (réduction par maximum)
ZOOM_ID = -2                 # identifiant interne de la "bande" de zoom live
CALIB_IDS = (-3, -4)         # bandes internes de la calibration entre deux tinySA (1er, 2e)
CALIB_SWEEPS = 3             # balayages par appareil pour calibrer
CALIB_TIMEOUT = 180.0
MAX_LABELS = 30              # nb max de noms affichés sur le graphe
HYST = 3.0                   # hystérésis (dB) pour repasser en "libre"
TINYSA_VID, TINYSA_PID = 0x0483, 0x5740
CFG_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "TinySAMonitor" / "config.json"
PROFILE_DIR = CFG_PATH.parent / "profils"
REF_PATH = CFG_PATH.parent / "reference.json"
CRASH_PATH = CFG_PATH.parent / "crash.log"
CFG_BAK = CFG_PATH.with_suffix(".json.bak")
AUTOSAVE_MS = 60_000
STOP_FORCE_MS = 4000
LAYOUT_VER = 3                # à monter quand la disposition de base change (les anciennes sont ignorées)          # « Arrêter » : au-delà, on ferme le port pour débloquer
LOG_DIR = Path.home() / "Documents" / "TinySA Monitor" / "Journaux"
SHOW_DIR = Path.home() / "Documents" / "TinySA Monitor" / "Shows"

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


LEVEL_UNITS = (("dbm", "dBm"), ("dbuv", "dBµV (50 Ω)"), ("pct", "% (comme WSM)"))
UNIT_SUFFIX = {"dbm": "dBm", "dbuv": "dBµV", "pct": "%"}


def to_unit(dbm, unit):
    """Niveau dBm -> unité d'affichage. dBµV = dBm + 107 (50 Ω) ; % = échelle WSM (0 % = −120 dBm, 100 % = 0 dBm)."""
    if dbm is None:
        return None
    if unit == "dbuv":
        return dbm + 107.0
    if unit == "pct":
        return min(100.0, max(0.0, (dbm + 120.0) * 100.0 / 120.0))
    return dbm


def from_unit(v, unit):
    """Unité d'affichage -> dBm (inverse de to_unit)."""
    if v is None:
        return None
    if unit == "dbuv":
        return v - 107.0
    if unit == "pct":
        return v * 120.0 / 100.0 - 120.0
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
    if not n:
        text = "Rien à appeler"
    elif not miss:
        text = f"Tout est là ✓ ({ok + weak} / {n})" + (f" (dont {weak} faible{'s' if weak > 1 else ''})" if weak else "")
    else:
        text = (f"{ok + weak} / {n} OK" + (f" (dont {weak} faible{'s' if weak > 1 else ''})" if weak else "") + f" · manque{'nt' if len(miss) > 1 else ''} : "
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
# 0 = type ignoré. 100 / 50 kHz = défauts des guides EazyRF (2 TX / 3 TX) ; 5ᵉ ordre : notre choix.
# Le 1er réglage (comme EazyRF : 2 TX 100 / 3 TX 50 kHz) est celui par défaut ; avec le FILTRE du récepteur
# (32 MHz dans le profil Wisycom d'EazyRF de Clément), son plan Wisycom donne 0 IM, comme dans EazyRF.
IM_TOL_PRESETS = [
    ("🟢 Comme EazyRF (2 TX ±100 · 3 TX ±50 kHz)", {"2tx3": 0.100, "3tx3": 0.050, "5": 0.0, "7": 0.0},
     "Les tolérances par défaut d'EazyRF : produits à 2 émetteurs (2A − B) à ±100 kHz et à 3 émetteurs "
     "(A + B − C) à ±50 kHz. Avec le filtre du récepteur réglé comme dans EazyRF, le verdict est le même."),
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
        parts.append(f"seuls comptent les émetteurs à ±{filt / 2:g} MHz de la fréquence touchée (filtre {filt:g} MHz)")
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
    dans le dict, 0 = type ignoré (comme une tolérance 0 dans EazyRF).
    -> (rows, info). rows = [dict(f, order, terms, ntx, target, delta, hw, gap)] ; terms = [(indice, coefficient)] ;
    hw = demi-largeur du produit ; gap = écart bord à bord avec la cible (≤ 0 : ça se chevauche)."""
    gd = dict(guard) if isinstance(guard, dict) else None
    guard = max(gd.values()) if gd else float(guard)

    def tol(order, ntx):
        return guard if gd is None else gd.get(im_class(order, ntx), guard)

    def ignored(order, ntx):
        """Tolérance 0 dans le dict = ce type de produit n'est pas compté (comme 0 dans EazyRF)."""
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


# ------------------------------------------------- vérification d'un plan de fréquences (façon EazyRF)
PF_SEP = 0.300          # écart mini par défaut entre deux porteuses (MHz) ; réglable dans la fenêtre


def pf_orders(tol):
    """Ordres à calculer d'après les tolérances (0 = ignoré). Jusqu'au 5ᵉ comme EazyRF : le 7ᵉ multiplie les
    combinaisons par ~100 (30 émetteurs : 200 millions) pour des produits très faibles."""
    return tuple(o for o, k in ((3, "2tx3"), (5, "5")) if tol.get(k, 0) > 0 or (o == 3 and tol.get("3tx3", 0) > 0))


# Profils d'appareil (comme les profils d'EazyRF) : écart mini, filtre d'entrée du récepteur, pas de réglage et
# tolérances d'intermod. Wisycom = le profil EazyRF de Clément (MRK980). Les autres sont des VALEURS DE DÉPART
# (non vérifiées) : un récepteur peu sélectif a un filtre large (ou aucun), donc plus d'émetteurs comptent.
RX_PROFILES = [
    ("wisycom", "Wisycom (MRK980, MTK952…) · très sélectif",
     dict(sep=0.500, filt=32.0, step=0.005, tol={"2tx3": 0.100, "3tx3": 0.050, "5": 0.0, "7": 0.0}),
     "Profil Wisycom d'EazyRF : filtre d'entrée 32 MHz (seuls les émetteurs à ±16 MHz comptent), séparation "
     "500 kHz, pas 5 kHz (MTK952 : 25 kHz)."),
    ("senn_dig", "Sennheiser numérique (EW-DX, EW-D, 6000)",
     dict(sep=0.400, filt=0.0, step=0.025, tol={"2tx3": 0.100, "3tx3": 0.050, "5": 0.0, "7": 0.0}),
     "Valeurs de départ (non vérifiées) : pas de filtre étroit, tous les émetteurs comptent ; séparation 400 kHz."),
    ("senn_ana", "Sennheiser analogique (EW G3 / G4, 2000, 5000)",
     dict(sep=0.400, filt=0.0, step=0.025, tol={"2tx3": 0.150, "3tx3": 0.075, "5": 0.0, "7": 0.0}),
     "Valeurs de départ (non vérifiées) : peu sélectif, tolérances plus larges (150 / 75 kHz)."),
    ("shure_dig", "Shure numérique (ULX-D, QLX-D, Axient, SLX-D)",
     dict(sep=0.350, filt=0.0, step=0.025, tol={"2tx3": 0.100, "3tx3": 0.050, "5": 0.0, "7": 0.0}),
     "Valeurs de départ (non vérifiées) : pas de filtre étroit, séparation 350 kHz."),
    ("shure_ana", "Shure analogique (UR, SLX, BLX…)",
     dict(sep=0.400, filt=0.0, step=0.025, tol={"2tx3": 0.150, "3tx3": 0.075, "5": 0.0, "7": 0.0}),
     "Valeurs de départ (non vérifiées) : peu sélectif, tolérances plus larges (150 / 75 kHz)."),
    ("iem", "Ears / IEM (PSM, EW IEM…) · émetteurs couplés",
     dict(sep=0.400, filt=0.0, step=0.025, tol={"2tx3": 0.150, "3tx3": 0.075, "5": 0.050, "7": 0.0}),
     "Valeurs de départ (non vérifiées) : émetteurs souvent couplés sur un combineur → on compte aussi le 5ᵉ "
     "ordre ; récepteurs ceinture peu sélectifs."),
]


def rx_profile(key):
    """Profil d'appareil par sa clé -> dict(sep, filt, step, tol), ou None (= réglages de la fenêtre)."""
    for k, _n, d, _w in RX_PROFILES:
        if k == key:
            return dict(d, tol=dict(d["tol"]))
    return None


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


def pf_check(freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, max_tx=None, filt=0.0):
    """Compatibilité d'un plan : pour chaque fréquence, la liste de ses problèmes.
    - « sep » : une autre porteuse à moins de `sep` MHz (bord à bord pour un bloc large) ;
    - « im » : un produit d'intermod des ÉMETTEURS (is_tx) tombe dessus, dans la tolérance de son type (`tol`,
      comme EazyRF : 2 TX / 3 TX / 5ᵉ ; 0 = type ignoré). Les réserves (is_tx False) sont protégées sans émettre.
    filt : largeur (MHz) du filtre d'entrée du récepteur (« Filtre » d'EazyRF) ; un produit ne gêne une fréquence
    que si tous ses émetteurs sont à ± filt / 2 d'elle (les autres sont filtrés). 0 = pas de filtre.
    sep, filt et tol peuvent être donnés PAR FRÉQUENCE (listes : profil d'appareil de chacune) : l'écart entre deux
    porteuses est le plus grand des deux, le filtre et les tolérances sont ceux de la fréquence touchée.
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
    txi = np.nonzero(tx)[0]
    orders = pf_orders(tmax)
    if len(txi) >= 2 and orders:
        TV = {k: np.array([t.get(k, 0.0) for t in TL]) for k in ("2tx3", "3tx3", "5", "7")}
        rows, info = im_scan(F[txi], orders, max_tx, targets=F, guard=tmax, bws=B[txi], tbws=B, limit=20000)
        for r in rows:
            src = [(int(txi[i]), c) for i, c in r["terms"]]
            used = {k for k, _c in src}
            tv = TV.get(im_class(r["order"], r["ntx"]), TV["5"])
            g_ = np.abs(F - r["f"]) - r["hw"] - B / 2.0
            for v in np.nonzero((tv > 0) & (g_ <= tv + 1e-9))[0].tolist():
                if v in used:
                    continue
                if FL[v] > 0 and any(abs(F[k] - F[v]) > FL[v] / 2.0 + 1e-9 for k in used):
                    continue                    # émetteur hors du filtre du récepteur : filtré
                issues[v].append(dict(kind="im", others=sorted(used), gap=float(g_[v]), order=r["order"],
                                      ntx=r["ntx"], terms=src, f=r["f"], hw=r["hw"]))
    return issues, info


def pf_issue_text(it, names, freqs):
    """Une ligne lisible pour un problème de pf_check."""
    if it["kind"] == "sep":
        o = it["others"][0]
        if it["gap"] < 0:
            return f"chevauche {names[o]} ({freqs[o]:.3f})"
        return f"trop près de {names[o]} ({freqs[o]:.3f}) : {it['gap'] * 1000:.0f} kHz d'écart"
    lab = IM_NAMES.get(it["order"], "IM") + f" {it['ntx']} TX"
    return f"{lab} : " + im_formula(it["terms"], names) + (" (pile dessus)" if it["gap"] <= 0.001 else
                                                        f" (à {it['gap'] * 1000:.0f} kHz)")


def pf_suggest(i, freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, max_tx=None, lo=None, hi=None, step=0.025,
               n=5, busy=None, max_check=600, filt=0.0):
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
    base, _ = pf_check(Fo, To, Bo, SPo, TLo, max_tx, FLo)
    base_n = sum(len(x) for x in base)
    grid = np.round(np.arange(math.ceil(lo / step - 1e-9) * step, hi + 1e-9, step), 6)
    grid = grid[np.abs(grid - f0) > 1e-9]
    half = FL[i] / 2.0 + 1e-9 if FL[i] > 0 else np.inf                    # filtre de la candidate
    Fa, Ba = np.asarray(Fo, dtype=float), np.asarray(Bo, dtype=float)
    Ha = np.where(np.asarray(FLo) > 0, np.asarray(FLo) / 2.0 + 1e-9, np.inf) if len(Fo) else np.zeros(0)
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
                    hit = np.abs(g[:, None] - pv[None, :]) - ph[None, :] - bi / 2.0 <= pt[None, :] + 1e-9
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
                    hit = (np.abs(val - vic) - hw - bv / 2.0 <= T2 + 1e-9) & (T2 > 0)
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
                    hit = (np.abs(val - vic) - hw - bv / 2.0 <= T3 + 1e-9) & (T3 > 0)
                    hit &= (np.abs(fj[None, :, None] - vic) > 1e-9) & (np.abs(fk[None, :, None] - vic) > 1e-9)
                    hit &= ((np.abs(g - vic) <= Hv) & (np.abs(fj[None, :, None] - vic) <= Hv)
                            & (np.abs(fk[None, :, None] - vic) <= Hv))
                    bad |= hit.any(axis=(1, 2))
            ok[k0:k0 + 500] &= ~bad
    cand = grid[ok]
    cand = cand[np.lexsort((cand, np.round(np.abs(cand - f0), 6)))]     # le plus proche, puis le plus bas
    out, checked = [], 0
    for c in cand:
        c = round(float(c), 6)
        if busy is not None and busy(c):
            continue
        checked += 1
        if checked > max_check:
            break
        iss, _ = pf_check(Fo + [c], To + [T[i]], Bo + [bi], SPo + [float(SP[i])], TLo + [ti], max_tx,
                          FLo + [float(FL[i])])                                  # vérification exacte
        if iss[-1] or sum(len(x) for x in iss[:-1]) > base_n:
            continue
        out.append((c, c - f0))
        if len(out) >= n:
            break
    return out


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
              max_check=600, guard3=None):
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
        if im3_clash(c, allf, guard, guard3):
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


def scan_write(F, L, fmt="wwb", sep=";", dec=",", funit="MHz", lunit="dbm", header=True, title=""):
    """Écrit un scan : fmt « wwb » (Shure : « 470.000, -98 »), « wsm » (Sennheiser, format supposé d'après
    les exports WSM : kHz et %), « csv » (personnalisé : séparateur, décimale, unités, en-tête)."""
    if fmt == "wwb":
        return wwb_scan_text(F, L)
    if fmt == "wsm":
        out = ["Sennheiser Wireless Systems Manager", f"Scan : {title or 'TinySA Monitor'}", "Receiver : tinySA",
               f"Start : {float(F[0]) * 1000:.0f} kHz", f"Stop : {float(F[-1]) * 1000:.0f} kHz", "",
               "Frequency;RF level (%);RF level;Memory (%);Memory"]
        for f, l in zip(F, L):
            if math.isfinite(float(f)) and math.isfinite(float(l)):
                pct = to_unit(float(l), "pct")
                out.append(f"{float(f) * 1000:.0f};{pct:.1f};{float(l):.1f};{pct:.1f};{float(l):.1f}".replace(".", ","))
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
        """Alarmes à afficher : en cours (non acquittées d'abord, appareil perdu en tête, par priorité), puis
        terminées (récentes d'abord)."""
        cur = sorted(self.active.values(), key=lambda a: (a["acked"], a["kind"] != "APPAREIL", -a["prio"], a["t0"]))
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


# --------------------------------------------------------------------------
# Shows : ce qui appartient à un événement (rappelable d'une année à l'autre), sans les préférences du logiciel
# --------------------------------------------------------------------------
SHOW_EXT = ".tsashow"
SHOW_KEYS = ("bands", "watch", "scenes", "statuses", "scope", "focus", "strong_on", "strong_thr",
             "points", "rbw", "zrbw", "input", "lna", "att", "seg", "offset",
             "thr", "weak_thr", "weak_on", "win", "absent_s", "occ_minutes", "ref_rel", "ref_margin",
             "country", "plan_custom", "dev_names")
SHOW_META = ("name", "venue", "date_from", "date_to", "notes")


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


# --------------------------------------------------------------------------
# Plusieurs tinySA : adresses (USB ou réseau) et répartition des bandes
# --------------------------------------------------------------------------
RELAY_PORT = 5025            # port TCP par défaut du relais réseau (TinySA-Monitor.exe --relais)


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


def calib_offset(F1, L1, F2, L2, snr=10.0, min_pts=5):
    """Écart de lecture entre deux tinySA qui ont balayé la même bande (même antenne / splitter).
    -> (correction à AJOUTER au 2e en dB, nb de points utilisés, base « signaux » | « bruit de fond ») ou None.
    On compare d'abord les signaux vus par les deux (> plancher + snr dB) ; sinon le plancher de bruit."""
    F1, L1, F2, L2 = (np.asarray(x, dtype=float) for x in (F1, L1, F2, L2))
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


def notify_text(a, site=""):
    """Alarme (dict AlarmBook) -> (titre, corps) courts, lisibles sur un écran verrouillé."""
    title = f"⚠ {a['kind']} — {a['name']}"
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
    return title, body


def ntfy_request(server, topic, title, body, prio=2):
    """Requête ntfy (appli gratuite iOS / Android, sans compte) -> (url, en-têtes, données)."""
    url = (server or "https://ntfy.sh").rstrip("/") + "/" + topic.strip().strip("/")
    hdr = {"Title": _hdr_safe(title),
           "Priority": "urgent" if prio >= 2 else "high", "Tags": "rotating_light" if prio >= 2 else "warning"}
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
<li>Dans TinySA Monitor (cette fenêtre) : <b>Service</b> = ntfy, garde le <b>Canal ntfy</b> proposé
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
<li>Clique <b>🔎 Trouver mon chat id</b> : TinySA Monitor demande à Telegram qui a écrit au bot et remplit le
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
APP_ICON_PNG64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAATEUlEQVR42t2beYyc9XnHP8/vveba2cNeH9jG2AZ8BWOKG646CZAmRIHcRk1oEylV/+gf/SN/VaGJAKmlUiK1KFGLohxKVUVqcRqUQloSJVDVAQzmDLbxweFrvbb38u7sXO/xe/rHOzu7Ozvj3bXdlHSkmdE78x6/5/k+9/P8hDYvBeExjNxLAqDfXX01Yj6FlY8AG7H0o2RABJ26SJoXtz8GkJbj1vNkcedPn6NADRhC5DDwCxLzuHz9wNsA+tguh3t32xl3a75kDvEPYOQhLIB+b80ORL6CcjeeKZJA860XIlbSg0URt0ji2x0bSd8iENoJhCdQ+4h87fBLrbS1ZcDUCfrA2gyr9W8x8hcE4lBVSEgAQUXS75ZFNFH5LSLf+r+qgiiKYsTBNxBqgtVv83b5q/JPx2utTJA5xD+6ehWB2U3GuYVSoigWxDSIn01s24Xr9O+/DeQ7MgNFNV17zhVqyfPUwl3y8NGBmUyQOcR75hkCcw0VG4F4c5DttND/S+Rbn9u6VktE1vGo26OE7u3y8OtNJogqwm4M5bUeke4hZ3ZQbhCvMwRFf0eQp5N90oiM61FNXsJM7uTg8YjdWMPuhrUP7TcoOIsnXqXluxMxXBryrcygHfK0sfPNZ3hUk4icu4Ok8A3ZTcJju4w0rb0xLxJjUQw6dfffYeTbq2iqEI4xhPb98vD+lwwAsdyPZwQLCyb+vY58e/uU0uiKIHo/gOijq67BcV8HMg3nIAsiHlJhafO/oIjy3kB+lnSSegcRsFrD2m0u4nyGQLJUNEFw5rf2U79ZRCuIasvDBXAAD8Vp/KqXbO0VQTGkVlvn0fdOnknSD6sJvpslTD7tItzZRH4hfh4BG2HF40B2J8fd9SROFkHxkzJ94SArw5OsjAdxbRkwQIBtLp75kaeVGQbRBEkqYHzAm8mZzsi3fYY0VEHB8ocuKpuIW6LCDmKvCGJjql4f/7H5AU45m1ibcSjmMohAFCccr9V5Y3wUGT9O/8QBtpZfYl34NsaWQQK0sXhRnR95TdVMbMSk28sry+5hy/mXWVo9CRLMFoELIT834pc0y5FNoo+uLSOSW4i+KgaJyzy98X4Orf8id/nDFDwHq2k2IpI+KLLCaCicmow4PTKCDL3JlrE93FDZRzYeA/GweBjVeW2Aotg44fHr7ufAmo9SfPdFvvz2N+muD6PitpEoaR8HtPVcWnZRshcUpRmLEhLUKXCi53quNpPkjFCOQVo4LGJZ6gvLlzpc37ecgVXLODSyg1fPHGHL0NPcNLmHXDwKkkFxUtPcQryqYMXBRFX2rL2PE9feRe7caSJcVMxcFZgP+ZnET51nJesiM1LatnqkDTMmiFrqTpbIZPEELIJIGwFDiBSiGESUNXm4Mp/nTP923hjayP7BO7nx3M+4qfQsTlJBJcVAVJvGzmiCEw1zMn8D+9bvwowNMXl+ki+c/hE9lQHUySNq59f5OVI94zwR486f1bWQZxWNYyZseyM8i/eNS8M0vmBZRvjIlTlO929j3+AGXh/YyR3nHmdj+XXAQcVDkjpiQ2p+Pwd6d/LqktspjYyCuHz43BNsHN07l/iFIt8mYHM7hI1N5KfFP7XGXlzFqZznXHwVdV9xZwrQPMyIFCILK7KGu9cVONx3Kz8buJY3Tv2Su0b/nUJ9iLPZ9bzWcxuHi9vpSUo8fWqMJOfyha4z7Bz8KdbJpbajY2B0AeR1rrt0O7ukdlmbwSEiP36Kk8uu53QI6zIpYcL8rylG1JP0YVv7PDb2rOTZ/i/w/cPXsLx2grHCVfRWTrFr4Ac8PepTr1zBpzdX6a0MIzZCTQaa6C8S+TYSbZq+nZnIt/cIFgGN6Zk8Tr1S451IqNvU0y/kNQWc7xiynsNYNWb/mXHGRs7gL9/AwLqPE5QG+KMT32Zy7Cx/Z2/iwdxL9PqCSerzhMSdIk25YJjtLgz52XxZXX+LF8dGGMv0ccR1uC7bWQp0SoUEAtegKGcn6xwaKjEwXiHvu2zoK7BlZR+93UWe6rmH7/kFfnLwHb7i7OU6Z5B9poc10f4Oa1wk8i3XuLORv3CxIv3XY014DL88TDju847XS79jWeHPZsIU4Y4RPFeox5Yjw5McGZ7gfC1ieSHDzqv6WdWdxTVCNYqo1Op89ob1fOnl1yjlV3Nz1wkY9bHGIx+XGhEhi9d57ZBAzbYB8yDfSHIUl2I4xMroJO+M9+DlfH4jObocJWsg1rQu6RnBGGG8GnF0pMQ7o2WsKut7C9y6dil9WR9ViKwlThRVxcQR3/nFHoZHzvLIfZ/gqaM3ctWR1STikY8mQdwW13MRyOtsNXfb36TzsWIwtsw11d9wJLeN2rlhWL2KV6uGm3NKxnVIFAZLVQ4NTXCmVKMrcNm2soe1PTlynkOcKPXYTuWdKEoh8PnN6SG+818v8Mgff4ob161ibV+Rn2TzjA6epDseB1VUpBFGL1Ln5+YDgOA8+LHeBxdVw2uoQj6psL94C/VYMHFILVegrkKtNMmeY8McGS5RDDzev6aPG67oZVk+AIUoUSw0AygFXGMohzFf/ekzfOx91/DJ664mRugp5FiZM7xweoJRU2Rz6QCOjVFxWpiwUOQ72YBFVG5SNfDpqw9wVeUgB7puIiyVMJ7Hif6lHBmPubYrw8ZlRYqBh1UltkqsaRou0uoZlGzg8w97XmZJPseXb7mekfEJcokln80wVku4shhg1n6WfybgvhPfx0vCNA+Yw4SFNmmmGeZeuILTSQ0E0Zgbx/fwZmEHGIfK6HnEccgt6SMXKF2+Uk9s0wNIh0DBiFCLIj6yaQPLunJYaxExVCbLJN1FymFE4Hns2r6GH5t7+BHKnxz7HsbahiTYxRM/QwJMewN4YW9gVMFkWF/Zz6raO4QmwBihPDxKdXSMAxV4rZyWQ0SYN1KMrbJlRR89GZ8oSRrXKBMT40xWa2R8F8Tw2a0rKOy4hx+v/nyjKHIxxOusMpppX8+fXy0sDk5c5uaxX6ZpMoqIUB4aIR4/z1uR4dWyNrk8X95Qi+KGmjSQEUO9HjIyXqKQTXP/yBo+s3Ul4Y2f42crP4nYEKvSBrR5DOCMJ5vFID/z2KiiJsuWiRdZWzlMXTKzmTA2xruJYV85jf/deSRBRNoEUspkPaQQ+ICkdQdxuHfbaga2f54X+nZikhqqZoG9yrmFVHPx1VsABzep8KHhJzAzeo4iwuTQKNHQCAOx8FwFxmPFW4A6tCSe1OPUtdJQp8RafNflc9vX8+L7vsTJ/AbE1tCpgHw+5Fu8gLmUdpWoRU2Wq0uvsG18L1WTw6S1JsQIlbHz1M+cZTRSnq0YTtbTghjMzwgjEMaWRBWN6miSIAgiQphY+vI+d954HU9uuI/Q5EATdEHIy6xSvrnkXp0KqOHOs//GkvAcsfjN1rEYQ600SeX0IOVqnZfrDm9UFdWFqUSYWKyCo5ZqvY4x0vQc9diypT/Pmt/7IM8s/zBiww4GUeYWTZg+x1xS3R5J4wLj010f5K4z/0Iizuz0D0hqdepnzxFOTHA4cni+AmMx+NJeGqayktBaIqtkXKFWq81hUGKV2zf0c2zzPQxmrkzT5aYt0w6NnNm5wAJtwIU7NqIWa3JsGXuOD557kqqTQ2yC8VzcYoGB8iSnhoapnhshHBribJiqxJvVNBDyZG6ZXwRqUYIj4DsOYRhiVWd5jtgqec+wfetmnr3idrB2RkInFyiXTdNoFpYIzVO3V8GgqMlwx+CP2THy31S8IoX+PpyuPNds3shAeZITIyNEE5NUTg1QK1c4EBp+XRbOhIoLODIzfRbqcYJnDK4R4sSm8w8tQVScKNuWFRjfcBvDwXIkiWbbAm1XJZaZEiAXjXwrM1IjZbj7xA+4pfwCw+U6zz73PPVanWvXr+Po4CAqQlQPKZ0+Q31omJHQsrfmsK8CEw1PMaWptdjiuykDtKOnULK+YcWadbzZvRls3FCDTsi3AneJyLfeWHHxkhofGH6KwFh8P4OoJZfPU41CrLUEvo+IUB07z+SpAWrjExwLlT1lw+tlpZxYAkmDI8+kS/RcD8d0qD0prOzt4mxx7Yy6xYWRn06GLnYyo1OXtmF/JpxuuvtXcuv7C+TyOcbGJ4is5eCpk1zR20s2CMh4PpJYwqFR/HKFuK+Xd02WM6FyNcpYaCn4DvlMBr/QldqAqQRIppMpRXAFqm4+ze9UWxuiHb9dLqpXN08lVpWaXyQxDtlsgCr4rovnOuw7cQpzeogeTyhmArJ+QD4ICBwH13HIdhXI9/Yw1t8P1qEvrDEaC6tdB78REKlqg3AwxkVEOXRmjCAqg8aoeu1bb22O3UW3pOlcXpr5qvldaZPDKhjF81zUy3C78w6BEZ6tL+dUpTJLv6XhlgzQV+zmqv5+lhZ7OF06xKqeAquXdLOyJ09fLkPGdzFArR7yysAoB4+d4YsjrzZiuzZusAMz3MuKPNPpXzXobubAqkrgOiRuhtV2ggecX/Nyfivf7P4Uh84ONZOlJEkIxUWNy+lSmcGJEoXAp79YZGmhi+5cnu5shnwmg+u6xDiMRwn10hifP/lT1o/sR02AUbvg5Mi9vMhPG55q0NvAMo38xHHoDjzepA+rLhuChFW9fRw8cw5pWPPVy1ZwRTSMjB1nwOlhjIBaFPLu0DDHhocJXI9cEFD0Pboc5SpbYnM0yK0TB9lYG0CdYPa8wgWnVmfZgMuA/ExDKg41r6sREqfiKCIUswEDmkesEDtZzkdgkwTXdbFxxJLefj7nVrhr+BeU6KKkLiV8yqQFVK2DrVnyNqRH6yzRGhmNwLgziF9cTcBtO/1xETo/83w1PjW/MN2/SxMDunIBR9TnL+VDlEvdvFk52XRtCpSrk5zuW0JiAro0pItaw6K31PtMai1QB4sHqrPbZYuoCbjtfOPFIN8cX4kmQRxCv6vJgKnZgXwmQ6zwuFyL1BMyWsIYAyKIMdTrNUruUiInwKmNok4eK05Dklp6lVORXKc22QKHt90FGcB5kFcxSFQDcTi58mYOrvsoI91rcWyY/tdwW4Hv4xhDXkLUpFUlay1xkhDGCZXKJJPeOh7b9Gdcf3Yvm4dfx48mUSfbGLrSzmtbNPGd4oBFIy9IWGGobzPPbftTTqzYQewGeHF12hc3av+ZII0Aa3Ea1xsRAs+jEAT05PMs7+5BVTnas5W3erewvHyanSd+zrYzzzemdi9igvxCI7zaLhJcDPIYJKry7uoP8POb76cWFPHjCk4YNaY4ZmfGgR+QCwIK2Sx9hQJ9hQK9uTy5IMBz0iAnThIyNk19z+VW8K+bvsxQ0M+dx55EjdthyOoi9yw0AqFp5dJFIp+ETBau4Klb/orQL5Ctj5MYd04NXERIkoTurgIf3raNjOPiOm4jmbFYVaJ4elIrUUXUEtiETJDhuT/4c9bKOFcf/RXqFdqO1FzUhg1FXZQaQrZjxtTB2stUTTCuce3xZziy9g7K2T6MjXFshLHJbC+gSuB7rFizisroGHEYpeltQxVkaqODMUiQQbI5TKFIxhNWnTtIcXwQjLewMbsFTa4LKFXRv950AkfWEKtOh24Lmb1tlBRtDEnE8JItvLX6NgaXbmG0+0qqmR4iNzvtGmVaGlBFE4u1Nh3ph6Y3cDUmG5bpLp9jxdk3WXdsL1eeegWSGNwgrZQuqhfQHnmMERI94aLsx8gawKaDOouZwFQQF3U9lo4cYum5/eBmKWeXcr5rFRO5ZUxmlxIGBep+gdgJZltyEYxNCMIKfr1EvjJKV3mY4vhpiqUhnNpEulfDzaJuBrH20olPAzOLMQ5xfMAFeRqRj3V0MfNOYDb6hU4WnHSSLF8eIj8xyCpNFjZ4Mev+BowLxkODrmbJTS4H8q1zQsivRB/YdC2uvAaSaYiXdM4OOzCn5Vxtjt3Ixemr0iamv0zETw1Lq9aIud7IQ4eOoDxFYCTdH3SBTlGnmZyWYQVRRaxN3zrzW+c5nvpNO1dyLhl5tXiOYOU/5YcvHE2ddWIfJmz0r23j1E4l5QtOZjD/+Np8C7+cfn7ucTrEE1vF6MNpKP3YLkceOvwSoX2UrOugxAtGftGTGfN1bPjfQz7dKxITeA6x/Uf53gsv665dTjrB/iACN2aQ2rMEznYqcYyI21HnFz2Ts/DQ9LLrfJN4jQk8lzB+laLcxqk1Ibt3WzM16CkPvVwh4hOE9i0yrovV6P8R8hGB5xLZoyTJJ+Xv91bZsrvR1APS3aIY+ZsDJwn1DkK7j5znNTYfJo29uS1ztrpIpBfasblsOq/YxtqznkdsX6Sa3CE/fOnkzI2TzYxlFhMmCh+kZr+FESXrOulEuSYoNmVKq0S8R5BXFKsWNAERAs/BGKUef4vz+iH50YunOm6dbRr1mZunv77190G+gsrHcZ1iWrnU9P1e1PlGLtGYu5lA5EmUR+S7z+9rpa0jA5rB3WO7jNy7O90+/7Xt10ByNyo7sWxDuaK5fX7RQY5cpOrMg7xSw8gAmDdQ3YPlCfn+3rcAdNcuh93tt8//D5b6x0vwpxIIAAAAAElFTkSuQmCC"

# vues de la page web (façon Ontime : une adresse, plusieurs écrans au choix) ; le PC choisit celles qu'il partage
WEB_VIEWS = [("liste", "📋", "Liste", "Toutes les fréquences, filtrables par scène / groupe"),
             ("mur", "🧱", "Mur", "Grandes tuiles lisibles de loin, plein écran"),
             ("spectre", "📈", "Spectre", "Le spectre en direct, avec tes fréquences"),
             ("waterfall", "🌊", "Waterfall", "L'historique du spectre qui défile"),
             ("alarmes", "🔔", "Alarmes", "Conflits et émetteurs absents, à acquitter")]
WEB_VIEW_KEYS = [k for k, *_ in WEB_VIEWS]


def web_views_norm(v):
    """{vue: bool} complet (les vues inconnues sont ignorées, les manquantes sont partagées)."""
    v = v if isinstance(v, dict) else {}
    return {k: bool(v.get(k, True)) for k in WEB_VIEW_KEYS}


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
                        scene=r.get("scene") or "", group=r.get("group") or "",
                        alarm="ABSENT" if r.get("absent") else ("CONFLIT" if r.get("conflict") else "")))
    al = [dict(id=int(a.get("id", 0)), kind=a["kind"], name=a["name"], freq=round(float(a["freq"] or 0), 4), prio=int(a["prio"]),
               acked=bool(a["acked"]), layer=a.get("layer") or "", info=a.get("info") or "", t0=a["t0"])
          for a in alarms if a.get("t_end") is None]
    return dict(rows=out, alarms=al, **info)


WEB_PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d0f13"><title>TinySA Monitor</title>
<link rel="icon" href="data:image/png;base64,__ICON__"><link rel="apple-touch-icon" href="data:image/png;base64,__ICON__">
<style>
:root{--bg:#0d0f13;--panel:#161a21;--panel2:#1c212a;--line:#272d38;--fg:#f2f4f7;--mut:#8b95a5;--acc:#ff9f1c;
--ok:#22c55e;--bad:#ef4444;--warn:#eab308;--abs:#f97316;--none:#3a4150;--r:14px}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
-webkit-tap-highlight-color:transparent}
button,input,select{font:inherit;color:inherit}
.hidden{display:none!important}.mut{color:var(--mut)}
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
.btn.pri{background:var(--acc);color:#111;border-color:var(--acc);width:100%;padding:13px;margin-top:18px;font-size:16px}
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
.c.free{border-left-color:#3b82f6}.t.free{background:#1e3a8a;border-color:#3b82f6}
.c.alarm{background:var(--abs);color:#111;border-color:var(--abs)}
.c .n{font-weight:800;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c .f{color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums}.c.alarm .f,.c.alarm .s{color:#111}
.c .l{font-size:15px;margin-top:3px;font-weight:600}.c .s{color:var(--mut);font-size:12.5px}
.wall{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(var(--tw,200px),1fr))}
.t{border-radius:16px;padding:14px;text-align:center;background:var(--panel2);border:3px solid var(--line);min-height:var(--th,130px);
display:flex;flex-direction:column;justify-content:center}
.t.ok{background:#14532d;border-color:#22c55e}.t.bad{background:#7f1d1d;border-color:#ef4444}
.t.warn{background:#713f12;border-color:#eab308}.t.alarm{background:var(--abs);border-color:#fff;color:#111}
.t .n{font-weight:800;font-size:calc(var(--fs,22px)*1.15);line-height:1.1}.t .f{opacity:.8;font-size:calc(var(--fs,22px)*.62)}
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
 <div class="logo">📡</div><h1 id="lt">TinySA Monitor</h1><p>Surveillance HF en direct</p>
 <label for="ln">Ton nom (pour que la régie sache qui regarde)</label>
 <input class="in" id="ln" maxlength="32" placeholder="ex. Clément — FOH" autocomplete="name">
 <div id="lpw"><label for="lp">Mot de passe</label><input class="in" id="lp" type="password" autocomplete="current-password"></div>
 <button class="btn pri" type="submit" id="lgo">Entrer</button><button class="btn hidden" type="button" id="lcancel" style="width:100%;margin-top:8px">Annuler</button>
 <div class="err" id="le"></div></form></div>
<div id="app" class="hidden">
 <header class="top"><div class="bar"><div class="logo">📡</div>
  <div class="ttl"><b id="t">TinySA Monitor</b><span id="meta" class="mut"></span></div>
  <span id="pill" class="pill"></span><span id="clock" class="clock"></span><button id="me" class="chip" title="Changer de nom"></button></div>
  <nav id="nav"></nav></header>
 <section id="al"></section><main id="view"></main>
</div>
<script>
const VIEWS=__VIEWS__;
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
 if((v==="spectre"||v==="waterfall")&&d.views.includes(v)){try{const s=await api("spectre.json");if(s.ok){spec=await s.json()}}catch(e){}}
 render()}finally{busy=false;$("#stale").style.display=(last&&Date.now()-last>8000)?"block":"none"}}
function clock(){const n=new Date();$("#clock").textContent=n.toLocaleTimeString("fr-FR",{hour12:false})}
setInterval(clock,500);clock();setInterval(tick,1000);tick();
window.addEventListener("hashchange",()=>{render();tick()});
window.addEventListener("resize",()=>{if(mounted==="spectre"||mounted==="waterfall"){wf=null;draw()}else if(mounted==="mur")render()});
// ---------- rendu
function render(){if(!D)return;const st=D.state,v0=route(),v=(v0===""||D.views.includes(v0))?v0:"";
 $("#t").textContent=st.title||"TinySA Monitor";document.title=st.title||"TinySA Monitor";$("#lt").textContent=st.title||"TinySA Monitor";
 $("#meta").textContent=(st.running?"● en surveillance":"○ arrêté")+(st.cycle?" · cycle "+st.cycle:"")+(st.ver?" · v"+st.ver:"");
 const un=st.alarms.filter(a=>!a.acked).length,all=st.alarms.length,p=$("#pill");
 p.className="pill "+(un?"bad":(all?"":"ok"));p.textContent=un?("⚠ "+un+" alarme"+(un>1?"s":"")):(all?all+" acquittée"+(all>1?"s":""):"✔ Tout va bien");
 p.onclick=()=>{if(D.views.includes("alarmes"))location.hash="#/alarmes"};
 $("#me").textContent="👤 "+(D.me||"Invité");
 $("#nav").innerHTML=`<a href="#/" class="${v===""?"on":""}">🏠 Accueil</a>`+D.views.map(k=>`<a href="#/${k}" class="${v===k?"on":""}">${VIEWS[k][0]} ${VIEWS[k][1]}</a>`).join("");
 $("#al").innerHTML=v==="alarmes"?"":st.alarms.filter(a=>!a.acked).slice(0,3).map(alHtml).join("");
 if(mounted!==v){mounted=v;wf=null;mount(v)}update(v)}
function alHtml(a){return `<div class="al${a.acked?" ack":""}"><div class="x">⚠ ${esc(a.kind)} — ${esc(a.name)}<small>${a.freq?a.freq.toFixed(3)+" MHz":""}${a.layer?" · "+esc(a.layer):""}${a.info?" · "+esc(a.info):""}${a.acked?" · acquittée":""}</small></div>${D.ack&&!a.acked?`<button data-id="${a.id}">Acquitter</button>`:""}</div>`}
document.addEventListener("click",e=>{const b=e.target.closest("button[data-id]");if(b)ack(b.dataset.id==="all"?"all":+b.dataset.id)});
async function ack(id){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 let r;try{r=await post("acquitter",{pin:pin,id:id})}catch(e){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);tick();return}
 try{localStorage.removeItem("pin")}catch(x){}
 alert(r.status===429?"Trop d'essais : réessaie dans une minute.":r.status===403?"Code faux (ou acquittement désactivé sur le PC).":"Erreur "+r.status)}
function layers(){return[...new Set(D.state.rows.map(lay).filter(x=>x))].sort()}
function layerSel(id){const k=LS.get("flt","");return `<select class="in" id="${id}"><option value="">Toutes les couches</option>${layers().map(l=>`<option${l===k?" selected":""}>${esc(l)}</option>`).join("")}</select>`}
function keepLayer(id){const s=$("#"+id);if(s)s.onchange=()=>{LS.set("flt",s.value);update(mounted)}}
function inLayer(r){const f=LS.get("flt","");return !f||lay(r)===f||r.scene===f}
function mount(v){const el=$("#view");
 if(v===""){el.innerHTML=`<div class="sum" id="kpi"></div><div class="home">${D.views.map(k=>`<a class="vcard" href="#/${k}"><div class="i">${VIEWS[k][0]}</div><b>${VIEWS[k][1]}</b><span>${VIEWS[k][2]}</span></a>`).join("")}</div><div class="who">Connecté en tant que <b>${esc(D.me||"Invité")}</b>${D.state.ver?" · TinySA Monitor v"+esc(D.state.ver):""}</div>`;return}
 if(v==="liste"){el.innerHTML=`<div class="tools">${layerSel("flt")}<input class="in" id="q" placeholder="🔎 Nom, fréquence…"><label class="sw"><input type="checkbox" id="oo"> Occupées seulement</label></div><div class="grid" id="g"></div>`;
  keepLayer("flt");$("#q").oninput=()=>update(v);$("#oo").onchange=()=>update(v);return}
 if(v==="mur"){el.innerHTML=`<div class="tools">${layerSel("flt")}<label class="sw"><input type="checkbox" id="oo"> Occupées / faibles seulement</label><button class="btn" id="fs">⛶ Plein écran</button></div><div class="wall" id="g"></div>`;
  keepLayer("flt");$("#oo").onchange=()=>update(v);$("#fs").onclick=()=>{const g=$("#view");(g.requestFullscreen?g.requestFullscreen():g.webkitRequestFullscreen&&g.webkitRequestFullscreen())};return}
 if(v==="spectre"||v==="waterfall"){el.innerHTML=`<div class="tools"><select class="in" id="band"></select>${v==="spectre"?'<label class="sw"><input type="checkbox" id="mh" checked> Max hold</label>':""}<label class="sw"><input type="checkbox" id="mk" checked> Mes fréquences</label></div><div class="plot"><canvas id="cv"></canvas><div class="read" id="rd"></div></div><div class="legend" id="lg"></div>`;
  $("#band").onchange=()=>{LS.set("band",$("#band").value);wf=null;draw()};["mh","mk"].forEach(i=>{const c=$("#"+i);if(c)c.onchange=()=>draw()});
  const cv=$("#cv");cv.onpointermove=cv.onpointerdown=e=>readout(e);cv.onpointerleave=()=>{$("#rd").textContent=""};return}
 if(v==="alarmes"){el.innerHTML=`<div class="tools"><b style="flex:1">Alarmes en cours</b><span id="aa"></span></div><div class="alist" id="g"></div>`;return}}
function update(v){const st=D.state;
 if(v===""){const rs=st.rows,occ=rs.filter(r=>r.state==="occ").length,ab=rs.filter(r=>r.alarm).length,k=$("#kpi");
  if(k)k.innerHTML=`<div class="kpi"><b>${rs.length}</b><span>fréquences</span></div><div class="kpi"><b>${rs.filter(r=>r.tone==="ok"||r.tone==="free").length}</b><span>OK / libres</span></div><div class="kpi"><b>${occ}</b><span>avec signal</span></div><div class="kpi"><b style="color:${ab?"var(--bad)":"inherit"}">${ab}</b><span>en alarme</span></div>`;return}
 if(v==="liste"){const q=($("#q").value||"").toLowerCase(),oo=$("#oo").checked;
  $("#g").innerHTML=st.rows.filter(r=>inLayer(r)&&(!oo||r.state==="occ"||r.state==="weak")&&(!q||(r.name+" "+r.freq.toFixed(3)+" "+r.status).toLowerCase().includes(q))).map(r=>`<div class="c ${r.tone}${r.alarm?" alarm":""}"${r.color&&!r.alarm?` style="border-left-color:${r.color}"`:""}><div class="n">${r.alarm?"⚠ ":""}${esc(r.name)}</div><div class="f">${r.freq.toFixed(3)} MHz${r.status?" · "+esc(r.status):""}</div><div class="l">${r.alarm&&!r.state_txt.includes(r.alarm)?esc(r.alarm)+" · ":""}${esc(r.state_txt)}${r.level_txt?" · "+esc(r.level_txt):""}</div><div class="s">${esc(lay(r))}</div></div>`).join("")||'<div class="empty">Aucune fréquence</div>';return}
 if(v==="mur"){const oo=$("#oo").checked,rs=st.rows.filter(r=>inLayer(r)&&(!oo||r.alarm||r.state==="occ"||r.state==="weak")),g=$("#g");
  const W=g.clientWidth||innerWidth,H=Math.max(200,innerHeight-g.getBoundingClientRect().top-20),n=Math.max(1,rs.length);
  let cols=Math.max(1,Math.min(n,Math.round(Math.sqrt(n*W/H/1.4))));const tw=Math.max(140,W/cols-10),th=Math.max(90,Math.min(H/Math.ceil(n/cols)-10,tw*.8));
  g.style.setProperty("--tw",tw+"px");g.style.setProperty("--th",th+"px");g.style.setProperty("--fs",Math.max(13,Math.min(40,th*.17,tw/9))+"px");
  g.innerHTML=rs.map(r=>`<div class="t ${r.tone}${r.alarm?" alarm":""}"${r.color&&!r.alarm&&r.tone!=="none"?` style="background:${r.color}${r.tone==="bad"?"aa":"55"};border-color:${r.color}"`:""}><div class="n">${r.alarm?"⚠ ":""}${esc(r.name)}</div><div class="f">${r.freq.toFixed(3)} MHz</div><div class="l">${esc(r.state_txt)}${r.level_txt?" · "+esc(r.level_txt):""}</div></div>`).join("")||'<div class="empty">Rien à afficher</div>';return}
 if(v==="alarmes"){const al=st.alarms,un=al.filter(a=>!a.acked).length;$("#aa").innerHTML=D.ack&&un>1?'<button class="btn" data-id="all">✔ Tout acquitter</button>':"";
  $("#g").innerHTML=al.map(a=>`<div class="row${a.acked?" ack":""}"><div class="x"><b>⚠ ${esc(a.kind)} — ${esc(a.name)}</b><div class="mut">${a.freq?a.freq.toFixed(3)+" MHz":""}${a.layer?" · "+esc(a.layer):""}${a.info?" · "+esc(a.info):""} · depuis ${new Date(a.t0*1000).toLocaleTimeString("fr-FR",{hour12:false})}${a.acked?" · acquittée":""}</div></div>${D.ack&&!a.acked?`<button class="ackbtn" data-id="${a.id}">Acquitter</button>`:""}</div>`).join("")||'<div class="empty">✔ Aucune alarme en cours</div>';
  if(!D.ack&&al.length)$("#g").insertAdjacentHTML("beforeend",'<div class="who">Acquittement depuis le téléphone désactivé (code PIN à régler sur le PC).</div>');return}
 if(v==="spectre"||v==="waterfall"){const b=$("#band"),bs=(spec&&spec.bands)||[],want=LS.get("band","*");
  const opts='<option value="*">Toutes les bandes</option>'+bs.map(x=>`<option${x.name===want?" selected":""}>${esc(x.name)}</option>`).join("");
  if(b.dataset.o!==opts){b.innerHTML=opts;b.dataset.o=opts;b.value=bs.some(x=>x.name===want)?want:"*"}
  if(spec&&spec.t!==specT){specT=spec.t;if(v==="waterfall")wfAdd()}draw()}}
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
function draw(){const cv=$("#cv");if(!cv||!spec)return;const ss=segs(),sp=span(ss),lg=$("#lg");
 const H=mounted==="spectre"?Math.max(240,Math.min(innerHeight-230,520)):Math.max(260,innerHeight-220);
 const[c,w,h]=setup(cv,H);c.clearRect(0,0,w,h);if(!sp){c.fillStyle="#8b95a5";c.font="15px system-ui";c.textAlign="center";c.fillText(spec.bands.length?"…":"Pas encore de balayage",w/2,h/2);return}
 const[f0,f1]=sp,X=f=>PL+(f-f0)/(f1-f0)*(w-PL-8);
 c.font="11px system-ui";c.fillStyle="#8b95a5";c.strokeStyle="#272d38";c.lineWidth=1;c.textAlign="center";
 ticks(f0,f1,Math.max(3,Math.floor(w/90))).forEach(f=>{const x=X(f);c.beginPath();c.moveTo(x,PT);c.lineTo(x,h-PB);c.stroke();c.fillText(f.toFixed(f1-f0<5?2:(f1-f0<50?1:0)),x,h-8)});
 if(mounted==="waterfall"){wfDraw(c,w,h,f0,f1);marks(c,w,h,f0,f1,PT);lg.innerHTML='<span>Récent en haut · une ligne par balayage (il se remplit tant que la vue est ouverte)</span><span><i style="background:linear-gradient(90deg,#0b1e5b,#1d9bf0,#22c55e,#eab308,#ef4444)"></i>faible → fort</span>';return}
 const lo=-120,hi=Math.max(-20,Math.ceil((Math.max(...ss.flatMap(s=>s.mh||s.l))+5)/10)*10),Y=v=>PT+(hi-v)/(hi-lo)*(h-PT-PB);
 c.textAlign="right";for(let v=lo;v<=hi;v+=10){const y=Y(v);c.strokeStyle="#272d38";c.beginPath();c.moveTo(PL,y);c.lineTo(w-8,y);c.stroke();c.fillText(v,PL-6,y+4)}
 const line=(arr,f,col,lw,fill)=>{c.beginPath();arr.forEach((v,i)=>{const x=X(f[i]),y=Y(Math.max(lo,v));i?c.lineTo(x,y):c.moveTo(x,y)});c.strokeStyle=col;c.lineWidth=lw;c.stroke();
  if(fill){c.lineTo(X(f[f.length-1]),h-PB);c.lineTo(X(f[0]),h-PB);c.closePath();const g=c.createLinearGradient(0,PT,0,h-PB);g.addColorStop(0,"#ff9f1c55");g.addColorStop(1,"#ff9f1c05");c.fillStyle=g;c.fill()}};
 const mh=$("#mh")&&$("#mh").checked;ss.forEach(s=>{if(mh&&s.mh)line(s.mh,s.f,"#ff9f1c55",1,false);line(s.l,s.f,"#ff9f1c",1.6,true)});
 if(D.state.thr!=null){const y=Y(D.state.thr);c.setLineDash([6,4]);c.strokeStyle="#ef4444";c.lineWidth=1.2;c.beginPath();c.moveTo(PL,y);c.lineTo(w-8,y);c.stroke();c.setLineDash([]);c.fillStyle="#ef4444";c.textAlign="left";c.fillText("seuil "+D.state.thr+" dBm",PL+4,y-4)}
 marks(c,w,h,f0,f1,PT);c.fillStyle="#8b95a5";c.textAlign="left";c.fillText("dBm",4,PT-8);
 lg.innerHTML='<span><i style="background:#ff9f1c"></i>en direct</span>'+(mh?'<span><i style="background:#ff9f1c55"></i>max hold</span>':"")+'<span><i style="background:#ef4444"></i>seuil « occupé »</span><span><i style="background:#22c55e"></i>mes fréquences (couleur = état)</span>'}
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
    "hackrf": dict(name="HackRF One", tool="hackrf_sweep", fmin=1.0, fmax=6000.0, bin_min=2445.0, bin_max=5e6,
                   lna=(0, 40, 8), vga=(0, 62, 2), amp=True),
    "rtlsdr": dict(name="RTL-SDR", tool="rtl_power", fmin=24.0, fmax=1766.0, bin_min=1.0, bin_max=2.8e6,
                   lna=(0, 50, 1), vga=None, amp=False),
}


def parse_sdr_addr(s):
    """« hackrf », « hackrf:<n° de série> », « rtlsdr », « rtlsdr:1 » -> (genre, n° de série / index ou ""), sinon None."""
    m = re.fullmatch(r"\s*(hackrf|rtlsdr|rtl-sdr|rtl)\s*(?::\s*([A-Za-z0-9]+))?\s*", str(s or ""), re.I)
    if not m:
        return None
    kind = "hackrf" if m.group(1).lower() == "hackrf" else "rtlsdr"
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
    if serial:
        a += ["-d", serial]
    return a + ["-"]

# ===== PURE-END


# --------------------------------------------------------------------------
# Communication avec le tinySA
# --------------------------------------------------------------------------
class Aborted(Exception):
    """Commande interrompue (bouton Arrêter)."""


class TinySA:
    PROMPT = b"ch>"
    NET_IDLE_MIN = 20.0          # réseau : liaison déclarée muette après ce silence (s), allongé selon le RBW

    def __init__(self, port, baud=115200, trace=None):
        # port : « COM3 » (USB) ou « socket://192.168.1.20:5025 » (réseau, via le relais ou ser2net)
        # baud : ignoré en USB (port COM virtuel) ; ne compte que sur un vrai port série (adaptateur, connecteur)
        self.net = "://" in str(port)
        self.idle = self.NET_IDLE_MIN          # tinySA muet (réseau coupé, appareil figé) : erreur → reconnexion
        self.abort = None                      # fonction : True = abandonner la commande en cours (Arrêter)
        self.trace = trace                     # fonction(texte) : journal des échanges (diagnostic)
        self.ser = serial.serial_for_url(port, int(baud), timeout=0.2)
        self.ser.reset_input_buffer()
        self.cmd("", timeout=5)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def cmd(self, text, timeout=15.0):
        if self.trace is None:
            return self._cmd(text, timeout)
        t0 = time.time()
        self.trace(f">> {text or '(entrée)'}")
        try:
            lines = self._cmd(text, timeout)
        except Exception as e:
            self.trace(f"!! {type(e).__name__} : {e} (après {time.time() - t0:.1f} s)")
            raise
        first = lines[0][:70] if lines else ""
        self.trace(f"<< {len(lines)} ligne(s) en {time.time() - t0:.2f} s" + (f" : {first}" if first else ""))
        return lines

    def _cmd(self, text, timeout=15.0):
        self.ser.reset_input_buffer()
        self.ser.write((text + "\r").encode())
        buf, t0 = b"", time.time()
        t_rx = t0
        while True:
            now = time.time()
            if now - t0 > timeout:
                raise TimeoutError(f"Pas de réponse du tinySA à « {text} »")
            if self.abort is not None and self.abort():
                raise Aborted()
            if self.idle is not None and now - t_rx > self.idle:
                # câble réseau arraché, Wi-Fi coupé, tinySA figé : la liaison ne se ferme pas, elle se tait
                raise TimeoutError(f"tinySA muet depuis {self.idle:.0f} s")
            n = self.ser.in_waiting
            chunk = self.ser.read(n if n else 1)
            if chunk:
                t_rx = time.time()
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

    def expect_scan(self, points, rbw_khz, step_khz=None):
        """Temps de silence toléré pendant un scan (le tinySA ne répond qu'à la fin du segment).
        RBW auto : le tinySA la règle sur le pas ; un pas fin (beaucoup de points) = RBW étroite = scan bien plus
        long. Avant, on supposait toujours 0,05 s / point : avec 10 000 points ou plus le tinySA était déclaré
        « muet » à tort → liaison perdue (retour de Clément)."""
        if rbw_khz is None and step_khz:
            rbw_khz = auto_rbw(step_khz)
        per_pt = 0.05 if rbw_khz is None else max(0.002, 3.0 / max(rbw_khz, 0.1))
        self.idle = self.NET_IDLE_MIN + points * per_pt

    def scan(self, start_hz, stop_hz, points):
        """Renvoie (freqs Hz ou None, niveaux dBm)."""
        lines = self.cmd(f"scan {int(start_hz)} {int(stop_hz)} {int(points)} 3", timeout=900)
        freqs, levels = parse_scan_lines(lines)
        if not len(levels):
            raise RuntimeError("Le tinySA n'a renvoyé aucune mesure (scan).")
        return freqs, levels


# --------------------------------------------------------------------------
# V8 : SDR (HackRF One, RTL-SDR) vus comme un tinySA, par leur outil de balayage officiel
# --------------------------------------------------------------------------
SDR_TOOL_DIRS = [r"C:\Program Files\PothosSDR\bin", r"C:\Program Files (x86)\PothosSDR\bin",
                 r"C:\Program Files\HackRF\bin", r"C:\Program Files\rtl-sdr\bin", "/usr/bin", "/usr/local/bin",
                 "/opt/homebrew/bin"]


def find_sdr_tool(name, extra_dir=""):
    """Chemin de hackrf_sweep / rtl_power : dossier choisi, à côté de l'appli (et ./outils), PATH, dossiers
    d'installation habituels (PothosSDR…). -> chemin ou None."""
    exe = name + (".exe" if sys.platform.startswith("win") else "")
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for d in [extra_dir, str(here), str(here / "outils"), str(here / "tools")]:
        if d and (Path(d) / exe).is_file():
            return str(Path(d) / exe)
    w = shutil.which(name)
    if w:
        return w
    for d in SDR_TOOL_DIRS:
        if (Path(d) / exe).is_file():
            return str(Path(d) / exe)
    return None


class SDRSweep:
    """Un SDR qui se comporte comme un TinySA pour le ScanWorker : l'outil de balayage tourne en continu sur
    toutes les bandes (une seule commande), un fil lit ses lignes (SweepAccum) ; scan(a, z, pts) rend le dernier
    passage complet rééchantillonné (max par cellule). Outil arrêté (SDR débranché) ou muet : erreur → le worker
    reconnecte comme pour un tinySA. Niveaux non étalonnés en dBm : offset / calibration avec un tinySA."""
    PROMPT = None

    def __init__(self, addr, tool_dir="", trace=None, tool=None):
        self.kind, self.serial = parse_sdr_addr(addr)
        self.spec = SDR_KINDS[self.kind]
        exe = tool if tool is not None else find_sdr_tool(self.spec["tool"], tool_dir)
        if exe is None:
            raise RuntimeError(f"{self.spec['tool']} introuvable : installe les outils {self.spec['name']} "
                               f"(PothosSDR sous Windows) ou indique leur dossier dans Outils › 📡 Réglages SDR.")
        self.exe, self.trace, self.abort = exe, trace, None
        self.idle = 30.0
        self.proc, self.key, self.rbw = None, None, None
        self.acc, self.lock = SweepAccum(), threading.Lock()
        self.err = deque(maxlen=30)
        self.served = {}

    def _t(self, txt):
        if self.trace is not None:
            self.trace(txt)

    def version(self):
        name = self.exe if isinstance(self.exe, str) else " ".join(map(str, self.exe))
        return f"{self.spec['name']} · {os.path.basename(str(name))}" + (f" · {self.serial}" if self.serial else "")

    def try_cmd(self, text):
        return True, ""

    def set_rbw(self, khz):
        self.rbw = khz
        return True, ""

    def set_input(self, high):
        return True, ""

    def expect_scan(self, points, rbw_khz, step_khz=None):
        self.idle = 30.0 + points * 0.0005

    def configure(self, bands, rbw_khz, gains):
        """Bandes du cycle -> (re)lance l'outil si les plages, la case ou les gains ont changé."""
        rng = sdr_ranges([(b["start_hz"], b["stop_hz"]) for b in bands], 10 if self.kind == "hackrf" else 1,
                         self.spec["fmin"], self.spec["fmax"])
        if not rng:
            return
        bw = sdr_bin_hz(self.kind, bands, rbw_khz)
        g = dict(lna=24, vga=20, amp=False)
        g.update(gains or {})
        key = (tuple(rng), bw, g["lna"], g["vga"], bool(g["amp"]))
        if key == self.key and self.proc is not None and self.proc.poll() is None:
            return
        self.key = key
        self._start(sdr_cmd(self.kind, self.exe, rng, bw, g["lna"], g["vga"], g["amp"], self.serial))

    def _start(self, argv):
        self._stop()
        with self.lock:
            self.acc = SweepAccum()
        self.served = {}
        self._t("lancement : " + " ".join(str(x) for x in argv))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen([str(x) for x in argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL, text=True, bufsize=1, creationflags=flags)
        proc = self.proc
        threading.Thread(target=self._read_out, args=(proc,), daemon=True).start()
        threading.Thread(target=self._read_err, args=(proc,), daemon=True).start()

    def _read_out(self, proc):
        acc = self.acc
        try:
            for line in proc.stdout:
                it = sweep_line(line)
                if it is not None:
                    with self.lock:
                        acc.feed(it)
        except Exception:  # noqa: BLE001 — processus tué pendant la lecture
            pass

    def _read_err(self, proc):
        try:
            for line in proc.stderr:
                line = line.strip()
                if line:
                    self.err.append(line)
                    self._t("outil : " + line[:160])
        except Exception:  # noqa: BLE001
            pass

    def scan(self, start_hz, stop_hz, points):
        """-> (freqs Hz, niveaux dB) du dernier passage complet pas encore servi pour cette plage."""
        if self.proc is None:
            raise RuntimeError(f"{self.spec['tool']} pas lancé (aucune bande ?)")
        key = (round(start_hz), round(stop_hz), int(points))
        need = self.served.get(key, 0)
        t0 = time.time()
        while True:
            with self.lock:
                passes, snap = self.acc.passes, self.acc.snapshot()
            if snap is not None and passes > need:
                break
            if self.abort is not None and self.abort():
                raise Aborted()
            if self.proc.poll() is not None:
                time.sleep(0.1)                          # laisse le fil d'erreur lire la dernière ligne
                why = self.err[-1] if self.err else f"code {self.proc.returncode}"
                raise RuntimeError(f"{self.spec['tool']} s'est arrêté ({why}) — {self.spec['name']} débranché ?")
            if time.time() - t0 > self.idle:
                raise TimeoutError(f"{self.spec['name']} muet depuis {self.idle:.0f} s")
            time.sleep(0.02)
        self.served[key] = passes
        F, L = snap
        x = np.linspace(start_hz, stop_hz, int(points))
        return x, resample_max(F, L, start_hz, stop_hz, int(points))

    def _stop(self):
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:  # noqa: BLE001
                pass

    def close(self):
        self._stop()


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
    link = Signal(bool)                            # liaison perdue (False) / retrouvée (True)

    RETRY_S = 5

    def __init__(self, port, demo, get_cfg, get_ver, label=""):
        super().__init__()
        self.port, self.demo = port, demo
        self.get_cfg, self.get_ver = get_cfg, get_ver
        self.label = label                         # « tinySA 2 » quand il y a plusieurs appareils
        self.retry_first = False                   # True : réessaie même si la toute 1re connexion échoue
        self.rng = np.random.default_rng()
        self.demo_carriers = {}
        self.seg_auto = 290
        self.ultra = False                         # tinySA Ultra (une seule prise, mode « ultra » > 800 MHz)
        self.baud = 115200
        self.trace = deque(maxlen=800)             # derniers échanges avec le tinySA (diagnostic)
        self.sdr = parse_sdr_addr(port) is not None    # V8 : HackRF / RTL-SDR par leur outil de balayage
        self.sdr_dir, self.sdr_tool = "", None          # dossier des outils ; sdr_tool : commande imposée (tests)
        self.get_sdr = lambda: {}                       # gains LNA / VGA / ampli
        self.st = dict(rbw="?", front="?", high=None)
        self.dev = None

    def force_close(self):
        """Arrêt qui traîne (tinySA qui ne répond plus) : on ferme le port depuis l'extérieur."""
        d = self.dev
        if d is not None:
            d.close()

    def _say(self, txt):
        return f"{self.label} : {txt}" if self.label else txt

    def _tr(self, txt):
        self.trace.append(f"{datetime.now():%H:%M:%S.%f}"[:-3] + " " + txt)

    def run(self):
        """Balaye en boucle. Liaison perdue (câble, réseau) : signal link(False), nouvel essai toutes les
        RETRY_S secondes, link(True) au retour. Échec de la toute 1re connexion : error (sauf retry_first)."""
        was_up, lost, fails = False, False, 0
        while not self.isInterruptionRequested():
            dev = None
            try:
                if not self.demo and self.sdr:
                    self._tr(f"SDR {self.port}")
                    dev = SDRSweep(self.port, self.sdr_dir, self._tr, self.sdr_tool)
                    dev.abort = self.isInterruptionRequested
                    self.dev = dev
                    self.info.emit(dev.version())
                    self.status.emit(self._say(f"{dev.spec['name']} prêt ({dev.spec['tool']})"))
                elif not self.demo:
                    self._tr(f"connexion à {self.port} ({self.baud} bauds)")
                    dev = TinySA(self.port, self.baud, self._tr)
                    dev.abort = self.isInterruptionRequested
                    self.dev = dev
                    ver = dev.version()
                    self.ultra = "tinysa4" in ver.lower()
                    if self.ultra:
                        self.seg_auto = 450
                    self.info.emit(ver or "tinySA")
                    self.status.emit(self._say(f"Connecté sur {self.port}"))
                else:
                    self.info.emit("Mode démo")
                    self.status.emit(self._say("Mode démo (signaux simulés)"))
                self.st = dict(rbw="?", front="?", high=None)
                was_up, fails = True, 0
                if lost:
                    lost = False
                    self.link.emit(True)
                self._loop(dev)
                return
            except Exception as e:  # noqa: BLE001
                if self.isInterruptionRequested():
                    return                                  # Arrêter : pas une panne
                if not was_up and not self.retry_first:
                    self.error.emit(self._say(str(e)))
                    return
                if not lost:
                    lost = True
                    self.link.emit(False)
                fails += 1
                self._tr(f"liaison perdue : {e}")
                hint = (" · le tinySA semble figé : débranche / rebranche son USB (ou éteins-le / rallume-le)"
                        if fails >= 3 else "")
                self.status.emit(self._say(f"⚠ liaison perdue ({e}) — nouvel essai dans {self.RETRY_S} s{hint}"))
                for _ in range(self.RETRY_S * 10):
                    if self.isInterruptionRequested():
                        return
                    self.msleep(100)
            finally:
                self.dev = None
                if dev is not None:
                    dev.close()

    def _loop(self, dev):
        while not self.isInterruptionRequested():
            cfg = self.get_cfg()
            bands = [b for b in cfg["bands"] if b["enabled"]]
            if not bands:
                if not self.label:
                    self.status.emit("Aucune bande active")
                self.msleep(300)
                continue
            if dev is not None:
                self._apply_settings(dev, cfg)
                if hasattr(dev, "configure"):
                    dev.configure(bands, cfg["rbw"], self.get_sdr())
                self._tr("cycle : " + ", ".join(f"{b['name']} {b['start_hz'] / 1e6:g}–{b['stop_hz'] / 1e6:g} MHz "
                                                f"{int(b['n'])} pts" for b in bands)
                         + f" · RBW {cfg['rbw'] or 'auto'} · entrée {cfg['input']}")
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
        seg = 10 ** 7 if self.sdr else (cfg["seg"] or self.seg_auto)     # SDR : une bande d'un coup
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
                want = input_plan(self.ultra, cfg["input"], a)
                if want is not None and (want == "high") != self.st["high"]:
                    high = want == "high"
                    ok, msg = dev.set_input(high)
                    self.st["high"] = high
                    if not ok:
                        self.status.emit(f"⚠ Changement d'entrée refusé — {msg}")
                    self._apply_front(dev, cfg)
                if self.ultra and a >= 800e6 and not self.st.get("ultra"):
                    dev.try_cmd("ultra on")                # au-delà de 800 MHz (sans effet si déjà actif)
                    self.st["ultra"] = True
                dev.expect_scan(pts, cfg["rbw"], (z - a) / max(1, pts - 1) / 1e3)
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
        for fc, bw in cfg.get("demo_blocks", ()):        # porteur large Spectera / WMAS : plateau
            m = (fr >= (fc - bw / 2) * 1e6) & (fr <= (fc + bw / 2) * 1e6)
            if m.any():
                lv[m] = np.maximum(lv[m], -68 + self.rng.normal(0, 1.5, int(m.sum())))
        t = time.time()
        for pos, amp, w, ph in car:
            if fr[0] - 2e5 <= pos <= fr[-1] + 2e5 and np.sin(t * w + ph) > -0.2:
                d = (fr - pos) / 100e3
                lv = np.maximum(lv, amp - 12 * d ** 2 + self.rng.normal(0, 0.8, len(fr)))
        return lv


# --------------------------------------------------------------------------
# Relais réseau : partage un tinySA branché en USB sur un autre PC
# --------------------------------------------------------------------------
def local_ips():
    """Adresses IPv4 de ce PC sur le réseau local (pour les afficher à l'utilisateur)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # aucun paquet envoyé : sert juste à choisir l'interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


class SerialRelay(threading.Thread):
    """Relaie les octets entre un port série (le tinySA) et UN client TCP (TinySA Monitor sur l'autre PC).
    Un nouveau client remplace l'ancien (reconnexion après une coupure réseau). Port USB débranché :
    réouverture automatique toutes les 2 s."""

    def __init__(self, port, tcp_port=RELAY_PORT, host="0.0.0.0", opener=None):
        super().__init__(daemon=True)
        self.port, self.tcp_port, self.host = port, int(tcp_port), host
        self.opener = opener or (lambda p: serial.serial_for_url(p, 115200, timeout=0.05))
        self.stop_evt, self.ready = threading.Event(), threading.Event()
        self.client, self.error, self.serial_ok = None, "", False
        self.rx = self.tx = 0                     # octets tinySA → réseau / réseau → tinySA

    def stop(self):
        self.stop_evt.set()

    def _open_serial(self):
        try:
            ser = self.opener(self.port)
            self.serial_ok, self.error = True, ""
            return ser
        except Exception as e:  # noqa: BLE001
            self.serial_ok, self.error = False, f"Port {self.port} : {e}"
            return None

    def run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name != "nt":      # sous Windows, SO_REUSEADDR laisserait deux programmes prendre le même port
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.tcp_port))
            srv.listen(2)
            self.tcp_port = srv.getsockname()[1]
        except OSError as e:
            self.error = f"Port réseau {self.tcp_port} indisponible : {e}"
            self.ready.set()
            return
        ser, conn = self._open_serial(), None
        self.ready.set()
        try:
            while not self.stop_evt.is_set():
                if ser is None:
                    if self.stop_evt.wait(2.0):
                        break
                    ser = self._open_serial()
                    continue
                socks = [srv] + ([conn] if conn is not None else [])
                rd, _, _ = select.select(socks, [], [], 0.01)
                if srv in rd:                      # nouveau client : il remplace l'ancien
                    new, addr = srv.accept()
                    new.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    if conn is not None:
                        conn.close()
                    conn, self.client = new, addr[0]
                    try:
                        ser.reset_input_buffer()
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    if conn is not None and conn in rd:
                        data = conn.recv(4096)
                        if not data:
                            conn.close()
                            conn, self.client = None, None
                        else:
                            ser.write(data)
                            self.tx += len(data)
                    n = ser.in_waiting
                    if n:
                        data = ser.read(n)
                        if conn is not None:
                            conn.sendall(data)
                            self.rx += len(data)
                except (OSError, socket.error) as e:
                    if conn is not None and isinstance(e, (ConnectionError, socket.timeout)):
                        conn.close()
                        conn, self.client = None, None
                    else:                          # erreur côté USB : on rouvre le port
                        self.serial_ok, self.error = False, f"Port {self.port} : {e}"
                        try:
                            ser.close()
                        except Exception:  # noqa: BLE001
                            pass
                        ser = None
                except Exception as e:  # noqa: BLE001   (serial.SerialException)
                    self.serial_ok, self.error = False, f"Port {self.port} : {e}"
                    try:
                        ser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    ser = None
        finally:
            for x in (conn, srv, ser):
                try:
                    if x is not None:
                        x.close()
                except Exception:  # noqa: BLE001
                    pass
            self.client = None


class Notifier:
    """Envoie les alertes sur téléphone sans jamais bloquer l'appli : file d'attente + fil séparé, 3 essais."""

    def __init__(self, sender=None, retry_s=3.0):
        self.q = queue.Queue(maxsize=50)
        self.sender = sender or self._http
        self.retry_s = retry_s
        self.last_error, self.sent = "", 0
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def _http(url, hdr, data):
        req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()

    def post(self, req):
        try:
            self.q.put_nowait(req)
        except queue.Full:
            self.last_error = "trop d'alertes en attente (pas de réseau ?)"

    def _run(self):
        while True:
            req = self.q.get()
            for k in range(3):
                try:
                    self.sender(*req)
                    self.sent += 1
                    self.last_error = ""
                    break
                except Exception as e:  # noqa: BLE001
                    self.last_error = str(e)
                    time.sleep(self.retry_s * (k + 1))


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"     # Windows : sinon un port déjà pris « marche » quand même
    daemon_threads = True


class WebServer(threading.Thread):
    """Page web de l'équipe (façon Ontime : une adresse, plusieurs vues).
    GET  « / » page · « /etat.json » état (+ qui je suis, vues partagées) · « /spectre.json » spectre allégé
    POST « /connexion » {name, password} → cookie de session · « /acquitter » {pin, id | "all"}.
    get_cfg() -> {password, views} (lu à chaque requête : les réglages du PC s'appliquent tout de suite).
    Sans mot de passe tout le monde entre ; avec, il faut s'être connecté (5 essais faux → bloqué 1 min)."""

    COOKIE = "tsm"

    def __init__(self, port, get_json, host="0.0.0.0", get_pin=None, on_ack=None, get_spec=None, get_cfg=None):
        super().__init__(daemon=True)
        self.port, self.host, self.get_json = int(port), host, get_json
        self.get_pin, self.on_ack = get_pin or (lambda: ""), on_ack
        self.get_spec = get_spec or (lambda: b'{"bands":[]}')
        self.get_cfg = get_cfg or (lambda: {})
        self.guard, self.login_guard, self._lock = PinGuard(), PinGuard(), threading.Lock()
        self.clients = ClientBook()
        self.httpd, self.error = None, ""
        self.ready = threading.Event()

    def cfg(self):
        c = dict(self.get_cfg() or {})
        return dict(password=str(c.get("password", "") or ""), views=web_views_norm(c.get("views")))

    def client_list(self):
        with self._lock:
            return self.clients.listing(time.time())

    def watching(self, views):
        with self._lock:
            return self.clients.watching(views, time.time())

    def revoke_all(self):
        with self._lock:
            self.clients.revoke_all()

    def rename(self, token, name):
        with self._lock:
            return self.clients.rename(token, name) is not None

    def identify(self, token):
        with self._lock:
            return self.clients.identify(token, time.time()) is not None

    def run(self):
        owner = self

        class H(BaseHTTPRequestHandler):
            def _send(self, code, body, ctype, extra=()):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj, extra=()):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8", extra)

            def _token(self):
                for part in (self.headers.get("Cookie") or "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == owner.COOKIE and re.fullmatch(r"[0-9a-f]{32}", v or ""):
                        return v
                return ""

            def _who(self, view=""):
                """-> (autorisé, entrée du client ou None)."""
                tok, cfg = self._token(), owner.cfg()
                with owner._lock:
                    e = owner.clients.touch(tok, self.client_address[0], view, time.time()) if tok else None
                    e = dict(e) if e else None
                return (e is not None or not cfg["password"]), e

            def _body(self):
                n = int(self.headers.get("Content-Length", 0) or 0)
                req = json.loads(self.rfile.read(min(max(n, 0), 4096)).decode("utf-8")) if n > 0 else {}
                if not isinstance(req, dict):
                    raise ValueError
                return req

            def do_GET(self):
                path, _, qs = self.path.partition("?")
                view = next((v for k, _, v in (p.partition("=") for p in qs.split("&")) if k == "v"), "")
                view = view if view in WEB_VIEW_KEYS else ""
                if path in ("/", "/index.html"):
                    self._send(200, WEB_PAGE.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if path not in ("/etat.json", "/spectre.json"):
                    self.send_error(404)
                    return
                ok, me = self._who(view)
                cfg = owner.cfg()
                if not ok:
                    self._json(401, dict(login=True, password=True))
                    return
                if path == "/spectre.json":
                    if not (cfg["views"]["spectre"] or cfg["views"]["waterfall"]):
                        self._json(403, dict(error="vue non partagée"))
                        return
                    self._send(200, owner.get_spec(), "application/json; charset=utf-8")
                    return
                head = dict(me=None if me is None else me["name"], password=bool(cfg["password"]),
                            ident=bool(me and me.get("ident", 0) > time.time()),
                            views=[k for k in WEB_VIEW_KEYS if cfg["views"][k]],
                            ack=len(str(owner.get_pin() or "").strip()) >= 4)
                body = (json.dumps(head, ensure_ascii=False)[:-1] + ',"state":').encode("utf-8") + owner.get_json() + b"}"
                self._send(200, body, "application/json; charset=utf-8")

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                if path == "/connexion":
                    try:
                        req = self._body()
                    except (ValueError, UnicodeDecodeError):
                        self._json(400, dict(error="requête invalide"))
                        return
                    pw = owner.cfg()["password"]
                    if pw:
                        with owner._lock:
                            res = owner.login_guard.check(pw, req.get("password"), self.client_address[0], time.time())
                        if res != "ok":
                            self._json(429 if res == "locked" else 403, dict(error=res))
                            return
                    tok = os.urandom(16).hex()
                    with owner._lock:
                        e = owner.clients.login(tok, req.get("name"), self.client_address[0],
                                                self.headers.get("User-Agent", ""), time.time())
                        name = e["name"]
                    self._json(200, dict(ok=True, name=name), [(
                        "Set-Cookie", f"{owner.COOKIE}={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200")])
                    return
                if path == "/renommer":
                    tok = self._token()
                    try:
                        req = self._body()
                    except (ValueError, UnicodeDecodeError):
                        self._json(400, dict(error="requête invalide"))
                        return
                    with owner._lock:
                        e = owner.clients.rename(tok, req.get("name")) if tok else None
                        name = e["name"] if e else None
                    if name is None:
                        self._json(401, dict(login=True))
                        return
                    self._json(200, dict(ok=True, name=name))
                    return
                if path != "/acquitter" or owner.on_ack is None:
                    self.send_error(404)
                    return
                ok, _me = self._who()
                if not ok:
                    self._json(401, dict(login=True))
                    return
                try:
                    req = self._body()
                    target = req.get("id")
                    if not (target == "all" or (isinstance(target, int) and not isinstance(target, bool))):
                        raise ValueError
                except (ValueError, AttributeError, UnicodeDecodeError):
                    self._json(400, dict(error="requête invalide"))
                    return
                with owner._lock:
                    res = owner.guard.check(owner.get_pin(), req.get("pin"), self.client_address[0], time.time())
                if res != "ok":
                    self._json(429 if res == "locked" else 403, dict(error=res))
                    return
                owner.on_ack(target)
                self._json(200, dict(ok=True))

            def log_message(self, *a):
                pass

        try:
            self.httpd = _HTTPServer((self.host, self.port), H)
            self.port = self.httpd.server_address[1]
        except OSError as e:
            self.error = f"Port {self.port} indisponible : {e}"
            self.ready.set()
            return
        self.ready.set()
        self.httpd.serve_forever(poll_interval=0.3)

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()


class AlertsDialog(QtWidgets.QDialog):
    """Réglages : alertes sur téléphone (ntfy / Telegram) et page web en lecture seule."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Alertes téléphone et page web")
        self.resize(580, 680)
        n, w = owner.notify_cfg, owner.web_cfg
        nb = QtWidgets.QGroupBox("📣 Alertes sur téléphone")
        nf = QtWidgets.QFormLayout(nb)
        self.mode = QtWidgets.QComboBox()
        for k, t in NOTIFY_MODES:
            self.mode.addItem(t, k)
        self.mode.setCurrentIndex(max(0, self.mode.findData(n["mode"])))
        self.service = QtWidgets.QComboBox()
        self.service.addItem("ntfy (appli gratuite, sans compte)", "ntfy")
        self.service.addItem("Telegram (bot)", "telegram")
        self.service.setCurrentIndex(max(0, self.service.findData(n["service"])))
        self.server = QtWidgets.QLineEdit(n["server"])
        self.topic = QtWidgets.QLineEdit(n["topic"] or f"tinysa-{os.urandom(4).hex()}")
        self.topic.setToolTip("Nom du « canal » ntfy : choisis-le long et difficile à deviner (toute personne qui le\n"
                              "connaît peut lire les alertes). Abonne-toi au même nom dans l'appli ntfy du téléphone.")
        self.tg_token = QtWidgets.QLineEdit(n["tg_token"])
        self.tg_token.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.tg_chat = QtWidgets.QLineEdit(n["tg_chat"])
        self.site = QtWidgets.QLineEdit(n["site"])
        self.site.setPlaceholderText("ex. Festival X — Grande scène")
        test = QtWidgets.QPushButton("Envoyer une alerte de test")
        test.setToolTip("Envoie une alerte d'essai avec les réglages ci-dessus (sans les enregistrer).")
        test.clicked.connect(lambda *_: self.send_test())
        tuto = QtWidgets.QPushButton("📖 Tuto pas à pas")
        tuto.setToolTip("Comment installer ntfy ou créer un bot Telegram, étape par étape.")
        tuto.clicked.connect(lambda *_: self.show_tuto())
        self.find_chat = QtWidgets.QPushButton("🔎 Trouver mon chat id")
        self.find_chat.setToolTip("Après avoir écrit un message à ton bot (ou dans le groupe où il est) : demande à\n"
                                  "Telegram qui lui a écrit et remplit le chat id.")
        self.find_chat.clicked.connect(lambda *_: self.fetch_chat_id())
        self.n_lbl = QtWidgets.QLabel("")
        self.n_lbl.setWordWrap(True)
        help_n = QtWidgets.QLabel(
            "<b>ntfy</b> : installe l'appli ntfy (iOS / Android), « S'abonner » au nom de canal ci-dessous. "
            "<b>Telegram</b> : crée un bot avec @BotFather (jeton), écris-lui un message, puis récupère ton "
            "identifiant de discussion (chat id). Il faut une connexion Internet (4G, wifi du site…). "
            "Détails : « 📖 Tuto pas à pas ».")
        help_n.setWordWrap(True)
        nf.addRow(help_n)
        nf.addRow(tuto)
        nf.addRow("Envoyer :", self.mode)
        nf.addRow("Service :", self.service)
        nf.addRow("Serveur ntfy :", self.server)
        nf.addRow("Canal ntfy :", self.topic)
        nf.addRow("Jeton du bot :", self.tg_token)
        chat_row = QtWidgets.QHBoxLayout()
        chat_row.addWidget(self.tg_chat, 1)
        chat_row.addWidget(self.find_chat)
        nf.addRow("Chat id :", chat_row)
        nf.addRow("Nom du site :", self.site)
        nf.addRow(test)
        nf.addRow(self.n_lbl)
        self.service.currentIndexChanged.connect(lambda *_: self._svc())
        wb = QtWidgets.QGroupBox("🌐 Page web pour l'équipe (réseau local)")
        wf = QtWidgets.QFormLayout(wb)
        self.web_on = QtWidgets.QCheckBox("Activer la page web")
        self.web_on.setChecked(bool(w["on"]))
        self.web_port = QtWidgets.QSpinBox()
        self.web_port.setRange(1024, 65535)
        self.web_port.setValue(int(w["port"]))
        self.web_pw = QtWidgets.QLineEdit(str(w.get("password", "")))
        self.web_pw.setPlaceholderText("vide = ouvert à tout le réseau")
        self.web_pw.setMaxLength(40)
        self.web_pw.setToolTip("Mot de passe demandé pour ouvrir la page (en plus du nom de la personne).\n"
                               "Le changer déconnecte tout le monde.")
        self.view_chks = {}
        vbox = QtWidgets.QWidget()
        vfl = FlowLayout(vbox)
        cur_v = web_views_norm(w.get("views"))
        for k, ic, t, d in WEB_VIEWS:
            cb = QtWidgets.QCheckBox(f"{ic} {t}")
            cb.setChecked(cur_v[k])
            cb.setToolTip(d + "\nDécoché : la vue n'apparaît pas sur la page.")
            self.view_chks[k] = cb
            vfl.addWidget(cb)
        self.clients = QtWidgets.QListWidget()
        self.clients.setMaximumHeight(110)
        self.clients.setToolTip("Les personnes qui ont la page ouverte (nom choisi, adresse, vue regardée).\n"
                                "Clic sur une ligne, puis « Renommer » ou « Identifier ».")
        self._sel_tok = None
        self.clients.itemSelectionChanged.connect(self._remember_sel)
        self.ren_btn = QtWidgets.QPushButton("✏ Renommer…")
        self.ren_btn.setToolTip("Change le nom du client choisi (il le voit tout de suite sur sa page).")
        self.ren_btn.clicked.connect(lambda *_: self.rename_client())
        self.id_btn = QtWidgets.QPushButton("👋 Identifier")
        self.id_btn.setToolTip("Fait clignoter l'écran du client choisi pendant 8 s : pratique pour savoir quelle\n"
                               "tablette / quel téléphone est lequel.")
        self.id_btn.clicked.connect(lambda *_: self.identify_client())
        self.kick_btn = QtWidgets.QPushButton("Déconnecter tout le monde")
        self.kick_btn.setToolTip("Oublie toutes les connexions : avec un mot de passe, chacun doit se reconnecter.")
        self.kick_btn.clicked.connect(lambda *_: (owner.web.revoke_all() if owner.web is not None else None,
                                                  self.refresh_clients()))
        self._ct = QtCore.QTimer(self)
        self._ct.timeout.connect(self.refresh_clients)
        self._ct.start(2000)
        self.web_pin = QtWidgets.QLineEdit(str(w.get("pin", "")))
        self.web_pin.setPlaceholderText("vide = lecture seule")
        self.web_pin.setMaxLength(12)
        self.web_pin.setToolTip("Code (4 caractères ou plus) demandé sur le téléphone pour acquitter une alarme.\n"
                                "Vide : la page reste en lecture seule. 5 codes faux → l'adresse est bloquée 1 min.")
        self.w_lbl = QtWidgets.QLabel("")
        self.w_lbl.setWordWrap(True)
        self.w_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        help_w = QtWidgets.QLabel("Sur un téléphone ou un PC du même réseau, ouvre l'adresse affichée : état des "
                                  "fréquences et alarmes, filtre par scène / groupe, rafraîchi chaque seconde. "
                                  "Vues au choix (liste, mur, spectre, waterfall, alarmes) ; chacun entre son nom, tu "
                                  "vois qui est connecté. Mot de passe pour fermer l'accès, code PIN pour pouvoir "
                                  "acquitter depuis le téléphone. Tout passe en clair sur le réseau : à n'activer que "
                                  "sur un réseau de confiance (réseau de prod, pas le Wi-Fi public).")
        help_w.setWordWrap(True)
        wf.addRow(help_w)
        wf.addRow(self.web_on)
        wf.addRow("Port :", self.web_port)
        wf.addRow("Mot de passe :", self.web_pw)
        wf.addRow("Code PIN (acquitter) :", self.web_pin)
        wf.addRow("Vues partagées :", vbox)
        wf.addRow(self.w_lbl)
        wf.addRow("Connectés :", self.clients)
        cr = QtWidgets.QHBoxLayout()
        for b_ in (self.ren_btn, self.id_btn, self.kick_btn):
            cr.addWidget(b_)
        wf.addRow(cr)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(nb)
        lay.addWidget(wb)
        lay.addStretch(1)
        lay.addWidget(bb)
        self._svc()
        self.refresh()

    def _svc(self):
        ntfy = self.service.currentData() == "ntfy"
        for wd in (self.server, self.topic):
            wd.setEnabled(ntfy)
        for wd in (self.tg_token, self.tg_chat, self.find_chat):
            wd.setEnabled(not ntfy)

    def values(self):
        return dict(mode=self.mode.currentData(), service=self.service.currentData(),
                    server=self.server.text().strip() or "https://ntfy.sh", topic=self.topic.text().strip(),
                    tg_token=self.tg_token.text().strip(), tg_chat=self.tg_chat.text().strip(),
                    site=self.site.text().strip()), dict(on=self.web_on.isChecked(), port=self.web_port.value(),
                                                     pin=self.web_pin.text().strip(), password=self.web_pw.text(),
                                                     views={k: c.isChecked() for k, c in self.view_chks.items()})

    def show_tuto(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Alertes téléphone : tuto")
        d.resize(640, 620)
        v = QtWidgets.QVBoxLayout(d)
        tb = QtWidgets.QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(TUTO_ALERTES)
        v.addWidget(tb)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        d.exec()

    def fetch_chat_id(self):
        token = self.tg_token.text().strip()
        if not token:
            self.n_lbl.setText("⚠ Colle d'abord le jeton du bot (donné par @BotFather).")
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=8) as r:
                chats = telegram_chats(json.loads(r.read().decode("utf-8")))
        except Exception as e:
            self.n_lbl.setText(f"⚠ Telegram injoignable ou jeton refusé : {e}")
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if not chats:
            self.n_lbl.setText("Personne n'a encore écrit au bot : envoie-lui un message (/start) dans Telegram, "
                               "puis réessaie.")
            return
        if len(chats) == 1:
            cid = chats[0][0]
        else:
            labels = [f"{n} ({c})" for c, n in chats]
            pick, ok = QtWidgets.QInputDialog.getItem(self, "Chat id", "Quelle discussion reçoit les alertes ?",
                                                      labels, 0, False)
            if not ok:
                return
            cid = chats[labels.index(pick)][0]
        self.tg_chat.setText(cid)
        self.n_lbl.setText(f"✔ Chat id trouvé : {cid} — clique « Envoyer une alerte de test ».")

    def send_test(self):
        n, _w = self.values()
        err = self.owner.send_notify("✔ Test TinySA Monitor", "Les alertes arrivent bien sur ce téléphone.", 2, cfg=n)
        self.n_lbl.setText(f"⚠ {err}" if err else "Envoyé… (vérifie le téléphone ; une erreur s'affichera ici)")
        QtCore.QTimer.singleShot(4000, self.refresh)

    def refresh(self):
        nt = self.owner.notifier
        if nt is not None and nt.last_error:
            self.n_lbl.setText(f"⚠ Dernier envoi en échec : {nt.last_error}")
        elif nt is not None and nt.sent:
            self.n_lbl.setText(f"✔ {nt.sent} alerte(s) envoyée(s) depuis le démarrage.")
        self.w_lbl.setText(self.owner.web_urls_text())
        self.refresh_clients()

    def _remember_sel(self):
        """Clic dans la liste : on retient QUI est choisi (la liste est reconstruite toutes les 2 s)."""
        it = self.clients.currentItem()
        d = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        self._sel_tok = d[0] if d else None

    def refresh_clients(self):
        ws = self.owner.web
        self.clients.blockSignals(True)         # ne pas perdre le choix pendant qu'on reconstruit
        try:
            self._fill_clients(ws)
        finally:
            self.clients.blockSignals(False)

    def _fill_clients(self, ws):
        self.clients.clear()
        if ws is None:
            self.clients.addItem("(page web arrêtée)")
            return
        names = {k: t for k, _i, t, _d in WEB_VIEWS}
        sel = getattr(self, "_sel_tok", None)
        lst = ws.client_list()
        for e in lst:
            ago = int(time.time() - e["last"])
            it = QtWidgets.QListWidgetItem(("🟢 " if e["online"] else "⚪ ") + f"{e['name']} · {e['addr']}"
                                           + (f" · {names.get(e['view'], 'Accueil')}" if e["online"]
                                              else f" · vu il y a {ago // 60} min"))
            it.setData(Qt.ItemDataRole.UserRole, (e["token"], e["name"]))
            self.clients.addItem(it)
            if e["token"] == sel:
                self.clients.setCurrentItem(it)
                it.setSelected(True)
        if not lst:
            self.clients.addItem("Personne pour l'instant")

    def _picked(self):
        tok = getattr(self, "_sel_tok", None)
        e = next((x for x in (self.owner.web.client_list() if self.owner.web is not None else [])
                  if x["token"] == tok), None)
        if e is None:
            self.n_lbl.setText("Choisis d'abord un client dans la liste des connectés.")
            return None
        return e["token"], e["name"]

    def rename_client(self):
        d = self._picked()
        if d is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=d[1])
        if ok and name.strip():
            self.owner.web.rename(d[0], name.strip())
            self.refresh_clients()

    def identify_client(self):
        d = self._picked()
        if d is None:
            return
        self.owner.web.identify(d[0])
        self.n_lbl.setText(f"👋 L'écran de « {d[1]} » clignote pendant 8 s.")


class RelayWindow(QtWidgets.QWidget):
    """Petite fenêtre « relais » à lancer sur le PC où est branché le 2ᵉ tinySA (TinySA-Monitor.exe --relais)."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(f"{APP_NAME} — relais réseau")
        self.resize(520, 330)
        self.relay = None
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.port_combo.setMinimumContentsLength(20)
        b_ref = QtWidgets.QToolButton()
        b_ref.setText("⟳")
        b_ref.clicked.connect(lambda *_: self.refresh_ports())
        self.tcp_spin = QtWidgets.QSpinBox()
        self.tcp_spin.setRange(1024, 65535)
        self.tcp_spin.setValue(RELAY_PORT)
        self.go_btn = QtWidgets.QPushButton("▶ Partager ce tinySA")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        self.addr_lbl = QtWidgets.QLabel("")
        self.addr_lbl.setWordWrap(True)
        self.addr_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.state_lbl = QtWidgets.QLabel("Arrêté.")
        self.state_lbl.setWordWrap(True)
        help_lbl = QtWidgets.QLabel(
            "Branche le tinySA en USB sur CE PC, choisis son port puis « Partager ». Sur le PC principal : "
            "Réglages › 2ᵉ tinySA › adresse affichée ci-dessous. Les deux PC doivent être sur le même réseau "
            "(câble de préférence). Windows peut demander d'autoriser l'accès réseau : accepte (réseau privé).")
        help_lbl.setWordWrap(True)
        form = QtWidgets.QFormLayout()
        h = QtWidgets.QHBoxLayout()
        h.addWidget(self.port_combo, 1)
        h.addWidget(b_ref)
        form.addRow("Port du tinySA :", h)
        form.addRow("Port réseau (TCP) :", self.tcp_spin)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(help_lbl)
        lay.addLayout(form)
        lay.addWidget(self.go_btn)
        lay.addWidget(self.addr_lbl)
        lay.addWidget(self.state_lbl)
        lay.addStretch(1)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.refresh_ports()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())
        ports.sort(key=lambda p: not (p.vid == TINYSA_VID and p.pid == TINYSA_PID))
        for p in ports:
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            self.port_combo.addItem(f"{p.device} — {p.description}{tag}", p.device)
        if not ports:
            self.port_combo.addItem("Aucun port détecté", None)

    def toggle(self):
        if self.relay is not None:
            self.relay.stop()
            self.relay.join(3)
            self.relay = None
            self.timer.stop()
            self.go_btn.setText("▶ Partager ce tinySA")
            self.port_combo.setEnabled(True)
            self.tcp_spin.setEnabled(True)
            self.addr_lbl.setText("")
            self.state_lbl.setText("Arrêté.")
            return
        port = self.port_combo.currentData()
        if not port:
            self.state_lbl.setText("⚠ Aucun port : branche le tinySA (et ferme tinySA-App).")
            return
        self.relay = SerialRelay(port, self.tcp_spin.value())
        self.relay.start()
        self.relay.ready.wait(3)
        if not self.relay.is_alive():
            self.state_lbl.setText("⚠ " + (self.relay.error or "Démarrage impossible."))
            self.relay = None
            return
        ips = local_ips() or ["<adresse IP de ce PC>"]
        self.addr_lbl.setText("Adresse à saisir sur le PC principal :  <b>"
                              + "</b>  ou  <b>".join(f"{ip}:{self.relay.tcp_port}" for ip in ips) + "</b>")
        self.go_btn.setText("■ Arrêter le partage")
        self.port_combo.setEnabled(False)
        self.tcp_spin.setEnabled(False)
        self.timer.start()
        self.tick()

    def tick(self):
        r = self.relay
        if r is None:
            return
        usb = "✔ tinySA ouvert" if r.serial_ok else f"⚠ {r.error or 'tinySA introuvable'} (nouvel essai…)"
        cli = f"✔ connecté à {r.client}" if r.client else "en attente du PC principal…"
        self.state_lbl.setText(f"{usb}\nRéseau : {cli}\nTrafic : {r.rx / 1024:.0f} Ko reçus du tinySA · "
                               f"{r.tx / 1024:.1f} Ko de commandes")

    def closeEvent(self, e):
        if self.relay is not None:
            self.relay.stop()
            self.relay.join(3)
            self.relay = None
        super().closeEvent(e)


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
def fill_rules_combo(combo):
    """Règles d'intermod dans une liste : nom + explication en bulle, et « Personnalisé » à la fin."""
    for txt, d, why in IM_TOL_PRESETS:
        combo.addItem(txt, d)
        combo.setItemData(combo.count() - 1, why, Qt.ItemDataRole.ToolTipRole)
    combo.addItem(IM_TOL_CUSTOM, None)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(max(len(t) for t, _d, _w in IM_TOL_PRESETS) + 2)
    combo.setItemData(combo.count() - 1, "Tes tolérances à toi (0 = type ignoré).", Qt.ItemDataRole.ToolTipRole)


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
            "pas quel appareil (émetteur, ampli d'antenne, combiner…) le fabrique vraiment. Blocs larges "
            "(Spectera / WMAS) : leurs produits sont des bandes (« 540.000 ± 8.0 »), comptées bord à bord.")
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
        self.src_combo.addItem("Émetteurs : toute la liste (sauf « doit rester libre »)", "all")
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
        # tolérances par type de produit (comme EazyRF : un 2A − B est bien plus fort qu'un A + B − C)
        self.tol_spins = {}
        for key, tip in (("2tx3", "2 TX, 3ᵉ ordre (2A − B) : le produit le plus fort."),
                         ("3tx3", "3 TX, 3ᵉ ordre (A + B − C) : plus faible, tolérance plus serrée."),
                         ("5", "5ᵉ ordre et au-delà (3A − 2B, 2A + B − 2C…) : faibles.")):
            sp = QtWidgets.QSpinBox()
            sp.setRange(0, 2000)
            sp.setSingleStep(10)
            sp.setSuffix(" kHz")
            sp.setPrefix("± ")
            sp.setSpecialValueText("ignoré")            # 0 = ce type de produit n'est pas compté (comme EazyRF)
            sp.setToolTip(tip + "\nUn produit plus loin que ça de ta fréquence est accepté (comme les tolérances "
                                "d'EazyRF).\n0 = « ignoré » : ce type de produit n'est pas compté du tout.")
            self.tol_spins[key] = sp
        self.tol_combo = QtWidgets.QComboBox()
        fill_rules_combo(self.tol_combo)
        self.tol_combo.setToolTip("Quels produits comptent, et à quelle distance de ta fréquence (survole chaque choix).\n"
                                  "Comme EazyRF = ses tolérances par défaut (2 TX 100 kHz, 3 TX 50 kHz).")
        self.tol_combo.currentIndexChanged.connect(lambda *_: self._tol_preset())
        self.filt_spin = QtWidgets.QDoubleSpinBox()
        self.filt_spin.setRange(0, 400)
        self.filt_spin.setDecimals(0)
        self.filt_spin.setSingleStep(4)
        self.filt_spin.setSuffix(" MHz")
        self.filt_spin.setSpecialValueText("aucun")
        self.filt_spin.setValue(float(owner.plan_opts["filt"]))
        self.filt_spin.setToolTip("Filtre d'entrée du récepteur (« Filtre » d'EazyRF, 32 MHz pour un Wisycom) : un "
                                  "produit ne compte sur une fréquence\nque si tous ses émetteurs sont à ± la moitié du "
                                  "filtre autour d'elle. aucun = tous comptent.\nSans effet en « aucune cible ».")
        self._tol_preset()
        for sp in self.tol_spins.values():
            sp.valueChanged.connect(lambda *_: self._tol_custom())
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
        lay.addLayout(R(self.tgt_combo, "Règles :", self.tol_combo, None))
        lay.addLayout(R("2 TX :", self.tol_spins["2tx3"], "3 TX :", self.tol_spins["3tx3"],
                        "5ᵉ / 7ᵉ ordre :", self.tol_spins["5"], "Filtre :", self.filt_spin, None))
        lay.addLayout(R("Plage (liste complète) :", self.fmin_spin, "à", self.fmax_spin, None, self.go_btn))
        lay.addWidget(self.msg)
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Produit MHz", "Ordre", "Origine (émetteurs)", "Tombe sur", "Écart kHz",
                                              "Mesuré dBm", "Verdict"])
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for c, w in ((0, 96), (1, 92), (3, 190), (4, 76), (5, 88), (6, 240)):
            self.table.setColumnWidth(c, w)
        for c, tip in ((1, "IM3 = 3ᵉ ordre, IM5 = 5ᵉ ordre ; « 2 TX » = 2 émetteurs (2A − B : le plus fort),\n"
                           "« 3 TX » = A + B − C (plus faible), etc."),
                       (4, "Écart entre le produit calculé et ta fréquence (0 = pile dessus)."),
                       (5, "Ce que le tinySA mesure EN CE MOMENT à cet endroit (pas la force du produit)."),
                       (6, "🔴 problème : on mesure un signal au-dessus de ton seuil « occupé » là où le produit tombe.\n"
                           "🟠 à vérifier : on mesure de l'énergie (au-dessus du seuil « faible »).\n"
                           "🟡 à surveiller : rien de mesuré, mais c'est un IM3 à 2 émetteurs (2A − B, le plus fort).\n"
                           "⚪ faible risque : rien de mesuré, produit plus faible (A + B − C, 5ᵉ ordre…).\n"
                           "Le calcul ne dit pas si c'est audible : ça dépend de la puissance, des distances et des\n"
                           "récepteurs. « cible en émission » : on ne peut pas mesurer sous sa propre porteuse.")):
            self.table.horizontalHeaderItem(c).setToolTip(tip)
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
        if kind != "sel":                   # une réserve « doit rester libre » n'émet pas : pas un émetteur
            idx = [i for i in idx if not o.is_keep_free(o.watch[i]["status"])]
        if self.active_chk.isChecked():
            idx = [i for i in idx if o.watch[i]["state"] in ("occ", "weak")]
        return idx

    def update_src(self, *_):
        self.src_lbl.setText(f"→ {len(self.source_indices())} émetteur(s)")

    def _tol_preset(self):
        d = self.tol_combo.currentData()
        if d is None:
            return
        self._applying = True
        for k, sp in self.tol_spins.items():
            sp.setValue(int(round(d[k] * 1000)))
        self._applying = False

    def _tol_custom(self):
        if getattr(self, "_applying", False):
            return
        self.tol_combo.blockSignals(True)
        self.tol_combo.setCurrentIndex(self.tol_combo.count() - 1)
        self.tol_combo.blockSignals(False)

    def tolerances(self):
        """-> dict pour im_scan (MHz) : 2 TX, 3 TX, 5ᵉ et 7ᵉ ordre."""
        t5 = self.tol_spins["5"].value() / 1000.0
        return {"2tx3": self.tol_spins["2tx3"].value() / 1000.0, "3tx3": self.tol_spins["3tx3"].value() / 1000.0,
                "5": t5, "7": t5}

    def orders(self):
        out = tuple(x for x, c in ((3, self.o3_chk), (5, self.o5_chk), (7, self.o7_chk)) if c.isChecked())
        return out or (3,)

    def compute(self):
        o = self.owner
        idx = self.source_indices()
        freqs = [o.watch[i]["freq"] for i in idx]
        names = [o.watch[i]["name"] for i in idx]
        bws = [float(o.watch[i].get("bw") or 0.0) for i in idx]        # blocs Spectera / WMAS : produits en bandes
        orders, max_tx, guard = self.orders(), self.maxtx_combo.currentData(), self.tolerances()
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
        tbws = None
        if origin:
            targets, fmin, fmax = [self.freq_spin.value()], 0.1, 6000.0
        else:
            tm = self.tgt_combo.currentData()
            fmin, fmax = self.fmin_spin.value(), self.fmax_spin.value()
            tw = o.watch if tm == "all" else (o.scope_ws() if tm == "scope" else None)
            if tw is not None:
                targets, fmin, fmax = [w["freq"] for w in tw], 0.1, 6000.0
                tbws = [float(w.get("bw") or 0.0) for w in tw]
            else:
                targets = None
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rows, info = im_scan(freqs, orders, max_tx, targets, guard, fmin, fmax, limit=5000, bws=bws, tbws=tbws)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        filt = self.filt_spin.value()
        o.plan_opts["filt"] = filt
        if filt > 0:                    # émetteurs hors du filtre du récepteur visé : produit coupé
            rows = [r for r in rows if r["target"] is None
                    or all(abs(freqs[i] - r["target"]) <= filt / 2.0 + 1e-9 for i, _c in r["terms"])]
        F, L = o.fresh_FL()
        win = max(0.05, o.win_spin.value() / 1000.0)
        thr, weak = o.thr_spin.value(), o.weak_spin.value()
        by_freq = {int(round(w["freq"] * 1000)): w["name"] for w in o.watch}
        by_w = {int(round(w["freq"] * 1000)): w for w in o.watch}
        for r in rows:
            r["text"] = im_formula(r["terms"], names)
            r["numtext"] = im_formula(r["terms"], freqs=freqs, numeric=True)
            tw_ = None if (r["target"] is None or origin) else by_w.get(int(round(r["target"] * 1000)))
            masked = tw_ is not None and tw_["state"] in ("occ", "weak") and o.is_keep_on(tw_["status"])
            if F is None or masked:     # la cible émet : on mesurerait sa propre porteuse, pas le produit
                r["meas"] = None
            elif tw_ is not None:       # niveau là où ça gêne : sur la fréquence (ou le bloc) protégée
                tb_ = float(tw_.get("bw") or 0.0)
                r["meas"] = (level_block(F, L, tw_["freq"], tb_, "max") if tb_ else level_at(F, L, tw_["freq"], win))
            elif r["hw"] > 0.05:        # produit large sans cible : son « plateau »
                r["meas"] = level_block(F, L, r["f"], 2 * r["hw"], "median")
            else:
                r["meas"] = level_at(F, L, r["f"], win)
            r["masked"] = masked
            if r["target"] is None:
                r["tname"] = ""
            elif origin:
                r["tname"] = f"signal à {r['target']:.3f}"
            else:
                r["tname"] = f"{by_freq.get(int(round(r['target'] * 1000)), '?')} ({r['target']:.3f})"
            if r["target"] is not None and not origin:
                r["sev"], r["verdict"] = im_verdict(r["meas"], thr, weak, o.weak_chk.isChecked(), r["order"],
                                                    r["ntx"], r.get("masked", False))
            elif origin:
                r["sev"], r["verdict"] = 1, "origine possible"
            elif r["meas"] is not None and r["meas"] >= thr:
                r["sev"], r["verdict"] = 3, "⚠ visible sur le spectre"
            elif r["meas"] is not None and o.weak_chk.isChecked() and r["meas"] >= weak:
                r["sev"], r["verdict"] = 2, "énergie faible mesurée"
            else:
                r["sev"], r["verdict"] = 0, ""
            r["level"] = 2 if r["sev"] == 3 else (1 if r["sev"] else 0)
        if targets is not None and not origin:
            rows.sort(key=lambda r: -r["sev"])                # le plus grave en haut
        self.rows = rows
        self.cur_freqs, self.cur_names = freqs, names
        self.fill()
        if targets is not None and not origin:
            npairs = f"{info['pairs']:,}".replace(",", " ")
            txt = (f"{npairs} combinaisons calculées ({len(freqs)} émetteurs, ordres "
                   f"{', '.join(str(x) for x in orders)}) · seules celles qui tombent sur une de tes fréquences "
                   f"(dans la tolérance) sont listées : {len(rows)} produit(s)")
            txt += " (liste tronquée)" if info["truncated"] else ""
        else:
            txt = f"{len(rows)} produit(s)" + (" (liste tronquée)" if info["truncated"] else "")
            txt += f" · {len(freqs)} émetteur(s) · ordres {', '.join(str(x) for x in orders)} · {info['pairs']:,} combinaisons examinées".replace(",", " ")
        cnt = [sum(1 for r in rows if r["sev"] == k) for k in range(4)]
        if targets is not None and not origin and rows:
            txt += (f"\n🔴 {cnt[3]} problème(s) mesuré(s) · 🟠 {cnt[2]} à vérifier · 🟡 {cnt[1]} à surveiller (IM3 2 TX) · "
                    f"⚪ {cnt[0]} faible risque — survole « Verdict » pour le détail")
        n_vis = cnt[3]
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
            wide = row["hw"] > 0.05 or (row["gap"] is not None and row["delta"] is not None
                                        and abs(abs(row["delta"]) - row["gap"]) > 1e-6)
            if row["delta"] is None:
                d_txt = ""
            elif wide:
                d_txt = "dans la bande" if row["gap"] <= 0 else f"bord à {row['gap'] * 1000:.0f}"
            else:
                d_txt = f"{row['delta'] * 1000:+.0f}"
            vals = (f"{row['f']:.3f}" + (f" ± {row['hw']:.1f}" if row["hw"] > 0.05 else ""),
                    f'{IM_NAMES.get(row["order"], str(row["order"]))} · {row["ntx"]} TX',
                    f'{row["text"]}   =   {row["numtext"]}', row["tname"], d_txt,
                    "—" if row["meas"] is None else f"{row['meas']:.1f}", row["verdict"])
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (0, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 2:
                    it.setToolTip(row["numtext"])
                sev = row.get("sev", 0)
                if sev == 3:
                    bg = blend(th["st_occ"], base, 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif c == 6 and row["verdict"]:
                    col_ = {2: "#f97316", 1: th["st_weak"]}.get(sev, th["st_none"])
                    bg = blend(col_, base, 0.55 if sev else 0.35)
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
        self.guard_spin.setValue(0.10)
        self.guard_spin.setPrefix("± ")
        self.guard_spin.setSuffix(" MHz")
        self.guard_spin.setToolTip("Tolérance d'intermodulation 3ᵉ ordre 2 TX (2A − B) avec tes fréquences ;\n"
                                   "la moitié pour les 3 TX (A + B − C). 100 kHz = défaut 2 TX d'EazyRF.")
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
                           self.thr_spin.value(), self.guard_spin.value(), guard3=self.guard_spin.value() / 2.0)
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
def rx_short(key):
    """Nom court d'un profil d'appareil (colonne « Appareil »)."""
    for k, n, _d, _w in RX_PROFILES:
        if k == key:
            return n.split(" (")[0].split(" ·")[0]
    return "par défaut"


def fill_rx_combo(combo, default_txt):
    """Profils d'appareil dans une liste : 1er choix = default_txt (donnée ""), explication en bulle."""
    combo.addItem(default_txt, "")
    for k, n, _d, why in RX_PROFILES:
        combo.addItem(n, k)
        combo.setItemData(combo.count() - 1, why, Qt.ItemDataRole.ToolTipRole)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)


class PlanCheckDialog(QtWidgets.QDialog):
    """Vérifie un plan de fréquences comme un logiciel de coordination (EazyRF…) : écart entre porteuses et
    intermod selon des tolérances, un verdict par fréquence, et une fréquence de remplacement compatible.
    Chaque fréquence peut avoir son profil d'appareil (w["rx"] : Wisycom très sélectif, Shure, Sennheiser…)."""
    COLS = ["État", "Nom", "MHz", "Appareil", "Problèmes"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Vérifier le plan de fréquences")
        self.resize(940, 660)
        self.ws, self.issues = [], []
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Comme le calcul de plan d'EazyRF : pour chaque fréquence, est-elle trop près d'une autre (écart entre "
            "porteuses), et un produit d'intermod de tes émetteurs tombe-t-il dessus (selon les tolérances) ? C'est un "
            "calcul, sans mesure. Les « doit rester libre » (réserves) sont protégées mais ne comptent pas comme "
            "émetteurs. Choisis une fréquence ✗ puis « Proposer » pour une remplaçante compatible.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        R = owner._row
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Plan : toute la liste", "all")
        self.src_combo.addItem("Plan : la couche active", "scope")
        self.src_combo.setToolTip("Les fréquences vérifiées ensemble (celles qui émettent en même temps au même endroit).")
        self.sep_spin = QtWidgets.QSpinBox()
        self.sep_spin.setRange(0, 3000)
        self.sep_spin.setSingleStep(25)
        po = owner.plan_opts
        self.sep_spin.setValue(int(po["sep"]))
        self.sep_spin.setSuffix(" kHz")
        self.sep_spin.setToolTip("Écart minimal entre deux porteuses (bord à bord pour un bloc large).\n"
                                 "« Séparation » dans un profil d'appareil EazyRF (500 kHz pour un Wisycom MRK980).")
        self.filt_spin = QtWidgets.QDoubleSpinBox()
        self.filt_spin.setRange(0, 400)
        self.filt_spin.setDecimals(0)
        self.filt_spin.setSingleStep(4)
        self.filt_spin.setSuffix(" MHz")
        self.filt_spin.setSpecialValueText("aucun")
        self.filt_spin.setValue(float(po["filt"]))
        self.filt_spin.setToolTip("Largeur du filtre d'entrée du récepteur (« Filtre » dans un profil EazyRF : 32 MHz "
                                  "pour un Wisycom MRK980).\nUn produit d'intermod ne gêne une fréquence que si TOUS ses "
                                  "émetteurs sont à ± la moitié du filtre\nautour d'elle : les émetteurs plus loin sont "
                                  "coupés par le filtre du récepteur.\naucun (0) = tous les émetteurs comptent (plus strict).")
        self.step_spin = QtWidgets.QSpinBox()
        self.step_spin.setRange(1, 1000)
        self.step_spin.setSuffix(" kHz")
        self.step_spin.setValue(int(po["step"]))
        self.step_spin.setToolTip("Pas des fréquences proposées (« Incrément » dans EazyRF) : le pas réglable de tes "
                                  "appareils.\n5 kHz pour un Wisycom MRK980, 25 kHz pour un MTK952.")
        self.prof_combo = QtWidgets.QComboBox()
        fill_rx_combo(self.prof_combo, "✏ Réglages ci-dessous")
        self.prof_combo.setToolTip("Appareil par défaut (comme un profil EazyRF) : remplit écart, filtre, pas et "
                                   "tolérances.\nWisycom = très sélectif (filtre 32 MHz) ; Shure / Sennheiser / ears = "
                                   "moins sélectifs.\nLes fréquences avec leur propre appareil (colonne « Appareil ») "
                                   "gardent le leur.\nValeurs des profils autres que Wisycom : de départ, NON vérifiées.")
        self.tol_combo = QtWidgets.QComboBox()
        fill_rules_combo(self.tol_combo)
        self.tol_combo.setToolTip("Quelle sévérité ? Survole chaque choix pour l'explication.\n"
                                  "Comme EazyRF = ses tolérances par défaut (2 TX 100 kHz, 3 TX 50 kHz).")
        self.tol_spins = {}
        for key in ("2tx3", "3tx3", "5"):
            sp = QtWidgets.QSpinBox()
            sp.setRange(0, 2000)
            sp.setSingleStep(10)
            sp.setPrefix("± ")
            sp.setSuffix(" kHz")
            sp.setSpecialValueText("ignoré")
            sp.setToolTip({"2tx3": "2 TX, 3ᵉ ordre (2A − B).", "3tx3": "3 TX, 3ᵉ ordre (A + B − C).",
                           "5": "5ᵉ ordre et plus."}[key] + "\n0 = ignoré.")
            self.tol_spins[key] = sp
        self.rule_lbl = QtWidgets.QLabel("")
        self.rule_lbl.setWordWrap(True)
        self.rule_lbl.setMinimumHeight(self.rule_lbl.fontMetrics().height() * 3)
        self.tol_combo.currentIndexChanged.connect(lambda *_: (self._prof_touched(), self._preset()))
        for sp in self.tol_spins.values():
            sp.valueChanged.connect(lambda *_: self._custom())
        self.sep_spin.valueChanged.connect(lambda *_: self._explain())
        self.filt_spin.valueChanged.connect(lambda *_: self._explain())
        self._preset()
        ix = self.prof_combo.findData(po.get("prof", ""))
        self.prof_combo.setCurrentIndex(max(0, ix))
        self._prof_default()
        self.prof_combo.currentIndexChanged.connect(lambda *_: self._prof_default())
        for sp in (self.sep_spin, self.filt_spin, self.step_spin):
            sp.valueChanged.connect(lambda *_: self._prof_touched())
        self.go_btn = QtWidgets.QPushButton("🧮 Vérifier")
        self.go_btn.setToolTip("Calcule la compatibilité de tout le plan.")
        self.go_btn.clicked.connect(lambda *_: self.compute())
        lay.addLayout(R(self.src_combo, "Appareil par défaut :", self.prof_combo, None, self.go_btn))
        lay.addLayout(R("Règles :", self.tol_combo, None))
        lay.addLayout(R("Écart mini :", self.sep_spin, "Filtre récepteur :", self.filt_spin, "Pas :", self.step_spin,
                        None))
        lay.addLayout(R("2A − B :", self.tol_spins["2tx3"], "A + B − C :", self.tol_spins["3tx3"], "5ᵉ ordre :",
                        self.tol_spins["5"], None))
        lay.addWidget(self.rule_lbl)
        self.sum_lbl = QtWidgets.QLabel("")
        f_ = self.sum_lbl.font()
        f_.setPointSize(f_.pointSize() + 3)
        f_.setBold(True)
        self.sum_lbl.setFont(f_)
        self.sum_lbl.setWordWrap(True)
        lay.addWidget(self.sum_lbl)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        for c, w_ in enumerate((120, 140, 80, 130)):
            self.table.setColumnWidth(c, w_)
        self.table.setToolTip("Survole « Problèmes » pour le détail complet. Double-clic : proposer une remplaçante.\n"
                              "Sélection multiple (Maj / Ctrl) pour donner un appareil à plusieurs fréquences.")
        self.table.cellDoubleClicked.connect(lambda r, c: self.suggest())
        lay.addWidget(self.table, 1)
        self.rx_combo = QtWidgets.QComboBox()
        fill_rx_combo(self.rx_combo, "par défaut (appareil ci-dessus)")
        self.rx_combo.setToolTip("L'appareil (récepteur) des fréquences choisies dans le tableau : son filtre, son écart, "
                                 "ses tolérances\net son pas comptent pour ELLES. Enregistré dans ta liste (et tes shows).")
        self.rx_btn = QtWidgets.QPushButton("Appliquer aux lignes choisies")
        self.rx_btn.setToolTip("Donne cet appareil aux fréquences sélectionnées, puis recalcule.")
        self.rx_btn.clicked.connect(lambda *_: self.set_rx())
        lay.addLayout(R("Appareil des lignes choisies :", self.rx_combo, self.rx_btn, None))
        self.sug_list = QtWidgets.QListWidget()
        self.sug_list.setMaximumHeight(110)
        self.sug_list.setToolTip("Fréquences compatibles avec tout le reste du plan, les plus proches d'abord.")
        self.avoid_chk = QtWidgets.QCheckBox("Éviter ce que le tinySA voit occupé")
        self.avoid_chk.setChecked(True)
        self.avoid_chk.setToolTip("Écarte les fréquences où le spectre mesuré dépasse ton seuil « faible »\n"
                                  "(ou « occupé » si le niveau faible est désactivé).")
        self.sug_btn = QtWidgets.QPushButton("🔍 Proposer une fréquence compatible")
        self.sug_btn.setToolTip("Pour la fréquence choisie : cherche à ± 10 MHz une fréquence sans aucun problème,\n"
                                "qui n'en crée pas de nouveau pour les autres.")
        self.sug_btn.clicked.connect(lambda *_: self.suggest())
        self.rep_btn = QtWidgets.QPushButton("✔ Remplacer")
        self.rep_btn.setToolTip("Remplace la fréquence choisie par la proposition sélectionnée (dans ta liste).")
        self.rep_btn.clicked.connect(lambda *_: self.replace())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(R(self.sug_btn, self.avoid_chk, None))
        lay.addWidget(self.sug_list)
        lay.addLayout(R(self.rep_btn, None, close))
        self._target = None
        self.compute()

    def _prof_default(self):
        """Profil par défaut choisi : remplit écart, filtre, pas et tolérances."""
        d = rx_profile(self.prof_combo.currentData())
        self.owner.plan_opts["prof"] = self.prof_combo.currentData() or ""
        if d is None:
            return
        self._filling = True
        self.sep_spin.setValue(int(round(d["sep"] * 1000)))
        self.filt_spin.setValue(d["filt"])
        self.step_spin.setValue(int(round(d["step"] * 1000)))
        ix = next((k for k in range(self.tol_combo.count() - 1) if self.tol_combo.itemData(k) == d["tol"]),
                  self.tol_combo.count() - 1)
        self.tol_combo.setCurrentIndex(ix)
        if ix == self.tol_combo.count() - 1:
            self._applying = True
            for k, sp in self.tol_spins.items():
                sp.setValue(int(round(d["tol"][k] * 1000)))
            self._applying = False
        self._filling = False
        self._explain()

    def _prof_touched(self):
        if not getattr(self, "_filling", False) and self.prof_combo.currentData():
            self.prof_combo.blockSignals(True)
            self.prof_combo.setCurrentIndex(0)                 # on a touché un réglage : « ✏ Réglages ci-dessous »
            self.prof_combo.blockSignals(False)
            self.owner.plan_opts["prof"] = ""

    def set_rx(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.ws)})
        if not rows:
            self.sum_lbl.setText("Choisis d'abord une ou plusieurs fréquences dans le tableau.")
            return
        key = self.rx_combo.currentData()
        for r in rows:
            if key:
                self.ws[r]["rx"] = key
            else:
                self.ws[r].pop("rx", None)
        self._explain()
        self.compute()
        self.owner.set_status(f"{len(rows)} fréquence(s) : appareil « {rx_short(key)} ».")

    def _preset(self):
        d = self.tol_combo.currentData()
        if d is not None:
            self._applying = True
            for k, sp in self.tol_spins.items():
                sp.setValue(int(round(d[k] * 1000)))
            self._applying = False
        self._explain()

    def _custom(self):
        self._prof_touched()
        if not getattr(self, "_applying", False):
            self.tol_combo.blockSignals(True)
            self.tol_combo.setCurrentIndex(self.tol_combo.count() - 1)
            self.tol_combo.blockSignals(False)
        self._explain()

    def _explain(self):
        why = self.tol_combo.itemData(self.tol_combo.currentIndex(), Qt.ItemDataRole.ToolTipRole) or ""
        own = sum(1 for w in self.owner.watch if rx_profile(w.get("rx")) is not None)
        self.rule_lbl.setText(f"<b>{self.tol_combo.currentText()}</b> — {why}<br>"
                              + im_rules_text(self.tolerances(), self.sep_spin.value() / 1000.0,
                                              self.filt_spin.value()) + "."
                              + (f"<br>{own} fréquence(s) ont leur propre appareil (colonne « Appareil ») : ce sont "
                                 "ses réglages qui comptent pour elles." if own else ""))

    def tolerances(self):
        t5 = self.tol_spins["5"].value() / 1000.0
        return {"2tx3": self.tol_spins["2tx3"].value() / 1000.0, "3tx3": self.tol_spins["3tx3"].value() / 1000.0,
                "5": t5, "7": t5}

    def _params(self):
        o = self.owner
        o.plan_opts.update(sep=self.sep_spin.value(), filt=self.filt_spin.value(), step=self.step_spin.value())
        ws = [w for w in o.watch if self.src_combo.currentData() == "all" or o.in_scope(w)]
        dflt = dict(sep=self.sep_spin.value() / 1000.0, filt=self.filt_spin.value(), tol=self.tolerances(),
                    step=self.step_spin.value() / 1000.0)
        P = [rx_profile(w.get("rx")) or dflt for w in ws]           # profil d'appareil de chaque fréquence
        self._steps = [q["step"] for q in P]
        return (ws, [w["freq"] for w in ws], [not o.is_keep_free(w["status"]) for w in ws],
                [float(w.get("bw") or 0.0) for w in ws], [q["sep"] for q in P], [q["tol"] for q in P], None,
                [q["filt"] for q in P])

    def compute(self):
        ws, F, T, B, sep, tol, mx, filt = self._params()
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.issues, info = pf_check(F, T, B, sep, tol, mx, filt)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.ws = ws
        names = [w["name"] or f"{w['freq']:.3f}" for w in ws]
        th, base = self.owner.theme, self.owner.theme["ui_base"]
        t = self.table
        t.setRowCount(len(ws))
        bad = 0
        for r, (w, iss) in enumerate(zip(ws, self.issues)):
            bad += bool(iss)
            txts = [pf_issue_text(it, names, F) for it in iss]
            state = "✔ compatible" if not iss else f"✗ {len(iss)} problème{'s' if len(iss) > 1 else ''}"
            if not T[r] and not iss:
                state = "✔ réserve libre"
            vals = [state, names[r], f"{w['freq']:.3f}", rx_short(w.get("rx")),
                    " · ".join(txts[:3]) + (" …" if len(txts) > 3 else "")]
            col = th["st_occ"] if iss else th["st_free"]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c == 0:
                    bg = blend(col, base, 0.7)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                if c == 4 and txts:
                    it.setToolTip("\n".join(txts))
                t.setItem(r, c, it)
        n = len(ws)
        self.too_big = bool(info.get("too_big"))
        if self.too_big:
            self.sum_lbl.setText("⚠ Trop de combinaisons pour calculer l'intermod (seuls les écarts sont vérifiés) : "
                                 "passe en « 2 TX seulement », ignore le 5ᵉ ordre, ou vérifie une couche à la fois.")
        elif not n:
            self.sum_lbl.setText("Aucune fréquence à vérifier.")
        elif not bad:
            self.sum_lbl.setText(f"✔ Plan compatible : {n} / {n} fréquences sans problème (pour ces règles).")
        else:
            kinds = {"sep": 0, "2tx3": 0, "3tx3": 0, "5": 0}
            for iss in self.issues:
                for it in iss:
                    k_ = "sep" if it["kind"] == "sep" else im_class(it["order"], it["ntx"])
                    kinds[k_ if k_ in kinds else "5"] += 1
            det = " · ".join(f"{v} {lab}" for lab, v in (("écart trop faible", kinds["sep"]), ("2A − B", kinds["2tx3"]),
                                                          ("A + B − C", kinds["3tx3"]), ("5ᵉ ordre", kinds["5"])) if v)
            self.sum_lbl.setText(f"✗ {bad} fréquence(s) à revoir sur {n} · ✔ {n - bad} compatibles ({det}). "
                                 "Choisis une ligne ✗ puis « Proposer ».")
        self.sum_lbl.setStyleSheet(f"color:{th['st_free'] if n and not bad else th['st_occ'] if bad else th['ui_text']}")
        self.sug_list.clear()
        self._target = None

    def _sel(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return rows[0] if rows and rows[0] < len(self.ws) else None

    def suggest(self):
        r = self._sel()
        self.sug_list.clear()
        if getattr(self, "too_big", False):
            self.sum_lbl.setText("⚠ Calcul trop gros : passe en « 2 TX seulement » ou ignore le 5ᵉ ordre, puis Vérifier.")
            return
        if r is None:
            self.sum_lbl.setText("Choisis d'abord une fréquence dans le tableau.")
            return
        ws, F, T, B, sep, tol, mx, filt = self._params()
        busy = None
        if self.avoid_chk.isChecked():
            o = self.owner
            Fm, Lm = o.fresh_FL(use_max=True)
            if Fm is not None:
                lim = o.weak_spin.value() if o.weak_chk.isChecked() else o.thr_spin.value()
                win = max(0.05, o.win_spin.value() / 1000.0)
                busy = (lambda c: (lambda v: v is not None and v >= lim)(level_at(Fm, Lm, c, win)))
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            kw = dict(n=6, busy=busy, step=self._steps[r], filt=filt)        # pas de l'appareil de cette fréquence
            sg = pf_suggest(r, F, T, B, sep, tol, mx, **kw)
            if not sg:                                  # rien tout près : on cherche dans toutes les bandes
                ext = self.owner._band_extent()
                if ext:
                    sg = pf_suggest(r, F, T, B, sep, tol, mx, lo=ext[0], hi=ext[1], max_check=1500, **kw)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._target = ws[r]
        name = ws[r]["name"] or f"{ws[r]['freq']:.3f}"
        if not sg:
            self.sug_list.addItem(f"Rien de compatible pour {name} dans tes bandes : élargis les tolérances, baisse "
                                  "l'écart mini ou décoche « Éviter ce que le tinySA voit occupé ».")
            return
        for c, d in sg:
            it = QtWidgets.QListWidgetItem(f"{c:.3f} MHz   ({d * 1000:+.0f} kHz)   pour {name}")
            it.setData(Qt.ItemDataRole.UserRole, c)
            self.sug_list.addItem(it)
        self.sug_list.setCurrentRow(0)

    def replace(self):
        it = self.sug_list.currentItem()
        c = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        w = self._target
        if c is None or w is None or not any(x is w for x in self.owner.watch):
            self.sum_lbl.setText("Propose d'abord une fréquence, puis choisis-la dans la liste.")
            return
        old = w["freq"]
        self.owner.set_watch_freq(w, c)
        self.owner.log_event(dict(name=w["name"], freq=0.0, note=f"{old:.3f} → {c:.3f} MHz (vérification du plan)"),
                             0.0, "NOUVELLE FRÉQUENCE")
        self.compute()
        self.owner.set_status(f"{w['name']} : {old:.3f} → {c:.3f} MHz (plan vérifié).")


class SdrDialog(QtWidgets.QDialog):
    """V8 : réglages des SDR (HackRF One, RTL-SDR) : dossier des outils, gains, et comment les installer."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Réglages SDR (HackRF, RTL-SDR)")
        self.resize(640, 470)
        c = owner.sdr_cfg
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "<b>Un SDR remplace (ou complète) un tinySA</b> : choisis « 📡 HackRF One » ou « 📡 RTL-SDR » dans la "
            "liste des ports (ou comme 2ᵉ appareil). L'appli lance l'outil officiel de balayage "
            "(<code>hackrf_sweep</code> / <code>rtl_power</code>) et lit ses mesures.<br><br>"
            "<b>Installer les outils (Windows)</b> : le plus simple est <b>PothosSDR</b> (contient hackrf_sweep, "
            "rtl_power et les pilotes), ou les outils HackRF de Great Scott Gadgets. Le pilote USB se met avec "
            "<b>Zadig</b> (WinUSB). Tu peux aussi copier <code>hackrf_sweep.exe</code> (et ses .dll) dans un dossier "
            "<code>outils</code> à côté de l'appli.<br><br>"
            "⚠ Les niveaux d'un SDR <b>ne sont pas des dBm étalonnés</b> : règle l'offset, ou fais la calibration "
            "automatique avec un tinySA (2ᵉ appareil).")
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setMinimumHeight(info.fontMetrics().height() * 9)
        lay.addWidget(info)
        f = QtWidgets.QFormLayout()
        self.dir_edit = QtWidgets.QLineEdit(c.get("dir", ""))
        self.dir_edit.setPlaceholderText("automatique (PATH, PothosSDR, dossier « outils »)")
        self.dir_edit.setToolTip("Dossier qui contient hackrf_sweep(.exe) / rtl_power(.exe). Vide = recherche "
                                 "automatique.")
        browse = QtWidgets.QPushButton("Parcourir…")
        browse.setToolTip("Choisir le dossier des outils SDR.")
        browse.clicked.connect(lambda *_: self._browse())
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        f.addRow("Dossier des outils :", row)
        self.found_lbl = QtWidgets.QLabel("")
        self.found_lbl.setWordWrap(True)
        f.addRow("Trouvés :", self.found_lbl)
        self.lna_spin = QtWidgets.QSpinBox()
        self.lna_spin.setRange(0, 50)
        self.lna_spin.setValue(int(c.get("lna", 24)))
        self.lna_spin.setSuffix(" dB")
        self.lna_spin.setToolTip("HackRF : gain LNA (0 à 40 dB par pas de 8). RTL-SDR : gain du tuner (0 à 50 dB).\n"
                                 "Trop de gain = le SDR sature et invente des signaux (intermod interne).")
        self.vga_spin = QtWidgets.QSpinBox()
        self.vga_spin.setRange(0, 62)
        self.vga_spin.setSingleStep(2)
        self.vga_spin.setValue(int(c.get("vga", 20)))
        self.vga_spin.setSuffix(" dB")
        self.vga_spin.setToolTip("HackRF seulement : gain VGA (bande de base, 0 à 62 dB par pas de 2).")
        self.amp_chk = QtWidgets.QCheckBox("Ampli d'entrée du HackRF (+14 dB)")
        self.amp_chk.setChecked(bool(c.get("amp", False)))
        self.amp_chk.setToolTip("HackRF seulement. Utile avec une petite antenne loin des émetteurs ; à éviter près "
                                "d'une scène (saturation).")
        f.addRow("Gain LNA / tuner :", self.lna_spin)
        f.addRow("Gain VGA :", self.vga_spin)
        f.addRow(self.amp_chk)
        lay.addLayout(f)
        note = QtWidgets.QLabel("Les gains s'appliquent au cycle suivant (l'outil est relancé). Pas encore testé "
                                "avec un vrai HackRF / RTL-SDR : dis-moi ce que ça donne !")
        note.setWordWrap(True)
        note.setMinimumHeight(note.fontMetrics().height() * 2)
        lay.addWidget(note)
        lay.addStretch(1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.dir_edit.textChanged.connect(lambda *_: self._found())
        self._found()

    def _browse(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier des outils SDR", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _found(self):
        out = []
        for k, sp in SDR_KINDS.items():
            p_ = find_sdr_tool(sp["tool"], self.dir_edit.text().strip())
            out.append(f"✔ {sp['tool']} ({p_})" if p_ else f"✗ {sp['tool']} introuvable")
        self.found_lbl.setText("\n".join(out))

    def values(self):
        return dict(dir=self.dir_edit.text().strip(), lna=self.lna_spin.value(), vga=self.vga_spin.value(),
                    amp=self.amp_chk.isChecked())


class ScanConvertDialog(QtWidgets.QDialog):
    """Convertit un scan d'un logiciel à l'autre : entrée (auto, CSV au choix, scan en cours) → sortie (WWB, WSM,
    CSV au choix), avec un aperçu."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Convertir / exporter un scan")
        self.resize(820, 600)
        self.paths, self.F, self.L = [], None, None
        lay = QtWidgets.QVBoxLayout(self)
        R = owner._row
        # ---- entrée
        ib = QtWidgets.QGroupBox("Entrée")
        il = QtWidgets.QVBoxLayout(ib)
        self.open_btn = QtWidgets.QPushButton("📂 Ouvrir un ou plusieurs fichiers…")
        self.open_btn.setToolTip("Scans exportés de WSM, WWB, EazyRF, d'un tableur…")
        self.open_btn.clicked.connect(lambda *_: self.open_files())
        self.cur_btn = QtWidgets.QPushButton("📈 Prendre le scan en cours")
        self.cur_btn.setToolTip("Le spectre mesuré par le tinySA (max hold ou dernier balayage).")
        self.cur_btn.clicked.connect(lambda *_: self.use_current())
        self.cur_combo = QtWidgets.QComboBox()
        self.cur_combo.addItem("Max hold (recommandé)", True)
        self.cur_combo.addItem("Dernier balayage", False)
        self.cur_combo.setToolTip("Quelle courbe prendre quand on part du scan en cours.")
        self.src_lbl = QtWidgets.QLabel("Aucun scan chargé.")
        self.src_lbl.setWordWrap(True)
        self.in_fmt = QtWidgets.QComboBox()
        self.in_fmt.addItem("Format : reconnaître tout seul (WSM, WWB, « fréquence ; niveau »)", "auto")
        self.in_fmt.addItem("Format : CSV personnalisé (je choisis les colonnes)", "custom")
        self.in_fmt.setToolTip("Auto : export WSM (kHz, %) ou fichier « fréquence, niveau ».\n"
                               "Personnalisé : séparateur, colonnes, unités et lignes à sauter au choix.")
        self.in_sep = QtWidgets.QComboBox()
        for k, t in SCAN_SEPS:
            self.in_sep.addItem(t, k)
        self.in_sep.setToolTip("Séparateur des colonnes du fichier.")
        self.in_fcol, self.in_lcol, self.in_skip = QtWidgets.QSpinBox(), QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        for sp_, v, tip in ((self.in_fcol, 1, "Numéro de la colonne des fréquences (1 = la première)."),
                            (self.in_lcol, 2, "Numéro de la colonne des niveaux."),
                            (self.in_skip, 0, "Lignes à sauter au début (titre, réglages…). Les lignes illisibles\n"
                                              "sont de toute façon ignorées.")):
            sp_.setRange(0 if sp_ is self.in_skip else 1, 200)
            sp_.setValue(v)
            sp_.setToolTip(tip)
        self.in_funit, self.in_lunit = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for u in SCAN_FREQ_UNITS:
            self.in_funit.addItem("auto (d'après les valeurs)" if u == "auto" else u, u)
        for k, t in SCAN_LEVEL_UNITS:
            self.in_lunit.addItem(t, k)
        self.in_funit.setToolTip("Unité des fréquences du fichier.")
        self.in_lunit.setToolTip("Unité des niveaux du fichier.")
        self.custom_box = QtWidgets.QWidget()
        cb = QtWidgets.QVBoxLayout(self.custom_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.addLayout(R("Séparateur :", self.in_sep, "Colonne fréquence :", self.in_fcol, "Colonne niveau :",
                       self.in_lcol, None))
        cb.addLayout(R("Fréquences en :", self.in_funit, "Niveaux en :", self.in_lunit, "Sauter :", self.in_skip,
                       "ligne(s)", None))
        il.addLayout(R(self.open_btn, self.cur_btn, self.cur_combo, None))
        il.addWidget(self.in_fmt)
        il.addWidget(self.custom_box)
        il.addWidget(self.src_lbl)
        lay.addWidget(ib)
        # ---- sortie
        ob = QtWidgets.QGroupBox("Sortie")
        ol = QtWidgets.QVBoxLayout(ob)
        self.out_fmt = QtWidgets.QComboBox()
        self.out_fmt.addItem("Shure WWB (scan à importer)", "wwb")
        self.out_fmt.addItem("Sennheiser WSM (format supposé, d'après les exports WSM)", "wsm")
        self.out_fmt.addItem("CSV personnalisé (EazyRF, tableur…)", "csv")
        self.out_fmt.setToolTip("WWB : « 470.000, -98 », MHz et dBm, sans en-tête.\n"
                                "WSM : kHz et % comme ses exports (import dans WSM non vérifié).\n"
                                "CSV : à toi de choisir séparateur, décimale, unités.")
        self.out_sep, self.out_dec = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for k, t in SCAN_SEPS[1:]:
            self.out_sep.addItem(t, k)
        self.out_dec.addItem("virgule (0,5)", ",")
        self.out_dec.addItem("point (0.5)", ".")
        self.out_funit, self.out_lunit = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for u in SCAN_FREQ_UNITS[1:]:
            self.out_funit.addItem(u, u)
        self.out_funit.setCurrentIndex(2)
        for k, t in SCAN_LEVEL_UNITS:
            self.out_lunit.addItem(t, k)
        self.out_hdr = QtWidgets.QCheckBox("Ligne d'en-tête")
        self.out_hdr.setChecked(True)
        for wd, tip in ((self.out_sep, "Séparateur des colonnes."), (self.out_dec, "Séparateur décimal."),
                        (self.out_funit, "Unité des fréquences."), (self.out_lunit, "Unité des niveaux."),
                        (self.out_hdr, "Ajoute « Fréquence (MHz) ; Niveau (dBm) » en première ligne.")):
            wd.setToolTip(tip)
        self.csv_box = QtWidgets.QWidget()
        xb = QtWidgets.QVBoxLayout(self.csv_box)
        xb.setContentsMargins(0, 0, 0, 0)
        xb.addLayout(R("Séparateur :", self.out_sep, "Décimale :", self.out_dec, self.out_hdr, None))
        xb.addLayout(R("Fréquences en :", self.out_funit, "Niveaux en :", self.out_lunit, None))
        ol.addWidget(self.out_fmt)
        ol.addWidget(self.csv_box)
        lay.addWidget(ob)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setToolTip("Les premières lignes du fichier qui sera écrit.")
        f_ = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        self.preview.setFont(f_)
        lay.addWidget(QtWidgets.QLabel("Aperçu du fichier de sortie :"))
        lay.addWidget(self.preview, 1)
        self.save_btn = QtWidgets.QPushButton("💾 Convertir et enregistrer…")
        self.save_btn.setToolTip("Écrit le fichier (un par fichier d'entrée s'il y en a plusieurs, à côté d'eux).")
        self.save_btn.clicked.connect(lambda *_: self.save())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(R(None, self.save_btn, close))
        for wd in (self.in_fmt, self.in_sep, self.in_funit, self.in_lunit, self.out_fmt, self.out_sep, self.out_dec,
                   self.out_funit, self.out_lunit):
            wd.currentIndexChanged.connect(lambda *_: self.reload())
        for wd in (self.in_fcol, self.in_lcol, self.in_skip):
            wd.valueChanged.connect(lambda *_: self.reload())
        self.out_hdr.toggled.connect(lambda *_: self.reload())
        self.reload()

    def _read(self, text):
        if self.in_fmt.currentData() == "custom":
            return parse_scan_custom(text, self.in_sep.currentData(), self.in_fcol.value() - 1,
                                     self.in_lcol.value() - 1, self.in_funit.currentData(),
                                     self.in_lunit.currentData(), self.in_skip.value())
        return parse_scan_text(text)

    def _write(self, F, L, title=""):
        return scan_write(F, L, self.out_fmt.currentData(), self.out_sep.currentData(), self.out_dec.currentData(),
                          self.out_funit.currentData(), self.out_lunit.currentData(), self.out_hdr.isChecked(), title)

    def open_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Scans à convertir", "",
                                                          "Scans (*.csv *.txt);;Tous les fichiers (*)")
        if paths:
            self.paths = list(paths)
            self.F = self.L = None
            self.reload()

    def use_current(self):
        F, L = self.owner.fresh_FL(use_max=self.cur_combo.currentData(), any_age=True)
        if F is None:
            self.src_lbl.setText("Pas encore de balayage : lance d'abord ▶ Démarrer.")
            return
        self.paths, self.F, self.L = [], F, L
        self.reload()

    def reload(self):
        self.custom_box.setVisible(self.in_fmt.currentData() == "custom")
        self.csv_box.setVisible(self.out_fmt.currentData() == "csv")
        F = L = None
        try:
            if self.paths:
                F, L, info = self._read(decode_text(Path(self.paths[0]).read_bytes()))
                kind = {"wsm": "export WSM", "simple": "fichier « fréquence, niveau »",
                        "custom": "CSV personnalisé"}.get(info["fmt"], info["fmt"])
                more = f" (+ {len(self.paths) - 1} autre(s) fichier(s))" if len(self.paths) > 1 else ""
                self.src_lbl.setText(f"✔ {os.path.basename(self.paths[0])}{more} : {kind}, {len(F)} points, "
                                     f"{F[0]:.3f} – {F[-1]:.3f} MHz, {L.min():.0f} … {L.max():.0f} dBm"
                                     + (f" · ⚠ {info['note']}" if info.get("note") else ""))
            elif self.F is not None:
                F, L = self.F, self.L
                self.src_lbl.setText(f"✔ Scan en cours : {len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz")
        except Exception as e:  # noqa: BLE001
            self.src_lbl.setText(f"⚠ Illisible avec ces réglages : {e}. Essaie « CSV personnalisé ».")
        self.cur = (F, L)
        if F is None:
            self.preview.setPlainText("")
            self.save_btn.setEnabled(False)
            return
        txt = self._write(F, L)
        lines = txt.splitlines()
        self.preview.setPlainText("\n".join(lines[:14]) + (f"\n… ({len(lines)} lignes)" if len(lines) > 14 else ""))
        self.save_btn.setEnabled(True)

    def save(self):
        ext = {"wwb": "_WWB.csv", "wsm": "_WSM.csv"}.get(self.out_fmt.currentData(), "_conv.csv")
        done, errs = [], []
        if not self.paths:
            F, L = self.cur
            out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le scan",
                                                           f"scan_{datetime.now():%Y%m%d_%H%M%S}{ext}", "CSV (*.csv)")
            if not out:
                return
            jobs = [(None, out, F, L)]
        else:
            jobs = []
            for k, p_ in enumerate(self.paths):
                dflt = Path(p_).with_name(Path(p_).stem + ext)
                if len(self.paths) == 1:
                    out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le scan converti", str(dflt),
                                                                   "CSV (*.csv)")
                    if not out:
                        return
                else:
                    out, n_ = dflt, 2
                    while Path(out).exists():
                        out = dflt.with_name(f"{dflt.stem} ({n_}).csv")
                        n_ += 1
                jobs.append((p_, str(out), None, None))
        for p_, out, F, L in jobs:
            try:
                if p_ is not None:
                    F, L, _i = self._read(decode_text(Path(p_).read_bytes()))
                with open(out, "w", newline="", encoding="utf-8") as fh:
                    fh.write(self._write(F, L, Path(p_).stem if p_ else ""))
                done.append(os.path.basename(out))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p_ or out)} : {e}")
        if done:
            self.src_lbl.setText(f"✔ {len(done)} fichier(s) écrit(s) : {', '.join(done[:3])}" + (" …" if len(done) > 3 else ""))
            self.owner.set_status(f"Scan converti : {', '.join(done[:3])}")
        if errs:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Conversion impossible pour :\n" + "\n".join(errs))


class LineCheckDialog(QtWidgets.QDialog):
    """Appel des micros : allume tes émetteurs un par un, chaque fréquence passe ✓ dès que son signal arrive."""
    COLS = ["État", "Nom", "MHz", "Niveau", "Heure", "Scène › Groupe"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Appel des micros")
        self.resize(760, 620)
        self.lc, self.keys, self.unknown, self.t0 = {}, [], {}, time.time()
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Allume tes émetteurs (micros, IEM, intercom…) : chaque fréquence passe ✓ dès que le tinySA voit son "
            "signal. À la fin, « Terminer » note le résultat dans le journal. Un signal inconnu tout près d'une "
            "fréquence qui manque = pack sans doute réglé sur le mauvais canal.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 3)
        lay.addWidget(info)
        self.what_combo = QtWidgets.QComboBox()
        self.what_combo.addItem("Les « doit émettre » de la couche active", "on")
        self.what_combo.addItem("Toute la couche active (sauf « doit rester libre »)", "all")
        self.what_combo.setToolTip("Quelles fréquences sont appelées. La couche active se choisit dans « Fréquences et "
                                   "couches » (Global = tout).")
        self.what_combo.currentIndexChanged.connect(lambda *_: self.restart())
        self.beep_chk = QtWidgets.QCheckBox("Bip à chaque ✓")
        self.beep_chk.setChecked(True)
        self.beep_chk.setToolTip("Un bip du PC quand une fréquence est validée : pratique quand tu es loin de l'écran.")
        self.restart_btn = QtWidgets.QPushButton("🔄 Recommencer")
        self.restart_btn.setToolTip("Remet toutes les fréquences « en attente » (nouvel appel).")
        self.restart_btn.clicked.connect(lambda *_: self.restart())
        lay.addLayout(owner._row(self.what_combo, self.beep_chk, None, self.restart_btn))
        self.run_lbl = QtWidgets.QLabel("La surveillance est arrêtée : démarre-la pour que l'appel avance.")
        self.run_btn = QtWidgets.QPushButton("▶ Démarrer la surveillance")
        self.run_btn.setToolTip("Lance les balayages (comme le bouton Démarrer en haut).")
        self.run_btn.clicked.connect(lambda *_: owner.toggle_run())
        self.run_box = QtWidgets.QWidget()
        rb = QtWidgets.QHBoxLayout(self.run_box)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.addWidget(self.run_lbl, 1)
        rb.addWidget(self.run_btn)
        lay.addWidget(self.run_box)
        self.sum_lbl = QtWidgets.QLabel("")
        f_ = self.sum_lbl.font()
        f_.setPointSize(f_.pointSize() + 5)
        f_.setBold(True)
        self.sum_lbl.setFont(f_)
        self.sum_lbl.setWordWrap(True)
        self.sum_lbl.setMinimumHeight(self.sum_lbl.fontMetrics().height() * 2 + 4)
        lay.addWidget(self.sum_lbl)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setFormat("%v / %m")
        self.bar.setToolTip("Fréquences validées / fréquences appelées.")
        lay.addWidget(self.bar)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Double-clic : voir la fréquence sur le spectre.")
        self.table.cellDoubleClicked.connect(lambda r, c: self._goto(r))
        for c, w_ in enumerate((96, 130, 72, 80, 64)):
            self.table.setColumnWidth(c, w_)
        lay.addWidget(self.table, 1)
        self.hint_lbl = QtWidgets.QLabel("")
        self.hint_lbl.setWordWrap(True)
        lay.addWidget(self.hint_lbl)
        self.ok_btn = QtWidgets.QPushButton("✓ Valider à la main")
        self.ok_btn.setToolTip("Valide les lignes choisies sans signal mesuré (vérifiée à l'oreille, émetteur hors "
                               "de portée du tinySA…).")
        self.ok_btn.clicked.connect(lambda *_: self.mark("manual"))
        self.skip_btn = QtWidgets.QPushButton("⏭ Ignorer")
        self.skip_btn.setToolTip("Retire les lignes choisies de l'appel (spare, émetteur pas utilisé ce soir…).")
        self.skip_btn.clicked.connect(lambda *_: self.mark("skip"))
        self.undo_btn = QtWidgets.QPushButton("↺ Remettre en attente")
        self.undo_btn.setToolTip("Les lignes choisies redeviennent « en attente ».")
        self.undo_btn.clicked.connect(lambda *_: self.mark(None))
        self.copy_btn = QtWidgets.QPushButton("📋 Copier le résumé")
        self.copy_btn.setToolTip("Copie le résultat (une ligne par fréquence) pour l'envoyer à la régie, sur WhatsApp…")
        self.copy_btn.clicked.connect(lambda *_: self.copy())
        self.done_btn = QtWidgets.QPushButton("📝 Terminer")
        self.done_btn.setToolTip("Note le résultat de l'appel dans le journal (et le journal auto CSV), puis ferme.")
        self.done_btn.clicked.connect(lambda *_: self.finish())
        lay.addLayout(owner._row(self.ok_btn, self.skip_btn, self.undo_btn, None, self.copy_btn, self.done_btn))
        self.restart()

    def _wanted(self):
        ow, mode = self.owner, self.what_combo.currentData()
        out = []
        for w in ow.watch:
            if not ow.in_scope(w) or ow.is_keep_free(w["status"]):
                continue
            if mode == "on" and not ow.is_keep_on(w["status"]):
                continue
            out.append(w)
        return out

    def restart(self):
        ws = self._wanted()
        if not ws and self.what_combo.currentData() == "on" and self.owner.watch:
            self.what_combo.blockSignals(True)          # aucun « doit émettre » : on appelle toute la couche
            self.what_combo.setCurrentIndex(1)
            self.what_combo.blockSignals(False)
            ws = self._wanted()
        self.keys = [int(round(w["freq"] * 1000)) for w in ws]
        self.lc = lc_new([(k, w["name"], w["freq"], self.owner.layer_text(w)) for k, w in zip(self.keys, ws)])
        self.keys = sorted(set(self.keys), key=lambda k: self.lc[k]["freq"])
        self.unknown, self.t0 = {}, time.time()
        self.table.setRowCount(len(self.keys))
        self.feed(beep=False)

    def feed(self, beep=True):
        """Appelé après chaque balayage (MainWindow.on_sweep)."""
        ow, now, new = self.owner, time.time(), 0
        for w in ow.watch:
            new += lc_feed(self.lc, int(round(w["freq"] * 1000)), w["state"], w["level"], now)
        for lst in ow.unk_now.values():
            for fr in lst:
                self.unknown[round(fr, 3)] = now
        self.unknown = {f: t for f, t in self.unknown.items() if now - t < 120}
        if new and beep and self.beep_chk.isChecked():
            QtWidgets.QApplication.beep()
        self.refresh()

    def refresh(self):
        ow, th = self.owner, self.owner.theme
        sm = lc_summary(self.lc)
        running = ow.is_running()
        self.run_box.setVisible(not running)
        col = {"ok": th["st_free"], "manual": th["st_free"], "weak": th["st_weak"], "skip": th["st_none"]}
        for r, k in enumerate(self.keys):
            e = self.lc[k]
            vals = [LC_TEXT[e["res"]], e["name"], f"{e['freq']:.3f}",
                    ow.lvl(e["lvl"], suffix=True) if e["lvl"] is not None else "",
                    datetime.fromtimestamp(e["t"]).strftime("%H:%M:%S") if e["t"] else "", e["layer"]]
            bg = QtGui.QColor(col.get(e["res"], th["ui_base"]))
            for c, v in enumerate(vals):
                it = self.table.item(r, c)
                if it is None:
                    it = QtWidgets.QTableWidgetItem()
                    self.table.setItem(r, c, it)
                if it.text() != v:
                    it.setText(v)
                if c == 0:
                    it.setBackground(bg)
                    it.setForeground(QtGui.QColor(contrast_text(bg.name())))
        self.bar.setMaximum(max(1, sm["n"]))
        self.bar.setValue(sm["ok"] + sm["weak"])
        self.sum_lbl.setText(sm["text"])
        self.sum_lbl.setStyleSheet(f"color:{th['st_free'] if sm['done'] else th['ui_text']}")
        hints = lc_hints(self.lc, list(self.unknown))
        self.hint_lbl.setText("" if not hints else "🔎 " + " · ".join(
            f"{n} ({fa:.3f}) manque, mais signal inconnu à {fu:.3f} MHz ({(fu - fa) * 1000:+.0f} kHz) : mauvais canal ?"
            for n, fa, fu in hints[:4]))

    def _sel_keys(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.keys[r] for r in rows if r < len(self.keys)]

    def mark(self, res):
        now = time.time()
        for k in self._sel_keys():
            e = self.lc[k]
            e["res"], e["t"] = res, (now if res else None)
            if res is None:
                e["lvl"] = None
        self.refresh()

    def _goto(self, r):
        if r < len(self.keys):
            f = self.lc[self.keys[r]]["freq"]
            try:
                self.owner.spec.getPlotItem().vb.setXRange(f - 2.0, f + 2.0, padding=0)
            except Exception:
                pass

    def summary_text(self):
        ow = self.owner
        return lc_text(self.lc, ow.show_meta.get("name", ""), datetime.now().strftime("%d/%m %H:%M"),
                       lambda v: ow.lvl(v, suffix=True))

    def copy(self):
        QtWidgets.QApplication.clipboard().setText(self.summary_text())
        self.owner.set_status("Résumé de l'appel copié : colle-le où tu veux.")

    def finish(self):
        sm = lc_summary(self.lc)
        self.owner.log_event(dict(name="Appel des micros", freq=0.0, note=sm["text"]), 0.0,
                             "APPEL OK" if sm["done"] else "APPEL INCOMPLET")
        self.owner.set_status(f"Appel des micros : {sm['text']}")
        self.close()

    def closeEvent(self, e):
        if self.owner._linecheck is self:
            self.owner._linecheck = None
        super().closeEvent(e)

    def done(self, r):
        if self.owner._linecheck is self:
            self.owner._linecheck = None
        super().done(r)


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
class LevelSpin(QtWidgets.QDoubleSpinBox):
    """Case de saisie d'un niveau : value() / setValue() restent en dBm (tout le code interne), mais l'affichage et
    la saisie se font dans l'unité choisie (dBm, dBµV ou %)."""
    unit = "dbm"                                  # unité commune, réglée par MainWindow.set_unit

    def textFromValue(self, v):
        return fmt_level(v, LevelSpin.unit, 1, suffix=True)

    def valueFromText(self, text):
        t = text.replace(UNIT_SUFFIX.get(LevelSpin.unit, ""), "").replace(",", ".").strip()
        try:
            return from_unit(float(t), LevelSpin.unit)
        except ValueError:
            return self.value()

    def validate(self, text, pos):
        t = text.replace(UNIT_SUFFIX.get(LevelSpin.unit, ""), "").replace(",", ".").strip()
        if t in ("", "-", "+"):
            return QtGui.QValidator.State.Intermediate, text, pos
        try:
            float(t)
            return QtGui.QValidator.State.Acceptable, text, pos
        except ValueError:
            return QtGui.QValidator.State.Invalid, text, pos

    def refresh(self):
        self.lineEdit().setText(self.textFromValue(self.value()))


class LevelAxis(pg.AxisItem):
    """Axe vertical du spectre gradué dans l'unité choisie (les courbes restent en dBm)."""
    unit = "dbm"

    def tickStrings(self, values, scale, spacing):
        return [fmt_level(v * scale, LevelAxis.unit, 0) for v in values]


class WallFullWindow(QtWidgets.QWidget):
    """Vraie fenêtre plein écran pour le mur (un panneau détaché refuse souvent le plein écran)."""

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Window)
        self.owner = owner
        self.setWindowTitle(f"{APP_NAME} – Mur de fréquences")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

    def closeEvent(self, e):
        if self.owner.wall_is_fullscreen():
            self.owner.wall_fullscreen(False)
        super().closeEvent(e)


class WallPickDialog(QtWidgets.QDialog):
    """Cases à cocher : quelles fréquences ont une tuile sur le mur (rangées par scène › groupe)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("Fréquences du mur")
        self.resize(460, 560)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Fréquence", "MHz"])
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.items = []                                   # (item, index dans owner.watch)
        groups = {}
        for i, w in enumerate(owner.watch):
            key = owner.layer_text(w) or "Sans scène"
            parent = groups.get(key)
            if parent is None:
                parent = QtWidgets.QTreeWidgetItem([key, ""])
                parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                self.tree.addTopLevelItem(parent)
                groups[key] = parent
            it = QtWidgets.QTreeWidgetItem([w["name"], f"{w['freq']:.3f}"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked if w.get("hide_wall") else Qt.CheckState.Checked)
            parent.addChild(it)
            self.items.append((it, i))
        self.tree.expandAll()
        b_all = QtWidgets.QPushButton("Tout cocher")
        b_none = QtWidgets.QPushButton("Tout décocher")
        b_all.clicked.connect(lambda *_: self._set_all(True))
        b_none.clicked.connect(lambda *_: self._set_all(False))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        info = QtWidgets.QLabel("Coche les fréquences qui ont une tuile sur le mur. Cocher une scène / un groupe "
                                "coche tout ce qu'il contient.")
        info.setWordWrap(True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.tree, 1)
        lay.addLayout(MainWindow._row(b_all, b_none, None))
        lay.addWidget(bb)

    def _set_all(self, on):
        for it, _i in self.items:
            it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def shown(self):
        """-> {index: True si la fréquence a une tuile}."""
        return {i: it.checkState(0) == Qt.CheckState.Checked for it, i in self.items}


class LabelsDialog(QtWidgets.QDialog):
    """Tes mots ET tes couleurs pour la colonne Signal (et le mur, la page web) : un réglage par situation."""

    def __init__(self, parent, labels, colors=None, default_color=None):
        super().__init__(parent)
        self.setWindowTitle("Mots et couleurs affichés")
        self.resize(720, 500)
        self._dflt = default_color or (lambda k: "#808080")
        self._cols = dict(colors or {})
        info = QtWidgets.QLabel("Pour chaque situation : le mot que tu veux voir (colonne Signal, mur, page web) et sa "
                                "couleur (clic sur la pastille). Vide = mot par défaut. Par défaut : vert = mon "
                                "émetteur est là (OK), bleu = libre, orange = à surveiller, rouge = problème.")
        info.setWordWrap(True)
        self.table = QtWidgets.QTableWidget(len(SIGNAL_LABELS), 3)
        self.table.setHorizontalHeaderLabels(["Situation", "Mot affiché", "Couleur"])
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for r, (key, situ, dflt) in enumerate(SIGNAL_LABELS):
            it = QtWidgets.QTableWidgetItem(situ)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(r, 0, it)
            ed = QtWidgets.QTableWidgetItem(labels.get(key, dflt))
            ed.setToolTip(f"Par défaut : {dflt}")
            self.table.setItem(r, 1, ed)
            b = QtWidgets.QPushButton()
            b.setToolTip("Clic : choisir la couleur de cette situation.")
            b.clicked.connect(lambda *_, k=key: self.pick_color(k))
            self.table.setCellWidget(r, 2, b)
        self._paint()
        b_reset = QtWidgets.QPushButton("Revenir aux mots et couleurs par défaut")
        b_reset.clicked.connect(lambda *_: self.reset())
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.addButton(b_reset, QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.table, 1)
        lay.addWidget(bb)

    def _paint(self):
        for r, (key, _s, _d) in enumerate(SIGNAL_LABELS):
            c = self._cols.get(key) or self._dflt(key)
            b = self.table.cellWidget(r, 2)
            b.setText(("● " if key in self._cols else "") + c)
            b.setStyleSheet(f"QPushButton{{background:{c};color:{contrast_text(c)};border-radius:4px;padding:2px 8px}}")

    def pick_color(self, key):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self._cols.get(key) or self._dflt(key)), self,
                                            "Couleur de la situation")
        if c.isValid():
            self._cols[key] = c.name()
            self._paint()

    def reset(self):
        for r, (_k, _s, d) in enumerate(SIGNAL_LABELS):
            self.table.item(r, 1).setText(d)
        self._cols = {}
        self._paint()

    def colors(self):
        """Seulement les couleurs choisies (clé -> "#rrggbb")."""
        return clean_colors(self._cols)

    def values(self):
        """Seulement les mots changés (clé -> texte)."""
        out = {}
        for r, (key, _situ, dflt) in enumerate(SIGNAL_LABELS):
            txt = self.table.item(r, 1).text().strip()
            if txt and txt != dflt:
                out[key] = txt[:30]
        return out


class ShowInfoDialog(QtWidgets.QDialog):
    """Infos d'un show : nom, lieu, dates, notes (pour le retrouver l'année suivante)."""

    def __init__(self, parent, meta, title="Infos du show"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 380)
        self.name = QtWidgets.QLineEdit(meta.get("name", ""))
        self.name.setPlaceholderText("ex. Festival des Vieilles Charrues")
        self.venue = QtWidgets.QLineEdit(meta.get("venue", ""))
        self.venue.setPlaceholderText("ex. Carhaix — scène Glenmor")
        today = QtCore.QDate.currentDate()
        self.d_from, self.d_to = QtWidgets.QDateEdit(), QtWidgets.QDateEdit()
        for wd, key in ((self.d_from, "date_from"), (self.d_to, "date_to")):
            wd.setCalendarPopup(True)
            wd.setDisplayFormat("dd/MM/yyyy")
            d = QtCore.QDate.fromString(meta.get(key, ""), "yyyy-MM-dd")
            wd.setDate(d if d.isValid() else today)
        self.notes = QtWidgets.QPlainTextEdit(meta.get("notes", ""))
        self.notes.setPlaceholderText("Contacts, coordinateur du site, antennes, ce qui a coincé l'an dernier…")
        f = QtWidgets.QFormLayout()
        f.addRow("Nom du show :", self.name)
        f.addRow("Lieu / scène :", self.venue)
        f.addRow("Du :", self.d_from)
        f.addRow("Au :", self.d_to)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(QtWidgets.QLabel("Notes :"))
        lay.addWidget(self.notes, 1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        a, b = self.d_from.date(), self.d_to.date()
        if b < a:
            b = a
        return dict(name=self.name.text().strip(), venue=self.venue.text().strip(),
                    date_from=a.toString("yyyy-MM-dd"), date_to=b.toString("yyyy-MM-dd"),
                    notes=self.notes.toPlainText().strip())


class ShowOpenDialog(QtWidgets.QDialog):
    """Liste des shows enregistrés (et des anciens profils) : nom, lieu, dates, nb de fréquences."""

    def __init__(self, parent, folders):
        super().__init__(parent)
        self.setWindowTitle("Ouvrir un show")
        self.resize(820, 460)
        self.path = ""
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Show", "Lieu", "Dates", "Fréquences", "Référence", "Fichier"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda *_: self.accept_sel())
        self.notes = QtWidgets.QLabel("")
        self.notes.setWordWrap(True)
        self.table.itemSelectionChanged.connect(self.on_sel)
        self.rows = []
        for folder, pat in folders:
            try:
                files = sorted(Path(folder).glob(pat))
            except OSError:
                files = []
            for fp in files:
                try:
                    doc = read_show(fp.read_text(encoding="utf-8"), fp.stem)
                except Exception:  # noqa: BLE001
                    continue
                self.rows.append((fp, doc, fp.stat().st_mtime))
        self.rows.sort(key=lambda r: (r[1]["meta"]["date_from"] or "", r[2]), reverse=True)
        self.table.setRowCount(len(self.rows))
        for i, (fp, doc, _mt) in enumerate(self.rows):
            sm = show_summary(doc)
            fr = f"{sm['n_freq']}" + (f" (dont {sm['n_blocks']} bloc(s))" if sm["n_blocks"] else "")
            for c, v in enumerate((sm["name"], sm["venue"], sm["dates"], fr, "✔" if sm["has_ref"] else "—",
                                   fp.name + ("  (ancien profil)" if fp.suffix == ".json" else ""))):
                self.table.setItem(i, c, QtWidgets.QTableWidgetItem(v))
        empty = QtWidgets.QLabel("Aucun show enregistré pour l'instant : 🎪 Shows › Enregistrer le show."
                                 if not self.rows else "")
        b_browse = QtWidgets.QPushButton("Parcourir…")
        b_browse.clicked.connect(lambda *_: self.browse())
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Open |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Open).setText("Ouvrir")
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept_sel)
        bb.rejected.connect(self.reject)
        bb.addButton(b_browse, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.table, 1)
        lay.addWidget(empty)
        lay.addWidget(self.notes)
        lay.addWidget(bb)
        if self.rows:
            self.table.selectRow(0)

    def on_sel(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            n = self.rows[r][1]["meta"]["notes"]
            self.notes.setText(f"Notes : {n}" if n else "")

    def accept_sel(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            self.path = str(self.rows[r][0])
            self.accept()

    def browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Ouvrir un show", str(SHOW_DIR),
                                                        f"Show (*{SHOW_EXT});;Ancien profil (*.json);;Tous (*)")
        if path:
            self.path = path
            self.accept()


class WallWindow(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setWindowTitle(f"{APP_NAME} – Mur de fréquences")
        self.resize(1100, 680)
        self.tiles, self._sig, self._vis, self._fs = [], [], None, 0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        top = FlowLayout()          # se replie : le panneau peut devenir étroit (avant : 929 px minimum)
        self.only_chk = QtWidgets.QCheckBox("Occupées / faibles")
        self.only_chk.toggled.connect(self.relayout)
        self.sum_lbl = QtWidgets.QLabel("")
        self.pick_btn = QtWidgets.QPushButton("📋 Choisir…")
        self.pick_btn.setToolTip("Choisis les fréquences qui ont une tuile sur le mur (case à cocher, par scène › groupe).\n"
                                 "Aussi : clic droit sur une tuile, ou dans la liste des fréquences.")
        self.pick_btn.clicked.connect(lambda *_: self.owner.pick_wall())
        self.alarm_chk = QtWidgets.QCheckBox("Alarmes toujours visibles")
        self.alarm_chk.setChecked(True)
        self.alarm_chk.setToolTip("Une fréquence retirée du mur y revient tant qu'elle est en alarme\n"
                                  "(ABSENT, CONFLIT, INTERMOD).")
        self.alarm_chk.toggled.connect(self.relayout)
        self.full_btn = QtWidgets.QPushButton("⛶ Plein écran")
        self.full_btn.clicked.connect(self.toggle_full)
        self.float_btn = QtWidgets.QPushButton("🗗 Détacher")
        self.float_btn.setToolTip("Détache le mur dans sa propre petite fenêtre : tu la poses où tu veux (2ᵉ écran,\n"
                                  "coin de l'écran) et tu choisis sa taille à la souris, les tuiles suivent.\n"
                                  "« Raccrocher » le remet en onglet à côté du spectre.")
        self.float_btn.clicked.connect(lambda *_: self.owner.wall_detach(not self.owner.dock_wall.isFloating()))
        self.screen_btn = QtWidgets.QPushButton("🖥 Autre écran")
        self.screen_btn.setToolTip("Envoie le mur dans une fenêtre sur l'autre écran (2ᵉ écran branché).\n"
                                   "F11 ensuite : plein écran sur cet écran-là.")
        self.screen_btn.clicked.connect(lambda *_: self.owner.wall_window_other_screen())
        try:
            n_scr = len(QtGui.QGuiApplication.screens())
        except TypeError:                     # (faux Qt des tests)
            n_scr = 1
        self.screen_btn.setVisible(n_scr > 1)
        self.size_combo = QtWidgets.QComboBox()
        for k, t in WALL_SIZES:
            self.size_combo.addItem(t, k)
        self.size_combo.setToolTip("Taille des tuiles. Auto : elles remplissent le panneau.\n"
                                   "Petites / Moyennes / Grandes : taille fixe, on fait défiler s'il y en a trop\n"
                                   "(pratique pour un mur rangé dans un petit panneau).")
        self.size_combo.currentIndexChanged.connect(lambda *_: self.relayout())
        for wd in (self.only_chk, self.alarm_chk, self.pick_btn, self.size_combo, self.float_btn, self.screen_btn,
                   self.full_btn):
            top.addWidget(wd)
        lay.addLayout(top)
        self.sum_lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        lay.addWidget(self.sum_lbl)
        self.host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.host)
        self.scroll.setMinimumSize(120, 60)
        self.scroll.viewport().installEventFilter(self)     # la barre qui se replie change la place des tuiles
        lay.addWidget(self.scroll, 1)
        for key, fn in (("F11", self.toggle_full), ("Escape", self.leave_full)):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)    # seulement quand le mur a le focus
            sc.activated.connect(fn)
        self.only_chk.setToolTip("N'affiche que les fréquences occupées ou faibles : les tuiles grossissent.")
        self.full_btn.setToolTip("Le mur se détache et passe en plein écran (F11 ; Échap pour revenir).")
        self.sum_lbl.setToolTip("Résumé : couche affichée, nombre de fréquences, occupées, faibles.")
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.relayout)

    def tile_menu(self, k, pos):
        if k >= len(self.owner.watch):
            return
        m = QtWidgets.QMenu(self)
        a_hide = m.addAction(f"Retirer « {self.owner.watch[k]['name']} » du mur")
        a_pick = m.addAction("📋 Choisir les fréquences du mur…")
        act = m.exec(self.tiles[k].mapToGlobal(pos))
        if act is a_hide:
            self.owner.set_wall_rows([k], False)
        elif act is a_pick:
            self.owner.pick_wall()

    def toggle_full(self):
        self.owner.wall_fullscreen(not self.owner.wall_is_fullscreen())

    def leave_full(self):
        if self.owner.wall_is_fullscreen():
            self.owner.wall_fullscreen(False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def eventFilter(self, obj, e):
        if e.type() == QtCore.QEvent.Type.Resize and obj is self.scroll.viewport():
            self._timer.start()
        return super().eventFilter(obj, e)

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
            lb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lb.customContextMenuRequested.connect(lambda pos, k=len(self.tiles): self.tile_menu(k, pos))
            self.tiles.append(lb)
        self._sig = [None] * len(self.tiles)
        self._vis = None
        self.relayout()
        self.refresh()

    def _visible_idx(self):
        ow = self.owner
        ws = ow.watch
        return [i for i, w in enumerate(ws)
                if wall_visible(w, ow.in_scope(w), ow.in_alarm(w), self.only_chk.isChecked(), self.alarm_chk.isChecked())]

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
        size = self.size_combo.currentData() or "auto"
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if size in WALL_TILE
                                               else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vp = self.scroll.viewport()
        W, H = vp.width(), vp.height()
        cols, rows, tile_h, fs = wall_grid(n, W, H, size)
        for k in range(self.grid.columnCount() + 1):
            self.grid.setColumnStretch(k, 0)
        for k in range(self.grid.rowCount() + 2):
            self.grid.setRowStretch(k, 0)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        for r in range(rows):
            self.grid.setRowStretch(r, 0 if tile_h else 1)
        if tile_h:
            self.grid.setRowStretch(rows, 1)            # tuiles fixes : calées en haut
        for k, i in enumerate(vis):
            t = self.tiles[i]
            if tile_h:
                t.setFixedHeight(tile_h)
            else:
                t.setMinimumHeight(0)
                t.setMaximumHeight(16777215)
            self.grid.addWidget(t, k // cols, k % cols)
            t.setVisible(True)
        if tile_h:
            self.host.setMaximumHeight(16777215)
            self.host.setMinimumHeight(rows * (tile_h + 6))
        else:       # auto : calé sur la partie visible (le texte replié des tuiles réclamerait plus de hauteur)
            self.host.setMinimumHeight(0)
            self.host.setMaximumHeight(max(1, H))
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
            lv = ow.lvl(w["level"], suffix=True)
            pct = w["occw"].pct()
            layer = "" if one_group else ow.layer_text(w)
            sig = (st, conf, absn, lv, w["name"], w["status"], round(w["freq"], 3), fs, layer,
                   None if pct is None else int(pct), th["ui_base"], th["st_occ"], th["st_free"], th["st_weak"])
            if self._sig[i] == sig:
                continue
            self._sig[i] = sig
            sig_txt, tone, tone_col = ow.sig_view(w)
            bg = {"bad": blend(tone_col, base, 0.85), "warn": blend(tone_col, base, 0.6),
                  "ok": blend(tone_col, base, 0.45), "free": blend(tone_col, base, 0.45)}.get(tone, blend(th["st_none"], base, 0.25))
            fg = contrast_text(bg)
            bd = ow.status_color(w["status"]) if w["status"] else bg
            name = ("⚠ " if (conf or absn) else "") + (w["name"] or "—")
            occ = "" if pct is None else f" · occ. {pct:.0f} %"
            html = (f"<div style='font-size:{fs}px;font-weight:bold'>{_html_esc(name)}</div>"
                    f"<div style='font-size:{max(8, int(fs * 0.72))}px'>{w['freq']:.3f} MHz</div>"
                    f"<div style='font-size:{int(fs * 0.95)}px'>{_html_esc(sig_txt)} · {lv}{occ}</div>")
            if layer:
                html += f"<div style='font-size:{max(8, int(fs * 0.6))}px'>{_html_esc(layer)}</div>"
            self.tiles[i].setText(html)
            self.tiles[i].setStyleSheet(
                "QLabel{background:%s;color:%s;border:4px solid %s;border-radius:8px;}" % (bg, fg, bd))
        n_hid = sum(1 for w in ow.watch if ow.in_scope(w) and w.get("hide_wall"))
        self.sum_lbl.setText(f"  {ow.scope_text()} · {n_tot} fréquences · {n_occ} occupée(s) · {n_weak} faible(s)"
                             + (f" · {n_hid} retirée(s) du mur" if n_hid else ""))


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
        self._linecheck = None          # appel des micros en cours (LineCheckDialog)
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
        self.wall = None                # mur de fréquences (panneau dock_wall, créé avec les panneaux)
        self._log_err_shown = False
        self.log_dir = LOG_DIR
        self.export_prefs = {}
        self.latest, self.latest_t, self.maxhold, self.partial_data = {}, {}, {}, {}
        self.history = {}          # anciens balayages complets par bande (rémanence)
        self._hist_items = []
        self.unk_now, self.unk_seen = {}, {}
        self.worker = None              # 1er tinySA (compatibilité) ; tous les appareils : self.workers
        self.workers = []
        self.dev2 = dict(on=False, addr="", offset=0.0)   # 2ᵉ tinySA : USB (« COM4 ») ou réseau (« 192.168.1.20:5025 »)
        self.dev_live = [True, True]    # liaison de chaque appareil (False = perdue, ses bandes passent sur l'autre)
        self.dev_cycle = {}
        self.dev_names = ["tinySA 1", "tinySA 2"]   # noms de position (« Plateau », « FOH »…)
        self.band_src = {}              # id bande -> n° du tinySA qui a fourni le dernier balayage
        self._calib = None              # calibration en cours : {band, t0, data:{0:[], 1:[]}}
        self._strong_src = {}           # alarmes « trop fort » en cours -> bande qui les a vues
        self.sig_labels = {}            # tes mots pour la colonne Signal (clé SIGNAL_LABELS -> texte)
        self.sig_colors = {}            # tes couleurs par situation (clé SIGNAL_LABELS -> "#rrggbb")
        self.sdr_cfg = dict(dir="", lna=24, vga=20, amp=False)    # V8 : HackRF / RTL-SDR
        self.plan_opts = dict(sep=int(round(PF_SEP * 1000)), filt=32.0, step=25, prof="")   # 🧮 : kHz, MHz, kHz, profil
        self.unit = "dbm"               # unité d'affichage des niveaux (en interne : toujours dBm)
        self.show_meta = {k: "" for k in SHOW_META}   # show en cours (🎪 Shows)
        self.show_path = ""
        self.recent_shows = []
        self.notify_cfg = dict(mode="off", service="ntfy", server="https://ntfy.sh", topic="", tg_token="",
                               tg_chat="", site="")
        self.notifier = None
        self._notified = set()          # id des alarmes déjà traitées pour l'envoi sur téléphone
        self.web_cfg = dict(on=False, port=WEB_PORT, pin="", password="", views=web_views_norm(None))
        self._web_spec = b'{"t":0,"bands":[]}'
        self._web_acks = queue.Queue()      # acquittements reçus de la page web (fil du serveur → fil Qt)
        self.web = None
        self._web_json = b"{}"
        self.view_id = -1
        self.wf_hist, self.wf_id = None, None
        self._fit_x = True
        self._updating = False
        self._last_xy = None
        self.last_cycle = 10.0
        self.labels = []
        self._mk_items = {}
        self.mk = mk_default()          # repères du spectre : filtres (état, couche, statut), style
        self.expert = False             # mode simple par défaut (☰ Plus › Mode expert)
        self.sections_open = dict(self.SECTIONS_OPEN)
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
        self._autosave = QtCore.QTimer(self)          # coupure de courant / plantage : on perd au plus une minute
        self._autosave.setInterval(AUTOSAVE_MS)
        self._autosave.timeout.connect(self._save_config)
        self._autosave.start()
        self._first_show = True

    def _fit_to_screen(self):
        """Petit écran (portable 1366×768…) : la fenêtre ne doit pas déborder."""
        scr = QtGui.QGuiApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        if g.width() > 0 and g.height() > 0:
            self.resize(min(self.width(), g.width()), min(self.height(), g.height()))

    def showEvent(self, e):
        super().showEvent(e)
        if getattr(self, "_first_show", False):
            self._first_show = False
            QtCore.QTimer.singleShot(120, self._late_layout)    # la fenêtre a alors sa vraie taille

    def _late_layout(self):
        if not self._state_restored:
            if self.view_id == -1:
                self.dock_wf.hide()      # pas de waterfall en vue « tout le spectre » : le spectre prend la place
            self._dock_sizes()

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

    # ------------------------------------------------------------------ aide au survol
    TIPS_ATTR = dict(
        port_combo="Port USB du tinySA (✔ tinySA = reconnu automatiquement). Ferme tinySA-App avant : un seul\n"
                   "logiciel à la fois peut parler au tinySA. ⟳ : relire la liste des ports.",
        start_btn="Lance / arrête le balayage (les deux tinySA si le 2ᵉ est activé). Pendant un arrêt, si le tinySA\n"
                  "ne répond plus, le port est fermé au bout de 4 s.",
        thr_spin="Seuil « occupé » : au-dessus, la fréquence est OCCUPÉE (rouge). « Auto » le place juste\n"
                 "au-dessus du bruit mesuré. Tu peux aussi tirer la ligne rouge sur le spectre.",
        weak_chk="Zone « faible » (jaune) entre ce niveau et le seuil occupé : un signal lointain ou un émetteur\n"
                 "en train de partir. Décoche pour n'avoir que libre / occupé.",
        weak_spin="Niveau à partir duquel un signal est « faible » (ligne pointillée sur le spectre).",
        ref_chk="Seuil relatif : occupé = courbe de référence du lieu + la marge (utile quand le bruit de fond\n"
                "n'est pas plat). Capture la référence avec 📏 Référence au-dessus du spectre.",
        ref_margin="Marge au-dessus de la courbe de référence pour déclarer « occupé ».",
        win_spin="Largeur de la fenêtre de mesure autour de chaque fréquence (± kHz) : le niveau retenu est le max\n"
                 "dans cette fenêtre.",
        occ_combo="Durée sur laquelle est calculé le taux d'occupation (colonne Occ.).",
        absent_spin="Une fréquence « Doit émettre » silencieuse plus longtemps que ça déclenche ⚠ ABSENT.",
        alert_chk="Son des alarmes (CONFLIT / ABSENT / appareil perdu). Les critiques sont répétées toutes les 10 s\n"
                  "jusqu'à l'acquittement.",
        unk_chk="Repère les pics au-dessus du seuil qui ne sont dans aucune liste : pointillés sur le spectre,\n"
                "« INCONNU » dans le journal.",
        rbw_combo="Résolution du tinySA (filtre). Petit RBW = plus précis et plancher plus bas, mais balayage\n"
                  "beaucoup plus lent. 100 kHz convient au monitoring HF.",
        zrbw_combo="RBW utilisé en zoom live. « Auto » l'adapte à la largeur zoomée (conseillé : un RBW étroit\n"
                   "sur une zone large rend le scan très lent).",
        input_combo="Entrée du tinySA Ultra : basse (≤ 800 MHz) ou haute. « Auto » choisit selon la fréquence.",
        lna_combo="Préampli du tinySA : plus sensible, mais risque de saturation près des émetteurs.",
        att_combo="Atténuateur d'entrée : à monter si des signaux forts saturent (produits parasites).",
        offset_spin="Correction ajoutée à toutes les mesures (câble, antenne, splitter…).",
        seg_combo="Taille des morceaux envoyés au tinySA à chaque commande. « Auto » selon le modèle.",
        points_combo="Points par balayage et par bande : plus il y en a, plus c'est fin… et plus c'est long.",
        country_combo="Pays : canaux TV et attributions affichés sous le spectre, canaux proposés pour les blocs\n"
                      "Spectera. « Éditer le plan » pour l'adapter.",
        alloc_chk="Affiche sous le spectre à qui appartient chaque bande (TNT + micros, 4G/5G, militaire…).",
        tv_chk="Affiche les numéros des canaux TV sous le spectre.",
        view_combo="Toutes les bandes, ou une seule (affiche aussi son waterfall).",
        hold_chk="Max hold : garde en orange le maximum atteint à chaque fréquence (Reset max pour effacer).",
        showref_chk="Affiche la courbe de référence du lieu (bruit de fond enregistré) sous le spectre.",
        filter_edit="Filtre la liste : un bout de nom, une fréquence (« 606 »), un statut…",
        occ_only_chk="N'affiche que les fréquences occupées ou faibles.",
        preset_combo="Ajoute une bande toute faite (UHF, Spectera, 1G4, 2,4 GHz, aperçu de tout le tinySA…).",
    )
    TIPS_TEXT = {
        "▶ Démarrer": TIPS_ATTR["start_btn"],
        "＋ Bande": "Ajoute une bande à balayer (modifie ensuite début, fin et pas dans la table).",
        "Supprimer": "Supprime la ou les lignes sélectionnées.",
        "Reset max": "Efface le max hold (courbe orange) et repart de zéro.",
        "📷 Capture": "Enregistre une image PNG du spectre.",
        "💾 Exporter le scan…": "Exporte le dernier balayage (CSV) pour WWB, WSM ou un tableur.",
        "Exporter le journal": "Enregistre le journal des événements en CSV.",
        "Effacer": "Vide le journal affiché (le fichier du journal automatique est gardé).",
        "📂 Ouvrir le dossier": "Ouvre le dossier des journaux, enregistrements et rapports.",
        "Choisir le dossier…": "Change le dossier des journaux, enregistrements et rapports.",
        "＋ Ajouter": "Ajoute une fréquence à surveiller (dans la couche active).",
        "📥 Importer CSV…": "Importe une liste de fréquences (EazyRF, WWB, WSM, Excel…). Tu peux aussi glisser le\n"
                           "fichier sur la fenêtre.",
        "Coller une liste": "Colle une liste copiée (Excel, mail…) : nom et fréquence par ligne.",
        "📤 Exporter": "Exporte ta liste de fréquences (CSV).",
        "Bandes depuis la liste": "Remplace les bandes par des zones qui couvrent juste tes fréquences (scan plus rapide).",
        "＋ Scène": "Crée une scène (ex. Grande scène) pour ranger les fréquences.",
        "＋ Groupe": "Crée un groupe dans une scène (ex. Micros HF, IEM, Intercom). Clic droit sur un groupe :\n"
                     "priorité des alarmes, couleur, import.",
        "Afficher": TIPS_ATTR["showref_chk"],
        "✔✔ Tout acquitter": "Coupe le son de toutes les alarmes en cours ; elles restent affichées tant que la\n"
                             "cause est là.",
        "🗑 Effacer les terminées": "Retire de la liste les alarmes terminées (le journal les garde).",
    }

    TIPS_MENU = {
        "📡 Réglages SDR": "V8 : HackRF One / RTL-SDR à la place (ou en plus) d'un tinySA : dossier des outils\n"
                          "(hackrf_sweep, rtl_power), gains, et comment les installer.",
        "🎤 Appel des micros": "Line check : allume tes émetteurs un par un, chaque fréquence passe ✓ quand son\n"
                               "signal arrive ; résumé « 14 / 16 OK, manquent… » noté au journal (Ctrl+L).",
        "🧮 Vérifier le plan": "Comme EazyRF : écart entre porteuses et intermod selon des tolérances, un verdict\n"
                               "par fréquence, et une fréquence de remplacement compatible.",
        "⚡ Intermodulation": "Produits d'intermodulation de tes émetteurs (2 / 3 / 5 TX) : ce qui retombe sur tes\n"
                             "fréquences, ou d'où peut venir un signal inconnu.",
        "🆘 Fréquence de secours": "Propose des fréquences libres d'après le spectre mesuré, sans intermod avec ta liste.",
        "⏪ Relecture": "Revoir le spectre des 30 dernières minutes (ou d'un enregistrement), saut aux événements.",
        "📄 Rapport de show": "Rapport de fin de show (alarmes, occupation, spectre) en HTML, imprimable en PDF.",
        "📤 Exporter les fréquences": "Exporte la liste par scène / groupe, pour EazyRF, WWB, WSM ou un tableur.",
        "📏 Importer un scan": "Charge un scan WSM / WWB comme courbe de référence (bruit de fond du lieu).",
        "🔁 Convertir / exporter un scan": "Convertit un scan d'un logiciel à l'autre (WSM, WWB, CSV au choix :\n"
                                          "colonnes, unités, séparateur), ou exporte le scan en cours.",
        "✏ Nommer la sélection": "Nomme d'un coup les lignes choisies : HF 1, HF 2… IEM 1…",
        "⇣ Numéroter vers le bas": "Numérote vers le bas à partir de la 1ʳᵉ ligne sélectionnée (Ctrl+D).",
        "Mon vocabulaire": "Mots proposés par l'auto-complétion des noms (MIC, HF, IEM, Intercom…).",
        "📡 Relais réseau": "Partage le tinySA branché sur CE PC pour l'utiliser comme 2ᵉ tinySA depuis un autre PC.",
        "🩺 Diagnostic": "Écrit un fichier avec les réglages, les bandes et les derniers échanges avec le tinySA,\n"
                         "à envoyer quand quelque chose bugue (aussi écrit tout seul quand le tinySA décroche).",
        "📣 Alertes": "Alertes sur téléphone (ntfy / Telegram) et page web en lecture seule pour l'équipe.",
        "📶 Ajouter un bloc": "Ajoute un porteur large Sennheiser Spectera / WMAS (canal 6 / 8 MHz) à surveiller.",
        "🧱 Mur": "Grandes tuiles, une par fréquence : panneau à détacher sur un 2ᵉ écran (F11 plein écran).",
        "🔤 Mots": "Choisis tes mots ET leurs couleurs pour la colonne Signal : OK, libre, ABSENT, INTERMOD, CONFLIT…",
        "ℹ À propos": "Version de TinySA Monitor, du tinySA branché, et où sont la config et les journaux.",
        "🎛 Mode expert": "Affiche tous les réglages (RBW, entrée, LNA, atténuateur, offset, calibration, relais…).",
        "Disposition standard": "Remet les panneaux à leur place d'origine.",
        "Double écran": "Envoie la liste, le journal et le waterfall sur l'autre écran.",
    }

    def _install_tips(self):
        """Une explication sur chaque bouton / case / liste, aussi recopiée dans la barre d'état au survol."""
        for name, tip in self.TIPS_ATTR.items():
            w_ = getattr(self, name, None)
            if w_ is not None and not w_.toolTip():
                w_.setToolTip(tip)
        for w_ in self.findChildren(QtWidgets.QAbstractButton):
            if not w_.toolTip() and w_.text() in self.TIPS_TEXT:
                w_.setToolTip(self.TIPS_TEXT[w_.text()])
        for btn, _box in self.sections.values():
            btn.setToolTip("Clic : replier / déplier cette section (l'état est mémorisé).")
        for w_ in self.findChildren(QtWidgets.QWidget):
            if w_.toolTip() and not w_.statusTip():
                w_.setStatusTip(w_.toolTip().split("\n")[0])
        menus = set(self.findChildren(QtWidgets.QMenu))
        todo = [self.more_menu]                      # sous-menus (Outils…) rattachés à des boutons hors fenêtre
        while todo:
            m_ = todo.pop()
            menus.add(m_)
            todo += [a_.menu() for a_ in m_.actions() if a_.menu() is not None and a_.menu() not in menus]
        for m_ in menus:
            m_.setToolTipsVisible(True)
            for a_ in m_.actions():
                tip = next((t for k, t in self.TIPS_MENU.items() if a_.text().startswith(k)), None)
                if tip:
                    a_.setToolTip(tip)
                    a_.setStatusTip(tip.split("\n")[0])

    SECTIONS_OPEN = dict(detect=True, bands=True, measure=False, dev2=False, country=False)

    def _section(self, key, box):
        """Groupe de réglages repliable : un bouton-titre (▾ / ▸) au-dessus du contenu."""
        title = box.title()
        box.setTitle("")
        wrap = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(wrap)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(0)
        btn = QtWidgets.QToolButton()
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        btn.setStyleSheet("QToolButton{border:none;font-weight:bold;text-align:left;padding:4px 2px;}")
        v.addWidget(btn)
        v.addWidget(box)

        def show(on):
            box.setVisible(on)
            btn.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
            self.sections_open[key] = bool(on)

        btn.setText(title)
        btn.toggled.connect(lambda *_: show(btn.isChecked()))
        self.sections[key] = (btn, box)
        self.sections_open = getattr(self, "sections_open", dict(self.SECTIONS_OPEN))
        on = self.sections_open.get(key, True)
        btn.setChecked(on)
        show(on)
        return wrap

    def set_expert(self, on):
        """Mode simple : seulement l'essentiel (seuils, bandes, 2ᵉ tinySA, pays). Expert : tous les réglages."""
        self.expert = bool(on)
        for form, w_ in getattr(self, "_expert_rows", []):
            form.setRowVisible(w_, self.expert)
        for w_ in (getattr(self, "ref_row", None), getattr(self, "persist_combo", None)):
            if w_ is not None:
                w_.setVisible(self.expert)
        if hasattr(self, "expert_act"):
            self.expert_act.setChecked(self.expert)
        if hasattr(self, "expert_hint"):
            self.expert_hint.setText("🎛 Mode expert : revenir au mode simple" if self.expert
                                     else "🎛 Mode simple : afficher tous les réglages")

    def open_section(self, key, on=True):
        if key in self.sections:
            self.sections[key][0].setChecked(on)

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
        prof_btn = QtWidgets.QPushButton("🎪 Shows")
        prof_btn.setToolTip("Enregistre / rappelle un show d'une année à l'autre : fréquences, scènes, bandes, statuts,\n"
                            "seuils, courbe de référence du lieu, infos et notes. Tes préférences (couleurs,\n"
                            "fenêtres, alertes, 2ᵉ tinySA…) ne bougent pas.  Ctrl+S : enregistrer.")
        self.show_menu = QtWidgets.QMenu(prof_btn)
        self.show_menu.aboutToShow.connect(lambda *_: self._build_show_menu())
        pmenu = self.show_menu
        sc_save = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(lambda *_: self.save_show())
        sc_lc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        sc_lc.activated.connect(lambda *_: self.open_linecheck())
        prof_btn.setMenu(pmenu)
        tools_btn = QtWidgets.QPushButton("🔧 Outils")
        tools_btn.setToolTip("Intermodulation, fréquence de secours, relecture, rapport, scans WSM/WWB, export par scène, "
                             "nommage rapide, vocabulaire.")
        tmenu = QtWidgets.QMenu(tools_btn)
        for txt, fn in (("🎤 Appel des micros (line check)…  Ctrl+L", lambda *_: self.open_linecheck()),
                        (None, None),
                        ("🧮 Vérifier le plan de fréquences (compatibilité)…", lambda *_: self.open_plan_check()),
                        ("⚡ Intermodulation (2 / 3 / 5 TX)…", lambda *_: self.open_intermod()),
                        ("🆘 Fréquence de secours…", lambda *_: self.open_rescue()),
                        (None, None),
                        ("⏪ Relecture : revoir le spectre…", lambda *_: self.open_replay()),
                        ("📄 Rapport de show…", lambda *_: self.make_report()),
                        ("📤 Exporter les fréquences (par scène / groupe)…", lambda *_: self.export_by_scene()),
                        (None, None),
                        ("📏 Importer un scan WSM / WWB comme référence…", lambda *_: self.import_scan_as_ref()),
                        ("🔁 Convertir / exporter un scan (WSM, WWB, CSV…)…", lambda *_: self.open_scan_convert()),
                        (None, None),
                        ("✏ Nommer la sélection (HF 1, HF 2…)…", lambda *_: self.quick_name_dialog()),
                        ("⇣ Numéroter vers le bas depuis la 1ʳᵉ ligne  (Ctrl+D)", lambda *_: self.fill_down_names()),
                        ("Mon vocabulaire…", lambda *_: self.edit_vocab()),
                        (None, None),
                        ("📡 Relais réseau : partager le tinySA de CE PC…", lambda *_: self.open_relay()),
                        ("🩺 Diagnostic tinySA (fichier pour le support)…", lambda *_: self.open_diag()),
                        ("📡 Réglages SDR (HackRF, RTL-SDR)…", lambda *_: self.open_sdr()),
                        ("📣 Alertes téléphone et page web…", lambda *_: self.open_alerts()),
                        (None, None),
                        ("📶 Ajouter un bloc Spectera / WMAS (canal 6 / 8 MHz)…", lambda *_: self.add_block_dialog())):
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
        # barre du haut épurée : l'essentiel visible, le reste dans « ☰ Plus »
        more_btn = QtWidgets.QPushButton("☰ Plus")
        more_btn.setToolTip("Outils (intermodulation, secours, relecture, rapport, scans WSM/WWB…), fenêtres et\n"
                            "dispositions, mur de fréquences, couleurs, statuts, mode simple / expert.")
        self.more_menu = QtWidgets.QMenu(more_btn)
        more_btn.setMenu(self.more_menu)
        tmenu.setTitle("🔧 Outils")
        self.win_menu.setTitle("🪟 Fenêtres et dispositions")
        self.more_menu.addMenu(tmenu)
        self.more_menu.addMenu(self.win_menu)
        self.more_menu.addSeparator()
        self.more_menu.addAction("🎤 Appel des micros (line check)…").triggered.connect(lambda *_: self.open_linecheck())
        self.more_menu.addAction("🧱 Mur de fréquences (2ᵉ écran)").triggered.connect(lambda *_: self.open_wall())
        self.more_menu.addAction("🎨 Couleurs…").triggered.connect(lambda *_: self.edit_colors())
        self.more_menu.addAction("🏷 Statuts…").triggered.connect(lambda *_: self.edit_statuses())
        self.more_menu.addAction("🔤 Mots et couleurs (OK, libre, ABSENT…)…").triggered.connect(
            lambda *_: self.edit_labels())
        self.more_menu.addSeparator()
        self.more_menu.addAction(f"ℹ À propos (version {APP_VER})…").triggered.connect(lambda *_: self.show_about())
        self.expert_act = self.more_menu.addAction("🎛 Mode expert (tous les réglages)")
        self.expert_act.setCheckable(True)
        self.expert_act.triggered.connect(lambda *_: self.set_expert(self.expert_act.isChecked()))
        self._spare_btns = [tools_btn, win_btn, wall_btn, colors_btn, status_btn]   # gardés pour leurs menus
        # barre d'outils sur toute la largeur (au-dessus des panneaux) : jamais coupée par les colonnes
        tb = QtWidgets.QToolBar("Commandes")
        tb.setObjectName("barre_commandes")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setEnabled(False)
        port_box = QtWidgets.QWidget()
        ph = QtWidgets.QHBoxLayout(port_box)
        ph.setContentsMargins(4, 2, 8, 2)
        for wd in (QtWidgets.QLabel("Port :"), self.port_combo, btn_ports, self.demo_chk, self.info_lbl):
            ph.addWidget(wd)
        tb.addWidget(port_box)
        for wd in (self.start_btn, prof_btn, self.alarm_btn, more_btn):
            tb.addWidget(wd)
            tb.addSeparator()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.cmd_bar = tb

        # --- panneau de gauche : réglages
        self.points_combo = self._combo([(f"{p:,}".replace(",", " "), p) for p in POINTS_CHOICES], 1000)
        self.points_combo.setToolTip("Nombre de points par balayage et par bande (appliqué à toutes les bandes).\n"
                                     "Plus il y en a, plus c'est précis… et plus c'est long.")
        self.points_combo.activated.connect(self.apply_points)
        self.rbw_combo = self._combo([("Auto", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST], 100)
        self.zrbw_combo = self._combo([("Auto (selon zoom)", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST])
        self.input_combo = self._combo([("Auto", "auto"), ("Basse (≤ 800 MHz)", "low"),
                                        ("Haute (> 800 MHz)", "high")])
        self.input_combo.setToolTip("Auto : tinySA d'origine → prise « haute » au-delà de 800 MHz ; tinySA Ultra (une\n"
                                    "seule prise) → rien n'est changé, il passe en mode « ultra » au-delà de 800 MHz.\n"
                                    "Basse / Haute : forcé (seulement utile sur un tinySA d'origine).")
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
        self.baud_combo = self._combo([(f"{b:,}".replace(",", " ") + " bauds", b)
                                       for b in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)], 115200)
        self.baud_combo.setToolTip("Vitesse du port série. En USB elle ne sert à rien (port COM virtuel : la vitesse\n"
                                   "est ignorée). Seulement pour un vrai port série (adaptateur USB-série, connecteur\n"
                                   "interne du tinySA, module série réseau) : mets la même que dans le tinySA.")
        mform.addRow("Vitesse série :", self.baud_combo)
        mform.addRow(self.est_lbl)

        self.thr_spin = LevelSpin()
        self.thr_spin.setRange(-130, 0)
        self.thr_spin.setValue(-80)
        self.thr_spin.valueChanged.connect(self._thr_from_spin)
        auto_btn = QtWidgets.QPushButton("Auto")
        auto_btn.setToolTip("Seuil = niveau médian mesuré + 10 dB")
        auto_btn.clicked.connect(self.auto_threshold)
        self.weak_chk = QtWidgets.QCheckBox("Niveau « faible » à partir de")
        self.weak_chk.setChecked(True)
        self.weak_spin = LevelSpin()
        self.weak_spin.setRange(-130, 0)
        self.weak_spin.setValue(-90)
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
        self.unit_combo = self._combo([(t, k) for k, t in LEVEL_UNITS], "dbm")
        self.unit_combo.setToolTip("Unité des niveaux partout (seuils, liste, mur, spectre, alarmes, page web).\n"
                                   "dBµV = dBm + 107 (50 Ω). % = échelle Sennheiser WSM : 0 % = −120 dBm, 100 % = 0 dBm.\n"
                                   "Les fichiers (journal CSV, shows, exports) restent en dBm.")
        self.unit_combo.currentIndexChanged.connect(lambda *_: self.set_unit(self.unit_combo.currentData()))
        dform.addRow("Unité des niveaux :", self.unit_combo)
        dform.addRow("Seuil « occupé » :", self._row(self.thr_spin, auto_btn))
        dform.addRow(self.weak_chk)
        dform.addRow("", self.weak_spin)
        dform.addRow(self.ref_chk)
        dform.addRow("", self.ref_margin)
        dform.addRow("Fenêtre :", self.win_spin)
        dform.addRow("Occupation sur :", self.occ_combo)
        dform.addRow("TX absent après :", self.absent_spin)
        self.strong_chk = QtWidgets.QCheckBox("Alerte « trop fort » au-dessus de")
        self.strong_chk.setChecked(True)
        self.strong_chk.setToolTip(
            "Un signal très fort (talkie collé à l'antenne, burst, émetteur trop près, intermod) peut saturer les\n"
            "récepteurs et faire décrocher les liaisons : alarme ⚠ TROP FORT dès qu'un signal des bandes balayées\n"
            "dépasse ce niveau (ligne violette sur le spectre). Le tinySA lui-même sature vers −10 dBm.")
        self.strong_spin = LevelSpin()
        self.strong_spin.setRange(-80.0, 10.0)
        self.strong_spin.setValue(-25.0)
        self.strong_spin.setToolTip(self.strong_chk.toolTip())
        for w_ in (self.strong_chk, self.strong_spin):
            (w_.toggled if w_ is self.strong_chk else w_.valueChanged).connect(lambda *_: self._strong_changed())
        dform.addRow(self.strong_chk)
        dform.addRow("", self.strong_spin)
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
        self.band_table = QtWidgets.QTableWidget(0, 6)
        self.band_table.setHorizontalHeaderLabels(["Bande", "Début MHz", "Fin MHz", "Points", "Pas kHz", "tinySA"])
        self.band_table.horizontalHeaderItem(5).setToolTip(
            "Quel tinySA balaye la bande (2ᵉ tinySA activé). Double-clic : Auto → 1 → 2.\n"
            "Auto = répartition équilibrée. Si un appareil décroche, l'autre reprend toutes les bandes.")
        self.band_table.cellDoubleClicked.connect(self.on_band_dbl)
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
        b_cut = QtWidgets.QPushButton("✂ Couper")
        b_cut.setToolTip("Coupe la bande sélectionnée en deux moitiés : avec deux tinySA, chacun en balaye une\n"
                         "(une seule grosse bande ne se partage pas).")
        b_cut.clicked.connect(lambda *_: self.cut_band())
        bl.addLayout(self._row(b_add, b_del, b_cut))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItem("➕ Ajouter un préréglage…")
        for p in BAND_PRESETS:
            self.preset_combo.addItem(p[0], p)
        self.preset_combo.activated.connect(self.on_preset)
        bl.addWidget(self.preset_combo)

        lcont = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(lcont)
        lv.setContentsMargins(6, 4, 6, 4)
        self.expert_hint = QtWidgets.QPushButton("🎛 Mode simple : afficher tous les réglages")
        self.expert_hint.setFlat(True)
        self.expert_hint.setToolTip("Le mode expert montre aussi RBW, entrée, LNA, atténuateur, offset, segments,\n"
                                    "fenêtre, seuil sur référence, calibration, relais… (☰ Plus › Mode expert).")
        self.expert_hint.clicked.connect(lambda *_: self.set_expert(not self.expert))
        lv.addWidget(self.expert_hint)
        self.sections = {}
        dev2_box = self._build_dev2_box()
        for key, box, stretch in (("detect", dbox, 0), ("bands", bbox, 1), ("measure", mbox, 0),
                                  ("dev2", dev2_box, 0), ("country", pbox, 0)):
            lv.addWidget(self._section(key, box), stretch)
        lv.addStretch(0)
        self._expert_rows = [(mform, w_) for w_ in (self.rbw_combo, self.zrbw_combo, self.input_combo, self.lna_combo,
                                                   self.att_combo, self.offset_spin, self.seg_combo, self.baud_combo)]
        self._expert_rows += [(dform, w_) for w_ in (self.ref_chk, self.ref_margin, self.win_spin, self.occ_combo,
                                                   self.unk_chk)]
        self._expert_rows += [(self._dev2_form, w_) for w_ in (self.dev2_off, self.calib_btn, self.relay_btn)]
        self._expert_rows += [(pform, plan_btn)]
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
        self.mk_btn = QtWidgets.QPushButton("📍 Repères")
        self.mk_btn.setToolTip("Repères des fréquences sur le spectre : lesquels afficher, noms, style, couleur.\n"
                               "Ctrl+M : tout masquer / réafficher.")
        self.mk_menu = QtWidgets.QMenu(self.mk_btn)
        self.mk_btn.setMenu(self.mk_menu)
        self.mk_menu.aboutToShow.connect(lambda *_: self._build_mk_menu())
        sc_mk = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+M"), self)
        sc_mk.activated.connect(lambda *_: self.toggle_markers())
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
        self._elastic(self.band_lbl)                 # une seule ligne, coupée si besoin : le spectre garde la place
        self.readout = QtWidgets.QLabel("")
        self.readout.setMinimumWidth(210)
        self.readout.setStyleSheet("font-family:Consolas,monospace;")

        self.spec = pg.PlotWidget(axisItems={"left": LevelAxis(orientation="left")})
        pi = self.spec.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau (dBm)")
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
        self.strong_line = pg.InfiniteLine(pos=-25, angle=0, movable=False,
                                           pen=pg.mkPen("#b06cff", width=1.4, style=Qt.PenStyle.DashDotLine))
        pi.addItem(self.strong_line)
        self.proxy = pg.SignalProxy(self.spec.scene().sigMouseMoved, rateLimit=30, slot=self.on_mouse)
        self._ovl_timer = QtCore.QTimer(self)
        self._ovl_timer.setSingleShot(True)
        self._ovl_timer.setInterval(40)
        self._ovl_timer.timeout.connect(self._update_markers)
        self._ovl_timer.timeout.connect(self.update_strip_labels)
        pi.vb.sigXRangeChanged.connect(lambda *a: self._ovl_timer.start())
        pi.vb.sigYRangeChanged.connect(lambda *a: self._ovl_timer.start())   # repères « discrets » collés en haut
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
        cl.addLayout(self._flow(("Vue :", self.view_combo), self.zoom_btn, self.mk_btn, self.hold_chk,
                                self.persist_combo, reset_btn, cap_btn, self.readout))
        self.ref_row = QtWidgets.QWidget()
        rl = self._row("Référence :", ref_btn, self.showref_chk, exp_btn, None)
        rl.setContentsMargins(0, 0, 0, 0)
        self.ref_row.setLayout(rl)
        cl.addWidget(self.ref_row)
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
        self.layer_tree.setMinimumHeight(46)
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
        for b_ in (self.global_btn, lb_sc, lb_gr, lb_rn, lb_dl):      # rétrécissables : le spectre d'abord
            b_.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, b_.sizePolicy().verticalPolicy())
            b_.setMinimumWidth(30)
        lv2.addLayout(self._row(self.global_btn, lb_sc, lb_gr, lb_rn, lb_dl))
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
        # libellés courts (le panneau doit pouvoir rétrécir pour laisser la place au spectre) ; détail en bulle
        for txt, tip, fn, lay in [
                ("＋ Ajouter", "Ajoute une fréquence à surveiller (dans la couche active).", self.add_watch_dialog, r1),
                ("📥 Importer", "Importe une liste de fréquences (EazyRF, WWB, WSM, Excel…). Tu peux aussi glisser\n"
                               "le fichier sur la fenêtre.", self.import_watch, r1),
                ("📋 Coller", "Colle une liste copiée (Excel, mail…) : nom et fréquence par ligne.", self.paste_watch, r1),
                ("📤 Exporter", "Exporte ta liste de fréquences (CSV).", self.export_watch, r2),
                ("🗑 Supprimer", "Supprime la ou les lignes sélectionnées.", self.del_watch, r2),
                ("↔ Bandes", "Bandes depuis la liste : remplace les bandes par des zones qui couvrent juste tes\n"
                             "fréquences (scan plus rapide).", self.bands_from_list, r2)]:
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, b.sizePolicy().verticalPolicy())
            b.setMinimumWidth(40)
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
        # le nom ne s'étire pas (sinon Signal / Statut sortent de la vue quand le panneau est étroit) : la dernière
        # colonne (attribution) prend la place restante
        self.watch_table.horizontalHeader().setSectionResizeMode(C_NAME, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.watch_table.setColumnWidth(C_NAME, 100)
        self.watch_table.horizontalHeader().setStretchLastSection(True)
        # ce qu'on lit d'abord : Nom, MHz, Signal, Statut ; colonnes déplaçables à la souris (ordre mémorisé)
        hh_ = self.watch_table.horizontalHeader()
        hh_.setSectionsMovable(True)
        hh_.moveSection(hh_.visualIndex(C_SIG), 2)
        hh_.moveSection(hh_.visualIndex(C_STAT), 3)
        for c, w in ((C_FREQ, 64), (C_LVL, 56), (C_MAX, 56), (C_THR, 56), (C_SIG, 78), (C_STAT, 84),
                     (C_OCC, 48), (C_LAYER, 120), (C_BAND, 190)):
            self.watch_table.setColumnWidth(c, w)
        self.watch_table.verticalHeader().setVisible(False)
        self.watch_table.setWordWrap(False)
        self.watch_table.setMinimumHeight(84)
        self.watch_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.watch_table.itemChanged.connect(self.on_watch_edit)
        self.watch_table.cellDoubleClicked.connect(self.on_watch_dbl)
        self.watch_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.watch_table.customContextMenuRequested.connect(self.watch_menu)
        self.watch_table.setItemDelegateForColumn(C_NAME, NameDelegate(self))
        sc_fill = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self.watch_table)
        sc_fill.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_fill.activated.connect(lambda *_: self.fill_down_names())
        # statut de la sélection au clavier : Ctrl+1…9 = statut n° 1…9, Ctrl+0 = aucun, Ctrl+E = « doit émettre »
        for key, which in [(f"Ctrl+{n}", n - 1) for n in range(1, 10)] + [("Ctrl+0", None), ("Ctrl+E", "on")]:
            sc_ = QtGui.QShortcut(QtGui.QKeySequence(key), self.watch_table)
            sc_.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc_.activated.connect(lambda *_, w_=which: self.quick_status(w_))
        fl.addWidget(self.watch_table, 1)
        tip = QtWidgets.QLabel("Double-clic sur « Statut » : change le statut · sur Niveau / Signal : zoom live · "
                               "sur « Seuil » : seuil propre à la fréquence.\n"
                               "Clic droit : menu complet. Tu peux aussi glisser un CSV sur la fenêtre.\n"
                               "Nom : l'auto-complétion propose MIC, HF 5, IEM… · Ctrl+D numérote vers le bas "
                               "(HF 1, HF 2…).\n"
                               "Statut de la sélection au clavier : Ctrl+E = En service (doit émettre), Ctrl+1…9 = "
                               "statut n° 1…9 (ordre du menu Statut), Ctrl+0 = aucun. Sélection rapide : Maj+clic, "
                               "Ctrl+clic, Ctrl+A.\n"
                               "Un statut « Doit rester libre » déclenche ⚠ CONFLIT si un signal apparaît.")
        tip.setToolTip(tip.text())
        tip.setText("ⓘ Double-clic Statut / Niveau / Seuil · clic droit = menu · Ctrl+E = en service · Ctrl+D numérote "
                    "(survole pour l'aide)")
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
        self.autolog_chk = QtWidgets.QCheckBox("Journal auto (CSV / jour)")
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
        self.rec_chk = QtWidgets.QCheckBox("💾 Enregistrer les balayages")
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

        # pas de zone centrale fixe : le spectre est un panneau comme les autres (détachable, déplaçable sur
        # l'autre écran, ré-accrochable). Qt exige un widget central : une case vide de taille nulle.
        root = QtWidgets.QWidget()
        root.setMaximumHeight(0)          # seulement la hauteur : la largeur doit suivre la colonne du milieu
        root.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCentralWidget(root)
        self.setDockNestingEnabled(True)
        # colonnes Réglages / Fréquences sur toute la hauteur ; spectre, waterfall, alarmes au milieu
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        left.setMinimumWidth(230)
        self._build_docks(left, ftab, ltab, self.wf_box, center)
        self._install_tips()
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
        self.ver_lbl = QtWidgets.QLabel(f" v{APP_VER} ")
        self.ver_lbl.setToolTip(f"{APP_NAME} version {APP_VER} (☰ Plus › À propos pour les détails).")
        self.statusBar().addPermanentWidget(self.ver_lbl)

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

    def ndev(self):
        return 2 if self.dev2["on"] else 1

    def band_devices(self):
        """{id bande: n° du tinySA qui la balaye} (tout sur le 1er quand il n'y en a qu'un)."""
        bs = [b for b in self.scan_bands() if b["enabled"]]
        if self.ndev() == 1:
            return {b["id"]: 0 for b in bs}
        return assign_bands([dict(id=b["id"], pts=self._npts(b), dev=b.get("dev")) for b in bs],
                            2, self.dev_live)

    def get_cfg(self, dev=0):
        with self.lock:
            c = self._cfg
            cal = self._calib
            if cal is not None and dev < 2:
                b = cal["band"]
                return dict(bands=[dict(id=CALIB_IDS[dev], name="Calibration", start_hz=b["start"] * 1e6,
                                        stop_hz=b["stop"] * 1e6, n=self._npts(b), enabled=True)],
                            rbw=c["rbw"], input=c["input"], lna=c["lna"], att=c["att"],
                            offset=c["offset"] + (float(self.dev2.get("offset", 0.0)) if dev == 1 else 0.0),
                            seg=c["seg"], demo_freqs=[w["freq"] for w in self.watch], ver=self._ver)
            if self._zoom:
                a, b = self._zoom
                n = max(2, int(c["points"]))
                step_khz = (b - a) * 1000.0 / (n - 1)
                bands = [dict(id=ZOOM_ID, name="Zoom", start_hz=a * 1e6, stop_hz=b * 1e6, n=n, enabled=True)]
                rbw = c["zrbw"] if c["zrbw"] is not None else auto_rbw(step_khz)
                zdev = 0 if (self.ndev() == 1 or self.dev_live[0] or not self.dev_live[1]) else 1
                if dev != zdev:
                    # le zoom live est fait par un seul tinySA ; l'autre continue de surveiller toutes les bandes
                    bands = [dict(id=b["id"], name=b["name"], start_hz=b["start"] * 1e6, stop_hz=b["stop"] * 1e6,
                                  n=self._npts(b), enabled=True) for b in self.scan_bands() if b["enabled"]]
                    rbw = c["rbw"]
            else:
                asg = self.band_devices()
                bands = [dict(id=b["id"], name=b["name"], start_hz=b["start"] * 1e6, stop_hz=b["stop"] * 1e6,
                              n=self._npts(b), enabled=b["enabled"]) for b in self.scan_bands()
                         if asg.get(b["id"], 0) == dev]
                rbw = c["rbw"]
            freqs = [w["freq"] for w in self.watch if not w.get("bw")]
            blocks = [(w["freq"], w["bw"]) for w in self.watch if w.get("bw") and self.is_keep_on(w["status"])]
            off = c["offset"] + (float(self.dev2.get("offset", 0.0)) if dev == 1 else 0.0)
            return dict(bands=bands, rbw=rbw, input=c["input"], lna=c["lna"], att=c["att"],
                        offset=off, seg=c["seg"], demo_freqs=freqs, demo_blocks=blocks, ver=self._ver)

    def _load_config(self):
        data = {}
        for i, path in enumerate((CFG_PATH, CFG_BAK)):     # config abîmée : on reprend la copie de secours
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("config illisible")
                if i:
                    QtCore.QTimer.singleShot(500, lambda: self.set_status(
                        "⚠ Config abîmée : la copie de secours (sauvegarde automatique) a été rechargée."))
                break
            except FileNotFoundError:
                data = {}
            except Exception:  # noqa: BLE001
                data = {}
        self._apply_config(data, startup=True)
        g = data.get("geometry")
        if g:
            try:
                self.restoreGeometry(QtCore.QByteArray.fromBase64(g.encode()))
            except Exception:
                pass
        st = data.get("docks")
        if int(data.get("layout_ver", 0) or 0) < LAYOUT_VER:
            st = None                    # ancienne disposition (spectre minuscule…) : on repart de la base
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
                dv = b.get("dev")
                self._append_band(b["name"], float(b["start"]), float(b["stop"]),
                                  float(b["step"]), bool(b.get("enabled", True)),
                                  dv if dv in (0, 1) else None)
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
                if w.get("hide_mk"):
                    self.watch[-1]["hide_mk"] = True
                if w.get("bw"):
                    self.watch[-1]["bw"] = max(0.0, float(w["bw"]))
                if w.get("hide_wall"):
                    self.watch[-1]["hide_wall"] = True
                if rx_profile(w.get("rx")) is not None:
                    self.watch[-1]["rx"] = w["rx"]          # profil d'appareil (🧮 Vérifier le plan)
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
                           (self.occ_combo, "occ_minutes"), (self.country_combo, "country"),
                           (self.baud_combo, "baud")]:
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
        self.set_unit(str(data.get("unit", "dbm")))
        wc = data.get("watch_cols")
        if isinstance(wc, str) and wc:
            try:
                self.watch_table.horizontalHeader().restoreState(QtCore.QByteArray.fromBase64(wc.encode()))
            except Exception:  # noqa: BLE001
                pass
        lb = data.get("labels")
        if isinstance(lb, dict):
            self.sig_labels = {k: str(v)[:30] for k, v in lb.items() if k in SIGNAL_DEFAULTS and str(v).strip()}
        if "sig_colors" in data:
            self.sig_colors = clean_colors(data.get("sig_colors"))
        sd = data.get("sdr")
        if isinstance(sd, dict):
            for k_, cast in (("dir", str), ("lna", int), ("vga", int), ("amp", bool)):
                try:
                    if k_ in sd:
                        self.sdr_cfg[k_] = cast(sd[k_])
                except (TypeError, ValueError):
                    pass
        if data.get("port"):
            self._want_port = str(data["port"])
            ix = self.port_combo.findData(self._want_port)
            if ix >= 0:
                self.port_combo.setCurrentIndex(ix)
        po = data.get("plan_opts")
        if isinstance(po, dict):
            if rx_profile(po.get("prof")) is not None:
                self.plan_opts["prof"] = po["prof"]
            for k_ in ("sep", "filt", "step"):
                try:
                    self.plan_opts[k_] = float(po[k_]) if k_ == "filt" else int(po[k_])
                except (KeyError, TypeError, ValueError):
                    pass
        self.strong_chk.setChecked(bool(data.get("strong_on", True)))
        try:
            self.strong_spin.setValue(float(data.get("strong_thr", -25.0)))
        except (TypeError, ValueError):
            pass
        self._strong_changed()
        self.set_expert(bool(data.get("expert", False)))
        ix = self.wall.size_combo.findData(data.get("wall_size", "auto"))
        self.wall.size_combo.setCurrentIndex(max(0, ix))
        so = data.get("sections")
        if isinstance(so, dict):
            for k_, v_ in so.items():
                self.open_section(k_, bool(v_))
        mk, base = data.get("markers"), mk_default()
        if isinstance(mk, dict):
            ok_states = {k for k, _ in MK_STATES}
            for k in ("on", "alarms", "unk"):
                base[k] = bool(mk.get(k, base[k]))
            if mk.get("style") in ("full", "top"):
                base["style"] = mk["style"]
            if isinstance(mk.get("states"), list):
                base["states"] = [x for x in mk["states"] if x in ok_states]
            for k in ("hide_layers", "hide_status"):
                if isinstance(mk.get(k), list):
                    base[k] = [str(x) for x in mk[k]]
        self.mk = base
        self._sync_mk_menu()
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
        d2 = data.get("dev2")
        if isinstance(d2, dict):
            self.dev2_chk.setChecked(bool(d2.get("on")))
            self.dev2_addr.setEditText(str(d2.get("addr", "")))
            try:
                self.dev2_off.setValue(float(d2.get("offset", 0.0)))
            except (TypeError, ValueError):
                pass
            self._read_dev2()
        for key, d in (("notify", self.notify_cfg), ("web", self.web_cfg)):
            v = data.get(key)
            if isinstance(v, dict):
                d.update({k: v[k] for k in d if k in v and isinstance(v[k], type(d[k]))})
        self.web_cfg["views"] = web_views_norm(self.web_cfg.get("views"))
        QtCore.QTimer.singleShot(0, self.apply_web)
        dn = data.get("dev_names")
        if isinstance(dn, list) and len(dn) == 2:
            self.dev1_name.setText("" if dn[0] == "tinySA 1" else str(dn[0]))
            self.dev2_name.setText("" if dn[1] == "tinySA 2" else str(dn[1]))
            self._dev_names_changed()
        if startup:
            self.demo_chk.setChecked(data.get("demo", False))
            sm = data.get("show_meta")
            if isinstance(sm, dict):
                self.show_meta = {k: str(sm.get(k, "") or "") for k in SHOW_META}
            self.show_path = str(data.get("show_path") or "")
            rs = data.get("recent_shows")
            self.recent_shows = [str(x) for x in rs if isinstance(x, str)][:8] if isinstance(rs, list) else []
            self.update_title()
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
                        scene=w["scene"], group=w["group"], **({"hide_mk": True} if w.get("hide_mk") else {}),
                        **({"bw": w["bw"]} if w.get("bw") else {}),
                        **({"hide_wall": True} if w.get("hide_wall") else {}),
                        **({"rx": w["rx"]} if w.get("rx") else {}))
                   for w in self.watch],
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
            baud=self.baud_combo.currentData(),
            persist=self.persist_combo.currentData(),
            thr=self.thr_spin.value(), weak_thr=self.weak_spin.value(), weak_on=self.weak_chk.isChecked(),
            win=self.win_spin.value(), alert=self.alert_chk.isChecked(), unk=self.unk_chk.isChecked(),
            absent_s=self.absent_spin.value(),
            names=self.names_chk.isChecked(), hold=self.hold_chk.isChecked(), markers=dict(self.mk),
            country=self.country_combo.currentData(), show_alloc=self.alloc_chk.isChecked(),
            show_tv=self.tv_chk.isChecked(), plan_custom=self.plan_custom,
            occ_minutes=self.occ_combo.currentData(), ref_rel=self.ref_chk.isChecked(),
            ref_margin=self.ref_margin.value(), show_ref=self.showref_chk.isChecked(),
            log_auto=self.autolog_chk.isChecked(), log_dir=str(self.log_dir), export=self.export_prefs,
            dev2=dict(self.dev2), dev_names=list(self.dev_names), web={k: v for k, v in self.web_cfg.items() if k not in ("pin", "password")},
            expert=self.expert, sections=dict(self.sections_open), wall_size=self.wall.size_combo.currentData(),
            strong_on=self.strong_chk.isChecked(), strong_thr=self.strong_spin.value(), labels=dict(self.sig_labels),
            sig_colors=dict(self.sig_colors), plan_opts=dict(self.plan_opts), sdr=dict(self.sdr_cfg),
            port=self.port_combo.currentData() or "",
            unit=self.unit, watch_cols=bytes(self.watch_table.horizontalHeader().saveState().toBase64()).decode())
        if full:
            data["demo"] = self.demo_chk.isChecked()
            data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
            data["docks"] = bytes(self.saveState().toBase64()).decode()
            data["layout_ver"] = LAYOUT_VER
            data["vocab"] = self.vocab_user
            data["notify"] = dict(self.notify_cfg)     # pas dans les profils partagés (jeton Telegram)
            data["web"]["pin"] = self.web_cfg.get("pin", "")          # code PIN : idem
            data["web"]["password"] = self.web_cfg.get("password", "")
            data["show_meta"] = dict(self.show_meta)
            data["show_path"] = self.show_path
            data["recent_shows"] = list(self.recent_shows)
        return data

    def _save_config(self):
        """Écriture sûre : fichier temporaire puis remplacement (une coupure de courant ne laisse jamais une
        config à moitié écrite), l'ancienne version gardée en .bak."""
        try:
            CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = CFG_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._collect_config(True), ensure_ascii=False, indent=1), encoding="utf-8")
            if CFG_PATH.exists():
                try:
                    os.replace(CFG_PATH, CFG_BAK)
                except OSError:
                    pass
            os.replace(tmp, CFG_PATH)
            return True
        except Exception:  # noqa: BLE001
            return False

    # --------------------------------------------------------------- shows
    def _build_show_menu(self):
        m = self.show_menu
        m.clear()
        cur = self.show_meta.get("name") or ""
        m.addAction("🆕 Nouveau show…").triggered.connect(lambda *_: self.new_show())
        m.addAction("📂 Ouvrir un show…").triggered.connect(lambda *_: self.open_show_dialog())
        m.addAction(f"💾 Enregistrer « {cur} »  (Ctrl+S)" if cur else "💾 Enregistrer le show…  (Ctrl+S)"
                    ).triggered.connect(lambda *_: self.save_show())
        m.addAction("💾 Enregistrer sous… (nouvelle édition, autre scène)").triggered.connect(
            lambda *_: self.save_show(as_new=True))
        m.addAction("📝 Infos du show (nom, lieu, dates, notes)…").triggered.connect(lambda *_: self.edit_show_info())
        rec = [p for p in self.recent_shows if Path(p).exists()]
        if rec:
            sub = m.addMenu("Récents")
            for pth in rec:
                sub.addAction(Path(pth).stem).triggered.connect(lambda *_, x=pth: self.open_show(x))
        m.addSeparator()
        m.addAction("Ouvrir le dossier des shows").triggered.connect(lambda *_: self.open_show_dir())

    def update_title(self):
        nm = self.show_meta.get("name") or ""
        yr = (self.show_meta.get("date_from") or "")[:4]
        show = f" — {nm}" + (f" {yr}" if yr and yr not in nm else "") if nm else ""
        self.setWindowTitle(f"{APP_NAME} {APP_VER}{show}" + (f" — {self.scope_text()}" if self.scope else ""))

    def edit_show_info(self, title="Infos du show"):
        dlg = ShowInfoDialog(self, self.show_meta, title)
        if not dlg.exec():
            return False
        self.show_meta = dlg.values()
        self.update_title()
        return True

    def save_show(self, as_new=False):
        if not self.show_meta.get("name"):
            if not self.edit_show_info("Enregistrer le show"):
                return
            if not self.show_meta.get("name"):
                self.set_status("Donne un nom au show pour l'enregistrer.")
                return
        path = self.show_path
        if as_new or not path:
            try:
                SHOW_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Enregistrer le show", str(SHOW_DIR / show_filename(self.show_meta)), f"Show (*{SHOW_EXT})")
            if not path:
                return
            if not path.endswith(SHOW_EXT):
                path += SHOW_EXT
        self.save_show_to(path)

    def save_show_to(self, path):
        try:
            doc = show_doc(self._collect_config(False), self.show_meta, self.ref_curves, APP_VER)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(str(path) + ".tmp")                # écriture sûre : jamais de show à moitié écrit
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, path)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Impossible d'enregistrer le show :\n{e}")
            return False
        self.show_path = str(path)
        self._add_recent(self.show_path)
        self.update_title()
        self.set_status(f"🎪 Show enregistré : {path}")
        return True

    def _add_recent(self, path):
        self.recent_shows = [str(path)] + [p for p in self.recent_shows if p != str(path)]
        del self.recent_shows[8:]

    def open_show_dialog(self):
        dlg = ShowOpenDialog(self, [(SHOW_DIR, "*" + SHOW_EXT), (PROFILE_DIR, "*.json")])
        if dlg.exec() and dlg.path:
            self.open_show(dlg.path)

    def open_show(self, path, ask=True):
        try:
            doc = read_show(Path(path).read_text(encoding="utf-8"), Path(path).stem)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Show illisible :\n{e}")
            return False
        sm = show_summary(doc)
        if ask:
            r = QtWidgets.QMessageBox.question(
                self, APP_NAME, f"Ouvrir « {sm['name']} » ({sm['dates'] or 'sans date'}, {sm['n_freq']} fréquences) ?\n\n"
                                "Remplace les fréquences, scènes, bandes, statuts et seuils actuels.\n"
                                "Tes préférences (couleurs, fenêtres, alertes, 2ᵉ tinySA) ne bougent pas.")
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return False
        self._apply_config(show_apply(self._collect_config(True), doc))
        if doc["ref"]:
            self._set_ref([(np.array(f), np.array(l)) for f, l in doc["ref"]])
            self._save_ref_file(REF_PATH)
        self.show_meta = dict(doc["meta"])
        legacy = str(path).endswith(".json")
        self.show_path = "" if legacy else str(path)    # un ancien profil sera enregistré en .tsashow
        if not legacy:
            self._add_recent(self.show_path)
        self.update_title()
        self.set_status(f"🎪 Show « {sm['name']} » ouvert : {sm['n_freq']} fréquences"
                        + (", courbe de référence du lieu chargée" if doc["ref"] else "") + ".")
        return True

    def new_show(self):
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, "Nouveau show : la liste de fréquences, les scènes et les groupes sont vidés.\n"
                            "Les bandes, statuts et seuils sont gardés comme point de départ.\n"
                            "Pense à enregistrer le show en cours avant (Ctrl+S). Continuer ?")
        if r != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        data = self._collect_config(True)
        data.update(watch=[], scenes=[], scope=None, focus=False)
        self._apply_config(data)
        self.show_meta = {k: "" for k in SHOW_META}
        self.show_path = ""
        self.update_title()
        self.edit_show_info("Nouveau show")

    def open_show_dir(self):
        try:
            SHOW_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(SHOW_DIR)))

    # --------------------------------------------------------------- profils (ancien format)
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
        for k, sp in SDR_KINDS.items():                 # V8 : SDR par leur outil de balayage
            self.port_combo.addItem(f"📡 {sp['name']} ({sp['tool']})", k)
        ix = self.port_combo.findData(getattr(self, "_want_port", None))
        if ix >= 0:
            self.port_combo.setCurrentIndex(ix)

    # ----------------------------------------------------------- run / stop
    def is_running(self):
        return any(w.isRunning() for w in self.workers)

    def toggle_run(self):
        if self.is_running():
            for w in self.workers:
                w.requestInterruption()
            self.start_btn.setEnabled(False)
            self.set_status("Arrêt en cours…")
            QtCore.QTimer.singleShot(STOP_FORCE_MS, self._force_stop)
            return
        demo = self.demo_chk.isChecked()
        port = self.port_combo.currentData()
        if not demo and not port:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Aucun appareil sélectionné.\n"
                                          "Branche le tinySA (et ferme tinySA-App), choisis un SDR (📡) "
                                          "ou active le mode démo.")
            return
        if not any(b["enabled"] for b in self.bands):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Coche au moins une bande à balayer.")
            return
        self._read_dev2()
        targets = [(port, "")]
        if self.dev2["on"]:
            kind, url = parse_device_addr(self.dev2["addr"])
            if not demo and kind is None:
                QtWidgets.QMessageBox.warning(self, APP_NAME, "Adresse du 2ᵉ tinySA illisible.\nExemples : COM4 "
                                              "(USB) · 192.168.1.20:5025 (réseau, relais lancé sur l'autre PC).")
                return
            if not demo and url == port:
                QtWidgets.QMessageBox.warning(self, APP_NAME, "Les deux tinySA ont le même port.")
                return
            targets = [(port, self.dev_name(0)), (url, self.dev_name(1))]
        self.dev_live = [True, True]
        self.dev_cycle = {}
        self.band_src = {}
        self.workers = []
        for i, (addr, label) in enumerate(targets):
            w = ScanWorker(addr, demo, (lambda d=i: self.get_cfg(d)), self.get_ver, label)
            w.retry_first = i > 0                 # le 2ᵉ (souvent en réseau) peut arriver après : on l'attend
            w.baud = int(self.baud_combo.currentData() or 115200)
            w.sdr_dir = self.sdr_cfg.get("dir", "")
            w.get_sdr = lambda: dict(self.sdr_cfg)
            w.sweep.connect(lambda bid, f, l, d=i: self.band_src.__setitem__(bid, d))
            w.sweep.connect(self.on_sweep)
            w.partial.connect(self.on_partial)
            w.cycle.connect(lambda dt, nb, d=i: self.on_cycle(dt, nb, d))
            w.status.connect(self.set_status)
            w.info.connect(lambda txt, d=i: self.on_info(txt, d))
            w.error.connect(lambda msg, d=i: self.on_error(msg, d))
            w.link.connect(lambda ok, d=i: self.on_link(d, ok))
            w.finished.connect(self.on_finished)
            self.workers.append(w)
        self.worker = self.workers[0]
        self._bump()
        for w in self.workers:
            w.start()
        self._style_start(True)
        self.port_combo.setEnabled(False)
        self.demo_chk.setEnabled(False)
        for wd in (self.dev2_chk, self.dev2_addr):
            wd.setEnabled(False)
        self.update_dev2_label()

    def _force_stop(self):
        """Le tinySA ne rend pas la main : on ferme les ports pour débloquer l'arrêt."""
        stuck = [w for w in self.workers if w.isRunning()]
        if not stuck:
            return
        for w in stuck:
            w.force_close()
        self.set_status("Arrêt forcé : le tinySA ne répondait plus (port fermé). Rebranche-le si le prochain "
                        "démarrage échoue.")
        QtCore.QTimer.singleShot(3000, lambda: self.on_finished() if not self.is_running() else None)

    def on_info(self, txt, dev=0):
        if dev == 0:
            self.info_lbl.setText(f"  {txt}")
            self.seg_known = 450 if "tinysa4" in txt.lower() else 290
            self.update_estimate()
        else:
            self.dev2_info = txt
            self.update_dev2_label()

    def dump_diag(self, reason="", quiet=False):
        """Écrit un fichier de diagnostic (pour le support) : versions, réglages, bandes, derniers échanges avec
        le(s) tinySA. -> chemin, ou None."""
        now = time.time()
        if quiet and now - getattr(self, "_diag_t", 0.0) < 60:          # automatique : au plus une fois par minute
            return None
        self._diag_t = now
        c = self._cfg
        out = [f"{APP_NAME} {APP_VER} — diagnostic du {datetime.now():%d/%m/%Y %H:%M:%S}",
               f"Raison : {reason or 'demandé'}", f"Python {sys.version.split()[0]} · Qt {QtCore.qVersion()} · {sys.platform}",
               f"tinySA : {self.info_lbl.text().strip() or '—'} · port {self.port_combo.currentData() or '—'}"
               f" · {self.baud_combo.currentData()} bauds · démo {self.demo_chk.isChecked()}",
               f"Réglages : points {c['points']} · RBW {c['rbw'] or 'auto'} · RBW zoom {c['zrbw'] or 'auto'} · "
               f"entrée {c['input']} · LNA {c['lna']} · atténuateur {c['att']} · segment {c['seg'] or 'auto'} · "
               f"offset {c['offset']}", "", "Bandes :"]
        for b in self.bands:
            out.append(f"  [{'x' if b['enabled'] else ' '}] {b['name']} : {b['start']:g}–{b['stop']:g} MHz, "
                       f"pas {b['step']:g} kHz, {self._npts(b)} points")
        for k, w in enumerate(list(self.workers)):
            tr = getattr(w, "trace", None)
            out += ["", f"Échanges avec {self.dev_name(k)} (plus récents en bas) :"] + [str(x) for x in list(tr or [])]
        try:
            d = self.log_dir / "diagnostic"
            d.mkdir(parents=True, exist_ok=True)
            p_ = d / f"diagnostic_tinysa_{datetime.now():%Y%m%d_%H%M%S}.txt"
            p_.write_text("\n".join(out) + "\n", encoding="utf-8")
            return p_
        except Exception as e:  # noqa: BLE001
            if not quiet:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Diagnostic impossible à écrire :\n{e}")
            return None

    def open_diag(self):
        p_ = self.dump_diag("demandé depuis le menu")
        if p_ is not None:
            QtWidgets.QMessageBox.information(
                self, APP_NAME, f"Fichier de diagnostic écrit :\n{p_}\n\nEnvoie-le avec la description du problème "
                                "(et le crash.log s'il y en a un). Un fichier est aussi écrit tout seul quand un tinySA "
                                "décroche.")
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(p_.parent)))

    def on_error(self, msg, dev=0):
        self._diag_pending = f"erreur : {msg}"          # écrit par _alarm_tick (crash 7.6.2 avec un singleShot)
        if dev == 0:                              # le 1er tinySA ne répond pas : on arrête tout
            for w in self.workers:
                w.requestInterruption()
        QtWidgets.QMessageBox.critical(self, APP_NAME, f"Erreur de balayage :\n{msg}")

    def on_link(self, dev, ok):
        """Un tinySA décroche (câble, réseau, relais) ou revient : alarme + répartition des bandes."""
        with self.lock:
            self.dev_live[dev] = bool(ok)
        if not ok and self._calib is not None:
            self._calib_end("⚠ Calibration annulée : un tinySA a décroché.")
        self._bump()
        now = time.time()
        key = ("APPAREIL", -(dev + 1))
        name = self.dev_name(dev)
        w = dict(name=name, freq=0.0)
        if ok:
            if self.alarms.clear(key, now) is not None and self.notify_cfg["mode"] != "off":
                self.send_notify(f"✔ {name} de nouveau en ligne", "Les bandes sont réparties à nouveau.", 1)
            self.log_event(w, 0.0, "APPAREIL RETROUVÉ")
            self.set_status(f"✔ {name} de nouveau en ligne : bandes réparties à nouveau.")
        else:
            self._diag_pending = f"liaison perdue avec {self.dev_name(dev)}"     # écrit par _alarm_tick
            other = f"{self.dev_name(1 - dev)} reprend ses bandes" if self.ndev() > 1 and any(self.dev_live) else \
                "plus aucune mesure"
            if self.alarms.raise_(key, "APPAREIL", name, 0.0, 2, now, layer="",
                                  info=f"liaison perdue — {other}"):
                self._alarm_sound(2)
            self.log_event(w, 0.0, "APPAREIL PERDU")
            self.set_status(f"⚠ {name} : liaison perdue — {other}. Nouvel essai toutes les {ScanWorker.RETRY_S} s.")
        self.update_dev2_label()
        self.refresh_alarms()
        self.update_band_dev_col()

    def on_finished(self):
        if self.is_running():
            return                                # l'autre tinySA tourne encore
        self._style_start(False)
        self.start_btn.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.demo_chk.setEnabled(True)
        for wd in (self.dev2_chk, self.dev2_addr):
            wd.setEnabled(True)
        self.partial_data.clear()
        if self._calib is not None:
            self._calib_end("Calibration annulée (balayage arrêté).", popup=False)
        for d in (0, 1):
            self.alarms.clear(("APPAREIL", -(d + 1)), time.time())
        self.dev_live = [True, True]
        self.update_dev2_label()
        self.set_status("Arrêté.")

    # ------------------------------------------------------------ 2ᵉ tinySA
    def _build_dev2_box(self):
        box = QtWidgets.QGroupBox("2ᵉ tinySA (USB ou réseau) · noms")
        self.dev2_box = box
        f = QtWidgets.QFormLayout(box)
        self.dev2_chk = QtWidgets.QCheckBox("Utiliser un 2ᵉ tinySA")
        self.dev2_chk.setToolTip("Deux tinySA balayent en parallèle : chaque bande est faite par l'un ou l'autre\n"
                                 "(colonne « tinySA » des bandes). Cycle deux fois plus court, et si l'un décroche,\n"
                                 "l'autre reprend toutes les bandes (alarme ⚠ APPAREIL).")
        self.dev2_chk.toggled.connect(lambda *_: self._dev2_changed())
        self.dev2_addr = QtWidgets.QComboBox()
        self.dev2_addr.setEditable(True)
        self.dev2_addr.setToolTip("USB : choisis le port (COM4…).\nRéseau : adresse du PC où le tinySA est branché, "
                                  "ex. 192.168.1.20:5025\n(sur ce PC-là : 🔧 Outils › 📡 Relais réseau, ou "
                                  "TinySA-Monitor.exe --relais).")
        self.dev2_addr.lineEdit().setPlaceholderText("COM4  ou  192.168.1.20:5025")
        self.dev2_addr.currentTextChanged.connect(lambda *_: self._dev2_changed())
        self.dev2_off = QtWidgets.QDoubleSpinBox()
        self.dev2_off.setRange(-40.0, 40.0)
        self.dev2_off.setDecimals(1)
        self.dev2_off.setSuffix(" dB")
        self.dev2_off.setToolTip("Correction ajoutée aux mesures du 2ᵉ tinySA (en plus de l'offset général),\n"
                                 "pour aligner deux appareils qui ne lisent pas tout à fait pareil.")
        self.dev2_off.valueChanged.connect(lambda *_: self._dev2_changed())
        self.dev2_lbl = QtWidgets.QLabel("")
        self.dev2_lbl.setWordWrap(True)
        relay_btn = QtWidgets.QPushButton("📡 Relais réseau (sur le PC du 2ᵉ tinySA)…")
        relay_btn.setToolTip("Partage un tinySA branché sur CE PC pour qu'un autre PC l'utilise par le réseau.")
        relay_btn.clicked.connect(lambda *_: self.open_relay())
        self.dev1_name, self.dev2_name = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        for e, n in ((self.dev1_name, 1), (self.dev2_name, 2)):
            e.setPlaceholderText(f"tinySA {n}")
            e.setToolTip("Nom de position (Plateau, FOH, Scène B…) : affiché dans les alarmes, le journal\n"
                         "(« vu par … ») et les messages. Utile pour savoir quelle antenne a vu le signal.")
            e.textChanged.connect(lambda *_: self._dev_names_changed())
        f.addRow("Nom du 1er :", self.dev1_name)
        f.addRow(self.dev2_chk)
        f.addRow("Nom du 2ᵉ :", self.dev2_name)
        f.addRow("Adresse :", self.dev2_addr)
        f.addRow("Offset :", self.dev2_off)
        self.calib_btn = QtWidgets.QPushButton("⚖ Calibrer le 2ᵉ sur le 1er…")
        self.calib_btn.setToolTip("Les deux tinySA doivent recevoir le MÊME signal (même antenne via un splitter, ou\n"
                                  "antennes côte à côte). Pendant ~20 s ils balayent la même bande, puis l'offset du\n"
                                  "2ᵉ est réglé pour qu'il lise comme le 1er. La surveillance reprend ensuite.")
        self.calib_btn.clicked.connect(lambda *_: self.start_calib())
        f.addRow(self.dev2_lbl)
        f.addRow(self.calib_btn)
        f.addRow(relay_btn)
        self._dev2_form, self.relay_btn = f, relay_btn
        self.dev2_info = ""
        self._dev2_ports()
        return box

    def _dev2_ports(self):
        cur = self.dev2_addr.currentText()
        self.dev2_addr.blockSignals(True)
        self.dev2_addr.clear()
        for p in serial.tools.list_ports.comports():
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            self.dev2_addr.addItem(f"{p.device}{tag}", p.device)
        for k in SDR_KINDS:
            self.dev2_addr.addItem(k, k)                 # V8 : « hackrf », « rtlsdr » (ou « hackrf:n° de série »)
        self.dev2_addr.setEditText(cur)
        self.dev2_addr.blockSignals(False)

    def _read_dev2(self):
        txt = self.dev2_addr.currentText().replace("✔ tinySA", "").strip()   # « COM4  ✔ tinySA » -> « COM4 »
        self.dev2.update(on=self.dev2_chk.isChecked(), addr=txt, offset=float(self.dev2_off.value()))

    def _dev2_changed(self):
        self._read_dev2()
        self._bump()
        self.update_band_dev_col()
        self.update_dev2_label()
        self.update_estimate()

    def update_dev2_label(self):
        if not hasattr(self, "dev2_lbl"):
            return
        d = self.dev2
        if not d["on"]:
            self.dev2_lbl.setText("Désactivé : un seul tinySA balaye tout.")
            return
        kind, url = parse_device_addr(d["addr"])
        where = {"serial": f"USB {d['addr']}", "net": f"réseau {url.split('://', 1)[-1]}"}.get(
            kind, "⚠ adresse à saisir (COM4 ou 192.168.1.20:5025)")
        if self.demo_chk.isChecked():
            where = "démo"
        run = self.is_running()
        st = ("✔ en ligne" if self.dev_live[1] else "⚠ liaison perdue (nouvel essai…)") if run else "prêt"
        cyc = "  ·  ".join(f"{self.dev_name(k)} : {v:.1f} s" for k, v in sorted(self.dev_cycle.items())) if run else ""
        self.dev2_lbl.setText(f"{where} · {st}" + (f" · {self.dev2_info}" if run and self.dev2_info else "")
                              + (f"\nCycle  {cyc}" if cyc else ""))

    def start_calib(self):
        """Les deux tinySA balayent la même bande quelques cycles ; l'offset du 2e est ajusté sur le 1er."""
        if self._calib is not None:
            self._calib_end("Calibration annulée.", popup=False)
            return
        if self.ndev() < 2 or not self.is_running() or not all(self.dev_live):
            QtWidgets.QMessageBox.information(self, APP_NAME, "Calibration : lance d'abord le balayage avec les deux "
                                              "tinySA en ligne (et le même signal sur les deux antennes).")
            return
        if self._zoom is not None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Coupe le zoom live avant de calibrer.")
            return
        bs = [b for b in self.scan_bands() if b["enabled"]]
        if not bs:
            return
        band = max(bs, key=lambda b: sum(1 for w in self.watch if b["start"] <= w["freq"] <= b["stop"]))
        with self.lock:
            self._calib = dict(band=dict(band), t0=time.time(), data={0: [], 1: []})
        self._bump()
        self.calib_btn.setText("⚖ Calibration en cours… (clic = annuler)")
        self.set_status(f"⚖ Calibration : les deux tinySA balayent « {band['name']} » ({CALIB_SWEEPS} fois chacun)…")

    def _calib_add(self, dev, f, l):
        cal = self._calib
        if cal is None:
            return
        cal["data"][dev].append((np.asarray(f), np.asarray(l)))
        if time.time() - cal["t0"] > CALIB_TIMEOUT:
            self._calib_end("⚠ Calibration abandonnée : trop long.")
            return
        if all(len(cal["data"][d]) >= CALIB_SWEEPS for d in (0, 1)):
            def maxhold(lst):
                f0 = lst[0][0]
                ls = [l_ for f_, l_ in lst if f_.shape == f0.shape]
                return f0, np.max(np.vstack(ls), axis=0)
            F1, L1 = maxhold(cal["data"][0])
            F2, L2 = maxhold(cal["data"][1])
            res = calib_offset(F1, L1, F2, L2)
            if res is None:
                self._calib_end("⚠ Calibration impossible : pas assez de points communs.")
                return
            delta, n, kind = res
            new = round(float(self.dev2.get("offset", 0.0)) + delta, 1)
            self.dev2_off.setValue(max(-40.0, min(40.0, new)))
            self._calib_end(f"⚖ Calibration faite : {self.dev_name(1)} {delta:+.1f} dB → offset {new:+.1f} dB "
                            f"(sur {n} points, base : {kind}).")

    def _calib_end(self, msg, popup=True):
        with self.lock:
            self._calib = None
        self._bump()
        self.calib_btn.setText("⚖ Calibrer le 2ᵉ sur le 1er…")
        self.calib_msg = msg
        self.set_status(msg)
        if popup:                                  # la barre d'état est vite réécrite par le balayage
            QtWidgets.QMessageBox.information(self, APP_NAME, msg)

    # ------------------------------------------------- alertes téléphone / page web
    def open_alerts(self):
        dlg = AlertsDialog(self)
        if dlg.exec():
            n, w = dlg.values()
            self.notify_cfg.update(n)
            pw_changed = w.get("password", "") != self.web_cfg.get("password", "")
            self.web_cfg.update(w)
            if pw_changed and self.web is not None:
                self.web.revoke_all()              # nouveau mot de passe : tout le monde se reconnecte
            self.apply_web()

    def send_notify(self, title, body, prio, cfg=None):
        """Met une alerte dans la file d'envoi. -> message d'erreur de réglage, ou "" si c'est parti."""
        c = cfg or self.notify_cfg
        if c["service"] == "telegram":
            if not c["tg_token"] or not c["tg_chat"]:
                return "Telegram : jeton du bot et chat id requis."
            req = telegram_request(c["tg_token"], c["tg_chat"], title, body)
        else:
            if not c["topic"]:
                return "ntfy : choisis un nom de canal."
            req = ntfy_request(c["server"], c["topic"], title, body, prio)
        if self.notifier is None:
            self.notifier = Notifier()
        self.notifier.post(req)
        return ""

    def _notify_new_alarms(self):
        for a in list(self.alarms.active.values()):
            if a["id"] in self._notified:
                continue
            self._notified.add(a["id"])
            if notify_wanted(a["prio"], self.notify_cfg["mode"]):
                title, body = notify_text(a, self.notify_cfg.get("site", ""))
                self.send_notify(title, body, a["prio"])

    def web_json(self):
        rows = []
        for w in self.watch:
            txt, tone, c_ = self.sig_view(w)
            rows.append(dict(w, conflict=(w["state"] == "occ" and self.is_keep_free(w["status"])), sig_txt=txt,
                             tone=tone, color=c_ if tone != "none" else "", level_txt="" if w["level"] is None else self.lvl(w["level"], suffix=True)))
        cyc = f"{self.last_cycle:.1f} s" if self.is_running() else ""
        site = self.notify_cfg.get("site", "")
        st = web_state(rows, self.alarms.listing(), dict(
            title=f"TinySA Monitor — {site}" if site else "TinySA Monitor", time=datetime.now().strftime("%H:%M:%S"),
            running=self.is_running(), cycle=cyc, ack=len(self.web_cfg.get("pin", "").strip()) >= 4, ver=APP_VER,
            thr=round(float(self.thr_spin.value()), 1)))
        return json.dumps(st, ensure_ascii=False).encode("utf-8")

    def web_spec_json(self):
        """Spectre allégé pour les vues Spectre / Waterfall de la page web (une entrée par bande récente)."""
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        names = {b["id"]: b["name"] for b in self.scan_bands()}
        segs, t = [], 0.0
        for k in sorted((k for k in self.latest if k != ZOOM_ID and now - self.latest_t.get(k, 0) <= stale),
                        key=lambda k: float(self.latest[k][0][0]) if len(self.latest[k][0]) else 0.0):
            f, l = self.latest[k]
            segs.append((names.get(k, f"{f[0]:.0f}–{f[-1]:.0f} MHz"), f, l, self.maxhold.get(k)))
            t = max(t, self.latest_t.get(k, 0.0))
        return json.dumps(dict(t=round(t, 3), bands=web_spectrum(segs)), ensure_ascii=False).encode("utf-8")

    def apply_web(self):
        want = self.web_cfg["on"]
        if self.web is not None and (not want or self.web.port != self.web_cfg["port"]):
            self.web.stop()
            self.web = None
        if want and self.web is None:
            self._web_json = self.web_json()
            ws = WebServer(self.web_cfg["port"], lambda: self._web_json, get_pin=lambda: self.web_cfg.get("pin", ""),
                           on_ack=self._web_acks.put, get_spec=lambda: self._web_spec, get_cfg=lambda: self.web_cfg)
            ws.start()
            ws.ready.wait(3)
            if ws.error:
                self.set_status(f"⚠ Page web : {ws.error}")
                return
            self.web = ws
            self.set_status("🌐 Page web active : " + self.web_urls_text())

    def web_urls_text(self):
        if self.web is None:
            return "Page web désactivée."
        ips = local_ips() or ["<adresse de ce PC>"]
        return "Adresse à ouvrir sur le téléphone : " + "  ou  ".join(f"http://{ip}:{self.web.port}" for ip in ips)

    def dev_name(self, d):
        n = (self.dev_names[d] if d < len(self.dev_names) else "").strip()
        return n or f"tinySA {d + 1}"

    def seen_by(self, f):
        """« vu par <nom> » : le tinySA qui a mesuré la fréquence f (MHz) en dernier, si deux appareils ; sinon ""."""
        if self.ndev() < 2:
            return ""
        best = None
        for bid, (F, _L) in self.latest.items():
            if len(F) and F[0] - 0.05 <= f <= F[-1] + 0.05 and bid in self.band_src:
                t = self.latest_t.get(bid, 0)
                if best is None or t > best[0]:
                    best = (t, self.band_src[bid])
        return f"vu par {self.dev_name(best[1])}" if best else ""

    def _dev_names_changed(self):
        self.dev_names = [self.dev1_name.text().strip() or "tinySA 1", self.dev2_name.text().strip() or "tinySA 2"]
        self.update_dev2_label()

    def open_relay(self):
        if getattr(self, "_relay_win", None) is None:
            self._relay_win = RelayWindow()
        self._relay_win.show()
        self._relay_win.raise_()

    def update_band_dev_col(self):
        """Colonne « tinySA » de la table des bandes : choix (Auto / 1 / 2) et appareil réellement utilisé."""
        if not hasattr(self, "band_table"):
            return
        asg = self.band_devices() if self.ndev() > 1 else {}
        self._updating = True
        for r, b in enumerate(self.bands):
            if r >= self.band_table.rowCount():
                break
            d = b.get("dev")
            if self.ndev() == 1:
                txt = "1" if d is None else f"{d + 1}"
            else:
                real = asg.get(b["id"])
                txt = "Auto" if d is None else f"{d + 1}"
                if real is not None and (d is None or real != d):
                    txt += f" → {real + 1}"
            self.band_table.setItem(r, 5, self._item(txt))
        self._updating = False

    def on_band_dbl(self, row, col):
        if col != 5 or row >= len(self.bands):
            return
        b = self.bands[row]
        cyc = [None, 0, 1]
        with self.lock:
            b["dev"] = cyc[(cyc.index(b.get("dev")) + 1) % len(cyc)] if b.get("dev") in cyc else None
        self._bands_changed()

    def cut_band(self):
        r = self.band_table.currentRow()
        if r < 0 or r >= len(self.bands):
            self.set_status("Sélectionne d'abord la bande à couper.")
            return
        b = self.bands[r]
        (a1, m1, st), (m2, z2, _st) = split_band(b["start"], b["stop"], b["step"])
        if m1 - a1 < 1.0:
            self.set_status("Bande trop étroite pour être coupée.")
            return
        with self.lock:
            self.bands.pop(r)
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(b["id"], None)
            for k, (lo, hi) in enumerate(((a1, m1), (m2, z2))):
                self.bands.insert(r + k, dict(id=self._next_id, name=f"{b['name']} ({'bas' if k == 0 else 'haut'})",
                                              start=lo, stop=hi, step=st, enabled=b["enabled"], dev=None))
                self._next_id += 1
        self._fit_x = True
        self._bands_changed()
        self.set_status(f"« {b['name']} » coupée en deux : {a1:g}–{m1:g} et {m2:g}–{z2:g} MHz.")

    # --------------------------------------------------------------- bandes
    def _append_band(self, name, start, stop, step, enabled=True, dev=None):
        with self.lock:
            self.bands.append(dict(id=self._next_id, name=name, start=start, stop=stop,
                                   step=step, enabled=enabled, dev=dev))
            self._next_id += 1

    def _bands_changed(self):
        self._bump()
        live = {b["id"] for b in self.scan_bands() if b["enabled"]} | {ZOOM_ID} | set(CALIB_IDS)
        for d in (self.latest, self.maxhold, self.partial_data, self.history):
            for k in [k for k in d if k not in live]:
                d.pop(k, None)
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
        self.update_band_dev_col()

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

    def _band_extent(self):
        """Étendue des bandes balayées (min début, max fin) : le zoom live n'en sort pas."""
        bs = [b for b in self.scan_bands() if b["enabled"]] or self.bands
        if not bs:
            return 0.1, 6000.0
        return min(b["start"] for b in bs), max(b["stop"] for b in bs)

    def _set_zoom(self, a, b):
        self._zoom_view = (a, b)
        lo, hi = self._band_extent()
        a, b = max(0.1, lo, a), min(6000.0, hi, b)
        if b <= a:                                  # vue entièrement hors des bandes : on reste au bord
            a, b = (lo, min(hi, lo + 1.0)) if b <= lo else (max(lo, hi - 1.0), hi)
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
        self.update_title()

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
            fr = [x for w in self.watch if self.in_scope(w) for x in block_points(w["freq"], w.get("bw"))]
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
    def _append_watch(self, name, freq, status="", thr=None, scene="", group="", bw=0.0):
        scene, group = (scene or "").strip(), (group or "").strip()
        if group and not scene:
            scene = DEFAULT_SCENE
        self.ensure_group(scene, group)
        band, cat = spectrum_info(freq, self.plan, self.tv)
        self.watch.append(dict(name=name, freq=freq, status=status, level=None, max=None,
                               state=None, peak=None, since=0.0, sig=None, thr=thr,
                               occw=OccWindow(self.occ_combo.currentData() or 60), t_acc=None,
                               band=band, cat=cat, scene=scene, group=group, free_since=None, absent=False,
                               bw=float(bw or 0.0)))     # bw > 0 : bloc large (Spectera / WMAS), en MHz

    def sort_watch(self):
        self.watch.sort(key=lambda w: w["freq"])

    def is_keep_free(self, name):
        return bool(name) and any(s["name"] == name and s.get("free") for s in self.statuses)

    def _strong_changed(self):
        self.strong_line.setValue(self.strong_spin.value())
        self.strong_line.setVisible(self.strong_chk.isChecked())
        if not self.strong_chk.isChecked():
            now = time.time()
            for k in [k for k in self.alarms.active if k[0] == "FORT"]:
                self.alarms.clear(k, now)
            self._strong_src = {}

    def check_strong(self, bid, f, l):
        """Alarme ⚠ TROP FORT : un signal au-dessus du seuil « trop fort » dans la bande qui vient d'être balayée.
        Une alarme par MHz ; elle se termine quand ce MHz repasse 3 dB sous le seuil."""
        src = self._strong_src
        if bid in CALIB_IDS or not self.strong_chk.isChecked() or l is None or not len(l):
            return
        thr, now = self.strong_spin.value(), time.time()
        peaks = strong_peaks(f, l, thr)
        keep = {("FORT", int(round(pf))) for pf, _ in peaks}
        # fin d'alarme : seulement pour les MHz couverts par CE balayage (hystérésis 3 dB)
        for key in [k for k, b in src.items() if b == bid and k not in keep]:
            mhz = key[1]
            seg = l[(f >= mhz - 0.5) & (f <= mhz + 0.5)]
            if not len(seg) or seg.max() < thr - 3.0:
                self.alarms.clear(key, now)
                src.pop(key, None)
        new = None
        for pf, pl in peaks:
            key = ("FORT", int(round(pf)))
            src[key] = bid
            w = min(self.watch, key=lambda w_: abs(w_["freq"] - pf), default=None)
            near = w is not None and abs(w["freq"] - pf) <= max(0.3, (w.get("bw") or 0) / 2)
            name = f"{w['name']} (trop près ?)" if near else f"Signal {pf:.3f} MHz"
            seen = self.seen_by(pf)
            if self.alarms.raise_(key, "TROP FORT", name, pf, 2, now, pl, self.layer_text(w) if near else "",
                                  ("risque de décrochage" + (f" · {seen}" if seen else ""))):
                new = (name, pf, pl)
                self.log_event(dict(name=name, freq=pf, scene="", group="", note=f"> {thr:.0f} dBm"), pl, "TROP FORT")
        if new is not None:
            self._alarm_sound(2)
            self.set_status(f"⚠ TROP FORT : {new[0]} à {new[2]:.0f} dBm ({new[1]:.3f} MHz) — risque de saturation / "
                            f"décrochage des récepteurs.")
            self.refresh_alarms()

    def set_unit(self, unit):
        """Unité d'affichage des niveaux (dBm, dBµV, %). Les valeurs internes, fichiers et shows restent en dBm."""
        unit = unit if unit in UNIT_SUFFIX else "dbm"
        self.unit = LevelSpin.unit = LevelAxis.unit = unit
        if self.unit_combo.currentData() != unit:
            self.unit_combo.blockSignals(True)
            self.unit_combo.setCurrentIndex(max(0, self.unit_combo.findData(unit)))
            self.unit_combo.blockSignals(False)
        for sp_ in (self.thr_spin, self.weak_spin, self.strong_spin):
            sp_.setSingleStep(1.0)
            sp_.refresh()
        u = UNIT_SUFFIX[unit]
        ax = self.spec.getPlotItem().getAxis("left")
        self.spec.getPlotItem().setLabel("left", f"Niveau ({u})")
        ax.picture = None
        ax.update()
        for c, base_ in ((C_LVL, "Niveau"), (C_MAX, "Max"), (C_THR, "Seuil")):
            it = self.watch_table.horizontalHeaderItem(c)
            if it is not None:
                it.setText(base_ if unit == "dbm" else f"{base_} ({u})")
        for w in self.watch:
            w["sig"] = None
        self.update_watch_table(force=True)
        self.refresh_alarms()
        if self.wall is not None and self.wall.isVisible():
            self.wall.rebuild()

    def lvl(self, dbm, suffix=False):
        return fmt_level(dbm, self.unit, 1, suffix)

    def wall_is_fullscreen(self):
        return getattr(self, "_wall_full", None) is not None

    def wall_fullscreen(self, on, screen=None):
        """Plein écran du mur : il quitte son panneau pour une vraie fenêtre, et y revient en sortant."""
        if on and not self.wall_is_fullscreen():
            if screen is None:
                screen = self.wall.screen()                 # l'écran où est le mur (2ᵉ écran s'il y est)
            win_ = WallFullWindow(self)
            hold = QtWidgets.QLabel("🧱 Mur en plein écran — Échap ou F11 pour le ramener ici.")
            hold.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dock_wall.setWidget(hold)
            win_.layout().addWidget(self.wall)
            self.wall.show()                # le panneau le cache en le lâchant : sinon plein écran tout noir (7.6.0)
            self._wall_full = win_
            if screen is not None:
                win_.setScreen(screen)
                win_.move(screen.geometry().topLeft())
            win_.showFullScreen()
            win_.activateWindow()
            QtCore.QTimer.singleShot(150, self.wall.rebuild)
            self.wall.full_btn.setText("⛶ Quitter (Échap)")
        elif not on and self.wall_is_fullscreen():
            win_, self._wall_full = self._wall_full, None
            self.dock_wall.setWidget(self.wall)
            self.wall.show()
            win_.hide()
            win_.deleteLater()
            self.wall.full_btn.setText("⛶ Plein écran")
            self.dock_wall.show()
            self.dock_wall.raise_()
        self.wall.relayout()

    def wall_detach(self, on):
        """Mur dans sa propre fenêtre (taille libre à la souris) ou en onglet à côté du spectre."""
        d = self.dock_wall
        if self.wall_is_fullscreen():
            self.wall_fullscreen(False)
        d.show()
        if on and not d.isFloating():
            d.setFloating(True)
            if d.width() > 900 or d.height() > 650 or d.width() < 250:     # 1re fois : une taille de vignette
                d.resize(560, 380)
                g = self.frameGeometry()
                d.move(g.right() - 600, g.top() + 80)
        elif not on and d.isFloating():
            d.setFloating(False)
        d.raise_()
        d.activateWindow()
        self._wall_float_txt()

    def _wall_float_txt(self, *_):
        if self.wall is not None:
            self.wall.float_btn.setText("📌 Raccrocher" if self.dock_wall.isFloating() else "🗗 Détacher")

    def in_alarm(self, w):
        return bool(w.get("absent")) or (w.get("state") == "occ" and self.is_keep_free(w["status"]))

    def set_wall_rows(self, rows, show):
        for r in rows:
            if 0 <= r < len(self.watch):
                if show:
                    self.watch[r].pop("hide_wall", None)
                else:
                    self.watch[r]["hide_wall"] = True
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()
            self.wall.refresh()

    def pick_wall(self):
        if not self.watch:
            self.set_status("La liste de fréquences est vide.")
            return
        dlg = WallPickDialog(self)
        if dlg.exec():
            shown = dlg.shown()
            self.set_wall_rows([i for i, on in shown.items() if on], True)
            self.set_wall_rows([i for i, on in shown.items() if not on], False)

    def edit_labels(self):
        dlg = LabelsDialog(self, self.sig_labels, self.sig_colors,
                           lambda k: self.tone_color(SIGNAL_TONES.get(k, "none")))
        if dlg.exec():
            self.sig_labels = dlg.values()
            self.sig_colors = dlg.colors()
            for w in self.watch:
                w["sig"] = None
            self.update_watch_table(force=True)
            self._update_markers()
            if self.wall is not None and self.wall.isVisible():
                self.wall.rebuild()

    def sig_view(self, w):
        """(texte, ton, couleur) du signal de w selon son statut (voir signal_view)."""
        key, tone = signal_key(w["state"], self.is_keep_free(w["status"]), self.is_keep_on(w["status"]),
                               bool(w.get("absent")), bool(w.get("im")))
        txt, _t = signal_view(w["state"], self.is_keep_free(w["status"]), self.is_keep_on(w["status"]),
                              bool(w.get("absent")), bool(w.get("im")), self.sig_labels)
        return txt, tone, self.sig_colors.get(key) or self.tone_color(tone)

    def tone_color(self, tone):
        th = self.theme
        return {"ok": th["st_free"], "free": th.get("st_libre", LIBRE_COLOR), "bad": th["st_occ"],
                "warn": th["st_weak"]}.get(tone, th["st_none"])

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
        overlaps = block_overlaps([(w["name"], w["freq"], w.get("bw") or 0.0) for w in self.watch])
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
            lv, mx = self.lvl(w["level"]), self.lvl(w["max"])
            stat = w["status"] or "—"
            thr_txt = self.lvl(w["thr"])
            pct = w["occw"].pct()
            occ_txt = "—" if pct is None else f"{pct:.0f} %"
            band = w["band"] or "—"
            if w.get("bw"):
                band = f"▬ bloc {w['bw']:g} MHz · {band}"
            if r in overlaps:
                band = f"⚠ dans le bloc « {overlaps[r]} » · {band}"
            layer = self.layer_text(w)
            gc = self.group_color(w["scene"], w["group"]) if layer else None
            sig = (lv, mx, st, conf, stat, w["name"], round(w["freq"], 3), thr_txt, occ_txt, band, layer, gc, absn)
            if not force and w["sig"] == sig:
                continue
            w["sig"] = sig
            sig_txt, tone, tone_col = self.sig_view(w)
            row_bg = {"bad": blend(th["st_occ"], base, 0.55), "warn": blend(th["st_weak"], base, 0.30)}.get(tone, base)
            row_fg = contrast_text(row_bg) if tone in ("bad", "warn") else th["ui_text"]
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
                if c == C_SIG and tone != "none":
                    bg = blend(tone_col, base, 1.0 if tone == "bad" else 0.85)
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
            self.set_watch_freq(w, v)
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
        a0 = m.addAction("— aucun statut\tCtrl+0")
        a0.setData("")
        for i, s in enumerate(self.statuses):
            a = m.addAction(color_icon(s["color"]), s["name"] + (f"\tCtrl+{i + 1}" if i < 9 else ""))
            a.setData(s["name"])
        return m

    def quick_status(self, which):
        """Raccourci clavier : statut n° which (0 = le 1er), None = aucun, "on" = le 1er « doit émettre »."""
        rows = self._sel_rows()
        if not rows:
            self.set_status("Sélectionne d'abord des fréquences dans la liste (clic, Maj+clic, Ctrl+A…).")
            return
        if which == "on":
            st = next((x for x in self.statuses if x.get("on")), None)
        elif which is None:
            st = dict(name="")
        else:
            st = self.statuses[which] if which < len(self.statuses) else None
        if st is None:
            self.set_status("Aucun statut à ce numéro (☰ Plus › Statuts… pour les voir / les ranger).")
            return
        self.set_status_rows(rows, st["name"])
        self.set_status(f"{len(rows)} fréquence(s) → « {st['name'] or 'aucun statut'} ».")

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
        a_blk = m.addAction("📶 Bloc large (Spectera / WMAS)…")
        wall_hid = all(self.watch[r].get("hide_wall") for r in rows)
        a_wall = m.addAction("🧱 Afficher sur le mur" if wall_hid else "🧱 Masquer sur le mur")
        hid = all(self.watch[r].get("hide_mk") for r in rows)
        a_mk = m.addAction("📍 Réafficher le repère sur le spectre" if hid else "📍 Masquer le repère sur le spectre")
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
            u = self.unit
            lo_, hi_ = (0.0, 100.0) if u == "pct" else (to_unit(-140.0, u), to_unit(20.0, u))
            v, ok = QtWidgets.QInputDialog.getDouble(
                self, "Seuil propre", f"Seuil « occupé » ({UNIT_SUFFIX[u]}) pour {len(rows)} fréquence(s) :",
                round(to_unit(cur, u), 1), lo_, hi_, 1)
            v = from_unit(v, u)
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
        elif act is a_mk:
            self.hide_marker_rows(rows, not hid)
        elif act is a_blk:
            self.set_block_rows(rows)
        elif act is a_wall:
            self.set_wall_rows(rows, wall_hid)
        elif self._assign_action(rows, act.data()):
            pass
        elif act.data() is not None:
            self.set_status_rows(rows, act.data())

    BLOCK_WIDTHS = (("Fréquence simple (pas de bloc)", 0.0), ("Bloc 6 MHz", 6.0), ("Bloc 8 MHz", 8.0),
                    ("Autre largeur…", None))

    def set_block_rows(self, rows):
        """Fréquence simple ↔ bloc large (Spectera / WMAS) pour les lignes choisies."""
        rows = [r for r in rows if 0 <= r < len(self.watch)]
        if not rows:
            return
        labels = [t for t, _ in self.BLOCK_WIDTHS]
        cur = self.watch[rows[0]].get("bw") or 0.0
        idx = next((i for i, (_t, v) in enumerate(self.BLOCK_WIDTHS) if v == cur), len(labels) - 1)
        txt, ok = QtWidgets.QInputDialog.getItem(
            self, "Bloc large", "Spectera / WMAS : un porteur large (canal TV) au lieu d'une fréquence.\n"
                                "« Doit émettre » : niveau médian du bloc · « Doit rester libre » : pic dans le bloc.\n\n"
                                "Largeur :", labels, idx, False)
        if not ok:
            return
        bw = dict(self.BLOCK_WIDTHS)[txt]
        if bw is None:
            bw, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc large", "Largeur du bloc (MHz) :",
                                                      max(cur, 1.0), 0.2, 40.0, 1)
            if not ok:
                return
        for r in rows:
            self.watch[r]["bw"] = float(bw)
            self.watch[r]["sig"] = None
        self._refresh_focus()
        self.update_watch_levels()
        self.update_watch_table(force=True)
        self._update_markers()

    def add_block_dialog(self):
        """Ajoute un bloc Spectera / WMAS : canal TV du pays, ou fréquence centrale + largeur."""
        ch = block_choices(self.tv)
        other = "Autre : fréquence centrale et largeur…"
        txt, ok = QtWidgets.QInputDialog.getItem(self, "Bloc Spectera / WMAS", "Canal (selon le pays choisi) :",
                                                 [c[0] for c in ch] + [other], 0, False)
        if not ok:
            return
        if txt == other:
            f, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc Spectera / WMAS", "Fréquence centrale (MHz) :",
                                                     610.0, 0.1, 6000.0, 3)
            if not ok:
                return
            bw, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc Spectera / WMAS", "Largeur (MHz) :",
                                                      8.0 if self.country not in ("US", "CA") else 6.0, 0.2, 40.0, 1)
            if not ok:
                return
            name = f"Spectera {f:.1f}"
        else:
            _lab, f, bw = next(c for c in ch if c[0] == txt)
            name = "Spectera " + txt.split(" — ")[0].replace("CH ", "ch ")
        sc, gr = self._scope_preset()
        on = next((x["name"] for x in self.statuses if x.get("on")), "")
        self._append_watch(name, f, status=on, scene=sc, group=gr, bw=bw)
        self.sort_watch()
        self.rebuild_watch_table()
        self._refresh_focus()
        self._update_markers()
        self.set_status(f"Bloc « {name} » ajouté : {f - bw / 2:g}–{f + bw / 2:g} MHz (statut « {on or 'aucun'} »).")

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
        fs = sorted(x for w in ws for x in block_points(w["freq"], w.get("bw")))
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
        vals = [datetime.now().strftime("%H:%M:%S"), w["name"], f'{w["freq"]:.3f}' if w["freq"] else "—",
                f"{level:.1f}" if w["freq"] else "—", event,
                self.layer_text(w) if "scene" in w else "", w.get("note", "")]
        col = (self.theme["st_occ"] if event in ("OCCUPÉ", "CONFLIT", "INTERMOD", "ABSENT", "APPAREIL PERDU", "TROP FORT",
                                                 "APPEL INCOMPLET")
               else self.theme["st_unk"]
               if event == "INCONNU" else self.theme["st_free"])
        self._auto_log(vals, w)                      # fichier : toujours en dBm
        if w["freq"]:
            vals = list(vals)
            vals[3] = self.lvl(level)
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
        if bid in CALIB_IDS:
            self._calib_add(CALIB_IDS.index(bid), f, l)
            return
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
        self.check_strong(bid, f, l)
        self.update_watch_table()
        if self.unk_chk.isChecked() or self._linecheck is not None:     # l'appel repère les packs mal réglés
            self.detect_unknown(bid, f, l)
        if self._linecheck is not None and bid != ZOOM_ID:
            self._linecheck.feed()
        if self.view_id in (-1, bid):
            self.update_plot()
        if self.view_id == bid:
            self.update_waterfall(bid, f, l)

    def on_partial(self, bid, f, l, i, n):
        if bid in CALIB_IDS:
            return
        self.partial_data[bid] = (f, l)
        name = next((b["name"] for b in self.scan_bands() if b["id"] == bid), "Zoom")
        self.set_status(f"Balayage « {name} » : segment {i}/{n}")
        if self.view_id in (-1, bid):
            self.update_plot(hist=False)

    def on_cycle(self, dt, nb, dev=0):
        self.dev_cycle[dev] = dt
        live = [v for k, v in self.dev_cycle.items() if k >= len(self.dev_live) or self.dev_live[k]]
        dt = max(live) if live else dt          # le plus lent des tinySA fixe le rythme de rafraîchissement
        nb = len([b for b in self.scan_bands() if b["enabled"]]) if self.ndev() > 1 and self._zoom is None else nb
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
            bw = w.get("bw") or 0.0
            how = "max" if self.is_keep_free(w["status"]) else "median"
            lvl = level_block(F, L, f, bw, how) if bw else level_at(F, L, f, win)
            w["level"] = lvl
            if lvl is None:
                w["state"], w["t_acc"] = None, None
                self._alarm_reset(w, now)
                continue
            w["max"] = lvl if w["max"] is None else max(w["max"], lvl)
            ref_l = ((level_block(self._ref_F, self._ref_L, f, bw, how) if bw else
                      level_at(self._ref_F, self._ref_L, f, win)) if rel else None)
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
                seen = self.seen_by(f)
                if keep_free:
                    f_at = f
                    if bw:                              # bloc : l'intrus est au pic mesuré dans le bloc
                        lo_ = int(np.searchsorted(F, f - bw / 2.0))
                        hi_ = int(np.searchsorted(F, f + bw / 2.0, side="right"))
                        if hi_ > lo_:
                            f_at = float(F[lo_ + int(np.argmax(L[lo_:hi_]))])
                    w["im"] = self.im_cause(w, f_at)
                    note = " · ".join(x for x in (w["im"], seen) if x)
                    self.log_event(dict(w, note=note) if note else w, lvl, "INTERMOD" if w["im"] else "CONFLIT")
                    conflict = w
                else:
                    self.log_event(dict(w, note=seen) if seen else w, lvl, "OCCUPÉ")
                    alert = w
            elif new == "occ":
                w["peak"] = max(w["peak"] or lvl, lvl)
            elif prev == "occ":
                w["im"] = ""
                self.log_event(w, w["peak"] or lvl, f"Libre ({now - w['since']:.0f} s)")
            w["state"] = new
            # ---- alarmes : CONFLIT (signal sur une fréquence « doit rester libre ») et ABSENT (« doit émettre » muette)
            fk = int(round(f * 1000))
            if new == "occ" and keep_free:
                prio = self.freq_prio(w)
                kind = "INTERMOD" if w.get("im") else "CONFLIT"
                if self.alarms.raise_(("CONFLIT", fk), kind, w["name"], f, prio, now, lvl, self.layer_text(w),
                                      " · ".join(x for x in (w.get("im", ""), self.seen_by(f)) if x)):
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
            live = {b["id"] for b in self.scan_bands() if b["enabled"]}
            keys = [k for k in set(self.latest) | set(self.partial_data) if k != ZOOM_ID and k in live]
            keys = [k for k in keys if self._series(k) is not None and len(self._series(k)[0])]
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

    MK_STYLE = (("full", "Trait sur toute la hauteur"), ("top", "Petit repère discret en haut"))

    def _build_mk_menu(self):
        """Menu 📍 Repères, reconstruit à chaque ouverture (couches et statuts peuvent avoir changé)."""
        m = self.mk_menu
        m.clear()
        mk = self.mk

        def check(menu, txt, on, setter):
            a = menu.addAction(txt)
            a.setCheckable(True)
            a.setChecked(bool(on))
            # on lit l'état de la case : avec un paramètre optionnel, PySide6 appelle la fonction SANS l'argument
            # « checked » (il valait toujours False : impossible de recocher à la souris)
            a.triggered.connect(lambda *_, a=a: setter(a.isChecked()))
            return a

        def toggle_in(key, value):
            def f(on):
                lst = [x for x in mk[key] if x != value]
                if not on:
                    lst.append(value)
                self.set_markers(**{key: lst})
            return f

        def toggle_state(value):
            def f(on):
                lst = [x for x in mk["states"] if x != value] + ([value] if on else [])
                self.set_markers(states=lst)
            return f

        m.addAction("✔ Tout afficher (enlève les filtres)").triggered.connect(lambda *_: self.reset_markers())
        check(m, "Masquer tous les repères  (Ctrl+M)", not mk["on"], lambda on: self.set_markers(on=not on))
        m.addSection("Afficher selon l'état mesuré")
        for key, txt in MK_STATES:
            check(m, txt, key in mk["states"], toggle_state(key))
        check(m, "Toujours montrer les fréquences en alarme", mk["alarms"], lambda on: self.set_markers(alarms=on))
        sub_l = m.addMenu("Par scène › groupe")
        for sc in self.scenes:
            groups = [g["name"] for g in sc["groups"]] or [""]
            for g in groups:
                k = mk_layer_key(sc["name"], g)
                check(sub_l, f"{sc['name']} › {g}" if g else sc["name"], k not in mk["hide_layers"],
                      toggle_in("hide_layers", k))
        check(sub_l, "Sans scène", "" not in mk["hide_layers"], toggle_in("hide_layers", ""))
        sub_s = m.addMenu("Par statut")
        for st in [x["name"] for x in self.statuses] + [""]:
            check(sub_s, st or "(sans statut)", st not in mk["hide_status"], toggle_in("hide_status", st))
        n_hid = sum(1 for w in self.watch if w.get("hide_mk"))
        if n_hid:
            m.addAction(f"Réafficher les {n_hid} repère(s) masqué(s) à la main").triggered.connect(
                lambda *_: self.hide_marker_rows([i for i, w in enumerate(self.watch) if w.get("hide_mk")], False))
        m.addSection("Affichage")
        check(m, "Noms des fréquences", self.names_chk.isChecked(), self.names_chk.setChecked)
        check(m, "Signaux inconnus (pointillés)", mk["unk"] and self.unk_chk.isChecked(), self.set_unk_markers)
        m.addSection("Style")
        grp = QtGui.QActionGroup(m)
        for key, txt in self.MK_STYLE:
            grp.addAction(check(m, txt, mk["style"] == key, lambda on, k=key: on and self.set_markers(style=k)))
        m.addSection("Couleur")
        grp2 = QtGui.QActionGroup(m)
        for i in range(self.mark_combo.count()):
            key, txt = self.mark_combo.itemData(i), self.mark_combo.itemText(i).replace("Repères : ", "")
            grp2.addAction(check(m, txt, self.mark_combo.currentData() == key,
                                 lambda on, k=key: on and self.mark_combo.setCurrentIndex(self.mark_combo.findData(k))))

    def _sync_mk_menu(self):
        if hasattr(self, "mk_btn"):
            self.mk_btn.setText("📍 Repères" + (" (masqués)" if not self.mk["on"] else
                                                 " (filtrés)" if mk_filtered(self.mk) else ""))

    def set_markers(self, **kw):
        for k, v in kw.items():
            if k in self.mk:
                self.mk[k] = v
        self._sync_mk_menu()
        self._update_markers()

    def set_unk_markers(self, on):
        """Repères des signaux inconnus ; les afficher demande aussi la détection (Réglages › Détection)."""
        if on and not self.unk_chk.isChecked():
            self.unk_chk.setChecked(True)
            self.set_status("Détection des signaux inconnus activée (Réglages › Détection) : leurs repères "
                            "apparaissent au prochain balayage.")
        self.set_markers(unk=on)

    def reset_markers(self):
        style, unk = self.mk["style"], self.mk["unk"]
        self.mk = dict(mk_default(), style=style, unk=unk)
        for w in self.watch:
            w.pop("hide_mk", None)
        self.set_markers()

    def toggle_markers(self):
        """Ctrl+M : tout masquer / réafficher (les filtres choisis sont gardés)."""
        self.set_markers(on=not self.mk["on"])
        self.set_status("Repères masqués (Ctrl+M pour les réafficher)." if not self.mk["on"] else "Repères affichés.")

    def hide_marker_rows(self, rows, hide=True):
        for r in rows:
            if 0 <= r < len(self.watch):
                if hide:
                    self.watch[r]["hide_mk"] = True
                else:
                    self.watch[r].pop("hide_mk", None)
        self.set_markers()

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
        vis = [w for w in self.watch if x0 <= w["freq"] + (w.get("bw") or 0) / 2 and
               w["freq"] - (w.get("bw") or 0) / 2 <= x1 and self.in_scope(w)]
        unk = [f for lst in self.unk_now.values() for f in lst if x0 <= f <= x1]
        mk = self.mk
        vis = [w for w in vis if marker_visible(
            w, mk, alarm=bool(w.get("absent")) or (w["state"] == "occ" and self.is_keep_free(w["status"])))]
        if not mk["on"] or not mk["unk"]:
            unk = []
        ys = [-130.0, 0.0] if self.mk["style"] == "full" else [y1 - (y1 - y0) * 0.07, y1]
        mode = self.mark_combo.currentData()
        groups, colors = {}, []
        for w in vis:
            col = None
            if mode == "status" and w["status"]:
                col = self.status_color(w["status"])
            elif mode == "group":
                col = self.group_color(w["scene"], w["group"])
            if col is None:
                col = self.sig_view(w)[2] if w["state"] is not None else self.theme["st_none"]
            seg = groups.setdefault((col, False), ([], []))
            bw = w.get("bw") or 0.0
            if bw:                         # bloc : bord gauche, bord droit, barre en haut
                a, b = w["freq"] - bw / 2, w["freq"] + bw / 2
                ybar = min(ys[1], y1 - (y1 - y0) * 0.015)
                seg[0].extend([a, a, b, b, a, b])
                seg[1].extend([ys[0], ys[1], ys[0], ys[1], ybar, ybar])
            else:
                seg[0].extend([w["freq"], w["freq"]])
                seg[1].extend(ys)
            colors.append(col)
        for f in unk:
            seg = groups.setdefault((self.theme["st_unk"], True), ([], []))
            seg[0].extend([f, f])
            seg[1].extend(ys)
        for key, (xs_, ys_) in groups.items():
            self._marker_item(key).setData(np.array(xs_), np.array(ys_))
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
                dy = (y1 - y0) * (0.08 if self.mk["style"] == "top" else 0.0)
                lab.setPos(vis[i]["freq"], y1 - 2.0 - dy - (i % 3) * 5.5)
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
        self.readout.setText(f"{x[k]:.3f} MHz   {self.lvl(float(y[k]), suffix=True)}")

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
        self._style_start(self.is_running())
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
        """Le mur est un panneau : on l'affiche (en onglet à côté du spectre, ou là où tu l'as rangé)."""
        self.dock_wall.show()
        self.dock_wall.raise_()
        self.wall.rebuild()

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

    def show_about(self):
        fw = self.info_lbl.text().strip() or "pas encore connecté"
        fw2 = f"<br>2ᵉ tinySA : {getattr(self, 'dev2_info', '') or '—'}" if self.dev2.get("on") else ""
        QtWidgets.QMessageBox.information(
            self, f"À propos de {APP_NAME}",
            f"<b>{APP_NAME}</b> version <b>{APP_VER}</b><br>"
            f"Python {sys.version.split()[0]} · Qt {QtCore.qVersion()}<br><br>"
            f"tinySA : {fw}{fw2}<br><br>"
            f"Config : {CFG_PATH}<br>Journaux : {self.log_dir}")

    def set_watch_freq(self, w, v):
        """Change la fréquence d'une ligne (mesures remises à zéro, liste retriée)."""
        w.update(freq=float(v), level=None, max=None, state=None, t_acc=None)
        w["occw"].clear()
        self.sort_watch()
        QtCore.QTimer.singleShot(0, self.rebuild_watch_table)
        self._update_markers()

    def open_sdr(self):
        d = SdrDialog(self)
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.sdr_cfg.update(d.values())
            for w in self.workers:
                w.sdr_dir = self.sdr_cfg.get("dir", "")
            self.set_status("Réglages SDR enregistrés" + (" (appliqués au prochain cycle)." if self.is_running()
                                                          else "."))

    def open_scan_convert(self):
        self._conv_dlg = ScanConvertDialog(self)
        self._conv_dlg.show()

    def open_plan_check(self):
        self._plan_dlg = PlanCheckDialog(self)
        self._plan_dlg.show()

    def open_linecheck(self):
        if self._linecheck is not None:
            self._linecheck.raise_()
            self._linecheck.activateWindow()
            return
        self._linecheck = LineCheckDialog(self)
        self._linecheck.show()

    def open_rescue(self):
        self._rescue_dlg = RescueDialog(self)
        self._rescue_dlg.show()

    def im_cause(self, w, f_at=None):
        """Le signal apparu sur w (doit rester libre), mesuré à f_at MHz (son pic), est-il un produit d'intermod de
        tes émetteurs qui émettent ? -> formule (« IM3 : 2×HF 1 − HF 3 ») ou ""."""
        tx = [x for x in self.watch if x is not w and x["state"] in ("occ", "weak") and not self.is_keep_free(x["status"])]
        if len(tx) < 2:
            return ""
        tx.sort(key=lambda x: -(x["level"] if x["level"] is not None else -999.0))
        tx = tx[:25]
        tol = max(0.05, self.win_spin.value() / 1000.0)
        rows, _info = im_explain(w["freq"] if f_at is None else f_at, [x["freq"] for x in tx], (3, 5), 3, tol, 3,
                                 bws=[float(x.get("bw") or 0.0) for x in tx])
        if not rows:
            return ""
        r = rows[0]
        return f"{IM_NAMES.get(r['order'], 'IM')} : " + im_formula(r["terms"], [x["name"] for x in tx])

    def im_note(self, fr, step):
        """Pour un signal inconnu : combinaison d'émetteurs actifs qui pourrait l'expliquer (IM3), sinon ''."""
        act = [w for w in self.watch if w["state"] in ("occ", "weak")]
        if len(act) < 2:
            return ""
        act.sort(key=lambda w: -(w["level"] if w["level"] is not None else -999.0))
        act = act[:25]
        rows, _info = im_explain(fr, [w["freq"] for w in act], (3,), 3, max(0.1, step * 1.5), 3,
                                 bws=[float(w.get("bw") or 0.0) for w in act])
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

    def _build_docks(self, left, ftab, ltab, wf_box, center):
        L, R, B = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        self.dock_set = self._make_dock("Réglages", "dock_reglages", left, L)
        self.dock_freq = self._make_dock("Fréquences et couches", "dock_freq", ftab, R)
        self.dock_log = self._make_dock("Journal", "dock_journal", ltab, R)
        self.dock_spec = self._make_dock("Spectre", "dock_spectre", center, B)
        self.dock_wf = self._make_dock("Waterfall", "dock_wf", wf_box, B)
        self.dock_alarm = self._make_dock("Alarmes", "dock_alarmes", self._build_alarm_panel(), B)
        self.wall = WallWindow(self)
        self.dock_wall = self._make_dock("Mur de fréquences", "dock_mur", self.wall, B)
        self.dock_wall.topLevelChanged.connect(self._wall_float_txt)
        self.splitDockWidget(self.dock_spec, self.dock_wf, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_wf, self.dock_alarm, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.dock_spec, self.dock_wall)       # en onglet à côté du spectre
        self.dock_spec.raise_()
        self.dock_alarm.hide()
        self.dock_wall.hide()
        self.docks = [self.dock_spec, self.dock_set, self.dock_freq, self.dock_log, self.dock_wf, self.dock_alarm,
                      self.dock_wall]
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
        self.win_menu.addAction("🧱 Mur sur l'autre écran (fenêtre)").triggered.connect(
            lambda *_: self.wall_window_other_screen())
        self.win_menu.addAction("🧱 Mur en plein écran sur l'autre écran").triggered.connect(self.wall_other_screen)

    def _dock_sizes(self):
        """Disposition de base : le spectre a la place (≈ la moitié de la largeur, ~70 % de la hauteur de sa
        colonne), réglages étroits à gauche, liste à droite, waterfall et alarmes en bandeaux sous le spectre."""
        W, H = max(self.width(), 900), max(self.height(), 600)
        left = max(230, min(330, int(W * 0.19)))
        right = max(290, min(560, int(W * 0.31)))
        over = left + right - int(W * 0.5)        # petit écran (portable ~1024 px) : le spectre garde la moitié
        if over > 0:
            right -= min(over, right - 290)
        self.resizeDocks([self.dock_set, self.dock_freq], [left, right], Qt.Orientation.Horizontal)
        self._middle_sizes()

    def _middle_sizes(self):
        """Colonne du milieu : spectre ~70 %, waterfall ~30 %, alarmes en bandeau (~170 px)."""
        H = max(self.height(), 600) - 80
        docks, sizes = [self.dock_spec], [0]
        if self.dock_wf.isVisible() and not self.dock_wf.isFloating():
            docks.append(self.dock_wf)
            sizes.append(int(H * 0.28))
        if self.dock_alarm.isVisible() and not self.dock_alarm.isFloating():
            docks.append(self.dock_alarm)
            sizes.append(170)
        sizes[0] = max(250, H - sum(sizes[1:]))
        if len(docks) > 1:
            self.resizeDocks(docks, sizes, Qt.Orientation.Vertical)

    def layout_standard(self):
        L, R, B = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        for d in self.docks:
            d.setFloating(False)
            d.show()
        self.addDockWidget(L, self.dock_set)
        self.addDockWidget(R, self.dock_freq)
        self.addDockWidget(R, self.dock_log)
        self.addDockWidget(B, self.dock_spec)
        self.splitDockWidget(self.dock_spec, self.dock_wf, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_wf, self.dock_alarm, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.dock_freq, self.dock_log)
        self.tabifyDockWidget(self.dock_spec, self.dock_wall)
        self.dock_freq.raise_()
        self.dock_spec.raise_()
        self.dock_alarm.hide()
        self.dock_wall.hide()
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

    def wall_window_other_screen(self):
        """Le mur dans une fenêtre normale qui occupe l'autre écran (la barre des tâches reste visible)."""
        scr = self._other_screen()
        self.open_wall()
        if scr is None:
            self.set_status("Un seul écran détecté : branche le 2ᵉ écran (ou détache le mur et place-le à la souris).")
            return
        if self.wall_is_fullscreen():
            self.wall_fullscreen(False)
        self.wall_detach(True)
        self.dock_wall.setGeometry(scr.availableGeometry())
        self.dock_wall.raise_()
        self.set_status("Mur sur l'autre écran. « 📌 Raccrocher » le remet à côté du spectre ; F11 = plein écran.")

    def wall_other_screen(self):
        scr = self._other_screen()
        self.open_wall()
        if scr is None:
            self.set_status("Un seul écran détecté : le mur est ouvert en fenêtre (F11 pour le plein écran).")
            return
        self.wall_fullscreen(True, scr)

    def _wf_show(self, on):
        self.wf.setVisible(bool(on))
        self.wf_hint.setVisible(not on)
        if on and getattr(self, "dock_wf", None) is not None and not self.dock_wf.isVisible():
            self.dock_wf.show()
            QtCore.QTimer.singleShot(0, self._middle_sizes)      # bandeau sous le spectre, pas la moitié

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
            was = self.dock_alarm.isVisible()
            self.dock_alarm.show()
            self.dock_alarm.raise_()
            if not was:
                QtCore.QTimer.singleShot(0, self._middle_sizes)
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
            for key in [k for k in self.alarms.active if k[0] not in ("APPAREIL", "FORT") and k[1] not in fks]:
                self.alarms.clear(key, now)
        for a in self.alarms.due_repeat(now):
            self._alarm_sound(a["prio"])
        self._notify_new_alarms()
        reason = getattr(self, "_diag_pending", None)
        if reason:
            self._diag_pending = None
            try:
                self.dump_diag(reason, quiet=True)
            except Exception:  # noqa: BLE001 — le diagnostic ne doit jamais faire tomber l'appli
                pass
        self._web_ack_pending()
        if self.web is not None:
            self._web_json = self.web_json()
            if self.web_cfg["views"].get("spectre") or self.web_cfg["views"].get("waterfall"):
                if self.web.watching(("spectre", "waterfall")):        # seulement si quelqu'un regarde
                    self._web_spec = self.web_spec_json()
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
            vals = (ALARM_PRIO.get(a["prio"], "?"), a["kind"], a["name"], f'{a["freq"]:.3f}' if a["freq"] else "—",
                    fmt_clock(a["t0"]), fmt_dur(end - a["t0"]), self.lvl(a["level"], suffix=True),
                    " · ".join(x for x in (a["layer"], "" if a["kind"] == "ABSENT" else a.get("info", "")) if x),
                    state)
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

    def _web_ack_pending(self):
        """Acquittements faits depuis un téléphone (page web, code PIN)."""
        n = 0
        while True:
            try:
                target = self._web_acks.get_nowait()
            except queue.Empty:
                break
            n += self.alarms.ack_all() if target == "all" else int(self.alarms.ack(target))
        if n:
            self.refresh_alarms()
            self.set_status(f"📱 {n} alarme(s) acquittée(s) depuis la page web.")
        return n

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
        if f:
            self.view_range(f - 1.0, f + 1.0)

    def toggle_alarm_dock(self):
        d = self.dock_alarm
        if d.isVisible():
            d.hide()
        else:
            d.show()
            d.raise_()
            QtCore.QTimer.singleShot(0, self._middle_sizes)

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
        for w in self.workers:
            if w.isRunning():
                w.requestInterruption()
        for w in self.workers:
            w.wait(8000)
        if getattr(self, "_relay_win", None) is not None:
            self._relay_win.close()
        if self.web is not None:
            self.web.stop()
            self.web = None
        if self.wall is not None and self.wall_is_fullscreen():
            self.wall_fullscreen(False)
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


def log_crash(kind, text, path=None):
    """Ajoute une erreur inattendue à crash.log (horodatée, avec la version). -> chemin du fichier."""
    path = Path(path or CRASH_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} · {APP_NAME} {APP_VER} · {kind}\n{text}\n")
    except OSError:
        pass
    return path


def install_crash_log(app=None):
    """L'exe n'a pas de console : toute erreur imprévue part dans crash.log, avec un message (au plus 1 / min).
    Plantage dur (segfault) : faulthandler écrit aussi dans crash.log."""
    state = {"last": 0.0}

    def hook(t, v, tb):
        if issubclass(t, KeyboardInterrupt):
            return
        path = log_crash("erreur", "".join(traceback.format_exception(t, v, tb)))
        if app is not None and time.time() - state["last"] > 60:
            state["last"] = time.time()
            try:
                QtWidgets.QMessageBox.warning(
                    None, APP_NAME, f"Erreur inattendue : {t.__name__}: {v}\n\nLe logiciel continue. Le détail est dans :\n"
                                    f"{path}\n(envoie ce fichier pour qu'on corrige).")
            except Exception:  # noqa: BLE001
                pass

    def thook(args):
        log_crash(f"erreur dans un fil ({getattr(args.thread, 'name', '?')})",
                  "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    sys.excepthook = hook
    threading.excepthook = thook
    try:
        CRASH_PATH.parent.mkdir(parents=True, exist_ok=True)
        fh = open(CRASH_PATH, "a", encoding="utf-8")
        faulthandler.enable(fh)
        return fh                                  # à garder ouvert
    except OSError:
        return None


def install_french(app):
    """Boutons standard de Qt en français (Oui / Non, OK / Annuler, Ouvrir…). Cherche aussi dans l'exe PyInstaller."""
    dirs = [QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.TranslationsPath)]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        dirs += [os.path.join(base, "PySide6", "Qt", "translations"), os.path.join(base, "PySide6", "translations")]
    ok = False
    for name in ("qtbase_fr", "qt_fr"):
        tr = QtCore.QTranslator(app)
        if any(tr.load(name, d) for d in dirs if d):
            app.installTranslator(tr)
            ok = True
    return ok


def install_gc_main_thread(app, interval_ms=500):
    """Le ramasse-miettes de Python ne tourne plus que dans le fil de l'interface.
    Sinon (Python 3.12+) il peut se déclencher dans le fil du tinySA et y détruire des objets Qt de l'interface
    (courbes, lignes de tableau jetées quand on change le nombre de points…) → « access violation » (crash.log de
    Clément, 7.4.2 : ScanWorker.run, boucle d'attente de reconnexion). Même remède que GarbageCollector de pyqtgraph."""
    gc.disable()
    thr = gc.get_threshold()

    def tick():
        c0, c1, c2 = gc.get_count()
        if c0 > thr[0]:
            gc.collect(0)
            if c1 > thr[1]:
                gc.collect(1)
                if c2 > thr[2]:
                    gc.collect(2)

    t = QtCore.QTimer(app)
    t.timeout.connect(tick)
    t.start(interval_ms)
    return t


def main():
    app = QtWidgets.QApplication(sys.argv)
    app._gc_timer = install_gc_main_thread(app)
    install_french(app)
    ico = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for cand in (ico / "icone.png", ico / "assets" / "icone.png"):     # exe (PyInstaller) ou sources
        if cand.exists():
            app.setWindowIcon(QtGui.QIcon(str(cand)))
            break
    app._crash_fh = install_crash_log(app)
    if "--relais" in sys.argv:              # PC où est branché le 2ᵉ tinySA : juste le relais réseau
        win = RelayWindow()
    else:
        win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
