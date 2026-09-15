"""Download EOD history for the KSE100/KMI30 universe from dps.psx.com.pk."""
import json, os, random, sys, time, urllib.request, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research"
OUT = os.path.join(BASE, "eod_history")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

universe = [l.strip() for l in open(os.path.join(BASE, "universe.txt")) if l.strip()]
print("universe size:", len(universe))

ok, empty, failed = [], [], []
t0 = time.time()
for i, sym in enumerate(universe, 1):
    path = os.path.join(OUT, sym + ".json")
    if os.path.exists(path) and os.path.getsize(path) > 100:
        ok.append(sym); continue
    url = f"https://dps.psx.com.pk/timeseries/eod/{sym}"
    data = None
    for attempt in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode()
            j = json.loads(body)
            if j.get("status") == 1 and j.get("data"):
                with open(path, "w") as f:
                    f.write(body)
                ok.append(sym)
            elif j.get("status") == 1:
                empty.append(sym)
            else:
                failed.append((sym, "status!=1: " + str(j)[:100]))
            break
        except Exception as e:
            if attempt == 3:
                failed.append((sym, repr(e)[:120]))
            else:
                time.sleep(2 * attempt)
    time.sleep(random.uniform(0.3, 0.7))
    if i % 20 == 0:
        print(f"{i}/{len(universe)} done ({time.time()-t0:.0f}s)")

print(f"OK={len(ok)} EMPTY={len(empty)} FAILED={len(failed)} in {time.time()-t0:.0f}s")
if empty: print("empty:", empty)
if failed: print("failed:", failed)
