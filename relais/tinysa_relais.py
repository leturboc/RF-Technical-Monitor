#!/usr/bin/env python3
"""Relais réseau du tinySA pour Raspberry Pi (ou tout Linux / Mac / PC sans écran) — RF Technical Monitor.

Le tinySA est branché en USB sur le Pi ; ce script le partage sur le réseau (TCP, port 5025 par défaut).
Sur le PC de régie, dans RF Technical Monitor : « 2ᵉ tinySA » = l'adresse du Pi, ex. « 192.168.1.42 » ou
« raspberrypi.local ». Seul besoin : Python 3 et pyserial (sudo apt install python3-serial).

    python3 tinysa_relais.py                 # trouve le tinySA tout seul, port 5025
    python3 tinysa_relais.py --serial /dev/ttyACM0 --port 5025
    python3 tinysa_relais.py --multi         # PLUSIEURS tinySA sur ce Pi : 5025, 5026, 5027…

En --multi, chaque tinySA est reconnu par son numéro de série USB : le même tinySA garde toujours le même port
réseau (quelle que soit la prise), retenu dans ~/.tinysa_relais_ports.json. Un tinySA branché plus tard reçoit le
port suivant.

Même protocole que « RF-Technical-Monitor.exe --relais » : les octets passent tels quels, un seul client à la fois
(un nouveau remplace l'ancien : reconnexion après une coupure Wi-Fi), réouverture du port USB s'il est débranché.
"""
import argparse
import glob
import json
import os
import select
import socket
import sys
import threading
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
    acm = sorted(glob.glob("/dev/ttyACM*"))       # pyserial ne voit pas tout (ex. /sys incomplet)
    return acm[0] if acm else None


def device_key(p):
    """Ce qui reconnaît UN tinySA : son numéro de série USB, sinon la prise USB, sinon le nom du port."""
    return str(getattr(p, "serial_number", None) or getattr(p, "location", None) or p.device)


def find_all_tinysa():
    """Tous les tinySA branchés -> [(clé, port)] triés par clé (voir device_key)."""
    out = [(device_key(p), p.device) for p in list_ports.comports() if (p.vid, p.pid) in TINYSA_IDS]
    if not out:                                   # pyserial ne voit pas tout : les ttyACM, par leur nom
        out = [(a, a) for a in sorted(glob.glob("/dev/ttyACM*"))]
    return sorted(out)


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def usb_devices(sys_root="/sys/bus/usb/devices"):
    """Appareils USB vus par le Pi : [(vid, pid, nom)] (hubs internes exclus)."""
    out = []
    for d in sorted(glob.glob(os.path.join(sys_root, "*"))):
        v, p_ = _read(os.path.join(d, "idVendor")), _read(os.path.join(d, "idProduct"))
        if not v or v == "1d6b":                     # 1d6b = hubs racine Linux
            continue
        name = " ".join(x for x in (_read(os.path.join(d, "manufacturer")), _read(os.path.join(d, "product"))) if x)
        out.append((v.lower(), p_.lower(), name or "?"))
    return out


