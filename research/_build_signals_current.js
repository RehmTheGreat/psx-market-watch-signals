function toNumber(value, fallback = 0) {
  if (value === null || value === undefined) return fallback;

  const cleaned = String(value)
    .replace(/,/g, "")
    .replace(/%/g, "")
    .replace(/[^\d.-]/g, "")
    .trim();

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
  const factor = Math.pow(10, decimals);
  return Math.round(n * factor) / factor;
}

function roundDownToLot(quantity, lotSize) {
  const q = Math.floor(toNumber(quantity, 0));
  const lot = Math.max(1, Math.floor(toNumber(lotSize, 1)));
  return Math.floor(q / lot) * lot;
}

function safeRows(nodeName) {
  try {
    return $(nodeName).all().map(item => item.json);
  } catch (error) {
    return [];
  }
}

function parseMarketWatch(rawInput) {
  const raw = String(rawInput || "");
  const rows = [];

  const trMatches = raw.match(/<tr[\s\S]*?<\/tr>/gi) || [];

  for (const tr of trMatches) {
    const cells = [...tr.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)]
      .map(match => cleanHtml(match[1]))
      .filter(cell => cell !== "");

    if (cells.length >= 8) rows.push(cells);
  }

  const parsed = [];

  for (const cells of rows) {
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

    parsed.push({
      symbol,
      ldcp,
      open,
      high,
      low,
      current,
      change,
      change_pct,
      volume
    });
  }

  if (parsed.length > 0) return parsed;

  const text = cleanHtml(raw);
  const roughLines = text
    .split(/(?=[A-Z0-9]{2,12}\s+\d{4}\s+)/g)
    .map(line => line.trim())
    .filter(Boolean);

  for (const line of roughLines) {
    const parts = line.split(/\s+/);
    if (parts.length < 10) continue;

    const symbol = parts[0].toUpperCase();
    if (symbol === "SYMBOL") continue;

    const numericTail = parts
      .slice(1)
      .filter(p => /^-?[\d,.]+%?$/.test(p));

    if (numericTail.length < 7) continue;

    const volume = toNumber(numericTail[numericTail.length - 1], null);
    const change_pct = toNumber(numericTail[numericTail.length - 2], null);
    const change = toNumber(numericTail[numericTail.length - 3], null);
    const current = toNumber(numericTail[numericTail.length - 4], null);
    const low = toNumber(numericTail[numericTail.length - 5], null);
    const high = toNumber(numericTail[numericTail.length - 6], null);
    const open = toNumber(numericTail[numericTail.length - 7], null);
    const ldcp = toNumber(numericTail[numericTail.length - 8], null);

    if (current === null || !Number.isFinite(current)) continue;

    parsed.push({
      symbol,
      ldcp,
      open,
      high,
      low,
      current,
      change,
      change_pct,
      volume
    });
  }

  return parsed;
}

const holdingRows = safeRows("Read Holdings");
const cashRows = safeRows("Read Cash");
const settingsRows = safeRows("Read Settings");
const watchlistRows = safeRows("Read Watchlist");
const psxItem = $("Fetch PSX Market Watch").first()?.json || {};

const settings = {};

for (const row of settingsRows) {
  const key = String(row.key || row.Key || "").trim();
  const value = String(row.value || row.Value || "").trim();
  if (key) settings[key] = value;
}

const cashStart = cashRows.reduce((sum, row) => {
  return sum + toNumber(row.amount || row.Amount, 0);
}, 0);

const minBuy = toNumber(settings.min_change_pct_buy, 1);
const minSell = toNumber(settings.min_change_pct_sell, -1);
const maxCashFraction = toNumber(settings.max_cash_fraction_per_trade, 0.2);
const defaultMaxTradeValue = toNumber(settings.default_max_trade_value, 50000);
const defaultLotSize = Math.max(1, toNumber(settings.default_lot_size, 1));

const projectLabel = "PSX REAL MONEY SIGNALS";

const rawMarket =
  psxItem.body ||
  psxItem.data ||
  psxItem.response ||
  JSON.stringify(psxItem);

const marketRows = parseMarketWatch(rawMarket);

const marketBySymbol = {};
for (const row of marketRows) {
  marketBySymbol[row.symbol.toUpperCase()] = row;
}

