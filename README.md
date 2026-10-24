# TinySA Monitor

Application Windows (Python / PySide6) pour **analyser le spectre** et **surveiller en continu 100+ fréquences**
avec un **tinySA Ultra** : pensée pour la coordination HF en festival, sonorisation et événementiel.

> Les attributions de bandes (police, aéro, 4G/5G, TNT, micros HF…) sont **indicatives** : vérifie toujours la
> réglementation locale avant d'émettre.

## Ce que ça fait

- **Spectre en direct** multi-bandes, max hold, waterfall, zoom, courbe de référence (bruit de fond du lieu)
- **Liste de fréquences** (nom, statut, seuil propre à chaque fréquence, taux d'occupation 10 min → 12 h)
- **Couches Scènes › Groupes** : un clic = on ne surveille / ne scanne que le groupe voulu ; bouton Global pour tout voir
- **Statuts** : « doit rester libre » (⚠ CONFLIT si un signal apparaît) et « doit émettre » (⚠ ABSENT si un TX se tait)
- **Alarmes** : panneau dédié, acquittement, priorité par groupe (Critique ❗ = son répété jusqu'à acquittement)
- **Intermodulation** 2 / 3 / 5 TX (ordres 3, 5, 7) et « d'où ça peut venir ? » pour un signal inconnu
- **Fréquence de secours** : canaux libres d'après le spectre mesuré, sans intermod avec ta liste
- **Nommage rapide** (MIC 1, HF 1, IEM 1, Intercom… avec numérotation automatique +1)
- **Enregistrement des balayages + relecture** (curseur de temps, lecture accélérée, saut à un événement)
- **Rapport de fin de show** (HTML autonome, imprimable en PDF)
- **Scans WSM / WWB** : import d'un scan comme référence, conversion WSM → WWB, export du scan au format WWB
- **Export des fréquences** par scène / par groupe
- **Fenêtres libres** : panneaux déplaçables / détachables (double écran), mur de fréquences plein écran
- **Deux tinySA** en parallèle, sur le même PC ou par le réseau (relais intégré), avec bascule automatique,
  noms de position et calibration
- **Alertes sur téléphone** (ntfy / Telegram) et **page web** en lecture seule pour l'équipe
- Guide des bandes 100 kHz – 5,9 GHz par pays, canaux TV, profils d'événement, journal CSV automatique

## Installer

### Option 1 — l'exe prêt à l'emploi
Page **Releases** du dépôt : `TinySA-Monitor.exe` dans la dernière version (stable, publiée à chaque nouvelle version
sur `main`) ou dans la pré-release « Test … » (dernière version de test, remplacée à chaque push de la branche).
Lien direct vers la dernière version stable :
`https://github.com/leturboc/TinySA-Monitor/releases/latest/download/TinySA-Monitor.exe`

### Option 2 — le compiler toi-même
Double-clique sur `build.bat` (installe Python via winget si besoin, puis crée `dist\TinySA-Monitor.exe`).

### Option 3 — lancer depuis Python
```
pip install -r requirements.txt
python tinysa_monitor.py
```
Python 3.12 ou 3.13 conseillé.

## Deux tinySA (USB ou réseau)

Deux tinySA balayent en parallèle : le cycle est environ deux fois plus court, et **si l'un décroche, l'autre
reprend toutes les bandes** (alarme critique ⚠ APPAREIL, nouvel essai de connexion toutes les 5 s).

1. **Réglages › 2ᵉ tinySA** : coche « Utiliser un 2ᵉ tinySA » et donne son adresse.
   - branché sur le même PC : son port (`COM4`) ;
   - branché sur **un autre PC** : sur ce PC-là, lance `TinySA-Monitor.exe --relais` (ou 🔧 Outils › 📡 Relais
     réseau), choisis le port du tinySA et clique « Partager ». La fenêtre affiche l'adresse à saisir sur le PC
     principal, par ex. `192.168.1.20:5025`. Windows demande d'autoriser l'accès réseau : accepte (réseau privé).
     Un pont série-TCP en mode brut (ser2net, Raspberry Pi…) marche aussi.
2. Table des **bandes**, colonne « tinySA » (double-clic) : **Auto** (répartition équilibrée), **1** ou **2**.
   Une seule grosse bande ne se partage pas : **✂ Couper** la divise en deux moitiés.
3. **Noms de position** (« Plateau », « FOH »…) : repris dans les alarmes et le journal (« vu par FOH »), pour
   savoir quelle antenne a vu le signal.
4. **Offset** du 2ᵉ : correction en dB si les deux appareils ne lisent pas pareil, ou **⚖ Calibrer le 2ᵉ sur le 1er**
   (les deux reçoivent le même signal, même antenne via un splitter : ~20 s et l'offset est réglé tout seul).

Pendant le zoom live, un tinySA zoome et l'autre continue de surveiller toutes les bandes. En réseau, préfère un câble au Wi-Fi ; une liaison qui se tait
(câble arraché) est détectée après ~30 s au réglage par défaut (plus long avec un RBW très étroit).

## Repères du spectre : choisir ce qu'on affiche

Bouton **📍 Repères** (au-dessus du spectre) :
- par **état mesuré** (occupées, faibles, libres, sans mesure), par **scène › groupe**, par **statut** ;
- **fréquence par fréquence** : clic droit dans la liste › « Masquer le repère sur le spectre » ;
- « Toujours montrer les fréquences en alarme » (coché par défaut : un filtre ne cache jamais une alarme) ;
- noms, signaux inconnus, style **trait plein** ou **petit repère discret en haut**, couleur (état / statut / groupe) ;
- **Ctrl+M** masque / réaffiche tout d'un coup ; « Tout afficher » enlève les filtres.

## Sennheiser Spectera (WMAS) et autres porteurs larges

Spectera émet un **porteur large de 6 ou 8 MHz** (un canal TV) au lieu d'une fréquence par micro : on le surveille
comme un **bloc**.
- 🔧 Outils › **📶 Ajouter un bloc Spectera / WMAS** : choisis le canal TV (selon le pays) ou une fréquence centrale +
  largeur. Ou, sur une fréquence existante : clic droit › « Bloc large ».
- « Doit émettre » : on regarde le **niveau médian** du bloc (le porteur est-il là ?) → ⚠ ABSENT s'il disparaît.
  « Doit rester libre » : on regarde le **pic** dans le bloc → ⚠ CONFLIT au moindre signal.
- Sur le spectre, un bloc est dessiné par ses deux bords et une barre. Une fréquence qui tombe **dans** un bloc est
  signalée dans la liste (« ⚠ dans le bloc … »).
- Préréglages de bandes : Spectera UHF 470–608 / 630–698 MHz et 1G4 1350–1400 / 1435–1525 MHz (selon les pays).
- Le mode démo simule un porteur Spectera pour les blocs « Doit émettre ».

L'intermodulation ne tient pas compte de la largeur des blocs (calcul sur leur fréquence centrale).

## Alertes sur téléphone et page web

🔧 Outils › **📣 Alertes téléphone et page web** :

- **Alertes push** (critiques seulement, ou critiques + normales) via **ntfy** (appli gratuite iOS / Android, sans
  compte : on s'abonne au nom de canal affiché) ou **Telegram** (bot créé avec @BotFather). Il faut Internet
  (4G, wifi du site). Bouton « Envoyer une alerte de test ». Un tinySA perdu / retrouvé est aussi signalé.
- **Page web en lecture seule** sur le réseau local : le régisseur ouvre l'adresse affichée
  (`http://192.168.x.x:8080`) sur son téléphone et voit les fréquences et alarmes, filtrées par scène / groupe,
  rafraîchies toutes les 2 s. Sans mot de passe : à n'activer que sur un réseau de confiance.

Le jeton Telegram reste dans la config de ce PC : il n'est pas copié dans les profils d'événement.

## Démarrage rapide

1. Branche le tinySA Ultra en USB, choisis le port (ou coche **Démo** pour essayer sans matériel), **▶ Démarrer**.
2. Importe tes fréquences (📥 Importer CSV : plan de fréquences EazyRF, WWB, Excel…) ou saisis-les, range-les en
   Scènes › Groupes.
3. Donne un statut à chaque fréquence : *Libre* (doit rester libre) ou *En service* (doit émettre).
4. 🔔 en haut à droite = alarmes. Clic droit sur un groupe → priorité des alarmes.

## Où sont mes données ?

- Réglages : `%APPDATA%\TinySAMonitor\` (`config.json`, `reference.json`, `profils\`)
- Journaux, enregistrements, rapports : `Documents\TinySA Monitor\Journaux\` (dossier modifiable dans l'appli)

## Crédits

Le format des exports de scan **Sennheiser WSM** et l'import de scans **Shure WWB** s'appuient sur le fonctionnement du
projet [nikharju/WSM-WWB-csv-converter](https://github.com/nikharju/WSM-WWB-csv-converter) (MIT) ; le code de ce dépôt
est une réécriture indépendante.
WSM, WWB, EazyRF, tinySA sont des marques de leurs propriétaires respectifs ; ce projet n'est affilié à aucun d'eux.
