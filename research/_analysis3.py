# Round 3: stability of reversion edge, breadth gate, tick structure completion.
import json, os, math, statistics as st, datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
EOD = os.path.join(BASE, "eod_history")

def load(sym):
    d = json.load(open(os.path.join(EOD, sym + ".json")))
    return sorted(d.get("data") or [])

syms = [f[:-5] for f in os.listdir(EOD) if f.endswith(".json")]
data = {s: load(s) for s in syms if len(load(s)) >= 260}
W = 0.12
def ok(x): return abs(x) <= W

def med20(rows, i):
    return st.median(r[2]*r[1] for r in rows[max(0, i-20):i])

# ---- 1. down-gap bounce: per-symbol breadth, halves, sub-buckets ----
print("== down-gap (-8%,-3%] bounce stability (turn20>=100M, winsorized) ==")
vals, bysym, halves = [], defaultdict(list), [[], []]
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        if med20(rows, i) < 1e8: continue
        g = o/pc-1
        if -0.08 < g <= -0.03:
            q = c/o-1
            if not ok(q) or not ok(g): continue
            vals.append(q); bysym[s].append(q)
            halves[0 if ts < 1735689600 else 1].append(q)
m, sd, n = st.mean(vals), st.stdev(vals), len(vals)
print(f"overall: n={n}, mean={m*100:.3f}%, sd={sd*100:.2f}%, t={m/(sd/math.sqrt(n)):.1f}, "
      f"hit(close>open)={sum(1 for x in vals if x>0)/n*100:.0f}%")
for lab, h in [("2021-2024", halves[0]), ("2025-2026", halves[1])]:
    if h: print(f"  {lab}: n={len(h)}, mean={st.mean(h)*100:.3f}%")
print(f"  symbols contributing: {len(bysym)}, median per-symbol mean: "
      f"{st.median([st.mean(v) for v in bysym.values() if len(v)>=5])*100:.3f}%  "
      f"(symbols with positive mean: {sum(1 for v in bysym.values() if len(v)>=5 and st.mean(v)>0)}/"
      f"{sum(1 for v in bysym.values() if len(v)>=5)})")

print("\n== finer down-gap buckets ==")
for lo, hi, lab in [(-0.03,-0.02,"(-3%,-2%]"), (-0.02,-0.015,"(-2%,-1.5%]"),
                    (-0.015,-0.01,"(-1.5%,-1%]"), (-0.05,-0.03,"(-5%,-3%]"), (-0.08,-0.05,"(-8%,-5%]")]:
    vv = []
    for s, rows in data.items():
        for i in range(21, len(rows)):
            ts, c, v, o = rows[i]; pc = rows[i-1][1]
            if pc in (None, 0) or o in (0, None) or med20(rows, i) < 1e8: continue
            g = o/pc-1
            if lo < g <= hi:
                q = c/o-1
                if ok(q) and ok(g): vv.append(q)
    if vv:
        m2 = st.mean(vv); t2 = m2/(st.stdev(vv)/math.sqrt(len(vv)))
        print(f"gap {lab}: n={len(vv)}, mean={m2*100:.3f}%, t={t2:.1f}, hit={sum(1 for x in vv if x>0)/len(vv)*100:.0f}%")

# ---- 2. combined signal: prev-day down + today down/flat gap ----
print("\n== combined reversion conditions (turn20>=100M, winsorized) ==")
def cond(lab, fn):
    vv = []
    for s, rows in data.items():
        for i in range(21, len(rows)):
            ts, c, v, o = rows[i]; pc = rows[i-1][1]
            if pc in (None, 0) or o in (0, None) or med20(rows, i) < 1e8 or i < 2: continue
            prev = rows[i-1][1]/rows[i-2][1]-1
            g = o/pc-1
            q = c/o-1
            if not ok(q): continue
            if fn(prev, g, rows, i): vv.append(q)
    if vv:
        m2 = st.mean(vv); t2 = m2/(st.stdev(vv)/math.sqrt(len(vv)))
        print(f"{lab}: n={len(vv)}, mean={m2*100:.3f}%, t={t2:.1f}, hit={sum(1 for x in vv if x>0)/len(vv)*100:.0f}%")
