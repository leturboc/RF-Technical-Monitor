#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RF Technical Monitor v7
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
import subprocess
import threading
import time
import tempfile
import traceback
import unicodedata
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta
from pathlib import Path

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 8.1 : AVANT numpy. Ses petits calculs
    os.environ.setdefault(_v, "1")   # (filtres du SDR) étaient lancés sur tous les cœurs, qui tournaient à vide : ×4 de
#                                      processeur pour rien, pris au son et à l'affichage -> saccades (« morse »)
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters  # noqa: F401  (capture PNG)
import serial
import serial.tools.list_ports
try:                                      # chargé par serial_for_url("socket://…") : à embarquer dans l'exe
    import serial.urlhandler.protocol_socket  # noqa: F401
except ImportError:                       # faux pyserial des tests
    pass
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

APP_NAME = "RF Technical Monitor"
APP_VER = "8.1.0"
POINTS_CHOICES = [101, 145, 290, 500, 1000, 3000, 5000, 10000, 30000]
SEG_CHOICES = [None, 145, 290, 450]     # points max par commande scan (None = auto)
WF_ROWS = 150                # profondeur du waterfall
WF_MAX_COLS = 3000           # colonnes max du waterfall (réduction par maximum)
ZOOM_ID = -2                 # identifiant interne de la "bande" de zoom live
MAX_DEVS = 8                 # tinySA en même temps au plus (1er, 2ᵉ, puis 3ᵉ à 8ᵉ : « devx »)
CALIB_IDS = tuple(-3 - d for d in range(MAX_DEVS))   # bandes internes de la calibration (une par tinySA)
CALIB_SWEEPS = 3             # balayages par appareil pour calibrer
CALIB_TIMEOUT = 180.0
MAX_LABELS = 30              # nb max de noms affichés sur le graphe
SEL_COLOR = "#ffb300"        # fréquence(s) choisie(s) dans la liste, sur le spectre (ambre : lisible clair / sombre)
SEL_MAX = 12                 # nb max de fréquences choisies surlignées
OCC_LOG_S = 3.0              # journal : une occupation plus courte n'est pas notée (journal de Clément 16/11/2026 :
                             # 310 lignes OCCUPÉ / Libre (1 s) pour un micro qui oscillait autour du seuil)
TINYSA_VID, TINYSA_PID = 0x0483, 0x5740
LEGACY_CFG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "TinySAMonitor"     # nom d'avant la 8.1
LEGACY_DOCS = Path.home() / "Documents" / "TinySA Monitor"
CFG_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "RFTechnicalMonitor" / "config.json"
DOCS_ROOT = Path.home() / "Documents" / "RF Technical Monitor"


def _swap_paths(v, old, new):
    """Chemins enregistrés dans la config : old/… -> new/… (récursif)."""
    if isinstance(v, str):
        for o, n in zip(old, new):
            if v == o or v.startswith(o + os.sep) or v.startswith(o + "/"):
                return n + v[len(o):]
        return v
    if isinstance(v, list):
        return [_swap_paths(x, old, new) for x in v]
    if isinstance(v, dict):
        return {k: _swap_paths(x, old, new) for k, x in v.items()}
    return v


MIGRATION_INFO = []           # 8.1 : ce que l'utilisateur doit savoir de la migration (affiché une fois au démarrage)


def _merge_dir(src, dst):
    """8.1 : fusionne src dans dst SANS RIEN ÉCRASER : chaque fichier absent de dst y est déplacé ; un fichier qui existe
    déjà des deux côtés reste dans src. Les dossiers vidés sont retirés. -> (déplacés, restés : [chemins relatifs])."""
    moved, kept = 0, []
    for root, dirs, files in os.walk(src, topdown=False):
        rel = os.path.relpath(root, src)
        for f in files:
            if f in ("instance.lock",):
                continue
            a = os.path.join(root, f)
            b = os.path.normpath(os.path.join(dst, rel, f))
            if os.path.exists(b):
                kept.append(os.path.normpath(os.path.join(rel, f)))
                continue
            try:
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.move(a, b)
                moved += 1
            except OSError:
                kept.append(os.path.normpath(os.path.join(rel, f)))
        try:
            if root != str(src) and not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass
    return moved, kept


def migrate_legacy(cfg_dir, docs, old_cfg=None, old_docs=None):
    """8.1 (TinySA Monitor -> RF Technical Monitor) : rien ne se perd. La 1re fois, la config est COPIÉE (l'ancienne reste
    pour revenir à une 8.0) et le dossier Documents est RENOMMÉ (journaux, shows, profils : pas de copie de plusieurs Go) ;
    les chemins enregistrés dans la config suivent. Dossier Documents impossible à renommer (fichier ouvert) : l'ancien
    reste utilisé. -> dossier Documents à utiliser."""
    old_cfg = Path(old_cfg) if old_cfg else LEGACY_CFG_DIR
    old_docs = Path(old_docs) if old_docs else LEGACY_DOCS
    cfg_dir, docs, notes = Path(cfg_dir), Path(docs), []
    try:
        if not cfg_dir.exists() and old_cfg.is_dir():
            shutil.copytree(old_cfg, cfg_dir, ignore=shutil.ignore_patterns("instance.lock"))
            notes.append(f"config copiée de {old_cfg}")
    except OSError as e:
        notes.append(f"config : copie impossible ({e})")
    use_docs = docs
    if not docs.exists() and old_docs.is_dir():
        try:
            os.rename(old_docs, docs)
            notes.append(f"dossier {old_docs} renommé en {docs}")
        except OSError as e:
            use_docs = old_docs
            notes.append(f"dossier {old_docs} gardé tel quel ({e})")
    elif (docs.is_dir() and old_docs.is_dir() and old_docs != docs and any(old_docs.iterdir())
          and not (old_docs / "LISEZMOI_migration.txt").exists()):      # déjà fusionné une fois : on n'y revient pas
        # 8.1 (audit) : les DEUX dossiers existent : fusion sans rien écraser ; les doublons restent dans l'ancien
        try:
            moved, kept = _merge_dir(str(old_docs), str(docs))
        except OSError as e:
            moved, kept = 0, [f"({e})"]
        if moved or kept:
            notes.append(f"dossier {old_docs} fusionné dans {docs} : {moved} fichier(s) déplacé(s), "
                         f"{len(kept)} laissé(s) (déjà présents)")
        if kept:
            try:
                with open(old_docs / "LISEZMOI_migration.txt", "w", encoding="utf-8") as fh:
                    fh.write(f"RF Technical Monitor 8.1 utilise maintenant {docs}.\n"
                             "Ces fichiers existaient déjà là-bas avec le même nom : ils sont restés ici, rien n'a été "
                             "écrasé. Compare-les et garde ceux que tu veux :\n" + "\n".join(kept[:500]) + "\n")
            except OSError:
                pass
            MIGRATION_INFO.append((str(old_docs), str(docs), len(kept)))
        else:
            try:
                old_docs.rmdir()
            except OSError:
                pass
    if notes and cfg_dir.is_dir():
        for f in ("config.json", "config.json.bak"):
            p = cfg_dir / f
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                old = [str(old_cfg)] + ([str(old_docs)] if use_docs == docs else [])
                new = [str(cfg_dir)] + ([str(docs)] if use_docs == docs else [])
                p.write_text(json.dumps(_swap_paths(d, old, new), ensure_ascii=False, indent=1), encoding="utf-8")
            except (OSError, ValueError):
                pass
        try:
            with open(cfg_dir / "migration.txt", "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%Y-%m-%d %H:%M} · " + " ; ".join(notes) + "\n")
        except OSError:
            pass
    return use_docs


