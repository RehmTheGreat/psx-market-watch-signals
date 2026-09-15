# PSX Data Portal (dps.psx.com.pk) — Probe Report

Date: 2026-09-15 (probed ~18:30 PKT, after market close 15:30 PKT). All probing done from the PC (Git Bash + curl/Python). The VPS was never needed — no blocks, no rate limiting encountered.

## 1. Endpoint inventory

### CONFIRMED WORKING (data endpoints)

| Endpoint | Method | Returns |
|---|---|---|
| `/market-watch` | GET | Server-rendered HTML table, 485 symbols. Columns: symbol (`<a class="tbl__symbol" href="/company/SYM" data-title="Full Name">`), sector code, index memberships (comma list), LDCP, OPEN, HIGH, LOW, CURRENT, CHANGE, CHANGE%, VOLUME. Machine-readable values in `data-order` attrs. **No JS on the page** — fully parseable statically. |
| `/timeseries/eod/<SYM>` | GET | `{"status":1,"message":"","data":[[unix_ts, close, volume, open], ...]}` **descending** by date. Works for stocks AND indices (`KSE100`, `KSE30`, `KMI30`, `ALLSHR` all verified). Unknown symbol → `{"status":1,"data":[]}` (empty, NOT an error — must check `data` emptiness). |
| `/timeseries/int/<SYM>` | GET | `{"status":1,"data":[[unix_ts, price, volume], ...]}` — **today's tick-by-tick trades**, descending. ~2,500 ticks/day for a liquid name. Session span 09:30:00–15:26 PKT. `?date=` query param is IGNORED (verified: response identical for `?date=2026-09-10`). **No intraday history — current day only.** |
| `/symbols` | GET | JSON array of ALL tradable symbols incl. debt/ETFs: `{"symbol","name","sectorName","isETF","isDebt"}` (~600+ entries). Better universe source than scraping market-watch. |
| `/daily-downloads` | POST (`date=YYYY-MM-DD`) | HTML fragment listing per-day bulk files under `/download/...` (see below). |
| `/historical-downloads` | POST | HTML fragment (GIS/sukuk coupon history PDFs). |
| `/other-downloads` | GET | HTML fragment listing static reference files (index membership `.lis.Z`, lot sizes, symbol lists). |
| `/download/<kind>/<YYYY-MM-DD>.<ext>` | GET | Bulk files. **Require `Referer: https://dps.psx.com.pk/...` + browser User-Agent, else 403** (hotlink protection). `.Z` files are actually ZIP archives. |

### Bulk daily files (from `/daily-downloads`, date-stamped)

