# TinySA Monitor — contexte pour Claude Code

Application Windows (un seul fichier : `tinysa_monitor.py`, ~7 600 lignes) pour tinySA Ultra : spectre en direct +
monitoring de 100+ fréquences, pensée pour la coordination HF en festival. Version courante : **7.0**.
Stack : Python 3.12/3.13, PySide6, pyqtgraph, numpy, pyserial. Compilée en .exe avec PyInstaller (`build.bat` ou le
workflow GitHub Actions `.github/workflows/build-exe.yml`).

## Qui / comment répondre
L'utilisateur (Clément) est technicien son/HF/AV en festivals (utilise EazyRF, WWB, WSM). Il parle un français
décontracté : réponds en français, ton détendu mais précis, concret et actionnable.
**Dis toujours ce qui n'est pas vérifié** : l'interface Qt réelle n'a jamais été lancée par Claude (voir Tests).

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
python tests/check_names.py      # noms non définis (les « hérités de Qt » sont normaux)
```
Chaque script affiche `ÉCHECS: 0` quand tout va bien. Les `smoke_test*` utilisent `tests/fakeqt.py`, un **faux Qt**
(classes « fourre-tout ») : ils vérifient la logique de `MainWindow` et des dialogues, **pas** le rendu ni le comportement
réel de Qt (docks, double écran, sons, redimensionnement). Sur un vrai Windows avec PySide6 installé, lancer l'appli
et vérifier à l'œil : docks et dispositions, bouton 🔔, panneau d'alarmes, relecture, rapport, imports WSM/WWB.

## Pièges connus
- PySide6 : énumérations qualifiées complètes (`Qt.ItemDataRole.UserRole`, etc.).
- Les signaux `clicked` / `triggered` passent un booléen `checked` : connecter avec `lambda *_: methode()` quand la
  méthode a des paramètres optionnels.
- Dans les tests, un balayage doit contenir de l'énergie aux fréquences testées : `on_sweep` recalcule tous les états.
- Modifications du gros fichier : patchs « remplacer exactement une occurrence » (échouer si 0 ou 2 correspondances),
  puis `python -m py_compile tinysa_monitor.py`, les tests, et ne jamais committer `__pycache__`.

## Reste à faire / idées
- **Deuxième tinySA** (deux ports, deux `ScanWorker`, répartition des bandes) : reporté, pas de matériel pour tester.
- Valider l'interface sur un vrai Windows (voir Tests) et corriger ce qui cloche.
- Ajouter les vrais formats d'import EazyRF / WWB / WSM dès que Clément fournit des exemples.
