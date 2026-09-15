# Throwaway analysis to derive STRATEGY_SPEC thresholds from real EOD data.
import json, os, csv, math, statistics as st
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
EOD = os.path.join(BASE, "eod_history")

def load(sym):
    d = json.load(open(os.path.join(EOD, sym + ".json")))
    rows = d.get("data") or []
    out = []
    for r in rows:  # descending -> build ascending
        ts, close, vol, opn = r
        out.append((ts, opn, close, vol))
    out.reverse()
    return out

syms = [f[:-5] for f in os.listdir(EOD) if f.endswith(".json")]

# ---- per symbol-day frames ----
data = {}  # sym -> list of dicts ascending
for s in syms:
    rows = load(s)
    if len(rows) < 260: continue
    days = []
    for i, (ts, opn, close, vol) in enumerate(rows):
        prev_close = rows[i-1][2] if i > 0 else None
        days.append(dict(ts=ts, o=opn, c=close, v=vol, pc=prev_close,
                         turn=close*vol))
    data[s] = days

print("symbols with >=260 days:", len(data))

# ---- 1. turnover distribution (per symbol, 1y tail) ----
turn_med = {}
for s, days in data.items():
    tail = days[-250:]
    turn_med[s] = st.median(d["turn"] for d in tail)
vals = sorted(turn_med.values(), reverse=True)
print("\n== median 1y turnover (PKR) percentiles ==")
for p in (50, 60, 75, 80, 100):
    print(f"top-{p}: {vals[min(p*len(vals)//100, len(vals)-1)]:,.0f}")
print("count >=50M:", sum(1 for v in vals if v >= 5e7),
      " >=100M:", sum(1 for v in vals if v >= 1e8),
      " >=250M:", sum(1 for v in vals if v >= 2.5e8))

# ---- 2. open->close move distribution, turnover-gated universe ----
trailing_turn = {}  # sym, idx -> median turnover of prior 20 days
def t20(s, i):
    days = data[s]
    lo = max(0, i-20)
    return st.median(d["turn"] for d in days[lo:i]) if i > 0 else 0

gates = (2e7, 5e7, 1e8, 2.5e8)
stats = {g: dict(n=0, absm=0.0, up=0, dn=0, ge24=0, ge50=0) for g in gates}
o2c_all = defaultdict(list)
for s, days in data.items():
    for i, d in enumerate(days):
        if i < 21 or d["pc"] in (None, 0) or d["o"] in (0, None): continue
        o2c = d["c"]/d["o"] - 1
        for g in gates:
            if t20(s, i) >= g:
                q = stats[g]
                q["n"] += 1; q["absm"] += abs(o2c)
                q["up"] += o2c > 0; q["dn"] += o2c < 0
                if abs(o2c) >= 0.0024: q["ge24"] += 1
                if abs(o2c) >= 0.005: q["ge50"] += 1
        o2c_all[2e7].append(o2c) if t20(s, i) >= 2e7 else None

print("\n== open->close stats by trailing-20d median turnover gate ==")
for g, q in stats.items():
    n = q["n"]
    print(f"gate {g/1e6:.0f}M: n={n}, mean|o2c|={q['absm']/n*100:.2f}%, "
          f"P(up)={q['up']/n*100:.1f}%, P(|o2c|>=24bps)={q['ge24']/n*100:.1f}%, "
          f"P(|o2c|>=50bps)={q['ge50']/n*100:.1f}%")

allv = o2c_all[2e7]
allv.sort()
n = len(allv)
print(">=20M o2c quantiles: p1=%.2f%% p5=%.2f%% p25=%.2f%% p50=%.2f%% p75=%.2f%% p95=%.2f%% p99=%.2f%%" % (
    allv[int(.01*n)]*100, allv[int(.05*n)]*100, allv[int(.25*n)]*100, allv[int(.50*n)]*100,
    allv[int(.75*n)]*100, allv[int(.95*n)]*100, allv[int(.99*n)]*100))

# ---- 3. gap continuation (core edge test) ----
# conditional on trailing turnover >= 100M, gap = open/prev_close-1
def cond_stats(conds, labels):
    print("\n== conditional close-vs-open (given entry at open) ==")
    for cond, lab in zip(conds, labels):
        vals_, byhalf = [], ([[], []])
        for s, days in data.items():
            for i, d in enumerate(days):
                if i < 21 or d["pc"] in (None, 0) or d["o"] in (0, None): continue
                if t20(s, i) < 1e8: continue
                gap = d["o"]/d["pc"] - 1
                o2c = d["c"]/d["o"] - 1
                if cond(gap, d, s, i):
                    vals_.append(o2c)
                    byhalf[0 if d["ts"] < 1735689600 else 1].append(o2c)  # 2025-01-01 split
        m = st.mean(vals_); sd = st.stdev(vals_); nn = len(vals_)
        t = m/(sd/math.sqrt(nn))
        h1 = st.mean(byhalf[0]) if byhalf[0] else 0
        h2 = st.mean(byhalf[1]) if byhalf[1] else 0
        neg = sum(1 for v in vals_ if v < 0)/nn
        v = sorted(vals_)
        print(f"{lab}: n={nn}, mean={m*100:.3f}%, sd={sd*100:.2f}%, t={t:.1f}, "
              f"P(<0)={neg*100:.1f}%, p5={v[int(.05*nn)]*100:.2f}%, p95={v[int(.95*nn)]*100:.2f}%, "
              f"halves mean: 21-24={h1*100:.3f}%, 25-26={h2*100:.3f}%")

