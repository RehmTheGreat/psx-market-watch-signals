// Harness: run engine_v1.js with mocked clock/inputs to exercise the ENTRY path.
const fs = require("fs");
const code = fs.readFileSync(__dirname + "/engine_v1.js", "utf-8");

// mock clock: 2026-09-16 09:50:00 PKT = 04:50 UTC (Wednesday)
const MOCK_MS = Date.UTC(2026, 8, 16, 4, 50, 0);
const RealDate = Date;
class MockDate extends RealDate {
  constructor(...args) { if (args.length === 0) super(MOCK_MS); else super(...args); }
  static now() { return MOCK_MS; }
}
global.Date = MockDate;

// mock inputs
const mk = (symbol, ldcp, open, high, low, current, volume, indices) =>
  ({ symbol, ldcp, open, high, low, current, change: current - ldcp, change_pct: (current / ldcp - 1) * 100, volume, indices });
const marketRows = [
  mk("GAPDOWN", 100, 98.0, 99.5, 97.8, 99.0, 3_000_000, "KSE100"),        // A: gap -2%, recovered above open
  mk("MOMO", 50, 50.2, 52.0, 50.0, 51.6, 8_000_000, "KSE100"),            // B: moving now
  mk("FADEUP", 100, 102.5, 103.0, 101.9, 102.2, 2_000_000, "KSE100"),     // gap +2.5% -> fade zone, excluded
  mk("LOCKDN", 100, 91.0, 92.0, 90.2, 90.5, 1_000_000, "KSE100"),         // change -9.5% -> band+lock excluded
  mk("PENNY", 3, 3.1, 3.4, 3.0, 3.3, 50_000_000, ""),                     // price < 5 excluded
  mk("FLAT", 100, 100, 100.4, 99.7, 100.1, 500_000, "KSE100"),            // no trigger
];
const round2 = n => Math.round(n * 100) / 100;
for (let i = 0; i < 60; i++) {
  const p = 40 + i;
  marketRows.push(mk("FILL" + i, p, p * 1.001, p * 1.006, p * 0.999, p * 1.002, 300_000, ""));
}
const psxBody = marketRows.map(m =>
  `<tr><td>${m.symbol}</td><td>1</td><td>${m.indices}</td><td>${m.ldcp}</td><td>${m.open}</td><td>${m.high}</td><td>${m.low}</td><td>${m.current}</td><td>${round2(m.change)}</td><td>${round2(m.change_pct)}%</td><td>${m.volume}</td></tr>`).join("");
const cache = { GAPDOWN: { current: 98.9, volume: 2_900_000, ts: "x" }, MOMO: { current: 51.2, volume: 7_500_000, ts: "x" } }; // 10 min old

const ctx = {
  "Read Holdings": [], "Read Cash": [{ amount: "500000" }],
  "Read Settings": [{ key: "stop_loss_pct", value: "1.5" }, { key: "default_max_trade_value", value: "100000" }, { key: "always_deploy", value: "FALSE" }],
  "Read Watchlist": [], "Read Cache": [],
};
const staticData = { market_cache: cache, market_cache_ts: new (MockDate)(MOCK_MS - 10 * 60 * 1000).toISOString() };
const $getWorkflowStaticData = () => staticData;
const $ = (name) => ({
  all: () => (ctx[name] || []).map(j => ({ json: j })),
  first: () => ({ json: name === "Fetch PSX Market Watch" ? { body: psxBody } : (ctx[name] || [{}])[0] }),
});
const fn = new Function("$", "$getWorkflowStaticData", code);
const out = fn($, $getWorkflowStaticData)[0].json;

console.log("eligible:", out.eligible_count, "| breadth:", out.breadth, "| entries_open:", out.entries_open, "| regime_ok:", out.regime_ok);
console.log("actionable:", out.actionable_count, "| cache_size:", out.cache_size);
for (const s of out.signals) {
  console.log("SIGNAL:", s.symbol, s.action, "qty", s.quantity, "px", s.current_price, "|", s.reason.slice(0, 90));
}
const buys = out.signals.filter(s => s.action === "BUY").map(s => s.symbol).sort();
const expected = ["GAPDOWN", "MOMO"];
console.log("PASS:", JSON.stringify(buys) === JSON.stringify(expected), "(expected", JSON.stringify(expected), ")");
console.log("static cache updated:", Object.keys(staticData.market_cache).length >= marketRows.length);
