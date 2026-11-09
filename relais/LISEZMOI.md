# Kit Raspberry Pi : le tinySA dans le sac, le PC en régie

Un tinySA branché en USB sur un Raspberry Pi (dans un sac, avec une batterie USB), partagé en Wi-Fi.
TinySA Monitor, sur le PC de régie, le voit comme s'il était branché sur le PC. Ton téléphone affiche la chasse
(page web, vue **🔎 Chasse**) et bippe.

- **Un seul tinySA** : il va dans le sac, et c'est le **1er tinySA** (liste des ports › « 🌐 tinySA en réseau… »).
- **Deux tinySA** : l'un reste sur le PC et surveille, l'autre va dans le sac comme **2ᵉ tinySA** (⚙ Réglages › 2ᵉ tinySA).

Ce dossier contient :

| Fichier | Rôle |
|---|---|
| `tinysa_relais.py` | Le programme du Pi : trouve le tinySA en USB et le partage sur le réseau (port TCP **5025**). Python + pyserial, rien d'autre. |
| `install_pi.sh` | L'installeur, à lancer **une seule fois** sur le Pi : installe pyserial, copie le programme dans `/opt/tinysa-relais` et le lance tout seul à chaque allumage. |
| `LISEZMOI.md` | Ce mode d'emploi. |

Où le trouver : sur la page de la release, à côté de `TinySA-Monitor.exe`, le fichier **`relais-raspberry-pi.zip`**.

## 1. Préparer la carte SD (sur le PC, une seule fois)

1. Installe **Raspberry Pi Imager** (raspberrypi.com/software) et lance-le.
2. Appareil : ton modèle de Pi. Système : **Raspberry Pi OS Lite** (sans bureau : c'est suffisant). Stockage : la carte SD.
3. Quand Imager propose de **modifier les réglages**, accepte :
   - nom d'hôte : `tinysa-sac` ;
   - nom d'utilisateur et mot de passe (note-les) ;
   - **Wi-Fi** : le réseau sur lequel sera le PC de régie (nom + mot de passe, pays FR) ;
   - onglet Services : **activer SSH** (mot de passe).
4. Écris la carte, mets-la dans le Pi, branche l'alimentation. Attends 1 à 2 minutes (1er démarrage plus long).

## 2. Copier le kit sur le Pi et l'installer (une seule fois)

Sur le PC Windows, dézippe `relais-raspberry-pi.zip` (par ex. dans Téléchargements). Ouvre **Terminal** (ou
« Invite de commandes »), puis :

```
cd Downloads\relais-raspberry-pi
scp -r relais tinysa-sac.local:
ssh tinysa-sac.local
```

(Le PC doit être sur le même Wi-Fi que le Pi. À la 1re connexion, réponds `yes`, puis le mot de passe du Pi.)
Une fois connecté au Pi :

```
cd relais
sh install_pi.sh
```

L'installeur affiche l'**adresse IP** du Pi : note-la (ex. `192.168.1.42`). C'est fini : tape `exit`.

Si `tinysa-sac.local` ne répond pas, utilise l'adresse IP du Pi (visible dans la page de ta box / routeur).

## 3. Le jour J

1. Branche le tinySA sur le Pi (câble USB-C), allume le tinySA, alimente le Pi. Le relais démarre tout seul,
   retrouve le tinySA même débranché / rebranché.
2. Dans TinySA Monitor (PC) :
   - liste des ports en haut › **🌐 tinySA en réseau : adresses enregistrées…** › **＋ Ajouter** (`tinysa-sac.local`
     ou l'IP du Pi) › **🔌 Tester** › **Utiliser pour le 1er tinySA** (un seul tinySA) ou **pour le 2ᵉ** (deux
     tinySA). Puis ▶ Démarrer ;
   - **le Pi change d'IP selon le Wi-Fi** : enregistre une adresse par réseau (« Pi · maison », « Pi · festival »,
     « Pi · téléphone »…) ; chacune apparaît dans la liste des ports, et elles sont gardées avec le show (🎪).
3. Sur le téléphone : page web de l'appli (📣 Alertes et page web), vue **🔎 Chasse** : choisis le tinySA du sac,
   la fréquence, ▶ Chasser (code PIN de la page web). Le téléphone bippe de plus en plus vite en approchant.

## 4. Plusieurs tinySA sur le même Pi

Un Pi peut partager jusqu'à 8 tinySA (un réseau, une boîte, plusieurs antennes) :

1. Installe le relais en mode « multi » : `sh install_pi.sh multi` (si le relais simple est déjà installé, relance
   simplement cette commande : elle remplace le réglage).
2. Branche les tinySA (sur un **hub USB alimenté** au-delà de deux : les prises du Pi ne fournissent pas assez de
   courant pour charger plusieurs tinySA).