def diagnose(sys_root="/sys/bus/usb/devices", dev_glob="/dev/ttyACM*", user=None):
    """Pourquoi le tinySA n'est pas trouvé : lignes de texte à lire dans journalctl (ou --diag)."""
    lines = []
    devs = usb_devices(sys_root)
    stm = [d for d in devs if d[0] == "0483"]
    acm = sorted(glob.glob(dev_glob))
    lines.append("Appareils USB vus : " + (", ".join(f"{v}:{p} {n}" for v, p, n in devs) or "AUCUN"))
    lines.append("Ports série USB (/dev/ttyACM*) : " + (", ".join(acm) or "aucun"))
    if any(p == "5740" for _, p, _ in stm):
        if not acm:
            lines.append("→ Le tinySA est bien branché (0483:5740) mais sans port série : redémarre le Pi.")
    elif any(p == "df11" for _, p, _ in stm):
        lines.append("→ Le tinySA est en mode MISE À JOUR (DFU) : éteins-le et rallume-le normalement.")
    elif stm:
        lines.append("→ Un appareil STM32 est vu mais pas en port série : le tinySA est peut-être en mode « disque USB »"
                     " (menu SD / USB) : quitte ce mode ou redémarre le tinySA.")
    else:
        lines.append("→ Le Pi ne voit PAS le tinySA du tout. Vérifie : 1) le tinySA est ALLUMÉ (éteint, il ne fait "
                     "que charger) ; 2) le câble transmet les données (beaucoup de câbles USB-C ne font que la "
                     "charge : essaie celui qui marche avec le PC) ; 3) il est branché sur un port USB-A du Pi (sur "
                     "un Pi 4 / 5, la prise USB-C sert UNIQUEMENT à l'alimentation ; sur un Pi Zero, prise « USB » "
                     "et pas « PWR », avec un adaptateur OTG).")
    for a in acm:
        if not os.access(a, os.R_OK | os.W_OK):
            u = user or os.environ.get("USER") or "pi"
            try:
                import grp
                in_dialout = u in grp.getgrnam("dialout").gr_mem
            except (ImportError, KeyError):
                in_dialout = False
            lines.append(f"→ {a} existe mais n'est pas accessible : " + (
                "redémarre le Pi (l'ajout au groupe dialout n'est pris en compte qu'après)." if in_dialout else
                f"sudo usermod -aG dialout {u} puis redémarre le Pi."))
    return lines


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


def serve(serial_port=None, tcp_port=RELAY_PORT, host="0.0.0.0", stop=None, opener=None, on_ready=None, finder=None,
          name="", allow=None):
    """Boucle du relais. serial_port None = détection automatique (et à chaque réouverture) ; finder() = port à ouvrir
    (mode --multi : le port de CE tinySA-là, None s'il est débranché). allow = adresses IP autorisées (None = toutes) :
    le relais n'a pas de mot de passe, réserve-le à un réseau technique isolé et / ou à l'adresse du PC de régie."""
    opener = opener or (lambda p: serial.serial_for_url(p, 115200, timeout=0.05, write_timeout=2.0))
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, int(tcp_port)))
    srv.listen(2)
    port = srv.getsockname()[1]
    tag = f"[{name}] " if name else ""
    log(f"{tag}Relais prêt sur le port {port} · adresse(s) du Pi : {', '.join(local_ips())}")
    if on_ready:
        on_ready(port)
    ser, conn, last_err = None, None, ""
    try:
        while not (stop and stop()):
            if ser is None:
                path = serial_port or (finder() if finder else find_tinysa())
                try:
                    if not path:
                        raise OSError("aucun tinySA vu en USB")
                    ser = opener(path)
                    log(f"{tag}tinySA ouvert : {path}")
                    last_err = ""
                except Exception as e:  # noqa: BLE001
                    if str(e) != last_err:
                        log(f"{tag}En attente du tinySA ({e})")
                        if serial_port is None and finder is None:
                            for ln in diagnose():
                                log("   " + ln)
                        last_err = str(e)
                    time.sleep(2.0)
                    continue
            socks = [srv] + ([conn] if conn is not None else [])
            rd, _, _ = select.select(socks, [], [], 0.01)
            if srv in rd:                          # nouveau client : il remplace l'ancien
                new, addr = srv.accept()
                if allow and addr[0] not in allow:
                    log(f"{tag}Connexion refusée : {addr[0]} n'est pas dans --allow")
                    new.close()
                    continue
                new.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                new.settimeout(5.0)        # client qui ne lit plus : envoi abandonné au bout de 5 s, client lâché
                if conn is not None:
                    conn.close()
                conn = new
                log(f"{tag}Client connecté : {addr[0]}")
                try:
                    ser.reset_input_buffer()
                except Exception:  # noqa: BLE001
                    pass
            try:
                if conn is not None and conn in rd:
                    data = conn.recv(4096)
                    if not data:
                        log(f"{tag}Client parti")
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
                    log(f"{tag}Client coupé")
                    conn.close()
                    conn = None
                else:                              # erreur côté USB : on rouvre le port
                    log(f"{tag}tinySA perdu ({e}) : nouvel essai")
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


