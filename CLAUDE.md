# TinySA Monitor — contexte pour Claude Code

Application Windows (un seul fichier : `tinysa_monitor.py`, ~7 600 lignes) pour tinySA Ultra : spectre en direct +
monitoring de 100+ fréquences, pensée pour la coordination HF en festival. Version courante : **8.0.3** (branche `refonte-8.1` : **8.1.0 « RF Technical Monitor »**, pas encore publiée).
Stack : Python 3.12/3.13, PySide6, pyqtgraph, numpy, pyserial. Compilée en .exe avec PyInstaller (`build.bat` ou le
workflow GitHub Actions `.github/workflows/build-exe.yml`).

## Qui / comment répondre
L'utilisateur (Clément) est technicien son/HF/AV en festivals (utilise des logiciels de coordination : EazyRF, WWB, WSM ;
« le logiciel de coord » = EazyRF, fichiers `.ezrf3` / `.lst4`). **Depuis le 25/11/2026 (Clément)** : EazyRF peut être cité
ici et dans les docs (manuel, README) **comme WWB ou WSM** — de façon neutre, pour la compatibilité des fichiers ; toujours
AUCUNE comparaison « comme EazyRF » ni nom de ses fonctions. 7.68.1 : aussi dans les textes de l'appli (« Importer un plan
EazyRF », « Plan EazyRF suivi »…). Il parle un français
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
**Quota de minutes (épuisé le 10/11/2026 : ~1 660 min de machine en 10 jours, une minute Windows compte double)** :
`concurrency` (un push annule la compilation en cours de la même branche, jamais sur main) ; `paths-ignore` (CLAUDE.md,
README, apercu/) ; job `gate` : sur main, aucune compilation si la release `v<APP_VER>` existe, sinon compilation +
auto-test + release SANS tests ni captures (commit déjà testé sur ui-validation).
**Regrouper les modifs en peu de pushs.**
Depuis le conteneur Claude, `gh run view <id>` montre les annotations, mais les journaux et artefacts (stockage Azure)
sont bloqués par le proxy. Sous Windows, **ne pas** lancer Qt en `offscreen` : il n'y a aucune police (mesures ×2).

## Branches (depuis 8.0.0, 26/11/2026)
- **Une seule version** : `ui-validation` (pré-release `test-ui-validation`) -> `main` (release `v<APP_VER>`). La V8 (SDR)
  a été fusionnée en 8.0.0 à la demande de Clément (« on passe en V8 ») AVANT son essai avec un vrai SDR : les fonctions
  SDR sont marquées **« bêta »** (mode du menu, sous-menu SDR, partie E du manuel) jusqu'à ce que `docs/passage_v8.md`
  soit coché. En mode 📟 tinySA, l'appli se comporte comme la V7.
- `v8-sdr` est figée (historique) ; `sync-v8.yml` supprimé ; `kit-sdr.yml` suit `ui-validation`.
- Le code SDR est encore écrit « façon V8 » : ajouté en fin de sections et branché par des ENVELOPPES (fonctions V7
  remplacées en fin de fichier : `_collect_config`, `_apply_config`, `closeEvent`, `SoundOut.play`,
  `SettingsDialog.__init__`, `MapScene`…) et ses traductions dans `lang_en_v8.py`. Prévu : refonte en 8.1 (modules,
  enveloppes repliées dans le vrai code) sur une branche à part, publiée seulement après un essai de Clément.
  Historique : de la 7.10 à la 7.68, la V8 n'avait pas le droit de toucher aux lignes de la V7 (conflits de synchro) ;
  cette règle ne s'applique plus.

## Organisation du fichier
- **Refonte 8.1 (branche `refonte-8.1`, publiée seulement après un essai de Clément)** — étape 1 faite : la section PURE
  est dans **`tsm_core.py`** (avec MIN_PTS, RBW_LIST, HYST et ses imports), `tinysa_monitor.py` l'importe nom par nom
  (`from tsm_core import (...)`, chemin du fichier ajouté à `sys.path` pour les tests qui le chargent par son chemin).
  Avant : la V8 rebranchait après coup des noms PURE (`USER_KEYS`, `user_doc`, `user_apply`, `WEB_VIEWS_HIDDEN`) —
  repliés dans tsm_core (un rebranchement dans tinysa_monitor ne serait plus vu par les fonctions du cœur : ne JAMAIS
  réaffecter un nom du cœur depuis l'interface, seulement modifier en place). Les tests lisent le code par
  `tests/_src.py` (`source()` = tinysa_monitor.py puis tsm_core.py).
  Étape 2 faite : PLUS AUCUNE enveloppe `_v7_…` / `_v8_…_s0`. Chaque méthode enveloppée est devenue, dans sa classe,
  `<méthode>_base` (le code V7) + `<méthode>` (appelle la base puis la partie V8, dans le même ordre qu'avant) :
  MainWindow `_apply_config_base`, `_collect_config_base`, `_close_base`, `_build_docks_base`, `_panel_docks_base`,
  `_set_level_base`, `_user_profile_load_base`, `_layout_base` (+ `_layout_mode` = disposition du mode, `layout_standard`
  = ramène les écrans puis `_layout_mode`), `_late_layout` -> `_late_layout_v8` ; MapScene `_scene_state_base`,
  `_keys_all_base`, `_label_base`, `_refresh_base`, `_update_links_base`, `_node_dropped_base`, `_node_open_base` ;
  `SoundOut._play_base` ; `SettingsDialog._init_base`. `set_rf_mode` et le menu du mode intègrent les écrans.
  Reste (étape 3) : ~64 fonctions V8 posées sur MainWindow par `MainWindow.x = _v8_x` (à regrouper en vraie classe /
  module SDR), découpage de l'interface en modules, tests plus rapides.
- **FAIT (branche refonte-8.1, 8.1.0) : renommage + nouvelle DA.** Tous les textes (code, lang_en, manuels, README, CI,
  build.bat, kit Pi, kit SDR) : « RF Technical Monitor », exe `RF-Technical-Monitor.exe`, dossiers
  `%APPDATA%\RFTechnicalMonitor` / `Documents\RF Technical Monitor` (`DOCS_ROOT`). `migrate_legacy` (au chargement du
  module) : config COPIÉE de `LEGACY_CFG_DIR`, Documents RENOMMÉ (repli : l'ancien reste utilisé), chemins de la config
  réécrits (`_swap_paths`), note dans `migration.txt` (test dans smoke_test6). Clé Run : « RFTechnicalMonitor », l'ancienne
  « TinySAMonitor » comptée puis retirée (`windows_startup_on`, `set_windows_startup`, recalée au démarrage). Formats
  internes GARDÉS (`.tsashow`, `.tsauser`, « tinysa-show », service Pi `tinysa-relais`, `tinysa_relais.py`). Icône
  maison `assets/make_icon.py` (Pillow) : carré graphite, trace menthe #4fd1c5, marqueur ambre #ffb300, seuil corail ;
  `APP_ICON_PNG64` (favicon + logo de la page de connexion). Couverture du manuel « tinySA Ultra et SDR ».
- **Nouveau nom à la 8.1 (Clément, 26/11/2026) : « RF Technical Monitor »** (sigle RFTM : le clin d'œil à « RTFM » est
  voulu, Clément : « je kiffe »). Raisons : depuis la V8 le logiciel n'est plus que tinySA, et « tinySA » est le nom du
  produit d'Erik Kaashoek (pas d'affiliation à laisser croire). « FreqWatch » écarté (logiciel RTL-SDR existant).
  Recherche web rapide : pas de logiciel de ce nom (PAS une vérification de marque). À faire avec la 8.1 : APP_NAME,
  titres, exe `RF-Technical-Monitor.exe` (workflow, build.bat, liens du README), page web, rapports, alertes, manuel,
  lang_en ; MIGRER sans perte : `%APPDATA%\TinySAMonitor` et `Documents\TinySA Monitor` (config, shows, journaux,
  profils), clé de démarrage Windows « TinySAMonitor », verrou d'instance, garde ; texte « compatible tinySA Ultra »
  gardé. Dépôt GitHub : son nom reste à Clément (renommer = redirection automatique de GitHub). Dépôt PRIVÉ : le passer
  open source (public + licence) est une décision de Clément, pas encore prise.
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
- Intermod : tolérances par type de produit (`im_class` : 2tx3 / 3tx3 / 5 / 7, `IM_TOL_PRESETS`, défaut
  100 / 50 kHz (tolérances courantes) ; 5ᵉ / 7ᵉ = notre choix). `guard` de `im_scan` = float ou dict.
  Les « doit rester libre » ne sont pas des émetteurs. Niveau « mesuré » masqué quand la cible est un « doit émettre »
  qui émet (on mesurerait sa porteuse). Clément trouvait l'ancien calcul (±300 kHz partout) « tout faux » face à
  Wisycom Manager : **demander sa liste Wisycom pour comparer** avant de toucher encore aux règles.
  Verdict « calcul seul · rien mesuré » (avant « à risque ») : le calcul dit que ça tombe dessus, le niveau mesuré
  est sous les seuils ; seules les combinaisons qui tombent dans la tolérance sont listées (message en tête).
  Gravité `im_verdict` (PURE) : 🔴 mesuré ≥ seuil occupé, 🟠 ≥ seuil faible, 🟡 IM3 2 TX non mesuré, ⚪ le reste ;
  triées du plus grave au moins grave (`sev`). Tolérance 0 (dict) = type ignoré ; préréglage
  « 2A − B seulement ». Sur le plan de Clément (558/574/606/614/646/478) : propre en 2A − B seul, conflits en
  A + B − C et IM5 pile dessus → les logiciels de coord ne comptent probablement pas ces produits (non vérifié).
- Vérifier le plan (🧮, Outils, `PlanCheckDialog`, demande de Clément) : PURE `pf_check` (écart entre
  porteuses `PF_SEP` bord à bord + intermod des émetteurs selon tolérances ; réserves protégées sans émettre ;
  produits larges → toutes les fréquences recouvertes), `pf_issue_text`, `pf_suggest` (pré-filtre vectorisé :
  écart, produits des autres sur la candidate, 3ᵉ ordre impliquant la candidate ; puis `pf_check` exact ;
  « aucun nouveau problème pour les autres »), `pf_orders` (3 et 5 seulement : le 7ᵉ = 200 M combinaisons à
  30 TX → « trop gros » silencieux avant). « Remplacer »
  → `MainWindow.set_watch_freq` + journal « NOUVELLE FRÉQUENCE ». Corrigé au passage : `im_scan.near_t` choisit
  la cible la plus proche qui n'est pas un émetteur du produit (un produit large était jeté s'il touchait d'abord
  un de ses émetteurs).
- **Règles d'intermod (7.7.0, demande de Clément : « on comprend pas »)** : `IM_TOL_PRESETS` = (nom, tolérances,
  explication) : 🟢 Standard (2A − B ±100 kHz, PAR DÉFAUT — le plan Wisycom réel de Clément passe), 🟡 3ᵉ ordre
  complet (+ A + B − C ±50), 🟠 Prudent (+ 5ᵉ), 🔴 Très prudent ; `IM_TOL_CUSTOM` « ✏ Personnalisé » (choisi tout
  seul si on touche une tolérance) ; `fill_rules_combo` (Qt), `im_rules_text` (PURE, phrase « On vérifie : … »).
  `pf_check` / `pf_suggest` : `max_tx` déduit des tolérances. Résumé de la vérification par type de problème.
- **Filtre récepteur (7.8.0)** : le plan Wisycom de Clément (470.2 471.3 478 558 574 606 614 646 660.95 661.45)
  donne « 0 IM » dans le logiciel de coord avec son profil MRK980 : 2 TX 100, 3 TX 50, Séparation 500, **Filtre 32 MHz**, Incrément
  0,005 (MTK952 : 0,025). Interprétation (déduite, pas lue dans une doc) : un produit ne gêne une fréquence que
  si TOUS ses émetteurs sont à ± filtre / 2 d'elle → avec ça, 0 problème ; sans filtre : des A + B − C.
  `pf_check(..., filt)`, `pf_suggest(..., step, filt)` (pré-filtre cohérent, test « rapide = brute » avec filtre),
  IntermodDialog `filt_spin` (cible connue seulement). Préréglage 1 = « 🟢 Standard (2 TX ±100 · 3 TX ±50) »,
  puis « ⚪ Simple » (2A − B). `self.plan_opts = {sep kHz, filt MHz, step kHz}` dans config.json.
  Diagnostic auto (liaison perdue / erreur) : plus de `QTimer.singleShot(0, lambda)` (crash.log 7.6.2 « access
  violation » dans `dump_diag`) → `self._diag_pending`, écrit par `_alarm_tick` dans un try.
