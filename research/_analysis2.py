# Round 2: intraday structure from ticks, weekday/Friday effects, regime conditioning, winsorized buckets.
import json, os, math, statistics as st
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
EOD = os.path.join(BASE, "eod_history")

def load(sym):
    d = json.load(open(os.path.join(EOD, sym + ".json")))
    rows = sorted(d.get("data") or [])  # ascending
    return rows

syms = [f[:-5] for f in os.listdir(EOD) if f.endswith(".json")]
data = {}
for s in syms:
    rows = load(s)
    if len(rows) >= 260:
        data[s] = rows

W = 0.12  # winsorize |o2c| and |gap| at 12% (band ~10% => beyond that is data error)
def ok(x): return abs(x) <= W

# ---- overnight vs intraday variance split (liquid set) ----
ovr, o2c_ = [], []
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        g, q = o/pc-1, c/o-1
        if ok(g) and ok(q):
            ovr.append(g); o2c_.append(q)
print(f"overnight: mean={st.mean(ovr)*100:.3f}%, sd={st.stdev(ovr)*100:.2f}%")
print(f"open->close: mean={st.mean(o2c_)*100:.3f}%, sd={st.stdev(o2c_)*100:.2f}%")

# ---- winsorized gap buckets ----
def bucket(lo, hi, lab, turn_gate=1e8, extra=None):
    vals = []
    for s, rows in data.items():
        for i in range(21, len(rows)):
            ts, c, v, o = rows[i]; pc = rows[i-1][1]
            if pc in (None, 0) or o in (0, None): continue
            med20 = st.median(r[2]*r[1] for r in rows[max(0,i-20):i])
            if med20 < turn_gate: continue
            g, q = o/pc-1, c/o-1
            if not (lo <= g < hi) or not ok(q) or not ok(g): continue
            if extra and not extra(g, q, rows, i): continue
            vals.append(q)
    if not vals:
        print(f"{lab}: n=0"); return
    m, sd, n = st.mean(vals), st.stdev(vals), len(vals)
    vs = sorted(vals)
    print(f"{lab}: n={n}, mean={m*100:.3f}%, median={vs[n//2]*100:.3f}%, sd={sd*100:.2f}%, "
          f"t={m/(sd/math.sqrt(n)):.1f}, P(<0)={sum(1 for x in vals if x<0)/n*100:.1f}%")

print("\n== winsorized o2c by gap bucket (turn20>=100M) ==")
bucket(-0.0025, 0.0025, "|gap|<0.25%")
bucket(0.0025, 0.01,  "gap [+0.25%,+1%)")
bucket(0.01, 0.02,    "gap [+1%,+2%)")
bucket(0.02, 0.04,    "gap [+2%,+4%)")
bucket(0.04, 0.06,    "gap [+4%,+6%)")
bucket(0.06, 0.12,    "gap [+6%,+12%) (band-risk)")
bucket(-0.01, -0.0025,"gap (-1%,-0.25%]")
bucket(-0.03, -0.01,  "gap (-3%,-1%]")
bucket(-0.08, -0.03,  "gap (-8%,-3%]")

# ---- prev-day big down -> today (bounce logic) ----
print("\n== conditioned on PREV day move ==")
def prevday(lo, hi, lab):
    bucket(-9, 9, lab, 1e8, extra=lambda g,q,r,i: lo <= r[i-1][1]/r[i-2][1]-1 < hi)
prevday(-0.99, -0.04, "prev day <= -4%")
prevday(0.04, 0.99, "prev day >= +4%")
prevday(-0.02, 0.02, "prev day flat |move|<2%")

# ---- Friday / weekday effects ----
import datetime
print("\n== o2c by weekday (turn20>=100M, winsorized) ==")
by_wd = defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        med20 = st.median(r[2]*r[1] for r in rows[max(0,i-20):i])
        if med20 < 1e8: continue
        g, q = o/pc-1, c/o-1
        if not ok(q): continue
        wd = datetime.datetime.utcfromtimestamp(ts).weekday()  # 0=Mon..4=Fri
        by_wd[wd].append(q)
for wd in range(5):
    vals = by_wd[wd]
    nm = "Mon Tue Wed Thu Fri".split()[wd]
    print(f"{nm}: n={len(vals)}, mean={st.mean(vals)*100:.3f}%, median={sorted(vals)[len(vals)//2]*100:.3f}%, P(<0)={sum(1 for x in vals if x<0)/len(vals)*100:.0f}%")

# Friday: gap-conditioned
print("\n== Friday gap buckets ==")
for lo, hi, lab in [(-0.0025,0.0025,"Fri |gap|<0.25%"), (0.0025,0.01,"Fri gap[+0.25%,+1%)"), (0.01,0.04,"Fri gap[+1%,+4%)"), (-0.01,-0.0025,"Fri gap(-1%,-0.25%]")]:
    vals = []
    for s, rows in data.items():
        for i in range(21, len(rows)):
            ts, c, v, o = rows[i]; pc = rows[i-1][1]
            if pc in (None, 0) or o in (0, None): continue
            if datetime.datetime.utcfromtimestamp(ts).weekday() != 4: continue
            med20 = st.median(r[2]*r[1] for r in rows[max(0,i-20):i])
            if med20 < 1e8: continue
            g, q = o/pc-1, c/o-1
            if lo <= g < hi and ok(q) and ok(g): vals.append(q)
    if vals:
        print(f"{lab}: n={len(vals)}, mean={st.mean(vals)*100:.3f}%, median={sorted(vals)[len(vals)//2]*100:.3f}%")

