"""8.1 : régénère dans tinysa_monitor.py la liste « from tsm_core import (...) » d'après les noms définis dans
tsm_core.py (à lancer après avoir ajouté quelque chose au cœur ; check_names signale un oubli)."""
import ast, os, re
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
core = open(os.path.join(ROOT, "tsm_core.py"), encoding="utf-8").read()
names = set()
for node in ast.parse(core).body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        names.add(node.name)
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    names.add(n.id)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
        names.add(node.target.id)
skip = {"bisect", "csv", "io", "itertools", "math", "re", "unicodedata", "deque", "np"}
names = sorted(names - skip)
p = os.path.join(ROOT, "tinysa_monitor.py")
src = open(p, encoding="utf-8").read()
m = re.search(r"from tsm_core import \(  # noqa: F401\n(.*?)\n\)\n", src, re.S)
body, line = "", "    "
for n in names:
    piece = n + ", "
    if len(line) + len(piece) > 116:
        body += line.rstrip() + "\n"
        line = "    "
    line += piece
body += line.rstrip()
src = src[:m.start(1)] + body + src[m.end(1):]
open(p, "w", encoding="utf-8").write(src)
print(len(names), "noms importés du cœur")