- **Profils d'appareil (7.9.0, Clément : « après Wisycom c'est très sélectif, il faut des machines moins sélectives
  Shure, Sennheiser… »)** : PURE `RX_PROFILES` (clé, nom, {sep, filt, step, tol}, explication) : wisycom (= vrai profil
  de Clément), senn_dig, senn_ana, shure_dig, shure_ana, iem (+ 5ᵉ ordre) ; **seul Wisycom vient d'un vrai
  profil, les autres sont des valeurs de départ NON vérifiées** (depuis 7.27 : tirés de sa bibliothèque `.lst4`). `rx_profile(key)`.
  `pf_check` / `pf_suggest` acceptent sep / filt / tol PAR FRÉQUENCE (listes, `_pf_vec`, `_pf_tols`) : écart d'une
  paire = le plus grand des deux, filtre et tolérances = ceux de la fréquence touchée (supposition raisonnable, pas
  lue dans une doc) ; pas des propositions = celui de l'appareil de la fréquence. `w["rx"]` (config + shows via
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
  - **Profils d'appareil** : filtres donnés par Clément : evolution 16, SLX 16, PSM 16, AD 32, QLX-D 32
    (ULX-D supposé idem) ; ADT inconnu (0 = prudent) ; `d["src"]` (valeur courante | guess | perso). Profils perso :
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
  reste celui de nikharju. Formats de **listes de fréquences** (WWB / WSM / Wisycom / logiciel de coord) : toujours pas de vrai
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
- **7.26.0 (Clément : « refaire le manuel, vraiment hyper détaillé, avec tout le processus » ; « pousser le tuto dans le
  soft, tout hyper détailler, comme à des gens qui n'y connaissent rien »)** :
  - **Tutos** : PURE `TOURS` (ecran, show, spectre, coord, scenes, live : clé, titre, minutes, description) +
    `GLOSSARY` (≈ 38 mots, explication pour débutant) + `glossary_find` (sans accents / casse). `tour_steps(o, key)` →
    étapes `(widget, titre, c'est quoi, pourquoi, comment, action)` ; action = (texte, nom de méthode MainWindow) →
    bouton « Fais-le ». `TourDialog` (3 rubriques, note si la partie est cachée par le niveau d'affichage, 📚
    Lexique), `TourChooser` (`start_tour()` sans clé), `GlossaryDialog` (`open_glossary`, recherche). ☰ Plus ›
    Aide : Tutos + Lexique. **Ajouter une étape = sa traduction dans lang_en (titre + 3 textes + bouton)** ; gui_reel
    parcourt les 6 tutos et vérifie que chaque action existe ; gui_en scanne chaque étape en anglais.
  - **Manuel** reconstruit par `tests/make_manual.py` (idempotent) : 5 parties (A commencer, B comprendre la HF, C le
    festival pas à pas, D référence des outils, E aide), 39 chapitres ; nouveaux chapitres dans
    `docs/src/nouveaux_fr.html` / `nouveaux_en.html` (blocs `<!--CH id|Titre-->`) ; les chapitres de référence restent
    éditables directement dans `docs/manuel.html` / `manual_en.html` ; le lexique du manuel est GÉNÉRÉ depuis
    `GLOSSARY` (+ lang_en) ; renvois « chapitre N » renumérotés. **Après toute modif : `python tests/make_manual.py`
    puis `python tests/make_pdf.py`.** Nouveau chapitre : l'ajouter dans `PARTS` du script.
- **7.26.1 (Clément : « ça m'affiche plus le scan continu après avoir fusionné mes calques dans Coordonner »)** : une
  scène qui avait un scan gardé devenait un « lieu » → `view_sites` n'y traçait que le direct des tinySA RATTACHÉS
  (`dev_scenes`, réglage expert) → rien en direct. Corrigé : si aucun tinySA n'est rattaché à une scène, `view_sites`
  renvoie None (direct de tous) et l'étiquette dit « scan gardé en pointillés ».
  **7.26.2 (Clément : « j'avais mal assigné le tiny, il faut que ce soit intuitif »)** : bandeau `site_bar` au-dessus
  du spectre (`update_site_bar`, appelé par `update_site_curve`) quand la scène regardée n'a aucun tinySA rattaché :
  qui surveille quoi + « 📡 Le Nᵉ tinySA est ici » (`set_dev_scenes(d, [scène])`), « 🌐 Tout le site », ⚙ ; « 📡 nom »
  dans l'arbre dès qu'un rattachement existe (plus seulement en expert) ; DevicesDialog : « Surveille : … » et
  « ∅ Aucune scène (tout le site) » par tinySA.
  **7.26.3 (Clément : « filtre 32 / 16 MHz, c'est pas le contraire ? Wisycom 32 MHz est bien plus sélectif qu'un SLX
  16 MHz »)** : nos textes confondaient « filtre » et qualité. Dans le calcul, le filtre = tranche qui entre dans le
  récepteur (quels émetteurs comptent) ; la ROBUSTESSE (linéarité, IP3, sélectivité canal) = écart + tolérances. Le
  profil SLX avait les tolérances de Wisycom (100 / 50) avec un filtre plus étroit → plans SLX jugés plus gentiment :
  passé à `_TOL_LARGE` (150 / 75, valeurs de départ). Textes corrigés (aide filtre, lexique, bulles, manuel).
  ~~À demander à Clément : ses profils~~ → FAIT en 7.27 avec sa bibliothèque `.lst4` (1 217 appareils) : ne
  plus les lui redemander. Restent « valeurs de départ » (src guess) : senn_ana, shure_ana, shure_adt (familles
  génériques ; un modèle précis s'importe depuis la bibliothèque, mode expert).
- **Retours terrain de Clément (31/10/2026)** : vue Terrain ✅, son (sortie choisie) ✅, 👋 Identifier ✅, ntfy ✅.
- **7.27.0 (Clément : bibliothèque d'appareils, « ça sonne beaucoup », compteur réseau, coord simple, manuel sans « non
  vérifié »)** :
  - **📚 Bibliothèque d'appareils** : PURE `parse_lst4` (XML « Appareils.lst4 » : Description, Départ / Arrêt MHz, Incrément,
    Tolérance / Tolérance3TX / Tolérance5e et Séparation en kHz, Filtre MHz, FréqImage), `rx_library_find`,
    `rx_from_library` ; `RX_LIBRARY` (fichier à part à côté de config.json : `rx_library`,
    `set_rx_library`) ; `RxLibraryDialog` (import, recherche, « Ajouter à mes profils » → profil perso (src « valeur courante »)
    avec `lo` / `hi`) ; `CoordDialog._range_from_prof` (la plage suit l'appareil). **Le fichier de Clément (1 217
    appareils) n'est PAS dans le dépôt** ; test sur `tests/data/appareils_essai.lst4` (inventé).
    `RX_PROFILES` recalés sur ses valeurs (SLX ≠ SLX-D, PSM 900 ≠ 1000, EW-D tolérances 0…) ; `_TOL_*` ont « 5 » = 50 kHz
    (le plan Wisycom de Clément reste à 0 problème avec le 5ᵉ ordre et le filtre 32 MHz). Pas encore géré : la
    fréquence image (FréqImage 10,7 MHz des analogiques).
  - **Alarmes** : `SOUND_DEFAULT` + `repeat` (30 s, `ALARM_REPEATS`, 0 = jamais → `AlarmBook.due_repeat`), `confirm`
    (CONFLIT seulement si occupé depuis ≥ 3 s : `w["since"]`), `occ_beep` (bip « occupé » coupé par défaut : c'était
    le bruit le plus fréquent) ; `snooze` / `snooze_until` / `snooze_btn` (🔕 5–60 min, PURE `snooze_left`) ; réglages
    dans ⚙ Son. smoke_test4/5 forcent `confirm=0, repeat=10` pour garder leurs vérifs.
  - **🌐 Compteur réseau** : `TinySA.rx_bytes` / `tx_bytes` / `rtt` (1er octet), `_net_tick` (2 s) → `net_text` (PURE)
    à côté de la version (`_info_base`, `_net_txt`, `_show_info`).
  - **Coord simple** : `coord_note()` en tête de Coord / Plan / Intermod / Secours (« utilise un vrai logiciel de
    coordination pour le plan »).
  - **Manuel** : chapitre « Ce qui n'est pas vérifié » retiré (`DROP` dans make_manual.py), plus de « non vérifié »
    ni de prénom dans le manuel / l'appli (le suivi reste ICI). Profils : tableau des valeurs courantes.
- **7.28.0 (Clément : « trop fouillis, usine à gaz », « un manuel beaucoup plus pro », sans « non testé »)** — choix validés
  avec lui : garder l'écran (parcours, ☰ Plus), tout dans ⚙ sauf les seuils, emojis sur les boutons clés seulement :
  - **Plus de panneau Réglages** (`dock_set` supprimé, `LAYOUT_VER` 4) : ses sections sont des pages `set_pages`
    (detect = seuils + alarmes, bands, measure, dev2, country) garées dans `set_park` (widget caché) et **empruntées**
    par `SettingsDialog` (liste `nav` à gauche + `tabs` à onglets cachés, `keys`, `show_page(clé)`, rendues par
    `_give_back` sur `finished`) : les widgets vivent toujours dans la fenêtre (config, `_sync_cfg`…).
    `SETTINGS_PAGES`, `open_settings(clé | n°)`. `open_section` = sans effet (config `sections` gardée).
  - **Barre des seuils** `thr_bar` au-dessus du spectre : « Occupé au-dessus de » thr_spin + Auto, `weak_chk`
    « Faible dès » + weak_spin, « TX absent après » absent_spin, ⚙ → page detect ; cachée en ultra simple.
  - **Barre du spectre** : Vue, 📶 Bandes, ⚡ Points, 🔍 Zoom, Max hold, Reset, `more_spec_btn` « ⋯ » → `spec_more`
    (repères, marqueurs, rémanence, capture, Scènes, légende, `ref_row`) ; config `spec_more`.
  - Boutons secondaires de la liste sans emoji (`_plain_btns`, retirés APRÈS `_install_tips`).
  - **Manuel** (`make_manual.py`) : couverture avec l'icône, CSS sobre (bloc `/*pro*/`), titres sans emoji
    (`clean_title`), captures de la vraie appli `docs/img/<fr|en>/*.jpg` intégrées en base64 (`FIGS` / `SHOTS` ;
    `python tests/make_manual.py --shots tests/captures tests/captures_en` après gui_reel + gui_en).
- **7.28.1 (retours de Clément sur 7.28)** :
  - Bug « des traits entre les bandes » dans les scans par lieu : PURE `scan_gaps` (trou = écart > 4 × le pas des DEUX
    côtés, donc deux bandes à pas différents ne font pas de faux trous) / `gap_nan` (NaN dans les trous, tracé
    `connect="finite"`) ; `merge_scans` coupe chaque scan en morceaux par bande avant d'interpoler (avant : il
    interpolait par-dessus le trou). Utilisé par `SitesDialog.redraw` (courbes par lieu + fusion) et `update_site_curve`.
  - **📻 Appareil par groupe (facultatif)** : clé `rx` d'un groupe (config `scenes` + shows) ; `rx_of(w)` = appareil
    de la fréquence sinon de son groupe sinon "" → Vérifier le plan (`_params`, colonne Appareil) et Coordonner
    (`compute`) ; clic droit sur un groupe / une scène › « 📻 Appareil de ce groupe » (`set_group_rx`, `_cur_rx`) ;
    nom court dans l'arbre ; `CoordDialog._prof_from_group` (scène + groupe choisis → leur appareil) et `add` ne
    pose `w["rx"]` que s'il diffère de celui du groupe. `group_row(scene, group)`.
  - make_manual : `clean_title` retire aussi les « () » vides laissés par un emoji.
- **7.29.0 (Clément : « plusieurs profils dans un groupe, pour faire de la coord entre appareils »)** : un groupe a une
  LISTE d'appareils (`g["rx"]` = liste ; ancien format chaîne relu par `group_rxs(g)`) ; `rx_of(w)` = le sien, sinon le
  1er du groupe ; menu à cases « 📻 Appareils de ce groupe » (`toggle_group_rx`, `set_group_rx` = un seul / aucun,
  `_cur_rxs`, `_set_rxs`). PURE `pf_fill_lots(lots, …)` : lots {n, sep, tol, filt, lo, hi, step} cherchés dans l'ordre,
  chaque trouvée rejoint le plan avec les règles de son appareil (test : 5 QLX-D + 4 PSM 1000 + plan Wisycom = 0
  problème). `CoordDialog` : encadré « Plusieurs appareils » (`lots`, `add_lot`, `del_lot`, `_show_lots`, `_lot_now`,
  `_lot_profile`) ; groupe à plusieurs appareils → un lot par appareil préparé ; `found` = [(lot, MHz)] ; `add`
  numérote par préfixe et ne pose `w["rx"]` que s'il diffère de `rx_of`.
- **7.30.0 (Clément : « scans par lieu, ça manque de fonctionnalités » → tout sauf « le niveau d'une fréq partout »)** :
  PURE `site_scan_info` (scène, date, plage, pas, bandes, `dur`), `fmt_duration`, `_fmt_ts` (import datetime LOCAL :
  la section PURE n'a pas datetime), `site_rename` (reste rangé dans sa scène) / `site_move`, `diff_spectra` (A − B
  seulement là où B a mesuré), `scene_timeline`, `only_here` (≥ 10 dB au-dessus de la fusion des AUTRES scènes),
  `_svg_multi` (axe coupé : bandes réunies, côte à côte, coupure grise), `SITE_COLORS`, `site_report_html` (sommaire,
  fusion, chaque lieu + signaux + « vus seulement ici », dans le temps). Durée des scans : `site_scan_doc(..., dur=)`
  (gardée par `site_scans_norm`), `_mh_t0` (début du max hold global, posé au 1er balayage après remise à zéro),
  `_site_mh_t0` (par scène, terrain). `SitesDialog` : liste (cases = afficher / fusionner, `_hidden`), `info`,
  Renommer / Ranger dans une scène / Supprimer (`do_rename`, `do_move`), onglets `tabs` : Spectres, Comparer
  (`cmp_a/b`, `cmp_plot`, `diff_plot`, `cmp_txt`), Signaux du lieu (`pk_thr`, `pk_only`, `pk_table`, `add_ext` =
  émetteurs extérieurs « Ext. f » SANS statut → pris en compte par Vérifier le plan / Coordonner, sans alarme,
  `copy_peaks`), Dans le temps (`tl_scene`, `tl_plot`, `tl_txt`) ; `report(path)` → `rapports/etude_site_*.html`.
- **7.31.0 (Clément : « des profils IP pour les tiny en réseau, le Pi change d'IP selon le Wi-Fi, et que ça s'enregistre
  avec le show »)** : PURE `net_profiles_norm` ({name, addr} réseau valides, noms uniques, ≤ 30), `net_profiles_merge`
  (PC + show, le show gagne à nom égal), `net_host_port`, `net_profile_name`. `self.net_profiles` (config
  `net_profiles` ; **SHOW_KEYS + `net_profiles`, `net_addr`, `port_net`, `dev2`** : le 2ᵉ tinySA suit maintenant le
  show, test_v7 mis à jour). `net_test(addr)` (connexion TCP 1,5 s : répond / nom introuvable / ne répond pas).
  `NetProfilesDialog` (table Nom / Adresse / Test, Ajouter, Supprimer, 🔌 Tester, Utiliser pour le 1er / 2ᵉ ; `save`
  sur `finished`), `open_net_profiles` (entrée `NET_ITEM` des ports, ⚙ › Connexions, ☰ Plus › 🔗, bouton à côté de
  l'adresse du 2ᵉ), `use_net_addr`. `refresh_ports` liste chaque adresse « 🌐 nom — adresse » (la choisie en tête),
  `_dev2_ports` aussi (« adresse  · nom », relu par `_read_dev2`). L'ancienne saisie QInputDialog a disparu.
- **7.31.1 (Clément : « nouveau show, un scan reste sur le spectre alors que Scans par lieu est vide »)** : `_sites_tick`
  réenregistrait toutes les 30 s le max hold EN MÉMOIRE (`site_mh`) de chaque scène comme scan gardé, même après
  suppression ou nouveau show. `forget_site(scène)` (vide `site_mh`, `_site_mh_t0`, `_site_base`) appelé par
  `SitesDialog.delete` ; `_sites_tick` oublie les scènes qui n'existent plus ; `new_show` → `clear_show_data` : liste,
  scènes, scans par lieu, max hold des scènes, `dev_scenes`, référence (aussi `REF_PATH`) et max hold vidés.
  Aussi en 7.31.1 : ⚙ Réglages ne fait plus `page.show()` sur les rubriques empruntées (elles s'empilaient sur
  « Général », capture de Clément) ; **Vue** propose « ＋ Nouvelle bande à balayer… » (`NewBandDialog`,
  `new_band_dialog`), « Gérer les bandes… » et les bandes non balayées « ○ … » (données `__add__` / `__manage__` /
  `on:<id>` gérées en tête de `on_view_changed`, `_view_prev`, `show_band`). **Fluidité** (Clément : 40 % de processeur,
  3 000 pts, rémanence 10) : mesuré en démo, ~80 % du temps = dessin (`drawPath`) → courbes NON lissées par défaut
  (`self.smooth`, `set_smooth`, config `smooth`, case ⚙ › Général), rémanence en `PlotDataItem` clip + downsampling,
  `on_partial` redessine au plus 5 fois / s ; démo : 113 % → 56 %. Clément : « ça le faisait pas avec mon autre écran »
  et « j'ai relancé ça va mieux » (écran plus grand / mise à l'échelle = plus de pixels à dessiner).
- **7.31.2 (Clément : « choisir la bande de fréq à exporter vers le logiciel de coord », « scans par lieu dans ① ou ②, pas ③ »)** :
  PURE `scan_crop(F, *cols, lo, hi)` ; widget `RangeBox` (tout / zone affichée / chaque bande / appareil de la
  bibliothèque avec `lo`/`hi` / à la main ; `values()` → (lo, hi) ou (None, None) ; `select`) dans `ExportScanDialog`
  (`lo`/`hi` pas gardés dans `export_prefs`), `SitesDialog.export` (« Plage exportée ») et `ScanConvertDialog._write`.
  Parcours : ① Scanner le lieu devient un menu (« ▶ Scanner ici », « 📍 Scans par lieu ») ; retiré de ③.
- **7.32.0 (Clément : « Suppr pour enlever partout, et un undo / redo »)** : PURE `UndoStack` (track(état, sig) / back
  / fwd / resync, limite 60). MainWindow : `undo_stack`, `UNDO_KEYS` (watch, scenes, bands, statuses), `_undo_state`
  (JSON de `_collect_config(True)` + `site_scans` en liste ; signature = JSON + (nom, scène) des scans, PAS leurs
  données : le scan continu des scènes ne crée pas de retour toutes les 30 s), `undo_track` (chaque seconde dans
  `_alarm_tick`, et juste après une suppression), `_undo_restore` (collect → update → `_apply_config`, `_undo_busy`),
  `undo` / `redo` (Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z ; ☰ Plus en tête ; aussi dans `SitesDialog`). **Suppr** :
  `del_key(widget, fn)` = filtre d'événements `_DelKeyFilter` (un QShortcut Delete n'est jamais déclenché sur les
  vues d'éléments) sur la liste (`del_watch`), l'arbre (`delete_selected_layer`), les bandes (`del_band`, garde une
  bande), Scans par lieu, adresses réseau. gui_reel : envoyer les touches au tableau (une fenêtre non modale laissée
  ouverte par un test précédent peut être la fenêtre active).
- **7.33.0** : import des plans `.ezrf3` (fichier / copier-coller) et règles de calcul du logiciel de coord (voir « Formats de
  fichiers »). Filtre = ± la valeur (avant : ± filtre / 2) → plus sévère qu'en 7.32.
- **7.34.0 (Clément, en plein show : « je suis pas en diversity, ça décroche sur le soft alors qu'aux récepteurs c'est
  ok »)** : **🔀 Diversity maison** : `dev2["div"]` (case `div_chk` dans ⚙ › 2ᵉ tinySA, config + shows via `dev2`),
  `diversity_on()` (2 tinySA ET case ET pas `multi_site`) → `band_devices` renvoie −1 (les deux balayent tout, colonne
  « 1 + 2 ») ; `on_sweep` → `_div_feed` : `div_buf` {bande: {tinySA: (F, L, t)}} → PURE `diversity_merge` (meilleur
  niveau point par point des balayages récents, `stale` = max(10 s, 2,5 cycles), grilles différentes interpolées,
  `src` = gagnant) ; `div_src` → `seen_by` « meilleur : nom » ; `update_dev2_label` : part de chaque tinySA (PURE
  `diversity_share`). Testé en faux Qt (smoke_test5) et en démo à 2 tinySA simulés (gui_reel) ; **jamais avec deux
  vrais tinySA sur deux antennes** (Clément n'avait qu'un tinySA au 05/11/2026).
- **7.35.0 (Clément : « une multitude de scènes, il faut pouvoir mettre beaucoup de tiny, pas que 2 »)** : **jusqu'à
  8 tinySA** (`MAX_DEVS`). N° FIXES : 0 = 1er (`port1()`), 1 = 2ᵉ (`dev2`, inchangé pour la V8 et les configs), 2… =
  `self.devx` [{on, addr, name, offset}] (PURE `devx_norm`, config + SHOW_KEYS « devx »). `dev_slots()` → [(n°, adresse,
  offset)] des tinySA en service, `dev_list()` (n°), `ndev()` = combien, `dev_offset(d)`, `set_dev_offset`, `live_mask()`
  ([bool] × 8 : en service ET en ligne ; n° inconnu de `dev_live` = en ligne), `multi_site_on()` (= `multi_site(...,
  MAX_DEVS, live_mask())`), `resolve_addr` (nom d'adresse enregistrée → adresse). PURE `dev_ord(d)` (« 1er », « 2ᵉ »,
  « 3ᵉ »… ; lang_en « 3ᵉ »→« 3rd »…). `dev_live` = 8 cases. Workers : `w.slot` = n° (⚠ `w.dev` = l'objet TinySA) ;
  `identify_device` / `number_device` cherchent par `slot`. `CALIB_IDS` = un id par tinySA (−3…−10) : la calibration
  cale TOUS les autres sur le 1er. Zoom : `zoom_dev` sinon le 1er vivant. Web Terrain / Chasse : la page envoie le
  RANG dans `dev_list()` (pas le n°). UI : tableau `devx_table` (Actif, Nom, Adresse, Offset) + `devx_add` /
  `devx_del` (Suppr ; les n° suivants descendent, leurs `dev_scenes` aussi), désactivés pendant la surveillance ;
  rubrique « Plusieurs tinySA et noms ». Testé : faux Qt (smoke_test5 : 4 tinySA, répartition, offsets, scènes, retrait)
  et démo à 4 tinySA simulés (gui_reel) ; **jamais avec plusieurs vrais tinySA**. Le relais Pi sert UN tinySA.
- **7.36.0 (Clément : « une page web spéciale tech où on peut manager le serveur, comme sur Ontime, mais pas l'accès
  à tous »)** : vue web **🛠 Tech** (`WEB_VIEWS` « tech », cachée par défaut). Sécurité : mot de passe Tech
  `web_cfg["tech"]` (≥ 6, jamais dans les shows, `tech_guard` 5 essais → 5 min) PUIS accord sur le PC si
  `web_cfg["tech_approve"]` (défaut) : `ClientBook.set_tech` / `tech_state` (« pending » / « ok », expire 12 h),
  `WebServer.tech_decide` / `revoke_tech`, routes POST `/tech/login`, `/tech/logout`, `/tech` (PURE `tech_request` :
  run, snooze, ack_all, thr, watch_add / edit / del (clé = kHz), dev_scenes / identify (RANG dans `dev_list()`),
  save), GET `/tech.json` (`get_tech` = `_tech_json`, refait chaque seconde seulement si quelqu'un regarde « tech »).
  MainWindow : files `_web_tech` / `_web_techreq` → `_web_techreq_pending` (QMessageBox NON modale, `_tech_boxes`) et
  `_web_tech_pending` → `tech_do` (message `_tech_msg`) ; `tech_state()`. AlertsDialog : `web_tech`, `web_tech_ok`,
  « 🛠 Retirer l'accès Tech », marques 🛠 / ⏳ dans les connectés. Testé : HTTP (test_alertes, 16 cas dont refus,
  blocage, autre navigateur), Chromium (page Tech, captures `web_tech.png`), vraie appli (gui_reel : accord par la
  fenêtre du PC, commandes appliquées). Pas de HTTPS (réseau de prod seulement).
  **✅ Vérifié en vrai par Clément (09/11/2026) : accès Tech depuis son téléphone, accord sur le PC, commandes : « tout fonctionne ».**
- **7.37.0 (Clément : « 📸 États », plusieurs plans dans un show)** : PURE `states_norm` ({name, keys
  = fréquences actives en kHz}, ≤ 30), `state_off`. `self.states` / `self.state_cur` (config + SHOW_KEYS « states »,
  « state_cur » ; appliqués APRÈS la liste dans `_apply_config`), `w["iso"]` (🔒 toujours active,
  gardé dans `watch`) ; `apply_state(nom)` pose `w["off"]` (+ efface CONFLIT / ABSENT), `w_paused` le respecte (pas
  d'ABSENT), CONFLIT sauté si `off`, `sig_view` « 💤 en pause (état) », `PlanCheckDialog._params` ignore les `off`.
  `_append_watch` ajoute la nouvelle à l'état actif ; `set_watch_freq` garde la fréquence dans ses états ;
  `clear_show_data` vide les états. UI : bouton `state_btn` (menu `_build_state_menu`) dans « Mes fréquences »,
  `StatesDialog` (liste + tableau Dans l'état / 🔒 Toujours, cocher une scène, dupliquer, Suppr), ⑤ + ☰ Plus ②.
  Tech : action « state » + `states` / `state_cur` dans `tech_state`, liste 📸 dans la page.
- **7.38.0** : **🔗 Suivre le plan `.ezrf3`** : case `follow` d'`EzrfImportDialog` (fichier seulement) → `self.ezrf_link`
  {path, mtime, name, status, skip_off} (config + SHOW_KEYS « ezrf_link »), `w["ez"]` = PURE `ezrf_id(scène, groupe,
  nom)` (gardé dans `watch`) ; `_ezrf_tick` (dans `_alarm_tick`, toutes les 5 s, attend 1 s après l'écriture) →
  PURE `ezrf_diff` (add / change / remove) → `EzrfSyncDialog` non modale (cases, Appliquer → `apply_ezrf_diff`, Plus
  tard, Ne plus suivre) ; ☰ Plus › 📋 Liste › « 🔗 Plan suivi… » (`ezrf_follow_info` : vérifier maintenant /
  arrêter). **Plusieurs tinySA sur un Pi** : `relais/tinysa_relais.py --multi` (`install_pi.sh multi`) :
  `find_all_tinysa` / `device_key` (n° de série USB, sinon prise), `serve_multi` (un thread `serve(..., finder=, name=)`
  par tinySA, rescan 5 s), ports retenus dans `~/.tinysa_relais_ports.json` (`load_ports` / `save_ports` /
  `next_port`). Sans `--multi` : comportement inchangé. Testé avec deux faux tinySA (pty) ; **jamais sur un vrai Pi
  avec plusieurs tinySA** (numéro de série USB du tinySA supposé présent, sinon la prise USB sert de clé).
- **7.39.0 (Clément : « on fortifie ? » → « Touuuut !! »)** :
  - **🛡 Garde** : `TinySA-Monitor.exe --garde` (`main()` → `run_guard`, sans Qt) lance l'appli (`_guard_env` : env
    PyInstaller remis à zéro, `TSM_HEARTBEAT` = fichier battement, `TSM_GUARD_RESTART` = 1 sur une relance) et la
    surveille : PURE `guard_action(code, âge du battement, durée)` → stop (code 0 = fermée exprès) / restart (plantée) /
    kill (pas de battement depuis `GUARD_HANG_S` 90 s, ou jamais après `GUARD_GRACE_S` 180 s) ; `guard_delay` (3 s,
    5 min si 5 relances en 10 min) ; PC en veille (boucle en retard) = battement remis à neuf ; journal `garde.log`
    + `log_crash`. Battement `guard_beat()` toutes les `GUARD_BEAT_S` dans `_alarm_tick` (appli figée = plus de tick).
    Relancée → `_late_layout` reprend la surveillance si `festival.was_running` (même sans mode festival ; aussi
    `TSM_RESUME` posé par `relaunch_guarded`, bouton « 🛡 Relancer maintenant sous garde » du `FestivalDialog`).
    `festival["guard"]` (défaut True) → `_startup_cmd` ajoute `--garde`. Test `tests/test_garde.py` (vrai processus
    enfant : plante, se fige, se ferme ; dans la CI). **✅ Vérifié par Clément (09/11/2026, exe Windows 7.50, bouton « 💥 Tester : plantage ») : l'appli se relance bien et la surveillance reprend toute seule.** « 🧊 appli figée » ✅ vérifié le 13/11/2026 (voir 7.52.1). Pas encore essayé : un vrai plantage, la relance au démarrage de Windows.
  - **✅ Prêt pour le show ?** : PURE `ready_checks(info)` (liste {key, level ok|warn|bad|info, title, text, fix =
    méthode de MainWindow}) / `ready_summary` ; `MainWindow.ready_info()` (devs, dernier balayage, fréquences hors des
    bandes balayées, `pf_check` si ≤ 80 fréquences, son, ntfy / Telegram, web, show, `session_cfg["rec"]`, disque,
    garde) ; `ReadyDialog` non modal (`self._ready`, rafraîchi toutes les 3 s, « Régler », 🔊 test, 📨 alerte test) ;
    `open_ready` (⑤, ☰ Plus ②, bouton du mode Show). Petites méthodes pour « Régler » : `toggle_demo_off`,
    `snooze_off`, `open_sound`, `open_settings_files`. gui_reel vérifie que chaque `fix` existe.
  - **🖥 Mode Show** : `ShowModeWindow` (plein écran, `self._show_mode`, `open_show_mode` = ouvre / referme, F10) :
    barre (● SURVEILLANCE / ■ ARRÊTÉE, ▶ / ■, ✔ Tout acquitter = Espace, 🔕 5–60 min, 📸 état, ✅ Prêt ?, 🖥 écran
    suivant, heure, ✖ / Échap), bandeau des alarmes en cours (sinon « ✔ Tout va bien »), tuiles `sig_view` des
    fréquences de `scope_ws()` non en pause (colonnes = largeur / 260, refaites si la liste change). `_hesc` = html.escape.
  - **Endurance** : `tests/endurance.py [minutes]` (vraie appli hors écran, 4 tinySA simulés, page web avec 3 clients,
    états, zoom ; relevés RSS / CPU / objets / tailles toutes les 30 s → CSV ; verdict sur la pente de la mémoire HORS
    relecture (`SweepStore` garde 30 min, voulu) et brute après 35 min). PAS dans la CI (long).
- **7.40.0 (Clément : « des fois les mics sont éteints et je le sais »)** : il a choisi de GARDER les statuts et d'ajouter
  **💤 Éteint (je sais)** qui reste jusqu'à ce qu'on rallume (pas de réveil automatique). `w["muted"]` (config + shows
  via `watch`) ; `set_muted(ws, on)` (efface l'ABSENT en cours, journal « ÉTEINT (je sais) » / « RALLUMÉ ») ;
  `w_paused` le respecte (pas d'ABSENT ; CONFLIT toujours actif, reste dans le plan) ; `sig_view` « 💤 éteint (je
  sais) ». Accès : clic droit liste (+ Ctrl+Espace sur la liste, `toggle_muted_sel`), clic droit scène / groupe
  (`layer_ws`, tout éteindre / rallumer), clic droit tuile du mur et du mode Show, page Tech (action `mute`, bouton 💤 /
  🔔). « Prêt pour le show ? » rappelle les fréquences éteintes (`muted`, info).
  **Suivi en direct WWB / WSM / Wisycom Manager** (idée de Clément) : en attente de vrais fichiers de LISTE / projet
  (ses fichiers reçus sont des SCANS) — WWB .shw / export « Frequency report », WSM projet, Wisycom Manager.
- **7.41.0 (Clément : « ai-je le droit de citer ce logiciel ? … bien rappeler que c'est une coord
  basique »)** : choix de Clément = **mentions neutres + avertissement, bibliothèque .lst4 gardée mais CACHÉE**. Règle
  désormais : WWB / WSM / Wisycom / le logiciel de coord ne sont cités QUE pour la compatibilité de fichiers (import .ezrf3, suivi,
  export de scans) ; plus de comparaison « comme [logiciel] » (préréglage 1 = « 🟢 Standard (2 TX ±100 · 3 TX ±50 kHz) », test_im
  adapté), plus de noms de fonctions d'autres logiciels dans les textes. `COORD_NOTE` (« ⚠ Coordination BASIQUE… ne remplace pas
  un logiciel de coordination ») + `TRADEMARKS` (pas affilié ni approuvé, marques de leurs propriétaires) : `coord_note()`
  en orange, « À propos », manuel (intro, Vérifier le plan, « Où sont mes fichiers ? »), README. Profils intégrés :
  `_EZ` = « Réglages de coordination courants pour ce modèle. », `RX_SRC_TXT` de la valeur « courante » = « courant » (la
  clé `src` d'origine reste dans les données). Bibliothèque : bouton « 📚 Bibliothèque (.lst4)… » visible SEULEMENT en mode expert,
  aucun nom de logiciel dans sa fenêtre, retirée du manuel. **Ne pas réintroduire de comparaison avec un autre logiciel.** 7.52 : derniers « comme … » retirés (commentaires,
  traductions orphelines, ce fichier) ; workflow manuel `menage-releases.yml` = suppression des releases < v7.41.0.
- **7.41.1 (Clément : « un tour du code pour l'alléger ou corriger les bugs »)** : pyflakes propre à 3 variables près ;
  vulture : ~130 lignes mortes sur 23 600 (laissées : gain nul, risque de conflit V8). **`tests/monkey.py [n] [graine]`**
  (« test du singe » : vraie appli en démo, clics au hasard sur boutons / menus / clics droits / fenêtres ; QMenu et
  QMessageBox remplacés par des sous-classes, car affecter `.exec` sur la classe C++ ne suffit pas et bloque hors écran)
  → 0 exception sur 2 × 1 500 actions, mais une **fuite** : chaque `QDialog(self)` restait vivant après fermeture
  (≈ 4 Mo par ouverture) + les menus sans parent de pyqtgraph (`ViewBox.menu`, `PlotItem.ctrlMenu`). Corrigé :
  `_reap_dialogs` (dans `_alarm_tick`, avec le battement : enfant QDialog direct caché depuis 10 s et non gardé par un
  attribut / liste / dict de MainWindow → `free_plot_menus` + `deleteLater`), `ShowModeWindow` en `WA_DeleteOnClose`.
  Mesure (16 fenêtres × 4) : +60 Mo / tour → ≈ +10 Mo / tour. **Garder une fenêtre réutilisée = la ranger dans un
  attribut de MainWindow** (sinon elle est détruite 10 s après fermeture). monkey.py PAS dans la CI (long).
- **7.42.0 (revue de code d'un autre développeur, transmise par Clément)** — fiabilité de l'acquisition :
  - **Réglages refusés** : `_apply_settings` / `_apply_front` (renvoie ok) / entrée haute-basse / `ultra on` ne
    mémorisent un réglage QUE s'il est accepté (sinon `"?"` / None → retenté au cycle suivant) ; `_warn` = message au
    plus 1×/min. Test smoke_test5 (faux tinySA qui refuse puis accepte).
  - **Calibration** : PURE `_clean_grid` (finies, croissantes), `calib_maxhold(sweeps, n)` = n PREMIERS balayages de
    chaque appareil (avant : 5 contre 3 → biais, −1,3 dB mesuré en test, −0,1 maintenant), balayages à grille différente
    ignorés ; `calib_repeat` (offset balayage par balayage → « répétabilité ±x dB » dans le message).
  - **Balayages contrôlés** : PURE `scan_check(fr, lv, a, z, pts)` → ok / court (moins de points : utilisé, signalé,
    compté) / invalide (→ RuntimeError → reconnexion) ; fréquences du tinySA non croissantes / hors bande → grille refaite.
  - `TinySA._cmd` : `time.monotonic()` + `bytearray` ; `ScanWorker.stats` / `stats_text()` (segments, cycles, temps
    de réglage, incomplets, invalides, refus, reconnexions) dans le 🩺 diagnostic.
  - **Relais** (Pi et `SerialRelay`) : `write_timeout=2` côté série, `settimeout(5)` sur le client (un client qui ne lit
    plus est lâché au lieu de bloquer) ; Pi : `--host` / `--allow` (ou `TSM_RELAY_HOST` / `TSM_RELAY_ALLOW` via
    `systemctl edit`), LISEZMOI § 5 Sécurité. Tests test_relais_pi (client lent, --allow).
  - **CI** : job `linux-tests` (ubuntu, pty) : test_reseau, test_reseau_qt, test_relais_pi, test_garde, test_v7.
  - Pas fait (proposé par la revue) : découpage du fichier en modules (conflits V8), interface `SpectrumDevice`
    (prévu avec la V8), calibration par fréquence, métadonnées de mesure complètes.
- **7.43.0 (Clément : « l'écran de base est assez imbuvable, penser hyper user friendly », « la coord je préfère la
  garder cachée pour moi, on peut laisser la fréquence de secours », « + fréq image »)** :
  - **🏠 Accueil** : `HomeBar` (toolbar `home_bar` sous `cmd_bar`) : cartes ① tinySA (`port_btn` menu = ports de
    `port_combo` + démo), ② Mes micros (Importer / Ajouter / Depuis le scan), ③ Surveiller (▶ / ■, ✅ Prêt ?, 🖥 Mode
    Show), 🎓 Tuto, ✕ ; carte à faire entourée (PURE `home_next`) ; grande phrase (PURE `home_status` : idle / ok /
    warn « sans signal pour l'instant » / bad alarmes, tinySA perdu). `home_info`, `update_home` (dans `_alarm_tick`),
    `set_home` (config `home`, ☰ Plus › 👁 Affichage › 🏠), `_home_layout` : avec l'accueil et hors expert, la barre de
    parcours et Port / Démarrer de `cmd_bar` (`_dup_acts`) sont cachés. Tuto « écran » : 3 étapes accueil en tête
    (`start_tour`), étapes visant des widgets cachés retirées.
  - **Coordination cachée** : `coord_on` (config `coord_tools`, défaut False, case `coord_chk` dans ⚙ › Général),
    `set_coord` : parcours ③ ④ (`_step_acts`, `_step_arrows`), `_coord_acts` (☰ Plus 🪄 🧮 🎛 + Intermod), tuto
    « coord » (`COORD_TOURS`), étapes des tutos dont l'action est dans `COORD_METHODS`, clic droit du journal
    « D'où ça peut venir », plan dans « Prêt ? ». 🆘 secours toujours visible. Manuel : encadrés « cachés par défaut ».
  - **Fréquence image** : `pf_check(..., img)` (FI par fréquence, `_pf_vec`) : récepteur à FI > 0 + ÉMETTEUR à
    f ± 2 × FI (les deux côtés, tolérance 2 TX du récepteur, 100 kHz si 0) → problème `img` ; `pf_suggest(..., img)`
    (vérif exacte) ; `pf_issue_text` ; profils : `img` gardé par `rx_custom_norm` / `rx_custom_dump`, lu des .ezrf3 et
    .lst4 (`rx_from_library`), champ « FI (fréquence image) » de `RxProfileEdit` ; PlanCheckDialog `_imgs`.
    **7.51.0 : règle corrigée à ± 1 × FI (plus 2 × FI), vérifiée par Clément dans le logiciel de coord (09/11/2026)** :
    Sennheiser EM300-500 G3 sur 600,000 + Wisycom sur 578,6 / 589,3 / 610,7 / 621,4 → le logiciel de coord signale « IMAGE de
    589,300 » et « IMAGE de 610,700 », rien pour 578,6 ni 621,4. Test « comme le test de Clément » dans test_plan.
  **7.43.1** : accueil compacté (titre et état d'une carte sur la même ligne) : sous Windows la hauteur mini était
  714 px (> 700, CI). Fusion V7 → V8 à la main (conflit dans `ScanWorker._loop` : `dev.configure` SDR + statistiques).
- **7.44.0 (suite de la revue de code : indicateurs de qualité de mesure)** : PURE `noise_floor(F, L, f)` (20ᵉ centile à
  ± 2 MHz sans ± 150 kHz autour de f), `snr_view(marge, keep_free)` (`SNR_GOOD/OK/LOW` 20 / 10 / 6 dB ; réserve :
  inversé), `sat_level(max_dbm, lna)` (`SAT_WARN/BAD` −25 / −15 dBm, `SAT_LNA_SHIFT` 15 dB — **valeurs de départ, pas
  mesurées sur un vrai Ultra**), `resolution_pairs(items, res)` (écart < 2 × max(pas, RBW)). `w["margin"]` (calculé
  dans `update_watch_levels`), colonne **Marge** `C_MARG` = 10 (ajoutée en dernier, déplacée visuellement à côté de
  Statut ; `WATCH_COLS_V` = 2 : un ordre de colonnes mémorisé avant 7.44 est ignoré). `_sat_max` {bande: (t, max)}
  rempli par `on_sweep` ; `quality_info()` (sat, sat_dbm, low_snr, res_pairs, stale) → `ready_checks` (clés sat, snr,
  res, stale ; « Régler » saturation = `open_measure`) et `home_status` (saturation = orange). Tuiles du mode Show :
  « niveau · +marge dB ». Manuel : chapitre « Lire les états » (marge, saturation, résolution).
  Fusion V7 → V8 à la main (2ᵉ fois de suite) : la V8 a modifié les lignes `sig_colors=… / unit=… watch_cols=…` de
  `_collect_config` (`sdr=`, `port=`) → **en V7, ajouter les nouvelles clés de config sur la ligne `coord_tools=` /
  `home=` (zone propre à la V7), JAMAIS sur ces deux lignes-là**.
- **7.45.0 (2ᵉ audit externe, « fiabilité critique »)** : `scan_check` refuse tout NaN et un balayage COURT sans
  fréquences fiables (avant : étalé sur la bande = signaux décalés) ; court AVEC fréquences = gardé à sa place.
  `TinySA.try_cmd` reconnaît `tinysa_refusal` (disque USB, mise à jour) → réglage non mémorisé. Calibration réussie →
  `history` vidé + `reset_max` (offsets changés = autre échelle). `_sync_cfg` prépare une copie puis
  `self._cfg.update` sous `self.lock`. Heure de MESURE : `ScanWorker.sweep_t` {bande: time.time()} posé avant
  `sweep.emit`, lu par `MainWindow._sweep_time` via `sender()` (signature du signal inchangée pour la V8 ; repli =
  heure actuelle). `SerialRelay(..., allow=)` + champ « PC autorisés » de `RelayWindow` (`refused` affiché), test
  dans test_reseau. Colonne Marge : bulle « Bruit de fond utilisé » (`w["floor"]`). Pas fait (plus tard) :
  calibration par bande, métadonnées de mesure, répartition adaptative des bandes, tampons préalloués.
- **7.46.0 (revue UX externe ; choix de Clément : « les deux, débutant d'abord » + une seule porte d'entrée, mots
  simples, fiches d'erreur)** :
  - **4 menus du travail** dans `cmd_bar`, juste avant ☰ Plus (`_more_act`) : `STEPS` = familles prep « 📋 Préparer »,
    show « 🎚 Surveiller », after « 📊 Analyser », hw « 🔌 Matériel » (SANS numéro : ① ② ③ = cartes de l'accueil) ;
    `_build_steps_bar` crée `step_btns` / `step_menus` (plus de barre de parcours : `steps_bar` = None, `step_lbl` /
    `tour_btn` gardés hors écran) ; `STEP_ALIAS` (scan / list / plan / im → prep) pour les tutos ; `do_step` met
    l'astuce `STEP_HINTS` dans la barre d'état. Actions de coordination (méthode dans `COORD_METHODS`) → `_coord_acts`
    (`COORD_STEPS` vide). `EXTRA_MENUS` (V8 : SDR) va dans 🔌 Matériel. ☰ Plus ne garde que Annuler / Rétablir,
    ⚙ Réglages, Fenêtres, Apparence, Affichage, Aide. Bulles des nouvelles entrées : `TIPS_MENU.update` juste après
    le dict. `open_devs_settings` (= ⚙ › dev2). Tutos / manuel : « ⑤ › … » devenus « 🎚 Surveiller › … ».
  - **Fiches « problème »** : PURE `PROBLEM_CARDS` (titre, ce qui se passe, étapes), `_PROBLEM_KEYS` (regex sur le
    message en minuscules — pas de chaînes simples : test_i18n les prendrait pour du texte), `problem_key`,
    `problem_card(msg, key)` ; `ProblemDialog` (Réessayer / mode démo / 🩺 / Fermer ; pas de Réessayer pour « lost ») ;
    `MainWindow.show_problem` remplace le QMessageBox de `on_error` et « Aucun port » ; `_last_problem` (effacé au
    démarrage et quand le tinySA revient) → `home_info["problem"]` → bouton « ❓ Que faire ? » de la carte ①
    (`HomeBar.help_btn`, `problem_help`).
  - **Mots simples** : PURE `UI_WORDS` / `ui_word(clé, expert)` (« Pics gardés » / « Max hold », « Effacer les pics » /
    « Reset max ») appliqués par `_apply_words` (dans `set_expert`, et après `_install_tips` : bulle d'origine gardée
    dans `_word_tips` + « (terme technique : …) ») ; RBW → « Finesse de mesure (RBW) », diversity → « Fusion des
    mesures (diversity) » ; lexique « Pics gardés ».
- **7.47.0 (2ᵉ revue UX, faite sur la 7.44 ; la moitié était déjà dans la 7.46)** :
  - **Jamais « tout va bien » sans mesure fraîche** : `home_status` lit `last_age` (None = aucune mesure depuis
    ▶ Démarrer → ton « wait »), `stale_lim` (max(15 s, 4 cycles) → « ⚠ Surveillance dégradée », bad) et `stale`
    (fréquences sans mesure → « partielle », warn) ; `_home_fresh()` (mesures postérieures à `_run_t0`, posé par
    `toggle_run`) ; `health()` = {tone, text} utilisé par l'accueil, le bandeau du mode Show (sans alarme) et la vue
    Régie web (`health` dans /etat.json, traduit ; classe CSS `.rg-al.warn`).
  - **Une seule logique d'état des données** : PURE `data_status(i)` (aucune mesure depuis ▶ Démarrer : « wait » puis
    « bad » au-delà de `stale_lim` grâce à `run_age` — avant, « Premier balayage en cours » pouvait rester sans fin ;
    âge = bande la PLUS EN RETARD parmi celles balayées (`_home_fresh`) ; zoom live avec un seul tinySA vivant =
    partielle ; `stale_names` nomme les fréquences sans mesure ; saturation `_sat_status`). `home_status` l'appelle ;
    `health()["data"]` = ce seul état des données, utilisé par le bandeau du mode Show (un micro faible ne remplace
    plus « Tout va bien ») et la vue Régie. L'âge part de l'heure d'ACQUISITION (`sweep_t`, 7.45). `quality_info` :
    `stale` (dans les bandes) ≠ `stale_names` (toutes).
  - Fiches : PURE `PROBLEM_IMPACT` (conséquence + état réel ; défaut = surveillance arrêtée, liste conservée ;
    « lost » = l'appli réessaie) → « Conséquence : » dans `ProblemDialog`. Réglages refusés (`_warn`) : « le réglage
    précédent reste actif, nouvel essai au prochain balayage ».
  - **🔎 Chercher une fonction** (Ctrl+K, bouton 🔎 avant ☰ Plus, ☰ Plus) : PURE `feature_match` (tous les mots, sans
    accents, nom puis bulle) ; `FeatureSearchDialog` parcourt `step_menus` + `more_menu` (actions visibles seulement :
    la coordination cachée n'apparaît pas). `open_feature_search`.
  - Réglages de mesure : aide en tête de la rubrique ; libellés « Préampli (LNA) », « Correction de niveau (offset) »,
    « Points par commande (segment) ».
  - Pas fait (proposé) : distinction systématique « détecté / déduit / recommandé » dans les alertes, profils de
    configuration rapides, tests utilisateurs (à faire par Clément : débutant + technicien).
- **7.48.0 (Clément a envoyé de VRAIS fichiers de plan : WWB .shw + .cug, WSM .wsm, Wisycom .wshow, DPA .acp ; PAS
  dans le dépôt, essais inventés `tests/data/wwb_essai.shw`, `wsm_essai.wsm`, `shure_essai.cug`, `wisycom_essai.wshow`,
  `dpa_essai.acp`)** : PURE `parse_wwb_show` (coordinated_data_root/freq_entry : value kHz, source_name, compat_key
  zone / series / band, model ; sinon inventaire channel/frequency), `parse_wsm_project` (FrequencyManager/Devices/
  Device : Frequency kHz, Name, StationaryDeviceType, Min/MaxFrequency, SearchStep, SpacingParams Carriers = écart,
  Device2TxIM3 / Device3TxIM3 / Device2TxIM5 = tolérances → profil perso), `parse_shure_cug` (custom_groups/frequencies
  series band / channel frequency number), `parse_wisycom_show` (ShowFile : seuls les ÉMETTEURS ont TunedFreq Hz ; les
  récepteurs MRK / MCR n'ont que des noms → `warn`), `parse_dpa_acp` (JSON : settings `/ch/N/name`,
  `/ch/N/radio/manual` kHz, mode → modelProfiles channelSpacing / spacingToIM3Product), `_number_dups` (« Shure » ×16 →
  « Shure 1… »), `PLAN_EXTS`, `parse_plan_file(data, nom)` (extension sinon contenu) → (doc au format de
  `parse_ezrf3`, logiciel). Tout passe par l'import `.ezrf3` existant : `import_ezrf_file` (tous les plans), `open_ezrf(...,
  kind)`, `EzrfImportDialog(..., kind)` (titre « Importer un plan {kind} »), `opts["kind"]`, `ezrf_link["kind"]`,
  `_ezrf_tick` → `parse_plan_file`, `EzrfSyncDialog` / messages avec le nom du logiciel ; filtre d'import et
  glisser-déposer. **Suivi en direct WWB / WSM / Wisycom / DPA = fait** (même mécanisme que .ezrf3).
  Constat sur ses fichiers : WWB et WSM ont importé notre export de scan (référencé dans le .shw et le .wsm) ; WSM 4.9
  exporte ses scans au format « Freq2D;RFA;RFB… » (celui qu'on appelait « Wisycom », déjà lu).
  - **Tester la garde** (Clément : « comment simuler un crash pour voir si l'appli se réouvre ? ») : 🌙 Mode festival,
    boutons `crash_btn` « 💥 Tester : plantage » (`os._exit(3)`) et `freeze_btn` « 🧊 Tester : appli figée » (le fil
    de l'interface dort `GUARD_HANG_S` + 30 s), visibles seulement sous garde ; `MainWindow.guard_test(how)` enregistre
    la config d'abord (la surveillance reprend) et note « TEST DE LA GARDE » au journal.
  - **1er lancement** (Clément : « la vue du spectre en 470-694 pour ceux qui le téléchargent ») : avant toute mesure,
    l'axe se cale sur les bandes (`_fit_range` dans la branche « pas de données » de `update_plot`) — avant, il
    montrait 0–1 MHz ; « Vue » restait vide (`refresh_view_combo` : `findData(None)` tombait sur un séparateur).
- **7.49.0 (Clément : « tu me l'as caché où la coord ??? », « re-ranger les menus, c'est incompréhensible, ordre
  alphabétique ? »)** : pas d'alphabétique (mélangerait des outils sans rapport) → **rubriques titrées** dans les 4 menus :
  entrée `("§Titre", None)` de `STEPS` = `QMenu.addSection` (Préparer : 1. Scanner le lieu / 2. Ma liste / 3.
  Coordination (avancé) / 4. Organiser le show ; Surveiller : Avant d'ouvrir / Pendant / Un micro est brouillé ? /
  À distance et la nuit ; Analyser : Revoir le show / Scans des autres logiciels ; Matériel : Mes tinySA / En réseau /
  Mesure et dépannage). Coordination cachée : entrée `_coord_hint` « 🔒 Outils de coordination cachés : les
  afficher… » (`show_coord_setting` = ⚙ › Général), visible seulement si `coord_on` est faux (`set_coord`). lang_en :
  les titres avec ET sans « § ».
- **7.49.1 (Clément : « pourquoi t'as que les IEM dans le .wshow ? », + 5 autres vrais shows Wisycom Manager 4.0 / 5.1)** :
  confirmé sur 6 fichiers : Wisycom Manager n'enregistre JAMAIS la fréquence des récepteurs (MRK980, MRK16, MCR54),
  connectés ou non, seulement celle des émetteurs MTK (DeviceChannel/TunedFreq). `parse_wisycom_show` : canaux dont le
  nom = nom de l'appareil (MAT288 = combineur d'antennes, MRK16) écartés de la liste « sans fréquence » ; show sans
  aucun émetteur (Maalouf) → message clair qui liste les canaux (« ajoute-les à la main, ou importe le plan depuis
  le logiciel de coord / un tableau ») au lieu de « aucune fréquence ». Piste non faite : interroger les récepteurs en réseau
  (port 2101 = protocole Wisycom non documenté ; `EmberPlus Attached` = false dans ces shows).
- **7.50.0 (Clément : « tu peux pas les add toi-même et faire une corrélation au nom ? »)** : `parse_wisycom_show` ne
  lève plus d'erreur sans émetteur : `doc["pending"]` = [{name, model}] (doublons numérotés « SPARE 1, 2… ») ; PURE
  `name_match(nom, candidats, avoid)` (identique, sinon mêmes numéros + chaque mot = début d'un mot du candidat :
  « DEP 1 » ↔ « HF 1 DEPART » ; `avoid=("IEM",)` pour un récepteur MRK / MCR ; égalité = None) — sur Roc : 12 / 16
  canaux retrouvés dans le plan `.ezrf3` de Roc ; `plan_fill_pending(doc, manual)` (ajoute les complétés, à l'import ET à chaque
  relecture du fichier suivi). `EzrfImportDialog` : tableau « À compléter » (`pend`, MHz pré-remplis par le nom dans
  la liste, `_pend_match`, bouton « 📂 Chercher les noms dans un autre plan… » `_pend_from_file`, `manual()` →
  `opts["manual"]` → `ezrf_link["manual"]`). **Suivi par fichier** : `w["ezsrc"]` = nom du fichier d'origine (config +
  shows) ; `_ezrf_cur(lk)` ne compare qu'avec les fréquences de CE fichier (avant : suivre un .wshow après un .ezrf3
  proposait de retirer toutes celles du `.ezrf3`) ; une entrée déjà reliée à un autre plan n'est plus « volée » ;
  ajouts dont la fréquence existe déjà = ignorés. Clément a mis à jour Wisycom Manager : **lui redemander un show
  enregistré avec la nouvelle version** (si les MRK ont un TunedFreq, ils sont lus sans rien changer).
- **7.52.0 (Clément : « penser à add un auto sur les seuils »)** : le bouton « Auto » (une fois, médiane + 10 dB) devient
  un MODE à cocher `thr_auto_btn` → `set_thr_auto` : **un seuil par fréquence** = bruit de fond appris + marges
  (`auto_occ_spin` « bruit + 12 dB », `auto_weak_spin` « bruit + 6 dB », visibles dans la barre à la place des seuils
  fixes). PURE `AUTO_THR_DEFAULT`, `floor_track` (descend vite `AUTO_FALL_S` 5 s, monte lentement `AUTO_RISE_S` 600 s,
  **ne monte pas tant que la fréquence est occupée** : un brouilleur large ne relève pas son propre seuil),
  `floor_curve` (20ᵉ centile à ± 2 MHz tous les 0,5 MHz, NaN dans les trous), `eff_thresholds(..., auto_floor,
  auto_m)` (seuil propre > référence > auto > global). `w["afl"]` / `w["afl_t"]` (bruit appris de la fréquence, à
  partir de `w["floor"]`, donc les blocs larges gardent leur fenêtre), `w["athr"]` → colonne Seuil « auto −95 ».
  `_acurve` (courbe apprise) → `auto_curve` en tirets (couleur `thr`), `auto_thr_at(f)`, `detect_unknown` seuil point
  par point ; `thr_spin` / `weak_spin` suivent la valeur TYPIQUE (médiane + marges) pour les outils qui lisent le seuil
  global. Config + SHOW_KEYS : `thr_auto`, `auto_occ`, `auto_weak` ; défaut = allumé au **1er lancement seulement**
  (`_first_run`), les configs existantes restent en seuils fixes. Seuil tapé depuis la page Tech → Auto coupé.
  **✅ Vérifié par Clément avec son vrai tinySA (09/11/2026) : « seuil auto ok »** (marges 12 / 6 dB gardées ; à + 4 dB,
  du bruit pur passait en « faible » en démo).
- **7.52.1 (test « 🧊 appli figée » de Clément, 10/11/2026)** : la garde a bien vu le gel (91 s) et relancé, MAIS
  `pr.kill()` ne tuait que le LANCEUR PyInstaller (exe « un seul fichier » = lanceur + appli Python dans un 2ᵉ
  processus) : l'appli figée restait vivante, gardait COM4 → nouvelle instance « could not open port 'COM4':
  PermissionError » (diagnostics de Clément), puis 2 appli après le dégel. Corrigé : `_kill_tree(pr)` (`taskkill /F
  /T /PID` sous Windows, puis kill) ; relance par la garde (`TSM_GUARD_RESTART`) → `retry_first` sur le 1er tinySA
  (l'ancienne instance peut mettre quelques secondes à libérer le port). **✅ Vérifié par Clément (13/11/2026, exe 7.60) :
  « 🧊 appli figée » → test à 16:18:24, une seule REPRISE AUTO à 16:19:49, COM4 repris, une seule appli : « vérifié ».**
- **7.52.2 (Clément : « je peux pas valider en cliquant OK sur la page web et notif, c'est caché »)** : `AlertsDialog`
  faisait 815 px de haut au minimum (> écran portable mis à l'échelle) → contenu dans un `QScrollArea`, OK / Annuler
  toujours en bas ; `fit_dialog(dlg, w, h)` borne la taille à l'écran (à réutiliser pour toute grande fenêtre).
  gui_reel : hauteur mini ≤ 600. Plus haute fenêtre restante mesurée : CoordDialog 639 px (cachée par défaut).
- **7.53.0 (3ᵉ audit externe, sur la 7.52.2)** :
  - **Jamais « OK » par défaut** : `health()` en exception → ton « bad » + PURE `UNKNOWN_HEALTH` (« État de surveillance
    indéterminé »), noté dans crash.log au plus toutes les 10 min (`_health_err_t`) ; `data` vaut maintenant
    `{tone: ok}` quand les mesures sont fraîches (avant : None = OK, indistinguable de « inconnu ») et None seulement
    surveillance arrêtée ; mode Show : pas de data en surveillance = indéterminé ; vue Régie : idem (`st.running` sans
    `health.data`) ; `update_home` en exception affiche UNKNOWN_HEALTH en rouge (avant : l'ancienne phrase restait).
  - **`scan_check`** : fréquences EXPLICITES mais incohérentes (dupliquées, hors bande, plus d'½ pas d'écart avec la
    grille) → « invalide » (avant : grille théorique reconstruite en silence) ; écart ≤ ½ pas (arrondi) → grille, ok.
    **Pas vérifié sur un vrai tinySA** : si un vrai Ultra renvoie des fréquences « bizarres » mais justes, ça
    déclenchera des reconnexions → regarder le 🩺 diagnostic (compteur « invalides »).
  - **Relais sans liste d'IP** : avertissement dans `RelayWindow` (« tout appareil du réseau peut piloter ce tinySA »)
    et dans le journal du Pi. Pas d'authentification ni de chiffrement (réseau technique de confiance seulement).
  - **4ᵉ audit (UX, même jour)** : surveillance ARRÊTÉE = jamais « tout va bien » : PURE `STOPPED_HEALTH` ; mode Show :
    `hl` = arrêtée / `health()["data"]` / indéterminé, et les alarmes S'AFFICHENT AVEC l'état de surveillance (ligne
    en dessous) au lieu de le masquer ; vue Régie : `hb` (arrêtée / indéterminé / problème) affiché sous les alarmes,
    « ✔ Tout va bien » seulement en surveillance, sans alarme et mesures fraîches. gui_reel : `is_running` forcé à
    False → bannière « arrêtée ».
  - Pas fait (proposé) : concaténations de `_scan_band` (à mesurer d'abord), mesure de cadence réelle par segment.
- **7.53.1 (5ᵉ audit externe, sur la 7.53.0)** : `parse_scan_lines` : réponse MÉLANGÉE (lignes « fréquence niveau » et
  lignes « niveau » seul) → fréquences = NaN (avant : None, pris pour « niveaux seuls » → grille théorique) →
  `scan_check` refuse. Même signature (la V8 l'utilise). `_sweep_time` : une heure de mesure ANCIENNE est gardée
  (avant : > 2 min → remplacée par « maintenant » = fraîcheur artificielle) ; heure future → maintenant ; absente → maintenant.
  Testé : test_v7 (parser), test_reseau_qt (vrai ScanWorker sur faux tinySA). **Pas vérifié sur un vrai tinySA.**
  Toujours pas fait : concaténations de `_scan_band`, authentification / chiffrement du relais (réseau technique).
  **Bilan de la 1re nuit sous garde (Clément, 10/11/2026, 7.52.0, 30 radios FM, 1 tinySA)** : 8 h 45 de surveillance
  sans plantage ni liaison perdue, bilan reçu à 09:00. MAIS ce bilan vient de l'instance FIGÉE par le test 🧊 (00:15)
  qui s'est réveillée et a continué : la relance n'a pas eu COM4 (bug corrigé en 7.52.1). RADIO 2 / RADIO 11 = stations
  faibles pile au seuil → 83 / 145 événements libre ↔ occupé (pas un bug : leur donner un seuil propre). Corrigé en
  7.53.1 : l'événement « Libre » notait le PIC de l'occupation (−69,7 dBm, plus fort que le « OCCUPÉ » à −91,7 :
  illisible) → il note le niveau actuel, le pic va dans la note « max pendant l'occupation : … ».
- **7.54.0 (Clément : « on taf sur le graphique ? » → les 4 zones, style « pro, type soft Apple »)** : thèmes PURE
  « Pro sombre » (NOUVEAU DÉFAUT : graphite #1c1c1e, couleurs système Apple) et « Pro clair » ; une config dont le thème
  est EXACTEMENT l'ancien défaut « Sombre doux » passe au nouveau (marque `theme_v` = 2 dans la config) ; un thème
  retouché reste tel quel. `make_stylesheet` = vraie feuille de style (gabarit `%(clé)s`, PAS un f-string : test_i18n
  prend les f-strings pour du texte) : boutons / champs / tableaux / menus / onglets arrondis, barres de défilement
  fines, police Segoe UI Variable / SF Pro. Cases à cocher et flèches des champs numériques NON stylées (il faudrait des
  images). PURE `soft_style(c, bg, txt)` = bandeau teinté + contour fin (phrase de l'accueil, « Tout va bien » du mode
  Show) ; une ALARME garde un fond plein. Liste : lignes à peine teintées, la couleur forte reste sur la case Signal.
  Mode Show : cartes sombres teintées, état en couleur ; tuile en problème = pleine. Spectre : repères fins (1,5 px) et
  un peu transparents ; bandeaux du plan / TV adoucis (`blend` 0,62 sur le fond). Bouton « Global » = accent bleu.
  Page web : palette Apple (fond noir, panneaux #1c1c1e, accent bleu #0a84ff), Régie / Mur / tuiles teintées, alarmes
  pleines. Aperçus avant / après : `apercu/` (pas dans le dépôt).
  **Boutons (Clément : « les boutons sont vraiment pas beaux »)** : PURE `plain_btn_text` (emoji de tête retiré ;
  un bouton qui n'est qu'une icône, « 🔔 », « 🔔 1 », « ⚙ », la garde) appliqué par `install_plain_buttons()` (appelé AU
  CHARGEMENT du module, donc AVANT install_language : la traduction voit le texte complet) sur
  `QAbstractButton.setText` et les constructeurs QPushButton / QToolButton ; menus et listes gardent leurs emojis ;
  les tests comparent via `plain_btn_text(...)`. `qss_icons(t)` dessine (QPainter → PNG dans le dossier temporaire)
  la flèche de menu et la coche aux couleurs du thème + styles QComboBox / QCheckBox / hauteur mini des boutons. **Rendu Windows réel pas vu par Claude** (captures de
  la CI seulement) ; un écran mis à l'échelle peut changer les tailles mini (gui_reel les vérifie).
  **Thèmes (Clément : « plusieurs daltoniens, le rouge et vert c'est pas beau, regarde d'autres softs »)** : 15 thèmes ;
  défaut « Pro sombre » = menthe #4fd1c5 (libre) / corail #ff6b6b (occupé) ; inspirés (de mémoire, palettes publiques)
  de Catppuccin Mocha, Tokyo Night, Dracula, Rosé Pine, Gruvbox, Nord ; daltoniens par type : deutéranopie (Okabe-Ito
  bleu / orange), protanopie, tritanopie (Paul Tol), Monochrome. `OLD_DEFAULT_THEME` (« Sombre doux ») → migré. Tests
  test_v7 : simulation Machado 2009 (sévérité 1) + ΔE CIE Lab entre états critiques (libre/occupé, réserve/occupé,
  faible/occupé…) ≥ 17 pour la vision visée (ancien défaut : ΔE 9 en deutéranopie) ; tous les thèmes ont toutes les
  THEME_KEYS. Bulles `_install_tips` : clés aussi en `plain_btn_text` (sinon 3 boutons sans bulle) ; marges QSS
  réduites (hauteur mini 687 px en expert sous Linux). **Pas vu par un vrai daltonien.**
- **7.54.1 (Clément : « Nuit rouge / Analyseur vert : le filtre rouge ou vert c'est pas beau du tout », « je vois plus le
  éteint dans mes fréquences »)** : ces 2 thèmes ont des surfaces NEUTRES (seuls courbes / accents colorés ; `_NIGHT_BP`
  supprimé, bandeaux = couleurs normales) ; leur SPECTRE est façon vieil analyseur à tube (photo de Clément) : clé de thème
  `plot_style` « crt » (« normal » ailleurs) → grille plus visible (alpha 0,40), trace phosphore + halo (`setShadowPen`),
  grille / axes / trace d'une seule teinte ; LUT « Phosphore vert ». Gamme « analo » (Clément : « un bleu aussi ») :
  Analyseur vert / bleu / ambre / blanc + Nuit (rouge), LUT « Phosphore bleu / ambre ».
  **Palettes des couches par thème** (Clément : « des couleurs prédéfinies pour les groupes qui suivent le thème, en analo
  aussi ») : PURE `THEME_PALETTES` (palettes des thèmes inspirés, Okabe-Ito / Tol pour les daltoniens), `phosphor_shades`
  (nuances clair / foncé alternées du phosphore), clé de thème `pal` (couleurs séparées par des virgules, gardée dans la
  config), `theme_pal(t)`, `layers_recolor(scènes, statuts, t)` (statut « doit rester libre » → `st_libre`, « doit émettre »
  → `st_free`, les autres → palette). Nouvelles scènes / groupes (`ensure_group`) et nouveaux statuts (`_resolve_status`,
  `StatusDialog`) prennent la palette du thème ; `ColorsDialog.recolor_chk` (décochée par défaut) → `recolor_layers()`
  (annulable). Thèmes « analyseur » : bandeaux du bas (`bp_*`) en nuances assombries du phosphore. 💤 : la case Signal ne dit « éteint » que si le micro ne capte rien (sinon elle
  montre la mesure) → la case **Statut** affiche « 💤 éteint · statut » (ou « 💤 hors état » pour un état 📸) et la ligne
  est grisée (`dim` dans `update_watch_table`), même si le micro émet encore.
- **7.54.2 (Clément : « go petit plus visuel + fluidité »)** — mesuré en démo (1920 × 1080, 30 fréquences, rémanence 10,
  profil cProfile, script de la session) : la grille FINE de pyqtgraph (sous-graduations, `AxisItem.paint` → `QPicture.play`
  15 ms) coûtait ~16 % de processeur → **grands carreaux seulement pour tous les thèmes** (`setStyle(maxTickLevel=0,
  maxTextLevel=0)`, `setTickDensity` 1,6 en fréquence / 2,6 en dB ≈ 10 dB par carreau, dans `apply_theme`). Le halo
  phosphore (`setShadowPen` > 1 px) doublait le dessin (43 → 87 %) : retiré. Rémanence : `DeviceCoordinateCache` sur les
  courbes (refaites seulement à chaque balayage, pas à chaque rafraîchissement). Total démo : Pro sombre 59 → 39 %,
  Analyseur vert 87 → ~45 %. Reste : rémanence ≈ +10 % (idée : image de densité au lieu de N courbes), `floor_curve` ≈ 3 %
  (centiles en boucle). **Pas mesuré sur le PC de Clément.**
- **7.55.0 (Clément : « go rémanence »)** : la rémanence du spectre n'est plus N courbes empilées mais UNE image de
  densité façon analyseur numérique : PURE `density_raster(traces, x0, x1, y0, y1, W, H, weights)` (chaque ancien
  balayage tracé en ligne brisée continue colonne par colonne — min / max entre les bords interpolés + points — donc pas
  de trou sur un pic raide ; coupures NaN entre bandes respectées ; somme pondérée / total, 0..1), `density_glow`
  (halo d'1 pixel), `density_lut(couleur)` (couleur de la trace, alpha gamma 0,45). MainWindow : `_update_history`
  garde `_dens_traces` (récent → ancien, poids 1 − i/(n+1)) → `_density_draw` (ImageItem `_dens_img`, taille = pixels
  de la vue, refait 60 ms après un zoom / déplacement / redimensionnement via `_dens_timer`), `_clear_hist_pool`
  remet la couleur au changement de thème. Démo : 39 → 29 % de processeur. Testé : test_v7 (raster), captures (vue
  seule) ; **pas vu sur le PC de Clément**.
  **✅ Vérifié par Clément (10/11/2026, vrai tinySA) : câble USB débranché en pleine surveillance → bandeau rouge tout de
  suite ; rebranché → la surveillance reprend seule et revient à « tout va bien ».**
- **7.56.0 (Clément : « j'aime bien tout ça, prends le temps, pousse pas trop vite »)** — 5 chantiers, un seul push :
  - **⚡ Préréglages rapides** (revue UX « profils de configuration rapides ») : PURE `QUICK_PRESETS` (festival, salle,
    nuit, scan : réglages thr_auto, auto_occ / auto_weak, points (donnée d'`AUTO_POINTS`), persist, absent, confirm,
    repeat (valeur d'`ALARM_REPEATS`), strong / strong_lvl, hold ; 5ᵉ champ = fenêtre proposée ensuite, « nuit » →
    `open_festival`), `PRESET_LABELS`, `quick_preset`, `preset_value_text`, `preset_changes(cur, clé)` (maintenant →
    après, seulement ce qui change), `preset_match`. MainWindow : `preset_current`, `apply_preset` (réglages seulement :
    liste / scènes / bandes jamais touchées), `open_presets` → `PresetDialog` (`self._presets`, liste avec ✓, tableau
    des changements, Appliquer). Entrées : 🎚 Surveiller › Avant d'ouvrir, ⚙ › Général. gui_reel applique les 4.
    Valeurs des préréglages = **choix de Claude, pas mesurées sur le terrain**.
  - **Alarmes expliquées** (revue UX « détecté / déduit / recommandé ») : PURE `ALARM_HELP` {type: (cause probable,
    conseil)} et `alarm_explain(a, now, niveau, seuil)` → {measured, deduced, advice} ; `w["ethr"]` = seuil appliqué ;
    MainWindow `alarm_explain`, `alarm_why_text`, étiquette `alarm_why` sous la liste des alarmes (alarme choisie, sinon
    la plus récente à acquitter) + bulle sur chaque ligne ; conseil sous l'alarme du mode Show ; `notify_text` ajoute
    une 2ᵉ ligne « quoi faire » (test_alertes mis à jour) ; page web : champ `hint` (traduit) dans les alarmes, affiché
    `.hint` dans les vues Alarmes / Régie / bandeau.
  - **Page web façon thème** : `web_json` envoie `plot` {bg, fg, curve, mh, thr, crt} ; JS `PC()` : fond du tracé,
    grille (phosphore si crt), trace, pics gardés, seuil et légende aux couleurs du thème ; rémanence en
    `globalCompositeOperation="lighter"` (les traces s'additionnent : ce qui revient brille), calque refait si la couleur
    change. Test Chromium : calque de rémanence allumé (plus de test « bleu »).
  - **Rapports au look pro** : PURE `REPORT_PRO_CSS` ajouté après les styles d'origine de `build_report_html` (rapport,
    bilan du matin) et `site_report_html` (typo système, cartes, tableaux arrondis, pastilles, couleurs système).
  - **Optimisations** : `floor_curve` sans boucle (centile linéaire à la main sur fenêtres triées, = np.percentile,
    ≈ 28× plus rapide, test « = calcul fenêtre par fenêtre ») ; `ScanWorker.stats["pts"]` → `stats_text` « vitesse N
    points/s (x ms par point) » dans le 🩺 diagnostic (**à lire sur le diagnostic de Clément**).
- **7.57.0 (Clément : « la Vue sur UHF 470-694 direct en France pour un nouveau show, déduire tout ça ; le waterfall
  ne s'affiche pas de lui-même ; pouvoir créer ces préréglages ; tout ça dans les shows ; un mode préférences user »)** :
  - **Déduire** : PURE `COUNTRY_UHF` / `country_uhf` (US / CA 470-608, sinon 470-694), `default_view_band(bandes, pays)`
    (la bande balayée qui recouvre le plus l'UHF, la plus étroite à égalité ; une seule bande -> elle),
    `country_from_locale` (« fr_FR » -> FR ; système en ANGLAIS -> rien : la CI Windows en_US passait en États-Unis), `single_band_view` (waterfall : la bande de la Vue, ou la SEULE bande balayée
    en « Toutes les bandes » — avant, le waterfall disait « choisis une bande »), `missing_bands(fréquences, bandes)`
    (bandes à proposer, ± 2 MHz, réunies à 10 MHz). MainWindow : `_wf_bid`, `auto_view` (nouveau show via
    `clear_show_data`, 1er lancement dans `_late_layout` avec le pays de `QLocale`), `_bands_changed` montre le waterfall
    si une seule bande, `set_level` rend le waterfall en quittant l'ultra simple (`_prev_level`),
    `offer_missing_bands` (fenêtre NON bloquante `_band_offer` après `open_import` / `apply_ezrf`).
    **Pays du show** (Clément : « demander où se situe le show pour déduire la bande ») : `ShowInfoDialog(..., country=)`
    → champ « Pays du show » (`country_combo`, `country()`), `edit_show_info` → `set_show_country(code, fresh)` (plan du
    pays, PURE `uhf_band_needed(bandes, pays)` → None / ("enable", id) / ("add", nom, début, fin, pas), Vue remise sur
    « Toutes » puis `auto_view` pour un nouveau show) ; `open_show` appelle aussi `auto_view`.
  - **⭐ Préréglages perso** : PURE `user_presets_norm` ({name, desc, st} ≤ 30, réglages bancals -> ceux du festival),
    `user_presets_merge` (à nom égal le nouveau gagne), `presets_all(user)` (clé « u:nom », « ⭐ nom ») ; `quick_preset` /
    `preset_changes` / `preset_match` prennent `user`. `self.user_presets` (config + SHOW_KEYS, FUSIONNÉS dans
    `_apply_config` comme `net_profiles`). PresetDialog : « ⭐ Enregistrer mes réglages actuels… » (`save_current`),
    « Supprimer » (`delete`), `_fill`. Noms perso jamais traduits. SHOW_KEYS + `persist`, `hold`, `alarm_timing`
    ({confirm, repeat} recopié dans `sound.cfg` à l'ouverture).
  - **👤 Profils utilisateur** : PURE `USER_KEYS` (affichage, couleurs, mots, seuils, alarmes, son SANS `device`,
    préréglages perso ; jamais le show / web / alertes / tinySA), `user_doc`, `read_user` (format « tinysa-user »),
    `user_apply` (garde la sortie audio du PC), `user_filename`. `USER_DIR` = Documents/TinySA Monitor/Profils, fichiers
    `.tsauser`. `UserProfilesDialog` (`self._userprof` : liste ✓, Charger, Enregistrer, Importer, Exporter, Supprimer,
    Dossier), `user_profile_save` / `user_profile_load` (+ `set_level`), `user_name` (config). ☰ Plus et ⚙ › Général.
    Testé : PURE (test_v7), vraie appli (scripts de la session + gui_reel). **Pas essayé par Clément.**
- **7.57.1 (Clément : « ça prend pas en compte la disposition de fenêtre dans le user profil », « canal 38 c'est ok en
  France »)** : `USER_KEYS` + « layout » = {`LAYOUT_PARTS` : geometry, docks, panel_windows, layout_ver} (fait par
  `user_doc`, jamais recopié dans la config par `user_apply`) → `MainWindow.user_apply_layout` (raccroche tout,
  restoreGeometry / restoreState, `panel_restore` ; disposition d'un ancien `LAYOUT_VER` ignorée). Qt ramène une fenêtre
  plus grande que l'écran à la taille de l'écran (vu hors écran : 800 × 800). Plan FR : 470-694 d'un seul tenant, canal
  38 utilisable (avant : « hors micros ») ; GB : canal 38 = licence Ofcom partagée (avant : « sans licence », de
  mémoire, pas revérifié). **Piste en cours : émetteurs TNT de l'ANFR** (data.gouv.fr, jeu « installations
  radioélectriques de plus de 5 watts », zip mensuel ~65 Mo : SUP_EMETTEUR `EMR_LB_SYSTEME` « RDF DVB-T » ≈ 10 350
  émetteurs, SUP_BANDE fréquences début / fin, SUP_SUPPORT coordonnées DMS ; fichiers en latin-1, `;`) ; environnement
  « TinySA-Monitor » de la session : data.anfr.fr, www.data.gouv.fr, static.data.gouv.fr, efis.cept.org autorisés.
  **Vitesse (diagnostics de Clément, 12/11/2026, firmware v1.4-266, LNA on)** : RBW 100 kHz forcée, pas 75 kHz =
  ≈ 700 points/s (1,4 ms / point, UHF 3 000 pts en 4,2 s) ; RBW auto, pas 125 kHz (Rapide) = ≈ 1 770 points/s (UHF 1 793
  pts en 1,0 s). L'appli n'ajoute rien (< 1 ms entre deux commandes). → 🩺 « Vitesse par réglage » (PURE `speed_table`,
  `ScanWorker.stats["by"]` {(rbw, pas kHz, lna): [points, s]}) : un seul diagnostic suffit pour comparer.
  « ✅ Prêt ? » : clé `speed` (warn) si RBW forcée ET tour complet ≥ `SLOW_CYCLE_S` (2,5 s) hors démo → « Régler » =
  `set_rbw_auto`. **RBW par défaut = Auto** (demande de Clément ; `_cfg` et `rbw_combo`) : une config qui a déjà « rbw »
  (toutes celles enregistrées) garde sa valeur.
  **Thèmes analo (Clément : « trop unis, ça fait trop vert, c'est surtout la visu qui est cool »)** : seul le spectre
  (fond, grille, axes, trace, waterfall phosphore) reste façon tube ; accent, palette des scènes / groupes et bandeaux
  du bas = ceux de « Pro sombre ». `OLD_CRT_THEMES` (accent / palette / bandeaux 7.54.1-7.57.0) → une config au
  `theme_v` < 3 qui les a gardés tels quels est migrée dans `_apply_config` (`theme_v` = 3).
- **7.58.0 (Clément : « une base à jour des bandes / TNT par internet ? » → « canaux, bonus ANFR et possibilité de faire
  sans »)** : constat (12/11/2026) : AUCUNE base ouverte « canaux TNT par émetteur » : la base ANFR (data.gouv.fr, jeu
  « installations radioélectriques de plus de 5 watts ») donne pour chaque émetteur DVB-T toute la bande (470-694 /
  470-790), le plan TNT de data.gouv date de 2015 (lien mort), « Ma couverture TNT » (Arcom) n'est qu'un outil en ligne
  (pas aspiré, pas d'accord de Clément). Donc **📺 canaux TNT MESURÉS** (sans internet) : PURE `tnt_channel_list(pays)`
  (canaux 8 MHz 21-48, USA / Canada 6 MHz ≤ 608), `tnt_measure(F, L, canaux, marge)` (bruit = 10ᵉ centile ; « tv » =
  médiane ≥ bruit + marge ET ≥ `TNT_FILL` 60 % des points au-dessus ; « other » = signal étroit ; « free » ; « none » =
  < 4 points), `tnt_summary`. **Bonus ANFR** (facultatif) : PURE `anfr_text` (UTF-8 sinon latin-1 : les fichiers
  mélangent), `anfr_tnt_sites(SUP_EMETTEUR, SUP_SUPPORT, SUP_STATION, SUP_EXPLOITANT)` → sites [lat, lon, multiplex,
  hauteur, lieu (sinon adresse), CP, exploitant] réunis par position + `cp` {code postal: centre des supports} (lieu sans
  internet), `anfr_pick` (ressources data.gouv les plus récentes), `geo_km`, `place_parse` (CP ou « lat, lon »),
  `tnt_sites_near`, `tnt_near_text`, `TNT_DEFAULT` / `tnt_cfg_norm`. Qt : `anfr_read_files` (.zip ou SUP_*.txt),
  `anfr_download(job)` (fil, sans Qt, dict partagé), `TntDialog` (`self._tnt`, onglets « Canaux mesurés ici » /
  « Émetteurs proches (ANFR) »), `open_tnt`, `tnt_measure_now(src)` (via `coord_FL`), `tnt_mark` (LinearRegionItem +
  InfLineLabel « TNT n », `_tnt_items`), `tnt_db` / `tnt_db_save` (`TNT_DB_PATH` = anfr_tnt.json à côté de config.json,
  ≈ 0,3 Mo). Config + SHOW_KEYS « tnt » {place, radius, margin, mark} ; nouveau show = lieu vidé, marques effacées.
  Menu 📋 Préparer › 1. Scanner le lieu. Vrai téléchargement testé dans la session (65 Mo, 18 s, 2 370 sites, Tour
  Eiffel = 7 multiplex) ; essai inventé `tests/data/anfr_essai_data.zip` / `anfr_essai_ref.zip`. **Pas essayé par
  Clément ; seuils de la détection (10 dB, 60 %) = choix de Claude, pas mesurés sur une vraie TNT.**
  **7.58.1 (Clément : « on peut pas griser manuellement »)** : `tnt_cfg["manual"]` {n° canal: « tv » | « free »}
  (config + shows via « tnt » ; nouveau show = vidé) ; PURE `tnt_apply_manual(res, manual)` (lignes copiées, `manual`
  = True) appliqué par `tnt_measure_now` ; TntDialog : double-clic = `cycle` (auto → tv → free → auto), clic droit =
  `_man_menu` (plusieurs lignes, `set_manual`), état « (à la main) » ; `tnt_mark_saved` (QTimer après `_apply_config`) :
  les canaux grisés à la main reviennent sur le spectre à l'ouverture, sans mesure.
  Aussi (Clément : « que ça puisse suivre le plan .ezrf3 au cas où ») : `ChTVActifList` de TOUS les groupes réunis
  (avant : 1er groupe) → `tnt_cfg["plan"]` / `plan_src` (nom du fichier) via `tnt_set_plan` (dans `apply_ezrf` si le
  doc a des canaux TV, et dans `_ezrf_tick` pour le fichier suivi : mis à jour en silence + barre d'état, vidé si le
  plan suivi n'en a plus) ; priorité main > plan > mesure (`tnt_apply_manual(res, manual, plan)`, `src`), état
  « 📺 TNT (plan) », `plan_lbl` dans TntDialog. Sens de « True » dans `ChTVActifList` = canal TV présent : **supposé**
  (lu sur les fichiers d'essai, pas vérifié dans le logiciel de coord).
  **7.58.2 (Clément, retour terrain : « tout fonctionne », mais « remettre les canaux TV en libre et que ça soit
  remesurable, import de fréquences en tournée »)** : `MainWindow.tnt_reset(clear_peaks)` (manual + plan oubliés,
  marques effacées, `reset_max` si demandé) ← bouton `reset_btn` « ↺ Nouveau lieu » (menu à 2 choix) de TntDialog ;
  `apply_ezrf` avec « Remplacer ma liste » remplace les canaux TV du plan (vidés si le nouveau plan n'en a pas).
  La 7.58.1 n'a PAS de release (compilation sur main refusée : paiement / limite de dépense GitHub, 12/11/2026) ;
  l'exe était dans la pré-release `test-ui-validation`.
  **7.58.3 (Clément : « quand je change de pays ça garde 470-694 ; on add des pays ? fais les recherches »)** :
  `COUNTRY_UHF` + GB 470-702, AU 520-694, NZ 502-606, JP 470-714 (recherches du 13/11/2026 : ACMA LIPD 2025, RSM GUSL
  272800 / GURL-SRD, tableau MIC, Ofcom entrelacé ; **indicatif**, bouts annexes dans `COUNTRY_NOTES`) ; COUNTRIES + AU,
  NZ, JP ; `tv_channels` AU (7 MHz, 27-51) et JP (6 MHz, 13-52) ; `uhf_band_needed` → ("resize", …) pour une bande
  cochée dont le nom commence par « UHF » (créée par l'appli) ; `set_show_country` l'applique ; le combo Pays des
  réglages appelle `set_show_country` sur `activated` (choix à la main seulement, pas au chargement). Pas trouvé de
  source fiable pour BR / MX / IN / ZA : pas ajoutés. Seuil auto « qui suit la TNT » (capture de Clément) : voulu
  (bruit LOCAL + marge ; sur le vrai bruit, un micro dans un canal TNT serait toujours « occupé » → ABSENT muet).
  Expliqué partout (Clément : « faut bien l'expliquer ») : PURE `AUTO_THR_HELP` / `auto_thr_help_html(tr)` → fiche
  ❓ `show_auto_thr_help` (`auto_help_btn` dans la barre des seuils, `_auto_help`), ligne « Seuil auto (tirets) » de la
  légende des courbes, bulle de Auto, lexique « Seuil auto », manuel (chapitre Seuils). Nouveau chapitre manuel
  **`pays` « Bandes et canaux TV par pays »** (partie B, `docs/src/nouveaux_*.html`) : tableau bande / canaux / autres
  bandes / source + formules de canaux (Clément : « que tu sources tous les canaux dans le manuel en fonction des pays »).
- **7.59.0 (Clément : « comment on rend tout ça intuitif, compréhensible ? » → les 4 propositions)** :
  - **🧭 Assistant « nouveau show »** : PURE `WIZARD_STEPS` (clé, titre, pourquoi, comment), `WIZARD_SCAN_S` (300 s),
    `wizard_status(info)` ; `ShowWizard` (non modal, `self._wizard`, liste à ✓ + pages de boutons, rafraîchi 2 s),
    `open_wizard(step)`, `wizard_info()` ; entrées : accueil (`HomeBar.wiz_btn`), 📋 Préparer en tête, et tout seul
    après `clear_show_data` (étape 2).
  - **Propositions** : PURE `hint_due(info, done)` (TNT trouvée après `HINT_TNT_S` de scan, liste vide après
    `HINT_EMPTY_S` de surveillance) ; `HintBar` (`self.hint_bar`, au-dessus de `thr_bar`, caché d'office, 2 boutons +
    ✕ → `_hints_done`, remis à zéro par un nouveau show), `_hints_tick` (5 s, dans `_alarm_tick`), `hint_info`,
    `show_hint`, `hint_tnt_mark` ; pays qui recale la bande → proposition « Annuler » (`_band_restore`).
  - **Légende** : PURE `LEGEND_ITEMS` ; `SpecLegend` = cadre ENFANT de `self.spec` (posé en haut à gauche, ne change
    pas la mise en page), pastilles à menu (explication + actions), `refresh()` chaque seconde (pastilles visibles
    selon ce qui est affiché). Étiquettes TNT descendues (0,87 / 0,80) pour passer sous la légende.
  - **Nettoyages** : étiquettes TNT de canaux collés en alternance ; port « COM4 — Périphérique série USB » (plus de
    « (COM4) » en double) ; note du plan FR raccourcie (ligne de survol) ; Port / Démarrer en double cachés dès que
    l'accueil est affiché (aussi en expert) ; `open_manual(chapitre)` + boutons « ❓ Manuel » (TNT → arrivee,
    assistant → vue, seuil auto → seuils).
  Testé : PURE (test_v7), vraie appli (script de session + gui_reel). **Pas essayé par Clément.**
- **7.59.1 (Clément : « pas sûr de toutes les bandes par pays »)** : Europe revérifiée dans le tableau OFFICIEL CEPT EFIS
  « Annex 4 : national conditions for audio PMSE » (ERC/REC 25-10, rempli par chaque régulateur ;
  efis.cept.org/report/report2510AnnexImplementation.do?annexId=1, lu le 12/11/2026). Corrigé : **608-614 MHz interdit aux
  micros en Allemagne** (radioastronomie), **Suisse** (près de Bleien), **Pays-Bas** (604-614 + petits créneaux
  556-558… réservés aux liaisons audio, régulateur = RDI), Belgique (470-786 « possible » selon la CEPT, à confirmer),
  Italie 694-698 / 736-738, Allemagne 1350-1400 / 1518-1525 en intérieur (au lieu de 1492-1525), UK bande de garde
  694-703, NZ **502-698** (622-698 aussi permis, RSM), Canada 614-617 / 652-663 (ISED), Australie + 1790-1800.
  `COUNTRY_NOTES` réécrites, `PLAN_OVERRIDES` DE / GB / CH / NL / IT (pas de chevauchement entre lignes d'un même pays :
  test_plan), tableau du chapitre `pays` du manuel. Hors Europe : sources nationales (FCC, ISED, ACMA, RSM, MIC), pas de
  tableau commun. apwpt.org et testefis.cept.org bloqués par le réseau de la session (efis.cept.org autorisé).
- **7.60.0 (audit externe sur la 7.59.1 : « séparer plage balayée et plages réglementaires »)** : TROIS notions
  distinctes : BALAYÉ (`country_uhf`, bandes à balayer), AUTORISÉ (PURE `COUNTRY_ALLOWED` {pays: [(début, fin,
  condition "" | licence | intérieur | limité)]}, d'après les notes 7.59.1, indicatif), OCCUPÉ (mesure). PURE
  `country_bands`, `reg_status(pays, f, bw)` → ok / cond / out / unknown (bloc : doit tenir dans des plages contiguës),
  `reg_allowed_pred`, `reg_issues` (émetteurs seulement), `reg_summary(pays, tr)`. `find_free(..., allowed=)` (diag
  `hors_bandes`). MainWindow : `country_code`, `reg_pred`, `reg_busy(busy)` (coordination `CoordDialog.compute`,
  `PlanCheckDialog.suggest`), `reg_note`, `reg_info` → `ready_checks` clé « reg » (warn hors bandes / info sous
  condition, Régler = `open_country`) ; case `reg_chk` (`reg_only`, config sur la ligne `coord_tools=`, défaut vrai)
  + `reg_lbl` (« Micros autorisés … / Balayé … ») dans ⚙ › Pays. Manuel : chapitre `pays`, encadré « Balayé, autorisé,
  occupé ». Pays sans liste = pas de filtre. **Pas essayé par Clément.**
  Puis (Clément transmet les sources conseillées : ITU, EFIS, régulateurs) : **base ITU-R ENG/PMSE 09/2026** lue
  (xlsx R0A0700004B0001XLSE, couleurs de cases : indexed 19 = licence, 17 = sans licence, 16 = les deux, 18 = rien) →
  Japon 470-714 AVEC licence (+ 806-810 sans, 1240-1260 licence), Canada 653-657 licence / 657-663 sans (comme les USA)
  + VHF, 902-928, 941-960, 1435-1492, 1920-1930, Australie + 174-230, USA + 169-172. Contradictions ITU ↔ régulateur
  (Suisse « licence » alors que l'OFCOM dit sans licence ; UK / FR 863-865) → **ordre de confiance : régulateur > CEPT
  EFIS > ITU**. `COUNTRY_ALLOWED` = (début, fin, condition, puissance) ; `COUNTRY_SOURCES` + `REG_CHECKED`
  (« novembre 2026 ») ; `country_bands` → power / sources / checked ; `reg_detail(pays, tr)` = bulle de `reg_lbl`
  (plage · condition · puissance, sources, date). Environnement de la session : + www.itu.int, www.ofcom.org.uk
  (bloqué par Cloudflare), www.bakom.admin.ch, apwpt.org, www.anfr.fr, www.bundesnetzagentur.de.
  Puis **LoRaWAN / IoT** (Clément : thethingsnetwork.org « frequencies by country », site ajouté) : PURE `LORA_PLANS`
  (EU863-870 : 867,0-868,6 / 868,7-868,9 / 869,4-869,65 + EU433 ; US902-928 ; AU915-928 ; AS920-923), `LORA_COUNTRY`,
  `lora_overlap(pays, f, bw)` → `reg_info` « lora » → `ready_checks` clé « lora » (info). Bandeaux : PLAN_EU 433,05-434,79
  et 865-870 (LoRaWAN), US 902-928 ; **AU / NZ / JP ont maintenant leurs propres bandeaux 790-960 MHz** (avant : plan
  européen, « GSM-R (trains) » sur 915-925 = faux) : mobile « plan du pays », ISM / LoRa 915-928, JP 806-810 micros.
- **7.60.1 (audit externe sur la 7.60.0)** : « une absence de données ne vaut jamais autorisation » : PURE `reg_known`,
  `reg_tag(pays, f, bw)` (« » / sous licence : autorisation à obtenir avant d'émettre / intérieur / limité / hors bandes /
  réglementation inconnue) collé sur CHAQUE proposition (secours : colonne Remarque ; coordination ; Vérifier le plan),
  `MainWindow.reg_tag` (case décochée → « filtre coupé : non vérifiée »), `reg_note` toujours affichée (inconnue / coupé /
  « libre ici = d'après la mesure, licence = AVANT d'émettre ») ; `ready_checks` : pays sans liste = warn
  (`reg_unknown`). `COUNTRY_REFS` (décisions ARCEP 2015-0830…, Vfg. BNetzA, RIR1009, 47 CFR § 74.802 / § 15.236, LIPD
  2025, GUSL 272800…) et `COUNTRY_DOUBTS` (BE 470-786, CH ITU ≠ OFCOM, CA 652-663, NZ 622-698…) dans `reg_detail`
  (+ « autorisé ≠ libre ici »). Restent des références « selon le tableau CEPT, texte national non lu » (ES, IT, BE).
- **7.60.2 (Clément : coordination de 40 fréquences, plusieurs appareils -> interface figée > 90 s, la garde a relancé
  l'appli MAIS l'ancienne ne s'est pas fermée -> « COM4 accès refusé » ; « une méthode aléatoire, à la suite ça
  fonctionne pas en général »)** :
  - **Vraie cause du COM4** : `subprocess` n'était PAS importé au niveau du module → dans `_kill_tree`, `taskkill`
    levait NameError, avalé par `except` : la fermeture de l'arbre (7.52.1) n'a JAMAIS tourné sous Windows (le test 🧊
    du 13/11 a dû réussir par chance). `import subprocess` en tête ; `guard_beat` écrit « heure pid » ; la garde lit le
    pid (`_beat_pid`), le ferme (`_kill_pid`) et **attend qu'il soit vraiment mort** (`_pid_alive`, 6 essais) avant de
    relancer, noté dans garde.log. `check_names.py` lance pyflakes et échoue sur tout « undefined name ».
    test_garde : pid dans le battement, fermeture par n°. **Pas encore revérifié par Clément sous Windows.**
  - **Calculs longs hors de l'interface** : `MainWindow.run_heavy(fn, done, label, what, status)` (fil `threading` +
    QTimer 250 ms ; job {done, cancel}) ; `CoordDialog.compute` → `_computed`, bouton `go_btn` « ■ Annuler le calcul »,
    `closeEvent` annule ; gui_reel `coord_wait`.
  - **Coordination au hasard** : PURE `COORD_ORDERS` (random = meilleur de 3, random1, low), `COORD_TRIES`, `_pf_pick`
    (recherche par FENÊTRES 2 / 6 / 20 / 60 MHz autour de la graine, puis tout), `pf_fill(..., order, rng)` (graine
    tirée au hasard dans la plage, 3 retirages), `_fill_score` (le plus trouvé, puis le plus grand écart mini),
    `pf_fill_lots(..., order, tries, seed, progress, cancel)`. Mesuré (2 lots × 20, Wisycom + QLX-D, 470-694) : à la
    suite 450-500 s, au hasard 1 essai 19,5 s, 0 problème au pf_check. `CoordDialog.order_combo` « Méthode »
    (`plan_opts["coord_order"]`, défaut random). Manuel (chapitre coordination). PlanCheck / secours / intermod
    restent dans le fil de l'interface (calculs courts).
  - **Vitesse** : « occupé ? » vectorisé (PURE `level_at_many`, `busy_pred` avec `.vec`, `reg_allowed_pred(...).vec`,
    `MainWindow.reg_busy` avec `.vec`) : `pf_suggest` filtre toutes les candidates d'un coup ; `pf_suggest(..., skip,
    stats)` + budget de vérifications partagé entre les fenêtres de `_pf_pick` (sans ça, un cas SANS place refaisait 800
    vérifications exactes par fenêtre : 214 s → 55 s). Cas de gui_reel « coord par scène » (17 fréquences de démo, Wisycom
    au pas de 5 kHz, aucune place) : ≈ 60 s, en arrière-plan. gui_reel : `coord_order` = random1 (8 min max sur la CI).
- **7.60.3 (Clément : « on complète l'expérience » → vérifier le plan en arrière-plan + coordination plus rapide sans
  place)** : mesuré, `pf_check` reste < 1 s jusqu'à 120 fréquences → PAS mis en arrière-plan ; MAIS dès ~60 émetteurs
  avec le 5ᵉ ordre il était « trop gros » et ne vérifiait AUCUNE intermod (seulement les écarts) → repli sur le 3ᵉ ordre
  (`info["reduced"]`, message « ⚠ 5ᵉ ordre NON vérifié » dans PlanCheckDialog ; vaut aussi pour pf_suggest et « Prêt ? »).
  `pf_fill_lots(max_check=300)` (avant 800) : même résultat 40 / 40 sur 2 × 20, cas sans place 40 s → 15 s.
  Bibliothèque `.lst4` (Clément ne la trouvait pas) : toujours mode expert + outils de coord › 🎛 Profils d'appareil ›
  📚 ; gardée dans `%APPDATA%\TinySAMonitor\appareils_eazyrf.json` ; seuls ses appareils ont une PLAGE (`lo` / `hi`).
  **v7.60.3 : compilation sur main refusée (« Actions budget », limite de dépense GitHub, 15/11/2026)** : pas de release ;
  exe dans la pré-release `test-ui-validation`. Relancer le workflow sur main quand Clément a relevé la limite.
- **7.61.0 (Clément : « ok pour 1/2/3/4 », « faut que ça calcule en fonction des bandes, même en fréq de secours »,
  bibliothèque : « que en mode expert »)** :
  - **Bande de l'appareil** : PURE `rx_band(profil)` ((lo, hi) des profils qui en ont : bibliothèque, plans importés,
    perso ; None pour les intégrés), `band_issue(f, bw, bande)` (problème `kind="band"`, `pf_issue_text` « hors de la
    bande de son appareil »), `band_clip(a, b, bande, bw)`. PlanCheckDialog : `_bands`, problème « band » en tête,
    « Proposer » limité à la bande (près puis toute la bande) ; « Prêt ? » le compte. RescueDialog : `rx_combo`
    (appareil de la fréquence choisie dans la liste d'office), `_from_rx` (écart, tolérance 2 TX, filtre, plage calée
    sur la bande), `search` coupe à la bande, grille = max(25 kHz, pas de l'appareil) calée sur le pas ;
    `add_free_freqs(..., rx)`. CoordDialog : chaque lot coupé à la bande de son appareil (`_clipped` → message).
    Clic droit groupe › 📻 › « 📚 Depuis la bibliothèque (avec sa bande)… » (expert) → `pick_library_rx(key)` →
    `RxLibraryDialog(pick=True)` (« ＋ Ajouter à ce groupe », se ferme).
  - **Coordination** : `pf_fill(..., tick, cancel)`, `pf_fill_lots(..., found)` → `CoordDialog.bar` (QProgressBar
    « trouvées / demandées ») ; PURE `coord_blockers` (grille du lot, plan FINAL : hors pays > occupé mesuré > trop
    près > reste = intermod), `coord_why_text`, `coord_why_advice` → « Ce qui bloque (lot) : … » + conseil.
  - **Résumé du matin** : PURE `morning_summary(events)` (verdict, heures dans l'ordre — la nuit passe minuit, même
    heure 24 h après = « 10' » —, `hot`, alarmes regroupées par (type, nom, MHz) de … à …, instables ≥ `MS_FLAP`
    OCCUPÉ, `moved` = NOUVELLE FRÉQUENCE, `top`), `_svg_hours`, `morning_html`, `MS_CSS` ; en tête de TOUS les rapports
    (`build_report_html`), donc du bilan du mode festival. 📊 Analyser › 🌅 Résumé de la nuit (`open_night_summary` :
    tout le journal, `rapports/resume_*.html`, ouvert dans le navigateur).
  - **Ménage** : nom du logiciel de coord retiré des commentaires / docstrings (script tokenize) et du pied des rapports ;
    restent les noms de FORMAT visibles (import .ezrf3, filtres de fichiers) et les clés de données (`"eazyrf"`,
    `appareils_eazyrf.json`, `EazyRFds`).
  Testé : test_plan / test_v7 (PURE), gui_reel (bibliothèque → groupe, plan hors bande, Proposer, secours, coord,
  résumé). **Pas essayé par Clément.**
- **7.62.0 (Clément : « pour simplifier et aller vite » → 4 fonctions, « 1/2/3/4 »)** :
  - **🆘 Remplacer ce micro** : `MainWindow.replace_args(w)` (plan actif, appareil + bande de chaque fréquence,
    max hold occupé, pays, préparé dans le fil de l'interface) → `replace_compute(a, n)` (staticmethod, calcul PUR :
    pas ≥ 25 kHz multiple du pas de l'appareil, ±10 puis ±40 MHz, `pf_suggest(n=14·n, max_check=80)`, propositions
    espacées d'au moins max(200 kHz, écart) ; rien avec toutes les règles → 2A − B seulement, `relaxed` signalé
    « règles allégées ») → `replace_decorate` (niveau, `reg_tag`) ; `suggest_replacements` (direct) ;
    `replace_watch(w, f, how)` (alarmes CONFLIT / ABSENT de l'ancienne effacées, journal NOUVELLE FRÉQUENCE,
    undo). `ReplaceDialog` (non modale, `self._replace`, `run_heavy`, gros boutons). Entrées : clic droit liste,
    bouton « 🆘 Remplacer ce micro » du panneau des alarmes (`_alarm_watch`), tuiles du mur et du mode Show
    (fenêtre au-dessus du plein écran), 🎚 Surveiller › « Un micro est brouillé ? ». Mesuré : ~1 s sur 35 émetteurs
    tirés au hasard, 11 s sur la liste de démo très chargée (passe en 2A − B).
  - **⌨ Saisie express** : PURE `parse_quick_entry(text)` (morceaux par ligne / « ; » / « , » non décimale / « / » ;
    nombre à virgule ≥ 30 ou entier ≥ 100 = MHz, 30 000–6 000 000 ou « kHz » = kHz ; nom = mots avant (après le
    dernier « : »), + 1–2 mots après ; plusieurs fréquences = « nom 1, nom 2 » ; doublons retirés) → (lignes,
    ignorés) ; `quick_names(items, prefix, taken)`. `QuickAddDialog` (non modale, `self._quickadd`, aperçu,
    scène / groupe modifiables, statut, préfixe, Ctrl+Entrée) ; `add_watch_dialog(text)` l'ouvre (l'ancienne saisie
    d'UNE fréquence a disparu) ; `in_scanned_band(f)`.
  - **📐 Nouveau show depuis un modèle** : PURE `show_template(doc)` (`TEMPLATE_DROP` : watch, site_scans, states,
    state_cur, ezrf_link, planning, scope, focus ; tnt.place / manual / plan vidés ; ref vide ; meta vide sauf le
    lieu ; `template` = nom d'origine) ; `new_show_from_template(path)` → `clear_show_data(template=doc)` ; 🎪 Shows.
  - **📱 Page Tech** : actions `quick_add` {text, scene, group, status}, `suggest` {key} (calcul via `run_heavy`,
    `self._tech_sugg` {key, name, freq, busy, cands} dans `tech_state` → `sugg`), `replace` {key, f}, `sugg_close`.
    Page : zone « ⌨ Ajouter des micros » (textarea `#tqa`, scène / groupe avec `datalist` `#tscl` / `#tgrl`),
    bouton 🆘 par micro (`data-trp`), encadré `#tsg` (boutons `data-trf`, confirmation).
  Testé : test_v7 (saisie, modèle), test_alertes (page Tech dans Chromium), gui_reel (saisie, remplacer, modèle,
  Tech). **Pas essayé par Clément.**
- **7.62.1 (6ᵉ audit externe, sur la 7.62.0 ; la moitié de ses idées existait déjà : assistant 7.59, « Prêt ? » 7.39,
  Ctrl+K 7.47, import avec aperçu)** : `ReplaceDialog._computed` : propositions `relaxed` → message en tête orange
  « ⚠ … 2A − B SEULEMENT (A + B − C et 5ᵉ ordre NON vérifiés) » (avant : « compatibles avec tout ton plan » même en
  règles allégées) ; `parse_quick_entry` : entier sans unité lu en kHz → `khz=True` → colonne Remarque de l'aperçu
  « ⚠ nombre lu en kHz : vérifie » (code postal 75011 = 75,011 MHz) ; **clic droit sur une alarme** (`alarm_menu` :
  voir, 🆘 remplacer, 🔎 chasser, ⚡ d'où ça vient si coordination, ✔ acquitter). Manuel : la section « Un micro est
  brouillé » est GÉNÉRÉE depuis `docs/src/nouveaux_*.html` (chapitre reagir) — les ajouts 7.61 / 7.62 faits dans
  `docs/manuel.html` avaient été écrasés par make_manual : remis dans la source. Idées de l'audit NON faites (à
  proposer à Clément) : export PDF de préparation, détection de dérive (les 5 autres faites en 7.63).
- **7.63.0 (Clément : « 1/2/3/4 5 !! » sur les idées de l'audit)** :
  - **📱 QR code** : dépendance **`segno`** (pur Python, BSD ; requirements.txt, `--hidden-import segno` dans le workflow
    et build.bat, vérifiée par `self_test`). PURE `web_link(ip, port, vue)` ; `qr_image(texte, px)` (QImage, niveau M,
    marge 4) ; `QrDialog` (`self._qr`, adresse = `local_ips()`, vue = vues partagées, Copier, PNG) ; `open_qr` ;
    🎚 Surveiller › À distance + bouton `qr_btn` dans AlertsDialog. gui_reel relit le PNG avec OpenCV si présent
    (`opencv-python-headless`, PAS dans requirements : test local seulement).
  - **📸 Avant / après** : PURE `scan_changes(FA, LA, FB, LB, thr)` (new = sous le seuil avant, gone = sous le seuil
    après, up / down ≥ 6 dB ; via `compare_spectra` + `scan_peaks`), `CHANGE_LABELS` ; SitesDialog onglet « Comparer »
    : `cmp_mode` (sites | time), `chg_table`, `_cmp_mode_changed` (A = le plus ancien), `_chg_view` ;
    `open_sites(before_after)`, `open_before_after` (📊 Analyser).
  - **⧉ Dupliquer** : PURE `copy_name` ; `duplicate_layer(key)` (groupe dans sa scène / scène + groupes, deepcopy,
    sans fréquences) ; clic droit de l'arbre.
  - **🕘 Historique** : PURE `watch_rows`, `watch_diff` (apparié par (nom, MHz), puis nom, puis MHz), `history_norm`,
    `HIST_MAX` 1000, `HIST_WHAT`. ⚠ `self.history` = rémanence du spectre (dict) : le nôtre est **`self.mod_history`**
    (clé de config / show « history », SHOW_KEYS, ligne `coord_tools=`) ; `history_track(who)` (chaque seconde dans
    `_alarm_tick` ; « 📱 nom » autour de `tech_do`, « 🔗 plan » autour de `apply_ezrf_diff` → `_apply_ezrf_diff`,
    « ↶ Annulé / ↷ Rétabli » dans `_undo_restore`) ; `_apply_config` remet `_hist_rows` à None (ouvrir un show ne crée
    pas d'entrées) ; nouveau show / modèle = vidé (`TEMPLATE_DROP` + history). `HistoryDialog` (`self._hist_dlg`,
    filtre, CSV, vider), `open_history` (📊 Analyser).
  - **📦 Sauvegarde ZIP** : PURE `config_public` (sans `notify`, ni web pin / password / tech), `bundle_pick` (7 jours,
    60 Mo, récents d'abord) ; `export_bundle(path)` : show.tsashow, config_sans_secrets.json, diagnostic frais,
    journaux / rapports / diagnostics de la semaine, crash.log, garde.log, LISEZMOI.txt ; 🎪 Shows + 🔌 Matériel.
  ⚠ test_reseau exécute le morceau `def local_ips():` → `class Notifier:` SANS Qt (et test_alertes `class Notifier:` →
  `class AlertsDialog`) : n'y mettre AUCUNE classe Qt (QrDialog / HistoryDialog y étaient → CI Linux en échec ; déplacés
  avant `class ReplaceDialog`).
  Testé : test_v7 (PURE), gui_reel (QR relu par OpenCV, dupliquer, historique, ZIP sans secret, avant / après).
  **Pas essayé par Clément** (QR à scanner avec un vrai téléphone).
- **7.64.0 (Clément : « cartographie avec les différents tiny, un peu en Araneo » = logiciel réseau de Luminex : canevas,
  glisser-déposer, plan facultatif ; « go 1 et 3 »)** :
  - **🗺 Carte du site** : PURE `MAP_DEFAULT`, `MAP_STEP` (40), `map_key("scene"|"dev", nom)`, `map_cfg_norm` (pos
    {clé: [x, y]}, bg / bg_op / bg_scale / bg_pos, grid, heat ≤ `HEAT_MAX`), `map_auto_place` (scènes en haut, tinySA
    dessous, à droite de l'existant), `map_snap`. Qt (placées AVANT `ReplaceDialog`, hors des morceaux lus par
    test_reseau / test_alertes) : `MapNode` (QGraphicsObject glissable, couleur = `tone_color` de la scène / tinySA en
    ligne, bande = couleur de la scène), `MapScene` (`sync`, `refresh` (chaque seconde si la fenêtre est visible),
    `update_links` (courbes tinySA → `dev_scenes`, pointillés si perdu), `sync_bg`, `sync_heat`, `node_dropped` (tinySA
    déposé SUR une scène → `toggle_dev_scene`), `node_open` (scène → `set_scope`), `mark(x, y)`), `MapView` (grille dans
    `drawBackground` = points discrets, molette = zoom, Ctrl + molette = taille du plan, fond = déplacement, pas de
    barres de défilement ; clic SIMPLE (pas un glisser) hors tuile pendant une chasse = point noté), `MapWindow` (vraie
    fenêtre, `self._map`). **Version épurée (Clément : « plus user friendly et plus épuré »)** : plus de palette « À
    placer » (`tick` pose tout seul ce qui manque), une barre fine 🖼 Plan (menu : image, opacité en `QWidgetAction`,
    `bg_move` « Caler le plan », retirer) / 🔥 Chaleur (menu `_build_heat_menu` : afficher, fréquence chassée, effacer,
    aide) / `count_lbl` / ⤢ Tout voir / ⋯ (grille `grid_act`, `relayout`, export) ; bulle `banner` en haut (`hint(txt,
    s)`, rappel de chasse tant que `marking()`), zoom + / − et `MapHeatLegend` posés sur la vue.
    MainWindow : `self.map_cfg` (config sur la ligne `coord_tools=` via `_map_cfg_dump`, SHOW_KEYS « map » ; modèle de show
    : points vidés ; nouveau show : carte vidée), `map_scene()` (créée à la demande), `open_map` (1re fois : tout posé),
    `map_png(maxw)` → (PNG, rectangle). Menus 🎚 Surveiller › Pendant et 🔌 Matériel › Mes tinySA.
  - **🔥 Carte de chaleur** : PURE `heat_for`, `heat_freqs`, `heat_scale` (10 dB mini), `heat_rgb` (bleu → jaune → rouge),
    `heat_hot`, `heat_field` (Clément : « led points chaud et froid, rendu bizarre » → dégradé CONTINU façon relevé Wi-Fi :
    noyau gaussien σ = 0,55 × `HEAT_REACH` (170), opacité pleine jusqu'à 0,4 × reach puis smoothstep) + `heat_rgba` →
    une seule image lissée sous les tuiles ; points = petits ronds nets + étiquette du niveau (unité choisie), le plus
    fort cerclé ;
    aides désactivables (Clément : « on fait tout mais désactivable », 🔥 Chaleur › Sur la carte, `set_heat_opt`,
    `map_cfg` `heat_iso` / `heat_arrow` (oui) / `heat_path` (non) / `heat_reach` (`HEAT_REACHES` 90 / 170 / 300)) :
    PURE `heat_isolines` (carrés qui marchent, tous les 5 dB, là où opacité ≥ 0,35), `heat_arrow` (du DERNIER point vers
    le plus fort, `here` si déjà dessus ou < 3 dB → texte dans la bulle), `heat_path`  ; rendu (Clément : « la flèche et la traînée ça fait
    Paint ») : « tu es ici » (halo + anneau accent) sur le dernier point + 3 chevrons ››› dégradés + pastille « +N dB »,
    parcours = trace Catmull-Rom fine, opacité croissante vers les derniers points ;
    réglages (Clément : « modifier les couleurs, intensité et tout ») : PURE `HEAT_PALETTES` (classic, thermal, viridis,
    ice, mint, accent = accent du thème), `heat_stops(pal, accent)`, `heat_rgb(..., stops)` / `heat_rgba(..., opacity,
    stops)` multi-couleurs, `heat_hex` ; `map_cfg` `heat_pal`, `heat_op` (0,1–0,95, curseur `heat_slider` dans le menu),
    `heat_labels`, `heat_dot` (`HEAT_DOT_SIZES` 0,7 / 1 / 1,5), `heat_trail` (`HEAT_TRAIL_WIDTHS` 1,2 / 2 / 3,5), `heat_dir`
    (`HEAT_DIR_COLORS` : accent | hot | #rrggbb, PURE `heat_dir_color`) ; `map_marks_rel` envoie la couleur `c` au
    téléphone (`#hdots`) ; point = {x, y, level (niveau ACTUEL de `HuntDialog`), f, t}, refusé sans chasse en cours. PC : clic sur la
    carte pendant la chasse. Téléphone : `hunt_request` actions `mark` {x, y ∈ [0, 1] de l'image} / `unmark` ; GET `/carte.png`
    (`WebServer(get_map=…)`, vues chasse ou terrain partagées) = `self._map_png` refait toutes les 5 s si quelqu'un regarde
    « chasse » (`_map_web_tick`) ; `map_mark_rel` (image → carte via `_map_rect`), `map_marks_rel` → `hunt_state` (`map`,
    `map_t`, `marks`) ; vue Chasse : « 🗺 Où suis-je ? » (`#hmi`, `#hdots`, `huntCmd`, `huntMark`). GPS du téléphone PAS
    utilisé (page en HTTP : le navigateur refuse la position).
  Testé : test_v7 (PURE), gui_reel (posé d'office, tinySA déposé sur une scène, plan, point refusé sans chasse, point avec
  la chasse en démo, « je suis ici » par l'image, PNG), test_alertes (vue Chasse dans Chromium : plan affiché, points,
  toucher le plan → `mark` x / y). **Pas essayé par Clément.**
- **7.65.0 (7ᵉ audit externe, sur la 7.64.0, transmis par Clément ; 2 bugs reproduits PUIS confirmés sur la 7.64.0)** :
  - **Avant / après** : PURE `scan_segments(F)` (plages mesurées, coupées par `scan_gaps`), `covered(x, segs, pad)`,
    `interp_measured(F, L, x)` (NaN hors plage ET dans les trous) ; `compare_spectra` et `scan_changes` ne comparent que
    là où les DEUX scans ont mesuré (avant : `np.interp` par-dessus un trou → « disparu » à 500 MHz dans une zone jamais
    balayée) ; `scan_changes` : doublon = zones qui se RECOUVRENT (`_zone` = f ± largeur / 2 ± ½ pas), plus « à moins de
    300 kHz » (une hausse de 8 dB à 500,2 était effacée par un « apparu » à 500,0). `diff_spectra` réutilise `covered`.
    Tests test_v7 avec les deux cas exacts de l'audit.
  - **Carte** : `_fin` / `MAP_COORD_MAX` (NaN, inf, 1e100 écartés partout dans `map_cfg_norm`) ; `map_png` pose ce qui
    manque (`auto_place`) et rafraîchit (carte du PC fermée → la scène manquait sur l'image du téléphone) ; **plan de
    fond embarqué dans le show / le ZIP** : PURE `map_bg_embed` / `map_bg_extract` (`bg_data` base64 ≤ `MAP_BG_MAX_B64`,
    `bg_name`), `MainWindow.map_for_show` (dans `save_show_to` et `export_bundle`), `_map_bg_restore` (à l'ouverture :
    recopié dans Documents/TinySA Monitor/Plans si le chemin n'existe pas ici ; `bg_data` jamais dans config.json) ;
    **état de surveillance d'une scène** : PURE `map_scene_monitor(running, devs, états)` → off / lost / nodata / partial
    / ok ; `MapScene.scene_devs` (rattachés, sinon tous) ; pastille « Surveillance perdue » / « Pas de mesure » / « Mesure
    partielle », points gris pour les micros sans mesure fraîche.
  - Pas fait (proposé par l'audit, plus tard) : diagnostic RF automatisé, analyse des perturbations répétitives, couche
    commune TinySA / SDR (V8). Rappels de l'audit déjà documentés : relais sans authentification, page web en HTTP.
- **7.66.0 (Clément : « dans scans par lieu je peux pas sélectionner plusieurs scans et supprimer en même temps ou ne
  plus les afficher » ; plan réel « PlaneR Fest 2026 Samedi » : « T2 = 2ᵉ scène, T1 = 1re, l'import crée plein de
  scènes, il faudrait l'option de rebouger les choses à l'import »)** :
  - **Scans par lieu, plusieurs à la fois** : `SitesDialog.lst` en `ExtendedSelection` ; `sel_names` (sélection, sinon
    le courant), `delete(names)` (tous, `undo_track` AVANT et après → Ctrl+Z ramène tout), `move` / `do_move(names)`,
    `set_hidden` / `only_selected` / `toggle_selected` (Espace) / `select_scene`, bouton `vis_btn` « 👁 Afficher » (menu),
    clic droit `list_menu`, `sel_lbl` « N scans choisis » ; `fill` garde la sélection (`setCurrentItem(..., NoUpdate)`,
    sinon le courant effaçait la sélection). **Masqué = mémorisé** : clé `hidden` du scan (gardée par
    `site_scans_norm`, donc config + show), PURE `site_set_hidden`, `site_visible` ; `sites_for_scope` ne prend que les
    visibles (spectre principal) ; la coordination (`coord_docs`) les prend TOUS, comme avant. PURE `site_replace` : le
    scan continu réécrit toutes les 30 s garde sa place et son masquage (avant : renvoyé en fin de liste).
  - **🗂 Ranger les scènes à l'import d'un plan** : PURE `EZRF_PREFIX`, `_abbrev` (« TERMINAL 2 » → « T2 »),
    `ezrf_scene_guess(src, candidates)` (préfixe « T2 - » = initiales ou nom d'une autre scène de la MÊME zone, multi-zones
    « Zone · … » géré), `ezrf_auto_map`, `ezrf_map_norm`, `ezrf_remap(entries, map)` (groupe : `keep` sections / `source`
    nom du passage / `both` « passage · section », défaut proposé), `EZRF_GROUP_MODES` ; `EzrfImportDialog` : tableau
    `map_tbl` (scène du plan / arrive dans la scène = combo modifiable / groupe), « Ranger automatiquement », « Tout
    laisser comme dans le plan », aperçu `_fill_tree` qui suit, `mapping()`, `entries()`, `fit_dialog` 820 × 760 ;
    `opts["map"]` → `apply_ezrf` + `ezrf_link["map"]` → `_ezrf_tick` (suivi du fichier rangé pareil).
    **🎬 Planning d'après les noms** : PURE `EZRF_TIMES`, `ezrf_planning(entries)` (un créneau par groupe dont le nom
    contient « HH:MM - HH:MM », tous les jours, passe minuit) ; case `plan_chk` (décochée d'office) → `opts["planning"]`.
    Sur le vrai plan de Clément : 8 scènes → 2 (TERMINAL 1 / 2), 8 créneaux trouvés (capture `apercu/import_planer.png`).
    **Pas essayé par Clément.**
- **7.66.1 (Clément : « dans le README c'est clairement cité », « vas-y tu peux »)** : nom du logiciel de coord retiré du
  README, de TOUS les textes de l'appli / lang_en et des manuels FR + EN (sources `docs/src` comprises) : on écrit « .ezrf3 »
  (nom de format) ou « ton logiciel de coordination ». Le « kind » du plan importé vaut maintenant ".ezrf3" ; un
  `ezrf_link` enregistré avec l'ancien nom est migré dans `_apply_config`. Restent (internes, voulus) : balise XML du
  format, clés de données / nom de fichier de la bibliothèque. (25/11/2026 : nom de nouveau permis dans le manuel, le README et ce
  fichier, comme WWB / WSM — voir l'en-tête ; pas dans les textes de l'appli.)
  Journal (journal de Clément du 16/11/2026 : 1 097 lignes en 1 h 45, dont 310 OCCUPÉ / « Libre (1 s) » pour UN micro
  AD4Q à 487,050 dans le canal TNT 23, ~−80 dBm pile au seuil, ET déjà 💤 éteint) : `OCC_LOG_S` (3 s) — une occupation
  sans statut « doit rester libre » n'est notée que si elle dure (`w["occ_log"]` False → True), les plus courtes sont
  comptées (`w["blips"]`) dans la note de la prochaine OCCUPÉ ; micro en pause (💤, état, planning) = rien au journal.
  CONFLIT / INTERMOD toujours immédiats. smoke_test / smoke_test2 mettent `OCC_LOG_S = 0` (anciens tests).
  **🏷 Noms d'après le groupe à l'import** (idée de Clément, « que ça reste une option ») : `ezrf_entries(doc, skip_off,
  naming)` (PURE `EZRF_NAMINGS` dev | group | both, `ezrf_group_label` = nom du groupe du plan sans « T2 - » ni horaire) :
  fréquence SANS nom → « THE BROWNING · MICS 1 » (modèle dans la note) ; nom écrit dans le plan gardé. Combo
  `EzrfImportDialog.naming` (`.ezrf3` seulement, s'il y a des fréquences sans nom), `opts["naming"]` →
  `ezrf_link["naming"]` (suivi). Les noms suivent l'ordre du fichier : réordonner les lignes du plan les renumérote.
  **Démo → tinySA en pleine surveillance** (Clément : « ça a fait planté le soft et il a pas redémarré ») : la carte ①
  de l'accueil décochait la démo pendant la surveillance (le balayage continuait en démo). `switch_source(demo, index)` :
  arrêt propre, bascule, reprise (`toggle_run(auto=True)`). Cause exacte du plantage NON trouvée (pas de crash.log) ;
  la garde ne relance que si l'appli a été lancée avec `--garde` (démarrage Windows ou « 🛡 Relancer sous garde »).
- **7.66.2 (crash.log de Clément, 16/11/2026, 7.66.0 : « access violation » dans `ScanWorker.run`, boucle de reconnexion ;
  garde.log : pas lancée sous garde ce jour-là)** : reproduit hors écran avec l'ancienne version : des fils de balayage
  pouvaient être recréés alors qu'un ancien tournait encore → deux sources mélangées (−64 / −99 dBm en alternance
  dans son journal). `_retire_workers` (appelé avant de recréer `self.workers`) : ancien fil vivant → interruption +
  `blockSignals(True)` (muet) + gardé dans `self._zombies` jusqu'à sa fin ; fil fini → `deleteLater`. `w.setParent(self)`
  (jamais détruit par Python en cours de route). `closeEvent` : attend aussi les `_zombies`, `force_close` si bloqué.
  Le plantage lui-même n'a PAS été reproduit sous Linux (cause la plus probable, pas prouvée).
- **7.66.3 (Clément : « j'arrive pas à calculer des fréquences en plus, c'est le seuil auto ? » ; « ça marche mieux avec le
  scan .ezrf3 importé depuis tinySA, bizarre que le bruit soit si haut chez nous »)** : en seuil auto, `thr_spin` = bruit
  INSTANTANÉ + 13 dB, comparé au MAX HOLD (des heures de pics de bruit, plus hauts) → « occupé 99 % ». PURE `BUSY_MODES`
  (auto | global | fixed), `BUSY_MARGIN` 15 dB, `busy_lim(L, mode, margin, fixed, glob)` (auto = 10ᵉ centile du spectre
  évité + marge). `MainWindow.busy_limit(L, mode, weak)` (défaut : auto si `thr_auto`, sinon le seuil de la fenêtre) ;
  `plan_opts` busy_mode / busy_margin / busy_fixed (config). Utilisé par CoordDialog (rangée « Occupé si » :
  `busy_mode`, `busy_val`, `busy_lbl` = seuil obtenu + % du spectre au-dessus, `_busy_ui` / `_busy_store` /
  `_busy_lim` / `_busy_preview`), `replace_args`, PlanCheck « Proposer », RescueDialog (valeur de départ du seuil en
  seuil auto). **Pas vérifié avec le vrai max hold de Clément** (son scan .ezrf3 : médiane −104, p10 −110 dBm).
  **RBW des scans** (Clément : « pour un scan pour la coord c'est important de le marquer », « qu'il faut un RBW fin ») :
  `site_scan_doc(..., rbw, rbw_est)` (kHz ; `rbw_est` = RBW auto estimée d'après le pas par `auto_rbw` ; « mixed » =
  scans de RBW différentes fusionnés), gardé par `site_scans_norm`, `site_scan_info` → rbw / rbw_est ; PURE `rbw_merge`,
  `rbw_combine`, `rbw_text`, `rbw_tag` (« RBW30k » dans les noms de fichiers exportés), `COORD_RBW_MAX` 30 kHz (conseil,
  pas une norme), `COORD_RBW_TIP`, `rbw_coord_line`. MainWindow : `scan_rbw(F)`, `live_rbw`, `coord_rbw(src)`,
  `set_rbw_fine` ; RBW notée par SitesDialog (Garder), `_sites_tick`, `terrain_save` (scans importés : inconnue).
  CoordDialog : rangée « Scan : » (`rbw_lbl` orange si > 30 kHz / inconnue / mélangée, bouton `rbw_btn`) ; Scans par
  lieu : infos, note, message d'export ; ExportScanDialog : ligne RBW ; rapport du site : colonne RBW.
- **7.66.5 (2ᵉ crash.log de Clément, 17/11/2026, exe 7.66.2, RBW 10 kHz + 3 000 points, pas lancée sous garde)** :
  « access violation » au MÊME endroit que le 16/11 (fil `ScanWorker`, boucle d'attente après « liaison perdue ») ; le fil
  de l'interface jouait le son d'alarme APPAREIL (`SoundOut.play` → `QAudioSink.start`). Les deux crashs suivent une
  liaison perdue. `ScanWorker.requestInterruption` / `isInterruptionRequested` surchargés : drapeau Python `_stop_ev`
  (threading.Event), le fil n'appelle plus l'objet Qt pendant l'attente. **Cause exacte toujours pas prouvée** (pas
  reproduite sous Linux) ; cause de la liaison perdue inconnue → demander le 🩺 diagnostic automatique de ce moment.
  Sa config : RBW 10 kHz forcée, 3 000 points sur 470-694 = un point tous les 75 kHz → PURE `scan_step_khz`,
  `rbw_coord_line(..., step)` prévient si le pas > 1,5 × RBW (signaux qui passent entre les points).
- **7.67.0 (Clément : « go 2/3/4 » sur : scan de coord automatique, dossier PDF, perturbations qui reviennent)** :
  - **📏 Scan pour la coordination** : `CoordScanDialog` (non modale, `self._cscan`, `open_coord_scan`, 📋 Préparer › 1.) :
    RBW 10 / 30 (conseillé) / 100 kHz, durée (5 min), lieu + étiquette ; `start` mémorise RBW / points / max hold /
    surveillance, règle la RBW, points ⚡ Auto équilibré (`auto_scan_step` met le pas ≤ RBW), max hold + `reset_max`,
    lance la surveillance si besoin ; `_tick` (1 s) ; à la fin `fresh_FL(use_max)` → `site_scan_doc(..., rbw)` dans
    `site_scans` (`snapshot_name`), réglages remis, surveillance arrêtée si elle ne tournait pas. Annuler = rien gardé.
  - **🖨 Dossier de préparation** : PURE `PREP_CSS`, `prep_html(info, tr, img)` (QTextDocument : HTML simple) ;
    `spectrum_qimage(F, L, thr, marks)` (QPainter, sans pyqtgraph) ; `MainWindow.prep_info()` (show_meta date_from /
    date_to, plan trié par scène, `reg_tag` des émetteurs, `reg_detail`, `tnt_measure_now`, scans + RBW, `pf_check` si
    `coord_on`, `COORD_NOTE` en bas), `export_prep(path)` : .pdf (`QPdfWriter` A4 + `QTextDocument.addResource`) ou
    .html (image en base64). 📋 Préparer › 4.
  - **🔁 Perturbations qui reviennent** : PURE `journal_csv_rows` (journal_AAAAMMJJ.csv), `recurring_events(rows,
    kinds, tol, min_days, on_statuses)` (même (événement, nom, MHz), minutes circulaires (23:50 ≈ 00:05), regroupement
    glouton : le centre qui couvre le plus de jours), `recurring_text`, `RECUR_KINDS` / `RECUR_LABELS` ; OCCUPÉ des
    statuts « doit émettre » ignoré. `MainWindow.journal_rows(days)`, `RecurringDialog` (jours, ± min, jours mini,
    case OCCUPÉ, double-clic = chasse), `open_recurring` (📊 Analyser). ⚠ 1er jet : boucle infinie (éléments recréés au
    lieu d'être repris de `left`) → test_v7 tué faute de mémoire ; corrigé.
  Testé : test_v7 (journal, répétitions dont minuit, dossier HTML), gui_reel (scan de coord raccourci à 4 s en démo :
  RBW 30 / Auto, gardé avec sa RBW, pas ≤ RBW, réglages remis ; PDF « %PDF- » ; HTML avec image ; perturbations sur 3
  faux journaux). **Pas essayé par Clément ; PDF jamais ouvert sous Windows.**
- **7.67.1 / 7.68.0 (Clément : « go 1234, important la SDR avec démodulation, écoute » + son 1er dossier PDF)** :
  - **Dossier de préparation revu** (PDF de Clément : spectre minuscule, 48 traits par-dessus, vide 700-820 MHz, tout
    « en pause ») : PURE `axis_panels` (axe COUPÉ : plages de `scan_segments` réunies si l'écart < max(10 MHz, 5 %)),
    `prep_dates` (« 12/11/2026 », un seul jour = une date) ; `spectrum_qimage(..., tv=)` 1600 × 560, une case par groupe
    de bandes + coupure, canaux TV grisés et numérotés, fréquences du plan = ▼ en haut, texte en pixels ;
    `info["img_w"]` = largeur de la page PDF ; lignes `why` (state = « hors état », muted = « éteint (je sais) »),
    résumé « N hors de l'état actif « X » », colonnes Appareil / Réglementation / Note retirées si vides, groupe pas
    répété. Ses 48 fréquences étaient toutes hors de l'état 📸 actif (pas un bug de la pause).
  - **🩺 Diagnostic RF** (`RfDiagDialog`, `self._rfdiag`, `open_rf_diag` ; 🎚 Surveiller › Avant d'ouvrir et 🔌 Matériel ›
    Mesure et dépannage) : PURE `rf_diagnose(info)` -> [{key, level, title, text, advice, fix, arg}] (saturation
    `sat_level`, bruit de fond vs `expected_floor` (`NOISE_DBM_HZ` −160 / −150 dBm/Hz avec / sans LNA, **valeurs de
    départ**), zones bruyantes hors TV `noisy_zones` sur `floor_curve`, seuil global trop bas / trop haut (seuils
    fixes), pas > 1,5 × RBW, micro « pile au seuil » (`flap_count` ≥ `DIAG_FLAPS` en 30 min ET niveau habituel à
    ± `DIAG_EDGE_DB` du seuil -> `suggest_own_thr`), micro dans un canal TV à moins de `DIAG_TV_MARGIN` au-dessus de la
    télé, « doit émettre » noyé, signaux hors liste) ; `rf_diag_summary`. MainWindow : `rf_diag_info()`,
    `watch_by_key`, `diag_set_thr(clé kHz, dBm)` (journal « RÉGLAGE »), `open_replace_key`. `update_watch_levels`
    garde `w["_flips"]` (heures des passages libre <-> occupé) et `w["_lvh"]` (niveaux toutes les 2 s, 400 max) :
    clés en `_`, PAS enregistrées. Textes en plusieurs lignes (« \n ») : traduits ligne à ligne, affichés sur une ligne.
  - **📍 Une fréquence partout** (onglet 5 de Scans par lieu ; clic droit liste « 📍 Niveau de cette fréquence dans
    chaque lieu », `open_sites(freq=(f, bw))`, `SitesDialog.show_freq` / `ev_draw`) : PURE `level_everywhere` (max à ±
    (0,1 + bw/2) MHz, None si non mesurée, bruit local, marge, RBW), `level_everywhere_text`.
  - **Fréquence image dans la coordination auto** : `pf_fill_lots(..., img=)` (FI des fréquences existantes, lot
    `img`), `pf_fill(..., img, new_img)`, `_pf_pick(..., IM, new_img)` -> `pf_suggest(img=)` ; `CoordDialog.compute`
    passe la FI des profils (avant : seuls Vérifier le plan / Proposer / Remplacer la vérifiaient) ; « Prêt ? » aussi.
  - **Prises pour la V8 (sans effet en V7)** : `MainWindow.FREQ_ACTIONS` [(texte, méthode(f, w))] proposées par
    `add_freq_actions` / `run_freq_action` dans le clic droit d'une alarme, des tuiles du mur et du mode Show, et en
    boutons dans la chasse ; `WebServer(extra_get={chemin: (vues, fn(query) -> (octets, type))}, extra_pin={chemin:
    (lecture, rappel)})` ; `MainWindow.web_extra()` -> ({}, {}) ; page : `EXT[vue] = {mount(el), update(st)}`,
    `Object.assign(VIEWS, /*__VIEWS_X__*/{})`, `/*__EXTRA_JS__*/` remplis par `web_page_full()` (WEB_VIEWS ajoutées
    après `_WEB_BASE_VIEWS`, `WEB_EXTRA_JS`). La V8 les remplit en fin de fichier (affectations au niveau du module).
- **7.68.1 (Clément, 25/11/2026 : « tu peux citer EazyRF comme WWB ou WSM »)** : commit 7f4ba10 (7.66.1) défait pour
  l'appli et `lang_en.py` : `kind` du plan importé = « EazyRF » (comme « Shure WWB »), titres / menus / bulles « EazyRF » ;
  un `ezrf_link` enregistré avec « .ezrf3 » (7.66.1 → 7.68.0) est migré dans `_apply_config`. Manuel FR + EN, PDF, README :
  le nom est revenu là où il s'agit d'EazyRF (import, suivi) ; les mentions génériques (« un logiciel de coordination »)
  restent. Toujours aucune comparaison avec un autre logiciel.
- **8.0.0 (Clément, 26/11/2026 : « on passe en V8 » -> « Okey gooo »)** : la branche `v8-sdr` (étapes 1-22 + audit) devient la
  version unique. `APP_VER = "8.0.0"` (la surcharge « 8.0-dev (base …) » retirée) ; SDR marqué « bêta » (`RF_MODES`,
  sous-menu SDR) ; manuel SDR fondu dans le manuel principal : partie **E. Le SDR (bêta)** de `tests/make_manual.py`
  (chapitres `sdr-*` lus dans `docs/src/sdr_fr.html` / `sdr_en.html`, préfixe car « surveiller » existait), Aide = F ;
  `manual_sdr.py`, `make_manual_sdr.py`, `docs/manuel_sdr.*` supprimés, `open_sdr_manual` = `open_manual("sdr-poste")`.
  `sync-v8.yml` supprimé, `kit-sdr.yml` sur `ui-validation`. Les notes « V8 étape N » plus bas restent l'historique du SDR.
  Clément : « bien réexpliquer ce qu'est un tinySA et ce qu'est le SDR, dans le manuel et au survol » : PURE `DEVICE_HELP`
  {tiny, sdr, both} (bulles du bouton de mode, de chaque mode du menu, de la carte ① de l'accueil, du nom du SDR dans le
  Récepteur ; spectre SDR « ce n'est pas le balayage du tinySA »), lexique + « tinySA », « SDR », « Démoduler » ; manuel :
  tableau « tinySA ou SDR : quelle différence ? » dans le chapitre Le matériel, SDR dans « En option ».
  1re CI de la 8.0 sous vrai Windows (12 min) : 5 échecs absents sous Linux. Vrai défaut corrigé : `layout_standard`
  montrait AUSSI les panneaux SDR (dans `self.docks`) -> le Récepteur (553 px mini) agrandissait la fenêtre (1 028 ->
  1 491 px ; sur un écran de 1 024 le spectre était écrasé à 422 px) : les docks `dock_sdr*` ne sont plus montrés par
  la disposition de base (+ `_v8_layout_standard` remet la taille en mode tinySA). Tests rendus robustes aux machines
  lentes : « SDR trouvé » (le faux SDR Python ne tient pas 4,8 MS/s sur la CI), « Revenir » (comparé à `_back`),
  « bilan » (5 premières lignes du journal) ; « tech » et « bilan » disent dans leur message les postes SDR en marche
  et la durée du calcul (5,5 s ici, > 120 s sur la CI Windows : cause pas trouvée).
- **8.0.1 (captures de Clément, écran 1920 × 1040 : « bug d'affichage en passant tinySA ↔ SDR, il faut ré-appuyer sur plein
  écran ; je n'ai plus accès à mes fréquences »)** : reproduit hors écran (`offscreen:configfile=` avec un écran 1920 × 1040) :
  en mode SDR la fenêtre agrandie passait à 2 115 × 1 534 px (Récepteur : 925 × 483 px mini, Journal sorti de son onglet
  au-dessus du Récepteur) -> bords coupés, panneaux superposés, « Mes fréquences » sous l'écran. Corrigé : rangées du
  Récepteur qui se replient (`SdrPanelBase._wrap`, FlowLayout) ; Récepteur dans `SdrScroll` (QScrollArea qui renvoie au
  panneau les attributs inconnus : `.widget().go_btn` etc. marchent toujours ; mini 220 × 140) ; `_sdr_arrange` remet le
  Journal en onglet avec Mes fréquences ; `_fit_screen` (après chaque mode / disposition et au démarrage) recale une
  fenêtre agrandie plus grande que l'écran ; `idle_sdr_view` : SDR pas démarré = axes de la fenêtre qu'il recevra (avant :
  0-1 dBFS et waterfall 0-600 MHz). Mesuré hors écran : 1920 × 1040 dans les 3 modes, mini 914 × 850 (SDR), 1 270 × 850
  (combiné) ; écran trop petit (portable) -> le Récepteur passe en onglet avec Mes fréquences ; `set_level` ne réaffiche plus
  le spectre / waterfall du tinySA en mode SDR. **Pas revu sur le vrai écran de Clément.**
- **8.0.2 (Clément : « un vrai mode double écran ou plus : tinySA complet sur l'un, SDR complet sur l'autre, ou un mix
  qu'on choisit »)** : PURE `SCREEN_PANELS` (panneau, groupe tiny | list | sdr, titre), `SCREEN_PRESETS` (tiny_sdr, sdr_tiny,
  list_out, all_here), `screen_preset`, `screens_norm` (config « screens » {on, plan {panneau: écran | -1}, full, hosts
  {écran: {geo, state}}}), `screens_used`, `screen_rf_mode` (le mode suit les panneaux montrés), `screen_plan_fit` (écran
  débranché -> fenêtre principale). `ScreenWindow` (QMainWindow d'un autre écran : panneaux PRÊTÉS par échange de widget
  comme `PanelWindow` — les objets dock restent dans MainWindow —, `arrange`, `place`, F11, fermer = tout ramener),
  `ScreensDialog` (`self._screens_dlg` : tableau panneau -> écran / caché, préréglages, 👋 `identify_screens`, plein
  écran). MainWindow : `dock_widget(d)` (le VRAI panneau, où qu'il soit : à utiliser au lieu de `d.widget()`),
  `screen_list`, `screens_docks`, `screens_current`, `screens_apply`, `screens_off`, `screens_state`, `screens_restore`
  (`_late_layout`), `open_screens` (menu du mode + 🪟 Fenêtres). Disposition de base, changement de mode, fermeture : tout
  revient. Testé : test_sdr (PURE), gui_reel (2ᵉ écran simulé = même écran 2 fois), script de session avec 2 écrans
  virtuels (`offscreen:configfile=` 2 × 1920 × 1040 : fenêtre sur S2, config relue). **Jamais vu sur un vrai double écran.**
  Aussi en 8.0.2 (Clément : « ajouter rapidement les micros à suivre depuis Mes fréquences à mes micros SDR ») : PURE
  `post_mics_norm` / `post_mics_set`, clé `mics` des postes (`sdr_posts_norm`), `post_watch(watch, scenes, mics)` : micros
  CHOISIS (kHz) s'il y en a, sinon ceux des scènes. MainWindow `watch_selected`, `sdr_follow(ws, on, pid)`,
  `sdr_follow_clear`, `_sdr_follow_menu` (clic droit de Mes fréquences, un sous-menu par SDR s'il y en a plusieurs),
  `sdr_follow_key` (Ctrl+Maj+F sur la liste : ajoute, ou retire si déjà tous suivis). `SdrMicsPanel` : « ＋ Ajouter ma
  sélection », Retirer (Suppr), ↺ Tous, `mode_lbl` ; micros choisis hors fenêtre listés grisés (clic = y aller) ; la
  patrouille « tous » = les suivis. Retirer le dernier = le SDR suit de nouveau tous les micros.
  Et (Clément : « le générateur audio ne fonctionne pas, j'ai qu'un 1 kHz ») : QSoundEffect garde en cache le son d'une
  adresse de fichier -> réécrire le MÊME fichier temporaire rejouait le 1er son ; et `_changed` faisait `play(False)` qui
  décochait ▶ -> plus aucune relance ensuite. `temp_wav_path(kind, old)` = nom neuf à chaque lecture (générateur et
  ⏪ remonter le temps) ; `_changed` -> `play(True)`. gui_reel relit le WAV joué (440 puis 5 000 Hz). **Son toujours
  jamais entendu par Claude.**
- **8.0.3 (Clément : « je peux ouvrir plusieurs fois le logiciel », « le générateur sert à quoi ? je peux l'affecter nulle
  part », « le mode test devrait générer la fréquence monitorée », « les sons d'alarme font chippppp »)** :
  - **Une seule instance** : `single_instance(app)` dans `main()` (pas pour `--relais`) : `QLockFile` instance.lock dans le
    dossier de config (`setStaleLockTime(0)` : verrou d'une appli plantée repris), 2ᵉ copie -> `QLocalSocket` « show » vers
    `_instance_name()` puis sortie (code 0) ; la 1re revient devant (`_instance_wake`). Relances (langue `restart_app`,
    garde `_guard_env`) : `TSM_WAIT_INSTANCE=1` = attend 20 s. `TSM_MULTI=1` = plusieurs copies (dépannage).
    `--hidden-import PySide6.QtNetwork` (workflow, build.bat, `self_test`). Test `tests/test_instance.py` (vrais processus,
    CI Linux). ⚠ Ne pas mettre HOME dans l'environnement d'un sous-processus de test (les paquets « --user » disparaissent).
  - **Démo du tinySA = plan du SDR démo** : `get_cfg` -> `demo_plan = demo_sdr_plan(self.demo_mics())` ; PURE
    `demo_plan_levels(fr, plan, t, rng)` (dBm = `DEMO_DBM` + lvl − 8) dans `ScanWorker._demo_levels` (+ 3 signaux inconnus) :
    tous tes micros émettent (avant : 1 sur 4). Type de signal par micro : `DEMO_SIG_KINDS` (auto, fm, digital,
    intermittent, jam, off), `sdr_cfg["demo_kind"]` {kHz: type} (gardé par `sdr_cfg_extra`), lu par `demo_mics` -> clé
    `kind` de `demo_sdr_plan`.
  - **Générateur affectable** : `AudioPickDialog` (standalone) « Utiliser ce son pour… » : `target` (données TEXTE
    « mic:kHz » / « alarm:alarm2 » / « tx: » — un tuple Python n'est pas retrouvé par `findData`), `sig`, `assign` ->
    `demo_sound` + `demo_kind`, `set_alarm_sound`, ou nouvelle ligne de `SdrTxDialog` ; phrase « À quoi ça sert ? ».
  - **Sons d'alarme** : `ALARM_TONES` plus graves (784 / 988 / 1 175 Hz montants ; 880 -> 698 « ding-dong » ; 784),
    `tone_pcm(..., timbre="chime")` -> `_chime_pcm` (harmoniques, attaque 8 ms, résonne et s'éteint) ; anciens sons =
    `ALARM_TONES_CLASSIC` / `TONE_OK_CLASSIC`, style « classic » (📟 Bips nets) de `SOUND_STYLES`. WAV d'essai envoyés à
    Clément. **Jamais entendus par Claude sur une vraie carte son.**
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
- **Vrais scans envoyés par Clément (7.32, fichiers PAS dans le dépôt, structures recopiées dans `tests/data/*_essai.csv`)** :
  WWB `470.000,-104.531` (LF, sans en-tête) ; TTI `470.0000,-88.0` (CRLF) ; **WSM réel** = métadonnées (`Receiver;…`,
  `Date/Time;…`, `RFUnit;dB`, Owner, ScanCity…, `ScanName`, `ScanPostalCode`), ligne vide, `Frequency Range [kHz];début;
  fin;pas`, `Frequency;RF level (%);RF level`, puis `kHz;;dBµV entier` (colonne % VIDE — l'ancien format nikharju en %
  est toujours lu) ; **Wisycom Manager** = `Freq2D;RFA;RFB;MaxRFA;MaxRFB`, `N;début kHz;fin kHz;-10.00;70.00`, puis
  `MHz(2 déc);4 niveaux dBµV` (on lit le max des 4, dBm = dBµV − 107). Un « WSM » peut aussi être un simple
  `470.2,-105`. `scan_write` : wwb / wsm / wisycom / tti identiques aux originaux (lignes de données identiques pour
  TTI, WWB, WSM) ; `scan_uniform` (grille régulière, max par case) pour WSM (pas entier en kHz) et Wisycom (1/100 MHz).
  **Retour de Clément (04/11/2026) : nos exports WWB et Wisycom s'importent bien dans le logiciel de coord** ; import de nos WSM / TTI
  pas vérifié.
- Les formats « logiciel de coord / WWB / WSM » pour l'**export de listes de fréquences** sont des suppositions génériques :
  demander à Clément un vrai fichier d'import avant de les « corriger ».
  Le site de l'éditeur du logiciel de coord est bloqué par le proxy.
- **Document `.ezrf3` (7.33, 7 vrais fichiers de Clément, PAS dans le dépôt ; essai inventé
  fichiers d'essai `.ezrf3` + collage dans `tests/data/`)** : XML (racine = nom du logiciel + « ds »), éléments À PLAT dans l'ordre
  `GroupeDt` (NbSect, ZoneNo, HorsFonction) / `SectionDt` (NbApp) / `AppareilDt` (AppareilName, AppDescription « #n »,
  NbreFréqDésiré, Tolérance / Tolérance3TX / Tolérance5e / Séparation en kHz, Filtre MHz, Incrément, Départ / Arrêt,
  Eval5eOrdre, FréqImage, AppNbIM) / `FréquenceDt` (Valeur « 558,200 » parfois VIDE = pas encore attribuée,
  Description, Rayé, Libéré) ; `ZonesDt` (NoZone, Title), `InterférencesDt`, `ParamsDt/ZipScanData` (gzip + base64 de
  paires float64 MHz / dBm), `OptionsDt/Eval5eOrdre` (interrupteur général du 5ᵉ ordre), `RésuméDt/NbIM`
  (« Nbre Intermodulation: N »), `InformsDt` (Titre, Date, Version). PURE `parse_ezrf3`, `parse_ezrf_paste` /
  `is_ezrf_paste` (copier-coller du plan : titres empilés après chaque ligne vide, `#n - Appareil`, `nom<TAB>MHz`),
  `ezrf_entries` (scène = groupe du document, préfixé de la zone si plusieurs ; groupe = section), `ezrf_profile_names`,
  `ezrf_dev_key`. `EzrfImportDialog`, `MainWindow.import_ezrf_file` / `open_ezrf` / `apply_ezrf` /
  `_ezrf_profiles` (profils perso créés ou réutilisés, posés sur les groupes), branchés sur `import_watch`,
  `open_import` (collage) et le glisser-déposer.
- **Règles de calcul du logiciel de coord (doc officielle envoyée par Clément, § 2.4, + vérifié sur ses 7 plans)** : Filtre =
  **± la valeur** (« 16 MHz : porteuse à 500 → émetteurs de 484 à 516 »), PAS ± filtre / 2 comme avant 7.33 ;
  tolérance = « au-delà de laquelle les IM sont acceptées » → **limite stricte** (produit pile à 50 kHz = OK ; marge
  1e-6) ; 5ᵉ ordre = case de l'appareil ET option du document ; **chaque zone est calculée à part**. Résultat
  (`pf_check` par zone, réglages par appareil) : Roc d'Azur 0/0, Maalouf 0/0, Isabelle 0/0, PlaneR Samedi 0/0,
  TechFest 6/6, PlaneR complet 104 (logiciel de coord) / 110 (nous, même détail appareil par appareil ; façon de compter
  différente). Image : `FréqImage` lue (profil `img`), calculée par `pf_check` (± 1 × FI, 7.51) et, depuis 7.68, évitée
  par la coordination auto.

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
- Ajouter les vrais formats d'import WWB / WSM / logiciel de coord dès que Clément fournit des exemples.
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
- **V8 étape 6 (fait, avec la 7.68 : « go 1234, important la SDR avec démodulation, écoute ») : écouter de partout** :
  branché sur les prises V7 7.68, sans toucher aux lignes V7 (affectations au niveau du module, juste avant
  `def self_test`) : `MainWindow.FREQ_ACTIONS += [🎧 listen_freq, ⏱ rt_freq]` (clic droit d'une alarme, tuiles du
  mur / mode Show, boutons de la chasse), `MainWindow.web_extra = _v8_web_extra`, `WEB_VIEWS` / `WEB_VIEW_KEYS` +
  « ecoute » (cachée par défaut : `WEB_VIEWS_HIDDEN`), `WEB_EXTRA_JS` (vue `EXT.ecoute`). PURE : `listen_windows`
  (fenêtres du SDR, ≤ 4 canaux), `HopState` (balayage d'écoute : `dwell` s par fenêtre, reste tant que ça parle +
  `hang` 2 s), `HOP_OPEN_DB` (squelch ouvert : « ça parle » = 12 dB au-dessus du canal le plus calme vu ; −50 dBFS fixe
  ne marchait pas : bruit d'un canal SDR au-dessus), `pcm_mono16k`, `PcmRing` (n° de morceaux, 1re demande = ½ s),
  `pcm_packet` (« TSMA » + n° + taux + PCM), `listen_request`. `ListenWorker.tap` (copie du son) ; taille du bloc IQ
  d'après `IQ_BYTES` (RSP1B : 4 octets). `ListenDialog(freqs=)` (fréquence hors liste « 📍 »), `rec_btn` /
  `toggle_rec` (WAV 48 kHz stéréo dans `<journaux>/enregistrements_audio/<date>/`), `pc_mute`, `hop_chk` + `dwell`
  (`_wins`, `_hop_next` relance le worker sur la fenêtre suivante, son et WAV continuent), `_publish` ->
  `owner._v8_listen`. MainWindow : `listen_freq(f, w)`, `rt_freq`, `listen_web_push` (seulement si quelqu'un regarde
  « ecoute »), `web_listen_pcm` / `web_listen_json` (fil du serveur), `web_listen_do` (via `V8Bridge`, signal en file
  d'attente). Page : « 🔊 Activer le son ici » (le navigateur exige un geste), Web Audio planifié, sondage 250 ms ;
  PIN demandé pour ▶ / ■. lang_en_v8 : `WEB` (morceaux de page) fusionné dans `lang_en.WEB` par `_load_lang_en`.
  **Couche appareil** : `SpectrumDevice` (abc : `scan` obligatoire, le reste facultatif ; `family`, `caps`),
  `SpectrumDevice.register(TinySA)`, `SDRSweep(SpectrumDevice)`, `register_spectrum_driver` / `spectrum_driver` /
  `open_spectrum_device` (ScanWorker V8). Testé : test_sdr (PURE), gui_reel (faux hackrf_transfer : hors liste, WAV,
  balayage d'écoute entre 2 fenêtres, téléphone : PIN, son reçu, état, arrêt). **Jamais avec un vrai SDR ni un vrai
  téléphone** (Web Audio sur iPhone / Android à vérifier, retard réel, Wi-Fi).
- **V8 étape 7 (Clément, avant la 7.68 : « check winradio et les fonctionnalités SDR, raccord monitoring + démodulation
  / écoute d'une ou plusieurs fréquences, mettre en place les SDR les plus fréquents, que ça s'adapte au nombre de bits
  et tout » ; il a choisi TOUS les SDR + « surveiller et écouter en même temps »)** :
  - **Fiches** PURE `SDR_MODELS` (clé, genre, nom, plage MHz, bits / ENOB, débits IQ, part utile, entrée max, étages de
    gain (clé, nom, min, max, pas, défaut), `cal` = dBm calibrés, `src`, note) : HackRF One / Pro, RTL-SDR V3 / V4,
    SDRplay RSP1A / 1B / dx / duo, Airspy R2 / Mini / HF+, LimeSDR Mini, Pluto, USRP B200/B210, bladeRF 2.0, WiNRADiO
    G39DDC (G65DDC listé, PAS pris en charge : 0-88 MHz, autre API). Vérifiées le 24/11/2026 sur greatscottgadgets.com,
    airspy.com, rtl-sdr.com, winradio.com ; **SDRplay / Lime / Pluto / USRP / bladeRF = fiches publiques NON relues**
    (site injoignable : `src` « fiche (non relue) »). `SDR_MODEL_DEFAULT`, `sdr_model`, `sdr_models_for`, `sdr_model_of`
    (choix {genre: clé}), `bits_dynamic`, `sdr_floor_dbfs` (échelle des barres de niveau de l'écoute), `sdr_rate`,
    `sdr_span_mhz`, `sdr_in_range`, `sdr_model_text` (fiche lisible), `sdr_cfg_extra` (config : model, models, gains
    {clé: {étage: n}}, offsets {clé: dB}), `sdr_gains_for` (gains -> outils, anciens lna / vga / amp repris).
    MainWindow : `sdr_model_for`, `sdr_gains` (remplace `dict(sdr_cfg)` pour les workers / écoute / temps réel),
    `sdr_offset`. `SdrDialog` réécrite : « Mon SDR », fiche, gains du modèle (créés d'après la fiche), dossier outils /
    DLL, correction de niveau par modèle.
  - **Genres** `SDR_KINDS` + airspy / airspyhf / lime / pluto / uhd / bladerf (clé `soapy` = pilote SoapySDR : rx_power /
    rx_sdr `-d driver=…`, IQ CS16) et winradio (`dll`) ; `SDR_ALIASES` (adresses « airspy », « usrp », « g39ddc:SN »…) ;
    `SDR_DTYPE`, `ci32_le`, `RT_RATES` complétés d'après les fiches. **`Resampler`** (linéaire en flux) au bout de
    `ChannelDemod` : un débit qui ne tombe pas juste (Airspy 10 MS/s, WiNRADiO 250 kS/s…) sort à 48 kHz exacts.
  - **WiNRADiO G39DDC** (doc + `G39DDCAPI.h` officiels : __stdcall, pack(1), `OpenDevice((char*)-1)`, `SetCallbacks`,
    rappels appelés par un fil de la DLL où on ne rappelle PAS la DLL, un récepteur = un seul fil) : ctypes
    `WR_DEVICE_INFO` / `WR_DDC_INFO` / `WR_CALLBACKS` + types de rappel, `WR_SIGS`, `WinradioG39` (ouvre, alimente,
    `set_gains` atténuateur 0/6/12/18 + préampli, `fe_round` au pas du front-end), **`WinradioSweep`** (balayage matériel
    `StartSweeping`, instantanés 16 bits à 100 MS/s copiés par le rappel, FFT + `GetIFSpectrumCompensation` = **dBm
    calibrés** dans le fil du worker, PURE `wr_snapshot_spectrum` (bande utile `FrontEndWindowWidth` autour de
    `CenterFrequency`, RF = front-end + écart, `inverted` en option : sens NON vérifié), `SweepAccum`), **`WinradioIQ`**
    (DDC1 : PURE `wr_pick_ddc` = plus petit type qui couvre la fenêtre, 16 bits de préférence ; front-end + décalage
    DDC1 ; rappel -> file). `find_winradio_dll`, `WINRADIO_DIRS`, `WINRADIO_LIB` (fausse DLL des tests). Son
    démodulateur intégré (2 canaux) et son niveau en dBm ne sont PAS utilisés (on garde notre démodulation : companders,
    stéréo, mêmes réglages pour tous). `WR_DDC1_MODE_WIDEBAND` = 1 supposé (absent de l'en-tête lu).
  - **Source d'IQ commune** `open_iq_source` -> `ProcIQ` (outil) ou `WinradioIQ` ; `.rate` / `.dtype` réels ;
    `ListenWorker` et `RealtimeWorker` passent par elle (débit réel du récepteur, plus de `subprocess` dans ces fils).
  - **Surveiller ET écouter** : `ListenWorker.want_spec` -> signal `spectrum` (F MHz, dBFS, FFT 2048, 2 fois / s) ;
    `ListenDialog._spec` -> `MainWindow.sdr_listen_feed(genre, F, L)` (dBFS + `sdr_offset`, dBm pour WiNRADiO) dans
    `latest[SDR_LISTEN_ID]` = −40 -> `update_watch_levels` surveille les fréquences de la fenêtre écoutée ; SEULEMENT si
    aucun autre appareil ne balaye (un tinySA garde la surveillance de tout : pas de mélange dBFS / dBm) ; `mon_lbl` le
    dit ; `sdr_listen_clear` à l'arrêt. Le temps réel ⏱ fait pareil (`RealtimeDialog._frame`, direct seulement).
    `ListenDialog` : plage du modèle vérifiée, barres de niveau d'après les bits, `span` (WiNRADiO : DDC le plus petit).
  - Tests : `tests/fake_winradio.py` (fausse G39DDCAPI : mêmes fonctions / structures, rappels depuis un fil,
    instantanés et IQ avec porteuses) ; test_sdr (fiches, gains, config, adresses, commandes Soapy, ci32, `wr_pick_ddc`,
    `wr_snapshot_spectrum`, `Resampler`) ; test_sdr_qt (vrai ScanWorker + ListenWorker sur la fausse DLL : porteuse à
    473 MHz, son à 1 kHz, spectre envoyé, récepteur refermé) ; gui_reel (fiche, gains par modèle, surveillance pendant
    l'écoute avec / sans tinySA). **Jamais avec un vrai WiNRADiO, SDRplay, Airspy, Lime, Pluto, USRP ni bladeRF.**
- **V8 étape 8 (Clément : « go 1/2/3/4/5 » sur ce que le SDR permet en plus)** — seuils = choix de Claude, testés sur des
  signaux SYNTHÉTIQUES seulement :
  1. **Type de signal** PURE `SIG_TYPES`, `classify_signal(F, L, f0, pilot, span)` (largeur à −20 dB du pic, platitude du
     haut, pilote 19 kHz -> fm_st ; tnt ≥ 4,5 MHz plat / wide / num 120 kHz – 1 MHz plat / fm_ana ≥ 50 kHz / nfm / cw ≤
     4,5 cases) ; colonne « Type » du journal du temps réel, colonne « Type · santé du micro » de l'écoute (`_types` via
     `_spec`), `ana_lbl` du temps réel (signal écouté ou `_ana_f`), FREQ_ACTIONS « 🔎 C'est quoi ce signal ? (SDR) » ->
     `MainWindow.analyze_freq` (temps réel centré + lancé).
  2. **Santé d'un micro FM** : `ChannelDemod._watch_health` (toutes les 0,5 s : déviation crête = 99,5ᵉ centile, dérive
     = écart moyen, en kHz -> `self.health`), 4ᵉ élément des `levels` de ListenWorker ; PURE `mic_health(dev, nominal du
     préréglage, dérive, pilote, audio)` -> (texte, ton : trop chaud > 1,25 × nominale, dérive > 5 / 15 kHz). Test :
     faux micro ±30 kHz mesuré 22-40.
  3. **Signaux brefs -> alarme** : `RealtimeDialog.burst_chk` (coché) -> `MainWindow.sdr_burst_conflict(genre, w, ev)` sur
     une « doit rester libre » : alarme kind CONFLIT de clé **(« BREF », kHz)** (pas effacée par `update_watch_levels`,
     qui n'efface que (« CONFLIT », kHz) ; pas par le tick non plus tant que la fréquence existe), journal, son, fin
     automatique après 60 s (QTimer).
  4. **Enregistrement sur alarme** : PURE `PreRing` (10 s de son), `alarms_in_window(alarmes, lo, hi, vues)` ;
     `ListenDialog.auto_chk` (coché) : `_alarm_check` toutes les 0,5 s -> WAV `alarme_HHMMSS_<MHz>.wav` = 10 s d'avant +
     10 s d'après (`_auto`, `_auto_end`, journal « ENREGISTRÉ (alarme) ») ; seules les alarmes NOUVELLES depuis ▶ ;
     `RealtimeDialog.autorec_chk` (décoché : gros fichiers) -> 15 s d'IQ SigMF.
  5. **Mesures** PURE `obw_khz` (99 % de la puissance au-dessus du bruit), `signal_report` (type · largeur occupée · dB
     au-dessus du bruit · ✔ tient / ⚠ déborde d'un canal de `CHANNEL_KHZ` 200 kHz pour les FM / porteuses).
- **V8 étape 9 (Clément : « Go ça part là dessus en V8 », tableau de 20 idées ; lot A)** : 📡 **moniteur multicanal**
  (☰ Plus › 📡 SDR, `open_multimon`, `self._multimon`) : `MultiMonitorWorker` (UNE fenêtre IQ, FFT 4096 par bloc de
  50 ms -> niveau / bruit / écart / voisins / largeur de TOUS les canaux ; « récepteurs virtuels » = `ChannelDemod`
  complet pour `plan_vrx` (celui écouté, alarmes, prio critique, puis rotation toutes les 5 s, `VRX_MAX` 8) ; signaux
  stats / spec / perf ; `t0` posé aux 1res données) ; `MultiMonitorDialog` (colonnes Nom, MHz, RF, Son, Santé, Largeur,
  Voisins, Diagnostic ; `_plan` = la plus grande grappe de la liste dans la fenêtre ; waterfall ± 150 kHz et historique
  du micro choisi). PURE `AudioMeter` (RMS / crête / saturation / silence / coupures), `adjacent_db`, `rf_audio_diag`
  (rf_low, rf_drops, mute, cuts, hot, drift, adj), `plan_vrx`, `MicHistory` (+ `drift_stats`), `perf_view`. Seuils
  `AUDIO_*`, `ADJ_WARN_DB` = choix de Claude. Testé : faux SDR (2 micros FM), gui_reel.
- **V8 étape 10 (lot B : incidents)** : PURE `IQ_RING_S` 20 s / `IQ_RING_BUDGET` 256 Mo (`iq_ring_seconds`), `AnomalyTracker`
  (par micro, 2 mesures / s : drop = RF 15 dB sous sa médiane 30 s s'il y avait une porteuse, sortie = retour à
  ± 7,5 dB du niveau d'avant (`ref`) ; flaps = 3 drops / 10 min ; noise = bruit 8 dB au-dessus de sa médiane 5 min ;
  adj = marge voisin < `ADJ_WARN_DB` ; appear = signal sur une « doit rester libre » (keep_on=False) ; diag = diagnostic
  rouge ; une fois par `INC_COOLDOWN_S` 60 s et par type), `ANOM_LABELS`, `anomaly_text`, `unknown_bursts`,
  `incident_slug`, `incident_prune`, `_svg_series`, `incident_report_html`. Worker : tampon `PreRing` de l'IQ brut,
  `inc_req` (file) -> IQ d'avant + `INC_POST_S` 10 s d'après -> `_inc_write` (fil Python : iq.sigmf-data / meta avec
  annotation) -> signal `incident` ; une demande pendant un enregistrement = MÊME dossier (`merged`, `iq["same"]`) ;
  `BurstDetector` (médiane + 15 dB) -> `bursts` (inconnus seulement). Dialogue : onglets « Micro choisi » /
  « Chronologie » (`chron`, `chron_tbl`, 500 lignes), `inc_chk` « 📦 Dossier d'incident automatique » (coché ; un toutes
  les `INC_GAP_S` 2 min, manuel compris), `iq_chk`, « 📦 Noter un incident » (`manual_incident`), « ▶ Rejouer » / double-clic
  (`open_incident` : rapport.html dans le navigateur + `RealtimeDialog.open_file(iq)`), `_inc_done` -> mesures.json +
  rapport.html, `_prune` (`INC_MAX_MB` 2 Go). Dossiers : `<journaux>/incidents/<date>/incident_HHMMSS_<nom>/`. Journal
  « INCIDENT SDR ». ☰ Plus › 📡 SDR › « 📦 Rejouer un incident SDR… » (`open_incidents`). Testé : faux SDR (le faux
  va moins vite que le vrai temps : 6 s d'IQ pour 10 s), gui_reel ; **jamais avec un vrai SDR / de vrais micros**
  (seuils à régler sur le terrain, place disque d'un vrai HackRF à 9,6 Mo/s non vécue).
- **V8 étape 11 (lot C)** :
  - **Répétition / spectacle** : PURE `SDR_MODES`, `RehearsalProfile` (learn(ligne) ; `summary` : snr p10 / médiane,
    bruit, rf, son p50 / p95 ; ≥ `REH_MIN_N` 60 mesures), `rehearsal_norm`, `rehearsal_check` (reh_rf ≥ 10 dB sous le
    p10, reh_noise + 6 dB, reh_audio + 6 dB au-dessus du p95). Moniteur : `mode_combo`, « 💾 Garder la répétition »
    (`save_rehearsal` -> `sdr_cfg["rehearsal"]`, relu par `sdr_cfg_extra`), en spectacle les écarts passent dans le
    diagnostic et l'`AnomalyTracker` (événement « diag » avec la phrase).
  - **Comparaison des récepteurs** : PURE `compare_receivers(a, b)` (paires à ± 1,5 s, décalage médian, écart-type,
    corrélation, décrochages vus par un seul), `compare_text` ; l'historique du moniteur note `tsa` (niveau tinySA si
    un tinySA balaye : `MainWindow.tsa_live`) et `rx` (récepteur Shure de la fréquence) -> lignes sous le micro choisi.
  - **Télémétrie Shure (14 / 15)** : PURE `SHURE_PORT` 2202, `shure_split`, `shure_parse`, `shure_apply` (CHAN_NAME,
    FREQUENCY kHz × 1000, RX_RF_LVL − 128 dBm, AUDIO_LVL − 50 dBFS, RF_ANTENNA, TX_BATT_BARS (255 = inconnu), TX_TYPE,
    SAMPLE … ALL <AX|XB|XX> rf … audio), `shure_init` (GET 0 ALL + METER_RATE 1 s), `DiversityAB`, `shure_addrs`.
    `ShureClient` (fil Python, reconnexion 5 s, muet 15 s = coupé), `ReceiversDialog` (📶, ☰ Plus › 📡 SDR),
    `MainWindow.receivers_start` (`sdr_cfg["shure"]`), `receivers`, `receiver_for(f)`, `watch_near`. **Protocole écrit
    DE MÉMOIRE d'après la doc publique Shure, jamais essayé sur un vrai ULX-D / QLX-D / AD** (format SAMPLE surtout :
    demander à Clément une capture `telnet <ip> 2202` au 1er essai). Testé avec un faux récepteur TCP (test_sdr_qt,
    gui_reel).
  - **Chasse / carte de chaleur avec le SDR (13)** : `sdr_listen_feed` nourrit aussi `HuntDialog.feed` (sans tinySA qui
    balaye) -> les points de la carte prennent le niveau du SDR (en dBFS + correction du modèle).
  - **Kit SDR** : `sdr_kit_dirs` (kit-sdr à côté de l'exe, ou Documents/TinySA Monitor/kit-sdr), `find_sdr_tool` y
    cherche `bin/` et pose `SOAPY_SDR_ROOT` ; `SDR_KIT_HINT` en tête de « Comment l'installer ? » (sauf WiNRADiO) ;
    `kit-sdr/LISEZMOI.txt` ; workflow **`.github/workflows/kit-sdr.yml`** (fichier propre à la V8 ; push sur v8-sdr qui
    touche kit-sdr/ ou le workflow, ou à la main) : télécharge l'installateur PothosSDR (URL **supposée**
    downloads.myriadrf.org …2021.07.25-vc16-x64.exe, 2e essai 2021.01.28), l'extrait au 7-Zip, garde bin (outils + dll)
    + lib/SoapySDR + licences, publie `kit-sdr-windows.zip` dans une pré-release À PART « kit-sdr » (test-v8-sdr est
    refaite à chaque compilation). **Jamais lancé au moment de l'écrire** (le réseau de la session ne voit ni GitHub
    des autres projets ni myriadrf) : lire ses annotations au 1er passage. SDRplay (API) et WiNRADiO (logiciel) ne
    peuvent pas être dans le kit ; le pilote USB (Zadig) reste à installer.
- **V8 étape 12 (Clément : « tout mettre en place, fiabiliser, hyper user friendly, pas usine à gaz », après une revue
  « 4 fondations + feuille de route 9-20 »)** :
  - **Son enregistré / vie privée** : PURE `PRIVACY_DEFAULT` (alarm_audio False, keep_days 7, ack False), `KEEP_DAYS`,
    `PRIVACY_TEXT`, `privacy_norm`, `keep_text`, `retention_pick` ; `sdr_cfg["privacy"]` (via `sdr_cfg_extra` si présent).
    `MainWindow.privacy()`, `privacy_ok(parent)` (QMessageBox.question la 1re fois -> `ack`), `sdr_retention()` (efface
    enregistrements_audio / enregistrements_iq / incidents plus vieux que keep_days, dossiers vides), `sdr_timer()`
    (1 h, appelé par open_listen / open_multimon). Écoute : `auto_chk` DÉCOCHÉ sauf accord + choix retenu,
    `_auto_toggled`, `rec_badge` (`_badge` : rouge = enregistre, orange = armé), `toggle_rec` demande l'accord. Moniteur :
    IQ des incidents = accord aussi. Réglages SDR : « Enregistrements gardés » (`keep_combo`) + « Pourquoi ? ».
  - **Horloge commune** : PURE `AcqClock` (heure de CAPTURE = ancre aux 1res données + échantillons / débit ; `lag` =
    retard réel ; recalage au-delà de 2 s compté `resyncs`) ; lignes du moniteur `t` = heure de capture, `MicHistory`
    datée avec, comparaison tinySA à l'heure de SON balayage (`MultiMonitorDialog._tsa_level` via `latest_t`, séries
    `self.ext` {clé: {tsa, rx}}), récepteur Shure à l'heure de réception.
  - **Capacité** : PURE `VRX_BUDGET` 0,6, `vrx_auto(charge FFT, coût d'un récepteur)` (mesurés dans le worker :
    `b_fft`, `b_vrx`, `n_vb`), `vrx_spin` 0 = « Auto » (défaut), `capacity_view` -> `cap_lbl` (dans la fenêtre / démodulées
    en continu / à tour de rôle / HORS fenêtre / ⚠ critiques sans récepteur, noté au journal toutes les 5 min) ; `_plan`
    utilise `sdr_span_mhz` (largeur UTILE du modèle) au lieu de 0,8 × débit.
  - **Santé du système** : PURE `count_overruns` (lignes d'erreur de l'outil), `resource_view`, `reconnect_delay` (3 /
    10 / 30 s) ; perf du worker complète (lag, resyncs, overruns, queue, ring_mb / ring_s, crit, vrx_want) ; onglet
    **Système** (`sys_tbl`, `_sys` : tailles des dossiers relues toutes les 30 s, disque libre) ; incident sans IQ si
    le disque a moins de max(2 Go, 3 × la taille) ; **reconnexion automatique** (`_want`, `_fails`, `disc`, `_retry`,
    journal « APPAREIL PERDU »).
  - **Fiche commune** : PURE `device_caps(kind, model)` / `caps_text` (tinySA : balaye ; SDR : balaye + IQ + largeur
    utile + bits) ; résumé des Réglages SDR « balaye, écoute et démodule ».
  - **Compléments** : 9. `RealtimeDialog.show_incident(doc, t0)` (encadré `inc_box` : chronologie du micro surlignée
    au fil de la lecture, `_inc_sync`, double-clic = `_inc_goto` 2 s avant) appelé par `open_incident` ; 10.
    `compare_receivers` + `std_a` / `std_b` (stabilité) ; 11. `expected_obw_khz(mode)` (Carson), `WIDE_RATIO` 1,3,
    événement « wide » (3 mesures de suite) et diag « wide » ; 12. `ADJ_RISE_DB` 10, `adj_lvl` dans les lignes,
    événement « adj_rise » ; 14. `shure_apply` lit les clés ALARM / WARN / FAULT / ERROR / RF_INT_DET (levées / retombées),
    `receiver_alerts` (pile ≤ 1 barre, alertes, antenne morte, ≥ 3 pertes de diversité) -> colonne « Alertes » (rouge,
    journal « RÉCEPTEUR » une fois) et diag du micro ; 15. `DiversityAB.losses` (épisodes sans antenne), `dead()` (< 5 %
    sur 300 mesures) ; 16. critiques sans récepteur (capacité) ; 17. `AudioMeter` : `afloor` (10ᵉ centile du son sur
    10 s, RF bonne) -> « souffle » > `AUDIO_NOISY_DB` −45, `chops` (passages son <-> rien en 10 s) -> « son haché » ≥
    `AUDIO_CHOPS` 8 ; 18. `incident_duration` (retour à ± 7,5 dB du niveau d'avant), `_svg_spectrum`, rapport : durée,
    capture du spectre (`incs[...]["spec"]` = dernier `_lastFL`), **waterfall.png** du micro ; 20. **phases** : PURE
    `PHASES`, `phases_norm` (l'ancienne `rehearsal` devient « Répétition »), `phases_table` ; `sdr_cfg["phases"]` ;
    `phase_combo` (modifiable) à côté du mode (« 🎭 Apprendre la phase » / « 🎤 Comparer à la phase »), onglet
    **Phases** (`ph_tbl`, `_fill_phases`). 13. carte : rien de neuf en plus de la chasse nourrie par le SDR (étape 11).
  - Seuils (souffle −45 dBFS, haché 8, largeur × 1,3, voisin + 10 dB, budget 0,6) = **choix de Claude, testés sur des
    signaux synthétiques seulement**. Rien de l'étape 12 n'a tourné avec un vrai SDR / récepteur / micro.
- **V8 étape 13 (Clément : « que Shure ? Sennheiser, Wisycom et les plus grosses marques »)** : PURE `RX_BRANDS` (shure
  TCP 2202 ; g4 = Sennheiser evolution G3 / G4 / 2000, UDP 53212, texte « Push 60 100 3 » puis « RF1 / RF2 / AF / Bat /
  Frequency / Name / Msg » ; ssc = Sennheiser Sound Control, UDP 45, JSON : EW-DX, Digital 6000, SpeechLine ; wisycom /
  other = AUCUN protocole public -> rien envoyé, explication `why`), `RX_ALIASES`, `receiver_addrs` (« g4:ip », « ssc:ip »,
  sans préfixe = Shure ; config toujours sous la clé `shure`), `receiver_addrs_text`, `g4_init` / `g4_apply` (RF en %,
  antenne = la plus forte des deux), `ssc_init` (requêtes de mémoire) / `ssc_flatten` / `ssc_apply` (chemins rx<n>/…,
  mates/tx<n>/battery/gauge), `json_dumps_compact` (pas de json dans la section PURE). `ReceiverClient(hôte, port,
  marque)` (TCP ou UDP, `_got`), `ShureClient` = sous-classe. `ReceiversDialog` : Marque + Adresse + « ＋ Ajouter », liste
  « Mes récepteurs » + Retirer (Suppr), `why` pour Wisycom / autres. Colonne RF en dBm ou % (`rf_unit`). **Protocoles
  Sennheiser écrits de mémoire, jamais essayés sur un vrai récepteur** (testés sur faux récepteurs UDP) : au 1er essai,
  demander à Clément une capture (Wireshark) si rien ne s'affiche. Wisycom : demander une capture Wisycom Manager ↔ MRK.
- **V8 étape 14 (2ᵉ audit externe de la V8 : « fiabilité avant tout », Clément : « Goo 1/2/3/4/5/6/7/8 »)** :
  1. **Jamais une valeur ancienne présentée comme actuelle** : PURE `FRESH_S` 2,5 s, `FROZEN_S` 8 s, `RX_STALE_S` 10 s,
     `freshness`, `age_text`. Moniteur : `_freshen` (toutes les 0,5 s via `_feed`, et à l'arrêt) grise les lignes et
     écrit « ⏸ mesure ancienne (il y a N s) » ; au-delà de FROZEN_S (2 × avant la 1re mesure), chien de garde :
     `MultiMonitorWorker.force_close` (ferme la source = tue l'outil, `frozen` -> raison « flux figé ») puis reconnexion
     automatique. Récepteurs : `st["t"]` par canal (`_got`), `age` / `live` dans `receivers()`, ligne grisée « ⏸ hôte ·
     il y a … » + bulle, `receiver_for(..., live_only=True)` (diagnostic et comparaison ignorent l'ancien).
  2. **Couverture par micro** : PURE `COVERAGE` (full, turn, degr, stale, out, stop, wait), `coverage_state`,
     `coverage_text` ; colonne « Suivi » (`C_COV` = 1, `C_DIAG` = 8) ; les fréquences de la plage du SDR hors fenêtre
     sont listées en bas (`out_ws`, « ○ PAS surveillé (hors fenêtre) ») ; `_perf_tone` -> « dégradée ».
  3. **Écriture sûre** : `write_atomic` (.part + fsync + os.replace) pour mesures.json / rapport.html / .sigmf-meta ;
     IQ des incidents en « .sigmf-data.part » renommé, le .meta en DERNIER ; `RealtimeDialog.open_file` refuse un
     « .part » seul (« enregistrement interrompu ») et un IQ < 0,05 s.
  4. **« 🔌 Tester mon SDR »** (Réglages SDR, `run_probe` via `run_heavy`) : PURE `SDR_PROBE` (hackrf_info, rtl_test -t,
     SoapySDRUtil --find[=driver=sdrplay]), `probe_seen`, `probe_rate`, `probe_report` ; `sdr_probe(kind, model, gains,
     dir, iq_tool, secs)` (outil, détection, IQ 2 s, débit ≥ 90 %) ; tests : `SDR_PROBE_RUNNER` (fausse détection).
  5. **Consentement précis** : `PRIVACY_TEXT` réécrit (mémoire / disque / déclencheurs / où / contenu / durée ; l'appli
     n'efface que SES fichiers, pas les copies).
  6. **Avalanche** : PURE `CHRON_GROUP_S` 600, `chron_group` ; `_chron_add(..., kind)` regroupe « ×N » (heure « de → à »),
     journal seulement la 1re fois.
  7. **Processus** : `SDR_PROCS` / `sdr_proc_track` (les deux Popen des outils SDR) / `sdr_kill_all` (atexit) ;
     `MainWindow.closeEvent` enveloppé (`_v8_close_event` : après la fermeture V7 acceptée, stop des fenêtres SDR et
     des récepteurs, puis outils tués).
  8. **Tests de résistance** `tests/test_sdr_stress.py` (vrai `MultiMonitorWorker`, `FakeSrc` : figé, mort, trou de 3 s,
     rafale de 5 incidents, disque plein, coupure pendant l'écriture, endurance 25 s à 12 micros, outils tués) ; PAS
     dans la CI (le workflow est commun à la V7) : à lancer à la main. Testé : tout ça + gui_reel (Suivi, ancien grisé,
     test du SDR, IQ coupé, récepteur muet). **Toujours rien sur du vrai matériel.**
- **V8 étape 15 (audit « comme un nouveau projet » fait par Claude, Clément : « go »)** : 1. incident = morceaux du
  tampon PRIS (`list(ring.q)`, plus de `dump()`), écrits un par un, mémoire rendue (avant : ~500-650 Mo de pic avec un
  HackRF) ; 2. Temps réel : « Enregistrer l'IQ » et « Sur alarme : enregistrer l'IQ 15 s » demandent l'accord vie privée ;
  3. `sdr_probe` : chien de garde `threading.Timer(secs + 6, src.close)` (outil figé) ; 4. phases : `activated` +
  `lineEdit().editingFinished`, `_phase_name` (taper un nom n'efface plus l'apprentissage) ; 5. `_late_layout`
  enveloppé (`_v8_late_layout`) -> `sdr_timer()` dès le démarrage ; petits : `capacity_view(..., planned=True)` avant ▶,
  `vrx_spin` connecté une fois, `stop(keep_paused=True)` pendant la reconnexion (le balayage SDR ne reprend pas 3 s).
  Tests : test_sdr_stress (morceaux, test figé), test_sdr.
- **V8 étape 16 (Clément : « le SDR doit être au cœur du projet, pas une fonction », « des fenêtres de base que
  l'utilisateur bouge et modifie à sa sauce, comme la base du soft », « mode Tiny, SDR ou combiné », « lié au profil
  utilisateur »)** : PURE `RF_MODES` (tiny, sdr, both), `SDR_LAYOUTS` (listen, watch, analyze, dual), `SDR_STEPS_KHZ`,
  `SDR_NFFT`, `STATION_DEFAULT` / `station_norm` (sdr_cfg « station » : a, b, b_on, step, vol, sq, split, nfft, maxhold),
  `rf_mode_norm` (sdr_cfg « rf_mode »), `sdr_level` (niveaux de l'appli : ultra = Simple, simple = Plus, expert = Expert),
  `s_meter` (S9 = −93 dBm), `vfo_inside`, `vfo_center` (A au quart de la fenêtre, pas sur le continu). Moteur :
  `RealtimeWorker.listen_b` / `split` / squelch `sq` / niveaux `lv_a` `lv_b` dans les trames. `SdrEngine` (`self.sdr_eng`,
  un seul flux partagé : start / stop / set_a / set_b / set_opts, recentrage auto quand A sort de la fenêtre, son, WAV /
  IQ avec accord, `sdr_listen_feed`), panneaux `SdrReceiverPanel` / `SdrSpectrumPanel` (bandes A / B glissables, micros en
  repères, clic = A, clic droit = B) / `SdrWaterfallPanel` / `SdrMicsPanel` (base `SdrPanelBase`, `apply_level`).
  Docks `SDR_DOCKS` (dock_sdr_rx / _spec / _wf / _mics) créés en enveloppant `_build_docks` (AVANT restoreState : la
  disposition enregistrée les replace), ajoutés à `self.docks`, 🪟 Fenêtres, `panel_docks` (vraies fenêtres / double
  écran). `layout_standard` enveloppé (range les panneaux SDR puis dispose le mode), `set_level` enveloppé (niveau des
  panneaux), `_sdr_arrange(mode, layout)` (removeDockWidget puis replacement : en combiné, spectre SDR dans sa colonne à
  droite du tinySA ; set_level réappliqué), `set_rf_mode`, `rf_mode_tiny/sdr/both`, bouton `mode_btn` (QToolButton dans
  `cmd_bar` avant ☰ Plus, `_build_mode_menu` : modes + pré-affichages + « ↺ Disposition de base ») posé par `mode_setup`
  (dans `_v8_late_layout`, relance le SDR si l'appli rouvre en mode SDR). Profil utilisateur : `USER_KEYS` + « sdr_view »,
  `user_doc` / `user_apply` enveloppés (mode + poste) ; disposition déjà dans « docks » ; `user_profile_load` enveloppé
  (`_sdr_reload`, SDR relancé ou arrêté). Testé : gui_reel (modes, recentrage, B, niveaux, pré-affichages, combiné côte
  à côte, panneau détaché retenu, profil), gui_en ; **jamais avec un vrai SDR ni sur un vrai 2ᵉ écran**.
- **V8 étape 16 bis / ter (Clément montre WiNRADiO G33WSM, un analyseur SDR moderne et SDR# ; « montre-moi l'affichage
  avant » ; « l'écoute avec compandeurs », « le vu-mètre on comprend pas les valeurs »)** : PURE `freq_digits` (texte
  « 598.300 000 » + valeur d'un cran par chiffre), `sdr_zones` (canaux TNT marqués tv à la main ou dans le plan ->
  zones « TNT n — à éviter »), `spectrum_status` (RBW = 1,73 × débit / FFT, Blackman), `next_mic`, `LEVEL_WORDS` /
  `level_words` (très faible < −95, faible < −80, bon < −55, fort < −30, trop fort ; choix de Claude). Widgets
  `FreqDisplay` (molette sur un chiffre, ←/→ ↑/↓, double-clic = saisir ; signal changed(MHz)) et `SMeterGauge` (arc du
  haut, échelle −120 → −20 dBm, zones rouge / orange / vert / rouge, « −62 dBm · bon », crête ; `format()`). Récepteur :
  ▶ / ■, 🔇, volume, A en grand + vu-mètre ; ligne « 🎧 Écoute » (préréglage d'appareil + compander) à TOUS les niveaux ;
  Plus : mode, désaccentuation, pas, squelch, B (petit vu-mètre ; en Simple, B coupé), zoom du canal (IF) et spectre
  du son (AF, `SdrEngine.af`) ; Expert : FFT, ⚙, charge. Spectre : micros étiquetés (nom + MHz, couleur d'état, 3
  hauteurs), zones TNT, A / B légendés, Micro préc. / suiv., zoom ＋ − ⤢, pics gardés, barre d'état + curseur (Expert).
  Taille du panneau Récepteur recalée sur son contenu à chaque changement de niveau.
- **V8 étape 17 (Clément : « plusieurs tinySA sur les scènes ET un ou plusieurs SDR qui monitorent, à placer sur la carte
  comme les tiny »)** : PURE `SDR_POSTS_MAX` 4, `sdr_posts_norm` (sdr_cfg « posts » [{id, name, model, serial, scenes}],
  le poste 1 toujours là), `post_watch`, `sdr_post_clash` (même genre et n° de série vide / égal). `SdrEngine(owner, pid)`
  : `post()`, `name()`, `ws()` (micros de SES scènes), `bid()` (bande de mesures : SDR_LISTEN_ID pour le 1, −100 − id
  sinon ; `sdr_listen_feed(..., bid)` / `sdr_listen_clear(bid)`), modèle et n° de série du poste (`RealtimeWorker(serial=)`),
  réglages « station » (poste 1) / « stations »[id] ; refus si un autre poste en marche est sur le même SDR. MainWindow :
  `sdr_engs`, `post_docks`, `_make_post`, `_post_title` (« 📡 <nom> · Spectre »), `_sdr_posts_sync` (création / renommage /
  retrait, appelé par `_apply_config` enveloppé, donc AVANT restoreState au démarrage), `_post_show` (onglets à côté du
  poste 1), `all_sdr_docks`. `SdrPostsDialog` (📡 Mes SDR : nom, modèle, n° de série, scènes à cocher, ▶ / ■, carte),
  `open_sdr_posts` (menu du mode, sous-menu SDR). Carte : tuiles « sdr:<id> » (`MapScene` enveloppé : keys_all, label,
  refresh, update_links + `_v8_sdr_links`, node_dropped = SDR posé sur une scène -> il la surveille, node_open -> ses
  panneaux, scene_state : une scène surveillée par un SDR en marche n'est pas « Arrêtée »). Limites : les mesures de
  tous les postes sont réunies (pire cas) dans la surveillance, pas encore « vu par SDR 2 » dans les alarmes ; testé
  avec 2 faux SDR (n° de série S1 / S2), **jamais avec plusieurs vrais SDR** (USB, charge du PC).
- **V8 étape 18 (Clément : « double-clic sur mes fréquences = le SDR se cale dessus », « des fréquences hyper importantes au
  pavé numérique qui basculent l'écoute, la fréquence et le SDR », « le mode écoute fait gros vide en Simple »)** : PURE
  `FAV_KEYS` 9, `favs_norm`, `fav_assign` (sdr_cfg « favs » {touche: kHz}). `MainWindow._engine_for(w)` (SDR rattaché à
  la scène du micro et qui couvre sa fréquence, sinon le 1er), `sdr_tune_mic(w, slot)` (passe en mode SDR si besoin,
  A (ou B) sur le micro, recentrage, démarrage, panneau Récepteur devant), `sdr_fav(k)`, `sdr_set_fav(k, w)`,
  `_v8_watch_dbl` (double-clic Nom / MHz de « Mes fréquences » en mode SDR / combiné ; en mode tinySA rien ne change)
  branché dans `mode_setup`, `fav_keys` = QShortcut Keypad+1…9 (ApplicationShortcut ; un champ de saisie garde ses
  chiffres). Récepteur : barre ⭐ 1…9 (clic = écouter, clic droit = y mettre le micro écouté / vider, bouton allumé =
  écouté) ; zoom du canal + spectre du son visibles aussi en Simple. Mes micros (SDR) : clic droit = menu (A, B, touche
  du pavé). Testé : gui_reel (double-clic, touche 3 du pavé avec QTest), script ; **pas sur un vrai clavier Windows**.
- **V8 étape 19 (Clément : « en favori, si ça vient d'un plan Workbench / .ezrf3… ça met le compandeur automatiquement ?
  modifiable ; et au pavé num ça change le compandeur aussi »)** : PURE `DEMOD_DIGITAL`, `DEMOD_RULES` (motifs ->
  préréglage : numériques ULX-D / AD / QLX-D / SLX-D / EW-D(X) / 6000 / Spectera d'abord, puis ears, Sennheiser 3000-5000,
  evolution, Shure UR / ULX / SLX / BLX, Wisycom, Lectrosonics, talkies, guide), `demod_guess(*textes)` (sans accents, en
  minuscules). `MainWindow.mic_demod(w)` -> (clé, « manual » | « auto ») : `w["demod"]` choisi à la main, sinon deviné de
  `rx_of(w)` + noms des profils (micro et groupe) + groupe + nom + scène ; `mic_demod_set` (rien si = deviné).
  `_collect_config` / `_apply_config` ENVELOPPÉS pour garder `demod` dans « watch » (liste, shows, annuler) sans toucher
  la ligne V7 de la liste blanche. Moteur : `SdrEngine.mic_at(f)`, `set_demod_key`, `set_a` applique le réglage du micro
  sur lequel A tombe (double-clic, pavé, clic spectre / micro, micro suivant…), message 📵 pour un numérique.
  Récepteur : `dem_lbl` « auto (d'après le micro) » / « ✋ choisi pour ce micro », `_dp_changed` retient le choix,
  `refresh` aligne la liste sur le moteur (`_sync`). Règles = choix de Claude d'après les gammes connues, **pas
  vérifiées sur les vrais plans de Clément** (un nom de groupe inattendu -> pas deviné, réglage précédent gardé).
- **V8 étape 20 (Clément : « 1234 !! » sur 4 idées pour surveiller avec le SDR)** — dans le poste SDR (`SdrEngine`, panneau
  Récepteur), pas dans les anciennes fenêtres (qui avaient déjà l'enregistrement sur alarme, le pilote, la classification) :
  PURE `SDR_AUTO_DEFAULT` / `sdr_auto_norm` (sdr_cfg « auto » : tune, rec, dwell, src, pilot_alarm ; dans `sdr_cfg_extra`),
  `PATROL_DWELLS`, `PATROL_SRCS`, `patrol_items` (favoris dans l'ordre des touches, sinon tous ; éteints / en pause sautés),
  `patrol_next`, `alarm_pick` (nouvelle par n° d'alarme, la plus grave), `ALARM_TUNE_KINDS`, `ALARM_USER_HOLD_S` 30 (fréquence
  choisie à la main il y a moins de 30 s : pas de calage, `_user_t`), reste 20 s sur une alarme (`_al_until`), `sdr_carrier`
  (porteuse jugée sur le spectre du SDR : pic ± 50 kHz ≥ médiane + 12 dB), `ALARM_REC_PRE_S` 10 /
  `_POST_S` 20, `ALARM_TUNE_COOLDOWN_S` 60, `pilot_learn` (même pilote ± `PILOT_TOL_HZ` 300 pendant `PILOT_LEARN_S` 3 s),
  `pilot_verdict` (same / other / missing après `PILOT_MISS_S` 5 s / wait / seen / none / off), `what_is` (± 0,5 MHz puis
  ± 5 MHz si large), `what_is_text`. Moteur : `tick` 0,5 s -> `_patrol_tick` (`_tune` = calage par l'appli ; tout autre
  `set_a` = « tu as pris la main » -> patrouille arrêtée), `_alarm_watch` (alarme d'un micro dont `_engine_for` est ce
  poste -> `_back` puis calage, `_arec_start` WAV `alarme_HHMMSS_<MHz>.wav` avec 10 s d'avant seulement si A y était déjà
  (`pre` vidé à chaque changement de fréquence), `_alarm_what` 1,5 s après : « SDR : … » dans `info` de l'alarme + journal
  « SDR SUR ALARME » ; la patrouille reprend après 20 s), `go_back` / `back_text`, `_watch_a` (pilote du FM démodulé de A,
  19 kHz stéréo ignoré ; `w["pilot"]` appris, gardé dans la liste / les shows par les enveloppes collect / apply),
  `_pilot_alarm` (clé (« PILOTE », kHz), kind PILOTE, `ALARM_HELP["PILOTE"]`), `forget_pilot`, `info_text`. Récepteur :
  rangée `row_auto` (🔁 Patrouille, durée, source, 🚨 Se caler sur les alarmes, ⏺ et enregistrer (accord vie privée),
  ↩ Revenir, `pat_lbl`) et ligne `info` (🏷 c'est quoi · 🔊 pilote, clic droit : oublier / alarme pilote). En Simple :
  patrouille + alarme seulement. Pavé numérique : `activatedAmbiguously` aussi (2 fenêtres principales = raccourci ambigu).
  Carte : pas de tuiles SDR en mode tinySA. `fake_iq.py` : « MHz:tonalité:pilote ».
  **Fluidité (2 SDR figeaient l'appli, déjà en étape 19, vu hors écran)** : `SdrEngine._frame_in` ne garde que la DERNIÈRE
  trame en attente (pics des sautées fusionnés) -> `_frame_go` ; `sdr_light_axes` (grands carreaux seulement) sur les
  graphes SDR : `QPicture.play` 10,5 s -> 2,9 s sur 25 s. Testé : test_sdr, script + gui_reel (pilote
  32 768 Hz appris, alarme PILOTE, patrouille, touche du pavé, calage sur alarme + WAV + retour). **Jamais avec un vrai
  SDR ni de vrais micros** : la fréquence réelle des pilotes des marques n'est PAS dans le code (appris sur le terrain) ;
  un pack sans pilote = « pas de pilote vu », rien d'autre ; « c'est quoi » = supposition d'après la forme du spectre.
- **V8 étape 21 (Clément : « un mode démo sur le SDR, avec audio pour écouter » + « générer avec du SDR ? » -> « Bothhh »)** :
  UN générateur pour les deux. PURE `DEMO_RATE` 2,4 MS/s, `DEMO_DBM` −40 (dBFS -> dBm du démo, via `sdr_offset("demo")`),
  `DEMO_PILOT` 32 768 Hz (exemple, pas une marque), `DEMO_SOUNDS` (voice « un, deux » synthétique, melody, beep, tone),
  `SIG_KINDS`, `SDR_DEMO_MODEL` (fiche à part : PAS dans `SDR_KINDS` / `SDR_MODELS`, qui alimentent les menus de balayage),
  `SDR_DEMO_KIND`, `demo_audio(kind, t, k)` (fonction du temps absolu : continue d'un bloc à l'autre), `sched_on` (période,
  allumé, décalage), `SigGen(rate, centre, signaux)` (`block(n)` : FM = cumul de phase gardé par signal, son à 48 kHz
  répété, pilote analytique ; noise = bruit filtré par FFT ; hors fenêtre sauté), `demo_sdr_plan(micros)` (tes micros :
  FM + son + pilote, numérique = bloc 200 kHz, bloc large, 1re « doit rester libre » = brouilleur 8 s / min, 1er micro
  éteint 15 s / 2 min, 2ᵉ sans pilote 10 s / 90 s, TNT 21 et 30 ; sans micros : 5 micros vers 606 MHz), `tx_plan` (centre
  décalé du continu, débit `TX_RATES` 4 / 10 / 20 MS/s, `TX_MAX_SIGS` 8), `tx_cmd` (`hackrf_transfer -t - -f -s -x -a
  [-d]`), `iq_ci8`. Qt : `SDR_DEMO_STATE` / `sdr_demo_set` (plan + émission simulée), `DemoIQ` (rythme réel, ne rattrape
  pas un gros retard), `open_iq_source("demo")`, `RealtimeWorker` accepte le genre « demo » (`SDR_KINDS.get`,
  `SDR_DTYPE.get` cf32). `SdrEngine.model()` = démo si `sdr_cfg["demo"]` (gardé par `sdr_cfg_extra`) ; plan rafraîchi
  toutes les 2 s (`_tick`, `demo_mics` : sans les 💤 / hors état) ; pas de conflit « même SDR » entre postes démo ; arrêt
  « introuvable » -> conseil « 🧪 SDR démo ». `TxRunner` (fil Python -> stdin de hackrf_transfer, somme des signaux à
  0,9 de la pleine échelle ; en démo : signaux posés dans le SDR démo), `SdrTxDialog` (`self._sdrtx` : tableau MHz / type
  / son / pilote / intermittent / niveau, « Depuis ma liste », gain 0–47 (0 d'office), ampli coupé, durée 1–30 min,
  case « EN CÂBLE » obligatoire hors démo, refus si un poste SDR tient le HackRF, journal « ÉMISSION SDR » / « FIN
  D'ÉMISSION SDR », arrêt à la fermeture et dans `_v8_close_event`). Menu du mode + sous-menu SDR : `set_sdr_demo`,
  `toggle_sdr_demo`, `open_sdr_tx`. `fake_iq.py -t` lit l'IQ et écrit ce qu'il a reçu (`FAKE_TX_OUT`). Testé : test_sdr
  (sons, phase continue, micro démo démodulé avec son et pilote, plan, émission), script + gui_reel (démo sans outil,
  niveaux, son, émission simulée vue par le démo, refus sans « câble », faux hackrf_transfer : porteuse à +300 kHz,
  gain 0). **Jamais avec un vrai HackRF en émission** : « -t - » (entrée standard) lu dans la doc, puissance réelle à
  mesurer au tinySA ; le compander n'est pas « encodé » dans la démo (couleur du son seulement).
  **Sons au choix (Clément : « choisir les audios, tous les sons de l'appli, un générateur 20 Hz – 20 kHz fréquence ou
  sweep, ajouter des WAV »)** : PURE `AUDIO_SRCS` (voice, melody, beep, tone, sweep, white, pink, app, wav, silence),
  `APP_SOUNDS` / `app_sound_seq` (alarmes 2 / 1 / 0, appel des micros : lus à l'appel, ALARM_TONES est défini plus bas),
  `WAV_PCM` {chemin: mono 48 kHz}, `audio_spec_norm` / `audio_text`, `_seq_audio`, `demo_audio(source dict…)` (balayage
  log / linéaire à phase exacte, bruit rose par FFT, WAV en boucle). Qt : `wav_load` (8 / 16 / 24 / 32 bits, mono /
  stéréo, rééchantillonné à 48 kHz, 10 min max), `AudioPickDialog` (source + réglages qui s'affichent selon la source,
  ▶ Écouter = QSoundEffect en boucle sur la sortie de l'appli ; `standalone` = 🎵 Générateur audio, `self._audiogen`),
  `audio_button` (colonne Son de l'émission : `b.spec`), son par micro du SDR démo (`sdr_cfg["demo_snd"]` {kHz: source},
  gardé par `sdr_cfg_extra` ; clic droit « Mes micros » en démo › 🎵, `demo_sound`, `pick_demo_sound`), menus du mode et
  du SDR (`open_audio_gen`). Testé : test_sdr (fréquence du générateur, milieu du balayage log, rose, alarme, WAV), script
  (WAV d'essai 1,5 kHz réentendu à 1 500 Hz après démodulation du SDR démo). **Son du générateur jamais entendu par
  Claude** (conteneur sans carte son : « format non supporté ») ; aigus coupés vers 15 kHz dans l'écoute FM (voulu).
  **Sons des alarmes au choix (Clément : « on peut même choisir les sons d'alarmes » -> « garde ça en V8 »)** : PURE
  `ALARM_SND_MAX_S` 4 s, `alarm_sounds_norm` ({alarm2 | alarm1 | alarm0 | ok: source}), `alarm_pcm` (durée selon la source,
  fondu 10 ms). `SoundOut.play` ENVELOPPÉ (`_v8_sound_play`) : la suite de notes reconnue par identité (`ALARM_TONES[n]`,
  `TONE_OK`) -> son choisi `self.sound.custom` en QAudioSink 48 kHz, sinon / en cas d'erreur le son d'origine V7.
  `SettingsDialog.__init__` ENVELOPPÉ : rubrique Son + « Sons des alarmes » (bouton par son, ▶ `test_alarm_sound`, ↺),
  `set_alarm_sound`. Config « alarm_sounds » (enveloppes collect / apply), `USER_KEYS` + « alarm_sounds » (profil
  utilisateur, pas les shows). **Jamais entendu par Claude** (pas de carte son ici : repli sur le son d'origine testé).
- **V8 étape 22 (Clément : « 1234 !! » sur : assistant premier branchement, calibrer avec le tinySA, remonter le temps,
  manuel SDR + liste du passage en 8.0)** : PURE `GAIN_OVF_MAX` 0,1 %, `GAIN_HEADROOM_DB` 6, `gain_steps(modèle, étage)`
  (8 valeurs au plus), `auto_gain_pick` (le plus fort sans écrêter avec 6 dB de marge ; crête proche du max sans
  écrêtage = le plus bas « peu de marge » ; tout écrête = le plus bas « sature »), `chan_power` (somme ± 100 kHz, case
  tinySA ramenée à pas / RBW, FFT divisée par l'ENBW Blackman 1,73), `calib_candidates` (signaux à + `CAL_SNR_DB` 15 des
  deux côtés), `sdr_tsa_offset` (médiane, écart max, ≥ `CAL_MIN_SIGNALS` 2), `RewindBuffer` (spectres max par 0,5 s réduits
  à 1 024 cases float16, son PCM, réglages de A ; `_trim` garde le réglage en cours au début ; `audio_from`, `tune_at`,
  `mem_mb`), `REWIND_MINUTES` 1 / 3 / 5. Qt : `sdr_gain_scan` (fil : chaque gain, 0,4 s d'IQ après 0,15 s jetées :
  écrêtage, bruit, crête), `SdrSetupWizard` (`self._sdrsetup` : 1 modèle, 2 `sdr_probe` via `run_heavy`, 3 gain ->
  `sdr_cfg["gains"][modèle]["lna"]` + journal « RÉGLAGE », 4 `sdr_tune_mic`, 5 calibration, 6 `diagnostic_sdr_*.txt` ;
  coupe le SDR démo ; arrête les postes avant de toucher au SDR), `SdrCalibDialog` (`self._sdrcalib` : 15 s de max hold
  SDR (`e.last`) et tinySA (`latest` des bandes ≥ 0) -> `calib_candidates` avec la RBW de `live_rbw` -> ✔ Appliquer =
  `sdr_cfg["offsets"][clé du modèle]` ; refus en SDR démo / sans tinySA / sans poste), `RewindDialog` (`self._rewind` :
  waterfall des minutes gardées, 0 s en haut, alarmes en repères, clic = instant + A à ce moment, ▶ 60 s en QSoundEffect,
  💾 WAV + PNG avec accord vie privée, journal « ENREGISTRÉ (SDR) »), bouton ⏪ du Récepteur (`rew_btn`),
  `SdrEngine.rew` (son poussé dans `_pump`, spectres dans `_frame`, réglages dans `set_a`), `sdr_cfg["rewind_min"]`.
  **Manuel SDR À PART** (pour ne pas toucher aux fichiers de la V7) : `docs/src/sdr_fr.html` / `sdr_en.html` (13 chapitres,
  blocs `<!--CH id|Titre-->`) -> `python tests/make_manual_sdr.py` -> `docs/manuel_sdr.html`, `docs/manual_sdr_en.html`, les
  PDF et **`manual_sdr.py`** (HTML embarqué : importé par le programme, PyInstaller le prend sans toucher au workflow) ;
  `open_sdr_manual` (fichier docs/ s'il est là, sinon le module écrit dans le dossier temporaire). **À refaire après toute
  modif du manuel SDR.** `docs/passage_v8.md` = la liste des essais en vrai + la procédure du passage en 8.0 (fondre le
  manuel SDR dans le principal ce jour-là). Menus du mode et SDR : 🔌 / 📏 / ⏪ / 📖. Testé : test_sdr (gain, calibration à
  0,2 dB, mémoire), script + gui_reel (faux SDR : assistant complet, gain, diagnostic, remonter le temps avec son,
  calibration sur données injectées, manuel embarqué). **Jamais avec un vrai SDR** : gain choisi, puissance de canal
  tinySA / SDR (RBW, ENBW) et calibration réelle à vérifier sur le terrain.
- **Audit V8 (Clément : « un p'tit audit ? », 26/11/2026, sur les étapes 19-22)** — corrigé : `chan_power` (point du
  tinySA × pas / RBW sans plafond : avant, pas 75 kHz / RBW 10 kHz = micro FM sous-estimé d'environ 9 dB -> calibration
  fausse ; message ⚠ si le pas > 1,5 × RBW) ; alarme PILOTE gardée jusqu'à 3 s de pilote retrouvé (`_pil_ok_t` : avant,
  elle retombait et renaissait avec un son à chaque fois) ; `wav_load` 3 min au plus (10 min = 115 Mo) ; `_seen_al`
  réduit aux alarmes en cours ; émission refusée aussi si un balayage `hackrf_sweep` tient le HackRF. Puis (Clément : « les
  points à voir avec moi, tu peux y aller ») : pilote vu = QUESTION « c'est bien ton émetteur ? » (`pil_pending`,
  `pilot_accept`, `pilot_reject` -> `w["_pil_rej"]`, non enregistré ; rangée `row_pil` du Récepteur) ; patrouille par
  fréquence (`patrol_items` trié : moins de recentrages) ; SDR seul à surveiller + alarme hors fenêtre = proposée
  (`_al_offer`, `alarm_offer`, `go_alarm`, bouton `go_al_btn` ; `_alarm_go` = le calage) ; ⏪ « Désactivé » (`REWIND_MINUTES`
  0, `RewindBuffer` n'enregistre rien) + mémoire par poste dans la bulle ; l'assistant DEMANDE avant d'arrêter un poste
  (`_busy`). Limite du test d'interface Windows de la CI : 12 min (workflow, côté V7).
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
