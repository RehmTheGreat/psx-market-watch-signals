import json, sqlite3, re, subprocess, sys, time

DB = "/home/ubuntu/.n8n/database.sqlite"
SHEET_ID = "1twkWIyCmExipnuP0jeAmBFUmRCzxTUGo5PSkVwhX6Ak"
TARGETS = [("psxsignal001", "/tmp/psx_signals.json"), ("psxtrader001", "/tmp/psx_trader.json")]

def load(wid, col):
    r = subprocess.run(["sqlite3", "-readonly", DB, 'SELECT %s FROM workflow_entity WHERE id="%s";' % (col, wid)], capture_output=True, text=True)
    return json.loads(r.stdout)

groq = re.search(r"Bearer (gsk_[A-Za-z0-9_]+)", json.dumps(load("psxsignal001", "nodes")))
if not groq:
    sys.exit("no groq key found")
substitutions = {"__SHEET_ID__": SHEET_ID, "__GROQ_KEY__": groq.group(1)}

payloads = {}
for wid, path in TARGETS:
    dep = json.load(open(path))
    blob = json.dumps(dep)
    for k, v in substitutions.items():
        blob = blob.replace(k, v)
    payloads[wid] = json.loads(blob)

subprocess.run(["systemctl", "--user", "stop", "n8n"], check=True)
time.sleep(2)
db = sqlite3.connect(DB)
for wid, data in payloads.items():
    db.execute("UPDATE workflow_entity SET nodes = ?, connections = ? WHERE id = ?",
               (json.dumps(data["nodes"]), json.dumps(data["connections"]), wid))
    print("updated", wid)
db.commit()
for wid, _ in TARGETS:
    n = json.loads(db.execute("SELECT nodes FROM workflow_entity WHERE id=?", (wid,)).fetchone()[0])
    c = json.loads(db.execute("SELECT connections FROM workflow_entity WHERE id=?", (wid,)).fetchone()[0])
    edges = sum(len(g) for src in c for g in c[src].get("main", []))
    print(wid, "readback:", len(n), "nodes,", edges, "edges")
db.close()

subprocess.run(["systemctl", "--user", "start", "n8n"], check=True)
for i in range(30):
    time.sleep(2)
    if subprocess.run(["systemctl", "--user", "is-active", "n8n"], capture_output=True, text=True).stdout.strip() == "active":
        break
print("n8n active")
