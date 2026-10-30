# TinySA Monitor — contexte pour Claude Code

Application Windows (un seul fichier : `tinysa_monitor.py`, ~7 600 lignes) pour tinySA Ultra : spectre en direct +
monitoring de 100+ fréquences, pensée pour la coordination HF en festival. Version courante : **7.25.0**.
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

## Deux branches : V7 (stable) et V8 (SDR)
- **V7** = `ui-validation` → `main` (releases `v7.x`). **V8** = `v8-sdr` (SDR : HackRF, RTL-SDR ; pré-release
  `test-v8-sdr` seulement). Ne PAS fusionner la V8 dans main avant le feu vert de Clément (quand il aura testé avec
  son HackRF Pro) : ce jour-là, retirer la surcharge `APP_VER` de la V8, monter la version (8.0.0), fusionner.
- **Toute modif de la V7 doit aller dans la V8** (demande de Clément, sinon conflits). Automatique : le workflow
  `.github/workflows/sync-v8.yml` fusionne `ui-validation` dans `v8-sdr` à chaque push sur `ui-validation`, puis
  relance la compilation de la V8 ; en cas de conflit il échoue (annotation « Conflit V7 → V8 dans : … ») sans rien
  pousser. Par sécurité, après chaque version V7, vérifier : `git fetch origin && git log origin/v8-sdr..origin/ui-validation`
  (doit être vide), sinon fusionner à la main.
- **Pour éviter les conflits** : la V8 ne modifie JAMAIS les lignes communes qui bougent à chaque version V7. La ligne
  `APP_VER = "7.x"` reste identique dans les deux branches ; la V8 la surcharge plus bas (`APP_VER = f"8.0-dev
  (base {APP_VER})"`, juste avant le bloc Qt « V8 : SDR ») — le workflow lit la 1re ligne `APP_VER`. L'en-tête de ce
  fichier (« Version courante ») est le même dans les deux branches ; les notes V8 vont dans « Reste à faire ».
  Le code V8 est surtout AJOUTÉ (nouvelles fonctions / classes en fin de sections) : garder ce style.
  Vu en 7.10.0 : V7 et V8 avaient chacune inséré une bulle juste après `TIPS_MENU = {` → conflit (le robot l'a
  signalé, fusion à la main). Règle : la V8 n'insère RIEN aux mêmes points d'ancrage que la V7 (début d'un dict,
  d'une liste de menu…) ; ses bulles sont dans `MainWindow.TIPS_MENU.update({...})` juste avant `def main()`.

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
- **Profils d'appareil (7.9.0, Clément : « après Wisycom c'est très sélectif, il faut des machines moins sélectives
  Shure, Sennheiser… »)** : PURE `RX_PROFILES` (clé, nom, {sep, filt, step, tol}, explication) : wisycom (= profil
  EazyRF de Clément), senn_dig, senn_ana, shure_dig, shure_ana, iem (+ 5ᵉ ordre) ; **seul Wisycom vient d'un vrai
  profil, les autres sont des valeurs de départ NON vérifiées** (lui demander ses profils EazyRF). `rx_profile(key)`.
  `pf_check` / `pf_suggest` acceptent sep / filt / tol PAR FRÉQUENCE (listes, `_pf_vec`, `_pf_tols`) : écart d'une
  paire = le plus grand des deux, filtre et tolérances = ceux de la fréquence touchée (supposition raisonnable, pas
  lue chez EazyRF) ; pas des propositions = celui de l'appareil de la fréquence. `w["rx"]` (config + shows via
  `watch`). `PlanCheckDialog` : `prof_combo` (appareil par défaut → remplit les réglages ; toucher un réglage →
  « ✏ Réglages ci-dessous »), colonne « Appareil » (`rx_short`), `rx_combo` + « Appliquer aux lignes choisies »
  (`set_rx`, sélection multiple), `fill_rx_combo`. `plan_opts["prof"]`.
