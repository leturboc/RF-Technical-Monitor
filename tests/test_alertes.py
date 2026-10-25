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

tc = ns["telegram_chats"]
upd = {"ok": True, "result": [
    {"update_id": 1, "message": {"chat": {"id": 42, "first_name": "Clément", "type": "private"}, "text": "/start"}},
    {"update_id": 2, "message": {"chat": {"id": -1001234, "title": "Équipe HF", "type": "supergroup"}}},
    {"update_id": 3, "message": {"chat": {"id": 42, "first_name": "Clément"}, "text": "re"}},
    {"update_id": 4, "my_chat_member": {"chat": {"id": -555, "title": "Régie"}}}]}
check("telegram : chats trouvés, récents d'abord, sans doublon", tc(upd) == [("-555", "Régie"), ("42", "Clément"),
                                                                            ("-1001234", "Équipe HF")], str(tc(upd)))
check("telegram : réponse vide", tc({"ok": True, "result": []}) == [] and tc(None) == [])
check("tuto : ntfy et Telegram expliqués", "BotFather" in ns["TUTO_ALERTES"] and "ntfy" in ns["TUTO_ALERTES"])

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

# ------------------------------------------------------------- vues, clients, spectre (PURE)
vn = ns["web_views_norm"]
check("vues : toutes par défaut", all(vn(None).values()) and list(vn(None)) == ns["WEB_VIEW_KEYS"])
check("vues : une décochée, inconnue ignorée", vn({"spectre": False, "x": True}) == dict(vn(None), spectre=False))
cb = ns["ClientBook"](online_s=10, keep_s=100)
cb.login("a" * 32, "  Clément   FOH ", "10.0.0.2", "UA", 0.0)
cb.login("b" * 32, "", "10.0.0.3", "UA", 0.0)
cb.touch("a" * 32, "10.0.0.2", "mur", 5.0)
L_ = cb.listing(12.0)
check("clients : nom nettoyé, invité par défaut", [e["name"] for e in L_] == ["Clément FOH", "Invité"], str(L_))
check("clients : jeton dans la liste (pour renommer)", L_[0]["token"] == "a" * 32)
check("clients : en ligne / hors ligne", [e["online"] for e in L_] == [True, False])
check("clients : qui regarde quoi", cb.watching(("mur",), 12.0) and not cb.watching(("spectre",), 12.0))
check("clients : jeton inconnu", cb.touch("c" * 32, "x", "", 1.0) is None)
cb.rename("a" * 32, "  Tablette   1 ")
cb.identify("a" * 32, 12.0)
check("clients : renommer / identifier", cb.c["a" * 32]["name"] == "Tablette 1" and cb.c["a" * 32]["ident"] == 20.0
      and cb.rename("z" * 32, "x") is None)
cb.purge(200.0)
check("clients : oubliés après le délai", cb.listing(200.0) == [])
wsp = ns["web_spectrum"]
import numpy as _np
F_ = _np.linspace(470, 694, 5001)
L_ = -100 + 0 * F_
L_[2500] = -40.0                              # pic étroit
out = wsp([("UHF", F_, L_, L_ + 1)], n_max=900)
check("spectre allégé : 900 points", len(out[0]["f"]) == 900 and len(out[0]["mh"]) == 900)
check("spectre allégé : le pic étroit reste", max(out[0]["l"]) == -40.0)
check("spectre allégé : petit segment intact", len(wsp([("x", F_[:100], L_[:100], None)])[0]["f"]) == 100)

# ------------------------------------------------------------- WebServer
import http.cookiejar
state = {"v": json.dumps(st, ensure_ascii=False).encode("utf-8")}
spec_b = json.dumps(dict(t=1.0, bands=out)).encode()
wcfg = dict(password="", views=vn(None))
w = ns["WebServer"](0, lambda: state["v"], host="127.0.0.1", get_spec=lambda: spec_b, get_cfg=lambda: wcfg)
w.start()
w.ready.wait(3)
check("serveur web démarré", not w.error and w.port > 0, w.error)
base = f"http://127.0.0.1:{w.port}"


def opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def get(op, path):
    try:
        r = op.open(base + path, timeout=5)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post_(op, path, obj, port=None):
    rq = urllib.request.Request(f"http://127.0.0.1:{port or w.port}{path}", data=json.dumps(obj).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = op.open(rq, timeout=5)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


o1 = opener()
code, page = get(o1, "/")
page = page.decode("utf-8")
check("page servie", code == 200 and "<title>TinySA Monitor</title>" in page and "etat.json" in page)
check("page : icône (parabole) en favicon", 'rel="icon" href="data:image/png;base64,iVBOR' in page and "__ICON__" not in page)
check("icône de l'exe présente", all(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", f))
                                     for f in ("icone.ico", "icone.png")))
check("page : vues injectées", '"waterfall":["🌊","Waterfall"' in page and "__VIEWS__" not in page)
code, b_ = get(o1, "/etat.json?v=liste")
js = json.loads(b_)
check("sans mot de passe : état lisible", code == 200 and js["state"]["rows"][0]["name"] == "HF 1" and js["me"] is None)
check("état : vues partagées", js["views"] == ns["WEB_VIEW_KEYS"] and js["password"] is False)
code, r_ = post_(o1, "/connexion", dict(name="Régie", password=""))
check("connexion sans mot de passe : nom enregistré", code == 200 and r_["name"] == "Régie")
code, b_ = get(o1, "/etat.json?v=mur")
check("connecté : « me »", json.loads(b_)["me"] == "Régie")
check("clients : la régie regarde le mur", [(e["name"], e["view"]) for e in w.client_list()] == [("Régie", "mur")])
code, b_ = get(o1, "/spectre.json")
check("spectre servi", code == 200 and json.loads(b_)["bands"][0]["name"] == "UHF")
wcfg["views"] = dict(vn(None), spectre=False, waterfall=False)
check("vues spectre / waterfall coupées → 403", get(o1, "/spectre.json")[0] == 403
      and "spectre" not in json.loads(get(o1, "/etat.json")[1])["views"])
wcfg["views"] = vn(None)
check("chemin inconnu : 404", get(o1, "/../config.json")[0] == 404)
# --- mot de passe
wcfg["password"] = "festival"
o2 = opener()
check("mot de passe : état refusé sans connexion", get(o2, "/etat.json")[0] == 401 and get(o2, "/spectre.json")[0] == 401)
check("mot de passe : faux → 403", post_(o2, "/connexion", dict(name="X", password="nope"))[0] == 403)
check("mot de passe : bon → cookie", post_(o2, "/connexion", dict(name="Plateau", password="festival"))[0] == 200
      and get(o2, "/etat.json")[0] == 200)
check("mot de passe : l'ancienne session reste valable", get(o1, "/etat.json")[0] == 200)
w.revoke_all()
check("déconnecter tout le monde", get(o1, "/etat.json")[0] == 401 and get(o2, "/etat.json")[0] == 401)
o3 = opener()
for _ in range(5):
    post_(o3, "/connexion", dict(name="X", password="bad"))
check("mot de passe : 5 essais faux → bloqué", post_(o3, "/connexion", dict(name="X", password="festival"))[0] == 429)
wcfg["password"] = ""
w.login_guard.bad.clear()
busy = ns["WebServer"](w.port, lambda: b"{}", host="127.0.0.1")
busy.start()
busy.ready.wait(3)
check("port déjà pris : erreur claire", "indisponible" in busy.error, busy.error)

# --- acquitter (code PIN)
acks, pin_ = [], {"v": "4321"}
wa = ns["WebServer"](0, lambda: state["v"], host="127.0.0.1", get_pin=lambda: pin_["v"], on_ack=acks.append,
                     get_spec=lambda: spec_b, get_cfg=lambda: wcfg)
wa.start()
wa.ready.wait(3)
oa = opener()
check("POST sans acquittement branché : 404", post_(o1, "/acquitter", dict(pin="1234", id=1))[0] == 404)
check("acquitter : code faux → 403", post_(oa, "/acquitter", dict(pin="0000", id=7), wa.port)[0] == 403 and not acks)
check("acquitter : bon code → 200", post_(oa, "/acquitter", dict(pin="4321", id=7), wa.port)[0] == 200 and acks == [7])
check("acquitter : tout", post_(oa, "/acquitter", dict(pin="4321", id="all"), wa.port)[0] == 200 and acks[-1] == "all")
check("acquitter : requête bancale → 400", post_(oa, "/acquitter", dict(pin="4321", id="1; rm"), wa.port)[0] == 400
      and post_(oa, "/acquitter", dict(pin="4321", id=True), wa.port)[0] == 400)
for _ in range(5):
    post_(oa, "/acquitter", dict(pin="9999", id=1), wa.port)
check("acquitter : trop d'essais → 429", post_(oa, "/acquitter", dict(pin="4321", id=1), wa.port)[0] == 429)
wa.guard.bad.clear()
pin_["v"] = ""
check("acquitter : code effacé sur le PC → refusé", post_(oa, "/acquitter", dict(pin="4321", id=1), wa.port)[0] == 403)
pin_["v"] = "4321"
check("état : acquittement proposé si code", json.loads(get(oa, "/etat.json".replace("/", "/", 1))[1] if False else
      urllib.request.urlopen(f"http://127.0.0.1:{wa.port}/etat.json", timeout=5).read())["ack"] is True)

# ------------------------------------------------------------- la page dans un vrai navigateur
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright is None:
    print("Playwright absent : rendu de la page non testé")
else:
    CAP = os.environ.get("CAPTURES")
    with sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"            # Chromium préinstallé (conteneur Claude) ; sinon celui de Playwright
        br = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
        errs = []
        pg = br.new_page(viewport=dict(width=390, height=800))
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "/")
        pg.wait_for_selector("#login:not(.hidden)", timeout=5000)
        check("navigateur : 1re visite → demande du nom, sans mot de passe", pg.locator("#lpw").is_hidden())
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_connexion.png"))
        pg.type("#ln", "Clément FO")
        pg.wait_for_timeout(2500)                     # la page se rafraîchit chaque seconde pendant la saisie
        check("connexion : le nom tapé ne s'efface pas", pg.input_value("#ln") == "Clément FO", pg.input_value("#ln"))
        pg.type("#ln", "H")
        pg.click("button[type=submit]")
        pg.wait_for_selector("#app:not(.hidden)", timeout=5000)
        check("navigateur : connecté, nom affiché", "Clément FOH" in pg.locator("#me").inner_text())
        check("navigateur : la régie le voit", any(e["name"] == "Clément FOH" for e in w.client_list()))
        tok_ = next(e["token"] for e in w.client_list() if e["name"] == "Clément FOH")
        w.rename(tok_, "Tablette FOH")
        pg.wait_for_function("document.querySelector('#me').textContent.includes('Tablette FOH')", timeout=4000)
        check("renommé depuis le PC : la page suit", "Tablette FOH" in pg.locator("#me").inner_text()
              and pg.evaluate("localStorage.getItem('name')") == "Tablette FOH")
        w.identify(tok_)
        pg.wait_for_selector("#ident:not(.hidden)", timeout=4000)
        check("identifier : l'écran clignote avec son nom", "Tablette FOH" in pg.locator("#ident").inner_text())
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_identifier.png"))
        w.clients.c[tok_]["ident"] = 0
        pg.wait_for_selector("#ident.hidden", state="attached", timeout=4000)
        check("navigateur : accueil avec les 5 vues", pg.locator(".vcard").count() == 5 and pg.locator("nav a").count() == 6,
              f'{pg.locator(".vcard").count()} {pg.locator("nav a").count()}')
        check("navigateur : pastille d'alarme", "1 alarme" in pg.locator("#pill").inner_text())
        check("navigateur : bandeau d'alarme", "ABSENT — HF 2" in pg.locator("#al").inner_text())
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_accueil.png"), full_page=True)
        pg.goto(base + "/#/liste")
        pg.wait_for_selector(".c", timeout=5000)
        cards = pg.locator(".c")
        check("liste : 3 cartes", cards.count() == 3, str(cards.count()))
        check("liste : carte occupée (ton rouge)", "bad" in (cards.nth(0).get_attribute("class") or ""))
        check("liste : carte en alarme", "alarm" in (cards.nth(2).get_attribute("class") or ""))
        pg.select_option("#flt", "Grande scène › Micros")
        pg.wait_for_function("document.querySelectorAll('.c').length === 2", timeout=3000)
        check("liste : filtre par couche", pg.locator(".c").count() == 2)
        pg.fill("#q", "HF 2")
        pg.wait_for_function("document.querySelectorAll('.c').length === 1", timeout=3000)
        check("liste : recherche", pg.locator(".c").count() == 1)
        pg.fill("#q", "")
        rows.append(dict(name="<b>x</b>", freq=600.0, level=-90.0, state="weak", status="", scene="Grande scène",
                         group="Micros", absent=False, conflict=False))
        state["v"] = json.dumps(ws(rows, al, dict(title="T", time="12:00:02", running=False, cycle="", thr=-80.0)),
                                ensure_ascii=False).encode("utf-8")
        pg.wait_for_function("document.querySelectorAll('.c').length === 3", timeout=6000)
        check("liste : mise à jour toute seule", pg.locator(".c").count() == 3)
        check("liste : texte échappé (pas de HTML injecté)", pg.locator(".c b").count() == 0
              and "<b>x</b>" in pg.locator(".c").nth(2).inner_text())
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_liste.png"), full_page=True)
        pg.goto(base + "/#/mur")
        pg.wait_for_selector(".t", timeout=5000)
        check("mur : tuiles", pg.locator(".t").count() >= 3)
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_mur.png"))
        pg.goto(base + "/#/spectre")
        pg.wait_for_function("document.querySelector('#lg') && document.querySelector('#lg').textContent.includes('direct')",
                             timeout=6000)
        nonblank = pg.evaluate("""() => {const c=document.querySelector('#cv'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let n=0;for(let i=0;i<d.length;i+=4){if(d[i]>200&&d[i+1]>120&&d[i+2]<80)n++}return n}""")
        check("spectre : courbe orange dessinée", nonblank > 200, str(nonblank))
        pg.mouse.move(200, 330)
        check("spectre : lecture au doigt (MHz · dBm)", "MHz" in pg.locator("#rd").inner_text())
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_spectre.png"))
        pg.goto(base + "/#/waterfall")
        for k in range(4):
            spec_b = json.dumps(dict(t=2.0 + k, bands=out)).encode()
            pg.wait_for_timeout(1100)
        rowsn = pg.evaluate("() => (typeof wf !== 'undefined' && wf ? wf.n : -1)")
        check("waterfall : une ligne par nouveau balayage", isinstance(rowsn, int) and rowsn >= 2, str(rowsn))
        if CAP:
            pg.screenshot(path=os.path.join(CAP, "web_waterfall.png"))
        pg.goto(base + "/#/alarmes")
        pg.wait_for_selector(".alist .row", timeout=5000)
        check("alarmes : liste, pas de bouton sans code PIN", pg.locator(".alist .row").count() == 1
              and pg.locator(".ackbtn").count() == 0)
        w.stop()
        pg.wait_for_function("document.querySelector('#stale').style.display === 'block'", timeout=25000)
        check("navigateur : PC injoignable signalé", pg.locator("#stale").is_visible())
        pg.close()
        # --- acquitter depuis la vue Alarmes (serveur avec code PIN)
        st_ack = ws(rows, al, dict(title="T", time="12:00:04", running=True, cycle="", thr=-80.0))
        st_ack["alarms"][0]["id"] = 7
        state["v"] = json.dumps(st_ack, ensure_ascii=False).encode("utf-8")
        pa = br.new_page(viewport=dict(width=390, height=800))
        pa.on("pageerror", lambda e: errs.append(str(e)))
        pa.add_init_script("localStorage.setItem('name','Plateau')")
        prompts = []
        pa.on("dialog", lambda d: (prompts.append(d.type), d.accept("4321") if d.type == "prompt" else d.accept()))
        pa.goto(f"http://127.0.0.1:{wa.port}/#/alarmes")
        pa.wait_for_selector(".ackbtn", timeout=5000)
        n0 = len(acks)
        pa.click(".ackbtn")
        t0 = time.time()
        while len(acks) == n0 and time.time() - t0 < 5:
            time.sleep(0.05)
        check("acquitter : code demandé puis envoyé", prompts == ["prompt"] and acks[-1] == 7, f"{prompts} {acks}")
        pa.click(".ackbtn")
        t0 = time.time()
        while len(acks) == n0 + 1 and time.time() - t0 < 5:
            time.sleep(0.05)
        check("acquitter : code retenu (pas redemandé)", prompts == ["prompt"] and len(acks) == n0 + 2, f"{prompts} {acks}")
        check("nom retenu : connecté sans redemander", any(e["name"] == "Plateau" for e in wa.client_list()))
        if CAP:
            pa.screenshot(path=os.path.join(CAP, "web_alarmes.png"))
        # --- grand écran (tablette / PC de la régie)
        pt = br.new_page(viewport=dict(width=1280, height=760))
        pt.on("pageerror", lambda e: errs.append(str(e)))
        pt.add_init_script("localStorage.setItem('name','Régie')")
        pt.goto(f"http://127.0.0.1:{wa.port}/#/spectre")
        pt.wait_for_timeout(2500)
        if CAP:
            pt.screenshot(path=os.path.join(CAP, "web_spectre_large.png"))
        pt.goto(f"http://127.0.0.1:{wa.port}/#/")
        pt.wait_for_timeout(1500)
        if CAP:
            pt.screenshot(path=os.path.join(CAP, "web_accueil_large.png"))
        # --- avec mot de passe
        wcfg["password"] = "festival"
        wa.revoke_all()
        pp = br.new_page(viewport=dict(width=390, height=800))
        pp.on("pageerror", lambda e: errs.append(str(e)))
        pp.goto(f"http://127.0.0.1:{wa.port}/")
        pp.wait_for_selector("#login:not(.hidden)", timeout=5000)
        check("mot de passe : champ affiché", pp.locator("#lpw").is_visible())
        pp.fill("#ln", "Plateau")
        pp.fill("#lp", "faux")
        pp.click("button[type=submit]")
        pp.wait_for_function("document.querySelector('#le').textContent.length > 0", timeout=3000)
        check("mot de passe : faux → message", "incorrect" in pp.locator("#le").inner_text())
        pp.fill("#lp", "festival")
        pp.click("button[type=submit]")
        pp.wait_for_selector("#app:not(.hidden)", timeout=5000)
        check("mot de passe : bon → entré", pp.locator("#app").is_visible())
        wcfg["password"] = ""
        check("navigateur : aucune erreur JavaScript", not errs, str(errs))
        br.close()
w.stop()
wa.stop()
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
