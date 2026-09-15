// PSX Intraday Capitalizer v1 - engine. Spec: research/STRATEGY_SPEC.md (2026-09-15).
// Inputs: whole-market DPS snapshot + per-symbol previous snapshot (MktCache) + sheet tabs.
// Long-only, no leverage, EOD flat. Family A = auction-fade recovery, B = 15-min momentum.
function toNumber(value, fallback = 0) {
  if (value === null || value === undefined) return fallback;
  const cleaned = String(value).replace(/,/g, "").replace(/%/g, "").replace(/[^\d.-]/g, "").trim();
  if (cleaned === "" || cleaned === "-" || cleaned === ".") return fallback;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : fallback;
}
function cleanHtml(value) {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#37;/g, "%")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
function roundTo(value, decimals = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * Math.pow(10, decimals)) / Math.pow(10, decimals);
}
function roundDownToLot(quantity, lotSize) {
  const lot = Math.max(1, Math.floor(toNumber(lotSize, 1)));
  return Math.floor(Math.floor(toNumber(quantity, 0)) / lot) * lot;
}
function safeRows(nodeName) {
  try { return $(nodeName).all().map(item => item.json); } catch (error) { return []; }
}
function parseMarketWatch(rawInput) {
  const raw = String(rawInput || "");
  const rows = [];
  for (const tr of (raw.match(/<tr[\s\S]*?<\/tr>/gi) || [])) {
    const rawCells = [...tr.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(match => cleanHtml(match[1]));
    const cells = rawCells.filter(cell => cell !== "");
    if (cells.length >= 8) rows.push({ cells, indices: rawCells.length >= 3 ? rawCells[2] : "" });
  }
  const parsed = [];
  for (const rowInfo of rows) {
    const cells = rowInfo.cells;
    const firstCell = String(cells[0] || "").trim().toUpperCase();
    if (!firstCell || firstCell === "SYMBOL") continue;
    const symbol = firstCell.split(/\s+/)[0];
    const volume = toNumber(cells[cells.length - 1], null);
    const change_pct = toNumber(cells[cells.length - 2], null);
    const change = toNumber(cells[cells.length - 3], null);
    const current = toNumber(cells[cells.length - 4], null);
    const low = toNumber(cells[cells.length - 5], null);
    const high = toNumber(cells[cells.length - 6], null);
    const open = toNumber(cells[cells.length - 7], null);
    const ldcp = toNumber(cells[cells.length - 8], null);
    if (!symbol || current === null || !Number.isFinite(current)) continue;
    parsed.push({ symbol, ldcp, open, high, low, current, change, change_pct, volume, indices: rowInfo.indices });
  }
  if (parsed.length > 0) return parsed;
  const text = cleanHtml(raw);
  for (const line of text.split(/(?=[A-Z0-9]{2,12}\s+\d{4}\s+)/g).map(l => l.trim()).filter(Boolean)) {
    const parts = line.split(/\s+/);
    if (parts.length < 10) continue;
    const symbol = parts[0].toUpperCase();
    if (symbol === "SYMBOL") continue;
    const t = parts.slice(1).filter(p => /^-?[\d,.]+%?$/.test(p));
    if (t.length < 7) continue;
    const row = { symbol, ldcp: toNumber(t[t.length - 8], null), open: toNumber(t[t.length - 7], null),
      high: toNumber(t[t.length - 6], null), low: toNumber(t[t.length - 5], null),
      current: toNumber(t[t.length - 4], null), change: toNumber(t[t.length - 3], null),
      change_pct: toNumber(t[t.length - 2], null), volume: toNumber(t[t.length - 1], null), indices: "" };
    if (row.current === null || !Number.isFinite(row.current)) continue;
    parsed.push(row);
  }
  return parsed;
}

const holdingRows = safeRows("Read Holdings");
const cashRows = safeRows("Read Cash");
const settingsRows = safeRows("Read Settings");
const psxItem = $("Fetch PSX Market Watch").first()?.json || {};
// previous-snapshot cache lives in workflow static data (zero Sheets API quota; persists
// across runs, saved on successful execution). The 2026-09-15 Sheets-tab cache blew the
// Google "writes per minute" quota with a ~450-row rewrite every 15 minutes.
const STATIC = $getWorkflowStaticData("global");
const prev = STATIC.market_cache || {};

const settings = {};
for (const row of settingsRows) {
  const k = String(row.key || "").trim(); const v = String(row.value || "").trim();
  if (k) settings[k] = v;
}
const knob = (k, d) => { const v = Number(settings[k]); return settings[k] !== undefined && settings[k] !== "" && Number.isFinite(v) ? v : d; };
const STOP_PCT = knob("stop_loss_pct", 1.5);
const ARM_PCT = knob("take_profit_arm_pct", 1.5);
const TRAIL_PCT = knob("trail_from_high_pct", 0.8);
const MAX_OPEN = Math.max(1, knob("max_open_positions", 5));
const CASH_FLOOR = knob("cash_floor_pct", 20) / 100;
const CASH_FRAC = knob("max_cash_fraction_per_trade", 0.5);
const MAX_TRADE = knob("default_max_trade_value", 100000);
const MIN_TV_M = knob("min_turnover_m", 25);
const BIG_TV_M = knob("big_turnover_m", 50);
const BAND_PCT = knob("max_band_dist_pct", 7);
const MIN_PRICE = knob("min_price", 5);
const cashStart = cashRows.reduce((sum, row) => sum + toNumber(row.amount, 0), 0);

const marketRows = parseMarketWatch(psxItem.body || psxItem.data || psxItem.response || JSON.stringify(psxItem));
const marketBySymbol = {};
for (const row of marketRows) marketBySymbol[row.symbol.toUpperCase()] = row;
const now = new Date();
const pktMin = (now.getUTCHours() * 60 + now.getUTCMinutes() + 330) % 1440;
const isFriday = now.getUTCDay() === 5;
let entriesOpen = false;
if (isFriday) entriesOpen = (pktMin >= 585 && pktMin <= 675) || (pktMin >= 885 && pktMin <= 886);
else entriesOpen = (pktMin >= 585 && pktMin <= 885);
const eodFlatTime = pktMin >= 900;
// PKT clock (server runs UTC; PKT weekday == UTC weekday during market hours)

// eligible universe
const eligible = [];
for (const m of marketRows) {
  const tvM = m.current * (m.volume || 0) / 1e6;
  const idx = String(m.indices || m.index || "").toUpperCase();
  if (m.current < MIN_PRICE) continue;
  if (Math.abs(m.change_pct) > BAND_PCT) continue;
  if (tvM < MIN_TV_M) continue;
  if (!(m.high > m.low)) continue;
  eligible.push(m);
}
const eligVols = eligible.map(m => m.volume || 0).sort((a, b) => a - b);
const medianVol = eligVols.length ? eligVols[eligVols.length >> 1] : 0;
let advCount = 0;
const chgSorted = [];
for (const m of eligible) { if (m.change_pct > 0) advCount++; chgSorted.push(m.change_pct); }
chgSorted.sort((a, b) => a - b);
const medChange = chgSorted.length ? chgSorted[chgSorted.length >> 1] : 0;
const breadth = eligible.length ? advCount / eligible.length : 0;
const regimeOk = !(breadth < 0.30 && medChange < -0.5);

// holdings
const lots = holdingRows
  .map(row => ({
    symbol: String(row.symbol || "").trim().toUpperCase(),
    lot_id: String(row.lot_id || "").trim(),
    shares: toNumber(row.shares, 0),
    avg_price: toNumber(row.avg_price, 0),
    max_trade_value: toNumber(row.max_trade_value, MAX_TRADE),
    lot_size: Math.max(1, toNumber(row.lot_size, 1))
  }))
  .filter(row => row.symbol);
const holdingsBySymbol = {};
for (const lot of lots) {
  if (!holdingsBySymbol[lot.symbol]) holdingsBySymbol[lot.symbol] = { symbol: lot.symbol, total_shares: 0, total_cost: 0, weighted_avg_price: 0, lot_size: lot.lot_size, lots: [] };
  const g = holdingsBySymbol[lot.symbol];
  g.total_shares += lot.shares;
  g.total_cost += lot.shares * lot.avg_price;
  g.lot_size = Math.max(1, Math.min(g.lot_size, lot.lot_size));
  g.lots.push(lot);
}
for (const g of Object.values(holdingsBySymbol)) g.weighted_avg_price = g.total_shares > 0 ? g.total_cost / g.total_shares : 0;
const heldSet = new Set(Object.keys(holdingsBySymbol).filter(s => holdingsBySymbol[s].total_shares > 0));
let openCount = heldSet.size;

const signals = [];      // rows to log/email: BUY, SELL, NO_DATA-on-held
const runTimestamp = new Date().toISOString();

// --- exits for held symbols
for (const sym of heldSet) {
  const g = holdingsBySymbol[sym];
  const market = marketBySymbol[sym];
  if (!market) {
    signals.push({ symbol: sym, action: "NO_DATA", quantity: 0, limit_price: null, current_price: null,
      weighted_avg_price: roundTo(g.weighted_avg_price, 2), total_shares: g.total_shares, change_pct: null,
      trade_value: 0, reason: "Held symbol missing from DPS snapshot - do not act on missing data." });
    continue;
  }
  const cost = g.weighted_avg_price;
  let action = null, reason = "";
  if (market.current <= cost * (1 - STOP_PCT / 100)) {
    action = "SELL"; reason = "EXIT-STOP: current " + market.current + " <= cost " + roundTo(cost, 2) + " x (1-" + STOP_PCT + "%). Cut full - losers bleed intraday.";
  } else if (market.high > 0 && market.current >= cost * (1 + ARM_PCT / 100) && market.current <= market.high * (1 - TRAIL_PCT / 100)) {
    action = "SELL"; reason = "EXIT-TRAIL: armed +" + roundTo((market.current / cost - 1) * 100, 2) + "% vs cost, faded " + TRAIL_PCT + "% off day high " + market.high + ". Lock all intraday gain.";
  } else if (eodFlatTime) {
    action = "SELL"; reason = "EODFLAT: day trader squares up at 15:00 PKT - overnight gaps are never carried.";
  }
  if (action) {
    signals.push({ symbol: sym, action, quantity: g.total_shares, limit_price: roundTo(market.current * 0.995, 2),
      current_price: roundTo(market.current, 2), weighted_avg_price: roundTo(cost, 2), total_shares: g.total_shares,
      high_price: roundTo(market.high, 2), change_pct: roundTo(market.change_pct, 2),
      trade_value: roundTo(g.total_shares * market.current * 0.995, 2), reason });
  }
}

// --- entries
let deployed = 0;
let candidateCount = 0;
const budget = Math.max(0, cashStart * (1 - CASH_FLOOR));
if (regimeOk && entriesOpen && !eodFlatTime && marketRows.length > 50) {
  const candidates = [];
  for (const m of eligible) {
    if (heldSet.has(m.symbol)) continue;
    const p = prev[m.symbol];
    const prevCur = p ? toNumber(p.current, 0) : 0;
    const vel = prevCur > 0 ? (m.current / prevCur - 1) * 100 : null;
    const relVol = medianVol > 0 ? (m.volume || 0) / medianVol : 0;
    const gap = m.ldcp > 0 ? (m.open / m.ldcp - 1) * 100 : 0;
    const rangePos = (m.current - m.low) / (m.high - m.low);
    const recov = (m.current / m.open - 1) * 100;
    const tvM = m.current * (m.volume || 0) / 1e6;
    const liqOk = tvM >= BIG_TV_M || /KSE100|KMI30/.test(String(m.indices || "").toUpperCase());
    if (!liqOk) continue;
    if (ALWAYS) {
      // dormant knob: forced best-of-market entry (disabled by default, pc ruling 2026-09-15)
      candidates.push({ m, family: "F", score: m.change_pct + relVol * 3, vel, relVol, gap, rangePos });
      continue;
    }
    if (gap <= -0.7 && recov >= 0 && (vel === null || vel >= -0.1)) {
      const score = recov + relVol * 2;
      if (score >= 0.5) candidates.push({ m, family: "A", score, vel, relVol, gap, rangePos });
    }
    if (vel !== null && vel >= 0.30 && m.change_pct >= 0.30 && relVol >= 1.2 && gap <= 1.0 && rangePos >= 0.60) {
      const score = vel * 2 + m.change_pct + relVol * 1.5;
      candidates.push({ m, family: "B", score, vel, relVol, gap, rangePos });
    }
  }
  candidates.sort((a, b) => b.score - a.score);
  const picked = new Set();
  for (const c of candidates) {
    if (picked.has(c.m.symbol)) continue;
    if (openCount >= MAX_OPEN || deployed >= budget) break;
    const roomPct = (c.m.high - c.m.low) / c.m.current * 100;
    if (roomPct < 0.8) continue;
    const capValue = Math.min(MAX_TRADE, budget - deployed, cashStart * CASH_FRAC);
    const qty = roundDownToLot(capValue / c.m.current, 1);
    if (qty <= 0) continue;
    const limitPrice = roundTo(c.m.current * 1.005, 2);
    deployed += qty * limitPrice;
    openCount += 1;
    picked.add(c.m.symbol);
    signals.push({
      symbol: c.m.symbol, action: "BUY", quantity: qty, limit_price: limitPrice,
      current_price: roundTo(c.m.current, 2), weighted_avg_price: 0, total_shares: 0,
      high_price: roundTo(c.m.high, 2), change_pct: roundTo(c.m.change_pct, 2),
      trade_value: roundTo(qty * limitPrice, 2),
      reason: "FAMILY-" + c.family + " score=" + roundTo(c.score, 2) + " gap=" + roundTo(c.gap, 2) + "% vel=" + (c.vel === null ? "n/a" : roundTo(c.vel, 2) + "%") + " relVol=" + roundTo(c.relVol, 2) + " rangePos=" + roundTo(c.rangePos * 100, 0) + "% - sim order for review."
    });
  }
}

// cache for next run's velocity (every traded symbol) -> workflow static data
const cache_map = {};
for (const m of marketRows) {
  if ((m.volume || 0) > 0) cache_map[m.symbol] = { current: m.current, volume: m.volume, ts: runTimestamp };
}
STATIC.market_cache = cache_map;
STATIC.market_cache_ts = runTimestamp;

const actionable = signals.filter(s => s.action === "BUY" || s.action === "SELL");
const openai_request = {
  model: settings.groq_model || "qwen/qwen3.8-27b",
  temperature: 0.2,
  max_completion_tokens: 2500,
  response_format: { type: "json_object" },
  messages: [
    {
      role: "system",
      content:
    "You are a cautious PSX decision-support analyst for a simulated intraday book. Use only the JSON provided in the input. The input contains the DPS market snapshot summary, current holdings context, configured settings, and precomputed rule-based intraday signals (BUY=enter now, SELL=exit now). Do not estimate missing prices or invent symbols, quantities, prices, or actions. Return JSON only, no markdown. Quantity and limit price must be copied from the input signal, never increased or made more aggressive. Keep reasons short and based only on supplied fields. Include this warning in email_html: Simulated trading - review before acting. If there are no BUY or SELL rows, the subject must say that no trade action was triggered. signal_count must equal the number of rows returned. Return exactly this JSON shape and nothing else: {\"email_subject\": string, \"email_html\": string, \"signal_count\": integer, \"rows\": [{\"symbol\": string, \"action\": \"BUY\"|\"SELL\"|\"DO_NOTHING\"|\"NO_DATA\", \"quantity\": number, \"limit_price\": number|null, \"current_price\": number|null, \"market_volume\": number|null, \"reason\": string}]}."
    },
    {
      role: "user",
      content: JSON.stringify({
        run_timestamp: runTimestamp,
        cash_start: roundTo(cashStart, 2),
        market_rows_found: marketRows.length,
        eligible_count: eligible.length,
        breadth_pct: roundTo(breadth * 100, 1),
        med_change: roundTo(medChange, 2),
        regime_ok: regimeOk, entries_open: entriesOpen, eod_flat_time: eodFlatTime,
        open_positions: heldSet.size,
        settings: { stop_loss_pct: STOP_PCT, take_profit_arm_pct: ARM_PCT, trail_from_high_pct: TRAIL_PCT,
          max_open_positions: MAX_OPEN, default_max_trade_value: MAX_TRADE },
        signals
      })
    }
  ]
};

return [{
  json: {
    project_label: "PSX INTRADAY CAPITALIZER",
    run_timestamp: runTimestamp,
    source_url: "https://dps.psx.com.pk/market-watch",
    settings, cash_start: roundTo(cashStart, 2),
    market_rows_found: marketRows.length,
    eligible_count: eligible.length,
    breadth: roundTo(breadth * 100, 1),
    med_change: roundTo(medChange, 2),
    regime_ok: regimeOk, entries_open: entriesOpen, eod_flat_time: eodFlatTime,
    open_positions: heldSet.size,
    actionable_count: actionable.length,
    candidate_count: candidateCount,
    deployed_this_run: roundTo(deployed, 2),
    cache_size: Object.keys(cache_map).length,
    openai_request,
    signals
  }
}];
