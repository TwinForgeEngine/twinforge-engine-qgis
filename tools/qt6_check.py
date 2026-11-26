"""Static Qt6 check: every `from qgis.PyQt.X import ...` name and every Qt enum path resolves under PyQt6."""
import ast, importlib, pathlib, sys
bad = []; n = 0
for f in pathlib.Path(sys.argv[1]).rglob("*.py"):
    t = ast.parse(f.read_text()); qtnames = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("qgis.PyQt."):
            mod = importlib.import_module("PyQt6." + node.module.split(".", 2)[2])
            in_try = any(isinstance(p, ast.Try) and node in ast.walk(p) and any(isinstance(h.type, ast.Name) and h.type.id == "ImportError" for h in p.handlers) for p in ast.walk(t))
            for a in node.names:
                n += 1
                if hasattr(mod, a.name): qtnames[a.asname or a.name] = getattr(mod, a.name)
                elif not in_try: bad.append(f"{f}:{node.lineno} import {node.module}.{a.name}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            m = getattr(node, "module", None) or ""
            if m.startswith("PyQt") or any(a.name.startswith("PyQt") for a in node.names): bad.append(f"{f}:{node.lineno} direct PyQt import")
    for node in ast.walk(t):
        if isinstance(node, ast.Attribute):
            parts = [node.attr]; v = node.value
            while isinstance(v, ast.Attribute): parts.append(v.attr); v = v.value
            if isinstance(v, ast.Name) and v.id in qtnames and parts[-1][:1].isupper():
                obj = qtnames[v.id]; path = parts[::-1]; n += 1
                try:
                    for p in path: obj = getattr(obj, p)
                except AttributeError:
                    bad.append(f"{f}:{node.lineno} {v.id}.{'.'.join(path)}")
        if isinstance(node, ast.Attribute) and node.attr == "exec_": bad.append(f"{f}:{node.lineno} exec_")
print("checked", n, "bad", len(bad)); print("\n".join(sorted(set(bad))))
