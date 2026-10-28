# TinySA Monitor — contexte pour Claude Code

Application Windows (un seul fichier : `tinysa_monitor.py`, ~7 600 lignes) pour tinySA Ultra : spectre en direct +
monitoring de 100+ fréquences, pensée pour la coordination HF en festival. Version courante : **7.8.0** (stable, branche `ui-validation` → main) ; **V8 en cours sur la branche `v8-sdr`**
(`APP_VER = "8.0-dev"`, pré-release `test-v8-sdr` seulement : ne PAS fusionner dans main avant le feu vert de Clément).
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
  `block_overlaps` (« ⚠ dans le bloc »). Démo : `demo_blocks` → plateau. IM des blocs : `im_scan(..., bws, tbws)` → produits en bandes
  (demi-largeur `hw` = Σ|coef|·bw/2, `gap` bord à bord).
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
  Ton `free` (libre, bleu `LIBRE_COLOR`) distinct de `ok` (mon émetteur est là) — demande de Clément 7.4.2.
  Couleur par situation : `self.sig_colors` (config `sig_colors`, `clean_colors`), défaut = `tone_color(SIGNAL_TONES[k])` ;
  `sig_view` → (texte, ton, couleur) ; la page web reçoit `color` par ligne.
- Mots : `SIGNAL_LABELS` / `SIGNAL_DEFAULTS`, `signal_key` → `signal_view(..., intermod, labels)` ;
  `self.sig_labels` (⚠ `self.labels` est la liste des TextItem du spectre !), dialogue `LabelsDialog` (mots + couleurs).
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
  `WallPickDialog`, case « Alarmes toujours visibles » (`in_alarm`). Barre du mur en `FlowLayout` (avant : 929 px
  de large mini, impossible à réduire) ; tuiles dans un `QScrollArea`, taille `size_combo` (`wall_grid` /
  `WALL_TILE` en PURE, `wall_size` dans config.json) : auto = remplit, s / m / l = hauteur fixe + défilement.
  Bouton « 🗗 Détacher / 📌 Raccrocher » (`wall_detach`) : en onglet du spectre, le mur ne peut pas être petit à
  côté d'un grand spectre ; détaché, il se redimensionne librement (demande de Clément, comme l'ancienne fenêtre).
  Plein écran : `self.wall.show()` après l'avoir mis dans `WallFullWindow` (sinon écran noir, 7.6.0) ; écran = celui
  où est le mur. `wall_window_other_screen` (bouton « 🖥 Autre écran » si 2 écrans, menu Fenêtres) : fenêtre sur
  l'autre écran.
- Intermod : tolérances par type de produit (`im_class` : 2tx3 / 3tx3 / 5 / 7, `IM_TOL_PRESETS`, défaut EazyRF
  100 / 50 kHz d'après ses guides V3.75 / V4.00 ; 5ᵉ / 7ᵉ = notre choix). `guard` de `im_scan` = float ou dict.
  Les « doit rester libre » ne sont pas des émetteurs. Niveau « mesuré » masqué quand la cible est un « doit émettre »
  qui émet (on mesurerait sa porteuse). Clément trouvait l'ancien calcul (±300 kHz partout) « tout faux » face à
  Wisycom Manager : **demander sa liste Wisycom pour comparer** avant de toucher encore aux règles.
  Verdict « calcul seul · rien mesuré » (avant « à risque ») : le calcul dit que ça tombe dessus, le niveau mesuré
  est sous les seuils ; seules les combinaisons qui tombent dans la tolérance sont listées (message en tête).
  Gravité `im_verdict` (PURE) : 🔴 mesuré ≥ seuil occupé, 🟠 ≥ seuil faible, 🟡 IM3 2 TX non mesuré, ⚪ le reste ;
  triées du plus grave au moins grave (`sev`). Tolérance 0 (dict) = type ignoré, comme EazyRF ; préréglage
  « 2A − B seulement ». Sur le plan de Clément (558/574/606/614/646/478) : propre en 2A − B seul, conflits en
  A + B − C et IM5 pile dessus → EazyRF / Wisycom ne comptent probablement pas ces produits (non vérifié).
- Vérifier le plan (🧮, Outils, `PlanCheckDialog`, demande de Clément « comme EazyRF ») : PURE `pf_check` (écart entre
  porteuses `PF_SEP` bord à bord + intermod des émetteurs selon tolérances ; réserves protégées sans émettre ;
  produits larges → toutes les fréquences recouvertes), `pf_issue_text`, `pf_suggest` (pré-filtre vectorisé :
  écart, produits des autres sur la candidate, 3ᵉ ordre impliquant la candidate ; puis `pf_check` exact ;
  « aucun nouveau problème pour les autres »), `pf_orders` (3 et 5 seulement : le 7ᵉ = 200 M combinaisons à
  30 TX → « trop gros » silencieux avant). « Remplacer »
  → `MainWindow.set_watch_freq` + journal « NOUVELLE FRÉQUENCE ». Corrigé au passage : `im_scan.near_t` choisit
  la cible la plus proche qui n'est pas un émetteur du produit (un produit large était jeté s'il touchait d'abord
  un de ses émetteurs).
