# Alertes (ntfy / Telegram), page web et son serveur, fenêtre Alertes, fenêtre du relais.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class Notifier:
    """Envoie les alertes sur téléphone sans jamais bloquer l'appli : file d'attente + fil séparé, 3 essais."""

    def __init__(self, sender=None, retry_s=3.0):
        self.q = queue.Queue(maxsize=50)
        self.sender = sender or self._http
        self.retry_s = retry_s
        self.last_error, self.sent = "", 0
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def _http(url, hdr, data):
        req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()

    def post(self, req):
        try:
            self.q.put_nowait(req)
        except queue.Full:
            self.last_error = "trop d'alertes en attente (pas de réseau ?)"

    def _run(self):
        while True:
            req = self.q.get()
            for k in range(3):
                try:
                    self.sender(*req)
                    self.sent += 1
                    self.last_error = ""
                    break
                except Exception as e:  # noqa: BLE001
                    self.last_error = str(e)
                    time.sleep(self.retry_s * (k + 1))


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"     # Windows : sinon un port déjà pris « marche » quand même
    daemon_threads = True


class WebServer(threading.Thread):
    """Page web de l'équipe (façon Ontime : une adresse, plusieurs vues).
    GET  « / » page · « /etat.json » état (+ qui je suis, vues partagées) · « /spectre.json » spectre allégé
    POST « /connexion » {name, password} → cookie de session · « /acquitter » {pin, id | "all"}.
    get_cfg() -> {password, views} (lu à chaque requête : les réglages du PC s'appliquent tout de suite).
    Sans mot de passe tout le monde entre ; avec, il faut s'être connecté (5 essais faux → bloqué 1 min)."""

    COOKIE = "tsm"

    def __init__(self, port, get_json, host="0.0.0.0", get_pin=None, on_ack=None, get_spec=None, get_cfg=None,
                 get_page=None, default_lang="fr", on_hunt=None, on_terrain=None, on_tech=None, on_tech_req=None,
                 get_tech=None, get_map=None, extra_get=None, extra_pin=None):
        super().__init__(daemon=True)
        # 7.68 : routes ajoutées par une autre version (V8 : 🎧 écoute sur le téléphone) sans toucher à ce code :
        # extra_get {chemin: (vues dont une doit être partagée, fn(query) -> (octets, type) ou None)},
        # extra_pin {chemin: (lecture de la requête, rappel)} = routes POST protégées par le code PIN.
        self.extra_get, self.extra_pin = dict(extra_get or {}), dict(extra_pin or {})
        self.get_map = get_map or (lambda: b"")      # 🗺 7.64 : image de la carte pour « je suis ici »
        self.port, self.host, self.get_json = int(port), host, get_json
        # langue de CHAQUE personne : get_json(lang) / get_page(lang) si fournis (sinon une seule langue)
        self.get_page = get_page or (lambda lang: WEB_PAGE.encode("utf-8"))
        self.default_lang = default_lang if default_lang in ("fr", "en") else "fr"
        self.get_pin, self.on_ack = get_pin or (lambda: ""), on_ack
        self.on_hunt = on_hunt                     # 🔎 chasse lancée / arrêtée depuis un téléphone (code PIN)
        self.on_terrain = on_terrain               # 🎒 tinySA volant : scènes, scans gardés (code PIN)
        self.on_tech, self.on_tech_req = on_tech, on_tech_req   # 🛠 commandes Tech, demandes d'accès à valider
        self.get_tech = get_tech or (lambda: b"{}")
        self.tech_guard = PinGuard(tries=5, lock_s=300.0)       # mot de passe Tech : 5 essais puis 5 min
        self.get_spec = get_spec or (lambda: b'{"bands":[]}')
        self.get_cfg = get_cfg or (lambda: {})
        self.guard, self.login_guard, self._lock = PinGuard(), PinGuard(), threading.Lock()
        self.clients = ClientBook()
        self.httpd, self.error = None, ""
        self.ready = threading.Event()

    def cfg(self):
        c = dict(self.get_cfg() or {})
        return dict(password=str(c.get("password", "") or ""), views=web_views_norm(c.get("views")),
                    tech=str(c.get("tech", "") or ""), tech_approve=bool(c.get("tech_approve", True)))

    def tech_decide(self, token, ok):
        """Réponse du PC à une demande d'accès Tech."""
        with self._lock:
            return self.clients.set_tech(token, "ok" if ok else None, time.time()) is not None

    def revoke_tech(self, token=None):
        """Retire l'accès Tech d'un navigateur (ou de tous)."""
        with self._lock:
            for t in ([token] if token else list(self.clients.c)):
                self.clients.set_tech(t, None, time.time())

    def client_list(self):
        with self._lock:
            return self.clients.listing(time.time())

    def watching(self, views):
        with self._lock:
            return self.clients.watching(views, time.time())

    def revoke_all(self):
        with self._lock:
            self.clients.revoke_all()

    def rename(self, token, name):
        with self._lock:
            return self.clients.rename(token, name) is not None

    def identify(self, token):
        with self._lock:
            return self.clients.identify(token, time.time()) is not None

    def run(self):
        owner = self

        class H(BaseHTTPRequestHandler):
            def _send(self, code, body, ctype, extra=()):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj, extra=()):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8", extra)

            def _token(self):
                for part in (self.headers.get("Cookie") or "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == owner.COOKIE and re.fullmatch(r"[0-9a-f]{32}", v or ""):
                        return v
                return ""

            def _who(self, view=""):
                """-> (autorisé, entrée du client ou None)."""
                tok, cfg = self._token(), owner.cfg()
                with owner._lock:
                    e = owner.clients.touch(tok, self.client_address[0], view, time.time()) if tok else None
                    e = dict(e) if e else None
                return (e is not None or not cfg["password"]), e

            def _tech(self):
                tok = self._token()
                with owner._lock:
                    return owner.clients.tech_state(tok, time.time()) if tok else None

            def _body(self):
                n = int(self.headers.get("Content-Length", 0) or 0)
                req = json.loads(self.rfile.read(min(max(n, 0), 4096)).decode("utf-8")) if n > 0 else {}
                if not isinstance(req, dict):
                    raise ValueError
                return req

            def _lang(self, qs):
                """Langue de la personne : ?lang= (retenu en cookie), cookie, sinon langue du téléphone."""
                q = next((v for k, _, v in (p.partition("=") for p in qs.split("&")) if k == "lang"), "")
                if q in ("fr", "en"):
                    return q, True
                for part in (self.headers.get("Cookie") or "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == "tsm_lang" and v in ("fr", "en"):
                        return v, False
                al = (self.headers.get("Accept-Language") or "").strip().lower()
                if al:
                    return ("fr" if al.startswith("fr") else "en"), False
                return owner.default_lang, False

            def _state(self, lang):
                try:
                    return owner.get_json(lang)
                except TypeError:                   # get_json sans langue (une seule langue)
                    return owner.get_json()

            def do_GET(self):
                path, _, qs = self.path.partition("?")
                view = next((v for k, _, v in (p.partition("=") for p in qs.split("&")) if k == "v"), "")
                view = view if view in WEB_VIEW_KEYS else ""
                lang, chosen = self._lang(qs)
                if path in ("/", "/index.html"):
                    extra = [("Set-Cookie", f"tsm_lang={lang}; Path=/; SameSite=Strict; Max-Age=31536000")] \
                        if chosen else []
                    self._send(200, owner.get_page(lang), "text/html; charset=utf-8", extra)
                    return
                if path not in ("/etat.json", "/spectre.json", "/tech.json", "/carte.png") and path not in owner.extra_get:
                    self.send_error(404)
                    return
                ok, me = self._who(view)
                cfg = owner.cfg()
                if not ok:
                    self._json(401, dict(login=True, password=True))
                    return
                if path == "/tech.json":
                    st = self._tech()
                    if not cfg["views"]["tech"] or len(cfg["tech"]) < 6:
                        self._json(403, dict(off=True))
                    elif st == "ok":
                        self._send(200, owner.get_tech(), "application/json; charset=utf-8")
                    else:
                        self._json(200 if st == "pending" else 403, dict(pending=st == "pending", login=st is None))
                    return
                if path in owner.extra_get:
                    need, fn_ = owner.extra_get[path]
                    res_ = fn_(qs) if any(cfg["views"].get(k_) for k_ in need) else None
                    if not res_:
                        self.send_error(404)
                        return
                    self._send(200, res_[0], res_[1])
                    return
                if path == "/carte.png":
                    data = owner.get_map() if (cfg["views"]["chasse"] or cfg["views"]["terrain"]) else b""
                    if not data:
                        self.send_error(404)
                        return
                    self._send(200, data, "image/png")
                    return
                if path == "/spectre.json":
                    if not (cfg["views"]["spectre"] or cfg["views"]["waterfall"]):
                        self._json(403, dict(error="vue non partagée"))
                        return
                    self._send(200, owner.get_spec(), "application/json; charset=utf-8")
                    return
                head = dict(me=None if me is None else me["name"], password=bool(cfg["password"]),
                            ident=bool(me and me.get("ident", 0) > time.time()),
                            views=[k for k in WEB_VIEW_KEYS if cfg["views"][k]],
                            ack=len(str(owner.get_pin() or "").strip()) >= 4)
                body = (json.dumps(head, ensure_ascii=False)[:-1] + ',"state":').encode("utf-8") + self._state(lang) + b"}"
                self._send(200, body, "application/json; charset=utf-8")

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                if path == "/connexion":
                    try:
                        req = self._body()
                    except (ValueError, UnicodeDecodeError):
                        self._json(400, dict(error="requête invalide"))
                        return
                    pw = owner.cfg()["password"]
                    if pw:
                        with owner._lock:
                            res = owner.login_guard.check(pw, req.get("password"), self.client_address[0], time.time())
                        if res != "ok":
                            self._json(429 if res == "locked" else 403, dict(error=res))
                            return
                    tok = os.urandom(16).hex()
                    with owner._lock:
                        e = owner.clients.login(tok, req.get("name"), self.client_address[0],
                                                self.headers.get("User-Agent", ""), time.time())
                        name = e["name"]
                    self._json(200, dict(ok=True, name=name), [(
                        "Set-Cookie", f"{owner.COOKIE}={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200")])
                    return
                if path == "/renommer":
                    tok = self._token()
                    try:
                        req = self._body()
                    except (ValueError, UnicodeDecodeError):
                        self._json(400, dict(error="requête invalide"))
                        return
                    with owner._lock:
                        e = owner.clients.rename(tok, req.get("name")) if tok else None
                        name = e["name"] if e else None
                    if name is None:
                        self._json(401, dict(login=True))
                        return
                    self._json(200, dict(ok=True, name=name))
                    return
                if path in ("/tech/login", "/tech/logout", "/tech"):
                    self._tech_post(path)
                    return
                pin_routes = {"/chasse": (hunt_request, owner.on_hunt), "/terrain": (terrain_request, owner.on_terrain)}
                pin_routes.update(owner.extra_pin)
                if path in pin_routes and pin_routes[path][1] is not None:
                    parse_, cb_ = pin_routes[path]
                    ok, _me = self._who()
                    if not ok:
                        self._json(401, dict(login=True))
                        return
                    try:
                        req = self._body()
                        cmd = parse_(req)
                    except (ValueError, AttributeError, TypeError, UnicodeDecodeError):
                        self._json(400, dict(error="requête invalide"))
                        return
                    with owner._lock:
                        res = owner.guard.check(owner.get_pin(), req.get("pin"), self.client_address[0], time.time())
                    if res != "ok":
                        self._json(429 if res == "locked" else 403, dict(error=res))
                        return
                    cb_(cmd)
                    self._json(200, dict(ok=True))
                    return
                if path != "/acquitter" or owner.on_ack is None:
                    self.send_error(404)
                    return
                ok, _me = self._who()
                if not ok:
                    self._json(401, dict(login=True))
                    return
                try:
                    req = self._body()
                    target = req.get("id")
                    if not (target == "all" or (isinstance(target, int) and not isinstance(target, bool))):
                        raise ValueError
                except (ValueError, AttributeError, UnicodeDecodeError):
                    self._json(400, dict(error="requête invalide"))
                    return
                with owner._lock:
                    res = owner.guard.check(owner.get_pin(), req.get("pin"), self.client_address[0], time.time())
                if res != "ok":
                    self._json(429 if res == "locked" else 403, dict(error=res))
                    return
                owner.on_ack(target)
                self._json(200, dict(ok=True))

            def _tech_post(self, path):
                """🛠 Accès Tech : mot de passe Tech (≥ 6 caractères, séparé de celui de la page) PUIS, si coché sur le
                PC, accord donné sur le PC pour chaque nouveau navigateur. Accès valable 12 h, retirable du PC."""
                cfg = owner.cfg()
                tok = self._token()
                ok, me = self._who()
                if not ok or me is None or not tok:
                    self._json(401, dict(login=True))
                    return
                if not cfg["views"]["tech"] or len(cfg["tech"]) < 6:
                    self._json(403, dict(error="off"))
                    return
                try:
                    req = self._body()
                except (ValueError, UnicodeDecodeError):
                    self._json(400, dict(error="requête invalide"))
                    return
                now = time.time()
                if path == "/tech/logout":
                    with owner._lock:
                        owner.clients.set_tech(tok, None, now)
                    self._json(200, dict(ok=True))
                    return
                if path == "/tech/login":
                    with owner._lock:
                        res = owner.tech_guard.check(cfg["tech"], req.get("password"), self.client_address[0], now)
                    if res != "ok":
                        self._json(429 if res == "locked" else 403, dict(error=res))
                        return
                    state = "pending" if cfg["tech_approve"] else "ok"
                    with owner._lock:
                        owner.clients.set_tech(tok, state, now)
                    if state == "pending" and owner.on_tech_req is not None:
                        owner.on_tech_req(dict(token=tok, name=me["name"], addr=self.client_address[0]))
                    self._json(200, dict(state=state))
                    return
                if self._tech() != "ok" or owner.on_tech is None:
                    self._json(403, dict(error="tech"))
                    return
                try:
                    cmd = tech_request(req)
                except (ValueError, TypeError, OverflowError):
                    self._json(400, dict(error="requête invalide"))
                    return
                cmd["by"] = me["name"]
                owner.on_tech(cmd)
                self._json(200, dict(ok=True))

            def log_message(self, *a):
                pass

        try:
            self.httpd = _HTTPServer((self.host, self.port), H)
            self.port = self.httpd.server_address[1]
        except OSError as e:
            self.error = f"Port {self.port} indisponible : {e}"
            self.ready.set()
            return
        self.ready.set()
        self.httpd.serve_forever(poll_interval=0.3)

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()


def fit_dialog(dlg, w, h):
    """Taille d'une fenêtre bornée à l'écran (barre des tâches comprise) : jamais plus grande que la place dispo."""
    try:
        scr = (dlg.parentWidget().screen() if dlg.parentWidget() else None) or QtWidgets.QApplication.primaryScreen()
        g = scr.availableGeometry()
        dlg.resize(min(w, g.width() - 40), min(h, g.height() - 60))
    except Exception:  # noqa: BLE001
        dlg.resize(w, h)


class AlertsDialog(QtWidgets.QDialog):
    """Réglages : alertes sur téléphone (ntfy / Telegram) et page web en lecture seule."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Alertes téléphone et page web")
        self.resize(580, 680)
        n, w = owner.notify_cfg, owner.web_cfg
        nb = QtWidgets.QGroupBox("📣 Alertes sur téléphone")
        nf = QtWidgets.QFormLayout(nb)
        self.mode = QtWidgets.QComboBox()
        for k, t in NOTIFY_MODES:
            self.mode.addItem(t, k)
        self.mode.setCurrentIndex(max(0, self.mode.findData(n["mode"])))
        self.service = QtWidgets.QComboBox()
        self.service.addItem("ntfy (appli gratuite, sans compte)", "ntfy")
        self.service.addItem("Telegram (bot)", "telegram")
        self.service.setCurrentIndex(max(0, self.service.findData(n["service"])))
        self.server = QtWidgets.QLineEdit(n["server"])
        self.topic = QtWidgets.QLineEdit(n["topic"] or f"tinysa-{os.urandom(4).hex()}")
        self.topic.setToolTip("Nom du « canal » ntfy : choisis-le long et difficile à deviner (toute personne qui le\n"
                              "connaît peut lire les alertes). Abonne-toi au même nom dans l'appli ntfy du téléphone.")
        self.tg_token = QtWidgets.QLineEdit(n["tg_token"])
        self.tg_token.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.tg_chat = QtWidgets.QLineEdit(n["tg_chat"])
        self.site = QtWidgets.QLineEdit(n["site"])
        self.site.setPlaceholderText("ex. Festival X — Grande scène")
        test = QtWidgets.QPushButton("Envoyer une alerte de test")
        test.setToolTip("Envoie une alerte d'essai avec les réglages ci-dessus (sans les enregistrer).")
        test.clicked.connect(lambda *_: self.send_test())
        tuto = QtWidgets.QPushButton("📖 Tuto pas à pas")
        tuto.setToolTip("Comment installer ntfy ou créer un bot Telegram, étape par étape.")
        tuto.clicked.connect(lambda *_: self.show_tuto())
        self.find_chat = QtWidgets.QPushButton("🔎 Trouver mon chat id")
        self.find_chat.setToolTip("Après avoir écrit un message à ton bot (ou dans le groupe où il est) : demande à\n"
                                  "Telegram qui lui a écrit et remplit le chat id.")
        self.find_chat.clicked.connect(lambda *_: self.fetch_chat_id())
        self.n_lbl = QtWidgets.QLabel("")
        self.n_lbl.setWordWrap(True)
        help_n = QtWidgets.QLabel(
            "<b>ntfy</b> : installe l'appli ntfy (iOS / Android), « S'abonner » au nom de canal ci-dessous. "
            "<b>Telegram</b> : crée un bot avec @BotFather (jeton), écris-lui un message, puis récupère ton "
            "identifiant de discussion (chat id). Il faut une connexion Internet (4G, wifi du site…). "
            "Détails : « 📖 Tuto pas à pas ».")
        help_n.setWordWrap(True)
        nf.addRow(help_n)
        nf.addRow(tuto)
        nf.addRow("Envoyer :", self.mode)
        nf.addRow("Service :", self.service)
        nf.addRow("Serveur ntfy :", self.server)
        nf.addRow("Canal ntfy :", self.topic)
        nf.addRow("Jeton du bot :", self.tg_token)
        chat_row = QtWidgets.QHBoxLayout()
        chat_row.addWidget(self.tg_chat, 1)
        chat_row.addWidget(self.find_chat)
        nf.addRow("Chat id :", chat_row)
        nf.addRow("Nom du site :", self.site)
        self.n_lang = QtWidgets.QComboBox()
        for lab_, k_ in (("comme l'appli", "app"), ("Français", "fr"), ("English", "en")):
            self.n_lang.addItem(lab_, k_)
        self.n_lang.setCurrentIndex(max(0, self.n_lang.findData(n.get("lang", "app"))))
        self.n_lang.setToolTip("Langue des alertes envoyées sur les téléphones (indépendante de la langue de l'appli).")
        nf.addRow("Langue des alertes :", self.n_lang)
        nf.addRow(test)
        nf.addRow(self.n_lbl)
        self.service.currentIndexChanged.connect(lambda *_: self._svc())
        wb = QtWidgets.QGroupBox("🌐 Page web pour l'équipe (réseau local)")
        wf = QtWidgets.QFormLayout(wb)
        self.web_on = QtWidgets.QCheckBox("Activer la page web")
        self.web_on.setChecked(bool(w["on"]))
        self.web_port = QtWidgets.QSpinBox()
        self.web_port.setRange(1024, 65535)
        self.web_port.setValue(int(w["port"]))
        self.web_pw = QtWidgets.QLineEdit(str(w.get("password", "")))
        self.web_pw.setPlaceholderText("vide = ouvert à tout le réseau")
        self.web_pw.setMaxLength(40)
        self.web_pw.setToolTip("Mot de passe demandé pour ouvrir la page (en plus du nom de la personne).\n"
                               "Le changer déconnecte tout le monde.")
        self.web_tech = QtWidgets.QLineEdit(str(w.get("tech", "")))
        self.web_tech.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.web_tech.setPlaceholderText("6 caractères ou plus · vide = pas de page Tech")
        self.web_tech.setMaxLength(40)
        self.web_tech.setToolTip("Mot de passe de la page 🛠 Tech (gérer le serveur depuis un téléphone : démarrer,\n"
                                 "seuils, fréquences, tinySA). Différent du mot de passe de la page, à ne donner qu'à\n"
                                 "l'équipe HF. 5 essais faux → bloqué 5 min. Accès valable 12 h.")
        self.web_tech_ok = QtWidgets.QCheckBox("Valider chaque nouvel appareil sur ce PC")
        self.web_tech_ok.setChecked(bool(w.get("tech_approve", True)))
        self.web_tech_ok.setToolTip("Coché (conseillé) : même avec le bon mot de passe, un téléphone n'a l'accès Tech\n"
                                    "qu'après ton accord sur ce PC (une fenêtre te le demande).")
        self.view_chks = {}
        vbox = QtWidgets.QWidget()
        vfl = FlowLayout(vbox)
        cur_v = web_views_norm(w.get("views"))
        for k, ic, t, d in WEB_VIEWS:
            cb = QtWidgets.QCheckBox(f"{ic} {t}")
            cb.setChecked(cur_v[k])
            cb.setToolTip(d + "\nDécoché : la vue n'apparaît pas sur la page.")
            self.view_chks[k] = cb
            vfl.addWidget(cb)
        self.clients = QtWidgets.QListWidget()
        self.clients.setMaximumHeight(110)
        self.clients.setToolTip("Les personnes qui ont la page ouverte (nom choisi, adresse, vue regardée).\n"
                                "Clic sur une ligne, puis « Renommer » ou « Identifier ».")
        self._sel_tok = None
        self.clients.itemSelectionChanged.connect(self._remember_sel)
        self.ren_btn = QtWidgets.QPushButton("✏ Renommer…")
        self.ren_btn.setToolTip("Change le nom du client choisi (il le voit tout de suite sur sa page).")
        self.ren_btn.clicked.connect(lambda *_: self.rename_client())
        self.id_btn = QtWidgets.QPushButton("👋 Identifier")
        self.id_btn.setToolTip("Fait clignoter l'écran du client choisi pendant 8 s : pratique pour savoir quelle\n"
                               "tablette / quel téléphone est lequel.")
        self.id_btn.clicked.connect(lambda *_: self.identify_client())
        self.untech_btn = QtWidgets.QPushButton("🛠 Retirer l'accès Tech")
        self.untech_btn.setToolTip("Retire l'accès Tech du client choisi (il garde la page en lecture).")
        self.untech_btn.clicked.connect(lambda *_: self.untech_client())
        self.kick_btn = QtWidgets.QPushButton("Déconnecter tout le monde")
        self.kick_btn.setToolTip("Oublie toutes les connexions : avec un mot de passe, chacun doit se reconnecter.")
        self.kick_btn.clicked.connect(lambda *_: (owner.web.revoke_all() if owner.web is not None else None,
                                                  self.refresh_clients()))
        self._ct = QtCore.QTimer(self)
        self._ct.timeout.connect(self.refresh_clients)
        self._ct.start(2000)
        self.web_pin = QtWidgets.QLineEdit(str(w.get("pin", "")))
        self.web_pin.setPlaceholderText("vide = lecture seule")
        self.web_pin.setMaxLength(12)
        self.web_pin.setToolTip("Code (4 caractères ou plus) demandé sur le téléphone pour acquitter une alarme.\n"
                                "Vide : la page reste en lecture seule. 5 codes faux → l'adresse est bloquée 1 min.")
        self.w_lbl = QtWidgets.QLabel("")
        self.w_lbl.setWordWrap(True)
        self.qr_btn = QtWidgets.QPushButton("📱 QR code…")
        self.qr_btn.setToolTip("Un QR code à scanner avec le téléphone : la page s'ouvre directement.")
        self.qr_btn.clicked.connect(lambda *_: owner.open_qr())
        self.w_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        help_w = QtWidgets.QLabel("Sur un téléphone ou un PC du même réseau, ouvre l'adresse affichée : état des "
                                  "fréquences et alarmes, filtre par scène / groupe, rafraîchi chaque seconde. "
                                  "Vues au choix (liste, mur, spectre, waterfall, alarmes) ; chacun entre son nom, tu "
                                  "vois qui est connecté. Mot de passe pour fermer l'accès, code PIN pour pouvoir "
                                  "acquitter depuis le téléphone. Tout passe en clair sur le réseau : à n'activer que "
                                  "sur un réseau de confiance (réseau de prod, pas le Wi-Fi public).")
        help_w.setWordWrap(True)
        wf.addRow(help_w)
        wf.addRow(self.web_on)
        wf.addRow("Port :", self.web_port)
        wf.addRow("Mot de passe :", self.web_pw)
        wf.addRow("Code PIN (acquitter) :", self.web_pin)
        wf.addRow("🛠 Mot de passe Tech :", self.web_tech)
        wf.addRow("", self.web_tech_ok)
        wf.addRow("Vues partagées :", vbox)
        wf.addRow(owner._row(self.w_lbl, self.qr_btn))
        wf.addRow("Connectés :", self.clients)
        cr = QtWidgets.QHBoxLayout()
        for b_ in (self.ren_btn, self.id_btn, self.untech_btn, self.kick_btn):
            cr.addWidget(b_)
        wf.addRow(cr)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        # contenu dans une zone qui défile, OK / Annuler toujours visibles en bas (Clément 7.52 : sur un écran
        # portable mis à l'échelle, la fenêtre dépassait de l'écran et le bouton OK était caché)
        body = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(nb)
        bl.addWidget(wb)
        bl.addStretch(1)
        sc = QtWidgets.QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setWidget(body)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(sc, 1)
        lay.addWidget(bb)
        fit_dialog(self, 620, 760)
        self._svc()
        self.refresh()

    def _svc(self):
        ntfy = self.service.currentData() == "ntfy"
        for wd in (self.server, self.topic):
            wd.setEnabled(ntfy)
        for wd in (self.tg_token, self.tg_chat, self.find_chat):
            wd.setEnabled(not ntfy)

    def values(self):
        return (dict(mode=self.mode.currentData(), service=self.service.currentData(),
                     server=self.server.text().strip() or "https://ntfy.sh", topic=self.topic.text().strip(),
                     tg_token=self.tg_token.text().strip(), tg_chat=self.tg_chat.text().strip(),
                     site=self.site.text().strip(), lang=self.n_lang.currentData() or "app"),
                dict(on=self.web_on.isChecked(), port=self.web_port.value(), pin=self.web_pin.text().strip(),
                     password=self.web_pw.text(), views={k: c.isChecked() for k, c in self.view_chks.items()},
                     tech=self.web_tech.text(), tech_approve=self.web_tech_ok.isChecked()))

    def show_tuto(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Alertes téléphone : tuto")
        d.resize(640, 620)
        v = QtWidgets.QVBoxLayout(d)
        tb = QtWidgets.QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(TUTO_ALERTES)
        v.addWidget(tb)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        d.exec()

    def fetch_chat_id(self):
        token = self.tg_token.text().strip()
        if not token:
            self.n_lbl.setText("⚠ Colle d'abord le jeton du bot (donné par @BotFather).")
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=8) as r:
                chats = telegram_chats(json.loads(r.read().decode("utf-8")))
        except Exception as e:
            self.n_lbl.setText(f"⚠ Telegram injoignable ou jeton refusé : {e}")
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if not chats:
            self.n_lbl.setText("Personne n'a encore écrit au bot : envoie-lui un message (/start) dans Telegram, "
                               "puis réessaie.")
            return
        if len(chats) == 1:
            cid = chats[0][0]
        else:
            labels = [f"{n} ({c})" for c, n in chats]
            pick, ok = QtWidgets.QInputDialog.getItem(self, "Chat id", "Quelle discussion reçoit les alertes ?",
                                                      labels, 0, False)
            if not ok:
                return
            cid = chats[labels.index(pick)][0]
        self.tg_chat.setText(cid)
        self.n_lbl.setText(f"✔ Chat id trouvé : {cid} — clique « Envoyer une alerte de test ».")

    def send_test(self):
        n, _w = self.values()
        err = self.owner.send_notify("✔ Test RF Technical Monitor", "Les alertes arrivent bien sur ce téléphone.", 2, cfg=n)
        self.n_lbl.setText(f"⚠ {err}" if err else "Envoyé… (vérifie le téléphone ; une erreur s'affichera ici)")
        QtCore.QTimer.singleShot(4000, self.refresh)

    def refresh(self):
        nt = self.owner.notifier
        if nt is not None and nt.last_error:
            self.n_lbl.setText(f"⚠ Dernier envoi en échec : {nt.last_error}")
        elif nt is not None and nt.sent:
            self.n_lbl.setText(f"✔ {nt.sent} alerte(s) envoyée(s) depuis le démarrage.")
        self.w_lbl.setText(self.owner.web_urls_text())
        self.refresh_clients()

    def _remember_sel(self):
        """Clic dans la liste : on retient QUI est choisi (la liste est reconstruite toutes les 2 s)."""
        it = self.clients.currentItem()
        d = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        self._sel_tok = d[0] if d else None

    def refresh_clients(self):
        ws = self.owner.web
        self.clients.blockSignals(True)         # ne pas perdre le choix pendant qu'on reconstruit
        try:
            self._fill_clients(ws)
        finally:
            self.clients.blockSignals(False)

    def _fill_clients(self, ws):
        self.clients.clear()
        if ws is None:
            self.clients.addItem("(page web arrêtée)")
            return
        names = {k: t for k, _i, t, _d in WEB_VIEWS}
        sel = getattr(self, "_sel_tok", None)
        lst = ws.client_list()
        for e in lst:
            ago = int(time.time() - e["last"])
            tech = {"ok": " · 🛠 Tech", "pending": " · ⏳ demande Tech"}.get(e.get("tech") or "", "")
            it = QtWidgets.QListWidgetItem(("🟢 " if e["online"] else "⚪ ") + f"{e['name']} · {e['addr']}{tech}"
                                           + (f" · {names.get(e['view'], 'Accueil')}" if e["online"]
                                              else f" · vu il y a {ago // 60} min"))
            it.setData(Qt.ItemDataRole.UserRole, (e["token"], e["name"]))
            self.clients.addItem(it)
            if e["token"] == sel:
                self.clients.setCurrentItem(it)
                it.setSelected(True)
        if not lst:
            self.clients.addItem("Personne pour l'instant")

    def _picked(self):
        tok = getattr(self, "_sel_tok", None)
        e = next((x for x in (self.owner.web.client_list() if self.owner.web is not None else [])
                  if x["token"] == tok), None)
        if e is None:
            self.n_lbl.setText("Choisis d'abord un client dans la liste des connectés.")
            return None
        return e["token"], e["name"]

    def rename_client(self):
        d = self._picked()
        if d is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=d[1])
        if ok and name.strip():
            self.owner.web.rename(d[0], name.strip())
            self.refresh_clients()

    def untech_client(self):
        d = self._picked()
        if d is None:
            return
        self.owner.web.revoke_tech(d[0])
        self.n_lbl.setText(f"🛠 « {d[1]} » n'a plus l'accès Tech.")
        self.refresh_clients()

    def identify_client(self):
        d = self._picked()
        if d is None:
            return
        self.owner.web.identify(d[0])
        self.n_lbl.setText(f"👋 L'écran de « {d[1]} » clignote pendant 8 s.")


class RelayWindow(QtWidgets.QWidget):
    """Petite fenêtre « relais » à lancer sur le PC où est branché le 2ᵉ tinySA (RF-Technical-Monitor.exe --relais)."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(f"{APP_NAME} — relais réseau")
        self.resize(520, 330)
        self.relay = None
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.port_combo.setMinimumContentsLength(20)
        b_ref = QtWidgets.QToolButton()
        b_ref.setText("⟳")
        b_ref.clicked.connect(lambda *_: self.refresh_ports())
        self.tcp_spin = QtWidgets.QSpinBox()
        self.tcp_spin.setRange(1024, 65535)
        self.tcp_spin.setValue(RELAY_PORT)
        self.allow_edit = QtWidgets.QLineEdit()
        self.allow_edit.setPlaceholderText("vide = tout le réseau · ex. 192.168.1.10")
        self.allow_edit.setToolTip("Adresses IP des PC qui ont le droit de se connecter à ce tinySA, séparées par des "
                                   "virgules. Vide = n'importe quel appareil du réseau.")
        self.go_btn = QtWidgets.QPushButton("▶ Partager ce tinySA")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        self.addr_lbl = QtWidgets.QLabel("")
        self.addr_lbl.setWordWrap(True)
        self.addr_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.state_lbl = QtWidgets.QLabel("Arrêté.")
        self.state_lbl.setWordWrap(True)
        help_lbl = QtWidgets.QLabel(
            "Branche le tinySA en USB sur CE PC, choisis son port puis « Partager ». Sur le PC principal : "
            "Réglages › 2ᵉ tinySA › adresse affichée ci-dessous. Les deux PC doivent être sur le même réseau "
            "(câble de préférence). Windows peut demander d'autoriser l'accès réseau : accepte (réseau privé).")
        help_lbl.setWordWrap(True)
        form = QtWidgets.QFormLayout()
        h = QtWidgets.QHBoxLayout()
        h.addWidget(self.port_combo, 1)
        h.addWidget(b_ref)
        form.addRow("Port du tinySA :", h)
        form.addRow("Port réseau (TCP) :", self.tcp_spin)
        form.addRow("PC autorisés :", self.allow_edit)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(help_lbl)
        lay.addLayout(form)
        lay.addWidget(self.go_btn)
        lay.addWidget(self.addr_lbl)
        lay.addWidget(self.state_lbl)
        lay.addStretch(1)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.refresh_ports()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())
        ports.sort(key=lambda p: not (p.vid == TINYSA_VID and p.pid == TINYSA_PID))
        for p in ports:
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            desc = str(p.description or "").replace(f" ({p.device})", "")      # 7.59 : « (COM4) » en double
            self.port_combo.addItem(f"{p.device} — {desc}{tag}", p.device)
        if not ports:
            self.port_combo.addItem("Aucun port détecté", None)

    def toggle(self):
        if self.relay is not None:
            self.relay.stop()
            self.relay.join(3)
            self.relay = None
            self.timer.stop()
            self.go_btn.setText("▶ Partager ce tinySA")
            self.port_combo.setEnabled(True)
            self.tcp_spin.setEnabled(True)
            self.allow_edit.setEnabled(True)
            self.addr_lbl.setText("")
            self.state_lbl.setText("Arrêté.")
            return
        port = self.port_combo.currentData()
        if not port:
            self.state_lbl.setText("⚠ Aucun port : branche le tinySA (et ferme tinySA-App).")
            return
        allow = [x.strip() for x in self.allow_edit.text().replace(";", ",").split(",") if x.strip()]
        self.relay = SerialRelay(port, self.tcp_spin.value(), allow=allow)
        self.relay.start()
        self.relay.ready.wait(3)
        if not self.relay.is_alive():
            self.state_lbl.setText("⚠ " + (self.relay.error or "Démarrage impossible."))
            self.relay = None
            return
        ips = local_ips() or ["<adresse IP de ce PC>"]
        self.addr_lbl.setText("Adresse à saisir sur le PC principal :  <b>"
                              + "</b>  ou  <b>".join(f"{ip}:{self.relay.tcp_port}" for ip in ips) + "</b>")
        self.go_btn.setText("■ Arrêter le partage")
        self.port_combo.setEnabled(False)
        self.tcp_spin.setEnabled(False)
        self.allow_edit.setEnabled(False)
        self.timer.start()
        self.tick()

    def tick(self):
        r = self.relay
        if r is None:
            return
        usb = "✔ tinySA ouvert" if r.serial_ok else f"⚠ {r.error or 'tinySA introuvable'} (nouvel essai…)"
        cli = f"✔ connecté à {r.client}" if r.client else "en attente du PC principal…"
        if r.refused:
            cli += f" · ⛔ refusé : {r.refused}"
        open_ = "" if r.allow else ("\n⚠ Aucun PC autorisé n'est indiqué : tout appareil du réseau peut piloter ce "
                                     "tinySA. À réserver à un réseau technique de confiance.")
        self.state_lbl.setText(f"{usb}\nRéseau : {cli}\nTrafic : {r.rx / 1024:.0f} Ko reçus du tinySA · "
                               f"{r.tx / 1024:.1f} Ko de commandes{open_}")

    def closeEvent(self, e):
        if self.relay is not None:
            self.relay.stop()
            self.relay.join(3)
            self.relay = None
        super().closeEvent(e)
