"""Compute 1y stats per universe symbol from eod_history files."""
import json, os, csv, statistics, datetime, io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research"
EOD = os.path.join(BASE, "eod_history")

universe = [l.strip() for l in open(os.path.join(BASE, "universe.txt")) if l.strip()]
rows_out = {}
for sym in universe:
    j = json.load(open(os.path.join(EOD, sym + ".json")))
    data = sorted(j["data"])  # ascending [ts, close, vol, open]
    if not data:
        continue
    last_ts = data[-1][0]
    cutoff = last_ts - 365 * 86400
    y = [r for r in data if r[0] >= cutoff]
    closes = [r[1] for r in y]
    vols = [r[2] for r in y]
    last_close = data[-1][1]
    turnover = [c * v for c, v in zip(closes, vols)]
    rets = []
    for a, b in zip(closes, closes[1:]):
        if a > 0 and b > 0:
            rets.append(__import__("math").log(b / a))
    ann_vol = statistics.stdev(rets) * (250 ** 0.5) if len(rets) > 2 else None
    abs_pct = [abs(b / a - 1) * 100 for a, b in zip(closes, closes[1:]) if a > 0]
    rows_out[sym] = {
        "last_close": last_close,
        "avg_daily_volume_1y": round(statistics.mean(vols), 1) if vols else None,
        "avg_daily_turnover_1y": round(statistics.mean(turnover), 0) if turnover else None,
        "median_daily_abs_pct_change_1y": round(statistics.median(abs_pct), 4) if abs_pct else None,
        "annualized_volatility_1y": round(ann_vol, 4) if ann_vol else None,
        "first_date": datetime.datetime.utcfromtimestamp(data[0][0]).strftime("%Y-%m-%d"),
        "last_date": datetime.datetime.utcfromtimestamp(last_ts).strftime("%Y-%m-%d"),
        "n_days": len(data),
        "n_days_1y": len(y),
    }

with open(os.path.join(BASE, "universe_stats.json"), "w") as f:
    json.dump(rows_out, f, indent=1)

with open(os.path.join(BASE, "universe_stats.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["symbol", "last_close", "avg_daily_volume_1y", "avg_daily_turnover_1y",
                "median_daily_abs_pct_change_1y", "annualized_volatility_1y",
                "first_date", "last_date", "n_days", "n_days_1y"])
    for sym, r in sorted(rows_out.items(), key=lambda kv: -(kv[1]["avg_daily_turnover_1y"] or 0)):
        w.writerow([sym] + [r[k] for k in ("last_close", "avg_daily_volume_1y", "avg_daily_turnover_1y",
                                           "median_daily_abs_pct_change_1y", "annualized_volatility_1y",
                                           "first_date", "last_date", "n_days", "n_days_1y")])

print("symbols:", len(rows_out))
top = sorted(rows_out.items(), key=lambda kv: -(kv[1]["avg_daily_turnover_1y"] or 0))[:10]
for s, r in top:
    print(s, r["last_close"], r["avg_daily_turnover_1y"], r["annualized_volatility_1y"])
with open(os.path.join(BASE, "top10_liquid.txt"), "w") as f:
    f.write("\n".join(s for s, _ in top))