# ---- regime: KSE100 20d vol buckets -> liquid o2c ----
kse = json.load(open(os.path.join(BASE, "_kse100.json")))
kse = sorted(kse)
krets = {kse[i][0]: math.log(kse[i][1]/kse[i-1][1]) for i in range(1, len(kse))}
kdates = [r[0] for r in kse]
kv20 = {}
for i in range(20, len(kse)):
    kv20[kse[i][0]] = st.stdev(math.log(kse[j][1]/kse[j-1][1]) for j in range(i-19, i+1))*math.sqrt(250)
# map stock ts -> nearest index ts (dates align as trading days)
kts_sorted = sorted(kv20)
import bisect
def nearest_kts(ts):
    pos = bisect.bisect_left(kts_sorted, ts)
    if pos == 0: return kts_sorted[0]
    if pos == len(kts_sorted): return kts_sorted[-1]
    return kts_sorted[pos] if abs(kts_sorted[pos]-ts) < abs(kts_sorted[pos-1]-ts) else kts_sorted[pos-1]

print("\n== o2c by KSE100 20d realized vol regime (all liquid, winsorized) ==")
reg = defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        q = c/o-1
        if not ok(q): continue
        volr = kv20.get(nearest_kts(ts))
        if volr is None: continue
        b = "<15%" if volr < .15 else "15-25%" if volr < .25 else "25-35%" if volr < .35 else ">35%"
        reg[b].append(q)
for b in ["<15%", "15-25%", "25-35%", ">35%"]:
    vals = reg[b]
    print(f"idx vol {b}: n={len(vals)}, o2c mean={st.mean(vals)*100:.3f}%, P(<0)={sum(1 for x in vals if x<0)/len(vals)*100:.0f}%")

# regime: index below 50d MA
print("\n== o2c by index trend ==")
treg = defaultdict(list)
for i in range(50, len(kse)):
    ma50 = st.mean(r[1] for r in kse[i-50:i])
    treg["below" if kse[i][1] < ma50 else "above"].append(kse[i][0])
ts_below = set(treg["below"])
tvals = defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        q = c/o-1
        if not ok(q): continue
        kt = nearest_kts(ts)
        tvals["below_ma50" if kt in ts_below else "above_ma50"].append(q)
for k in tvals:
    vals = tvals[k]
    print(f"idx {k}: n={len(vals)}, o2c mean={st.mean(vals)*100:.3f}%, P(<0)={sum(1 for x in vals if x<0)/len(vals)*100:.0f}%")

# ---- intraday tick structure (today, 10 names) ----
print("\n== intraday tick structure 2026-09-15 ==")
tickdir = os.path.join(BASE, "intraday_history")
buckets = defaultdict(list)      # time bucket -> 15-min returns
ret_1015 = []                    # capture from 10:15 to close vs open->close
mom = []
for f in os.listdir(tickdir):
    sym = f.split("_")[0]
    ticks = json.load(open(os.path.join(tickdir, f)))["data"]
    ticks = sorted(ticks)  # ascending [ts, price, vol]
    # 15-min buckets 09:30..15:30 PKT = 04:30..10:30 UTC
    series = []
    for ts, p, v in ticks:
        minutes = (ts % 86400) / 60.0   # UTC minutes
        series.append((minutes, p))
    series.sort()
    # build 15-min close series
    binned = {}
    for minutes, p in series:
        b = int(minutes // 15) * 15
        binned[b] = p
    bs = sorted(binned)
    rets = [(bs[j], math.log(binned[bs[j]]/binned[bs[j-1]])) for j in range(1, len(bs))]
    for b, r in rets:
        buckets[b].append(r)
    mom.extend(r for _, r in rets)
    # 10:15 capture
    first = series[0]; p1015 = None
    for minutes, p in series:
        if minutes >= 5*60+45:  # 10:45 UTC = 15:45? no: PKT = UTC+5; 10:15 PKT = 05:15 UTC
            pass
    p1015 = next((p for m, p in series if m >= 5*60+15), None)
    if p1015:
        o = series[0][1]; cl = series[-1][1]
        ret_1015.append((cl/p1015-1, cl/o-1, sym))
print("15-min return by PKT time bucket (mean x 100, n names):")
for b in sorted(buckets):
    vals = buckets[b]
    pkt = (b + 300) % 1440
    print(f"  {pkt//60:02d}:{pkt%60:02d} PKT: mean={st.mean(vals)*100:+.3f}%, n={len(vals)}")
ac = [mom[j] for j in range(1, len(mom))]
print(f"15-min return autocorr (pooled, 10 names 1 day): r={st.correlation(mom[:-1], ac):.3f}")
print("10:15->close vs open->close (today):")
for a, b, s in ret_1015:
    print(f"  {s}: o2c={b*100:+.2f}%, 10:15->close={a*100:+.2f}%")
