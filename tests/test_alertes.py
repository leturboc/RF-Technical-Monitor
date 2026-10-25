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
exec("import bisect, csv, io, itertools, json, math, os, queue, re, threading, time, unicodedata, urllib.request\n"
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
st2 = ws([dict(rows[0], sig_txt="OK", tone="ok")], [], dict(title="T", time="t", running=True, cycle=""))
check("état web : texte et ton selon le statut", (st2["rows"][0]["state_txt"], st2["rows"][0]["tone"]) == ("OK", "ok"))
check("état web : 3 fréquences", len(st["rows"]) == 3 and st["rows"][0]["level"] == -60.0)
check("état web : états lisibles", [r["state_txt"] for r in st["rows"]] == ["OCCUPÉ", "—", "libre"])
check("état web : ABSENT marqué", st["rows"][2]["alarm"] == "ABSENT")
check("état web : seulement les alarmes en cours", [x["kind"] for x in st["alarms"]] == ["ABSENT"])
check("état web : sérialisable", json.loads(json.dumps(st))["title"] == "T")

# ------------------------------------------------------------- code PIN
pg_ = ns["PinGuard"](tries=3, lock_s=60.0)
check("PIN : pas de code = désactivé", pg_.check("", "1234", "a", 0.0) == "off" and pg_.check("12", "12", "a", 0.0) == "off")
check("PIN : bon code", pg_.check("1234", "1234", "a", 0.0) == "ok")
check("PIN : code faux", pg_.check("1234", "1235", "a", 0.0) == "bad" and pg_.check("1234", "12345", "a", 0.0) == "bad")
check("PIN : 3ᵉ erreur → bloqué, même avec le bon code", pg_.check("1234", "", "a", 1.0) == "locked"
      and pg_.check("1234", "1234", "a", 30.0) == "locked")
check("PIN : une autre adresse n'est pas bloquée", pg_.check("1234", "1234", "b", 30.0) == "ok")
check("PIN : débloqué après le délai", pg_.check("1234", "1234", "a", 62.0) == "ok")
check("état web : id des alarmes", st["alarms"][0]["id"] == 0 and "ack" not in st)

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
def post(port, obj, raw=None):
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/acquitter", data=raw if raw is not None else json.dumps(obj).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(rq, timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code


check("POST sans acquittement branché : 404", post(w.port, dict(pin="1234", id=1)) == 404)
acks, pin_ = [], {"v": "4321"}
wa = ns["WebServer"](0, lambda: state["v"], host="127.0.0.1", get_pin=lambda: pin_["v"], on_ack=acks.append)
wa.start()
wa.ready.wait(3)
check("acquitter : code faux → 403", post(wa.port, dict(pin="0000", id=7)) == 403 and not acks)
check("acquitter : bon code → 200", post(wa.port, dict(pin="4321", id=7)) == 200 and acks == [7], str(acks))
check("acquitter : tout", post(wa.port, dict(pin="4321", id="all")) == 200 and acks[-1] == "all")
check("acquitter : requête bancale → 400", post(wa.port, None, raw=b"{pas du json") == 400
      and post(wa.port, dict(pin="4321", id="1; rm")) == 400 and post(wa.port, dict(pin="4321", id=True)) == 400)
for _ in range(5):                  # 5 codes faux de suite
    post(wa.port, dict(pin="9999", id=1))
check("acquitter : trop d'essais → 429", post(wa.port, dict(pin="4321", id=1)) == 429)
wa.guard.bad.clear()
pin_["v"] = ""
check("acquitter : code effacé sur le PC → refusé", post(wa.port, dict(pin="4321", id=1)) == 403)
pin_["v"] = "4321"
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
        check("navigateur : carte occupée (ton rouge)", "bad" in (cards.nth(0).get_attribute("class") or ""))
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
        # acquitter depuis le téléphone : bouton visible seulement si un code est réglé sur le PC
        check("navigateur : pas de bouton sans code", pg.locator(".al button").count() == 0)
        st_ack = ws(rows, al, dict(title="T", time="12:00:04", running=True, cycle="", ack=True))
        st_ack["alarms"][0]["id"] = 7
        state["v"] = json.dumps(st_ack, ensure_ascii=False).encode("utf-8")
        pa = br.new_page(viewport=dict(width=390, height=800))
        pa.on("pageerror", lambda e: errs.append(str(e)))
        prompts = []
        pa.on("dialog", lambda d: (prompts.append(d.type), d.accept("4321") if d.type == "prompt" else d.accept()))
        pa.goto(f"http://127.0.0.1:{wa.port}/")
        pa.wait_for_selector(".al button", timeout=5000)
        n0 = len(acks)
        pa.click(".al button")
        pa.wait_for_function("1", timeout=1000)
        t0 = time.time()
        while len(acks) == n0 and time.time() - t0 < 5:
            time.sleep(0.05)
        check("navigateur : Acquitter → code demandé puis envoyé", prompts == ["prompt"] and acks[-1] == 7, f"{prompts} {acks}")
        pa.click(".al button")
        t0 = time.time()
        while len(acks) == n0 + 1 and time.time() - t0 < 5:
            time.sleep(0.05)
        check("navigateur : code retenu (pas redemandé)", prompts == ["prompt"] and len(acks) == n0 + 2, f"{prompts} {acks}")
        if os.environ.get("CAPTURES"):
            pa.screenshot(path=os.path.join(os.environ["CAPTURES"], "page_web_acquitter.png"), full_page=True)
        pa.close()
        w.stop()
        pg.wait_for_function("document.querySelector('#stale').style.display === 'block'", timeout=25000)
        check("navigateur : PC injoignable signalé", pg.locator("#stale").is_visible())
        check("navigateur : aucune erreur JavaScript", not errs, str(errs))
        br.close()
w.stop()
wa.stop()
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
