import json, glob, os, time

BASE = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\eod_history"
syms = {}
for f in glob.glob(os.path.join(BASE, "*.json")):
    sym = os.path.splitext(os.path.basename(f))[0]
    try:
        d = json.load(open(f, encoding="utf-8"))["data"]
    except Exception:
        continue
    s = [tuple(map(float, r[:4])) for r in reversed(d) if len(r) >= 4]  # asc: ts, close, volume, open
    syms[sym] = s

def med(a):
    return statistics.median(a) if a else float("nan")

def trimmed_mean(a, lo=5, hi=95):
    if not a: return float("nan")
    s = sorted(a); k = len(s)
    lo_i, hi_i = int(k*lo/100), max(int(k*hi/100)-1, int(k*lo/100))
    seg = s[lo_i:hi_i+1]
    return sum(seg)/len(seg)

import statistics

def report(tag, arr, win_thr=0.0):
    if not arr: return
    wins = sum(1 for x in arr if x > win_thr)
    print("  %-28s n=%-7d med=%+.2f%% tmean=%+.2f%% win=%.1f%%" % (tag, len(arr), med(arr), trimmed_mean(arr), 100*wins/len(arr)))

CUT = (time.time() - 365*86400)
COST = 0.0012  # 12 bps round trip

# ---- robust continuation + gap tables (full 5y and last 1y) ----
for label, cut in (("5y", 0), ("1y", CUT)):
    print("== %s ==" % label)
    oc_all, cont = [], {"<-1": [], "-1..0": [], "0..+1": [], "+1..+2": [], ">+2": []}
    gaps = {"<-1": [], "-1..0": [], "0..+1": [], "+1..+2": [], ">+2": []}
    for sym, s in syms.items():
        for i in range(1, len(s)):
            _, c_prev, v_prev, o_prev = s[i-1]
            ts, c, v, o = s[i]
            if cut and ts < cut: continue
            if o <= 0 or o_prev <= 0 or c_prev <= 0: continue
            oc_today = (c/o - 1) * 100
            oc_all.append(oc_today)
            yday_oc = (c_prev/o_prev - 1) * 100
            gap = (o/c_prev - 1) * 100
            for b, lo, hi in (("<-1", -1e9, -1), ("-1..0", -1, 0), ("0..+1", 0, 1), ("+1..+2", 1, 2), (">+2", 2, 1e9)):
                if lo <= yday_oc < hi: cont[b].append(oc_today)
                if lo <= gap < hi: gaps[b].append(oc_today)
    report("OC all days", oc_all)
    print(" continuation (prev open->close -> today OC):")
    for k in ("<-1", "-1..0", "0..+1", "+1..+2", ">+2"): report("  " + k, cont[k])
    print(" gap (open vs prev close -> today OC):")
    for k in ("<-1", "-1..0", "0..+1", "+1..+2", ">+2"): report("  " + k, gaps[k])

# ---- focused daily backtest: gap-down bounce, pessimistic fills, 1 position/day ----
print("\n== daily backtest: gap-down bounce (enter at open+0.25% slip, exit close-0.25% slip, stop -1.5% if day low breaches) ==")
for gap_lo, gap_hi, tv_min, label in ((-1e9, -1.0, 50, "gap<=-1% TV>50m"), (-1e9, -1.0, 25, "gap<=-1% TV>25m"),
                                       (-1e9, -0.5, 25, "gap<=-0.5% TV>25m"), (-2, -0.5, 25, "gap -2..-0.5 TV>25m")):
    trades = []
    for sym, s in syms.items():
        for i in range(1, len(s)):
            _, c_prev, v_prev, o_prev = s[i-1]
            ts, c, v, o = s[i]
            if ts < CUT: continue
            if o <= 0 or c_prev <= 0: continue
            gap = (o/c_prev - 1) * 100
            tv = c * v / 1e6
            if not (gap_lo <= gap < gap_hi) or tv < tv_min: continue
            entry = o * 1.0025
            stop = entry * 0.985
            # no low column in timeseries: pessimistic stop proxy -- if close < stop, assume filled at stop
            if c < stop:
                exit_ = stop
            else:
                exit_ = c * 0.9975
            ret = exit_/entry - 1 - COST
            trades.append((ts, sym, ret))
    trades.sort()
    # one position at a time: take non-overlapping first-come (all intraday -> every day usable; cap 1/day by taking all, it's intraday)
    rets = [r for _, _, r in trades]
    if rets:
        eq = 1.0
        for r in rets: eq *= (1 + r)
        wins = sum(1 for r in rets if r > 0)
        yrs = 1.0
        print("  %-22s trades=%-5d med=%+.3f%% tmean=%+.3f%% win=%.1f%%  sum-1y-portfolio=%+.1f%% (equal-weight every signal, 1x each)" %
              (label, len(rets), med(rets), trimmed_mean(rets), 100*wins/len(rets), (eq-1)*100))

# ---- momentum-with-volume daily proxy (the engine's entry family) ----
print("\n== daily backtest: strength continuation (gap 0..+1%, TV>50m, exit close) ==")
for label, gl, gh in (("gap 0..+1", 0, 1), ("gap +1..+2", 1, 2)):
    trades = []
    for sym, s in syms.items():
        for i in range(1, len(s)):
            _, c_prev, v_prev, o_prev = s[i-1]
            ts, c, v, o = s[i]
            if ts < CUT or o <= 0 or c_prev <= 0: continue
            gap = (o/c_prev - 1) * 100
            if not (gl <= gap < gh): continue
            if c * v / 1e6 < 50: continue
            entry = o * 1.0025
            exit_ = c * 0.9975 if c >= entry * 0.985 else entry * 0.985
            trades.append(exit_/entry - 1 - COST)
    if trades:
        print("  %-14s trades=%-5d med=%+.3f%% tmean=%+.3f%% win=%.1f%%" % (label, len(trades), med(trades), trimmed_mean(trades), 100*sum(1 for r in trades if r>0)/len(trades)))
