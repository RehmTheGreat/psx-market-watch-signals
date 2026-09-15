import json, sqlite3, re, subprocess, sys, time

GEN = "/tmp/psx_signals.json"
WID = "psxsignal001"
DB = "/home/ubuntu/.n8n/database.sqlite"
SHEET_ID = "1twkWIyCmExipnuP0jeAmBFUmRCzxTUGo5PSkVwhX6Ak"

def load(wid, col):
    r = subprocess.run(["sqlite3", "-readonly", DB, 'SELECT %s FROM workflow_entity WHERE id="%s";' % (col, wid)], capture_output=True, text=True)
    return json.loads(r.stdout)

live_nodes = load(WID, "nodes")
m = re.search(r"Bearer (gsk_[A-Za-z0-9_]+)", json.dumps(live_nodes))
if not m:
    sys.exit("could not locate groq key in live workflow")
dep = json.load(open(GEN))
blob = json.dumps(dep).replace("__SHEET_ID__", SHEET_ID).replace("__GROQ_KEY__", m.group(1))
dep = json.loads(blob)

subprocess.run(["systemctl", "--user", "stop", "n8n"], check=True)
time.sleep(2)
db = sqlite3.connect(DB)
db.execute("UPDATE workflow_entity SET nodes = ?, connections = ? WHERE id = ?",
           (json.dumps(dep["nodes"]), json.dumps(dep["connections"]), WID))
db.commit()

chk_nodes = json.loads(db.execute("SELECT nodes FROM workflow_entity WHERE id=?", (WID,)).fetchone()[0])
chk_conns = json.loads(db.execute("SELECT connections FROM workflow_entity WHERE id=?", (WID,)).fetchone()[0])
db.close()
names = [n["name"] for n in chk_nodes]
edges = sum(len(g) for c in chk_conns.values() for g in c.get("main", []))
print("live now: nodes", len(names), "| edges", edges)
print("has Gate:", "Gate" in names, "| has Join Inputs:", "Join Inputs" in names, "| has Read Watchlist:", "Read Watchlist" in names)
print("fallback in code:", "ALWAYS-DEPLOY FALLBACK" in next(n["parameters"]["jsCode"] for n in chk_nodes if n["name"] == "Build Signals"))
ids = [n["id"] for n in chk_nodes]
print("duplicate ids:", len(ids) != len(set(ids)))

subprocess.run(["systemctl", "--user", "start", "n8n"], check=True)
for i in range(30):
    time.sleep(2)
    if subprocess.run(["systemctl", "--user", "is-active", "n8n"], capture_output=True, text=True).stdout.strip() == "active":
        break
print("n8n active")
