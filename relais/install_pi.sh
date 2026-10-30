#!/bin/sh
# Installe le relais du tinySA sur un Raspberry Pi (Raspberry Pi OS) et le lance tout seul à chaque démarrage.
#   sh install_pi.sh
set -e
DIR=/opt/tinysa-relais
U=$(id -un)
sudo apt-get install -y python3-serial
sudo mkdir -p "$DIR"
sudo cp "$(dirname "$0")/tinysa_relais.py" "$DIR/"
sudo usermod -aG dialout "$U"
sudo tee /etc/systemd/system/tinysa-relais.service >/dev/null <<UNIT
[Unit]
Description=Relais réseau du tinySA (TinySA Monitor)
After=network-online.target
Wants=network-online.target

[Service]
User=$U
ExecStart=/usr/bin/python3 $DIR/tinysa_relais.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now tinysa-relais.service
echo
echo "Relais installé et lancé (il redémarre tout seul). Adresse(s) du Pi :"
hostname -I
echo "Dans TinySA Monitor (PC) : 2ᵉ tinySA = une de ces adresses, ou $(hostname).local"
echo "Voir ce qu'il fait :  journalctl -u tinysa-relais -f"