- **Règles d'intermod (7.7.0, demande de Clément : « on comprend pas »)** : `IM_TOL_PRESETS` = (nom, tolérances,
  explication) : 🟢 Standard (2A − B ±100 kHz, PAR DÉFAUT — le plan Wisycom validé par EazyRF passe), 🟡 3ᵉ ordre
  complet (+ A + B − C ±50), 🟠 Prudent (+ 5ᵉ), 🔴 Très prudent ; `IM_TOL_CUSTOM` « ✏ Personnalisé » (choisi tout
  seul si on touche une tolérance) ; `fill_rules_combo` (Qt), `im_rules_text` (PURE, phrase « On vérifie : … »).
  `pf_check` / `pf_suggest` : `max_tx` déduit des tolérances. Résumé de la vérification par type de problème.
- **Filtre récepteur (7.8.0)** : le plan Wisycom de Clément (470.2 471.3 478 558 574 606 614 646 660.95 661.45)
  donne « 0 IM » dans EazyRF avec son profil MRK980 : 2 TX 100, 3 TX 50, Séparation 500, **Filtre 32 MHz**, Incrément
  0,005 (MTK952 : 0,025). Interprétation (déduite, pas lue dans une doc EazyRF) : un produit ne gêne une fréquence que
  si TOUS ses émetteurs sont à ± filtre / 2 d'elle → avec ça, 0 problème comme EazyRF ; sans filtre : des A + B − C.
  `pf_check(..., filt)`, `pf_suggest(..., step, filt)` (pré-filtre cohérent, test « rapide = brute » avec filtre),
  IntermodDialog `filt_spin` (cible connue seulement). Préréglage 1 = « 🟢 Comme EazyRF (2 TX ±100 · 3 TX ±50) »,
  puis « ⚪ Simple » (2A − B). `self.plan_opts = {sep kHz, filt MHz, step kHz}` dans config.json.
  Diagnostic auto (liaison perdue / erreur) : plus de `QTimer.singleShot(0, lambda)` (crash.log 7.6.2 « access
  violation » dans `dump_diag`) → `self._diag_pending`, écrit par `_alarm_tick` dans un try.
