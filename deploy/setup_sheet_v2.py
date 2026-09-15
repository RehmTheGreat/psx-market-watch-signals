import json, subprocess, urllib.request, urllib.parse

def run(cmd, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True)
    return r.stdout, r.stderr

key = open("/home/ubuntu/.n8n/encryption_key").read().strip()
blob, _ = run(["sqlite3", "-readonly", "/home/ubuntu/.n8n/database.sqlite",
               "SELECT data FROM credentials_entity WHERE id='nweeZqVpxfEvZ2Og';"])
plain, err = run(["openssl", "enc", "-d", "-aes-256-cbc", "-md", "md5", "-a", "-A", "-pass", "pass:" + key], blob.strip())
d = json.loads(plain); ot = d["oauthTokenData"]
data = urllib.parse.urlencode({"client_id": d["clientId"], "client_secret": d["clientSecret"],
                               "refresh_token": ot["refresh_token"], "grant_type": "refresh_token"}).encode()
tok = json.loads(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data), timeout=30).read())
access = tok["access_token"]
H = {"Authorization": "Bearer " + access, "Content-Type": "application/json"}
SHEET = "1twkWIyCmExipnuP0jeAmBFUmRCzxTUGo5PSkVwhX6Ak"

def api(url, body=None, method="GET"):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method, headers=H)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "body": e.read().decode()[:200]}

# 1) create MktCache tab if missing
meta = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}?fields=sheets.properties.title")
titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
if "MktCache" not in titles:
    r = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}:batchUpdate",
            {"requests": [{"addSheet": {"properties": {"title": "MktCache"}}}]}, "POST")
    print("MktCache created:", "__error__" not in r)
else:
    print("MktCache exists")

# 2) settings updates
rows = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values/Settings%21A1:B60").get("values", [])
kv = {r[0]: (i + 1, r[1] if len(r) > 1 else "") for i, r in enumerate(rows) if r}
updates = {"stop_loss_pct": "1.5", "take_profit_arm_pct": "1.5", "trail_from_high_pct": "0.8"}
appends = [["max_open_positions", "5"], ["eod_flat", "TRUE"], ["round_trip_cost_bps", "12"], ["cgt_pct", "15"],
           ["cash_floor_pct", "20"], ["min_turnover_m", "25"], ["big_turnover_m", "50"],
           ["max_band_dist_pct", "7"], ["min_price", "5"]]
reqs = []
for k, v in updates.items():
    if k in kv:
        reqs.append({"range": f"Settings!B{kv[k][0]}", "values": [[v]]})
if reqs:
    r = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values:batchUpdate",
            {"valueInputOption": "RAW", "data": reqs}, "POST")
    print("updated rows:", r.get("totalUpdatedCells", r))
existing_new = [k for k, _ in appends if k in kv]
to_append = [a for a in appends if a[0] not in kv]
if to_append:
    r = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values/Settings%21A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
            {"values": to_append}, "POST")
    print("appended", len(to_append), "knobs:", [a[0] for a in to_append])
if existing_new:
    print("already present (skipped):", existing_new)

# 3) verify
rows = api(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values/Settings%21A1:B60").get("values", [])
print("final settings keys:", [r[0] for r in rows if r])