PORTS_FILE = os.path.join(os.path.expanduser("~"), ".tinysa_relais_ports.json")


def load_ports(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {str(k): int(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_ports(path, ports):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ports, f, indent=1)
        os.replace(tmp, path)
    except OSError:
        pass


def next_port(ports, base):
    """Port réseau pour un nouveau tinySA : le premier libre à partir de base."""
    used = set(ports.values())
    p = base
    while p in used:
        p += 1
    return p


def serve_multi(base_port=RELAY_PORT, host="0.0.0.0", stop=None, opener=None, lister=None, ports_file=PORTS_FILE,
                scan_s=5.0, on_ready=None, allow=None):
    """--multi : un relais (un port TCP) par tinySA branché sur ce Pi. Le même tinySA (même numéro de série) garde son
    port, retenu dans ports_file ; un nouveau prend le premier port libre. base_port 0 = ports au hasard (tests)."""
    lister = lister or find_all_tinysa
    stop = stop or (lambda: False)
    ports = load_ports(ports_file) if ports_file else {}
    running, waiting_logged = {}, False
    log(f"Mode plusieurs tinySA · adresse(s) du Pi : {', '.join(local_ips())}")
    while not stop():
        cur = dict(lister())
        for key in sorted(cur):
            if key in running:
                continue
            if base_port:
                if key not in ports:
                    ports[key] = next_port(ports, base_port)
                    if ports_file:
                        save_ports(ports_file, ports)
                port = ports[key]
            else:
                port = 0
            th = threading.Thread(target=serve, daemon=True, kwargs=dict(
                tcp_port=port, host=host, stop=stop, opener=opener, name=key[-12:], allow=allow,
                finder=(lambda k=key: dict(lister()).get(k)),
                on_ready=(lambda p, k=key: on_ready(k, p)) if on_ready else None))
            th.start()
            running[key] = th
            log(f"tinySA {key} → port {port or '(auto)'}")
        if not running and not waiting_logged:
            log("En attente d'un tinySA en USB…")
            for ln in diagnose():
                log("   " + ln)
            waiting_logged = True
        t0 = time.time()
        while time.time() - t0 < scan_s and not stop():
            time.sleep(0.1)
    for th in running.values():
        th.join(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relais réseau du tinySA (RF Technical Monitor)")
    ap.add_argument("--serial", help="port du tinySA (défaut : trouvé tout seul)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("TSM_RELAY_PORT", RELAY_PORT)),
                    help=f"port TCP (défaut {RELAY_PORT})")
    ap.add_argument("--diag", action="store_true", help="dit pourquoi le tinySA n'est pas trouvé, puis quitte")
    ap.add_argument("--host", default=os.environ.get("TSM_RELAY_HOST", "0.0.0.0"),
                    help="n'écouter que sur cette adresse du Pi (défaut : toutes)")
    ap.add_argument("--allow", default=os.environ.get("TSM_RELAY_ALLOW", ""),
                    help="adresses IP autorisées, séparées par des virgules (ex. l'IP du PC de régie ; défaut : toutes)")
    ap.add_argument("--multi", action="store_true",
                    help="plusieurs tinySA sur ce Pi : un port réseau chacun (5025, 5026…), retenu par numéro de série")
    a = ap.parse_args(argv)
    if a.diag:
        print("tinySA trouvé :", find_tinysa() or "NON")
        for k, dev in find_all_tinysa():
            print(f"   {dev}  (n° {k})")
        for ln in diagnose():
            print(ln)
        return
    allow = [x.strip() for x in a.allow.split(",") if x.strip()] or None
    if allow:
        log(f"Seules ces adresses peuvent se connecter : {', '.join(allow)}")
    else:
        log("ATTENTION : aucune liste --allow : tout appareil du reseau peut piloter le tinySA. "
            "A reserver a un reseau technique de confiance (LISEZMOI, section Securite).")
    try:
        if a.multi and not a.serial:
            serve_multi(a.port, host=a.host, allow=allow)
        else:
            serve(a.serial, a.port, host=a.host, allow=allow)
    except KeyboardInterrupt:
        log("Arrêt")


if __name__ == "__main__":
    main()