const lots = holdingRows
  .map(row => ({
    symbol: String(row.symbol || row.Symbol || "").trim().toUpperCase(),
    lot_id: String(row.lot_id || row.Lot_id || row.lot || "").trim(),
    shares: toNumber(row.shares || row.Shares, 0),
    avg_price: toNumber(row.avg_price || row.Avg_price || row["avg price"], 0),
    max_trade_value: toNumber(row.max_trade_value || row.Max_trade_value, defaultMaxTradeValue),
    lot_size: Math.max(1, toNumber(row.lot_size || row.Lot_size, defaultLotSize))
  }))
  .filter(row => row.symbol);

const watchlist = watchlistRows
  .map(row => ({
    symbol: String(row.symbol || row.Symbol || "").trim().toUpperCase(),
    max_trade_value: toNumber(row.max_trade_value || row.Max_trade_value, defaultMaxTradeValue),
    lot_size: Math.max(1, toNumber(row.lot_size || row.Lot_size, defaultLotSize))
  }))
  .filter(row => row.symbol);

const holdingsBySymbol = {};

for (const lot of lots) {
  if (!holdingsBySymbol[lot.symbol]) {
    holdingsBySymbol[lot.symbol] = {
      symbol: lot.symbol,
      total_shares: 0,
      total_cost: 0,
      weighted_avg_price: 0,
      max_trade_value: 0,
      lot_size: lot.lot_size,
      lots: []
    };
  }

  const group = holdingsBySymbol[lot.symbol];

  group.total_shares += lot.shares;
  group.total_cost += lot.shares * lot.avg_price;
  group.max_trade_value = Math.max(group.max_trade_value, lot.max_trade_value);
  group.lot_size = Math.max(1, Math.min(group.lot_size, lot.lot_size));
  group.lots.push(lot);
}

for (const item of watchlist) {
  if (!holdingsBySymbol[item.symbol]) {
    holdingsBySymbol[item.symbol] = {
      symbol: item.symbol,
      total_shares: 0,
      total_cost: 0,
      weighted_avg_price: 0,
      max_trade_value: item.max_trade_value || defaultMaxTradeValue,
      lot_size: item.lot_size || defaultLotSize,
      lots: []
    };
  }
}

for (const group of Object.values(holdingsBySymbol)) {
  group.weighted_avg_price =
    group.total_shares > 0 ? group.total_cost / group.total_shares : 0;

  if (!group.max_trade_value || group.max_trade_value <= 0) {
    group.max_trade_value = defaultMaxTradeValue;
  }

  if (!group.lot_size || group.lot_size <= 0) {
    group.lot_size = defaultLotSize;
  }
}

let simulatedCashRemaining = cashStart;
const signals = [];