cond("prev<=-3% & gap in (-6%,-0.5%]", lambda p,g,r,i: p <= -0.03 and -0.06 < g <= -0.005)
cond("prev<=-3% & |gap|<3%", lambda p,g,r,i: p <= -0.03 and abs(g) < 0.03)
cond("prev>=+3% & |gap|<3%", lambda p,g,r,i: p >= 0.03 and abs(g) < 0.03)
cond("gap down only (>-6%,<=-1.5%]", lambda p,g,r,i: -0.06 < g <= -0.015)
cond("prev<=-4% & gap<=0", lambda p,g,r,i: p <= -0.04 and g <= 0)
cond("prev<=-4% & gap<=0 & day>=250M turn", lambda p,g,r,i: p <= -0.04 and g <= 0 and med20(r,i) >= 2.5e8)

# ---- 3. breadth regime gate: prev-day breadth -> today o2c (clean, no lookahead) ----
# breadth per ts: fraction of liquid names with close>prev close, computed across dataset
day_close_up = defaultdict(lambda: [0, 0])
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0): continue
        day_close_up[ts][1] += 1
        if c > pc: day_close_up[ts][0] += 1
breadth = {ts: a/b for ts, (a, b) in day_close_up.items() if b >= 20}
kts = sorted(breadth)
import bisect
def prev_breadth(ts):
    pos = bisect.bisect_left(kts, ts)
    return breadth[kts[pos-1]] if pos > 0 else None

print("\n== today o2c by PREV-day breadth (liquid names, winsorized) ==")
breg = defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None) or med20(rows, i) < 1e8: continue
        q = c/o-1
        if not ok(q): continue
        pb = prev_breadth(ts)
        if pb is None: continue
        b = "<20%" if pb < .2 else "20-40%" if pb < .4 else "40-60%" if pb < .6 else "60-80%" if pb < .8 else ">=80%"
        breg[b].append(q)
for b in ["<20%", "20-40%", "40-60%", "60-80%", ">=80%"]:
    vv = breg[b]
    print(f"prev breadth {b}: n={len(vv)}, o2c mean={st.mean(vv)*100:.3f}%, "
          f"down-gap bounce mean={st.mean([x for x in vv if x>-.12])*1:.4f}")
# down-gap bounce within bad breadth
vv_bad, vv_good = [], []
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None) or med20(rows, i) < 1e8: continue
        g, q = o/pc-1, c/o-1
        if not (-0.06 < g <= -0.015 and ok(q)): continue
        pb = prev_breadth(ts)
        if pb is None: continue
        (vv_bad if pb < 0.3 else vv_good).append(q)
for lab, vv in [("bounce w/ prev breadth<30%", vv_bad), ("bounce w/ prev breadth>=30%", vv_good)]:
    if vv: print(f"{lab}: n={len(vv)}, mean={st.mean(vv)*100:.3f}%")

# ---- 4. tick structure completion ----
print("\n== intraday ticks 2026-09-15 (10 liquid names) ==")
tickdir = os.path.join(BASE, "intraday_history")
buckets = defaultdict(list); mom = []; cap = []; ranges = []
for f in os.listdir(tickdir):
    sym = f.split("_")[0]
    ticks = sorted(json.load(open(os.path.join(tickdir, f)))["data"])
    series = [((ts % 86400)/60.0, p) for ts, p, v in ticks]
    binned = {}
    for mts, p in series: binned[int(mts//15)*15] = p
    bs = sorted(binned)
    rets = [math.log(binned[bs[j]]/binned[bs[j-1]]) for j in range(1, len(bs))]
    mom.extend(rets)
    for j in range(1, len(bs)):
        buckets[bs[j]].append(math.log(binned[bs[j]]/binned[bs[j-1]]))
    p1015 = next((p for mts, p in series if mts >= 5*60+15), None)
    o, cl = series[0][1], series[-1][1]
    if p1015: cap.append((sym, cl/o-1, cl/p1015-1))
    day_hi = max(p for _, p in series); day_lo = min(p for _, p in series)
    ranges.append((sym, (day_hi-day_lo)/o, (day_hi-cl)/o))

ac = st.mean([(mom[j]-st.mean(mom))*(mom[j-1]-st.mean(mom)) for j in range(1, len(mom))])/st.pvariance(mom)
print(f"15-min return autocorr (pooled): r={ac:.3f}; sd(15min)={st.stdev(mom)*100:.2f}% "
      f"=> 6x15min naive sd={st.stdev(mom)*100*math.sqrt(6):.2f}%")
print("capture from 10:15 to close vs open->close:")
for sym, a, b in cap: print(f"  {sym}: o2c={b*100:+.2f}%, 10:15->close={a*100:+.2f}%")
print("daily range and close-vs-high (today):")
for sym, r, fade in ranges: print(f"  {sym}: range/open={r*100:.2f}%, close {fade*100:.2f}% below high")