DOCS_ROOT = migrate_legacy(Path(os.environ.get("APPDATA", str(Path.home()))) / "RFTechnicalMonitor", DOCS_ROOT)
PROFILE_DIR = CFG_PATH.parent / "profils"
REF_PATH = CFG_PATH.parent / "reference.json"
CRASH_PATH = CFG_PATH.parent / "crash.log"
CFG_BAK = CFG_PATH.with_suffix(".json.bak")
AUTOSAVE_MS = 60_000
STOP_FORCE_MS = 4000
LAYOUT_VER = 4                # à monter quand la disposition de base change (les anciennes sont ignorées)          # « Arrêter » : au-delà, on ferme le port pour débloquer
LOG_DIR = DOCS_ROOT / "Journaux"
SHOW_DIR = DOCS_ROOT / "Shows"
TNT_DB_PATH = CFG_PATH.parent / "anfr_tnt.json"     # 📺 base ANFR réduite aux sites TNT (7.58)
USER_DIR = DOCS_ROOT / "Profils"      # 👤 profils utilisateur (7.57)

# 8.1 : la partie sans interface est dans tsm_core.py (testée seule) ; tout est importé ici.
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:     # tests qui chargent ce fichier par son chemin
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tsm_core import (  # noqa: F401
    ADJ_RISE_DB, ADJ_WARN_DB, ALARM_HELP, ALARM_ORDER, ALARM_PRIO, ALARM_REC_POST_S, ALARM_REC_PRE_S,
    ALARM_REPEATS, ALARM_SND_MAX_S, ALARM_TONES, ALARM_TONES_CLASSIC, ALARM_TUNE_COOLDOWN_S, ALARM_TUNE_KINDS,
    ALARM_USER_HOLD_S, ANFR_DATASET, ANFR_TNT_SYSTEM, ANOM_APPEAR_DB, ANOM_DROP_DB, ANOM_FLAPS, ANOM_FLAP_S,
    ANOM_LABELS, ANOM_NOISE_DB, APP_ICON_PNG64, APP_SOUNDS, AUDIO_ALIGNS, AUDIO_CHOPS, AUDIO_CLIP, AUDIO_DYN_DB,
    AUDIO_NOISY_DB, AUDIO_PRESENT_DB, AUDIO_REF_DEFAULT, AUDIO_SILENCE_DB, AUDIO_SRCS, AUDIO_UNITS, AUTO_BUDGET,
    AUTO_FALL_S, AUTO_POINTS, AUTO_RISE_S, AUTO_STEPS_KHZ, AUTO_THR_DEFAULT, AUTO_THR_HELP, AcqClock, AlarmBook,
    AnomalyTracker, AudioMeter, BAND_PRESETS, BUSY_MARGIN, BUSY_MODES, BurstDetector, CAL_HALF_MHZ,
    CAL_MIN_SIGNALS, CAL_SNR_DB, CATEGORIES, CHANGE_LABELS, CHANNEL_KHZ, CHRON_GROUP_S, CMP_IMPL, CMP_MODEL_VER,
    COMPANDERS, COMPANDER_CARDS, COORD_METHODS, COORD_ORDERS, COORD_RBW_MAX, COORD_RBW_TIP, COORD_STEPS,
    COORD_TOURS, COORD_TRIES, COUNTRIES, COUNTRY_ALLOWED, COUNTRY_DOUBTS, COUNTRY_NOTES, COUNTRY_REFS,
    COUNTRY_SOURCES, COUNTRY_UHF, COUNTRY_UHF_DEFAULT, COVERAGE, ChannelDemod, ClientBook, CompChain, CompTx,
    DBU_V, DBV_DBU, DEFAULT_SCENE, DEFAULT_STATUSES, DEFAULT_THEME, DELIMS, DEMOD_CUSTOM, DEMOD_DIGITAL,
    DEMOD_PRESETS, DEMOD_RULES, DEMO_DBM, DEMO_FAULTS, DEMO_FAULT_HELP, DEMO_PILOT, DEMO_RATE, DEMO_SIG_KINDS,
    DEMO_SOUNDS, DEVICE_HELP, DIAG_EDGE_DB, DIAG_FLAPS, DIAG_FLAP_MIN, DIAG_ICONS, DIAG_NOISE_HIGH, DIAG_TV_MARGIN,
    DIAG_ZONE_DB, DIAG_ZONE_MHZ, DiversityAB, EZRF_GROUP_MODES, EZRF_NAMINGS, EZRF_PREFIX, EZRF_TIMES, FAV_KEYS,
    FESTIVAL_DEFAULT, FREQ_FORMATS, FRESH_S, FROZEN_S, FirDecim, GAIN_HEADROOM_DB, GAIN_OVF_MAX, GEN_MODS,
    GLOSSARY, GROUP_COLORS, GROUP_COLORS_DEF, GROUP_WORDS, GUARD_BEAT_S, GUARD_GRACE_S, GUARD_HANG_S,
    HEAT_DIR_COLORS, HEAT_DOT_SIZES, HEAT_MAX, HEAT_PALETTES, HEAT_PAL_DEFAULT, HEAT_REACH, HEAT_REACHES,
    HEAT_TRAIL_WIDTHS, HINT_EMPTY_S, HINT_TNT_S, HIST_MAX, HIST_WHAT, HOP_OPEN_DB, HYST, HopState, IM_CHUNK,
    IM_MAX_PAIRS, IM_NAMES, IM_SEV_TEXT, IM_TOL_CUSTOM, IM_TOL_PRESETS, INC_AUTO_KINDS, INC_COOLDOWN_S, INC_GAP_S,
    INC_MAX_MB, INC_POST_S, IQ_BYTES, IQ_RING_BUDGET, IQ_RING_S, KEEP_DAYS, LAB_DIFF_KEYS, LAB_EXPECT, LAB_FAULTS,
    LAB_FAULT_HELP, LAB_MODES, LAB_MOD_STEPS, LAB_PLOT_HELP, LAB_RATE, LAB_SCENARIOS, LAB_SECONDS,
    LAB_SESSION_KINDS, LANGS, LAYOUT_PARTS, LC_TEXT, LEGEND_ITEMS, LEVEL_UNITS, LEVEL_WORDS, LIBRE_COLOR,
    LISTEN_COMPANDERS, LISTEN_HOP_DWELL, LISTEN_IF, LISTEN_MODES, LISTEN_RATE, LISTEN_WEB_KEEP, LISTEN_WEB_RATE,
    LOG_KINDS, LORA_COUNTRY, LORA_PLANS, MAP_BG_MAX_B64, MAP_COORD_MAX, MAP_DEFAULT, MAP_STEP, METER_STYLES,
    MIN_PTS, MK_STATES, MOD_QUIZ_CHOICES, MS_BAD, MS_CSS, MS_FLAP, MS_WARN, MUTE_AUDIO_DB, MUTE_CARRIER_DB,
    MUTE_HOLD_S, MicHistory, NAME_WORDS, NOISE_DBM_HZ, NOISE_RATE, NOTIFY_MODES, OLD_CRT_THEMES, OLD_DEFAULT_THEME,
    OccWindow, PATROL_DWELLS, PATROL_SRCS, PF_SEP, PHASES, PILOT_LEARN_S, PILOT_MISS_S, PILOT_TOL_HZ,
    PLANNING_DEFAULT, PLAN_EU, PLAN_EXTS, PLAN_OVERRIDES, PLAN_US, PLAN_US_LOW, POST_MICS_MAX, PREP_CSS,
    PRESET_LABELS, PRIVACY_DEFAULT, PRIVACY_TEXT, PROBE_STEPS, PROBE_TEXT, PROBLEM_CARDS, PROBLEM_IMPACT,
    PROBLEM_IMPACT_DEFAULT, PROVENANCE, PcmRing, Persist, PinGuard, PreRing, QUICK_PRESETS, RBW_LIST, READY_ICONS,
    RECUR_KINDS, RECUR_LABELS, REG_CHECKED, REH_AUDIO_DB, REH_MIN_N, REH_NOISE_DB, REH_SNR_DB, RELAY_PORT,
    REPORT_PRO_CSS, REWIND_BINS, REWIND_FRAME_S, REWIND_MINUTES, RF_MODES, RT_FFT, RT_RATES, RX_AF_VIEWS,
    RX_ALIASES, RX_BRANDS, RX_CUSTOM, RX_IF_VIEWS, RX_LIBRARY, RX_PROFILES, RX_SRC_TXT, RX_STALE_S, RefCompare,
    RehearsalProfile, Resampler, RewindBuffer, S9_DBM, SAT_BAD, SAT_LNA_SHIFT, SAT_WARN, SCALES, SCAN_FREQ_UNITS,
    SCAN_LEVEL_UNITS, SCAN_SEPS, SCENE_WORDS, SCREEN_HIDE, SCREEN_PANELS, SCREEN_PRESETS, SDR_ALIASES,
    SDR_AUTO_DEFAULT, SDR_DEMO_KIND, SDR_DEMO_MODEL, SDR_DTYPE, SDR_EVENTS, SDR_EVENTS_HEAD, SDR_HIST_MAX,
    SDR_KINDS, SDR_LAYOUTS, SDR_MODELS, SDR_MODEL_DEFAULT, SDR_MODES, SDR_NFFT, SDR_POSTS_MAX, SDR_PROBE,
    SDR_SESSION_HEAD, SDR_STEPS_KHZ, SECRET_WEB, SEP, SESSION_DEFAULT, SESSION_JOURNAL_HEAD, SHOW_EXT, SHOW_KEYS,
    SHOW_META, SHURE_PORT, SIGNAL_DEFAULTS, SIGNAL_LABELS, SIGNAL_TONES, SIG_KINDS, SIG_TYPES, SIM_MARK,
    SITE_COLORS, SLOW_CYCLE_S, SNR_GOOD, SNR_LOW, SNR_OK, SOUND_DEFAULT, SOUND_STYLES, STAIR_GAP_S, STAIR_LEVELS,
    STAIR_PERIOD, STAIR_STATES, STAIR_STEP_S, STATE_TXT, STATION_DEFAULT, STATUS_AUTO_COLORS, STATUS_HELP, STEPS,
    STEP_ALIAS, STEP_DEFAULT, STEP_HINTS, STOPPED_HEALTH, SigGen, StreamStats, SweepAccum, SweepStore,
    TECH_ACTIONS, TEMPLATE_DROP, THEMES, THEME_KEYS, THEME_PALETTES, TINYSA_REFUSALS, TNT_DEFAULT, TNT_FILL,
    TNT_MARGIN_DB, TONE_OK, TONE_OK_CLASSIC, TOURS, TOUR_KEYS, TR, TUTO_ALERTES, TX_DURATIONS, TX_MAX_SIGS,
    TX_RATES, Translator, UI_LEVELS, UI_WORDS, UNIT_DIV, UNIT_SUFFIX, UNKNOWN_HEALTH, USER_KEYS, UndoStack,
    VRX_BUDGET, VRX_MAX, WALL_SIZES, WALL_TILE, WAV_PCM, WEB_PAGE, WEB_PORT, WEB_VIEWS, WEB_VIEWS_HIDDEN,
    WEB_VIEW_KEYS, WF_MAPS, WIDE_RATIO, WIZARD_SCAN_S, WIZARD_STEPS, WR_ADC_RATE, _BRANDS, _CARD_APPROX, _EZ,
    _EZ_DEV_RE, _FREQ_WORDS, _G, _GROUP_WORDS, _LABEL_RE, _LEAD_ICON, _NAME_PRIORITY, _NOISE, _OKABE, _OLD_CRT_ACC,
    _OVR, _PROBLEM_KEYS, _QE_NUM, _SCENE_WORDS, _SRC_CEPT, _SRC_ITU, _SRC_LEVEL, _STATUS_WORDS, _TOL_EZ, _TOL_IEM,
    _TOL_LARGE, _TOL_NONE, _TOL_SLXD, _WEB_BASE_VIEWS, _abbrev, _anfr_dms, _audio_text, _chime_pcm, _circ_dist,
    _clean_grid, _cp, _cp_state, _deemph_taps, _ez_dev_params, _ez_num, _fill_score, _fin, _fmt_ts, _gain_stream,
    _hdr_safe, _hm, _khz, _lab_comp, _lab_db, _lab_dyn, _lab_env, _level_fn, _name_tokens, _noise_loop, _norm_hdr,
    _num, _number_dups, _pf_pick, _pf_tols, _pf_vec, _plan_doc, _run_chunks, _rx_num, _sat_status, _scan_float,
    _scan_step, _scan_tokens, _scan_unit_hint, _seq_audio, _sine, _split_free_line, _svg_hours, _svg_iq_spectrum,
    _svg_multi, _svg_series, _svg_spectrum, _tone_env, _valid, _xml_root, _zone, adjacent_db, age_text,
    alarm_explain, alarm_pcm, alarm_pick, alarm_sounds_norm, alarm_stats, alarms_in_window, analyze_csv, anfr_pick,
    anfr_text, anfr_tnt_sites, anomaly_text, app_sound_seq, apply_overrides, assign_bands, audio_align, audio_gain,
    audio_int16, audio_meter, audio_ref_norm, audio_source_level, audio_source_stats, audio_spec_norm, audio_text,
    auto_gain_pick, auto_rbw, auto_scan_step, auto_thr_help_html, axis_panels, band_clip, band_issue, bb_views,
    bits_dynamic, blend, block_choices, block_overlaps, block_points, build_entries, build_entries_ex, build_plan,
    build_report_html, bundle_pick, busy_lim, busy_pred, calib_candidates, calib_maxhold, calib_offset,
    calib_repeat, capacity_view, caps_text, chan_power, chron_group, classify_signal, clean_colors, cmp_metrics,
    comp_compare, comp_compare_real, comp_curve, comp_report_html, compander_card, compare_receivers,
    compare_spectra, compare_text, compress2, config_public, contrast_text, coord_blockers, coord_docs,
    coord_why_advice, coord_why_text, copy_name, count_overruns, country_bands, country_from_locale, country_uhf,
    coverage_state, coverage_text, covered, data_status, datetime_utc_iso, dbfs_to_unit, decimate_max, decode_text,
    default_view_band, demo_audio, demo_plan_levels, demo_sdr_plan, demod_guess, demod_preset, density_glow,
    density_lut, density_raster, describe_freq, detect_brand, dev_ord, dev_scenes_norm, deviation_db, device_caps,
    devx_norm, diag_short, diff_spectra, diversity_merge, diversity_share, eff_thresholds, expand2, expected_floor,
    expected_obw_khz, ezrf_auto_map, ezrf_dev_key, ezrf_diff, ezrf_entries, ezrf_group_label, ezrf_id,
    ezrf_map_norm, ezrf_planning, ezrf_profile_names, ezrf_remap, ezrf_scene_guess, fav_assign, favs_norm,
    feature_match, festival_cfg_norm, festival_due, festival_text, find_free, find_header, flap_count, floor_curve,
    floor_track, fm_deviation, fmt_audio, fmt_comma, fmt_duration, fmt_freq_mhz, fmt_level, focus_plan,
    freq_digits, freq_list_text, freshness, from_unit, g4_apply, g4_init, gain_steps, gain_to_target, gap_nan,
    gen_commands, geo_km, glossary_find, gonio_points, guard_action, guard_delay, header_kind, heat_arrow,
    heat_dir_color, heat_field, heat_for, heat_freqs, heat_hex, heat_hot, heat_isolines, heat_path, heat_rgb,
    heat_rgba, heat_scale, heat_stops, hex_to_rgb, hint_due, history_norm, home_next, home_status, html_esc,
    hunt_level, hunt_request, hunt_tone, im3_clash, im_class, im_explain, im_formula, im_pairs, im_rules_text,
    im_scan, im_verdict, incident_duration, incident_prune, incident_report_html, incident_slug, input_plan,
    interp_measured, iq_ci8, iq_decode, iq_from_bytes, iq_ring_seconds, is_ezrf_paste, iso_to_epoch,
    journal_csv_rows, json_dumps_compact, keep_text, key_dec, key_enc, lab_align, lab_chain, lab_chain_iq,
    lab_findings, lab_findings_real, lab_modulations, lab_plot_help, lab_session_diff, lab_session_doc,
    lab_session_ok, label_words, layers_recolor, lc_feed, lc_hints, lc_new, lc_summary, lc_text, level_at,
    level_at_many, level_block, level_everywhere, level_everywhere_text, level_words, listen_center, listen_cmd,
    listen_request, listen_windows, log_kind, log_kinds_norm, lora_overlap, lowpass_taps, make_label,
    make_stylesheet, map_auto_place, map_bg_embed, map_bg_extract, map_cfg_norm, map_key, map_scene_monitor,
    map_snap, marker_visible, measure_freq, measure_transfer, measure_transient, merge_scans, meter_ticks,
    mic_health, missing_bands, mk_default, mk_filtered, mk_layer_key, mod_hint, mod_quiz_score, morning_html,
    morning_summary, multi_site, mute_check, name_candidates, name_match, name_rank, net_host_port,
    net_profile_name, net_profiles_merge, net_profiles_norm, net_text, next_free_number, next_mic, next_state,
    noise_floor, noisy_zones, norm_freq, notify_text, notify_wanted, ntfy_request, number_run, obw_khz,
    occupied_width, only_here, palette_color, parse_device_addr, parse_deviceid, parse_dpa_acp, parse_ezrf3,
    parse_ezrf_paste, parse_freq_cell, parse_label, parse_lst4, parse_plan_file, parse_plan_text,
    parse_quick_entry, parse_scan_custom, parse_scan_lines, parse_scan_text, parse_sdb3, parse_sdr_addr,
    parse_shure_cug, parse_wisycom_show, parse_wsm_project, parse_wwb_show, patrol_items, patrol_next, pcm_mono16k,
    pcm_packet, peak_near, perf_view, pf_check, pf_fill, pf_fill_lots, pf_issue_text, pf_orders, pf_suggest,
    phases_norm, phases_table, phosphor_shades, pilot_learn, pilot_verdict, place_parse, plain_btn_text,
    plan_fill_pending, plan_to_text, plan_vrx, planning_active, planning_lines, planning_norm, planning_paused,
    post_mics_norm, post_mics_set, post_watch, prep_dates, prep_html, preset_changes, preset_match,
    preset_value_text, presets_all, privacy_norm, probe_rate, probe_report, probe_seen, problem_card, problem_key,
    quick_names, quick_preset, rbw_combine, rbw_coord_line, rbw_merge, rbw_tag, rbw_text, read_rows, read_show,
    read_user, ready_checks, ready_summary, rec_mb_per_hour, rec_size_text, receiver_addrs, receiver_addrs_text,
    receiver_alerts, reconnect_delay, recurring_events, recurring_text, reg_allowed_pred, reg_detail, reg_issues,
    reg_known, reg_status, reg_summary, reg_tag, rehearsal_check, rehearsal_norm, resample_max, resolution_pairs,
    resource_view, retention_pick, rf_audio_diag, rf_diag_summary, rf_diagnose, rf_linear_text, rf_mode_norm,
    rgb_to_hex, rt_frames, rt_freqs, rt_useful, rx_all, rx_band, rx_custom_dump, rx_custom_norm, rx_from_library,
    rx_help_html, rx_library_find, rx_profile, rx_set_custom, s_meter, safe_filename, sat_level, scales_help_html,
    scan_changes, scan_check, scan_crop, scan_csv, scan_gaps, scan_peaks, scan_segments, scan_step_khz,
    scan_uniform, scan_unit_scale, scan_write, scene_timeline, sched_on, scope_match, screen_plan_fit,
    screen_preset, screen_rf_mode, screens_norm, screens_used, sdr_auto_norm, sdr_bin_hz, sdr_carrier,
    sdr_cfg_extra, sdr_cmd, sdr_compat_rows, sdr_event, sdr_event_row, sdr_floor_dbfs, sdr_gains_for, sdr_in_range,
    sdr_iq_rate, sdr_level, sdr_model, sdr_model_of, sdr_model_text, sdr_models_for, sdr_post_clash,
    sdr_posts_norm, sdr_quality_events, sdr_ranges, sdr_rate, sdr_session_html, sdr_session_row, sdr_span_mhz,
    sdr_tsa_offset, sdr_zones, segment_plan, session_cfg_norm, session_journal_rows, session_name, show_apply,
    show_doc, show_filename, show_summary, show_template, shure_addrs, shure_apply, shure_init, shure_parse,
    shure_split, sigmf_annot, sigmf_info, sigmf_meta, signal_key, signal_report, signal_view, single_band_view,
    site_doc_scene, site_move, site_rename, site_replace, site_report_html, site_scan_doc, site_scan_info,
    site_scans_norm, site_set_hidden, site_visible, sites_for_scope, snapshot_name, sniff_delimiter, snooze_left,
    snr_view, soft_style, sound_cfg_norm, spectrum_info, spectrum_status, spectrum_text, speed_table, split_band,
    split_freq_rows, ssc_apply, ssc_flatten, ssc_init, stair_fit, stair_signal, stair_validity, state_off,
    states_norm, station_norm, store_occupancy, stream_quality, strong_peaks, suggest_labels, suggest_own_thr,
    sweep_line, tech_request, telegram_chats, telegram_request, terrain_request, theme_pal, tinysa_refusal,
    tnt_apply_manual, tnt_cfg_norm, tnt_channel_list, tnt_measure, tnt_near_text, tnt_sites_near, tnt_summary,
    to_stereo, to_unit, tone_pcm, trace_at, tv_channels, tx_cmd, tx_plan, uhf_band_needed, ui_word, unit_hint,
    unit_to_dbfs, unknown_bursts, user_apply, user_doc, user_filename, user_presets_merge, user_presets_norm,
    vfo_center, vfo_inside, vrx_auto, wall_grid, wall_visible, watch_diff, watch_rows, web_link, web_page_lang,
    web_spectrum, web_state, web_views_norm, what_is, what_is_text, wizard_status, wr_pick_ddc,
    wr_snapshot_spectrum, wsm_to_wwb_text, wwb_scan_text, xfer_spectrum, zoom_points,
)


