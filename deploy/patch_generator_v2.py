import re

P = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\deploy\build_workflows.py"
s = open(P, encoding="utf-8").read()

# --- A: Build Signals repo patch block -> skip (engine_v1.js loaded instead) ---
start = s.index('    if m["name"] == "Build Signals":')
end_marker = '        m["parameters"]["jsCode"] = c2\n'
end = s.index(end_marker, start) + len(end_marker)
s = s[:start] + '    if m["name"] == "Build Signals":\n        continue  # 2026-09-15: replaced wholesale by engine_v1.js (loaded below)\n' + s[end:]

# --- B: load engine after the repo loop (before trigger wiring) ---
anchor = '# schedule trigger with same outgoing wiring'
assert anchor in s
engine_block = '''# 2026-09-15: intraday capitalizer engine (see research/STRATEGY_SPEC.md)
engine = code_node("Build Signals", open(os.path.join(HERE, "engine_v1.js"), encoding="utf-8").read(), [900, 600])
sig["nodes"].append(engine)

'''
s = s.replace(anchor, engine_block + anchor, 1)

# --- C: trigger outs no longer needed for wiring (Gate is the target now) ---
old_trig = '''conns = repo["connections"]
outs = conns.get(oldname, {}).get("main", [[], [], []])
sig["nodes"].append(sched("Schedule 15min", "*/15 9-15 * * 1-5", [80, 300]))
sig["connections"]["Schedule 15min"] = {"main": outs}
sig["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "manual-run", "name": "Manual Run", "position": [80, 460]})
sig["connections"]["Manual Run"] = {"main": outs}'''
new_trig = '''sig["nodes"].append(sched("Schedule 15min", "*/15 9-15 * * 1-5", [80, 300]))
sig["nodes"].append({"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "id": "manual-run", "name": "Manual Run", "position": [80, 460]})'''
assert old_trig in s
s = s.replace(old_trig, new_trig, 1)

