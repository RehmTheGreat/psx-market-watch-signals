import json, re, subprocess, sys

path = sys.argv[1] if len(sys.argv) > 1 else "psx_signals.json"
d = json.load(open(path, encoding="utf-8"))
nodes = d["nodes"]; conns = d["connections"]
names = {n["name"] for n in nodes}
errors = []

# 1) every code/expression $() ref exists
for n in nodes:
    blob = json.dumps(n.get("parameters", {}))
    for m in re.finditer(r"\$\((['\"])(.+?)\1\)", blob):
        if m.group(2) not in names:
            errors.append("ref missing node: %s (in %s)" % (m.group(2), n["name"]))
    for m in re.finditer(r"safeRows\((['\"])(.+?)\1\)", blob):
        if m.group(2) not in names:
            errors.append("safeRows missing node: %s (in %s)" % (m.group(2), n["name"]))

# 2) connection endpoints exist
for src, c in conns.items():
    if src not in names: errors.append("conn src missing: " + src)
    for g in c.get("main", []):
        for t in g:
            if t["node"] not in names: errors.append("conn dst missing: " + t["node"])

# 3) reachability from triggers
adj = {s: [t["node"] for g in c.get("main", []) for t in g] for s, c in conns.items()}
triggers = [n["name"] for n in nodes if "trigger" in n["type"].lower()]
seen, stack = set(), list(triggers)
while stack:
    cur = stack.pop()
    if cur in seen: continue
    seen.add(cur); stack += adj.get(cur, [])
for n in nodes:
    if n["name"] not in seen: errors.append("unreachable: " + n["name"])

# 4) merge input indexes all connected (inputs live under SOURCE nodes' connections)
for n in nodes:
    if n["type"].endswith(".merge"):
        need = n["parameters"].get("numberInputs", 2)
        idxs = set()
        for src, c in conns.items():
            for g in c.get("main", []):
                for t in g:
                    if t["node"] == n["name"]:
                        idxs.add(t.get("index", 0))
        if len(idxs) != need:
            errors.append("merge %s: %d/%d inputs connected (%s)" % (n["name"], len(idxs), need, sorted(idxs)))

print("edges:", sum(len(g) for c in conns.values() for g in c.get("main", [])), "| nodes:", len(nodes))
print("VALIDATE:", "OK" if not errors else errors)
sys.exit(1 if errors else 0)