cond_stats(
    [lambda g,d,s,i: 0.005 <= g,
     lambda g,d,s,i: 0.01 <= g < 0.04,
     lambda g,d,s,i: 0.01 <= g < 0.05 and d["v"]*d["o"] >= 2e7,   # + today turnover-so-far proxy
     lambda g,d,s,i: 0.015 <= g < 0.05,
     lambda g,d,s,i: 0.02 <= g < 0.06,
     lambda g,d,s,i: g >= 0.05,
     lambda g,d,s,i: -0.05 <= g <= -0.01,
     lambda g,d,s,i: abs(g) < 0.0025],
    ["gap>=+0.5% (turn20>=100M)",
     "gap in [+1%,+4%) (turn20>=100M)",
     "gap in [+1%,+5%) & day turnover>=20M",
     "gap in [+1.5%,+5%) (turn20>=100M)",
     "gap in [+2%,+6%) (turn20>=100M)",
     "gap>=+5% (turn20>=100M)",
     "gap in [-5%,-1%] (turn20>=100M)",
     "flat open |gap|<0.25% (turn20>=100M)"])

# ---- 4. qualified names per day (portfolio feasibility) ----
per_day = defaultdict(int)
for s, days in data.items():
    for i, d in enumerate(days):
        if i < 21 or d["pc"] in (None, 0) or d["o"] in (0, None): continue
        if t20(s, i) < 1e8: continue
        gap = d["o"]/d["pc"] - 1
        if 0.01 <= gap < 0.05 and abs(gap) < 0.08:
            per_day[d["ts"] // 86400] += 1
counts = sorted(per_day.values())
print("\n== #names/day with gap in [+1%,+5%) & turn20>=100M ==")
print(f"days with >=1 cand: {len(counts)}/{len(set(per_day))}, "
      f"median/day={st.median(counts)}, p25={counts[len(counts)//4]}, p75={counts[3*len(counts)//4]}, "
      f"P(>=3 names)={sum(1 for c in counts if c>=3)/len(counts)*100:.0f}%")

# ---- 5. band room: how often do gaps approach +-10% band ----
big = 0; tot = 0
for s, days in data.items():
    for i, d in enumerate(days):
        if i < 1 or d["pc"] in (None, 0) or d["o"] in (0, None): continue
        tot += 1
        if abs(d["o"]/d["pc"] - 1) >= 0.08: big += 1
print(f"\nopen already >=8% from LDCP: {big}/{tot} = {big/tot*100:.2f}% of symbol-days")

# ---- 6. next-day follow-through (carry rejection test) ----
nxt_up, nxt = [], []
for s, days in data.items():
    for i in range(21, len(days)-1):
        d, d1 = days[i], days[i+1]
        if d["pc"] in (None, 0) or d["o"] in (0, None) or d1["o"] in (0, None): continue
        if t20(s, i) < 1e8: continue
        day_move = d["c"]/d["pc"] - 1
        if day_move >= 0.04:
            nxt.append((d1["o"]/d["c"]-1, d1["c"]/d1["o"]-1))
if nxt:
    g = [a for a, b in nxt]; oc = [b for a, b in nxt]
    print(f"\nafter a +4%+ day (n={len(nxt)}): next gap mean={st.mean(g)*100:.3f}%, "
          f"next o2c mean={st.mean(oc)*100:.3f}%")

# ---- 7. 20d drift feature test ----
drift_hi, drift_lo = [], []
for s, days in data.items():
    for i in range(21, len(days)):
        d = days[i]
        if d["pc"] in (None, 0) or d["o"] in (0, None): continue
        if t20(s, i) < 1e8: continue
        drift = d["c"]/days[i-20]["c"] - 1
        o2c = d["c"]/d["o"] - 1
        if drift > 0.10: drift_hi.append(o2c)
        elif drift < -0.10: drift_lo.append(o2c)
print(f"20d drift>+10%: n={len(drift_hi)}, o2c mean={st.mean(drift_hi)*100:.3f}%")
print(f"20d drift<-10%: n={len(drift_lo)}, o2c mean={st.mean(drift_lo)*100:.3f}%")

# ---- 8. index (fetch KSE100 if network allows) ----
try:
    import urllib.request
    req = urllib.request.Request("https://dps.psx.com.pk/timeseries/eod/KSE100",
                                 headers={"User-Agent": "Mozilla/5.0"})
    idx = json.loads(urllib.request.urlopen(req, timeout=15).read())
    rows = sorted(idx["data"])
    rets = [math.log(rows[i][1]/rows[i-1][1]) for i in range(1, len(rows))]
    print(f"\nKSE100: n={len(rows)} days, ann.vol={st.stdev(rets)*math.sqrt(250)*100:.1f}%, "
          f"mean daily={st.mean(rets)*100:.3f}%")
    # 20d realized vol regime
    vols = [st.stdev(rets[i-20:i])*math.sqrt(250) for i in range(20, len(rets))]
    vols_sorted = sorted(vols)
    print(f"KSE100 20d-realized-vol: p50={vols_sorted[len(vols)//2]*100:.1f}%, "
          f"p80={vols_sorted[int(.8*len(vols))]*100:.1f}%, p95={vols_sorted[int(.95*len(vols))]*100:.1f}%")
    open(r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\_kse100.json", "w").write(json.dumps(rows))
except Exception as e:
    print("\nKSE100 fetch failed:", e)