for (const holding of Object.values(holdingsBySymbol)) {
  const market = marketBySymbol[holding.symbol];

  if (!market) {
    signals.push({
      symbol: holding.symbol,
      action: "NO_DATA",
      quantity: 0,
      limit_price: null,
      current_price: null,
      weighted_avg_price: roundTo(holding.weighted_avg_price, 2),
      total_shares: holding.total_shares,
      market_volume: null,
      change_pct: null,
      trade_value: 0,
      reason: "Symbol was not found in the fetched DPS PSX market-watch data."
    });
    continue;
  }

  let action = "DO_NOTHING";
  let quantity = 0;
  let limitPrice = market.current;
  let reason = "No trade rule triggered.";

  const maxTradeValue = Math.min(
    defaultMaxTradeValue,
    simulatedCashRemaining * maxCashFraction
  );

  const avgCost = Number(holding.weighted_avg_price) || 0;
  const takeProfitArm = Number(settings.take_profit_arm_pct) || 5;
  const trailFromHigh = Number(settings.trail_from_high_pct) || 2;
  const isFinalSession = new Date().toISOString().slice(0, 10) >= "2026-09-19";
  if (holding.total_shares > 0 && avgCost > 0 && market.high > 0
      && market.current >= avgCost * (1 + takeProfitArm / 100)
      && market.current <= market.high * (1 - trailFromHigh / 100)) {
    action = "SELL";
    quantity = holding.total_shares;
    limitPrice = market.current * 0.995;
    reason = "Profit-lock SELL ALL: up " + (Math.round((market.current / avgCost - 1) * 10000) / 100) + "% vs avg cost " + avgCost + " (armed at +" + takeProfitArm + "%) and faded " + trailFromHigh + "% off day high " + market.high + ". Human review required before placing order.";
    simulatedCashRemaining += quantity * limitPrice;
  } else if (holding.total_shares > 0 && market.change_pct <= minSell) {
    action = "SELL";
    quantity = roundDownToLot(
      Math.max(holding.lot_size, holding.total_shares * 0.5),
      holding.lot_size
    );
    quantity = Math.min(quantity, holding.total_shares);
    limitPrice = market.current * 0.995;

    if (quantity <= 0) {
      action = "DO_NOTHING";
      quantity = 0;
      limitPrice = market.current;
      reason = "Sell rule triggered, but no sellable quantity was available.";
    } else {
      reason = `Candidate SELL: change_pct ${market.change_pct}% is <= sell threshold ${minSell}%. Human review required before placing order.`;
      simulatedCashRemaining += quantity * limitPrice;
    }
  } else if (holding.total_shares <= 0 && market.change_pct >= minBuy && simulatedCashRemaining > 0
      && !isFinalSession && market.high > 0 && market.current >= market.high * 0.99
      && (!market.volume || market.current * market.volume >= (Number(settings.min_traded_value_floor) || 0))) {
    action = "BUY";
    quantity = roundDownToLot(maxTradeValue / market.current, holding.lot_size);
    limitPrice = market.current * 1.005;

    if (quantity <= 0) {
      action = "DO_NOTHING";
      quantity = 0;
      limitPrice = market.current;
      reason = "Buy rule triggered, but available cash was too small for the lot size.";
    } else {
      reason = `Candidate BUY: change_pct ${market.change_pct}% is >= buy threshold ${minBuy}%. Human review required before placing order.`;
      simulatedCashRemaining -= quantity * limitPrice;
    }
  } else {
    action = "DO_NOTHING";
    quantity = 0;
    limitPrice = market.current;
    reason = `No trade rule triggered: shares=${holding.total_shares}, change_pct=${market.change_pct}%, buy threshold=${minBuy}%, sell threshold=${minSell}%.`;
  }

  const tradeValue = quantity * limitPrice;

  signals.push({
    symbol: holding.symbol,
    action,
    quantity,
    limit_price: roundTo(limitPrice, 2),
    current_price: roundTo(market.current, 2),
    weighted_avg_price: roundTo(holding.weighted_avg_price, 2),
    total_shares: holding.total_shares,
    open_price: roundTo(market.open, 2),
    high_price: roundTo(market.high, 2),
    low_price: roundTo(market.low, 2),
    market_volume: market.volume,
    change_pct: roundTo(market.change_pct, 2),
    trade_value: roundTo(tradeValue, 2),
    reason
  });
}

// ALWAYS-DEPLOY FALLBACK (pc ruling 2026-09-15)
const alwaysDeploy = String(settings.always_deploy == null ? "FALSE" : settings.always_deploy).toUpperCase() === "TRUE";
const isExperimentEnd = new Date().toISOString().slice(0, 10) >= "2026-09-19";
if (alwaysDeploy && !isExperimentEnd && simulatedCashRemaining > 0) {
  const hasBuy = signals.some(s => s.action === "BUY");
  if (!hasBuy) {
    const floorValue = Number(settings.min_traded_value_floor) || 0;
    const candidates = [];
    for (const item of watchlist) {
      const held = holdingsBySymbol[item.symbol];
      if (held && held.total_shares > 0) continue;
      const market = marketBySymbol[item.symbol];
      if (!market || !(market.current > 0) || !(market.high > market.low)) continue;
      if (market.volume && market.current * market.volume < floorValue) continue;
      const rangePos = (market.current - market.low) / (market.high - market.low);
      const turnover = market.current * (market.volume || 0);
      const score = (market.change_pct || 0) * 4 + rangePos * 30 + Math.min(turnover / 100000000, 1) * 30;
      candidates.push({ item: item, market: market, score: Math.round(score * 100) / 100 });
    }
    candidates.sort((a, b) => b.score - a.score);
    const pick = candidates[0];
    if (pick) {
      const capValue = Math.min(pick.item.max_trade_value || defaultMaxTradeValue, simulatedCashRemaining * maxCashFraction);
      const qty = roundDownToLot(capValue / pick.market.current, pick.item.lot_size || defaultLotSize);
      if (qty > 0) {
        const limitPrice = pick.market.current * 1.005;
        simulatedCashRemaining -= qty * limitPrice;
        const rangePosPct = Math.round(((pick.market.current - pick.market.low) / (pick.market.high - pick.market.low)) * 100);
        signals.push({
          symbol: pick.item.symbol,
          action: "BUY",
          quantity: qty,
          limit_price: roundTo(limitPrice, 2),
          current_price: roundTo(pick.market.current, 2),
          weighted_avg_price: 0,
          total_shares: 0,
          open_price: roundTo(pick.market.open, 2),
          high_price: roundTo(pick.market.high, 2),
          low_price: roundTo(pick.market.low, 2),
          market_volume: pick.market.volume,
          change_pct: roundTo(pick.market.change_pct, 2),
          trade_value: roundTo(qty * limitPrice, 2),
          reason: "Always-deploy BUY: strongest ranked not-held watchlist candidate this run (score " + pick.score + ", change_pct " + roundTo(pick.market.change_pct, 2) + "%, at " + rangePosPct + "% of day range). Human review required before placing order."
        });
      }
    }
  }
}

