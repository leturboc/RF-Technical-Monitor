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
   - **un seul tinySA** : liste des ports en haut › **🌐 tinySA en réseau (Raspberry Pi, autre PC)…** › adresse
     `tinysa-sac.local` (ou l'IP). L'appli s'en souvient la fois suivante. Puis ▶ Démarrer ;
   - **deux tinySA** : ⚙ Réglages › 2ᵉ tinySA › « Utiliser un 2ᵉ tinySA », adresse `tinysa-sac.local`, nom de
     position « Sac à dos ». Puis ▶ Démarrer.
3. Sur le téléphone : page web de l'appli (📣 Alertes et page web), vue **🔎 Chasse** : choisis le tinySA du sac,
   la fréquence, ▶ Chasser (code PIN de la page web). Le téléphone bippe de plus en plus vite en approchant.

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
local. **Jamais testé sur un vrai Raspberry Pi** par l'auteur du programme (testé avec un tinySA simulé) : en cas de
souci, envoie la sortie de `journalctl -u tinysa-relais`.