- Appel des micros : `LineCheckDialog` (non modal, `self._linecheck`, nourri par `on_sweep`, force `detect_unknown`),
  PURE `lc_new` / `lc_feed` / `lc_summary` / `lc_hints` (inconnu à ±3 MHz d'une manquante) / `lc_text` ; Ctrl+L.
- Page web v2 (« façon Ontime », demande de Clément) : `WEB_PAGE` (r-string, `__VIEWS__` / `__ICON__` remplacés),
  routes `#/liste` `#/mur` `#/spectre` `#/waterfall` `#/alarmes` + accueil ; `WEB_VIEWS` / `web_views_norm` ;
  `web_cfg = {on, port, pin, password, views}` (pin et password jamais dans la config partagée) ; `WebServer` :
  `/etat.json` = {me, password, views, ack, state}, `/spectre.json` (`web_spectrum` : max par paquet, ≤ 900 pts,
  préparé par `web_spec_json` seulement si quelqu'un regarde), `POST /connexion` (cookie `tsm`, `ClientBook`,
  `login_guard`), `POST /acquitter` (PIN, `PinGuard`, file `_web_acks`). Liste des connectés dans `AlertsDialog`
  (`refresh_clients`, « Déconnecter tout le monde » = `revoke_all`, « Renommer » = `rename`, « 👋 Identifier » =
  `identify` → `ident` dans /etat.json → écran du client qui clignote 8 s). Waterfall rempli côté navigateur (vue ouverte).
  Piège corrigé en 7.4.1 : `showLogin` ne doit pas réécrire le champ nom s'il est déjà affiché (tick chaque seconde).
  7.4.3 : la liste des connectés est reconstruite toutes les 2 s → le choix est retenu dans `_sel_tok`
  (`itemSelectionChanged`, signaux bloqués pendant la reconstruction). Le client change son nom par
  `POST /renommer` (même session) ; `editing` empêche le tick de refermer l'écran de saisie.
- Icône : `assets/icone.png` / `.ico` (parabole Noto Color Emoji, Apache 2.0), `--icon` + `--add-data` PyInstaller,
  `app.setWindowIcon` dans `main()`, favicon `APP_ICON_PNG64`.
- Statut au clavier (liste) : Ctrl+1…9 = statut n° 1…9 (ordre de `self.statuses`), Ctrl+0 = aucun, Ctrl+E = 1er
  « doit émettre » → `quick_status`. Alertes : bouton « 📖 Tuto » (`TUTO_ALERTES`, PURE) et « 🔎 Trouver mon chat id »
  (`getUpdates` → `telegram_chats`, PURE). Intermod : colonne Origine = noms = chiffres, Ordre = « IM3 · 3 TX ».
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
- Pas de zone centrale : widget central vide de hauteur 0 (**surtout pas `setMaximumSize(0, 0)`** : la largeur
  bloquée à 0 fige la colonne du milieu, `resizeDocks` n'a plus d'effet et le spectre reste minuscule — v7.2.1) ; le **spectre est un dock** (`dock_spec`, zone du bas, au-dessus
  du waterfall et des alarmes) ; coins inférieurs donnés aux zones gauche / droite (`setCorner`) sinon la zone du
  bas passe sous les colonnes et la hauteur mini explose. `_dock_sizes` (appelé ~120 ms après le 1er affichage, quand la fenêtre a sa vraie taille) : réglages ~19 %,
  liste ~31 %, le reste au spectre ; `_middle_sizes` : waterfall ~28 % et alarmes ~170 px en bandeaux sous le
  spectre (aussi quand ils apparaissent). `LAYOUT_VER` : une disposition enregistrée plus ancienne est ignorée.
  Largeurs mini réduites (réglages 230, liste ~290 : boutons courts / rétrécissables) pour pouvoir agrandir le spectre.
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
- **Ramasse-miettes dans le fil de l'interface** (`install_gc_main_thread`, appelé dans `main()` et par gui_reel) :
  `gc.disable()` + minuteur 500 ms. Sans ça (Python 3.12), le GC tourne dans le fil `ScanWorker` et détruit des
  objets Qt de l'interface → « access violation » (crash.log de Clément 7.4.2 en changeant le nombre de points).
  Ne jamais réactiver `gc` automatique.
- `TinySA.expect_scan(points, rbw, step_khz)` : en RBW auto, délai de silence calculé avec `auto_rbw(pas)` (avant :
  0,05 s / point fixe → tinySA déclaré « muet » à tort avec beaucoup de points). Après 3 reconnexions ratées, le
  message conseille de débrancher / rebrancher le tinySA (il peut figer au bout d'un moment, aussi avec tinySA-App).
- **tinySA Ultra = une seule prise** : `input_plan` (PURE) → en Auto, toujours « mode low input » sur un Ultra
  (7.5.0 envoyait « mode high input » au-delà de 800 MHz → tinySA bancal ; 7.5.1 n'envoyait plus RIEN → un Ultra
  resté en « high » ne revenait jamais : plus aucune bande ne scannait, retour de Clément → corrigé 7.6.2) ;
  « ultra on » une fois au-delà de 800 MHz (`ScanWorker.ultra`, détecté par « tinysa4 » dans `version`).
  Commande « ultra on » **non vérifiée sur un vrai Ultra** (si refusée : ignorée).
- Vue « Toutes les bandes » : `update_plot` ne trace que les bandes cochées ; `_bands_changed` oublie les données
  des bandes décochées / supprimées (avant : ancienne et nouvelle bande mélangées jusqu'à la fin d'un cycle).
- **Diagnostic tinySA** : `TinySA(port, baud, trace)` note chaque commande / réponse / erreur ; `ScanWorker.trace`
  (deque 800) ; `MainWindow.dump_diag` → `<journaux>/diagnostic/diagnostic_tinysa_*.txt` (versions, réglages,
  bandes, échanges), automatique sur liaison perdue / erreur (1 / min), menu Outils › 🩺. **Le demander à Clément**
  pour tout bug avec le vrai tinySA (bandes qui « plantent » après 7.5.1 : cause non trouvée en démo).
- Vitesse série `baud_combo` (expert, config `baud`, 115200) : ignorée en USB (CDC), utile sur un vrai port série.
- Convertisseur de scans `ScanConvertDialog` (Outils › 🔁) : entrée auto (`parse_scan_text`) ou CSV personnalisé
  (`parse_scan_custom` : séparateur, colonnes, unités, lignes sautées), ou scan en cours ; sortie `scan_write`
  (wwb, wsm — format supposé —, csv : séparateur, décimale, unités, en-tête). Remplace « WSM → WWB » et
  « Exporter le scan au format WWB » dans le menu (`convert_wsm_wwb` / `export_scan_wwb` restent, testés).
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
- Idée : import d'un plan Spectera (WSM / Spectera Control).
- **Plus tard (demande de Clément, pas maintenant)** : d'autres appareils de mesure que le tinySA (SDR type RTL-SDR /
  HackRF / Airspy, autres analyseurs…) → isoler une interface « appareil » (balayage → F, L) derrière `TinySA` /
  `ScanWorker` pour en brancher plusieurs.
