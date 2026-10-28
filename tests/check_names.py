import ast, builtins, sys

src = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()
tree = ast.parse(src)

# ---- 1. noms globaux non définis (approximation)
stored = set(dir(builtins)) | {"__file__"}       # toujours défini dans un module
for n in ast.walk(tree):
    if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
        stored.add(n.id)
    elif isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
        stored.add(n.name)
    elif isinstance(n, ast.arg):
        stored.add(n.arg)
    elif isinstance(n, (ast.Import, ast.ImportFrom)):
        for a in n.names:
            stored.add((a.asname or a.name).split(".")[0])
    elif isinstance(n, ast.ExceptHandler) and n.name:
        stored.add(n.name)
used = {}
for n in ast.walk(tree):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in stored:
        used.setdefault(n.id, n.lineno)
print("Noms possiblement non définis:", used or "aucun")

# ---- 2. attributs self.xxx de MainWindow / ScanWorker / dialogs
for cls in [c for c in tree.body if isinstance(c, ast.ClassDef)]:
    defined = {f.name for f in cls.body if isinstance(f, ast.FunctionDef)}
    for n in ast.walk(cls):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" \
                and isinstance(n.ctx, ast.Store):
            defined.add(n.attr)
    # attributs de classe
    for f in cls.body:
        if isinstance(f, ast.Assign):
            for t in f.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
    missing = {}
    for n in ast.walk(cls):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" \
                and isinstance(n.ctx, ast.Load) and n.attr not in defined:
            missing.setdefault(n.attr, n.lineno)
    print(f"[{cls.name}] self.* non définis ici (hérités de Qt ?):", sorted(missing))
