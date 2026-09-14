# Generates n8n workflow JSONs for the PSX virtual-trading deployment on A1.
# Placeholder __SHEET_ID__ in the imported workflows is replaced after bootstrap runs.
import json, copy, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHEETS_CRED = {"googleSheetsOAuth2Api": {"id": "nweeZqVpxfEvZ2Og", "name": "Sheets for abdul.71433@iqra.edu.pk"}}
DOC = {"__rl": True, "value": "__SHEET_ID__", "mode": "id"}

def sheets_node(name, op, doc, tab, columns=None, creds=True, extra=None, position=(0, 0), notes=None):
    p = {"operation": op, "documentId": doc, "sheetName": {"__rl": True, "value": tab, "mode": "name"}, "options": {}}
    if op not in ("read",):
        cols = copy.deepcopy(columns) if columns else {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}
        if not cols.get("schema"):
            names = cols.get("value", {}).keys() if cols.get("mappingMode") == "defineBelow" else SCHEMAS.get(tab, [])
            # full resource-mapper entry shape: without displayName the defineBelow value
            # map silently resolves no columns and the append degrades to autoMap of input
            cols["schema"] = [{"id": c, "name": c, "displayName": c, "display": True, "type": "string",
                               "required": False, "canBeUsedToMatch": True, "removeValue": False} for c in names]
        p["columns"] = cols
    if extra:
        p.update(extra)
    n = {"parameters": p, "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.7,
         "id": name.lower().replace(" ", "-"), "name": name, "position": list(position)}
    if creds:
        n["credentials"] = SHEETS_CRED
    if notes:
        n["notes"] = notes
    return n

def code_node(name, code, position=(0, 0)):
    return {"parameters": {"jsCode": code}, "type": "n8n-nodes-base.code", "typeVersion": 2,
            "id": name.lower().replace(" ", "-"), "name": name, "position": list(position)}

def http_psx(name, position=(0, 0)):
    return {"parameters": {"url": "https://dps.psx.com.pk/market-watch", "options": {"response": {"response": {"neverError": True, "responseFormat": "text", "outputPropertyName": "body"}}}},
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.4, "id": name.lower().replace(" ", "-"),
            "name": name, "position": list(position), "executeOnce": True, "onError": "continueRegularOutput"}

def sched(name, expr, position=(0, 0)):
    return {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": expr}]}},
            "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
            "id": name.lower().replace(" ", "-"), "name": name, "position": list(position)}

def connect(wf, frm, tos):
    wf["connections"][frm] = {"main": [[{"node": t, "type": "main", "index": 0} for t in tos]]}

def connecti(wf, frm, to, idx):
    wf["connections"][frm] = {"main": [[{"node": to, "type": "main", "index": idx}]]}

def merge_node(name, ninputs, position=(0, 0)):
    return {"parameters": {"mode": "append", "numberInputs": ninputs}, "type": "n8n-nodes-base.merge",
            "typeVersion": 3, "id": name.lower().replace(" ", "-"), "name": name, "position": list(position)}

SETTINGS = [
    ("recipient", "a.rehman0364@gmail.com"),
    ("min_change_pct_buy", 1), ("min_change_pct_sell", -1),
    ("max_cash_fraction_per_trade", 0.5), ("default_max_trade_value", 50000), ("default_lot_size", 1),
    ("momentum_weight_pct", 40), ("position_weight_pct", 30), ("volume_weight_pct", 30),
    ("score_buy_threshold", 60), ("score_sell_threshold", 60), ("volume_surge_lookback_days", 20),
    ("circuit_breaker_pct", 10), ("stop_loss_pct", 7), ("max_position_pct_of_portfolio", 75),
    ("min_traded_value_floor", 1000000), ("data_freshness_max_minutes", 15),
    ("openai_model", "fable"), ("discovery_enabled", "FALSE"),
]
WATCHLIST = ["OGDC", "PPL", "MARI", "ENGRO", "LUCK", "HBL", "UBL", "FFC", "TRG", "SYS"]
TABS = ["Holding", "Cash", "Settings", "Watchlist", "Signals", "Trades", "State", "Equity"]
SCHEMAS = {
    "Holding": ["symbol", "lot_id", "shares", "avg_price", "max_trade_value", "lot_size"],
    "Cash": ["amount"], "Settings": ["key", "value"],
    "Watchlist": ["symbol", "max_trade_value", "lot_size"],
    "Signals": ["run_ts", "symbol", "action", "quantity", "limit_price", "current_price", "change_pct", "trade_value", "reason"],
    "Trades": ["ts", "symbol", "side", "quantity", "price", "value", "cash_after", "note"],
    "State": ["key", "value"],
    "Equity": ["ts", "cash", "holdings_value", "portfolio_value", "notes"],
}