3. Chaque tinySA a son port réseau : le premier vu **5025**, le suivant **5026**, puis 5027… Il est reconnu par son
   numéro de série USB : le même tinySA garde **toujours** le même port, quelle que soit la prise (souvenir gardé
   dans `~/.tinysa_relais_ports.json`). Pour voir qui est sur quel port : `journalctl -u tinysa-relais -f`
   (« tinySA … → port 5026 ») ou `python3 /opt/tinysa-relais/tinysa_relais.py --diag`.
4. Dans TinySA Monitor : une adresse enregistrée par tinySA, avec le port : `tinysa-sac.local:5025`,
   `tinysa-sac.local:5026`… puis ⚙ › Plusieurs tinySA (le 2ᵉ, puis le tableau des 3ᵉ à 8ᵉ).

Astuce : colle une étiquette « 5025 », « 5026 »… sur chaque tinySA une fois les ports attribués.

## 5. Sécurité du réseau

Le relais n'a **pas de mot de passe** : toute machine du réseau qui joint le Pi sur le port 5025 peut parler au
tinySA. Sur un réseau technique isolé (le réseau de la régie, un routeur à toi), ce n'est pas un problème. Sur un
Wi-Fi partagé (public, catering…), limite l'accès :

- **Seulement le PC de régie** : remplace `192.168.1.10` par l'IP du PC.
  ```
  sudo systemctl edit tinysa-relais
  ```
  puis écris ces deux lignes, enregistre (Ctrl+O, Entrée, Ctrl+X) :
  ```
  [Service]
  Environment=TSM_RELAY_ALLOW=192.168.1.10
  ```
  et `sudo systemctl restart tinysa-relais`. Plusieurs PC : `TSM_RELAY_ALLOW=192.168.1.10,192.168.1.11`.
  Le journal dit « Connexion refusée » pour les autres.
- **Une seule interface** du Pi (ex. seulement le câble Ethernet) : `Environment=TSM_RELAY_HOST=192.168.1.50` (l'IP
  du Pi sur ce réseau-là).
- Les mêmes réglages existent en ligne de commande : `--allow 192.168.1.10` et `--host 192.168.1.50`.

Un client qui se fige (PC en veille, Wi-Fi qui décroche) est lâché au bout de 5 s : il ne bloque plus le relais.

## Dépannage

### « En attente du tinySA (aucun tinySA vu en USB) »

Le Pi ne voit pas le tinySA. Lance le diagnostic : `python3 /opt/tinysa-relais/tinysa_relais.py --diag`
(il liste ce que le Pi voit en USB et dit quoi faire ; le journal l'affiche aussi). Dans 9 cas sur 10 :

1. **Le tinySA est éteint** : éteint, il ne fait que se charger, il n'apparaît pas en USB. Allume-le.
2. **Le câble ne fait que la charge** : beaucoup de câbles USB-C n'ont pas les fils de données. Prends celui qui marche
   avec le PC (tinySA-App / TinySA Monitor).
3. **Mauvaise prise du Pi** : sur un Pi 4 / Pi 5, la prise USB-C sert **seulement** à l'alimentation → branche le
   tinySA sur un port USB-A (câble USB-A ↔ USB-C). Sur un Pi Zero : la prise marquée « USB » (pas « PWR ») avec un
   adaptateur OTG.
4. **Le tinySA est en mode « disque USB » ou mise à jour (DFU)** : redémarre-le normalement.

Commandes utiles : `lsusb` (le tinySA = `0483:5740 STMicroelectronics`), `ls -l /dev/ttyACM*`,
`sudo dmesg | tail -20` juste après l'avoir branché.

### Le reste

- Ce que fait le relais : `ssh tinysa-sac.local` puis `journalctl -u tinysa-relais -f`
- Le relancer : `sudo systemctl restart tinysa-relais` · l'arrêter : `sudo systemctl stop tinysa-relais`
- Sans l'installer (pour essayer) : `python3 tinysa_relais.py` (ou `--serial /dev/ttyACM0 --port 5025`)
- Pas de Wi-Fi au festival ? Un petit routeur Wi-Fi de poche (ou le partage de connexion du téléphone) pour le PC,
  le Pi et le téléphone : il suffit qu'ils soient sur le même réseau. Pour changer de Wi-Fi sur le Pi :
  `sudo nmtui`.

⚠ Le Pi, le PC et le téléphone doivent rester dans la couverture du même Wi-Fi. Tout passe en clair sur le réseau
local. Testé sur un Raspberry Pi 4 avec un tinySA Ultra (firmware 2026). En cas de
souci, envoie la sortie de `journalctl -u tinysa-relais`.