# --- D: 5->6 merge inputs + Read Cache node ---
old_head = '''psx_pos = next(n["position"] for n in sig["nodes"] if n["name"] == "Fetch PSX Market Watch")
wl_read = sheets_node("Read Watchlist", "read", copy.deepcopy(DOC), "Watchlist",
                      position=(psx_pos[0] - 220, psx_pos[1] + 200))
wl_read["alwaysOutputData"] = True
sig["nodes"].append(wl_read)
join = merge_node("Join Inputs", 5, (psx_pos[0] + 260, psx_pos[1] + 200))
sig["nodes"].append(join)
HEAD_READS = ["Read Holdings", "Read Cash", "Read Settings", "Read Watchlist"]
for i, nm in enumerate(HEAD_READS):
    connecti(sig, nm, "Join Inputs", i)
connecti(sig, "Fetch PSX Market Watch", "Join Inputs", 4)
connect(sig, "Gate", HEAD_READS + ["Fetch PSX Market Watch"])
connect(sig, "Join Inputs", ["Build Signals"])
connect(sig, "OpenAI Format Signals", ["Extract Email"])
connect(sig, "Extract Email", ["Send Signal Email"])
sig["connections"]["Build Signals"] = {"main": [[{"node": "OpenAI Format Signals", "type": "main", "index": 0}, {"node": "Flatten Signals", "type": "main", "index": 0}]]}
sig["connections"]["Flatten Signals"] = {"main": [[{"node": "Log Signals", "type": "main", "index": 0}]]}'''
new_head = '''psx_pos = next(n["position"] for n in sig["nodes"] if n["name"] == "Fetch PSX Market Watch")
wl_read = sheets_node("Read Watchlist", "read", copy.deepcopy(DOC), "Watchlist",
                      position=(psx_pos[0] - 220, psx_pos[1] + 200))
wl_read["alwaysOutputData"] = True
sig["nodes"].append(wl_read)
rc = sheets_node("Read Cache", "read", copy.deepcopy(DOC), "MktCache",
                 position=(psx_pos[0] - 220, psx_pos[1] + 400))
rc["alwaysOutputData"] = True
sig["nodes"].append(rc)
join = merge_node("Join Inputs", 6, (psx_pos[0] + 260, psx_pos[1] + 200))
sig["nodes"].append(join)
HEAD_READS = ["Read Holdings", "Read Cash", "Read Settings", "Read Watchlist", "Read Cache"]
for i, nm in enumerate(HEAD_READS):
    connecti(sig, nm, "Join Inputs", i)
connecti(sig, "Fetch PSX Market Watch", "Join Inputs", 5)
connect(sig, "Gate", HEAD_READS + ["Fetch PSX Market Watch"])
connect(sig, "Join Inputs", ["Build Signals"])
# email only when the run produced actionable signals (kills 28x/day no-action spam)
has_action = {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
               "conditions": [{"leftValue": "={{ $json.actionable_count }}", "rightValue": 0,
                               "operator": {"type": "number", "operation": "gt"}}], "combinator": "and"}, "options": {}},
              "type": "n8n-nodes-base.if", "typeVersion": 2, "id": "has-action", "name": "Has Action", "position": [1180, 300]}
sig["nodes"].append(has_action)
# per-run market cache write-back (feeds velocity on the next run)
emit_cache = code_node("Emit Cache", "const rows=$('Build Signals').first().json.cache_rows||[];\\nreturn rows.map(r=>({json:r}));", [1400, 460])
sig["nodes"].append(emit_cache)
clear_mc = sheets_node("Clear MktCache", "clear", copy.deepcopy(DOC), "MktCache"); clear_mc["position"] = [1620, 460]
append_mc = sheets_node("Append MktCache", "append", copy.deepcopy(DOC), "MktCache", {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}); append_mc["position"] = [1840, 460]
sig["nodes"] += [clear_mc, append_mc]
connect(sig, "Build Signals", ["Has Action", "Flatten Signals", "Emit Cache"])
connect(sig, "Has Action", ["OpenAI Format Signals"])
connect(sig, "Emit Cache", ["Clear MktCache"]); connect(sig, "Clear MktCache", ["Append MktCache"])
connect(sig, "OpenAI Format Signals", ["Extract Email"])
connect(sig, "Extract Email", ["Send Signal Email"])
sig["connections"]["Flatten Signals"] = {"main": [[{"node": "Log Signals", "type": "main", "index": 0}]]}'''
assert old_head in s
s = s.replace(old_head, new_head, 1)

# --- E: bootstrap tabs + schema for MktCache; settings seeds ---
s = s.replace('TABS = ["Holding", "Cash", "Settings", "Watchlist", "Signals", "Trades", "State", "Equity"]',
              'TABS = ["Holding", "Cash", "Settings", "Watchlist", "Signals", "Trades", "State", "Equity", "MktCache"]', 1)
s = s.replace('"State": ["key", "value"],',
              '"State": ["key", "value"], "MktCache": ["symbol", "current", "volume", "ts"],', 1)
s = s.replace('("circuit_breaker_pct", 10), ("stop_loss_pct", 7), ("max_position_pct_of_portfolio", 75),',
              '("circuit_breaker_pct", 10), ("stop_loss_pct", 1.5), ("max_position_pct_of_portfolio", 75),\n    ("take_profit_arm_pct", 1.5), ("trail_from_high_pct", 0.8), ("max_open_positions", 5),\n    ("eod_flat", "TRUE"), ("round_trip_cost_bps", 12), ("cgt_pct", 15), ("cash_floor_pct", 20),\n    ("min_turnover_m", 25), ("big_turnover_m", 50), ("max_band_dist_pct", 7), ("min_price", 5),', 1)

open(P, "w", encoding="utf-8").write(s)
print("generator patched (signals engine + cache + email gate + tabs + settings)")
