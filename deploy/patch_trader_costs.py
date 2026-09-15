P = r"C:\Users\pc\Desktop\Claude\psx-market-watch-signals\deploy\build_workflows.py"
s = open(P, encoding="utf-8").read()

start_marker = 'apply_ = code_node("Apply Trades", """const run=$(\'Decide\').first().json;'
end_marker = 'return [{json:{lots,cash,trades,last_row:run.max_row}}];""", [1160, 300])'
start = s.index(start_marker)
end = s.index(end_marker) + len(end_marker)

new_block = '''apply_ = code_node("Apply Trades", """const run=$('Decide').first().json;
if (run.mode!=='trade') return [{json:{noop:true}}];
const FEE=6/10000;   // per side; Settings round_trip_cost_bps=12 split across the round trip
const CGT=0.15;      // Settings cgt_pct: NCCPL-withheld tax on realized intraday gains
let cash=$('Read Cash').all().reduce((a,i)=>a+Number(i.json.amount||0),0);
const lots=$('Read Holding').all().map(i=>({symbol:i.json.symbol,lot_id:i.json.lot_id,shares:Number(i.json.shares||0),avg_price:Number(i.json.avg_price||0),max_trade_value:Number(i.json.max_trade_value||100000),lot_size:Number(i.json.lot_size||1)})).filter(l=>l.shares>0);
const trades=[];
for (const s of run.new_signals){
  const price=Number(s.current_price)||Number(s.limit_price)||0;
  const base={ts:s.run_ts||new Date().toISOString(),symbol:s.symbol};
  if (!(price>0)){trades.push({...base,side:'SKIP',quantity:0,price:0,value:0,cash_after:Math.round(cash*100)/100,note:'no price'});continue;}
  if (s.action==='BUY'){
    let qty=Math.floor(Number(s.quantity)||0);
    if (qty<=0){trades.push({...base,side:'SKIP',quantity:0,price,value:0,cash_after:Math.round(cash*100)/100,note:'qty 0'});continue;}
    let cost=qty*price;
    let fee=cost*FEE;
    if (cost+fee>cash){qty=Math.floor(cash/(price*(1+FEE)));cost=qty*price;fee=cost*FEE;}
    if (qty<=0){trades.push({...base,side:'SKIP',quantity:0,price,value:0,cash_after:Math.round(cash*100)/100,note:'insufficient cash'});continue;}
    lots.push({symbol:s.symbol,lot_id:'v'+Date.now()+Math.random().toString(36).slice(2,5),shares:qty,avg_price:price,max_trade_value:100000,lot_size:1});
    cash-=(cost+fee);
    trades.push({...base,side:'BUY',quantity:qty,price,value:Math.round(cost*100)/100,cash_after:Math.round(cash*100)/100,note:'auto fee='+Math.round(fee)+' | '+String(s.reason||'').slice(0,70)});
  } else if (s.action==='SELL'){
    const held=lots.filter(l=>l.symbol===s.symbol);
    const heldQty=held.reduce((a,l)=>a+l.shares,0);
    const qty=Math.min(Number(s.quantity)||0, heldQty);
    if (qty<=0){trades.push({...base,side:'SKIP',quantity:0,price,value:0,cash_after:Math.round(cash*100)/100,note:'no holding'});continue;}
    let remaining=qty, proceeds=0, costBasis=0;
    for (const l of held){ if (remaining<=0) break; const take=Math.min(remaining,l.shares); proceeds+=take*price; costBasis+=take*l.avg_price; l.shares-=take; remaining-=take; }
    for (let k=lots.length-1;k>=0;k--){ if (lots[k].shares<=0) lots.splice(k,1); }
    const fee=proceeds*FEE;
    const realized=proceeds-costBasis;
    const tax=realized>0?realized*CGT:0;
    cash+=(proceeds-fee-tax);
    trades.push({...base,side:'SELL',quantity:qty,price,value:Math.round(proceeds*100)/100,cash_after:Math.round(cash*100)/100,note:'auto fee='+Math.round(fee)+' tax='+Math.round(tax)+' pnl='+Math.round(realized)+' | '+String(s.reason||'').slice(0,60)});
  }
}
return [{json:{lots,cash,trades,last_row:run.max_row}}];""", [1160, 300])'''

s = s[:start] + new_block + s[end:]
open(P, "w", encoding="utf-8").write(s)
print("Apply Trades updated: fees + CGT + proportional multi-lot sells")