| Kind | Ext | Contents (verified on 2026-09-15 samples) |
|---|---|---|
| `mkt_summary` | .Z (zip) | `closing11.lis` — **full-market EOD**, pipe-delimited: `DATE\|SYM\|SECTOR\|NAME\|OPEN\|HIGH\|LOW\|CLOSE\|VOLUME\|LDCP\|\|\|`. ~74 KB/day. This is the one-file-per-day OHLCV for ALL symbols. |
| `symbol_price` | .zip | CSV: `MARKET_CODE,SYMBOL_CODE,SYMBOL_NAME,SETTLEMENT_TYPE,ORDER_REJECT_UPPER_PRICE,ORDER_REJECT_LOWER_PRICE,LAST_DAY_CLOSE_PRICE` (circuit limits; generated post-close with that day's close). |
| `symbol_name` | .zip | `symbolname.lis`, UTF-16-ish with control chars — short + long names. |
| `post_close` | .Z (zip) | Post-close turnover: `SYM\|NAME\|shares\|value\|*`. |
| `closing_rates` | .pdf | Closing rates report. |
| `indhist` | .xls | Real Excel (CFB) — **index historical data**. |
| also | | `announce`, `csf_opn_int`, `dfc_nbs`, `dvf_trade`, `fut_opn_int`, `itsubs`, `nd_accepted/rejected/threshold`, `omts`, `pos_limit_fut`, `reval_rates_gis`, `short_sell_vol`, `sif_fair_val`, `sif_opn_int`, `var_margin` (PDF/CSV/XLS mixes — futures OI, margins, NVDR etc.). |

### Static reference files (`/other-downloads`)
`/download/text/kse100.lis.Z`, `allshr_new.lis.Z`, `kse_index.lis.Z`, `listed_cmp.lst.Z`, `zerovolume.lis.Z`, `/download/lot_size/Symbol_LotSize.zip`, `/download/historical/HBLTTI.csv`, market-report PDFs.

### Page routes seen in `/static/script.js?v=1.75` router (2.8 MB)
`/market-watch` (via `/`), `/company/<SYM>`, `/announcements`, `/calendar`, `/circuit-breakers`, `/downloads`, `/eligible-scrips`, `/etf/<SYM>`, `/indices`, `/graphical-view`, `/listings`, `/screener`, `/sector-summary`, `/sectors`, `/trading-panel`, `/portfolio/*` (full virtual-trading app: login/register/trade/positions/history + admin contest endpoints), `/debt-market`, `/payouts`, `/monthly-reports`, `/financial-reports`, `/analysis-reports`, `/gis-auction-results`.

### What does NOT exist (probed, 404 / dead end)
- **`/timeseries/intraday|/iex|/chart|/intra|/eod2|/zzz/<SYM>`** — all return HTTP 200 with the **EOD** payload byte-identical to `/timeseries/eod/<SYM>` (md5-verified). The Flask route is a wildcard `/timeseries/<anything>/<SYM>` where only `int` and `eod` are meaningful. `/timeseries/int` = today only; there is **no historical intraday endpoint**.
- `/api/timeseries/*`, `/historical/<SYM>` — 404.
- `/trading-board/` direct GET — 404 (fragment only loads with page context; not needed).

## 2. EOD field semantics — CONFIRMED

`/timeseries/eod/<SYM>` row = `[unix_ts, close, volume, open]`.

Proof (newest row vs live market-watch, same day, market closed so close==current):

| Symbol | ts (PKT) | f1 vs current | f2 vs volume | f3 vs open | prev-row close vs LDCP |
|---|---|---|---|---|---|
| ENGROH | 2026-09-15 16:00 | 263.83 == 263.83 ✓ | 991,381 == 991,381 ✓ | 262.11 == 262.11 ✓ | 261.27 vs 261.28 (0.01 rounding) |
| OGDC | 2026-09-15 16:00 | 314.87 == 314.87 ✓ | 1,499,010 == 1,499,010 ✓ | 317.00 == 317.00 ✓ | 315.13 == 315.13 ✓ |
| LUCK | 2026-09-15 16:00 | 413.87 == 413.87 ✓ | 781,195 == 781,195 ✓ | 416.50 == 416.50 ✓ | 406.18 == 406.18 ✓ |

Confidence: **very high** — exact match on all 9 field comparisons, and corroborated by the site's own JS (`script.js`: `value:d[1],volume:d[2],open:d[3]`) and by `symbol_price` zip LAST_DAY_CLOSE matching the EOD close.

Timestamp details: ts is 11:00 UTC = **16:00 PKT** for the newest row (varies slightly on older rows, e.g. 10:44–11:06 UTC). **Use the date only (UTC+5), never the time-of-day.**

History depth: **rolling 5-year window** — oldest row 2021-09-16 for long-listed names (later for newly listed; universe range 2021-09-16 to 2024-05-20). Cadence: one row per trading day (gap histogram: 1-day gaps dominate; 3-day gaps = Sat/Sun weekend; ~245–250 rows/yr). No missing-weeks pattern.

For indices, `[ts, index_close, total_constituent_volume, prev_close_or_open_ref]` — same shape, f3 is the index open.

## 3. Intraday findings

- **Intraday history does NOT exist** on dps.psx.com.pk. Only `/timeseries/int/<SYM>`: current-day ticks `[unix_ts, price, volume]`, no OHLC bars, no aggregation, `?date=` ignored. The company-page chart uses `int` only for the 1D range; every other range pulls `eod`.
- Per task spec (download 20 days of intraday bars **if the endpoint exists**), historical intraday download was therefore skipped. As evidence I saved **today's full tick stream** for the 10 most liquid symbols into `research\intraday_history\<SYM>_2026-09-15.json` (PPL 2,663 ticks; OGDC 2,499; etc.).
- If intraday history is ever needed: it must be captured daily by polling `/timeseries/int/<SYM>` before ~16:00 PKT, or aggregated from ticks the pipeline already pulls.

## 4. Download stats

- Universe: **103 symbols** with KSE100 or KMI30 membership (from one market-watch fetch of 485 symbols).
- EOD history: **103/103 downloaded OK, 0 empty, 0 failed**, `research\eod_history\<SYM>.json` (raw API responses).
- Politeness: 0.3–0.7 s jittered delay; ~103 requests in 187 s.
- **Rate-limit behavior: none observed.** ~170 requests total this session; a 12-request zero-delay burst all returned HTTP 200 in 1.1–1.9 s (server latency only, no 429/403/captcha). The only 403s were the `/download/*` files without Referer/UA (hotlink protection, fixed with headers).

## 5. Universe stats (`research\universe_stats.json`, `.csv`)

103 symbols; 1y window = last 245–250 trading days each. Top 5 by avg daily turnover (PKR):
PPL 1.75B · NBP 1.68B · OGDC 1.61B · PSO 1.49B · BOP 1.46B.
Columns: symbol, last_close, avg_daily_volume_1y, avg_daily_turnover_1y, median_daily_abs_pct_change_1y, annualized_volatility_1y (stdev log returns × √250), first_date, last_date, n_days, n_days_1y. Ann. vol range ≈ 0.32 (OGDC) – ~0.8 (illiquid names).

## 6. Files produced (all under `C:\Users\pc\Desktop\Claude\psx-market-watch-signals\research\`)

- `market_watch_snapshot.json` — 485 symbols, full fields incl. index memberships
- `universe.txt` — the 103 KSE100/KMI30 symbols
- `eod_history\<SYM>.json` × 103 — raw `/timeseries/eod` responses (5y each)
- `intraday_history\<SYM>_2026-09-15.json` × 10 — today's tick streams (evidence for §3)
- `universe_stats.json`, `universe_stats.csv` — 1y stats per symbol
- `downloads_samples\` — mkt_summary / symbol_price / symbol_name / post_close / indhist samples of 2026-09-15 (incl. extracted `closing11.lis`, `202615sep.txt`)
- `parse_market_watch.py`, `download_eod.py`, `compute_stats.py` — reproducible pipeline
- `_mw.html` — raw market-watch HTML snapshot

## 7. Practical guidance for the trading system

- **Daily EOD refresh**: one GET per symbol of `/timeseries/eod/<SYM>` (0.3 s+ delay) is trivially safe; or fetch `mkt_summary/<date>.Z` (1 request = whole market OHLCV, needs Referer+UA, `.Z` is a zip, open inner `closing11.lis`).
- **Universe membership**: parse index lists from `/market-watch` (field 3) or use `/symbols` JSON for the full instrument catalog.
- **Live prices**: poll `/market-watch` (server-rendered, parse `data-order` attrs) — the same page the website uses.
- **Backtest window limit**: EOD history is a rolling 5 years — no deeper history exists via API. For longer windows use `indhist/*.xls` (index only) or third-party sources.
- Sector codes come as numeric strings (e.g. `0820`); map via sector names on the `/sectors` page if needed.
