"""Alertes téléphone et page web, sans Qt : textes / requêtes ntfy et Telegram (section PURE), Notifier (file
d'envoi, essais, faux serveur ntfy local), WebServer (page + JSON), et la page dans un vrai navigateur si
Playwright + Chromium sont disponibles (sinon cette partie est sautée).

    python tests/test_alertes.py
"""
import base64
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

fails = 0


def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)


SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()


def chunk(start, end):
    a = SRC.index(start)
    return SRC[a:SRC.index(end, a)]


ns = dict(__name__="tsm_alertes")
exec("import bisect, csv, io, itertools, math, os, queue, re, threading, time, unicodedata, urllib.request\n"
     "from collections import deque\nfrom http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
     "import numpy as np\n", ns)
ns.update(MIN_PTS=51, HYST=3.0, RBW_LIST=[1, 3, 10, 30, 100])
exec(chunk("# ===== PURE-BEGIN", "# ===== PURE-END"), ns)
exec(chunk("class Notifier:", "class AlertsDialog"), ns)  # Notifier, _HTTPServer, WebServer

# ------------------------------------------------------------- textes
nw, nt = ns["notify_wanted"], ns["notify_text"]
check("critiques seulement : prio 2 oui, 1 non", nw(2, "crit") and not nw(1, "crit"))
check("toutes : prio 1 oui, info non", nw(1, "all") and not nw(0, "all"))
check("désactivées", not nw(2, "off"))
a = dict(kind="CONFLIT", name="HF 3", freq=512.0, level=-61.6, layer="Grande scène › IEM", info="vu par FOH", prio=2)
t, b = nt(a, "Festival X")
check("titre", t == "⚠ CONFLIT — HF 3", t)
check("corps", b == "[Festival X] 512.000 MHz · -62 dBm · Grande scène › IEM · vu par FOH", b)
t, b = nt(dict(kind="APPAREIL", name="FOH", freq=0.0, level=None, layer="", info="liaison perdue", prio=2))
check("alarme appareil : pas de fréquence", b == "liaison perdue", b)

url, hdr, data = ns["ntfy_request"]("https://ntfy.sh/", "/tinysa-abc", t, "corps é", 2)
check("ntfy : url", url == "https://ntfy.sh/tinysa-abc", url)
check("ntfy : urgent", hdr["Priority"] == "urgent")
check("ntfy : titre encodable en en-tête HTTP", all(ord(ch) < 256 for ch in hdr["Title"]), hdr["Title"])
enc = hdr["Title"]
check("ntfy : titre RFC 2047 décodable", enc.startswith("=?UTF-8?B?")
      and base64.b64decode(enc[10:-2]).decode("utf-8") == t, enc)
check("ntfy : titre simple non encodé", ns["ntfy_request"]("", "x", "Test", "b", 1)[1]["Title"] == "Test")
check("ntfy : serveur par défaut", ns["ntfy_request"]("", "x", "a", "b")[0] == "https://ntfy.sh/x")
url, hdr, data = ns["telegram_request"](" 123:ABC ", " 42 ", "Titre", "Corps")
check("telegram : url", url == "https://api.telegram.org/bot123:ABC/sendMessage", url)
check("telegram : json", json.loads(data) == dict(chat_id="42", text="Titre\nCorps", disable_web_page_preview=True))

# ------------------------------------------------------------- état web
ws = ns["web_state"]
rows = [dict(name="HF 1", freq=470.2, level=-60.04, state="occ", status="En service", scene="Grande scène",
             group="Micros", absent=False, conflict=False),
        dict(name="Libre 1", freq=499.0, level=None, state=None, status="Libre", scene="", group="", absent=False,
             conflict=False),
        dict(name="HF 2", freq=471.8, level=-98.0, state="free", status="En service", scene="Grande scène",
             group="Micros", absent=True, conflict=False)]
al = [dict(kind="ABSENT", name="HF 2", freq=471.8, prio=2, acked=False, layer="Grande scène › Micros", info="",
           t0=1.0, t_end=None),
      dict(kind="CONFLIT", name="X", freq=1.0, prio=1, acked=False, layer="", info="", t0=1.0, t_end=5.0)]
st = ws(rows, al, dict(title="T", time="12:00:00", running=True, cycle="1.0 s"))
check("état web : 3 fréquences", len(st["rows"]) == 3 and st["rows"][0]["level"] == -60.0)
check("état web : états lisibles", [r["state_txt"] for r in st["rows"]] == ["OCCUPÉ", "—", "libre"])
check("état web : ABSENT marqué", st["rows"][2]["alarm"] == "ABSENT")
check("état web : seulement les alarmes en cours", [x["kind"] for x in st["alarms"]] == ["ABSENT"])
check("état web : sérialisable", json.loads(json.dumps(st))["title"] == "T")

# ------------------------------------------------------------- Notifier
got = []
n = ns["Notifier"](sender=lambda u, h, d: got.append((u, d)), retry_s=0.05)
n.post(("u1", {}, b"x"))
t0 = time.time()
while not got and time.time() - t0 < 3:
    time.sleep(0.02)
check("notifier : envoyé hors du fil principal", got == [("u1", b"x")] and n.sent == 1)
calls = []


def flaky(u, h, d):
    calls.append(u)
    if len(calls) < 3:
        raise OSError("réseau absent")


