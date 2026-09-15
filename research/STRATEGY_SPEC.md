# STRATEGY_SPEC.md — PSX Intraday Capitalizer v1 (2026-09-15)

Evidence base: 5y + 1y daily EOD for 103 KSE100/KMI30 symbols (research\eod_history),
2026-09-15 whole-market snapshot, DPS endpoint probe. Author: orchestrator (subagent quota
down); audit pass queued. Everything below runs in ONE n8n Code node over the whole-market
snapshot + a per-symbol previous-snapshot cache.

## Measured facts the strategy exploits (all robust, medians)
1. Median open->close on liquid names = **-0.40%/day** (5y AND 1y): the 09:32 opening auction
   systematically overshoots (pre-open orders are irrevocable) and prices drift down all day.
   Buying the open is a structural headwind.
2. Chasing opening strength loses: gap 0..+1% entries -> median -0.40%/OC day, 37% win;
   gap +1..+2% -> -0.87%, 31% win (1y). Gap-ups are the fade zone.
3. Gap-down stabilization has a raw bounce (gap <= -1%: median +0.58%, 61% win) that nets
   ~zero after costs with dumb daily fills — it needs the intraday timing layer (velocity)
   to be worth trading, so we trade it only with confirmation from the live cache.
4. Prev-day continuation is ~zero. Volume pace >1.5x median skews days positive (46% vs 32%
   win) — activity is a quality filter, not a standalone signal.
5. Friction: 12 bps round trip (day-trade one-side commission) + 15% CGT on realized gains.

## Universe gate (per run, from the snapshot alone)
Eligible iff ALL: (a) index list contains KSE100 or KMI30, OR today turnover (current x
volume) >= 50M PKR; (b) today turnover >= 25M PKR hard floor; (c) |change_pct| <= 7% (band
room: exits must not face a ±10% lock); (d) current >= PKR 5 (penny filter); (e) high > low.

## Two entry families (both gated by regime + session windows)
Family A — Auction-fade recovery: gap_pct = (open-ldcp)/ldcp <= -0.7%, AND stabilization:
current >= open AND 15-min velocity_pct >= -0.1 (stopped sinking). Score A =
(current/open - 1)*100 + rel_vol*2, where rel_vol = volume / median(volume over eligible set).
Family B — Intraday momentum continuation: velocity_pct = (current - prev_current)/prev_current
*100 >= 0.30, AND change_pct >= +0.30, AND rel_vol >= 1.2, AND gap_pct <= +1.0 (fade-zone
exclusion), AND position in day range (current-low)/(high-low) >= 0.60. Score B =
velocity_pct*2 + change_pct + rel_vol*1.5.
Entry requires range room: (high-low)/current >= 0.8% (the day's range must afford costs +
trail). Combined candidate list sorted by score; take top candidates while
open_positions < max_open_positions (5) and cash_used <= 80% of book (cash floor 20%).
Quantity = min(100k, cash*0.5) / current, lot-rounded. No rotation in v1.

## Exits (engine emits SELL rows; trader executes)
- Hard stop: current <= avg_price * (1 - 1.5%) -> SELL ALL (knob stop_loss_pct=1.5).
  Replaces V2's "-1% sell half" (churn vs costs; losers bleed, cut full).
- Profit trail: current >= avg_price * 1.015 AND current <= day_high * 0.992 -> SELL ALL
  (take_profit_arm_pct=1.5, trail_from_high_pct=0.8; tuned to liquid-name intraday ranges:
  median |open-close| 1.3%, p75 2.9%).
- EOD FLAT: at the 15:00 run (every day incl. Friday; Friday positions also held through the
  12:00-14:30 intraday break), SELL ALL open positions (eod_flat=TRUE). The sim is a true
  day trader: overnight gap risk is never carried, and the measured -0.40% open-drift is
  harvested position-by-position rather than via a market-wide short (which is impossible
  long-only).
- NO_DATA for a held symbol: DO_NOTHING (never act on missing data).

## Regime stand-down
- Breadth = share of eligible names with change_pct > 0. If breadth < 30% AND median
  eligible change_pct < -0.5% -> no new entries (exits still fire).
- Session windows (Asia/Karachi): entries only 09:45-14:45 Mon-Thu; Friday first session
  entries 09:45-11:15 (hold through the break), second session entries 14:45-15:15 only.
  First run(s) before 09:45 evaluate but do not enter (auction print, 5-min DPS delay).

## Costs & tax (charged in the trader, visible in cash_after + note)
- Friction: round_trip_cost_bps=12 -> 6 bps of traded value per side, deducted each trade.
- CGT: cgt_pct=15 of realized gain on each SELL (vs lot avg_price), deducted at sale.
- Trade note carries "fee=<x>; tax=<y>; family=<A|B|EXIT-TYPE>".

## Logging (per signal row)
run_ts, symbol, family (A/B/EXIT-STOP/EXIT-TRAIL/EODFLAT), score, gap_pct, velocity_pct,
change_pct, rel_vol, range_pos, breadth, turnover_m — enough to validate the 15-min layer
FORWARD (the daily data cannot validate intraday dynamics; honest limitation).

## Honesty / falsifiability
- Expectation: net of costs, a good week is single-digit bps-to-low-%% per day with real
  drawdown days; losing days/weeks are expected. No promise of beating professionals; the
  structural edges are breadth (485 names vs a human's handful), discipline, and cost
  awareness, plus the measured auction-fade bias.
- Falsified if: after ~3 weeks of forward data, Family A win rate < 50% net of costs, or
  Family B velocity entries show negative expectancy, or EOD-flat turnover costs exceed gross
  gains. Kill switches: 3 consecutive days of > 2% book drawdown -> stand down (State flag).
- Top failure modes: (1) 5-min DPS delay makes velocity stale on fast reversals; (2) fills
  at snapshot price overstate reality during fast moves; (3) a low-breadth month makes the
  fade family dominate and it underperforms if the regime flips to strong uptrend.

## Backtest status (honest)
- Validated on daily data: auction-fade bias (-0.40% median), fade-zone exclusion, cost bar.
- NOT validatable on daily data: 15-min velocity timing. Validated forward via the logging
  above. Audit pass (lookahead, thresholds) queued as an independent subagent review.
