#!/usr/bin/env python3
"""Relais réseau du tinySA pour Raspberry Pi (ou tout Linux / Mac / PC sans écran) — TinySA Monitor.

Le tinySA est branché en USB sur le Pi ; ce script le partage sur le réseau (TCP, port 5025 par défaut).
Sur le PC de régie, dans TinySA Monitor : « 2ᵉ tinySA » = l'adresse du Pi, ex. « 192.168.1.42 » ou
« raspberrypi.local ». Seul besoin : Python 3 et pyserial (sudo apt install python3-serial).

    python3 tinysa_relais.py                 # trouve le tinySA tout seul, port 5025
    python3 tinysa_relais.py --serial /dev/ttyACM0 --port 5025

Même protocole que « TinySA-Monitor.exe --relais » : les octets passent tels quels, un seul client à la fois
(un nouveau remplace l'ancien : reconnexion après une coupure Wi-Fi), réouverture du port USB s'il est débranché.
"""
import argparse
import os
import select
import socket
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:                              # pragma: no cover
    sys.exit("pyserial manque : sudo apt install python3-serial   (ou : pip3 install pyserial)")

TINYSA_IDS = {(0x0483, 0x5740)}                  # tinySA et tinySA Ultra (port série virtuel STM32)
RELAY_PORT = 5025


def find_tinysa():
    """Port du tinySA : d'abord par son identifiant USB, sinon le 1er /dev/ttyACM*. None si rien."""
    ports = list(list_ports.comports())
    for p in ports:
        if (p.vid, p.pid) in TINYSA_IDS:
            return p.device
    for p in ports:
        if "ACM" in p.device:
            return p.device
    return None


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips) or ["(pas de réseau ?)"]


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def serve(serial_port=None, tcp_port=RELAY_PORT, host="0.0.0.0", stop=None, opener=None, on_ready=None):
    """Boucle du relais. serial_port None = détection automatique (et à chaque réouverture)."""
    opener = opener or (lambda p: serial.serial_for_url(p, 115200, timeout=0.05))
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, int(tcp_port)))
    srv.listen(2)
    port = srv.getsockname()[1]
    log(f"Relais prêt sur le port {port} · adresse(s) du Pi : {', '.join(local_ips())}")
    if on_ready:
        on_ready(port)
    ser, conn, last_err = None, None, ""
    try:
        while not (stop and stop()):
            if ser is None:
                path = serial_port or find_tinysa()
                try:
                    if not path:
                        raise OSError("aucun tinySA branché en USB")
                    ser = opener(path)
                    log(f"tinySA ouvert : {path}")
                    last_err = ""
                except Exception as e:  # noqa: BLE001
                    if str(e) != last_err:
                        log(f"En attente du tinySA ({e})")
                        last_err = str(e)
                    time.sleep(2.0)
                    continue
            socks = [srv] + ([conn] if conn is not None else [])
            rd, _, _ = select.select(socks, [], [], 0.01)
            if srv in rd:                          # nouveau client : il remplace l'ancien
                new, addr = srv.accept()
                new.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if conn is not None:
                    conn.close()
                conn = new
                log(f"Client connecté : {addr[0]}")
                try:
                    ser.reset_input_buffer()
                except Exception:  # noqa: BLE001
                    pass
            try:
                if conn is not None and conn in rd:
                    data = conn.recv(4096)
                    if not data:
                        log("Client parti")
                        conn.close()
                        conn = None
                    else:
                        ser.write(data)
                n = ser.in_waiting
                if n:
                    data = ser.read(n)
                    if conn is not None:
                        conn.sendall(data)
            except (OSError, socket.error) as e:
                if conn is not None and isinstance(e, (ConnectionError, socket.timeout)):
                    log("Client coupé")
                    conn.close()
                    conn = None
                else:                              # erreur côté USB : on rouvre le port
                    log(f"tinySA perdu ({e}) : nouvel essai")
                    try:
                        ser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    ser = None
    finally:
        for x in (conn, srv, ser):
            try:
                if x is not None:
                    x.close()
            except Exception:  # noqa: BLE001
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relais réseau du tinySA (TinySA Monitor)")
    ap.add_argument("--serial", help="port du tinySA (défaut : trouvé tout seul)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("TSM_RELAY_PORT", RELAY_PORT)),
                    help=f"port TCP (défaut {RELAY_PORT})")
    a = ap.parse_args(argv)
    try:
        serve(a.serial, a.port)
    except KeyboardInterrupt:
        log("Arrêt")


if __name__ == "__main__":
    main()