const runTimestamp = new Date().toISOString();

const openaiRequest = {
  model: settings.groq_model || "qwen/qwen3.8-27b",
  temperature: 0.2,
  max_completion_tokens: 2500,
  response_format: { type: "json_object" },
  messages: [
    {
      role: "system",
      content:
    "You are a cautious PSX decision-support analyst for a real-money portfolio. Use only the JSON provided in the input. The input contains DPS PSX market-watch data, portfolio holdings, available cash, configured risk settings, and precomputed rule-based signals. Do not estimate missing prices, infer missing volumes, or invent symbols, quantities, prices, cash balances, or actions. Return JSON only. Do not include markdown outside JSON. Do not override the provided numeric data. Do not invent new trades. Do not recommend margin, leverage, short selling, aggressive averaging down, or all-in trades. If market data is missing, stale, inconsistent, or impossible, mark the row as NO_DATA or DO_NOTHING and explain why. BUY means candidate buy signal for human review. SELL means candidate sell signal for human review. DO_NOTHING means no trade candidate based on supplied rules/data. Quantity must be copied from the input signal. Never increase it. Limit price must be copied from the input signal. Never make it more aggressive. Keep reasons short, specific, and based only on supplied fields such as change_pct, current_price, weighted_avg_price, market_volume, cash, holdings, and configured thresholds. Include this warning in email_html: Real money involved — review manually before placing any order. If there are no BUY or SELL rows, the subject must say that no trade action was triggered. signal_count must equal the number of rows returned. Return exactly this JSON shape and nothing else: {\"email_subject\": string, \"email_html\": string, \"signal_count\": integer, \"rows\": [{\"symbol\": string, \"action\": \"BUY\"|\"SELL\"|\"DO_NOTHING\"|\"NO_DATA\", \"quantity\": number, \"limit_price\": number|null, \"current_price\": number|null, \"market_volume\": number|null, \"reason\": string}]}. Output raw JSON with no markdown fences.",
    },
    {
      role: "user",
      content: JSON.stringify({
    run_timestamp: runTimestamp,
    cash_start: roundTo(cashStart, 2),
    simulated_cash_remaining: roundTo(simulatedCashRemaining, 2),
    market_rows_found: marketRows.length,
    lots,
    watchlist,
    cash_rows: cashRows,
    settings: {
      min_change_pct_buy: minBuy,
      min_change_pct_sell: minSell,
      max_cash_fraction_per_trade: maxCashFraction,
      default_max_trade_value: defaultMaxTradeValue,
      default_lot_size: defaultLotSize
    },
    signals
  })
    }
  ]
};

return [
  {
    json: {
      project_label: projectLabel,
      run_timestamp: runTimestamp,
      source_url: "https://dps.psx.com.pk/market-watch",
      settings,
      lots,
      watchlist,
      holdings: Object.values(holdingsBySymbol),
      cash_rows: cashRows,
      cash_start: roundTo(cashStart, 2),
      simulated_cash_remaining: roundTo(simulatedCashRemaining, 2),
      market_rows_found: marketRows.length,
      signals,
      openai_request: openaiRequest
    }
  }
];