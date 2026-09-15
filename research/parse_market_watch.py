"""Parse dps.psx.com.pk/market-watch HTML into snapshot JSON + KSE100/KMI30 universe."""
import json, re, sys, io
from html.parser import HTMLParser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HTML_PATH = r"C:\Users\pc\AppData\Local\Temp\market_watch.html"
OUT_SNAPSHOT = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\market_watch_snapshot.json"
OUT_UNIVERSE = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\universe.txt"

# find the actual fetched html location (git bash /tmp maps to AppData Temp for some tools; fallback)
import os
for cand in [r"C:\Users\pc\AppData\Local\Temp\market_watch.html", "/tmp/market_watch.html",
             r"C:\Program Files\Git\tmp\market_watch.html", r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\_mw.html"]:
    if os.path.exists(cand) and os.path.getsize(cand) > 10000:
        HTML_PATH = cand
        break

raw = open(HTML_PATH, encoding="utf-8", errors="replace").read()
# strip comments so <!-- td ... --> placeholders never match
raw_nc = re.sub(r"<!--.*?-->", "", raw, flags=re.S)

TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
DATA_ORDER = re.compile(r'data-order="([^"]*)"')
SYMBOL_RE = re.compile(r'<a class="tbl__symbol" href="/company/([^"]+)"')
TAG_RE = re.compile(r"<[^>]+>")

def num(s):
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

rows = {}
for tr in TR_RE.finditer(raw_nc):
    body = tr.group(1)
    tds = TD_RE.findall(body)
    if len(tds) < 11:
        continue
    m = SYMBOL_RE.search(tds[0])
    if not m:
        continue
    sym = m.group(1).strip()
    # data-order attributes carry the machine-readable values
    orders = DATA_ORDER.findall(body)
    # order of data-order occurrences in a row: symbol, ldcp, open, high, low, current, change, change%, volume
    def o(i):
        try:
            return float(orders[i].replace(",", ""))
        except (IndexError, ValueError):
            return None
    name_m = re.search(r'data-title="([^"]*)"', tds[0])
    rows[sym] = {
        "symbol": sym,
        "name": name_m.group(1) if name_m else None,
        "sector": tds[1].strip(),
        "indices": [x.strip() for x in tds[2].split(",") if x.strip()],
        "ldcp": o(1), "open": o(2), "high": o(3), "low": o(4),
        "current": o(5), "change": o(6), "change_pct": o(7), "volume": o(8),
    }

print("parsed rows:", len(rows))

universe = sorted(s for s, r in rows.items() if "KSE100" in r["indices"] or "KMI30" in r["indices"])
print("universe (KSE100 or KMI30):", len(universe))

with open(OUT_SNAPSHOT, "w") as f:
    json.dump(rows, f, indent=1)
with open(OUT_UNIVERSE, "w") as f:
    f.write("\n".join(universe))

# quick spot check
for s in ("ENGROH", "OGDC", "LUCK"):
    print(s, rows.get(s))
