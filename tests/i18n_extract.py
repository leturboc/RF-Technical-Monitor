"""Textes à traduire du programme (utilisé par tests/test_i18n.py et pour préparer lang_en.py).
extract(src) -> (constantes, modèles f-string, morceaux de texte des gros HTML)."""
import ast
import re

LETTERS = re.compile(r"[A-Za-zÀ-ÿ]{2,}")
CODEISH = re.compile(r"^[a-z0-9_.\-/:%#+*=?&|\\\[\]()^$<>{}',\"]+$")      # identifiants, regex, chemins…
SKIP_PREFIX = ("http://", "https://", "socket://", "%Y", "<!doctype", "<!DOCTYPE")
HTML_MIN = 400                       # au-delà : document HTML / CSS / JS traité à part (texte entre les balises)


CSS = re.compile(r"^\s*[.#@a-z*][^{}]*\{[^{}]*:[^{}]*\}")                   # .classe{prop:valeur}
CAMEL = re.compile(r"^[a-z]+[A-Z][A-Za-z0-9]*$")                           # showMessage, setText…


JS = re.compile(r"\$\{|\$\(|=>|function\b|\bconst |\);|^\s*[)};,]|\b(if|return)\(")
TAG = re.compile(r"</?[a-zA-Z][^<>]*>")
REGEXISH = re.compile(r"\[[^\]]*-[^\]]*\]|\(\?|\\[dswb]|\([a-z]+(\|[a-z ]+)+\)")


def is_ui(s):
    st = s.strip()
    if not LETTERS.search(st) or st.startswith(SKIP_PREFIX) or CSS.match(st) or CAMEL.match(st):
        return False
    if JS.search(st) or REGEXISH.search(st) or re.fullmatch(r"&\w+;", st):
        return False
    if CODEISH.match(st) and not re.search(r"[À-ÿ]", st):
        return False
    if re.fullmatch(r"[A-Z0-9_]+", st) and len(st) > 1 and "_" in st:
        return False                 # CONSTANTE_INTERNE
    return True


def html_texts(h):
    out = []
    for m in re.finditer(r">([^<>]+)<", h):
        t = m.group(1).strip()
        if is_ui(t) and not re.search(r"[{};]\s*$|^\s*[.#@]", t) and "=>" not in t and "function" not in t:
            out.append(t)
    for m in re.finditer(r'title="([^"]+)"', h):
        if is_ui(m.group(1)):
            out.append(m.group(1))
    return out


def extract(src):
    tree = ast.parse(src)
    doc, inside_f = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant):
                doc.add(id(b[0].value))
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                inside_f.add(id(v))
    consts, tpls, html = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(v.value.replace("{", "{{").replace("}", "}}"))
                else:
                    parts.append("{}")
            t = "".join(parts)
            if is_ui(t.replace("{}", " ")):
                tpls.add(t)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in doc or id(node) in inside_f:
                continue
            s = node.value
            if (len(s) >= HTML_MIN and "<" in s and ">" in s) or TAG.search(s):
                html.update(html_texts(">" + s + "<"))                 # HTML : le texte entre les balises
            elif s.count("|") >= 6 and s.count("\n") >= 3:            # tableau de données « a|b|texte »
                for line in s.split("\n"):
                    for field in line.split("|"):
                        if is_ui(field) and not re.fullmatch(r"[\d.\-]+", field.strip()):
                            consts.add(field.strip())
            elif is_ui(s):
                consts.add(s)
    return consts, tpls, html
