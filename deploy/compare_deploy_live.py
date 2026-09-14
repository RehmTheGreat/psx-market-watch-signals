import json, subprocess, sys

def load(wid, col):
    r = subprocess.run(["sqlite3", "-readonly", "/home/ubuntu/.n8n/database.sqlite",
                        'SELECT %s FROM workflow_entity WHERE id="%s";' % (col, wid)], capture_output=True, text=True)
    return json.loads(r.stdout)

SUB = {"__SHEET_ID__": None, "__GROQ_KEY__": None}
row = subprocess.run(["sqlite3", "-readonly", "/home/ubuntu/.n8n/database.sqlite",
                      "SELECT value FROM system_state WHERE key='test'"], capture_output=True, text=True)

def sub(s):
    for k, v in SUB.items():
        if v:
            s = s.replace(k, v)
    return s

# pull placeholder real values from live workflow JSON itself
live_nodes = load(sys.argv[1], "nodes")
blob = json.dumps(live_nodes)
sheet_id = "1twkWIyCmExipnuP0jeAmBFUmRCzxTUGo5PSkVwhX6Ak"
SUB["__SHEET_ID__"] = sheet_id
import re
m = re.search(r"Bearer (gsk_[A-Za-z0-9_]+)", blob)
SUB["__GROQ_KEY__"] = m.group(1) if m else ""

dep = json.load(open(sys.argv[2]))
dep_blob = sub(json.dumps(dep))
depw = json.loads(dep_blob)

dn = {n["name"]: n for n in depw["nodes"]}
ln = {n["name"]: n for n in live_nodes}
issues = []
for name in sorted(set(dn) | set(ln)):
    if name not in dn: issues.append("only-live: " + name); continue
    if name not in ln: issues.append("only-deploy: " + name); continue
    a, b = dn[name], ln[name]
    for field in ("type", "typeVersion", "executeOnce", "alwaysOutputData", "onError"):
        if bool(a.get(field)) != bool(b.get(field)):
            issues.append("%s.%s: deploy=%r live=%r" % (name, field, a.get(field), b.get(field)))
    if json.dumps(a.get("parameters", {}), sort_keys=True) != json.dumps(b.get("parameters", {}), sort_keys=True):
        issues.append("%s.parameters DIFFER" % name)
    if json.dumps(a.get("credentials", {}), sort_keys=True) != json.dumps(b.get("credentials", {}), sort_keys=True):
        issues.append("%s.credentials DIFFER" % name)

lc = load(sys.argv[1], "connections")
dc = depw["connections"]
norm = lambda c: {s: sorted(t["node"] for g in v.get("main", []) for t in g) for s, v in c.items()}
if norm(dc) != norm(lc):
    issues.append("CONNECTIONS DIFFER: deploy=%s live=%s" % (norm(dc), norm(lc)))

print("=== %s vs live %s ===" % (sys.argv[2], sys.argv[1]))
if issues:
    for i in issues: print(" -", i)
else:
    print("MATCH: nodes, parameters, flags, credentials, connections all identical")
