# Configuration Reference

Complete reference for all configurable parameters in the **Settings** tab of the Google Sheets spreadsheet.

Every setting is a key-value pair in the Settings tab. The workflow reads all rows at runtime — no code changes or redeployment needed.

---

## Trading Thresholds

These control when BUY and SELL signals are generated.

| Key | Type | Default | Description |
|:----|:-----|:--------|:-----------|
| `min_change_pct_buy` | Number | `1` | Minimum positive price-change percentage (from LDCP) needed for BUY consideration. A stock must be up by at least this % to trigger a buy signal. |
| `min_change_pct_sell` | Number | `-1` | Minimum negative price-change percentage (from LDCP) needed for SELL consideration. A stock must be down by at least this % to trigger a sell signal. |
| `max_cash_fraction_per_trade` | Number | `0.5` | Maximum fraction of available cash that can be used in one proposed trade. `0.5` means no single trade can use more than 50% of remaining cash. |
| `default_max_trade_value` | Number | `50000` | Maximum trade value (PKR) per signal. Can be overridden per-symbol in the Holdings or Watchlist tabs. |
| `default_lot_size` | Number | `1` | Default lot size for position rounding. Quantities are always rounded down to the nearest multiple of lot size. |

---

## Composite Scoring

The composite score is a weighted blend of three factors, scored 0–100.

| Key | Type | Default | Description |
|:----|:-----|:--------|:-----------|
| `momentum_weight_pct` | Number | `40` | Weight (%) of price momentum in the composite score. Measures % change from LDCP. |
| `position_weight_pct` | Number | `30` | Weight (%) of intraday position. Measures where the current price sits relative to the day's high and low. |
| `volume_weight_pct` | Number | `30` | Weight (%) of volume surge. Compares today's volume to the average daily volume over the lookback period. |
| `score_buy_threshold` | Number | `60` | Minimum composite score (0–100) needed to label a candidate BUY signal. |
| `score_sell_threshold` | Number | `60` | Minimum composite score (0–100) needed to label a candidate SELL signal. |
| `volume_surge_lookback_days` | Number | `20` | Number of trading days used to compute the average daily volume baseline. |

### Score Calculation

```
composite_score = (momentum_weight_pct × momentum_score
                 + position_weight_pct × position_score
                 + volume_weight_pct × volume_score) / 100
```

Where:
- **Momentum score**: Normalized `change_pct` relative to the threshold
- **Position score**: `(current - low) / (high - low) × 100`
- **Volume score**: `min(100, today_volume / avg_volume × 50)`

---

## Risk Controls

Safety guardrails to prevent overexposure and catch anomalies.

| Key | Type | Default | Description |
|:----|:-----|:--------|:-----------|
| `circuit_breaker_pct` | Number | `10` | PSX circuit breaker band: 10%, or Rs.1, whichever is higher. If a stock's change exceeds this, it may be at the circuit limit. |
| `stop_loss_pct` | Number | `7` | Percentage loss from average cost that triggers a stop-loss risk flag on a holding. |
| `max_position_pct_of_portfolio` | Number | `75` | Pyramiding ceiling — stops proposing further BUYs on a symbol once it exceeds this % of total portfolio value. |
| `min_traded_value_floor` | Number | `1000000` | Minimum Rs. traded today for a symbol to be included in scoring. Below this threshold, the symbol is excluded entirely (too illiquid). |
| `data_freshness_max_minutes` | Number | `15` | Maximum age (in minutes) of price data before a run is flagged as stale. Helps catch stale data from weekend/holiday runs. |

---

## Discovery Mode *(Phase 2)*

> 🔮 **Coming Soon** — These settings are reserved for future functionality.

| Key | Type | Default | Description |
|:----|:-----|:--------|:-----------|
| `discovery_enabled` | Boolean | `FALSE` | Whether to scan the broader market for new volatile movers outside Holdings/Watchlist. Leave `FALSE` until the feature is built. |
| `discovery_top_n` | Number | `10` | How many top market movers get a full score recompute each run. |
| `news_lookback_hours` | Number | `72` | How far back to look for company/news catalysts (Phase 2 feature). |

---

## System Settings

| Key | Type | Example | Description |
|:----|:-----|:--------|:-----------|
| `recipient` | Email | `you@gmail.com` | Email address that receives the trading signal alerts. |
| `openai_model` | String | `gpt-4o-mini` | OpenAI model name used by the automation. Supports any model available via the Responses API. |
| `project_label` | String | `Real money involved` | Project label or risk/context note shown in the workflow output. |
| `sender_name` | String | `PSX ACTION` | Display name on the outgoing signal email. |
| `webhook_base_url` | URL | `https://...` | *(Phase 2)* The n8n production webhook URL the email action buttons point to. |
| `webhook_secret` | String | `psx_...` | *(Phase 2)* Shared secret placed in action email URLs to prevent casual/accidental writes. |

---

## Example Settings Sheet

Here's a complete example Settings tab:

| key | value |
|:----|:------|
| `recipient` | `your-email@gmail.com` |
| `min_change_pct_buy` | `1` |
| `min_change_pct_sell` | `-1` |
| `max_cash_fraction_per_trade` | `0.5` |
| `openai_model` | `gpt-4o-mini` |
| `project_label` | `Real money involved` |
| `momentum_weight_pct` | `40` |
| `position_weight_pct` | `30` |
| `volume_weight_pct` | `30` |
| `score_buy_threshold` | `60` |
| `score_sell_threshold` | `60` |
| `min_traded_value_floor` | `1000000` |
| `max_position_pct_of_portfolio` | `75` |
| `volume_surge_lookback_days` | `20` |
| `circuit_breaker_pct` | `10` |
| `stop_loss_pct` | `7` |
| `data_freshness_max_minutes` | `15` |
| `discovery_enabled` | `FALSE` |
| `discovery_top_n` | `10` |
| `news_lookback_hours` | `72` |
| `sender_name` | `PSX ACTION` |

---

## Tips

- **No code changes needed** — All parameters are read dynamically from the sheet at runtime
- **Changes take effect immediately** — Just update the cell value and run the workflow again
- **Safe defaults** — If a setting is missing, the workflow falls back to sensible defaults (documented in the Default column above)
- **Per-symbol overrides** — `max_trade_value` and `lot_size` can be overridden per-symbol in the Holdings and Watchlist tabs
