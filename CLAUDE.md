# TinySA Monitor — contexte pour Claude Code

Application Windows (un seul fichier : `tinysa_monitor.py`, ~7 600 lignes) pour tinySA Ultra : spectre en direct +
monitoring de 100+ fréquences, pensée pour la coordination HF en festival. Version courante : **7.2.1**.
Stack : Python 3.12/3.13, PySide6, pyqtgraph, numpy, pyserial. Compilée en .exe avec PyInstaller (`build.bat` ou le
workflow GitHub Actions `.github/workflows/build-exe.yml`).

## Qui / comment répondre
L'utilisateur (Clément) est technicien son/HF/AV en festivals (utilise EazyRF, WWB, WSM). Il parle un français
décontracté : réponds en français, ton détendu mais précis, concret et actionnable.
**Dis toujours ce qui n'est pas vérifié** : l'interface Qt réelle est lancée par `tests/gui_reel.py` (Linux offscreen
en local, vrai Windows dans la CI) ; ni le vrai tinySA, ni les sons, ni un vrai double écran n'ont été testés par Claude.

## Exe et CI
`.github/workflows/build-exe.yml` (windows-latest), à chaque push sur n'importe quelle branche : tests, `gui_reel.py`
en vrai rendu Windows (non bloquant ; résultat OK/FAIL remonté en **annotations** du run), PyInstaller → artefact
`TinySA-Monitor` (l'exe) et `captures-interface-windows`. Publication automatique : push sur une branche ≠ main →
pré-release `test-<branche>` remplacée à chaque push ; push sur main → release `v<APP_VER>` (une fois par version :
monter `APP_VER` pour publier). Un tag `v*` poussé à la main attache aussi l'exe. Le proxy du conteneur Claude
interdit de pousser des tags / créer des releases : passer par le workflow. Dépôt **privé** : téléchargement réservé
aux comptes qui y ont accès.
Depuis le conteneur Claude, `gh run view <id>` montre les annotations, mais les journaux et artefacts (stockage Azure)
sont bloqués par le proxy. Sous Windows, **ne pas** lancer Qt en `offscreen` : il n'y a aucune police (mesures ×2).

## Organisation du fichier
- En-tête + constantes, puis la section **PURE** entre `# ===== PURE-BEGIN` et `# ===== PURE-END` : tout le code
  sans interface (formats de scan WSM/WWB, `AlarmBook`, `SweepStore`, intermodulation `im_scan`/`im_pairs`,
  occupation, seuils, export de listes, rapport HTML…). Les tests exécutent cette section seule.
- Ensuite les classes Qt : `TinySA` (série), `ScanWorker` (QThread), dialogues (`StatusDialog`, `ImportDialog`,
  `QuickNameDialog`, `IntermodDialog`, `RescueDialog`, `ReplayDialog`, `ReportDialog`, `ExportListDialog`…),
  `SweepRecorder`, `WallWindow`, puis `MainWindow` (le gros morceau), `main()`.
- Mettre tout nouveau code « sans GUI » dans la section PURE (et le tester) ; la section est exécutée par les tests
  avec un espace de noms restreint (`itertools, re, csv, io, math, np, unicodedata, bisect, deque, MIN_PTS, HYST,
  RBW_LIST`) : n'y ajoute pas de dépendance à Qt ni à d'autres globales sans mettre à jour les tests.

## Modèles de données à connaître
- Fréquence surveillée (`self.watch`) : dict `name, freq, status, thr, scene, group, level, max, state
  (None|free|weak|occ), t_acc, occw, peak, since, free_since, absent`.
- Statuts (`self.statuses`) : `name, color, free` (doit rester libre → CONFLIT) et `on` (doit émettre → ABSENT).
- Couches : `self.scenes = [{name, color, groups:[{name, color, prio}]}]`, `prio` 2 critique / 1 normale / 0 info.
- Alarmes : `AlarmBook`, clés `("CONFLIT"|"ABSENT", int(round(freq*1000)))` ; l'acquittement coupe le son mais garde
  l'alarme ; les critiques rejouent le son toutes les 10 s (`_alarm_tick`, timer 1 s).
- Relecture : `SweepStore` (tampon mémoire 30 min) + `SweepRecorder` (tranches `.npz` compressées float16 dans
  `<dossier journaux>/enregistrements/<date>/`, 2 Go max).
- Deux tinySA : `self.dev2 = {on, addr, offset}` (adresse USB « COM4 » ou réseau « 192.168.1.20:5025 », lue par
  `parse_device_addr`) ; bande `dev` None (auto) / 0 / 1 ; `band_devices()` → `assign_bands` (équilibre en points,
  repli sur l'appareil vivant) ; `get_cfg(dev)` ne donne à chaque worker que ses bandes (zoom : un seul appareil).
  `self.workers` (un `ScanWorker` par appareil, `self.worker` = le 1er), `is_running()`. `ScanWorker.link(bool)`
  → `on_link` : `dev_live`, alarme `("APPAREIL", -(n+1))` (prio 2, en tête, ignorée par le nettoyage du tick).
  Le worker réessaie toutes les `RETRY_S` s ; échec de la 1re connexion = `error` sauf `retry_first` (le 2ᵉ).
- Réseau : `TinySA` ouvre tout par `serial.serial_for_url` (`socket://hôte:port`) ; délai de silence `idle`
  (`NET_IDLE_MIN` + points × f(RBW), `expect_scan`), en réseau ET en USB, pour détecter un câble arraché ou un tinySA
  figé (→ link False, reconnexion). `TinySA.abort` = `isInterruptionRequested` : « Arrêter » coupe la commande en
  cours (`Aborted`) ; au-delà de `STOP_FORCE_MS`, `_force_stop` ferme les ports (`ScanWorker.force_close`).
- Zoom live borné à `_band_extent()` (étendue des bandes) : dézoomer ne fait plus scanner hors des bandes. `SerialRelay` (thread,
  sans Qt) + `RelayWindow` : `TinySA-Monitor.exe --relais` sur le PC du 2ᵉ tinySA, port TCP 5025 (`RELAY_PORT`).
- Noms de position `self.dev_names` (`dev_name(d)`), `band_src` (bande → appareil du dernier balayage) →
  `seen_by(f)` « vu par … » (note du journal, info des alarmes CONFLIT). Zoom : l'autre appareil garde les bandes.
- Calibration : `start_calib` → `self._calib`, `get_cfg` donne la même bande aux deux sous `CALIB_IDS` (-3, -4),
  `on_sweep` les détourne vers `_calib_add` ; `calib_offset` (PURE, signaux vus par les deux, sinon plancher).
- Alertes : `notify_cfg` (ntfy / Telegram, `notify_text`, `ntfy_request`, `telegram_request` en PURE) ; `Notifier`
  (file + fil, 3 essais) ; `_notify_new_alarms` dans `_alarm_tick` (une fois par alarme, `_notified`). `notify` est
  dans config.json mais PAS dans les profils (jeton). Page web : `web_cfg`, `WebServer` (`/`, `/etat.json`),
  `web_json()` rafraîchi chaque seconde, page `WEB_PAGE` + `web_state` (PURE). Dialogue `AlertsDialog`.
- Repères : `self.mk` (`mk_default`, `marker_visible`, `mk_filtered` en PURE : on, states, hide_layers, hide_status,
  alarms, unk, style full|top) ; `w["hide_mk"]` (clic droit) ; menu `mk_menu` reconstruit à chaque ouverture
  (`_build_mk_menu`) ; `names_chk` / `mark_combo` gardés comme modèles (config) mais hors de la barre ; Ctrl+M.
- Blocs larges (Spectera / WMAS) : `w["bw"]` MHz (0 = fréquence simple). Niveau `level_block` (médiane, ou max si
  « doit rester libre »), `block_choices(tv)`, `block_points` (scan ciblé, bandes depuis la liste),
  `block_overlaps` (« ⚠ dans le bloc »). Démo : `demo_blocks` → plateau. IM : calcul sur le centre seulement.
- Shows (🎪) : fichier `.tsashow` = `show_doc` (PURE) {meta (SHOW_META), show (clés SHOW_KEYS seulement), ref} ;
  `read_show` lit aussi les anciens profils .json ; ouverture = `show_apply(config complète actuelle, doc)` → les
  préférences ne bougent pas. `show_meta`, `show_path`, `recent_shows` dans config.json (pas dans les shows).
  `SHOW_DIR` = Documents/TinySA Monitor/Shows. Dialogues `ShowInfoDialog`, `ShowOpenDialog`. Ctrl+S.
- Robustesse : `_save_config` atomique (tmp + os.replace, ancienne version en `.json.bak`, relue si config abîmée),
  sauvegarde auto toutes les `AUTOSAVE_MS` ; `install_crash_log` (sys / threading.excepthook + faulthandler →
  `crash.log`, message au plus 1/min) ; `install_french` charge `qtbase_fr` (aussi embarqué par PyInstaller
  `--add-data`) : sans lui, Oui / Non / Annuler s'affichent en anglais.
- Sens du signal : `signal_view(state, keep_free, keep_on, absent)` (PURE) → texte + ton ok|bad|warn|none ;
  `sig_view(w)` / `tone_color` utilisés par la liste, le mur, les repères (« état du signal ») et la page web
  (`tone`). Doit émettre + signal = « OK » vert (demande de Clément : occupé rouge = « pas de place ici »).
- Mots : `SIGNAL_LABELS` / `SIGNAL_DEFAULTS`, `signal_key` → `signal_view(..., intermod, labels)` ;
  `self.sig_labels` (⚠ `self.labels` est la liste des TextItem du spectre !), dialogue `LabelsDialog`.
  INTERMOD : `im_cause(w, f_at)` au passage en occupé d'une « doit rester libre » (pic mesuré pour un bloc),
  `w["im"]` = formule ; alarme de clé CONFLIT mais `kind` INTERMOD.
- Unités : `to_unit` / `from_unit` / `fmt_level` (PURE, dbm | dbuv | pct WSM) ; `self.unit`, `set_unit` ;
  `LevelSpin` (value() en dBm, affichage / saisie dans l'unité) pour thr / weak / strong ; `LevelAxis` (axe gauche) ;
  `self.lvl()` pour liste, mur, alarmes, journal (affichage ; le CSV reste en dBm), curseur, page web (`level_txt`).
- Alerte TROP FORT : `strong_chk` / `strong_spin` (Détection, visible en mode simple, dans SHOW_KEYS),
  `check_strong` (après chaque balayage, `strong_peaks` PURE), clés `("FORT", MHz)` (prio 2, hystérésis 3 dB,
  ignorées par le nettoyage du tick), `strong_line` violette.
- Mur : panneau `dock_wall` (onglet du spectre) contenant `WallWindow`. Plein écran = `wall_fullscreen` : le mur
  passe dans une vraie fenêtre `WallFullWindow` puis revient dans le dock (un dock flottant refuse souvent le plein
  écran : type « outil »). Tuiles : `wall_visible` (PURE) + `w["hide_wall"]`, `set_wall_rows`, `pick_wall` /
  `WallPickDialog`, case « Alarmes toujours visibles » (`in_alarm`).
- Aide : `TIPS_ATTR` / `TIPS_TEXT` / `TIPS_MENU` + `_install_tips` (bulles + statusTip) ; gui_reel échoue si un
  contrôle visible n'a pas de bulle.
- Config : `%APPDATA%/TinySAMonitor/config.json` (`_collect_config` / `_apply_config`, avec migration des anciennes configs).

## Formats de fichiers
- Export de scan **Sennheiser WSM** : CSV `;`, 6 lignes de métadonnées, en-tête à la ligne 7
  (`Frequency;RF level (%);RF level;Memory (%);…`), fréquence en kHz, niveau en % (0 % = −120 dBm, 100 % = 0 dBm),
  ~13 lignes de pied de page. Référence : https://github.com/nikharju/WSM-WWB-csv-converter (MIT).
- Import de scan **Shure WWB** : lignes `470.000, -98` (MHz à 3 décimales, virgule + espace, dBm entier, sans en-tête).
- Les formats « EazyRF / WWB / WSM » pour l'**export de listes de fréquences** sont des suppositions génériques :
  demander à Clément un vrai fichier d'import avant de les « corriger ».

## Tests (`tests/`, à lancer depuis la racine du dépôt)
```
python tests/test_v7.py ; python tests/test_im.py ; python tests/test_plan.py     # logique pure
python tests/smoke_test.py ; ...smoke_test2.py ; ...smoke_test3.py ; ...smoke_test4.py   # GUI simulée
python tests/smoke_test5.py      # 2e tinySA dans MainWindow (faux Qt)
python tests/smoke_test6.py      # shows, config sûre / copie de secours, crash.log (faux Qt)
python tests/test_reseau.py      # faux tinySA (pty) → relais → TCP → TinySA ; test_reseau_qt.py : vrai ScanWorker,
                                 # coupure, liaison muette, reconnexion (Linux/macOS ; sautés sous Windows)
python tests/test_alertes.py     # ntfy / Telegram / Notifier / WebServer ; page testée dans Chromium si Playwright
python tests/check_names.py      # noms non définis (les « hérités de Qt » sont normaux)
python tests/gui_reel.py         # VRAI PySide6 hors écran, mode démo : captures PNG dans tests/captures/
```
Chaque script affiche `ÉCHECS: 0` quand tout va bien. Les `smoke_test*` utilisent `tests/fakeqt.py`, un **faux Qt**
(classes « fourre-tout ») : ils vérifient la logique de `MainWindow` et des dialogues, **pas** le rendu ni le comportement
réel de Qt. `gui_reel.py` complète : il lance la vraie fenêtre (offscreen), fait tourner le mode démo, ouvre
dispositions, dialogues, relecture, mur, imports WSM/WWB, rapport, relance avec la config, vérifie la taille minimale
(≤ 1280 × 700) et l'absence d'exception ; **regarder les captures** après une modif d'interface. Sous Linux il faut
`pip install PySide6 pyqtgraph pyserial numpy` et `apt install libegl1 libgl1 libxkbcommon0 fonts-noto-color-emoji`.
Restent à vérifier sur Windows : sons (`QApplication.beep`), vrai port série, double écran, rendu natif, exe PyInstaller.

## Pièges connus
- Barre du haut = `QToolBar` `cmd_bar` (Port, Démarrer, Shows, 🔔, ☰ Plus → `more_menu` : Outils, Fenêtres, Mur,
  Couleurs, Statuts, Mode expert) sur toute la largeur. NE PAS la remettre dans une zone entre les docks : une
  rangée qui se replie y est coupée par Qt (bouton Démarrer invisible à 1280 px, vu en v7.2 dev).
- Pas de zone centrale : widget central vide (0×0) ; le **spectre est un dock** (`dock_spec`, zone du bas, au-dessus
  du waterfall et des alarmes) ; coins inférieurs donnés aux zones gauche / droite (`setCorner`) sinon la zone du
  bas passe sous les colonnes et la hauteur mini explose. `_dock_sizes` proportionnel à la largeur.
- Mode simple / expert : `self.expert`, `set_expert` (`_expert_rows` = (QFormLayout, widget) → `setRowVisible`,
  `ref_row`, `persist_combo`) ; sections repliables `_section(key, box)`, `sections_open` (config). Les seuils
  occupé / faible / TX absent restent visibles en mode simple (demande de Clément).
- `MainWindow._flow(...)` (`FlowLayout`) : rangées qui se replient (ligne « Vue » du spectre).
- Textes repliés (`setWordWrap`) dans un `QSplitter` : leur réserver une hauteur mini, sinon ils se chevauchent.
- `&` dans un titre de dock ou d'onglet = raccourci clavier Qt (il disparaît) : écrire « et ».
- PySide6 : énumérations qualifiées complètes (`Qt.ItemDataRole.UserRole`, etc.).
- Les signaux `clicked` / `triggered` passent un booléen `checked` : connecter avec `lambda *_: methode()` quand la
  méthode a des paramètres optionnels.
- **Jamais `lambda checked=False: …` sur triggered / toggled / clicked** : PySide6 appelle alors la lambda SANS
  argument (checked vaut toujours False → impossible de recocher à la souris, bug v7.1 du menu Repères). Lire l'état
  avec `lambda *_, a=a: f(a.isChecked())`. Garde-fou dans test_v7 ; gui_reel clique chaque case dans les 2 sens.
- Dans les tests, un balayage doit contenir de l'énergie aux fréquences testées : `on_sweep` recalcule tous les états.
- Modifications du gros fichier : patchs « remplacer exactement une occurrence » (échouer si 0 ou 2 correspondances),
  puis `python -m py_compile tinysa_monitor.py`, les tests, et ne jamais committer `__pycache__`.

## Reste à faire / idées
- **Deuxième tinySA** : fait (USB + réseau, bascule auto). Testé avec un faux tinySA ; **jamais avec deux vrais
  tinySA** ni un vrai réseau de festival. À vérifier : délai `expect_scan` avec RBW étroit, Wi-Fi.
- Alertes ntfy / Telegram testées avec un faux serveur local : **pas d'envoi réel** vérifié vers ntfy.sh / Telegram.
- Interface validée en vrai Qt (Linux + Windows CI : ≤ 1280 × 700). **Retour terrain de Clément : 1 tinySA réel,
  2 h sans souci** (version de test d'octobre 2026). Restent : 2 tinySA réels, relais, sons, nuit complète.
- Ajouter les vrais formats d'import EazyRF / WWB / WSM dès que Clément fournit des exemples.
- Spectera : faits issus de la doc / presse Sennheiser (6 / 8 MHz, 2 canaux larges par base, plages UHF / 1G4) ;
  **jamais mesuré** un vrai porteur Spectera au tinySA (niveau du plateau selon RBW, seuil à régler).
- Idée : IM des blocs larges (produits en bandes), import d'un plan Spectera (WSM / Spectera Control).