- **Vraies fenêtres (7.10.0, Clément : « on pouvait pas placer les fenêtres comme on veut », « pas hyper fluide »)** :
  `PanelWindow` (QWidget `Qt.Window`, pas « outil » : agrandir, barre des tâches ; barre 🖥 Écran suivant / ⛶ Plein
  écran / 📌 Raccrocher ; F11 / Échap ; fermer = raccrocher) ; `MainWindow.panel_window(dock, on, screen, mode)`
  déplace le widget du dock dans la fenêtre (le dock garde un bouton « cliquer pour raccrocher » et se cache),
  `panel_wins` {objectName: fenêtre}, `panel_docks()` (tous sauf le mur, qui a son mécanisme), `panel_next_screen`,
  sous-menu « 🗗 Vraies fenêtres / double écran » reconstruit à l'ouverture (`_fill_panel_menu` : par panneau,
  fenêtre libre / écran N agrandie / plein écran), `panel_attach_all` (aussi dans `layout_standard`),
  `layout_dual` = liste agrandie sur l'autre écran. Config `panel_windows` (`panel_state` : geo, mode, nom d'écran)
  rouverte par `_late_layout` → `panel_restore` ; `closeEvent` ferme ces fenêtres (sinon l'appli resterait ouverte).
  Fluidité : courbes du spectre `setClipToView` + `setDownsampling(auto, "peak")` (pics gardés), `setAnimated(False)`.
- **Manuel** : `docs/manuel.html` (HTML autonome, clair / sombre, sommaire, téléphone), embarqué dans l'exe
  (`--add-data "docs/manuel.html;docs"`, workflow + build.bat), ☰ Plus › 📖 Manuel (`manual_path` / `open_manual`).
  **Le tenir à jour à chaque nouveauté visible** (V8 : ajouter les chapitres SDR quand elle partira sur main).
- **Langues (7.11.0, Clément : « une full trad en anglais avec choix de langue »)** : le programme reste écrit en
  français ; l'anglais passe par une couche posée sur Qt. PURE : `Translator` (`TR`, vide = français), `LANGS`,
  `web_page_lang`. `lang_en.py` (racine, `--hidden-import lang_en`) : `EXACT` (texte → anglais), `TEMPLATES`
  (f-strings, « {} » = trou traduit à son tour), `SAME_TEMPLATES` (volontairement non traduits), `WEB` (morceaux
  de `WEB_PAGE`), `VOCAB` (mots proposés pour les noms : les noms de l'utilisateur ne sont JAMAIS dans `EXACT`).
  Moteur : exact → espaces → morceaux séparés par « · » / « | » / « — » → modèles (tous les découpages essayés)
  → « Libellé : valeur » → emoji de tête → suffixes « : », « … », « . » → minuscule → ligne à ligne ; HTML
  (`TR.html`) : texte entre les balises. `install_language(code)` (avant les fenêtres, dans `main()`) enveloppe
  constructeurs et setters Qt (`_patch`, `_tr_args`) ; listes modifiables (`isEditable`) jamais traduites (relues
  par le programme). `read_language()` : `TSM_LANG`, puis config « lang », sinon langue de Windows.
  ☰ Plus › 🌐 Langue / Language (`lang_menu`, `set_language` : enregistre, propose de redémarrer). Hors Qt :
  `send_notify`, `web_json`, `export_log`, rapport (`TR.html`), libellés dessinés du bandeau (`update_strip_labels`).
  **Relire un texte affiché = piège** : comparer à `TR("…")` ou passer par `itemData` (ex. thèmes de couleurs).
  **Tout nouveau texte visible → sa traduction dans `lang_en.py`** (`tests/test_i18n.py` échoue sinon, et
  `tests/gui_en.py` lance l'appli en anglais et relève tout texte français visible). V8 : ses textes à elle dans
  un fichier à part (`lang_en_v8.py`, fusionné au chargement), pour ne pas toucher aux lignes de `lang_en.py`.
  Manuel anglais `docs/manual_en.html` (`manual_path` suit la langue) : le tenir à jour avec le français.
- **7.12.0 (retours de Clément après 7.11)** :
  - Redémarrage après changement de langue : `restart_app()` (QProcess + `PYINSTALLER_RESET_ENVIRONMENT=1`, variables
    `_PYI_*` / `_MEIPASS2` retirées). Avant : l'exe relancé réutilisait le dossier `_MEI…` de l'ancien, effacé à sa
    fermeture → « No module named numpy._core._multiarray_umath » (capture de Clément).
  - **Sessions** : à ▶ Démarrer, `SessionDialog` (« Enregistrer cette session ? », dossier au choix, nom, « ne plus
    demander ») ; `session_cfg = {ask, rec, dir}` (config `session`, PURE `SESSION_DEFAULT`, `session_cfg_norm`,
    `session_name`) ; `_session_begin` / `_session_end` (à ▶ Arrêter, `on_finished`) / `_session_log` : dossier =
    chunks `SweepRecorder` + `session.json` (watch, bandes, show, début / fin) + `journal.csv` (`SESSION_JOURNAL_HEAD`).
    Relecture : « 📂 Ouvrir une session » (`open_rec` lit session.json → `sess_watch`, journal.csv →
    `sess_events`, PURE `session_journal_rows`), « 🕘 Dernière session », « 💾 Exporter… » (`export_store`).
    Case « Demander à chaque démarrage » (`sess_ask_chk`, onglet Journal). `rec_mb_per_hour` (place estimée).
  - **Profils d'appareil** : filtres donnés par Clément (EazyRF) : evolution 16, SLX 16, PSM 16, AD 32, QLX-D 32
    (ULX-D supposé idem) ; ADT inconnu (0 = prudent) ; `d["src"]` (eazyrf | guess | perso). Profils perso :
    `RX_CUSTOM`, `rx_all`, `rx_custom_norm` / `rx_set_custom` / `rx_custom_dump` (config ET shows : `rx_custom` dans
    SHOW_KEYS, appliqué en tête de `_apply_config`), `RxProfilesDialog` / `RxProfileEdit`, `rx_profiles_changed`.
    Aide : `rx_help_html` (PURE), `show_filter_help`, `filter_help_btn` (PlanCheck + Intermod).
  - **Intermod d'après le spectre** (Clément : « il faut partir du spectre, pas des appareils déclarés ») :
    source « spectrum » de `IntermodDialog` = `spectrum_sources()` (pics max hold au-dessus du seuil faible,
    centrés, voisins ±50 MHz d'abord, 24 max), choisie d'office en recherche d'origine ; tri par ordre puis écart.
  - **❓ Courbes** (`SpectrumLegendDialog`, `open_spectrum_legend`, gardée en mémoire : ses liens restent valides) :
    chaque trait du spectre expliqué + réglages reliés dans les deux sens (`_link`), encart « bases RF ».
  - **Réglages** : « Détection » coupée en « Seuils : quand est-ce occupé ? » (`dform`, clé `detect`) et « Alarmes »
    (`aform`, clé `alarms`). **Journal** : PURE `LOG_KINDS` / `log_kind` / `log_kinds_norm`, `self.log_kinds`
    (config `log_kinds`), filtre en tête de `log_event`, menu « 📝 Quoi noter… » (`logwhat_menu`, `_logwhat_acts`).
  - **Thèmes doux** : `DEFAULT_THEME = "Sombre doux"`, + Nord, Ardoise, Daltonien (Okabe-Ito), Clair doux ; clé
    `st_libre` (bleu « réserve libre ») dans THEME_KEYS ; statuts par défaut adoucis.
  - **☰ Plus rangé** par moment du travail (sections Pendant le show / Préparer et analyser / Affichage / Aide ;
    sous-menus 📐 Plan, 📋 Liste, 📊 Scans et rapports, 🔗 Connexions, 🪟 Fenêtres, 🎨 Apparence et langue) +
    boutons rapides dans la barre (`quick_btns` : 🎤 🧱 ⏪ 🧮 ⚡ 📣). `MainWindow.EXTRA_MENUS` = sous-menus ajoutés
    par une autre version (V8 : SDR) **sans toucher au code du menu** (anti-conflit).
  - **Langue par personne** : page web FR / EN au choix de chacun (bouton en haut, cookie `tsm_lang`, sinon
    `Accept-Language`, sinon langue de l'appli) : `WebServer(get_page, default_lang)`, `get_json(lang)` ;
    `web_json()` → `{"fr": bytes, "en": bytes}` ; `en_translator()` (anglais même si l'appli est en français),
    `web_page_bytes(lang)`, `_load_lang_en()`. Alertes : `notify_cfg["lang"]` (app | fr | en), `n_lang`.
    `QDialogButtonBox.addButton` traduit aussi.
  - **Manuel** réécrit (25 chapitres, bases RF, lire le spectre, seuils, filtre, sessions, menus) FR + EN, et **PDF**
    `docs/manuel.pdf` / `docs/manual_en.pdf` (GitHub n'affiche pas le HTML) : `python tests/make_pdf.py`
    (Playwright / Chromium) **à relancer après chaque modif du manuel**.
- **7.13.0 (un utilisateur de Clément : « j'ai rien compris », Clément : « ordre logique scan → PF → intermod →
  monitoring », « mode ultra simple », « mode tuto »)** : barre **Parcours** (2ᵉ rangée, `_build_steps_bar`, PURE
  `STEPS` / `STEP_DEFAULT` / `STEP_HINTS` / `STATUS_HELP`, `do_step`, `step_scan`, `step_monitor`, `step_lbl` =
  quoi faire) : ① Scanner le lieu › ② Mes fréquences (menu) › ③ Vérifier le plan › ④ Intermod › ⑤ Surveiller
  (menu) › ⑥ Après le show (menu) ; remplace les boutons rapides 7.12. **Niveaux** `UI_LEVELS` (ultra | simple |
  expert), `self.ui_level` (config `ui_level` ; 1er lancement sans config = ultra), `set_level` (ultra : réglages,
  journal, waterfall et classement `layer_box` cachés ; `set_expert` reste et suit). **Tuto** `TourDialog`
  (non modal, bulle posée à côté du widget entouré en orange, `tour_steps(o)`), `start_tour`, `tour_finished`,
  `tour_done` (config ; bouton « 🎓 Première fois ? Tuto » tant que pas fait). Noms : panneau « Mes fréquences »
  (était « Fréquences et couches »), encadré « Classer par scène › groupe (facultatif) » avec bulle explicative.
  ☰ Plus dans l'ordre du travail : ① Préparer / ② Pendant le show / ③ Après le show / Réglages et connexions /
  Aide (👁 Affichage, 🎓 Tuto). `self.more_btn`.
  **📡 Ajouter depuis le scan** (idée de Clément : « ajoute les fréquences à monitorer seul ») : PURE `scan_peaks`
  (zones au-dessus du seuil ; points VOISINS du balayage = même signal même si le pas est grossier, sinon un plateau
  TNT en pas de 224 kHz donnait 41 « signaux » ; plateau ≥ 1,5 MHz = `wide`, centre ; déjà dans la liste →
  écarté), `ScanAddDialog` (max hold / direct, seuil, réunir à, nom « Scan n », scène / groupe / statut), menus
  ② Mes fréquences et ☰ Plus › 📋 Liste, `open_scan_add`.
- **7.14.0 (Clément : « j'adore tout » sur 8 idées, + retours)** :
  - **Coordination auto** : PURE `pf_fill` (glouton, la plus basse compatible d'abord, via `pf_suggest`),
    `CoordDialog` (appareil, combien, plage, évite le max hold ≥ seuil « occupé »), `open_coord` ; parcours ③
    renommé « Coordonner le plan » (menu).
  - **Marqueurs M1 / M2** : PURE `trace_at`, `peak_near`, `occupied_width` ; `_build_markers_bar`, `mkr_btn`,
    `marker_refresh` (appelé par `update_plot` en finally), `_mkr_trace` (robuste sans courbe : faux Qt).
  - **Comparer deux sessions** : PURE `compare_spectra` ; ReplayDialog « ⚖ » (`cmpcurve`, violet pointillé).
  - **Occupation par heure** : PURE `store_occupancy` ; `OccupancyDialog` (Relecture 📊, ⑥, ☰ Plus).
  - **Zoom live : points auto** (Clément : « ça sert à rien d'en avoir énormément ») : PURE `zoom_points`
    (~10 kHz de pas, ≤ 290, ≤ points des bandes, ≥ MIN_PTS) ; `zpts_combo` « Points en zoom » (expert, `zpts`
    dans `_cfg`, config, SHOW_KEYS) ; `zoom_info()` dans la barre d'état.
  - **Sélection dans la liste → surbrillance sur le spectre** : `_update_selection` (fin de `_update_markers`),
    `_on_watch_sel`, `SEL_COLOR` ambre, `SEL_MAX`, régions + trait + étiquette (côté intérieur près d'un bord).
  - **📶 Bandes** (à côté de « Vue », `bands_btn`, `_build_bands_menu`) : toutes / cocher-décocher
    (`set_band_enabled`, garde au moins une) / « ne balayer que la bande affichée » (`scan_follow`, config ;
    `_follow_id`, `_scan_now` utilisé par `get_cfg`, `band_devices`, `update_estimate`, `on_cycle`). Fréquences hors
    bandes balayées : données périmées → état None, pas d'alarme (pas surveillées, dit dans la barre d'état).
- **7.14.1 (Clément : « la fréq de secours ne trouve rien », 30 radios FM déclarées)** : `find_free(...,
  emitters, filt, im3, alt)` : intermod seulement avec les émetteurs (pas les « doit rester libre »), filtre récepteur,
  2 TX seulement possible, guard None = sans intermod ; s'il en manque → « moins mauvaises » (`warn`, orange,
  colonne Remarque). `RescueDialog` : `im_combo`, `filt_spin`, message qui dit ce qui bloque. 30 émetteurs sur 20 MHz =
  bande vraiment pleine même en 2A − B (≈ 870 produits) : c'est physique.
- **7.15.0 (Clément : « go régie et festival »)** :
  - **🌙 Mode festival** : PURE `FESTIVAL_DEFAULT`, `festival_cfg_norm`, `festival_due` (1×/jour dès l'heure,
    rattrapé), `alarm_stats`, `festival_text` ; `ntfy_request` prio −1 = « default » + ✅. `FestivalDialog`,
    `open_festival` (☰ Plus ② et ⑤), config `festival` (`was_running` = tourne au moment de la sauvegarde ET pas
    `_closing` : fermeture volontaire = pas de reprise). `_late_layout` → `_festival_autostart` (4 s, réessaie
    toutes les 30 s sans tinySA ; `toggle_run(auto=True)` → `_session_prompt(auto)` sans question ; journal
    « REPRISE AUTO »). `_keep_awake` (SetThreadExecutionState, via `_style_start`), `windows_startup_on` /
    `set_windows_startup` (clé HKCU Run « TinySAMonitor ») **non testés sur Windows**. `_festival_tick` (dans
    `_alarm_tick`, toutes les 30 s) → `festival_bilan` : rapport `rapports/bilan_*.html` (`collect_report(v,
    last_n)` = événements depuis le bilan précédent, `_log_n` / `_fest_log_mark`) + message + journal « BILAN DU
    JOUR ».
  - **🎛 Vue Régie** de la page web (`WEB_VIEWS` « regie ») : alarmes en très gros en haut (sinon « ✔ Tout va
    bien »), un voyant par scène › groupe (rouge = alarme, orange = faible / occupé sans alarme, vert = OK),
    filtre de couche, plein écran. Testée dans Chromium (test_alertes, captures `CAPTURES=dossier`).
- **7.15.1 (Clément a mis à jour son tinySA : v1.4-49 de 02/2023 → firmware 2026)** : lu dans le source officiel
  (github.com/erikkaashoek/tinySA, v1.4-255 du 23/10/2026) : invite « ch> », format de `scan … 3` et commandes
  `rbw` / `mode` / `lna` / `attenuate` / **`ultra on|off|auto`** inchangés (« ultra on » existe bien). Nouveautés qui
  nous concernent : verrou des commandes (CMD_WAIT_MUTEX, corrige des blocages USB), `scan` refuse < 2 points,
  mode « disque USB » / mise à jour SD qui refusent tout → PURE `TINYSA_REFUSALS` / `tinysa_refusal(lines)`, message
  clair levé par `TinySA.scan`. **Retour de Clément avec le firmware à jour : « ça balaye bien plus vite »**
  (pas encore de 🩺 diagnostic ni de nuit complète avec ce firmware).
- **7.16.0 (Clément : « un bouton auto sur les points par scan, le plus opti entre rapidité et visibilité en fonction
  du fenêtrage total »)** : `points_combo` 1re entrée « ⚡ Auto (rapide et lisible) » (donnée 0 ; défaut d'une
  nouvelle installation : `points_auto` absent ET `points` absent). PURE `AUTO_STEPS_KHZ`, `auto_scan_step(total_mhz,
  rbw, budget=4500, step_min=10)` (pas rond ; ≤ RBW imposée). `_auto_steps()` (même pas pour toutes les bandes,
  oublie les données des bandes changées, `_auto_changed`) appelé par `apply_points`, `_bands_changed`, `_sync_cfg`
  (RBW). Saisie à la main des points / du pas d'une bande (`on_band_edit` col 3 / 4) → sort de l'Auto. `est_lbl` :
  « ⚡ Auto : pas de X kHz ». `c["points"]` reste 1000 en Auto (zoom, scan ciblé). Config / shows : `points_auto`.
  Budget 4 500 = **choix de Claude, pas mesuré** sur le vrai tinySA (à ajuster selon le retour de Clément).
- **7.16.1 (Clément : « pour tous les modes, mais faut pouvoir modifier »)** : PURE `AUTO_POINTS` (donnée −1 rapide
  2 000 / 0 équilibré 4 500 / −2 détaillé 9 000), `AUTO_BUDGET` ; `points_auto()` = budget ou None. Bouton
  **⚡ Points** (`pts_btn`, `_build_pts_menu`, `set_points_choice`, `_update_pts_btn` « ⚡ Auto · 50 kHz ») dans la
  barre du spectre, visible même en ultra simple. Config / shows : `points_sel` (donnée exacte du menu) ; **absent →
  Auto équilibré pour tout le monde** (y compris les configs existantes, demande de Clément).
- **7.16.2 (comparatif de formats envoyé par Clément, texte de source inconnue — à prendre avec prudence)** :
  `parse_scan_text` lisait déjà WWB (virgule / point-virgule / tabulation, sans en-tête), un « WSM » à blocs
  `[Data]`, décimale à virgule, Hz ; **ajout : en-tête « dBµV » (Wisycom Manager) → dBm = dBµV − 107**. Le format WSM
  du comparatif (`[Data]`, MHz, dBm) contredit celui de nikharju (kHz + %, ligne 7) : on lit les deux, l'export WSM
  reste celui de nikharju. Formats de **listes de fréquences** (WWB / WSM / Wisycom / EazyRF) : toujours pas de vrai
  fichier → demander des exemples à Clément (docs.soundbase.app bloqué par le réseau de la session).
- **7.17.0 (Clément : « choisir la sortie audio, un menu Settings avec roue crantée », « hyper chaud de la chasse au
  brouilleur »)** :
  - **Son** : PURE `SOUND_DEFAULT` / `SOUND_STYLES` / `ALARM_TONES` / `TONE_OK` / `sound_cfg_norm` / `tone_pcm` (PCM
    16 bits, fondu). `SoundOut` (QtMultimedia importé à la demande : `QMediaDevices.audioOutputs`, `QAudioSink` sur un
    `QBuffer`, 22 050 Hz mono ; style « beep » ou erreur → `QApplication.beep`). `self.sound` remplace tous les
    `beep()` (alarmes, alerte, appel des micros). Config `sound`. `--hidden-import PySide6.QtMultimedia` (workflow +
    build.bat). **Pas testé sur un vrai Windows / dans l'exe** (CI Linux et Windows sans carte son).
  - **⚙ Réglages** : `SettingsDialog` (onglets Général / Son / Fichiers / Connexions, tout s'applique tout de suite,
    reflète les contrôles existants), bouton `settings_btn` « ⚙ » dans `cmd_bar`, ☰ Plus › Réglages et connexions,
    Ctrl+, , `open_settings(tab)`.
  - **🔎 Chasse au brouilleur** : PURE `hunt_level` (max à ± 100 kHz ou pic de la zone), `hunt_tone` (400 → 2 000 Hz,
    1 000 → 80 ms) ; `HuntDialog` (non modal, `self._hunt`, nourri par `on_sweep` pour `ZOOM_ID`, zoom live sur
    f ± zone/2 ; bouton zoom resté coché sans zoom → `toggle_zoom(True)` direct), `open_hunt(f0)` (sélection de la
    liste, M1, centre de la vue) ; ⑤, ☰ Plus ②, clic droit du journal.
- **7.18.0 (Clément : « le planning, corrélé avec les scènes », « mode émission juste pour kiffer, test de récepteur »)** :
  - **🎬 Planning** : PURE `PLANNING_DEFAULT`, `_hm`, `planning_norm` (créneau {scene, group "" = toute la scène, day ""
    = tous les jours / AAAA-MM-JJ, start, end ; fin < début = après minuit}), `planning_active(pl, ymd, minute, prev,
    next)` (marges `pre` / `post`), `planning_paused`, `planning_lines`. `PlanningDialog` (table de widgets, aperçu
    « Maintenant » ; `values()` ignore une ligne en cours de création), `open_planning` (⑤, ☰ Plus ②). MainWindow :
    `self.planning` (config + SHOW_KEYS « planning »), `_plan_state`, `_planning_now`, `_planning_tick` (dans
    `_alarm_tick`, 15 s : journal « CHANGEMENT DE PLATEAU », ABSENT des groupes partis effacés), `w_paused(w)` →
    pas d'ABSENT (`update_watch_levels`), `sig_view` « 💤 pas sur scène » (⏸ ne s'affiche pas partout), page web
    `paused` (Régie : groupe gris).
  - **📡 Mode émission** : commandes LUES dans le source du firmware (pas testées sur un vrai Ultra) : « mode low
    output », `gen_commands` (PURE : freq, level, modulation off|fm|am, modulation freq / deviation), « output on|off »,
    retour « mode low input ». `EmitDialog` (case « en câble » obligatoire, refus si la surveillance tourne, connexion
    `TinySA` à part, démo = commandes notées dans `sent`, « Parcourir ma liste »), `open_emit` (☰ Plus ②).
- **7.19.0 (Clément : « chercher le brouilleur en me déplaçant, le PC reste en régie », « j'ai un Raspberry »)** :
  - **Relais autonome pour Raspberry Pi** : `relais/tinysa_relais.py` (pyserial seul, SANS Qt : copie de la logique de
    `SerialRelay`, même protocole ; `find_tinysa` = USB 0483:5740 sinon 1er ttyACM ; réouverture auto ; `serve(...,
    stop, opener, on_ready)`), `relais/install_pi.sh` (service systemd `tinysa-relais`, groupe dialout),
    `relais/LISEZMOI.md`. Test `tests/test_relais_pi.py` (pty, sauté sous Windows ; dans la liste de la CI).
    **Testé en vrai par Clément en 7.23.2 (Pi 4).** Si on touche `SerialRelay`, garder `tinysa_relais.py` cohérent.
  - **Chasse avec le 2ᵉ tinySA** : `self.zoom_dev` (préférence du zoom live dans `get_cfg`), `HuntDialog.dev_combo`
    (2ᵉ par défaut), remis à 0 à l'arrêt.
  - **Vue web 🔎 Chasse** (`WEB_VIEWS` « chasse ») : commandes POST `/chasse` {pin, action start|stop|reset, f, span,
    follow, dev} (PURE `hunt_request`, code PIN comme `/acquitter`, `WebServer(on_hunt=…)`), file `_web_hunts` →
    `_web_hunt_pending` (ouvre / règle la chasse, PC muet) ; état `hunt_state()` dans /etat.json (`hunt`) ; bip joué
    par le NAVIGATEUR (Web Audio, `huntTone` = même formule que `hunt_tone`) ; liste des tinySA reconstruite si elle
    change (montée avant le 1er état).
- **7.20.0 (Clément : « un multi-spectre en fonction des scènes, un tiny en mouvance entre scènes, export ou merge des
  scans pour une coord complète »)** : PURE `merge_scans` (grille au pas le plus fin, interpolation sur la plage de
  chaque scan + points exacts posés, MAX = pire cas ; trous sans mesure retirés), `site_scan_doc` (compact),
  `site_scans_norm`. `SitesDialog` (lieu = combo modifiable, scènes proposées ; « 📍 Garder » = max hold actuel,
  « ajouter (max) » ou remplacer ; 📥 import d'un fichier ; courbes par lieu + fusion pointillée coupée sur les trous ;
  export fusion / lieu en WWB / WSM / CSV via `scan_write` ; 📏 fusion = référence ; case `sites_coord`).
  `self.site_scans` (config + SHOW_KEYS « site_scans »), `coord_FL()` (max hold + lieux si `sites_coord`) utilisé par
  `CoordDialog.compute` et `RescueDialog.search`. `open_sites` (☰ Plus ①, parcours ③).
  **7.20.1** : spectre principal = scan gardé de la scène choisie dans l'arbre (PURE `sites_for_scope`), fusion en
  Global : `sitecurve` (PlotCurveItem, ignoreBounds), `site_lbl`, `update_site_curve` (appelé par `set_scope`,
  `open_sites`, la config).
  **7.21.0 (Clément : « ça scanne en continu, c'est vraiment la sélection du lieu visualisé sur le spectre »)** :
  `self.dev_site` {appareil: lieu} (config `dev_sites`), `set_dev_site`, bouton `sites_btn` = QToolButton à menu
  (`_build_sites_menu` : « 1er tinySA est à… », afficher, Scans par lieu ; toujours visible) + combos dans SitesDialog.
  `on_sweep` → `_site_feed` (via `band_src` : `site_live` {lieu: {bande: (F, L, t)}}, `site_mh` max hold du lieu,
  `_site_base` = scan gardé au 1er balayage) ; `_sites_tick` (30 s, dans `_alarm_tick`) garde `site_mh` fusionné à
  `_site_base` dans `site_scans`. `view_sites()` : scène choisie qui est un lieu → `_update_plot` trace le direct du
  lieu (`site_live`), rien en direct si aucun tinySA n'y est (étiquette « pas de tinySA ici »). PURE `multi_site` :
  2 tinySA vivants à 2 lieux différents → `band_devices` renvoie -1 (chacun balaye toutes les bandes, `get_cfg`
  accepte -1), `latest` global = max des lieux (pire cas), `update_watch_levels` juge une fréquence de la scène X avec
  `site_fresh(X)`. Testé en démo (2 tinySA simulés) ; **jamais avec deux vrais tinySA à deux endroits**.
- **7.22.0 (Clément : « rattacher un tiny à une ou plusieurs scènes, intuitif, en expert, à tout moment ; un mode pour
  reconnaître le tiny »)** : `self.dev_scenes` {appareil: [scènes]} remplace `dev_site` (config `dev_scenes`, l'ancien
  `dev_sites` est relu par PURE `dev_scenes_norm`) ; `multi_site` compare des ensembles de scènes ; `_site_feed`
  alimente toutes les scènes du tinySA. `set_dev_scenes` / `toggle_dev_scene` (`set_dev_site` = enveloppe à 1 scène).
  `DevicesDialog` (non modal, `self._devdlg`, `open_devices`) : grille scènes × tinySA, 👋 Identifier, 🔢 Numéroter.
  Clic droit sur une scène › « 📡 Surveillée par » ; arbre « 📡 nom » (`dev_tag`) ; bouton `sites_btn` « 📡 Scènes »
  — tout ça **en mode expert seulement** (`set_expert`), la surveillance par scène continue en simple.
  `ScanWorker.cmdq` (file traitée entre deux bandes par `_run_cmds`) : identify = palette lue par `color` (PURE
  `palette_color`), fond `color 0 0xFF9F1C` ×4 puis restauré ; setid = `deviceid n` + `saveconfig`. Numéro lu à la
  connexion (`deviceid`, PURE `parse_deviceid`) → signal `devid` → `on_devid` : `devid_scenes` {n°: scènes} (config)
  → un tinySA numéroté retrouve ses scènes s'il est branché à l'autre place. **Commandes lues dans le firmware, jamais
  essayées sur un vrai Ultra** (clignotement / numéro).
- **7.23.0 (Clément : « mieux m'expliquer le kit Pi », il n'a qu'UN tinySA)** : le **1er tinySA peut être en réseau** :
  dernière entrée de `port_combo` « 🌐 tinySA en réseau (Raspberry Pi, autre PC)… » (`NET_ITEM`) → `_port_chosen`
  (QInputDialog, `parse_device_addr`) ; `self.net_addr` / `self.port_net` (config `net_addr`, `port_net`) : l'adresse
  retenue s'affiche « 🌐 adresse (réseau) » (en tête si choisie) ; **`port1()`** = adresse du 1er tinySA (jamais
  `NET_ITEM`) : à utiliser au lieu de `port_combo.currentData()`. Worker réseau : `retry_first` (le Pi peut démarrer
  après). Workflow : étape « Kit Raspberry Pi » → `dist/relais-raspberry-pi.zip` (dossier `relais/`, fins de ligne LF
  forcées, `install_pi.sh` exécutable) attaché aux releases et pré-releases. `relais/LISEZMOI.md` réécrit pas à pas
  (Imager, scp / ssh depuis le Terminal Windows, 1 ou 2 tinySA, dépannage). **Pi toujours jamais testé en vrai.**
  **7.23.1 (1er essai de Clément : « le Pi ne détecte pas le tiny en USB selon journalctl »)** : `tinysa_relais.py` :
  `diagnose()` (lu dans /sys/bus/usb/devices : rien vu → allumé / câble data / prise USB-A ; 0483:df11 = DFU ; autre
  0483 = disque USB ? ; 5740 sans ttyACM ; ttyACM sans droits → dialout), écrit dans le journal à chaque attente,
  `--diag` ; `find_tinysa` retombe sur `glob /dev/ttyACM*`. Cause réelle chez Clément : **câble USB-C charge seule**.
  **7.23.2 (Clément : « tiny ouvert dans journalctl mais pas le lien à l'appli », ping OK)** : l'exe n'embarquait PAS
  `serial.urlhandler.protocol_socket` (importé dynamiquement par `serial_for_url`) → **tout tinySA en réseau était
  impossible dans l'exe** depuis toujours (1er comme 2ᵉ ; les tests tournent en Python, pas dans l'exe). Corrigé :
  `import serial.urlhandler.protocol_socket` en tête + `--hidden-import` (workflow, build.bat). Nouveau
  `TinySA-Monitor.exe --selftest fichier` (`self_test` : socket:// réel en local, lang_en, QtMultimedia, manuels) lancé
  par la CI après PyInstaller, **bloquant** (annotation « auto-test exe »). Tout nouvel import dynamique → l'y ajouter.
  **✅ Vérifié en vrai par Clément (7.23.2, 30/10/2026)** : Raspberry Pi 4 + tinySA Ultra (firmware 2026) + relais
  installé par `install_pi.sh`, 1er tinySA en réseau dans l'exe Windows : « ça fonctionne ». Restent non testés : la
  chasse depuis le téléphone avec ce kit, une longue durée, le Wi-Fi d'un vrai festival.
- **7.24.0 (Clément : « depuis l'interface web, en mode caché, affecter le tiny volant à n'importe quelle scène ou
  toutes, et save des scans, pour la coord en amont » ; « en save plusieurs sur des scènes différentes »)** : vue web
  **🎒 Terrain** (`WEB_VIEWS` « terrain », **cachée par défaut** : `WEB_VIEWS_HIDDEN`, `web_views_norm`) ; POST
  `/terrain` {pin, action assign|reset|save|delete, dev, scenes, label, name} (PURE `terrain_request`, routes à PIN
  génériques `pin_routes` dans `WebServer`, `on_terrain`) → file `_web_terrain` → `_web_terrain_pending` (dans le tick) :
  `set_dev_scenes`, `terrain_reset` (vide `site_mh`, base = scan continu), `terrain_save` (max hold `_site_mh_FL` →
  scan à part), effacer. **Plusieurs scans par scène** : doc `site_scan_doc(..., scene=)` (clé `scene`, gardée par
  `site_scans_norm`), nom unique `snapshot_name` (« Scène · étiquette » ou l'heure) ; `site_doc_scene(d)` ;
  `sites_for_scope` prend le continu + les gardés de la scène ; `update_site_curve` « fusion de N scans gardés ».
  État `terrain_state()` dans /etat.json (`terrain`). Testé : PURE, route (faux PIN 403…), page dans Chromium
  (capture `web_terrain.png`), vraie appli (gui_reel). **Pas essayé par Clément sur le terrain.**
  **7.25.0 (Clément : « avec une rémanence si possible »)** : vue web Spectre, case « Rémanence » (`#rm`, retenue
  `LS rm`) : `persLayer` = canevas hors écran, à chaque nouveau balayage (`spec.t`) estompé (destination-out 0,13) puis
  trace bleue `rgba(56,189,248,.45)` ; remis à zéro si bande / échelle / taille changent (`pers.k`). Clément voulait
  ça **dans la vue cachée Terrain** : spectre intégré (« 📈 Ce que voit le tinySA », rémanence cochée d'office) +
  **max hold par scène** (« avec max hold aussi par scène ») : `/spectre.json` porte `scenes` {scène: {color, segs}}
  (`site_mh` réduit par `web_spectrum`, seulement si quelqu'un regarde Terrain : `watching(("terrain",))`), liste
  `#tmh` (aucun / toutes / une scène, `LS tmh`). Limite : le direct / la rémanence = spectre global (avec 2 tinySA
  à 2 endroits, le max des deux), le max hold, lui, est bien celui de la scène. Côté PC : pas de rémanence.
  **Coordination par scène ou globale** (Clément : « je me balade en faisant mes scans sur différents lieux pour que ça
  enregistre sur le serveur sur chaque scène, pour faire une coord par scène ou globale après ») : PURE `coord_docs`
  (live | all | une scène) ; `coord_FL(src)` (scène = ses scans + `_site_mh_FL`) ; `fill_coord_combo` (« Spectre : … »,
  scène de « Mes fréquences » d'office) dans `CoordDialog.spec_combo` et `RescueDialog.spec_combo`.
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
- **Scan natif WWB `.sdb3` (7.22.1, vrai fichier de Clément : SLXD4, H56, WWB 7.0, `tests/data/wwb_slxd4_scan.sdb3`)** :
  `//@ShureScan` + JSON (`BinarySchema` : start-of-sweep 4, id 4, timestamp 4, Curve {FreqRanges kHz Start/End/Step},
  crc16 2 ; `BitWidth` 16, `Scale Factor` 10, `NoDataValue` −1400), puis `@Binary:` = enregistrements `@Swp` (niveaux
  int16 **big-endian** / 10 = dBm), `@Extended:` (Band, Channel, Creator), `@End`. PURE `parse_sdb3` (plusieurs
  balayages → max), appelé par `parse_scan_text` (decode_text lit ce fichier en latin-1 pour retrouver les octets).
  CRC non vérifié ; un fichier à plusieurs courbes / plusieurs balayages jamais vu en vrai.
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
python tests/test_sdr.py ; python tests/test_sdr_qt.py   # V8 : SDR (faux hackrf_sweep)
python tests/test_alertes.py     # ntfy / Telegram / Notifier / WebServer ; page testée dans Chromium si Playwright
python tests/test_i18n.py        # traduction anglaise complète (lang_en.py), moteur Translator, page web anglaise
python tests/gui_en.py          # VRAI Qt en anglais : relève tout texte français visible (captures tests/captures_en/)
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
- **V8 étape 1 (fait, branche `v8-sdr`) : SDR en balayage** par leur outil officiel : `hackrf_sweep` (HackRF One)
  et `rtl_power` (RTL-SDR), même CSV. PURE : `SDR_KINDS`, `parse_sdr_addr` (« hackrf », « hackrf:<série> »,
  « rtlsdr:1 » ; `parse_device_addr` → genre « sdr »), `sweep_line`, `SweepAccum` (passage complet quand un bloc
  revient), `resample_max` (max par cellule, `reduceat` + sentinelle), `sdr_ranges` (MHz entiers, ≤ 10 plages),
  `sdr_bin_hz`, `sdr_cmd`. Qt-side : `find_sdr_tool` (dossier choisi, à côté de l'appli / `outils`, PATH, PothosSDR),
  `SDRSweep` (même interface que `TinySA` : l'outil tourne en continu sur toutes les bandes, `configure()` le
  relance si plages / case / gains changent, `scan()` rend le dernier passage pas encore servi ; outil arrêté ou
  muet → erreur → reconnexion du worker). `ScanWorker.sdr / sdr_dir / sdr_tool (tests) / get_sdr`, un seul segment
  par bande. Ports : « 📡 HackRF One / RTL-SDR » dans `port_combo` et `dev2_addr` ; `self.sdr_cfg` {dir, lna, vga,
  amp} (config « sdr ») ; port choisi gardé (config « port », `_want_port`) ; `SdrDialog` (Outils › 📡).
  Tests : `tests/fake_sdr.py` (faux hackrf_sweep, `FAKE_SDR_CARRIERS`, `FAKE_SDR_DIE`), `test_sdr.py`,
  `test_sdr_qt.py` (vrai ScanWorker). **Jamais testé avec un vrai HackRF / RTL-SDR** ; niveaux non étalonnés.
  `configure()` lève une erreur si l'outil est mort entre deux cycles (avant : relancé en silence → débranchement
  invisible, vu dans la CI Windows).
- **V8 étape 2 (fait) : écoute 🎧** (Outils, clic droit sur la liste) : PURE `LISTEN_MODES` (wfm ±50 kHz / nfm /
  am), `LISTEN_COMPANDERS` (none, x2 = expanseur 2:1 générique `expand2`, approximation), `sdr_iq_rate` (HackRF
  4,8 MS/s, RTL 2,4 MS/s), `iq_from_bytes`, `lowpass_taps`, `FirDecim` (FIR + décimation en flux, sliding_window_view),
  `ChannelDemod` (mélange NCO, 240 kHz, discriminateur, 48 kHz, désaccentuation en FIR, squelch dBFS),
  `audio_int16`, `listen_center` (plus grande grappe dans ±0,4·fs, évite le continu), `listen_cmd`
  (`hackrf_transfer -r -` / `rtl_sdr -`). Qt : `ListenWorker` (QThread, ≤ 4 canaux, `sel` = canal entendu, -1 =
  mélange, `audio` deque, `levels`), `AudioOut` (QtMultimedia QAudioSink, retard jeté > 0,5 s), `ListenDialog`.
  Le SDR ne balaye pas pendant l'écoute : `ScanWorker.paused` → `Aborted` dans `scan` → outil arrêté, statut
  « 🎧 écoute en cours », pas de « liaison perdue » ; reprise ensuite. ~17 % d'un cœur par canal à 4,8 MS/s.
  Tests : `tests/fake_iq.py` (IQ FM synthétique au rythme réel), test_sdr (DSP), test_sdr_qt (bout en bout, pause).
  **Non vérifié** : vrai HackRF / RTL-SDR, `hackrf_transfer -r -` vers stdout sous Windows, son réel (QAudioSink),
  rendu des companders. Reste : WiNRADiO (SDK Windows propre à chaque modèle).
- **V8 étape 3 (fait) : ⏱ temps réel** (Outils, clic droit sur la liste « autour de cette fréquence ») : fenêtre
  fixe vue SANS TROU (FFT jointives de tous les échantillons). PURE : `RT_RATES` (HackRF 19,2 / 9,6 / 4,8 MS/s,
  RTL 2,4 ; multiples de 240 kHz pour démoduler), `RT_FFT`, `rt_frames` (moyenne + max dBFS par bloc de 50 ms),
  `rt_freqs`, `rt_useful` (80 %), `decimate_max`, `Persist` (histogramme fréquence × niveau qui s'efface),
  `BurstDetector` (signaux au-dessus d'un seuil : groupes de cases, suivis, événement {t0, t1, f, peak, width} à la
  disparition). Qt : `RealtimeWorker` (frame / events / stopped, `thr`, `listen` = démodulation sur le même flux,
  `load` = charge, saturation = échantillons à pleine échelle), `RealtimeDialog` (spectre + max-hold + persistance
  + waterfall + journal des signaux, « ignorer mes fréquences », « aussi dans le journal », clic = écouter en
  accrochant le pic à ±100 kHz). Écoute 🎧 et temps réel s'excluent (un seul flux par SDR). Optimisations :
  oscillateur par table × phase par bloc (exp() par échantillon = 60 % d'un cœur), IQ lu directement en complex64.
  Mesuré ici : 19,2 MS/s ≈ 50 % d'un cœur (+ 12 % pour l'écoute). `fake_iq.py` : `FAKE_IQ_BURSTS`.
  **Clément n'a pas encore de SDR** : rien sur main tant qu'il n'a pas testé.
- **V8 étape 4 (fait) : enregistrement IQ + relecture, préréglages de démodulation, companders** :
  PURE `SDR_DTYPE`, `IQ_BYTES`, `iq_decode` (ci8 / cu8 / ci16_le / cf32_le), `sigmf_meta` / `sigmf_info` /
  `sigmf_annot` (signaux détectés en annotations SigMF), `datetime_utc_iso` / `iso_to_epoch`, `rec_size_text` ;
  `DEMOD_PRESETS` (+ `demod_preset`, `DEMOD_CUSTOM`) : Sennheiser / Shure / Wisycom / Lectrosonics analogiques, ears,
  guide, PMR446, radio FM, aviation = mode, déviation, largeur, bande audio, désaccentuation, compander (valeurs
  de départ NON vérifiées) ; `ChannelDemod(..., dev, cut, audio)`. `COMPANDERS` = (nom, taux, montée, descente) :
  FLAT, ENC, ENR, ENS, ENC / ENR 1.2, SEN / EVO (HDX), Shure, LEX — noms des modes de compatibilité des récepteurs
  Wisycom (capture Google de Clément) ; courbes réelles non publiées → `expand2(..., ratio)` approché, différences
  ENC / ENR / ENS **inventées au jugé** (temps de réponse). Qt : `DemodPick` (préréglage + mode + compander +
  désaccentuation liés), utilisé par `ListenDialog` et `RealtimeDialog`. `RealtimeWorker` : `src` = relecture
  SigMF (rythme réel, `speed` ×1/×2/×4, `playing`, `seek_to`, heure d'origine), `start_rec` / `stop_rec` (fichiers
  `<journaux>/enregistrements_iq/<date>/iq_HHMMSS_<MHz>.sigmf-data/-meta`, méta réécrite toutes les 10 s, arrêt
  sous 2 Go libres ou à `sdr_cfg["rec_max_gb"]`). `RealtimeDialog` : ⏺ / 📂 / 📁, barre de lecture (pause,
  curseur, vitesse, « Revenir au direct »), pas d'enregistrement d'une relecture.
- **V8 étape 5 (fait) : tous les modes courants + companders d'après le manuel Wisycom** : `LISTEN_MODES` = wfm,
  wfm_st (stéréo : pilote 19 kHz filtré, cos θ par dérivée centrée, sous-porteuse sin 2θ ; ALIGNEMENT : `FirDecim`
  avance sa sortie de la moitié du filtre, donc G+D et G−D sont pris sur le composite sans ses 63 premiers
  échantillons — test de séparation ≥ 20 dB), nfm, am (AGC), usb / lsb (canal à 48 kHz, décalage ±cut/2, passe-bas
  complexe 255 points, retour, partie réelle, AGC), cw (bip `BFO` 700 Hz). Sortie son STÉRÉO partout (`to_stereo`,
  `audio_int16` entrelacé, `AudioOut` 2 voies ; tests : voie gauche = `[0::2]`). `COMPANDERS` = dicts (`_cp` :
  ratio, attack, release, det avg|rms, deemph forcée, knee + low = expansion plus forte sous le genou, hf =
  détecteur sans les aigus) : FLAT (ni compander ni désaccentuation, « test purposes only »), NONE-d50, NONE-d75,
  ENC (désaccentuation 25 µs, voix), ENR (genou −30 dB, détecteur < 8 kHz, bruit), ENS (live), ENC / ENR 1.2,
  SA572, RMS, SEN (Sennheiser 3000 / 5000), EVO (evolution, HDX), Shure, LEX. Sources : manuel Wisycom (tableau NONE-d50 / d75 / ENR-WISY / ENC-WISY / FLAT envoyé
  par Clément), fiches MCR54, docs lues par Clément ; courbes réelles inconnues → valeurs AU JUGÉ.
  `ChannelDemod(compander=None)` par défaut (sinon « none » = FLAT couperait la désaccentuation).
  Couleur à l'oreille (Clément) : `_cp(air=dB, lp=Hz)` → EQ FIR 63/125 points après démodulation (`self.eq`, une
  par voie) : ENS +4 dB d'aigus (« beaucoup plus d'air »), ENC plat, ENR / ENR 1.2 passe-bas 10 kHz (« coupe haut »).
  Pilote : `ChannelDemod._watch_pilot` (FFT 8192 du FM démodulé, pic 15–100 kHz > 20 dB au-dessus du bruit →
  `self.pilot` = (Hz, dB)) → colonne « Pilote / données » (écoute) et libellé du temps réel. **Batterie : non
  décodée** (protocoles Wisycom « analogue / digital battery data », pilotes Sennheiser / Shure non publiés) ;
  piste = rétro-ingénierie sur des enregistrements IQ à niveaux de pile connus, sans garantie.
  **HackRF Pro** (choix de Clément) : d'après Great Scott Gadgets, 8 bits jusqu'à 20 MS/s comme le One, mode 16 bits
  (ENOB 9–11) à débit plus bas ; outils `hackrf_*` a priori identiques — à vérifier à réception.
- **SDR choisi par Clément : SDRplay RSP1B** (14 bits, 1 kHz – 2 GHz, 10 MHz). V8 : genre `sdrplay` dans
  `SDR_KINDS` via rx_tools (`rx_power` = clone rtl_power, `rx_sdr` IQ CS16 → `ci16_le`) au-dessus de SoapySDR +
  SoapySDRPlay3 + API SDRplay ; adresse « sdrplay » / « rsp1b:<série> ». **Jamais testé avec un vrai RSP1B** (gain
  `-g` global supposé, débits 4,8 / 9,6 MS/s supposés acceptés) : demander à Clément son diagnostic au 1er essai.
- **V8 SDR (branche `v8-sdr`), idées de Clément** : priorité WiNRADiO et HackRF ; **démodulation** d'une ou plusieurs
  fréquences suivies (écouter un canal : FM large / étroite, AM) et **companders des marques** pour écouter un micro
  analogique proprement. À savoir : les companders (Sennheiser HDX, Shure, Wisycom…) sont propriétaires et non
  publiés → on ne peut faire qu'une approximation (expanseur 2:1 générique réglable) ; les systèmes numériques
  (ULX-D, Axient D, EW-D/DX, 6000, Spectera, Wisycom numérique) ne s'écoutent pas (codecs propriétaires, AES-256).
  Un tinySA ne démodule pas en audio : il faut un SDR (flux IQ).
- **Plus tard (demande de Clément, pas maintenant)** : d'autres appareils de mesure que le tinySA (SDR type RTL-SDR /
  HackRF / Airspy, autres analyseurs…) → isoler une interface « appareil » (balayage → F, L) derrière `TinySA` /
  `ScanWorker` pour en brancher plusieurs.