# ---------------- bootstrap + seed ----------------
wf = {"name": "PSX 1. Bootstrap & Seed", "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}}
create = {"parameters": {"resource": "spreadsheet", "operation": "create", "title": "PSX Market Watch Virtual",
                          "sheetsUi": {"sheetValues": [{"title": t} for t in TABS]}, "options": {}},
          "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.7, "credentials": SHEETS_CRED,
          "id": "create-spreadsheet", "name": "Create Spreadsheet", "position": [300, 300]}
wf["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "go", "name": "Go", "position": [80, 300]})
wf["nodes"].append(create)
connect(wf, "Go", ["Create Spreadsheet"])
DYN = {"__rl": True, "value": "={{ $('Create Spreadsheet').first().json.spreadsheetId }}", "mode": "id"}
prev = "Create Spreadsheet"
# settings rows
code = "const rows=" + json.dumps([{"key": k, "value": str(v)} for k, v in SETTINGS]) + ";\nreturn rows.map(r=>({json:r}));"
n = code_node("Build Settings Rows", code); n["position"] = [520 + 200 * len(wf["nodes"]), 320]; wf["nodes"].append(n); connect(wf, prev, [n["name"]])
n2 = sheets_node("Seed Settings", "append", DYN, "Settings", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n2["position"] = [720 + 200 * len(wf["nodes"]), 320]; wf["nodes"].append(n2); connect(wf, "Build Settings Rows", ["Seed Settings"]); prev = "Seed Settings"
# watchlist rows
code = "const syms=" + json.dumps(WATCHLIST) + ";\nreturn syms.map(s=>({json:{symbol:s,max_trade_value:50000,lot_size:1}}));"
n = code_node("Build Watchlist Rows", code); n["position"] = [520 + 200 * len(wf["nodes"]), 520]; wf["nodes"].append(n); connect(wf, prev, [n["name"]])
n2 = sheets_node("Seed Watchlist", "append", DYN, "Watchlist", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n2["position"] = [720 + 200 * len(wf["nodes"]), 520]; wf["nodes"].append(n2); connect(wf, "Build Watchlist Rows", ["Seed Watchlist"]); prev = "Seed Watchlist"
# cash row
n2 = sheets_node("Seed Cash", "append", DYN, "Cash", {"mappingMode": "defineBelow", "value": {"amount": "500000"}, "matchingColumns": [], "schema": []})
n2["position"] = [720 + 200 * len(wf["nodes"]), 720]; wf["nodes"].append(n2); connect(wf, prev, ["Seed Cash"]); prev = "Seed Cash"
# state rows
code = ("return [{json:{key:'end_date',value:'2026-09-19T15:30:00+05:00'}},"
        "{json:{key:'last_row',value:'1'}},{json:{key:'status',value:'RUNNING'}},"
        "{json:{key:'start_value',value:'500000'}},{json:{key:'started',value:'2026-09-12'}}];")
n = code_node("Build State Rows", code); n["position"] = [520 + 200 * len(wf["nodes"]), 720]; wf["nodes"].append(n); connect(wf, prev, [n["name"]])
n2 = sheets_node("Seed State", "append", DYN, "State", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n2["position"] = [720 + 200 * len(wf["nodes"]), 720]; wf["nodes"].append(n2); connect(wf, "Build State Rows", ["Seed State"])
wf["id"] = "psxboot0001"
json.dump(wf, open(os.path.join(HERE, "bootstrap.json"), "w"), indent=1)
print("bootstrap.json:", len(wf["nodes"]), "nodes")

# ---------------- signals workflow (patch repo JSON) ----------------
repo = json.load(open(os.path.join(REPO, "workflow", "psx-market-watch-signals.json"), encoding="utf-8"))
sig = {"name": "PSX 2. Market Watch Signals", "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}, "active": False}
oldname = "When clicking 'Execute workflow'"
for n in repo["nodes"]:
    if n["name"] == oldname:
        continue
    m = copy.deepcopy(n)
    if m["name"] in ("Read Holdings", "Read Cash", "Read Settings"):
        tab = {"Read Holdings": "Holding", "Read Cash": "Cash", "Read Settings": "Settings"}[m["name"]]
        m["parameters"]["documentId"] = copy.deepcopy(DOC)
        m["parameters"]["sheetName"] = {"__rl": True, "value": tab, "mode": "name"}
        m["credentials"] = copy.deepcopy(SHEETS_CRED)
        # 2026-09-15 fix: a sheets read that matches zero rows emits ZERO items and the
        # whole downstream chain silently starves (day-1 empty Holding tab killed every
        # run while n8n still reported success). alwaysOutputData keeps the chain alive.
        m["alwaysOutputData"] = True
    if m["name"] == "OpenAI Format Signals":
        # Groq chat completions (pc ruling 2026-09-13: PSX AI-format runs on Groq's free tier,
        # NOT on rehms-inference). Body needs a single leading "=" (expression mode); the
        # repo's "=={{ }}" renders a literal "=" into the JSON body and every API rejects it.
        m["parameters"]["url"] = "https://api.groq.com/openai/v1/chat/completions"
        m["parameters"].pop("authentication", None); m["parameters"].pop("genericAuthType", None)
        m["parameters"]["body"] = "={{ JSON.stringify($json.openai_request) }}"
        m["parameters"]["sendHeaders"] = True
        m["parameters"]["headerParameters"] = {"parameters": [{"name": "Authorization", "value": "Bearer __GROQ_KEY__"},
            {"name": "User-Agent", "value": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}]}
        # browser UA required: Groq is behind Cloudflare and 1010-blocks non-browser UAs from the VPS
        m.pop("credentials", None)
    if m["name"] == "Build Signals":
        # Translate the OpenAI Responses request into Groq's chat-completions contract.
        # Model is a Settings-tab value (groq_model); default qwen/qwen3.8-27b per pc
        # (2026-09-13: "use qwen 3.8 27b, intelligence matters more than parameters";
        # llama-70b-instruct is decommissioned on Groq).
        c = m["parameters"]["jsCode"]
        reps = [
            ('settings.openai_model || "gpt-4o-mini"', 'settings.groq_model || "qwen/qwen3.8-27b"'),
            ('  max_output_tokens: 2500,\n  instructions:\n',
             '  max_completion_tokens: 2500,\n'
             '  response_format: { type: "json_object" },\n'
             '  messages: [\n    {\n      role: "system",\n      content:\n'),
            ('must equal the number of rows returned.",',
             'must equal the number of rows returned. Return exactly this JSON shape and nothing else: '
             '{\\"email_subject\\": string, \\"email_html\\": string, \\"signal_count\\": integer, \\"rows\\": [{\\"symbol\\": string, '
             '\\"action\\": \\"BUY\\"|\\"SELL\\"|\\"DO_NOTHING\\"|\\"NO_DATA\\", \\"quantity\\": number, \\"limit_price\\": number|null, '
             '\\"current_price\\": number|null, \\"market_volume\\": number|null, \\"reason\\": string}]}. '
             'Output raw JSON with no markdown fences.",'),
            ('  input: JSON.stringify({\n',
             '    },\n    {\n      role: "user",\n      content: JSON.stringify({\n'),
        ]
        for old, new in reps:
            assert old in c, "Build Signals anchor missing: " + old[:50]
            c = c.replace(old, new, 1)
        c2 = re.sub(r"  \}\),\n  text: \{[\s\S]*?\n\};", "  })\n    }\n  ]\n};", c, count=1)
        assert c2 != c and "text: {" not in c2 and "messages: [" in c2 and "json_object" in c2, "Build Signals tail rewrite failed"
        m["parameters"]["jsCode"] = c2
    if m["name"] == "Extract Email":
        # Anthropic + chat-completions reply shapes (keep the OpenAI Responses branches for repo parity).
        c = m["parameters"]["jsCode"]
        anchor = "let outputText = null;\n"
        anth = (anchor + "\n"
                'if (!outputText && Array.isArray(response.content)) {\n'
                '  for (const contentItem of response.content) {\n'
                '    if (contentItem.type === "text" && typeof contentItem.text === "string") {\n'
                "      outputText = contentItem.text;\n      break;\n    }\n  }\n}\n"
                'if (!outputText && Array.isArray(response.choices) && response.choices.length > 0) {\n'
                '  const msg = response.choices[0].message;\n'
                '  if (msg && typeof msg.content === "string") outputText = msg.content;\n'
                "}\n")
        assert anchor in c, "Extract Email anchor missing"
        m["parameters"]["jsCode"] = c.replace(anchor, anth, 1)
    if m["name"] == "Send Signal Email":
        m["credentials"] = {"gmailOAuth2": {"id": "0e1IkEOGRZQdlHcF", "name": "Gmail for abdul.71433@iqra.edu.pk"}}
    sig["nodes"].append(m)
# schedule trigger with same outgoing wiring
conns = repo["connections"]
outs = conns.get(oldname, {}).get("main", [[], [], []])
sig["nodes"].append(sched("Schedule 15min", "*/15 9-15 * * 1-5", [80, 300]))
sig["connections"]["Schedule 15min"] = {"main": outs}
sig["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "manual-run", "name": "Manual Run", "position": [80, 460]})
sig["connections"]["Manual Run"] = {"main": outs}
# signal logging branch
flat = code_node("Flatten Signals",
    "const src=$json.signals||[];\nreturn src.map(s=>({json:{run_ts:$json.run_timestamp,symbol:s.symbol,action:s.action,quantity:s.quantity,limit_price:s.limit_price,current_price:s.current_price,change_pct:s.change_pct,trade_value:s.trade_value,reason:s.reason}}));",
    [1552, 240])
log = sheets_node("Log Signals", "append", copy.deepcopy(DOC), "Signals", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
log["position"] = [1776, 240]
sig["nodes"].append(flat); sig["nodes"].append(log)
# 2026-09-15 fix: Build Signals reads the watchlist via safeRows("Read Watchlist") but the
# node never existed, so safeRows' try/catch silently returned [] and the sim could never
# find a single BUY candidate. Add the read and wire the FULL execution chain - the patch
# below only carried trigger->Read Holdings plus the logging branch, leaving Read Cash,
# Read Settings, Fetch PSX, Build Signals' intake and the whole email leg disconnected.
psx_pos = next(n["position"] for n in sig["nodes"] if n["name"] == "Fetch PSX Market Watch")
wl_read = sheets_node("Read Watchlist", "read", copy.deepcopy(DOC), "Watchlist",
                      position=(psx_pos[0] - 220, psx_pos[1]))
wl_read["alwaysOutputData"] = True
sig["nodes"].append(wl_read)
connect(sig, "Read Holdings", ["Read Cash"])
connect(sig, "Read Cash", ["Read Settings"])
connect(sig, "Read Settings", ["Read Watchlist"])
connect(sig, "Read Watchlist", ["Fetch PSX Market Watch"])
connect(sig, "Fetch PSX Market Watch", ["Build Signals"])
connect(sig, "OpenAI Format Signals", ["Extract Email"])
connect(sig, "Extract Email", ["Send Signal Email"])
sig["connections"]["Build Signals"] = {"main": [[{"node": "OpenAI Format Signals", "type": "main", "index": 0}, {"node": "Flatten Signals", "type": "main", "index": 0}]]}
sig["connections"]["Flatten Signals"] = {"main": [[{"node": "Log Signals", "type": "main", "index": 0}]]}
sig["id"] = "psxsignal001"  # explicit id or n8n import inserts NULL id and fails
json.dump(sig, open(os.path.join(HERE, "psx_signals.json"), "w"), indent=1)
print("psx_signals.json:", len(sig["nodes"]), "nodes; outs from trigger:", [t["node"] for t in (outs[0] if outs and outs[0] else [])])

# ---------------- virtual trading dashboard (webhook page + data API) ----------------
# Same-origin design: page and data webhook both live under the n8n funnel host, so the
# page fetches its relative API path with zero CORS and zero external dependencies.
DASH_HTML = open(os.path.join(HERE, "dashboard.html"), encoding="utf-8").read()
assert not DASH_HTML.startswith("="), "dashboard.html must not start with '=' (n8n expression trigger)"
dash = {"id": "psxdash0001", "name": "PSX 6. Virtual Dashboard", "nodes": [], "connections": {},
        "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}, "active": False}
dash["nodes"] += [
    {"parameters": {"path": "psx-virtual-dashboard", "httpMethod": "GET", "responseMode": "responseNode", "options": {}},
     "type": "n8n-nodes-base.webhook", "typeVersion": 1.2, "webhookId": "d5a1e2f0-6f4a-4b8e-9c21-7d0e5a1b2c01",
     "id": "dash-page-webhook", "name": "Dashboard Page", "position": [-300, 340]},
    {"parameters": {"respondWith": "text", "responseBody": DASH_HTML,
                    "options": {"responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]}}},
     "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "id": "dash-page-respond", "name": "Respond Page", "position": [-60, 340]},
    {"parameters": {"path": "psx-virtual-dashboard-data", "httpMethod": "GET", "responseMode": "responseNode", "options": {}},
     "type": "n8n-nodes-base.webhook", "typeVersion": 1.2, "webhookId": "d5a1e2f0-6f4a-4b8e-9c21-7d0e5a1b2c02",
     "id": "dash-data-webhook", "name": "Data In", "position": [-300, 700]},
]
dash["connections"]["Dashboard Page"] = {"main": [[{"node": "Respond Page", "type": "main", "index": 0}]]}
TABS = ["Holding", "Cash", "Settings", "Watchlist", "Signals", "Trades", "State", "Equity"]
read_targets = []
for i, tab in enumerate(TABS):
    r = sheets_node("Read " + tab, "read", copy.deepcopy(DOC), tab, position=(-60, 420 + 150 * i))
    r["onError"] = "continueRegularOutput"
    t = code_node("Tag " + tab,
                  "return $input.all().map(i=>({json:{__tab:" + json.dumps(tab) + ",row:i.json}}));",
                  [180, 420 + 150 * i])
    dash["nodes"] += [r, t]
    read_targets.append({"node": r["name"], "type": "main", "index": 0})
    dash["connections"][r["name"]] = {"main": [[{"node": t["name"], "type": "main", "index": 0}]]}
    connecti(dash, t["name"], "Join Tabs", i)
dash["connections"]["Data In"] = {"main": [read_targets]}
dash["nodes"].append(merge_node("Join Tabs", len(TABS), [420, 1080]))
dash["nodes"].append(code_node("Assemble",
    "const out = {holding: [], cash: [], settings: [], watchlist: [], signals: [], trades: [], state: [], equity: []};\n"
    "for (const item of $input.all()) {\n"
    "  const j = item.json || {};\n"
    "  const k = String(j.__tab || '').toLowerCase();\n"
    "  if (out[k]) out[k].push(j.row);\n"
    "}\n"
    "return [{json: {fetched_at: new Date().toISOString(), ...out}}];", [640, 1080]))
dash["nodes"].append({"parameters": {"respondWith": "firstIncomingItem", "options": {}},
                      "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "id": "dash-data-respond",
                      "name": "Respond Data", "position": [860, 1080]})
dash["connections"]["Join Tabs"] = {"main": [[{"node": "Assemble", "type": "main", "index": 0}]]}
dash["connections"]["Assemble"] = {"main": [[{"node": "Respond Data", "type": "main", "index": 0}]]}
json.dump(dash, open(os.path.join(HERE, "psx_dashboard.json"), "w"), indent=1)
print("psx_dashboard.json:", len(dash["nodes"]), "nodes")

# ---------------- trader ----------------
tr = {"name": "PSX 3. Virtual Trader", "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}, "active": False}
tr["nodes"].append(sched("Schedule Trader", "7-59/15 9-15 * * 1-5", [0, 300]))
readstate = sheets_node("Read State", "read", copy.deepcopy(DOC), "State"); readstate["position"] = [220, 300]
readsig = sheets_node("Read Signals", "read", copy.deepcopy(DOC), "Signals"); readsig["position"] = [220, 480]
tr["nodes"] += [readstate, readsig]
jr = merge_node("Join Reads", 2, [440, 380]); tr["nodes"].append(jr)
connect(tr, "Schedule Trader", ["Read State", "Read Signals"])
tr["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "manual-run", "name": "Manual Run", "position": [0, 480]})
connect(tr, "Manual Run", ["Read State", "Read Signals"])
connecti(tr, "Read State", "Join Reads", 0); connecti(tr, "Read Signals", "Join Reads", 1)
decide = code_node("Decide", """const state={}; for (const it of $('Read State').all()) state[it.json.key]=it.json.value;
const end=new Date(state.end_date||'2026-09-19T15:30:00+05:00');
const sigs=$('Read Signals').all().map(i=>i.json).filter(r=>r.symbol);
const last=Number(state.last_row||1);
const fresh=sigs.filter(r=>Number(r.row_number||0)>last && ['BUY','SELL'].includes(r.action));
if (new Date()>=end || state.status!=='RUNNING') return [{json:{mode: state.status==='DONE'?'noop':'final'}, last_row:last, state}];
return [{json:{mode:'trade', last_row:last, max_row:Math.max(last,...sigs.map(r=>Number(r.row_number||0))), new_signals:fresh}}];""", [440, 300])
decide["executeOnce"] = True
tr["nodes"].append(decide); connect(tr, "Join Reads", ["Decide"])
route = {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": "={{ $json.mode }}", "rightValue": "trade", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "options": {}},
         "type": "n8n-nodes-base.if", "typeVersion": 2, "id": "is-trade", "name": "Is Trade Run", "position": [660, 300]}
tr["nodes"].append(route); connect(tr, "Decide", ["Is Trade Run"])
readcash = sheets_node("Read Cash", "read", copy.deepcopy(DOC), "Cash"); readcash["position"] = [880, 300]
readhold = sheets_node("Read Holding", "read", copy.deepcopy(DOC), "Holding"); readhold["position"] = [1020, 300]
# 2026-09-15 fix: on the first trade of the week the Holding tab is empty; a zero-item
# read would starve Apply Trades and silently drop the trade (and every later one).
readhold["alwaysOutputData"] = True
tr["nodes"] += [readcash, readhold]
connect(tr, "Is Trade Run", ["Read Cash"]); connect(tr, "Read Cash", ["Read Holding"])
apply_ = code_node("Apply Trades", """const run=$('Decide').first().json;
if (run.mode!=='trade') return [{json:{noop:true}}];
let cash=$('Read Cash').all().reduce((a,i)=>a+Number(i.json.amount||0),0);
const lots=$('Read Holding').all().map(i=>({symbol:i.json.symbol,lot_id:i.json.lot_id,shares:Number(i.json.shares||0),avg_price:Number(i.json.avg_price||0),max_trade_value:Number(i.json.max_trade_value||50000),lot_size:Number(i.json.lot_size||1)})).filter(l=>l.shares>0);
const trades=[];
for (const s of run.new_signals){
  const price=Number(s.current_price)||Number(s.limit_price)||0;
  const base={ts:s.run_ts||new Date().toISOString(),symbol:s.symbol};
  if (!(price>0)){trades.push({...base,side:'SKIP',quantity:0,price:0,value:0,cash_after:Math.round(cash*100)/100,note:'no price'});continue;}
  if (s.action==='BUY'){
    const qty=Math.floor(Number(s.quantity)||0);
    const cost=qty*price;
    if (qty<=0){trades.push({...base,side:'SKIP',quantity:0,price,value:0,cash_after:Math.round(cash*100)/100,note:'qty 0'});continue;}
    if (cost>cash){trades.push({...base,side:'SKIP',quantity:qty,price,value:cost,cash_after:Math.round(cash*100)/100,note:'insufficient cash'});continue;}
    lots.push({symbol:s.symbol,lot_id:'v'+Date.now()+Math.random().toString(36).slice(2,5),shares:qty,avg_price:price,max_trade_value:50000,lot_size:1});
    cash-=cost;
    trades.push({...base,side:'BUY',quantity:qty,price,value:Math.round(cost*100)/100,cash_after:Math.round(cash*100)/100,note:'auto'});
  } else if (s.action==='SELL'){
    const held=lots.filter(l=>l.symbol===s.symbol);
    const qty=held.reduce((a,l)=>a+l.shares,0);
    if (qty<=0){trades.push({...base,side:'SKIP',quantity:0,price,value:0,cash_after:Math.round(cash*100)/100,note:'no holding'});continue;}
    for (const l of held){lots.splice(lots.indexOf(l),1);}
    const value=qty*price; cash+=value;
    trades.push({...base,side:'SELL',quantity:qty,price,value:Math.round(value*100)/100,cash_after:Math.round(cash*100)/100,note:'auto'});
  }
}
return [{json:{lots,cash,trades,last_row:run.max_row}}];""", [1160, 300])
apply_["executeOnce"] = True
tr["nodes"].append(apply_)
# writers: trades, holding (clear+append full state), cash (clear+append), state (appendOrUpdate)
emit_t = code_node("Emit Trade Rows", "const t=$('Apply Trades').first().json.trades||[];\nreturn t.map(x=>({json:x}));", [1380, 140])
wt = sheets_node("Append Trades", "append", copy.deepcopy(DOC), "Trades", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); wt["position"] = [1600, 140]
cl_h = sheets_node("Clear Holding", "clear", copy.deepcopy(DOC), "Holding"); cl_h["position"] = [1380, 380]
emit_h = code_node("Emit Lot Rows", "const l=$('Apply Trades').first().json.lots||[];\nreturn l.map(x=>({json:x}));", [1600, 380])
ap_h = sheets_node("Append Holding", "append", copy.deepcopy(DOC), "Holding", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_h["position"] = [1820, 380]
cl_c = sheets_node("Clear Cash", "clear", copy.deepcopy(DOC), "Cash"); cl_c["position"] = [2040, 380]
emit_c = code_node("Cash Row", "return [{json:{amount: String($('Apply Trades').first().json.cash)}}];", [2260, 260])
ap_c = sheets_node("Append Cash", "append", copy.deepcopy(DOC), "Cash", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_c["position"] = [2480, 260]
up_s = sheets_node("Update State", "appendOrUpdate", copy.deepcopy(DOC), "State", {"mappingMode": "defineBelow", "value": {"key": "last_row", "value": "={{ $('Apply Trades').first().json.last_row }}"}, "matchingColumns": ["key"], "schema": []}); up_s["position"] = [2700, 380]
tr["nodes"] += [emit_t, wt, cl_h, emit_h, ap_h, cl_c, emit_c, ap_c, up_s]
connect(tr, "Read Holding", ["Apply Trades"])
connect(tr, "Apply Trades", ["Emit Trade Rows", "Clear Holding"])
connect(tr, "Emit Trade Rows", ["Append Trades"])
# 2026-09-15 fix: the tail used to be Append Holding -> Clear Cash -> ... -> Update State,
# a chain that emits zero items whenever the book has no lots (sell-ALL trail exits and
# no-action runs). That starved the cash rewrite AND the last_row cursor: after a full
# liquidation the Holding tab was wiped without cash being credited, and stale BUY/SELL
# rows stayed eligible forever. All bookkeeping now hangs off Clear Holding, which always
# emits exactly one item; Emit Lot Rows -> Append Holding stays a leaf that writes nothing
# when there are no lots. Every branch is idempotent, so running it on no-action runs is
# a harmless rewrite of unchanged values.
connect(tr, "Clear Holding", ["Emit Lot Rows", "Clear Cash", "Update State"])
connect(tr, "Emit Lot Rows", ["Append Holding"])
connect(tr, "Clear Cash", ["Cash Row"]); connect(tr, "Cash Row", ["Append Cash"])
tr["id"] = "psxtrader001"
json.dump(tr, open(os.path.join(HERE, "psx_trader.json"), "w"), indent=1)
print("psx_trader.json:", len(tr["nodes"]), "nodes")

# ---------------- EOD valuation / final liquidation ----------------
PARSER = r"""
function toNumber(v,f=0){if(v===null||v===undefined)return f;const c=String(v).replace(/,/g,'').replace(/%/g,'').replace(/[^\d.-]/g,'').trim();if(c===''||c==='-'||c==='.')return f;const n=Number(c);return Number.isFinite(n)?n:f;}
function cleanHtml(v){return String(v||'').replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&#37;/g,'%').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();}
function parseMarket(raw){const rows={};const trs=String(raw||'').match(/<tr[\s\S]*?<\/tr>/gi)||[];
for(const tr of trs){const cells=[...tr.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(m=>cleanHtml(m[1])).filter(c=>c!=='');if(cells.length<8)continue;const sym=String(cells[0]||'').trim().toUpperCase().split(/\s+/)[0];if(!sym||sym==='SYMBOL')continue;const cur=toNumber(cells[cells.length-4],null);if(cur)rows[sym]=cur;}
return rows;}
"""
eod = {"name": "PSX 4. EOD Valuation", "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}, "active": False}
eod["nodes"].append(sched("Schedule EOD", "35 15 * * 1-5", [0, 300]))
rs = sheets_node("Read State", "read", copy.deepcopy(DOC), "State"); rs["position"] = [220, 300]
eod["nodes"].append(rs); connect(eod, "Schedule EOD", ["Read State"])
eod["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "manual-run", "name": "Manual Run", "position": [0, 480]})
connect(eod, "Manual Run", ["Read State"])
gate = code_node("Gate", """const state={}; for (const it of $('Read State').all()) state[it.json.key]=it.json.value;
const end=new Date(state.end_date||'2026-09-19T15:30:00+05:00');
const past=new Date()>=end;
return [{json:{mode: past ? (state.status==='DONE'?'noop':'final') : 'value', state}}];""", [440, 300])
gate["executeOnce"] = True
eod["nodes"].append(gate); connect(eod, "Read State", ["Gate"])
eod["nodes"].append(http_psx("Fetch PSX"))
fetch = eod["nodes"][-1]; fetch["position"] = [660, 500]
readh = sheets_node("Read Holding", "read", copy.deepcopy(DOC), "Holding"); readh["position"] = [660, 200]
readc = sheets_node("Read Cash", "read", copy.deepcopy(DOC), "Cash"); readc["position"] = [660, 680]
eod["nodes"] += [readh, readc]
jd = merge_node("Join Data", 3, [880, 560]); eod["nodes"].append(jd)
connect(eod, "Gate", ["Fetch PSX", "Read Holding", "Read Cash"])
connecti(eod, "Fetch PSX", "Join Data", 0); connecti(eod, "Read Holding", "Join Data", 1); connecti(eod, "Read Cash", "Join Data", 2)
val = code_node("Value Portfolio", PARSER + """
const mode=$('Gate').first().json.mode;
const market=parseMarket($json.body||'');
const cash=$('Read Cash').all().reduce((a,i)=>a+Number(i.json.amount||0),0);
const lots=$('Read Holding').all().map(i=>({symbol:i.json.symbol,lot_id:i.json.lot_id,shares:Number(i.json.shares||0),avg_price:Number(i.json.avg_price||0)})).filter(l=>l.shares>0);
let hv=0; const valuations=[];
for (const l of lots){const p=market[l.symbol]||l.avg_price;hv+=l.shares*p;valuations.push({symbol:l.symbol,shares:l.shares,price:p,value:Math.round(l.shares*p*100)/100});}
hv=Math.round(hv*100)/100;
return [{json:{mode,cash,holdings_value:hv,portfolio_value:Math.round((cash+hv)*100)/100,lots,valuations,market_found:Object.keys(market).length}}];""", [880, 400])
val["executeOnce"] = True
eod["nodes"].append(val); connect(eod, "Join Data", ["Value Portfolio"])
eq_row = code_node("Equity Row", "const v=$('Value Portfolio').first().json;\nreturn [{json:{ts:new Date().toISOString(),cash:v.cash,holdings_value:v.holdings_value,portfolio_value:v.portfolio_value,notes:v.mode}}];", [1100, 140])
eod["nodes"].append(eq_row)
ap_eq = sheets_node("Append Equity", "append", copy.deepcopy(DOC), "Equity", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_eq["position"] = [1320, 140]
eod["nodes"].append(ap_eq); connect(eod, "Value Portfolio", ["Equity Row"]); connect(eod, "Equity Row", ["Append Equity"])
fin = code_node("Build Liquidation", """const v=$('Value Portfolio').first().json;
if (v.mode!=='final') return [];
const cash=v.cash; const trades=[]; const proceeds=[];
for (const val of v.valuations){const value=val.value;proceeds.push(value);trades.push({ts:new Date().toISOString(),symbol:val.symbol,side:'SELL',quantity:val.shares,price:val.price,value,cash_after:0,note:'final liquidation'});}
let c=cash; for (const p of proceeds){c+=p;}
const fixed=trades.map(t=>({...t,cash_after:Math.round(c*100)/100}));
return [{json:{trades:fixed,final_cash:Math.round(c*100)/100,final_value:Math.round(c*100)/100}}];""", [1100, 500])
eod["nodes"].append(fin)
ftr = code_node("Emit Final Trades", "return (($('Build Liquidation').first().json||{}).trades||[]).map(t=>({json:t}));", [1100, 640])
eod["nodes"].append(ftr); connect(eod, "Build Liquidation", ["Emit Final Trades"])
ap_tr = sheets_node("Append Final Trades", "append", copy.deepcopy(DOC), "Trades", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_tr["position"] = [1320, 500]
eod["nodes"].append(ap_tr); connect(eod, "Emit Final Trades", ["Append Final Trades"])
cl_h2 = sheets_node("Clear Holding Final", "clear", copy.deepcopy(DOC), "Holding"); cl_h2["position"] = [1540, 500]
eod["nodes"].append(cl_h2); connect(eod, "Append Final Trades", ["Clear Holding Final"])
fcr = code_node("Final Cash Row", "return [{json:{amount: String($('Build Liquidation').first().json.final_cash)}}];", [1760, 640])
eod["nodes"].append(fcr); connect(eod, "Clear Holding Final", ["Final Cash Row"])
ap_c2 = sheets_node("Append Final Cash", "append", copy.deepcopy(DOC), "Cash", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_c2["position"] = [1980, 640]
eod["nodes"].append(ap_c2); connect(eod, "Final Cash Row", ["Append Final Cash"])
feq_row = code_node("Final Equity Row", "const v=$('Build Liquidation').first().json;\nreturn [{json:{ts:new Date().toISOString(),cash:v.final_cash,holdings_value:0,portfolio_value:v.final_value,notes:'FINAL'}}];", [2200, 640])
eod["nodes"].append(feq_row); connect(eod, "Append Final Cash", ["Final Equity Row"])
ap_eq2 = sheets_node("Append Final Equity", "append", copy.deepcopy(DOC), "Equity", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); ap_eq2["position"] = [2420, 640]
eod["nodes"].append(ap_eq2); connect(eod, "Final Equity Row", ["Append Final Equity"])
done = sheets_node("Mark Done", "appendOrUpdate", copy.deepcopy(DOC), "State", {"mappingMode": "defineBelow", "value": {"key": "status", "value": "DONE"}, "matchingColumns": ["key"], "schema": []}); done["position"] = [2200, 500]
eod["nodes"].append(done); connect(eod, "Append Final Equity", ["Mark Done"])
eod["id"] = "psxeod00001"
json.dump(eod, open(os.path.join(HERE, "psx_eod.json"), "w"), indent=1)
print("psx_eod.json:", len(eod["nodes"]), "nodes")

# ---------------- reset utility ----------------
rst = {"name": "PSX 5. Reset Virtual Book", "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"}}
rst["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "go", "name": "Go", "position": [80, 300]})
prev = "Go"
for tab in TABS:
    n = sheets_node("Clear " + tab, "clear", copy.deepcopy(DOC), tab); n["position"] = [280 + 120 * len(rst["nodes"]), 300]
    rst["nodes"].append(n); connect(rst, prev, [n["name"]]); prev = n["name"]
HEADERS = {
    "Holding": {"symbol": "symbol", "lot_id": "lot_id", "shares": "shares", "avg_price": "avg_price", "max_trade_value": "max_trade_value", "lot_size": "lot_size"},
    "Cash": {"amount": "amount"}, "Settings": {"key": "key", "value": "value"},
    "Watchlist": {"symbol": "symbol", "max_trade_value": "max_trade_value", "lot_size": "lot_size"},
    "Signals": {"run_ts": "run_ts", "symbol": "symbol", "action": "action", "quantity": "quantity", "limit_price": "limit_price", "current_price": "current_price", "change_pct": "change_pct", "trade_value": "trade_value", "reason": "reason"},
    "Trades": {"ts": "ts", "symbol": "symbol", "side": "side", "quantity": "quantity", "price": "price", "value": "value", "cash_after": "cash_after", "note": "note"},
    "State": {"key": "key", "value": "value"},
    "Equity": {"ts": "ts", "cash": "cash", "holdings_value": "holdings_value", "portfolio_value": "portfolio_value", "notes": "notes"},
}
sr = code_node("Settings Rows", "const rows=" + json.dumps([{"key": k, "value": str(v)} for k, v in SETTINGS]) + ";\nreturn rows.map(r=>({json:r}));")
sr["position"] = [280 + 120 * len(rst["nodes"]), 500]; rst["nodes"].append(sr); connect(rst, prev, ["Settings Rows"])
n = sheets_node("Seed Settings", "append", copy.deepcopy(DOC), "Settings", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n["position"] = [280 + 120 * len(rst["nodes"]), 500]; rst["nodes"].append(n); connect(rst, "Settings Rows", ["Seed Settings"]); prev = "Seed Settings"
wr = code_node("Watchlist Rows", "const syms=" + json.dumps(WATCHLIST) + ";\nreturn syms.map(s=>({json:{symbol:s,max_trade_value:50000,lot_size:1}}));")
wr["position"] = [280 + 120 * len(rst["nodes"]), 650]; rst["nodes"].append(wr); connect(rst, prev, ["Watchlist Rows"])
n = sheets_node("Seed Watchlist", "append", copy.deepcopy(DOC), "Watchlist", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n["position"] = [280 + 120 * len(rst["nodes"]), 650]; rst["nodes"].append(n); connect(rst, "Watchlist Rows", ["Seed Watchlist"]); prev = "Seed Watchlist"
cr = code_node("Cash Row", "return [{json:{amount:'500000'}}];")
cr["position"] = [280 + 120 * len(rst["nodes"]), 800]; rst["nodes"].append(cr); connect(rst, prev, ["Cash Row"])
n = sheets_node("Seed Cash", "append", copy.deepcopy(DOC), "Cash", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n["position"] = [280 + 120 * len(rst["nodes"]), 800]; rst["nodes"].append(n); connect(rst, "Cash Row", ["Seed Cash"]); prev = "Seed Cash"
st = code_node("State Rows", "return [{json:{key:'end_date',value:'2026-09-19T15:30:00+05:00'}},{json:{key:'last_row',value:'1'}},{json:{key:'status',value:'RUNNING'}},{json:{key:'start_value',value:'500000'}},{json:{key:'started',value:'2026-09-12'}}];")
st["position"] = [280 + 120 * len(rst["nodes"]), 950]; rst["nodes"].append(st); connect(rst, prev, ["State Rows"])
n = sheets_node("Seed State", "append", copy.deepcopy(DOC), "State", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
n["position"] = [280 + 120 * len(rst["nodes"]), 950]; rst["nodes"].append(n); connect(rst, "State Rows", ["Seed State"])
rst["id"] = "psxreset001"
json.dump(rst, open(os.path.join(HERE, "psx_reset.json"), "w"), indent=1)
print("psx_reset.json:", len(rst["nodes"]), "nodes")
print("ALL BUILT")
