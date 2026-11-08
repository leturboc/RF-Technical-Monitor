#!/bin/sh
# Installe le relais du tinySA sur un Raspberry Pi (Raspberry Pi OS) et le lance tout seul à chaque démarrage.
#   sh install_pi.sh          (un tinySA sur ce Pi)
#   sh install_pi.sh multi    (PLUSIEURS tinySA sur ce Pi : ports 5025, 5026, 5027…)
set -e
OPT=""
[ "$1" = "multi" ] && OPT=" --multi"
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
ExecStart=/usr/bin/python3 $DIR/tinysa_relais.py$OPT
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
if [ -n "$OPT" ]; then
  echo "Mode plusieurs tinySA : le 1er tinySA branché a le port 5025, le suivant 5026, etc. (chaque tinySA garde le sien)."
  echo "Dans TinySA Monitor (PC) : adresse:port, ex. $(hostname).local:5025 puis $(hostname).local:5026…"
else
  echo "Dans TinySA Monitor (PC) : 2ᵉ tinySA = une de ces adresses, ou $(hostname).local"
fi
echo "Voir ce qu'il fait :  journalctl -u tinysa-relais -f"