# ====================================================================================================
# 8.1 étape 3 : le reste de l'interface est rangé par thème dans tsm_ui/ (une partie = un fichier), exécuté ICI,
# dans l'ordre, dans l'espace de noms de ce fichier : tout se voit comme avant (tests, réglages remplacés à chaud).
from tsm_ui import load_parts as _load_parts  # noqa: E402
_load_parts(globals())  # ===== PARTIES-ICI


# ====================================================================================================
# Fenêtre principale (8.1 étape 3 : après les parties SDR, dont elle hérite les méthodes)
class MainWindow(FenConstruction, FenConfig, FenAppareils, FenScenes, FenListe, FenSpectre, FenOutils, FenAlarmes,
                 SdrPostsMixin, SdrModeMixin, SdrReceiversMixin, SdrDemoMixin, SdrToolsMixin, SdrFollowMixin,
                 ScreensMixin, LabMixin, QtWidgets.QMainWindow):
    """Fenêtre principale : ses méthodes sont dans tsm_ui/fen_*.py (V7) et tsm_ui/sdr_fenetres.py, labo.py (SDR) ;
    ici, seulement les attributs de classe (bulles d'aide, menus, constantes)."""

    # ------------------------------------------------------------------ aide au survol
    TIPS_ATTR = dict(
        port_combo="Port USB du tinySA (✔ tinySA = reconnu automatiquement). Ferme tinySA-App avant : un seul\n"
                   "logiciel à la fois peut parler au tinySA. ⟳ : relire la liste des ports.\n"
                   "🌐 tinySA en réseau : le tinySA est branché sur un Raspberry Pi (ou un autre PC) qui le partage.",
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
        points_combo="Points par balayage et par bande : plus il y en a, plus c'est fin… et plus c'est long.\n"
                     "⚡ Auto : le meilleur compromis vitesse / lisibilité d'après la largeur totale balayée.",
        zpts_combo="Points du zoom live. « Auto » en met moins quand on zoome (un point tous les ~10 kHz,\n"
                   "290 au plus) : assez fin pour une porteuse de micro, et le balayage reste rapide.",
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

    EXTRA_MENUS = []          # [(titre, [(texte, nom de méthode)])] : sous-menus ajoutés au ☰ Plus (V8 : SDR)

    # 7.68 : actions « sur une fréquence » ajoutées par une autre version (V8 : 🎧 écouter) SANS toucher aux menus :
    # [(texte, nom de méthode)] ; méthode(f MHz, fréquence de la liste ou None). Proposées par clic droit sur une alarme,
    # sur une tuile du mur / du mode Show, et en bouton dans la chasse.
    FREQ_ACTIONS = []

    TIPS_MENU = {
        "🔗 Plan suivi": "Le plan importé avec « Suivre ce fichier » (EazyRF, WWB, WSM, Wisycom, DPA) : à chaque\n"
                        "réenregistrement dans le logiciel,\n"
                               "l'appli propose les fréquences ajoutées, modifiées ou retirées.",
        "📸 États": "Plusieurs plans (artistes, scènes, jours) dans le même show ;\n"
                   "un clic bascule de l'un à l'autre, les fréquences hors de l'état passent en pause.",
        "📖 Manuel": "Le manuel complet (s'ouvre dans ton navigateur, marche hors ligne).",
        "🎤 Appel des micros": "Line check : allume tes émetteurs un par un, chaque fréquence passe ✓ quand son\n"
                               "signal arrive ; résumé « 14 / 16 OK, manquent… » noté au journal (Ctrl+L).",
        "🧮 Vérifier le plan": "Coordination simple : écart entre porteuses et intermod selon des tolérances, un verdict\n"
                               "par fréquence, et une fréquence de remplacement compatible.",
        "🎛 Profils d'appareil": "Filtre récepteur, écart, pas et tolérances par appareil (Wisycom, Shure, Sennheiser…),\n"
                                "et tes profils perso. ❓ explique ce que change le filtre.",
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
        "ℹ À propos": "Version de RF Technical Monitor, du tinySA branché, et où sont la config et les journaux.",
        "🎛 Mode expert": "Affiche tous les réglages (RBW, entrée, LNA, atténuateur, offset, calibration, relais…).",
        "Disposition standard": "Remet les panneaux à leur place d'origine.",
        "Double écran": "Envoie la liste, le journal et le waterfall sur l'autre écran.",
        "📐 Plan de fréquences": "Préparer : vérifier le plan (coordination simple), intermodulation, profils d'appareil,\n"
                                "blocs Spectera / WMAS.",
        "📋 Liste de fréquences": "Nommer, numéroter, vocabulaire, exporter la liste par scène / groupe.",
        "📊 Scans et rapports": "Rapport de show, scans WSM / WWB (référence, conversion, export).",
        "🔗 Connexions": "Alertes téléphone et page web, relais réseau (2ᵉ tinySA), diagnostic.",
        "🎨 Apparence": "Couleurs et thèmes, statuts, mots de la colonne Signal, langue.",
        "🎨 Couleurs": "Thèmes (Pro sombre, Catppuccin, Nord, Daltonien…) et chaque couleur à la main.",
        "🏷 Statuts": "Tes statuts (Libre, En service…) : couleur, « doit rester libre » / « doit émettre ».",
        "🌐 Langue": "Français / English (appliqué au redémarrage).",
        "🪟 Fenêtres": "Panneaux, vraies fenêtres, double écran, dispositions prêtes.",
    }

    TIPS_MENU.update({                              # 7.46 : entrées des 4 menus Préparer / Surveiller / Analyser / Matériel
        "📏 Scan pour la coordination": "Scan fait tout seul pour une coordination : RBW fine (30 kHz conseillé), points calés\n"
                                       "dessus, pics gardés N minutes, puis rangé dans Scans par lieu avec sa RBW.",
        "🖨 Dossier de préparation": "Une fiche à imprimer ou envoyer : plan de fréquences par scène, appareils,\n"
                                     "réglementation, canaux TNT, scans du lieu (avec leur RBW), spectre.",
        "🔁 Perturbations qui reviennent": "D'après les journaux de plusieurs jours : ce qui revient à la même heure\n"
                                           "(talkie tous les soirs vers 19 h, micro qui décroche toujours au même moment).",
        "📦 Tout envoyer pour un dépannage": "Un seul ZIP avec le show, la config (sans jetons ni mots de passe), un\n"
                                              "diagnostic tout frais, les journaux, rapports et diagnostics de la semaine.",
        "🗺 Carte du site": "Tes scènes et tes tinySA sur un canevas : glisse-les, dépose un tinySA sur une scène pour la lui\n"
                            "rattacher, plan du site en fond si tu veux, état en direct, carte de chaleur de la chasse.",
        "🕘 Historique des modifications": "Chaque changement de ta liste (ajout, retrait, fréquence, nom, statut, scène),\n"
                                           "avec l'heure et qui l'a fait (PC ou téléphone). Gardé dans le show.",
        "📸 Comparer avant / après": "Deux scans gardés (avant l'installation des micros / après, ou avant / après un\n"
                                     "changement) : ce qui est apparu, a disparu, est monté ou a baissé.",
        "📱 QR code de la page web": "Un QR code à scanner : l'équipe ouvre la page web sur son téléphone sans taper\n"
                                     "l'adresse (vue au choix : mur, alarmes, régie, Tech…). Imprimable.",
        "🌅 Résumé de la nuit": "Tout le journal en une page : verdict, événements par heure, alarmes regroupées,\n"
                               "fréquences instables ou changées. S'ouvre dans le navigateur.",
        "🧭 Assistant": "Pas à pas pour un nouveau show : le show (pays, lieu), tes micros, le scan du lieu,\n"
                        "les canaux TNT, puis « Prêt pour le show ? ».",
        "📺 Canaux TNT": "Les canaux pris par la TNT, d'après ton scan (sans internet), grisés sur le spectre ;\n"
                         "et les émetteurs TNT proches du lieu (base ouverte de l'ANFR, facultatif).",
        "👤 Profils utilisateur": "Tes préférences (affichage, disposition des fenêtres, couleurs, seuils, alarmes, préréglages perso) dans un\n"
                                 "fichier : à recharger sur n'importe quel PC ou à passer à un collègue.",
        "⚡ Préréglages rapides": "Festival plein air, salle, nuit de surveillance, scan de repérage : règle d'un coup\n"
                                 "les seuils, la mesure, la rémanence et les alarmes (tu vois ce qui change avant).",
        "🔒 Outils de coordination": "Vérifier le plan, coordonner, intermod et profils d'appareil sont cachés :\n"
                                    "⚙ Réglages › Général › « Outils de coordination (avancé) » pour les afficher.",
        "▶ Scanner ici": "Démarre le balayage et remet les pics à zéro : laisse tourner quelques minutes pour voir\n"
                        "ce qui occupe déjà le lieu (télé, autres équipes, brouilleurs).",
        "📍 Scans par lieu": "Un scan gardé par scène / lieu : comparer, fusionner, exporter, rapport d'étude de site.",
        "📡 Ajouter depuis le scan": "Ajoute à ta liste les signaux que le tinySA voit au-dessus d'un seuil.",
        "📥 Importer une liste": "Ton plan de fréquences depuis un fichier (EazyRF, WWB, WSM, Wisycom, DPA, Excel / CSV…).",
        "🆘 Remplacer ce micro": "Le micro choisi (liste ou alarme) est brouillé : 3 fréquences libres et compatibles\n"
                                 "(son appareil, sa bande, tout ton plan), un clic remplace et note au journal.",
        "⌨ Ajouter des micros": "Tape ou colle tes fréquences n'importe comment : « HF1 558.2, HF2 574, IEM 606.5 »,\n"
                                "un message reçu, un tableau. Aperçu avant d'ajouter.",
        "📋 Coller une liste": "Colle des lignes « nom ; MHz » copiées d'un tableur ou d'un autre logiciel.",
        "🪄 Trouver N fréquences": "Coordination simple : l'appli cherche N fréquences compatibles avec ta liste et le\n"
                                  "spectre mesuré.",
        "🎬 Planning": "Qui joue quand, par scène : pas d'alarme ABSENT pendant les changements de plateau.",
        "❓ Doit émettre": "La différence entre « doit émettre » (alarme ABSENT) et « doit rester libre » (alarme CONFLIT).",
        "✅ Prêt pour le show": "Vérifie tout avant d'ouvrir : tinySA, bandes, son, alertes, enregistrement…",
        "▶ Démarrer la surveillance": "Lance la surveillance de tes fréquences (le balayage tourne en continu).",
        "🖥 Mode Show": "Plein écran, seulement l'essentiel en très gros (F10).",
        "🔎 Chasse au brouilleur": "Un bip qui accélère quand tu te rapproches du signal, comme un détecteur de métaux.",
        "🌙 Mode festival": "Nuit complète : reprise après coupure, PC qui ne s'endort pas, bilan chaque matin.",
        "📊 Occupation par heure": "À quelles heures chaque fréquence a été occupée : les créneaux à risque.",
        "📡 Mes tinySA": "Quel tinySA surveille quelle scène ; 👋 Identifier fait clignoter son écran.",
        "➕ Plusieurs tinySA": "Jusqu'à 8 tinySA : adresses (USB ou réseau), noms, corrections de niveau.",
        "🌐 tinySA en réseau": "Les adresses de tes tinySA en réseau (Raspberry Pi, autre PC), avec un bouton Tester.",
        "🎛 Réglages de mesure": "Finesse de mesure (RBW), préampli (LNA), atténuateur, entrée, correction de niveau.",
        "⚖ Calibrer": "Avec plusieurs tinySA sur la même antenne : aligne leurs niveaux sur le 1er.",
        "📡 Mode émission": "Le tinySA devient un petit émetteur (en câble) pour tester un récepteur.",
    })

    SECTIONS_OPEN = dict(detect=True, alarms=True, bands=True, measure=False, dev2=False, country=False)

    home_on = True

    # --------------------------------------------------------------- ports
    NET_ITEM = "__net__"

    BLOCK_WIDTHS = (("Fréquence simple (pas de bloc)", 0.0), ("Bloc 6 MHz", 6.0), ("Bloc 8 MHz", 8.0),
                    ("Autre largeur…", None))

    # ------------------------------------------------------- ↶ annuler / ↷ rétablir (7.32, demande de Clément)
    UNDO_KEYS = ("watch", "scenes", "bands", "statuses")

    coord_on = False

    MK_STYLE = (("full", "Trait sur toute la hauteur"), ("top", "Petit repère discret en haut"))

    SDR_LISTEN_ID = -40                     # étape 7 : « bande » des mesures venues du flux d'écoute / temps réel

    LIB_PATH = CFG_PATH.parent / "appareils_eazyrf.json"


# Ce qui complète la classe une fois créée (sous-menus, actions, raccourcis des modes)
MainWindow.EXTRA_MENUS.append(("📡 SDR (bêta : écoute et moniteur)", [   # V8 : sous-menu (sans toucher au menu V7), ordre d'usage
    ("📡 Mode SDR (panneaux SDR à l'écran)", "rf_mode_sdr"),
    ("📟+📡 Mode combiné (tinySA + SDR)", "rf_mode_both"),
    ("📟 Mode tinySA seul", "rf_mode_tiny"),
    ("📡 Mes SDR (plusieurs, scènes, carte)…", "open_sdr_posts"),
    ("🔌 Premier branchement SDR (assistant)…", "open_sdr_setup"),
    ("🧪 SDR démo (allumer / éteindre)", "toggle_sdr_demo"),
    ("📏 Caler les niveaux du SDR sur le tinySA…", "open_sdr_calib"),
    ("⏪ Remonter le temps (dernières minutes)…", "open_rewind"),
    ("📖 Manuel SDR", "open_sdr_manual"),
    ("📡 Émettre avec un HackRF (en câble)…", "open_sdr_tx"),
    ("🎵 Générateur audio (20 Hz – 20 kHz)…", "open_audio_gen"),
    ("🧪 Labo SDR (RF Compander Lab)…", "open_sdr_lab"),
    ("📋 SDR pris en charge (tableau)…", "open_sdr_compat"),
    ("📡 Moniteur multicanal (tous mes micros d'un coup)…", "open_multimon"),
    ("🎧 Écouter un micro…", "open_listen"),
    ("⏱ Temps réel (un bout de bande, sans trou)…", "open_realtime"),
    ("📦 Rejouer un incident…", "open_incidents"),
    ("📶 Récepteurs en réseau (Shure, Sennheiser…)…", "open_receivers"),
    ("📡 Réglages SDR (mon SDR, sensibilité)…", "open_sdr")]))
MainWindow.TIPS_MENU.update({
        "🧪 Labo SDR": "8.2 : le banc de mesure du SDR : chaîne complète d'un micro HF (son -> compresseur -> FM -> SDR ->\n"
                       "expanseur), comparaison des compandeurs (transfert, transitoires, EQ, phase, rapport), en direct sur\n"
                       "le son reçu (écoute A/B, mesure d'un vrai émetteur), modulations, pannes simulées.",
        "📋 SDR pris en charge": "8.2 : ce que l'appli sait faire avec chaque SDR (balayage, écoute, émission, dBm) et ce qui\n"
                                "a été essayé en vrai.",
        "🧪 SDR démo": "V8 : pas de SDR ? L'appli fabrique les signaux de tes micros (son, pilote, brouilleur qui passe,\n"
                       "micro qui s'éteint) : tout le poste SDR marche, écoute comprise.",
        "🔌 Premier branchement SDR": "V8 : choisir son SDR, le trouver, régler le gain tout seul, écouter un micro,\n"
                                     "caler les niveaux, et un diagnostic à envoyer si ça coince.",
        "📏 Caler les niveaux du SDR": "V8 : compare les mêmes signaux vus par le tinySA et le SDR : niveaux du SDR en vrais dBm.",
        "⏪ Remonter le temps": "V8 : les dernières minutes du poste SDR (waterfall + son) : réécouter un passage, le garder.",
        "📖 Manuel SDR": "V8 : le manuel du poste SDR (écoute, surveillance, démo, émission, calibration…).",
        "🎵 Générateur audio": "V8 : une fréquence de 20 Hz à 20 kHz, un balayage, du bruit, les sons de l'appli ou ton\n"
                              "WAV, joués sur la sortie audio de l'appli (et utilisables pour l'émission / le SDR démo).",
        "📡 Émettre avec un HackRF": "V8 : faux micros FM, porteuses, brouilleur intermittent émis par un HackRF, EN CÂBLE\n"
                                    "avec un atténuateur (tester un récepteur, l'intermod, s'entraîner à la chasse).",
        "⏱ Temps réel": "V8 : une fenêtre fixe (jusqu'à ~15 MHz sur un HackRF) vue SANS TROU : max-hold,\n"
                         "persistance, waterfall, journal des signaux brefs, clic = écouter.",
        "🎧 Écouter": "V8 : démodule une ou plusieurs fréquences proches avec un HackRF / RTL-SDR (FM, AM),\n"
                     "niveau de chaque canal, expanseur 2:1 (approximation des companders).",
        "📡 Réglages SDR": "V8 : HackRF One / RTL-SDR à la place (ou en plus) d'un tinySA : dossier des outils\n"
                          "(hackrf_sweep, rtl_power), gains, et comment les installer.",
        "📡 SDR": "V8 : réglages SDR, écoute (démodulation) et temps réel avec un HackRF / RTL-SDR.",
        "📶 Récepteurs en réseau": "V8 : niveau RF, antenne A / B, diversity, son, pile et alertes de tes récepteurs en\n"
                                   "réseau (Shure, Sennheiser), reliés à ta liste ; comparés au SDR dans le moniteur.",
        "📡 Mes SDR": "V8 : plusieurs SDR en même temps que les tinySA, chacun ses scènes et ses panneaux, placés sur la\n"
                     "carte comme les tinySA (glisser un SDR sur une scène = il la surveille).",
        "📡 Mode SDR": "V8 : le SDR à l'écran (récepteur, spectre, waterfall, mes micros) à la place du spectre tinySA.\n"
                       "Tous les panneaux se déplacent, s'empilent, se détachent ; ta disposition est retenue.",
        "📟+📡 Mode combiné": "V8 : tinySA et SDR ensemble, les deux spectres côte à côte.",
        "📟 Mode tinySA": "V8 : la disposition tinySA seule (les panneaux SDR sont rangés, le SDR s'arrête).",
        "📦 Rejouer un incident": "V8 : choisis un dossier d'incident du moniteur multicanal : son rapport s'ouvre et\n"
                                  "son IQ est rejoué dans le temps réel (écouter, revoir le spectre).",
        "📡 Moniteur multicanal": "V8 : tous tes micros de la fenêtre du SDR mesurés en même temps (niveau, voisins,\n"
                                 "largeur) ; les plus importants démodulés (son, déviation, dérive, coupures).",
})
for _k, _t in RF_MODES:
    setattr(MainWindow, f"rf_mode_{_k}", (lambda k: lambda self: self.set_rf_mode(k))(_k))
MainWindow.FREQ_ACTIONS += [("🎧 Écouter avec le SDR", "listen_freq"), ("🔎 C'est quoi ce signal ? (SDR)", "analyze_freq"),
                             ("⏱ Temps réel autour (SDR)", "rt_freq")]


if __name__ == "__main__":
    main()
