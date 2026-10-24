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
- **Deux tinySA** en parallèle, sur le même PC ou par le réseau (relais intégré), avec bascule automatique
- Guide des bandes 100 kHz – 5,9 GHz par pays, canaux TV, profils d'événement, journal CSV automatique

## Installer

### Option 1 — l'exe prêt à l'emploi
Onglet **Actions** du dépôt → dernier run « Build TinySA-Monitor.exe » → télécharge l'artefact `TinySA-Monitor`.
Quand tu pousses un tag (`v7.0`, …), l'exe est aussi attaché à la page **Releases**.

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
3. **Offset** du 2ᵉ : correction en dB si les deux appareils ne lisent pas tout à fait pareil.

Le zoom live est fait par un seul tinySA. En réseau, préfère un câble au Wi-Fi ; une liaison qui se tait
(câble arraché) est détectée après ~30 s au réglage par défaut (plus long avec un RBW très étroit).

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
