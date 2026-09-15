# DESIGN BRIEF — PSX Intraday Capitalizer (strategy redesign, Sep 2026)

## Goal (pc's words, interpreted)
An automated intraday trading agent for PSX that wakes every 15 minutes while the market is
open, may trade the WHOLE tradeable market (not a fixed 10-symbol watchlist), and tries to
maximize capital growth. Honest goal: maximize risk-adjusted growth of a PKR 500,000 virtual
book; NOT a promise to beat professionals. Buying is optional — on genuinely bad days the
correct output is "no trade", and that must not be punished.

## Hard platform facts (verified)
- Engine: n8n Code node (JS, ES2020, no libraries). Runs every 15 min (`*/15 9-15 * * 1-5`, Asia/Karachi)
  via schedule; trader executes 7 min later; EOD valuation 15:35.
- Per-run data: ONE snapshot of the whole market from https://dps.psx.com.pk/market-watch
  (485 symbols: LDCP, open, high, low, current, change, change_pct, volume, index memberships).
  Officially ~5-minute delayed. After close, current == close.
- No historical intraday endpoint. `/timeseries/int/<SYM>` = TODAY's ticks only (price, volume).
  Historical daily: `/timeseries/eod/<SYM>` = [ts, close, volume, open] x 5y (103 KSE100/KMI30
  symbols already downloaded to research\eod_history\). Whole-market daily OHLCV+LDCP per day:
  mkt_summary/<date>.Z bulk files (sample in research\downloads_samples\closing11.lis).
- Storage: one Google Sheet. Tabs: Holding, Cash, Settings, Watchlist, Signals (append log),
  Trades (append log), State (key/value), Equity (daily). A per-symbol 15-min-ago cache is
  feasible (clear+rewrite one tab per run, ~500 rows) if the strategy needs snapshot deltas.
- Executions: trader fills at the snapshot "current" price (sim). Costs must be charged
  explicitly (see below). Entry limit offsets exist but fills are at snapshot price.

## Market facts (verified via research)
- Long-only. No ready-market shorting. T+1 settlement, same-day square-up normal.
- Day trades bill commission ONE side: all-in round trip ~4 bps (negotiated) / ~9-12 bps
  (typical online 0.15%) / 20-30 bps (bad). CGT 15% on net intraday gains (NCCPL-withheld) —
  report separately from friction; friction knob: round_trip_cost_bps (default 12).
- Per-scrip band: ±10% of LDCP (or Re 1). At a lock the order book is one-sided: cannot exit
  through a lock. Market-wide KSE30 halt possible (45-60 min), rare.
- Hours: Mon-Thu continuous 09:32-15:30 (pre-open 09:15-09:30, match 09:30-09:32). Friday TWO
  sessions: 09:17-12:00 and 14:32-16:30. No closing auction: close = last trade.
- Liquidity: ~55-100 names trade > PKR 50M/day. At PKR 100k clips the top ~60-100 by traded
  value are safely tradeable. Universe selection must be turnover-gated, dynamic daily.
- DPS feed is 5-min delayed; signals are computed on stale-ish data — do not build anything
  that needs faster reaction than ~5-10 min.

## Existing risk rails to keep (tunable)
max_trade_value 100k/symbol, cash fraction 0.5/trade, liquidity floor (min traded value),
circuit-breaker awareness, stop-loss + profit-lock trail (V2: loss-cut half at <= -1%... note:
audit flagged -1% loss-cut as likely too tight for PSX noise; re-derive exits from data,
don't inherit), EOD valuation/experiment-end liquidation.

## Current engine behavior being replaced
Build Signals evaluates holdings+watchlist only, single rule: BUY if not held and
change_pct >= +1% and current within 1% of day high and turnover >= 1M; SELL half if held and
change_pct <= -1%; SELL ALL if armed at +5% vs cost and 2% off day high. On red days: all
DO_NOTHING (correct, but the engine was blind to the other 475 symbols and to intraday
structure). A forced always-deploy fallback existed for one evening and was REMOVED at pc's
order — do not reintroduce forced buying.

## Design requirements for STRATEGY_SPEC.md
1. Universe: dynamic daily tradeable set (turnover + volatility + band-room gates), not a
   fixed watchlist. Specify the exact gate thresholds and where they come from (EOD history
   or live snapshot).
2. Features per candidate per run, computed ONLY from: the current whole-market snapshot,
   an optional per-symbol last-15-min cache, today's `/timeseries/int` ticks for a SHORTLIST
   (budget: <= ~30 int calls per run), and precomputed daily-history features (e.g. ATR%,
   avg turnover, 20d drift — precomputed daily, not per-run).
3. Entry logic: ranked, thresholded, cost-aware (expected move must clear ~2x round-trip
   cost). Explain WHY each feature has predictive logic on PSX intraday specifically.
4. Exit logic: intraday stop/trail with LOCK awareness (can't exit through a lock; avoid
   entering names near their band), EOD flat vs carry decision (argue it), Friday
   two-session handling.
5. Portfolio construction: how many concurrent positions, sizing, rotation (does a stronger
   candidate displace a weaker holding? under what rule), cash floor.
6. Regime filter: when to stand down entirely (index-level crash, breadth collapse, first
   N minutes of the session, pre-close window).
7. Cost model: friction knob + CGT reporting split.
8. Logging: what metadata each signal/trade must record so the week's data can be analyzed
   and the strategy improved WITHOUT relitigating blind.
9. Honesty section: expected performance range, what would falsify the strategy, and the
   top-3 ways it fails live.
10. BACKTEST PLAN: how to validate on the downloaded 5y daily data (explicit approximation
    rules: entry at X% into the day's range, exits pessimistic, cost bps), and what metric
    bar the strategy must clear vs KSE100 buy-and-hold before it ships.

Constraints: everything must run in one Code node pass over ~485 snapshot rows in < a few
seconds; total Sheets writes per run bounded (~a few hundred rows max); no external API calls
except the <= ~30 allowed `/timeseries/int` shortlist calls; deterministic (same input ->
same output). Write the spec to research\STRATEGY_SPEC.md.
