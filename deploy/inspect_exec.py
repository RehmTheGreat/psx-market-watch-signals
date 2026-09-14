import json, subprocess, sys

DB = "/home/ubuntu/.n8n/database.sqlite"
wid = sys.argv[1] if len(sys.argv) > 1 else "psxsignal001"

eid = subprocess.run(["sqlite3", "-readonly", DB,
    'SELECT e.id FROM execution_entity e WHERE e.workflowId="%s" ORDER BY e.startedAt DESC LIMIT 1;' % wid],
    capture_output=True, text=True).stdout.strip()
print("execution id:", eid)
data = subprocess.run(["sqlite3", "-readonly", DB,
    'SELECT data FROM execution_data WHERE executionId=%s;' % int(eid)],
    capture_output=True, text=True).stdout
raw = json.loads(data)
N = len(raw)

def res(x, depth=0):
    if depth > 60: return "?"
    if isinstance(x, dict): return {k: res(v, depth+1) for k, v in x.items()}
    if isinstance(x, list): return [res(v, depth+1) for v in x]
    if isinstance(x, str) and x.isdigit() and int(x) < N: return res(raw[int(x)], depth+1)
    return x

rd = res(raw[0]["resultData"])["runData"]
for name, runs in rd.items():
    for r in runs:
        outs = r.get("data", {}).get("main", [])
        for i, o in enumerate(outs):
            if o is None:
                print("%-28s out[%d]: null" % (name, i)); continue
            print("%-28s out[%d]: %d items" % (name, i, len(o)))
            if name == "Fetch PSX Market Watch" and o:
                j = o[0].get("json", {})
                body = str(j.get("data") or j.get("body") or "")[:0]  # skip huge body
                print("   fetch json keys:", list(j.keys())[:8])
            if name == "Build Signals" and o:
                j = o[0].get("json", {})
                sig = j.get("signals", [])
                print("   signals:", len(sig))
                for s in sig[:12]:
                    print("   *", s.get("symbol"), s.get("action"), "| px", s.get("current_price"), "| chg%", s.get("change_pct"), "| qty", s.get("quantity"), "| reason:", str(s.get("reason"))[:80])
            if name == "Send Signal Email" and o:
                j = o[0].get("json", {})
                print("   email id:", j.get("id"), "| threadId:", j.get("threadId"), "| to:", j.get("to"))
            if name == "Log Signals" and o:
                for it in o[:3]:
                    print("   row:", json.dumps(it.get("json", {}))[:160])
            if name == "Extract Email" and o:
                j = o[0].get("json", {})
                print("   subject:", str(j.get("email_subject"))[:120], "| count:", j.get("signal_count"))
