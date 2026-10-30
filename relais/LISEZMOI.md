# Relais réseau du tinySA sur Raspberry Pi

Pour chasser un brouilleur loin du PC : un tinySA branché en USB sur un Raspberry Pi (dans un sac, avec une batterie
USB), partagé en Wi-Fi. TinySA Monitor (sur le PC de régie) le voit comme **2ᵉ tinySA**, et ton téléphone affiche
la chasse (page web, vue **🔎 Chasse**) et bippe.

## Installer (une seule fois)

1. **Raspberry Pi Imager** → Raspberry Pi OS (Lite suffit). Dans les réglages d'Imager : nom d'hôte (ex.
   `tinysa-sac`), **Wi-Fi du site** (ou de ta régie), utilisateur / mot de passe, **SSH activé**.
2. Démarre le Pi, puis depuis ton PC : `scp -r relais tinysa-sac.local:` (ou copie le dossier `relais` avec une clé USB).
3. Sur le Pi (`ssh tinysa-sac.local`) : `cd relais && sh install_pi.sh`

C'est tout : le relais démarre **tout seul à chaque allumage**, trouve le tinySA tout seul (même débranché /
rebranché) et attend TinySA Monitor sur le port **5025**. L'installeur affiche l'adresse du Pi.

## Dans TinySA Monitor (PC)

Réglages › **2ᵉ tinySA** : coche « Utiliser un 2ᵉ tinySA », adresse = `tinysa-sac.local` (ou son adresse IP, ex.
`192.168.1.42`), nom de position « Sac à dos ». Puis ▶ Démarrer.

## Sur le téléphone

Page web de l'appli (📣 Alertes et page web), vue **🔎 Chasse** : fréquence, « 2ᵉ tinySA · Sac à dos », ▶ Chasser
(code PIN de la page web). Le 1er tinySA continue de surveiller toutes les bandes pendant ce temps.

## Utile

- Voir ce que fait le relais : `journalctl -u tinysa-relais -f`
- L'arrêter / le relancer : `sudo systemctl stop tinysa-relais` / `sudo systemctl restart tinysa-relais`
- Sans installer : `python3 tinysa_relais.py` (ou `--serial /dev/ttyACM0 --port 5025`)
- Besoin : Python 3 + pyserial (`sudo apt install python3-serial`, fait par l'installeur).

⚠ Le Pi et le téléphone doivent rester dans la couverture du Wi-Fi. Tout passe en clair sur le réseau local.
