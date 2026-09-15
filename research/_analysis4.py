# Round 4: flagship bucket quantiles + naive daily portfolio sim vs KSE100.
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
def med20(rows, i):
    return st.median(r[2]*r[1] for r in rows[max(0, i-20):i])

# ---- flagship bucket quantiles & yearly ----
print("== flagship: prev<=-4% & gap in [-6%,0] & turn20>=250M ==")
vals, yearly = [], defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        prev = rows[i-1][1]/rows[i-2][1]-1
        g = o/pc-1
        if prev <= -0.04 and -0.06 <= g <= 0 and med20(rows, i) >= 2.5e8:
            q = c/o-1
            if abs(q) > W: continue
            vals.append((ts, q)); yearly[datetime.datetime.utcfromtimestamp(ts).year].append(q)
qs = sorted(x for _, x in vals)
n = len(qs)
print(f"n={n}, mean={st.mean(qs)*100:.3f}%, median={qs[n//2]*100:.3f}%, sd={st.stdev(qs)*100:.2f}%")
for p in (.05, .10, .25, .75, .90, .95):
    print(f"  p{int(p*100)}: {qs[int(p*n)]*100:+.2f}%")
print("P(o2c > 12bps cost):", f"{sum(1 for x in qs if x > 0.0012)/n*100:.0f}%",
      " P(o2c < -2%):", f"{sum(1 for x in qs if x < -0.02)/n*100:.1f}%")
for y in sorted(yearly):
    vv = yearly[y]
    print(f"  {y}: n={len(vv)}, mean={st.mean(vv)*100:.3f}%")

# ---- naive daily portfolio sim ----
print("\n== naive sim: daily equal-weight top-3 qualifiers, entry=open, exit=close, 12bps RT ==")
# qualifiers per day
day_cands = defaultdict(list)
for s, rows in data.items():
    for i in range(21, len(rows)):
        ts, c, v, o = rows[i]; pc = rows[i-1][1]
        if pc in (None, 0) or o in (0, None): continue
        prev = rows[i-1][1]/rows[i-2][1]-1
        g = o/pc-1
        if prev <= -0.04 and -0.06 <= g <= 0 and med20(rows, i) >= 2.5e8:
            q = c/o-1
            if abs(q) <= W:
                day_cands[ts].append((s, g, q))
rets = []
for ts in sorted(day_cands):
    cands = sorted(day_cands[ts], key=lambda x: x[1])  # deepest gap first
    picks = cands[:3]
    gross = st.mean(q for _, _, q in picks)
    dep = min(1.0, len(picks) * 1/3)
    net = gross * dep - 0.0012 * dep
    rets.append((ts, net, len(picks)))
print(f"days with >=1 qualifier: {len(rets)} of {len(set().union(*[set(day_cands)])) if day_cands else 0}")
r_ = [r for _, r, _ in rets]
print(f"net daily: mean={st.mean(r_)*1e4:.1f} bps, median={sorted(r_)[len(r_)//2]*1e4:.1f} bps, "
      f"sd={st.stdev(r_)*1e4:.0f} bps, win-days={sum(1 for x in r_ if x>0)/len(r_)*100:.0f}%, "
      f"ann Sharpe={st.mean(r_)/st.stdev(r_)*math.sqrt(250):.2f}")
cum = 1.0; peak = 1.0; mdd = 0.0
for _, r, _ in rets:
    cum *= 1 + r; peak = max(peak, cum); mdd = max(mdd, 1 - cum/peak)
print(f"cumulative net multiple over {len(rets)} active days: {cum:.3f}, maxDD={mdd*100:.1f}%")
peryear = defaultdict(list)
for ts, r, k in rets: peryear[datetime.datetime.utcfromtimestamp(ts).year].append(r)
for y in sorted(peryear):
    vv = peryear[y]
    print(f"  {y}: active-days={len(vv)}, mean net/day={st.mean(vv)*1e4:.1f} bps")
# same sim with pessimistic +30bps entry haircut
r2 = [g*min(1.0, 0) + 0 for g in []]
rets2 = []
for ts in sorted(day_cands):
    cands = sorted(day_cands[ts], key=lambda x: x[1])[:3]
    gross = st.mean(q for _, _, q in cands) - 0.003   # enter 30bps above open
    dep = min(1.0, len(cands)/3)
    rets2.append(gross*dep - 0.0012*dep)
print(f"with +30bps entry haircut: mean net/day={st.mean(rets2)*1e4:.1f} bps, "
      f"win-days={sum(1 for x in rets2 if x>0)/len(rets2)*100:.0f}%")

# KSE100 benchmark over same window
kse = sorted(json.load(open(os.path.join(BASE, "_kse100.json"))))
kmap = {r[0]: r[1] for r in kse}
kts = sorted(kmap)
import bisect
bret = []
for ts, _, _ in rets:
    pos = bisect.bisect_left(kts, ts)
    if 0 < pos < len(kts):
        bret.append(kmap[kts[pos]]/kmap[kts[pos-1]] - 1)
print(f"KSE100 same active days: mean/day={st.mean(bret)*1e4:.1f} bps, "
      f"ann={((1+st.mean(bret))**250-1)*100:.1f}%, annvol={st.stdev(bret)*math.sqrt(250)*100:.1f}%")
cumk = 1.0
for r in bret: cumk *= 1 + r
print(f"KSE100 cumulative over those days: x{cumk:.3f}")

# frequency: how many active days per week & candidates/day
cd = [len(v) for v in day_cands.values()]
all_days = sorted(set(kmap))
active = set(day_cands)
print(f"candidates/day when active: median={st.median(cd)}, p75={sorted(cd)[3*len(cd)//4]}")
print(f"active days / total trading days: {len(active)}/{len(all_days)} = {len(active)/len(all_days)*100:.0f}%")
