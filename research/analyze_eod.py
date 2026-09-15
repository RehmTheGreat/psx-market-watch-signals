import json, glob, statistics, os

BASE = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\eod_history"
rows = []  # (sym, ts, close, volume, open)
for f in glob.glob(os.path.join(BASE, "*.json")):
    sym = os.path.splitext(os.path.basename(f))[0]
    try:
        d = json.load(open(f, encoding="utf-8"))["data"]
    except Exception:
        continue
    # descending by date; flip to ascending
    for r in reversed(d):
        if len(r) >= 4:
            rows.append((sym, r[0], float(r[1]), float(r[2]), float(r[3])))

print("symbols:", len(set(r[0] for r in rows)), "| day rows:", len(rows))

# per-day metrics
oc = []      # |close-open|/open
hl = []      # (high-low)/open  -- NOTE: no high/low in timeseries! skip
ho = []      # can't compute either. Use open->close only + prev-close relations.
byday = {}
for sym, ts, c, v, o in rows:
    if o > 0:
        oc.append(abs(c - o) / o * 100)
        byday.setdefault(sym, []).append((ts, o, c, v))

oc.sort()
def pct(a, p):
    return a[min(len(a)-1, int(len(a)*p))]
print("\n|close-open|/open %% distribution (all liquid KSE100/KMI30, 5y):")
print("  p10=%.2f p25=%.2f p50=%.2f p75=%.2f p90=%.2f mean=%.2f" % (pct(oc,.1), pct(oc,.25), pct(oc,.5), pct(oc,.75), pct(oc,.9), sum(oc)/len(oc)))
print("  days with |OC|>0.3%%: %.1f%%  >0.5%%: %.1f%%  >1%%: %.1f%%" % (
    100*sum(1 for x in oc if x>0.3)/len(oc), 100*sum(1 for x in oc if x>0.5)/len(oc), 100*sum(1 for x in oc if x>1)/len(oc)))

# continuation: yesterday's close-to-close change vs today's open->close
print("\ncontinuation test: yesterday +X%% close/close -> today open->close mean (in %%)")
syms = {}
for sym, series in byday.items():
    series.sort()
    syms[sym] = series
buckets = {"<-1": [], "-1..0": [], "0..1": [], "1..2": [], ">2": []}
for sym, series in syms.items():
    for i in range(1, len(series)):
        _, o_prev, c_prev, _ = series[i-1]
        _, o, c, v = series[i]
        if o_prev <= 0 or o <= 0: continue
        yday = (c_prev/o_prev - 1) * 100      # yesterday's open->close
        today = (c/o - 1) * 100               # today's open->close
        if yday < -1: buckets["<-1"].append(today)
        elif yday < 0: buckets["-1..0"].append(today)
        elif yday < 1: buckets["0..1"].append(today)
        elif yday < 2: buckets["1..2"].append(today)
        else: buckets[">2"].append(today)
for k, arr in buckets.items():
    if arr: print("  prev OC %-6s n=%-7d mean today OC=%+.3f%%  win%%=%.1f" % (k, len(arr), sum(arr)/len(arr), 100*sum(1 for x in arr if x>0)/len(arr)))

# gap continuation: today's OPEN gap vs prev close -> today open->close
print("\ngap test: open gap vs prev close -> today open->close mean (in %%)")
gb = {"<-1": [], "-1..0": [], "0..1": [], "1..2": [], ">2": []}
for sym, series in syms.items():
    for i in range(1, len(series)):
        _, _, c_prev, _ = series[i-1]
        _, o, c, v = series[i]
        if c_prev <= 0 or o <= 0: continue
        gap = (o/c_prev - 1) * 100
        oc_today = (c/o - 1) * 100
        if gap < -1: gb["<-1"].append(oc_today)
        elif gap < 0: gb["-1..0"].append(oc_today)
        elif gap < 1: gb["0..1"].append(oc_today)
        elif gap < 2: gb["1..2"].append(oc_today)
        else: gb[">2"].append(oc_today)
for k, arr in gb.items():
    if arr: print("  gap %-6s n=%-7d mean OC=%+.3f%%  win%%=%.1f" % (k, len(arr), sum(arr)/len(arr), 100*sum(1 for x in arr if x>0)/len(arr)))

# relative-volume effect: volume vs symbol's median volume -> today OC (momentum proxy for pace)
print("\nvolume pace (vs own median) -> same-day OC mean:")
vb = {"<0.7": [], "0.7..1.5": [], ">1.5": []}
for sym, series in syms.items():
    vols = sorted(x[3] for x in series)
    med = vols[len(vols)//2] if vols else 0
    for _, o, c, v in series:
        if med <= 0 or o <= 0: continue
        oc_today = (c/o - 1) * 100
        ratio = v / med
        if ratio < 0.7: vb["<0.7"].append(oc_today)
        elif ratio <= 1.5: vb["0.7..1.5"].append(oc_today)
        else: vb[">1.5"].append(oc_today)
for k, arr in vb.items():
    if arr: print("  vol %-9s n=%-7d mean OC=%+.3f%%  win%%=%.1f" % (k, len(arr), sum(arr)/len(arr), 100*sum(1 for x in arr if x>0)/len(arr)))

# turnover today distribution (close*volume) to set liquidity gates
tv = sorted(c*v/1e6 for _, _, c, v, _ in [(r[0], r[1], r[2], r[3], r[4]) for r in rows])
print("\ntraded value (PKR m) per symbol-day: p10=%.0f p25=%.0f p50=%.0f p75=%.0f p90=%.0f" % (pct(tv,.1), pct(tv,.25), pct(tv,.5), pct(tv,.75), pct(tv,.9)))
print("share of symbol-days with TV>25m: %.1f%%  >50m: %.1f%%  >100m: %.1f%%" % (
    100*sum(1 for x in tv if x>25)/len(tv), 100*sum(1 for x in tv if x>50)/len(tv), 100*sum(1 for x in tv if x>100)/len(tv)))

# last 1y only, same continuation numbers (recency check)
import time
cutoff = time.time() - 365*86400
b2 = {"<-1": [], "0..1": [], "1..2": [], ">2": []}
for sym, series in syms.items():
    for i in range(1, len(series)):
        _, o_prev, c_prev, _ = series[i-1]
        _, o, c, v = series[i]
        if series[i][0] < cutoff*1000 or o <= 0 or o_prev <= 0: continue
        yday = (c_prev/o_prev - 1) * 100
        today = (c/o - 1) * 100
        if yday < -1: b2["<-1"].append(today)
        elif yday < 1: b2["0..1"].append(today)
        elif yday < 2: b2["1..2"].append(today)
        else: b2[">2"].append(today)
print("\nlast-1y continuation (prev open->close -> today open->close):")
for k, arr in b2.items():
    if arr: print("  prev OC %-6s n=%-6d mean today OC=%+.3f%%  win%%=%.1f" % (k, len(arr), sum(arr)/len(arr), 100*sum(1 for x in arr if x>0)/len(arr)))