n2 = ns["Notifier"](sender=flaky, retry_s=0.05)
n2.post(("u", {}, b""))
t0 = time.time()
while n2.sent == 0 and time.time() - t0 < 5:
    time.sleep(0.02)
check("notifier : 3 essais puis succès", len(calls) == 3 and n2.sent == 1 and n2.last_error == "", str(calls))
n3 = ns["Notifier"](sender=lambda *a: (_ for _ in ()).throw(OSError("pas de 4G")), retry_s=0.01)
n3.post(("u", {}, b""))
time.sleep(0.5)
check("notifier : échec mémorisé (affiché dans le dialogue)", n3.last_error == "pas de 4G" and n3.sent == 0)
check("notifier : post ne bloque jamais", (lambda t: (n3.post(("u", {}, b"")), time.time() - t)[1] < 0.05)(time.time()))

# --- faux serveur ntfy local : vraie requête HTTP
recv = []


class Ntfy(BaseHTTPRequestHandler):
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        recv.append((self.path, dict(self.headers), self.rfile.read(ln)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Ntfy)
threading.Thread(target=srv.serve_forever, daemon=True).start()
n4 = ns["Notifier"]()
title, body = nt(a, "Site")
n4.post(ns["ntfy_request"](f"http://127.0.0.1:{srv.server_address[1]}", "tinysa-test", title, body, 2))
t0 = time.time()
while not recv and time.time() - t0 < 5:
    time.sleep(0.02)
check("ntfy local : requête reçue", len(recv) == 1 and recv[0][0] == "/tinysa-test", str(recv))
if recv:
    h = recv[0][1]
    check("ntfy local : corps UTF-8", recv[0][2].decode("utf-8") == body)
    check("ntfy local : priorité urgente", h.get("Priority") == "urgent")
srv.shutdown()

# ------------------------------------------------------------- WebServer
state = {"v": json.dumps(st, ensure_ascii=False).encode("utf-8")}
w = ns["WebServer"](0, lambda: state["v"], host="127.0.0.1")
w.start()
w.ready.wait(3)
check("serveur web démarré", not w.error and w.port > 0, w.error)
base = f"http://127.0.0.1:{w.port}"
page = urllib.request.urlopen(base + "/", timeout=5).read().decode("utf-8")
check("page servie", "<title>TinySA Monitor</title>" in page and "etat.json" in page)
js = json.loads(urllib.request.urlopen(base + "/etat.json", timeout=5).read())
check("etat.json servi", js["rows"][0]["name"] == "HF 1")
try:
    urllib.request.urlopen(base + "/../config.json", timeout=5)
    check("chemin inconnu : 404", False)
except urllib.error.HTTPError as e:
    check("chemin inconnu : 404", e.code == 404)
busy = ns["WebServer"](w.port, lambda: b"{}", host="127.0.0.1")
busy.start()
busy.ready.wait(3)
check("port déjà pris : erreur claire", "indisponible" in busy.error, busy.error)

# ------------------------------------------------------------- la page dans un vrai navigateur
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright is None:
    print("Playwright absent : rendu de la page non testé")
else:
    with sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"            # Chromium préinstallé (conteneur Claude) ; sinon celui de Playwright
        br = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
        pg = br.new_page(viewport=dict(width=390, height=800))
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "/")
        pg.wait_for_selector(".c", timeout=5000)
        cards = pg.locator(".c")
        check("navigateur : 3 cartes", cards.count() == 3, str(cards.count()))
        check("navigateur : carte occupée", "occ" in (cards.nth(0).get_attribute("class") or ""))
        check("navigateur : carte en alarme", "alarm" in (cards.nth(2).get_attribute("class") or "")
              and "ABSENT" in cards.nth(2).inner_text())
        check("navigateur : bandeau d'alarme", "ABSENT — HF 2" in pg.locator("#al").inner_text())
        check("navigateur : en-tête", "en surveillance" in pg.locator("#meta").inner_text())
        pg.select_option("#flt", "Grande scène › Micros")
        check("navigateur : filtre par couche", pg.locator(".c").count() == 2)
        rows.append(dict(name="<b>x</b>", freq=600.0, level=-90.0, state="weak", status="", scene="Grande scène",
                         group="Micros", absent=False, conflict=False))
        state["v"] = json.dumps(ws(rows, al, dict(title="T", time="12:00:02", running=False, cycle="")),
                                ensure_ascii=False).encode("utf-8")
        pg.wait_for_function("document.querySelectorAll('.c').length === 3", timeout=6000)
        check("navigateur : mise à jour toute seule (2 s)", pg.locator(".c").count() == 3)
        check("navigateur : texte échappé (pas de HTML injecté)", pg.locator(".c b").count() == 0
              and "<b>x</b>" in pg.locator(".c").nth(2).inner_text())
        check("navigateur : filtre gardé", pg.locator("#flt").input_value() == "Grande scène › Micros")
        if os.environ.get("CAPTURES"):
            pg.screenshot(path=os.path.join(os.environ["CAPTURES"], "page_web.png"), full_page=True)
        w.stop()
        pg.wait_for_function("document.querySelector('#stale').style.display === 'block'", timeout=25000)
        check("navigateur : PC injoignable signalé", pg.locator("#stale").is_visible())
        check("navigateur : aucune erreur JavaScript", not errs, str(errs))
        br.close()
w.stop()
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
