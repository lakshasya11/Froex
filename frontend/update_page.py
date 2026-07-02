import sys
import re

file_path = "src/app/page.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
imports_addition = """import toast, { Toaster } from 'react-hot-toast';
import CountUp from 'react-countup';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
"""
content = content.replace("import { useEffect, useState } from 'react';", "import { useEffect, useState } from 'react';\n" + imports_addition)

# 2. Toaster component inside the main layout
# We will insert it right after the opening div of the main return
insertion_idx = content.find('<div className="min-h-screen bg-slate-50 text-slate-900')
if insertion_idx != -1:
    div_end = content.find('>', insertion_idx)
    content = content[:div_end+1] + '\n      <Toaster position="bottom-right" />' + content[div_end+1:]
else:
    print("Could not find main layout div")
    sys.exit(1)

# 3. Replace tradeMessage state and logic with react-hot-toast
# Replace: const [tradeMessage, setTradeMessage] = useState('');
content = content.replace("const [tradeMessage, setTradeMessage] = useState('');\n", "")

# Replace executeTrade block
old_execute_trade = """  const executeTrade = async (direction: string) => {
    setIsTrading(true);
    setTradeMessage('Executing trade in MT5 terminal...');
    
    try {
      const res = await fetch('/api/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          direction,
          count: parseFloat(tradeCount),
          lotSize: parseFloat(lotSize),
          sl: parseFloat(slPoints),
          tp: parseFloat(tpPoints)
        })
      });
      
      const data = await res.json();
      if (data.success) {
        setTradeMessage(`✅ SUCCESS:\\n${data.output}`);
        fetchTrades(); // instantly fetch new trades
        setTimeout(() => setTradeMessage(''), 8000); // Auto-hide after 8 seconds
      } else {
        setTradeMessage(`❌ FAILED:\\n${data.error || 'Unknown error'}`);
        setTimeout(() => setTradeMessage(''), 8000);
      }
    } catch (err: any) {
      setTradeMessage(`❌ ERROR:\\n${err.message}`);
      setTimeout(() => setTradeMessage(''), 8000);
    } finally {
      setIsTrading(false);
    }
  };"""

new_execute_trade = """  const executeTrade = async (direction: string) => {
    setIsTrading(true);
    const toastId = toast.loading('Executing trade in MT5 terminal...');
    
    try {
      const res = await fetch('/api/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          direction,
          count: parseFloat(tradeCount),
          lotSize: parseFloat(lotSize),
          sl: parseFloat(slPoints),
          tp: parseFloat(tpPoints)
        })
      });
      
      const data = await res.json();
      if (data.success) {
        toast.success(`Success:\\n${data.output}`, { id: toastId, duration: 5000 });
        fetchTrades(); // instantly fetch new trades
      } else {
        toast.error(`Failed:\\n${data.error || 'Unknown error'}`, { id: toastId, duration: 6000 });
      }
    } catch (err: any) {
      toast.error(`Error:\\n${err.message}`, { id: toastId, duration: 6000 });
    } finally {
      setIsTrading(false);
    }
  };"""

content = content.replace(old_execute_trade, new_execute_trade)

# Remove the tradeMessage display box
trade_msg_box = """          {tradeMessage && (
            <div className={`mt-4 p-3 rounded-lg text-sm border ${tradeMessage.includes('FAILED') || tradeMessage.includes('ERROR') ? 'bg-rose-500/10 border-rose-500/20 text-rose-300' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'}`}>
              <pre className="whitespace-pre-wrap font-mono text-xs">{tradeMessage}</pre>
            </div>
          )}"""
content = content.replace(trade_msg_box, "")

# 4. CountUp for Stats Cards
content = content.replace(
    '<span className="text-3xl font-black text-slate-900">${balance.toFixed(2)}</span>',
    '<span className="text-3xl font-black text-slate-900">$<CountUp end={balance} decimals={2} duration={1.5} preserveValue /></span>'
)
content = content.replace(
    '<p className="text-3xl font-black text-emerald-600">+${grossProfit.toFixed(2)}</p>',
    '<p className="text-3xl font-black text-emerald-600">+$<CountUp end={grossProfit} decimals={2} duration={1.5} preserveValue /></p>'
)
content = content.replace(
    '<p className="text-3xl font-black text-rose-600">-${Math.abs(grossLoss).toFixed(2)}</p>',
    '<p className="text-3xl font-black text-rose-600">-$<CountUp end={Math.abs(grossLoss)} decimals={2} duration={1.5} preserveValue /></p>'
)
content = content.replace(
    '<p className="text-xl font-bold text-emerald-600">${avgWin.toFixed(2)}</p>',
    '<p className="text-xl font-bold text-emerald-600">$<CountUp end={avgWin} decimals={2} duration={1.5} preserveValue /></p>'
)
content = content.replace(
    '<p className="text-xl font-bold text-rose-600">-${Math.abs(avgLoss).toFixed(2)}</p>',
    '<p className="text-xl font-bold text-rose-600">-$<CountUp end={Math.abs(avgLoss)} decimals={2} duration={1.5} preserveValue /></p>'
)

# 5. Insert Recharts P&L Equity Curve
# We will insert it just above the RECENT TRADES / NEWS TABLE
chart_code = """
      {/* P&L EQUITY CURVE */}
      {viewMode === 'trades' && filteredTrades.length > 0 && (
        <div className="max-w-7xl mx-auto mb-8 relative z-10">
          <div className="bg-white shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-200 p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
              Equity Curve (Net P&L)
            </h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={[...filteredTrades].reverse().map((t, i, arr) => {
                    const runningPnL = arr.slice(0, i + 1).reduce((sum, trade) => sum + trade.profit_dollars, 0);
                    return {
                      name: t.ticket,
                      pnl: runningPnL,
                      profit: t.profit_dollars,
                      date: t.entry_time.split(' ')[0],
                      time: t.entry_time.split(' ')[1]
                    };
                  })}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="colorPnL" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} tickMargin={10} minTickGap={30} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(val) => `$${val}`} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}
                    itemStyle={{ color: '#0f172a', fontWeight: 'bold' }}
                    labelStyle={{ color: '#64748b', marginBottom: '4px' }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cumulative P&L']}
                  />
                  <Area type="monotone" dataKey="pnl" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorPnL)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace("      {/* RECENT TRADES / NEWS TABLE */}", chart_code + "\n      {/* RECENT TRADES / NEWS TABLE */}")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
