import React from 'react';
import { TrendingUp, TrendingDown, Target } from 'lucide-react';

export default React.memo(function TradeHistory({ trades }: { trades: any[] }) {
  return (
            <table className="w-full text-left border-collapse relative">
              <thead className="sticky top-0 z-20">
                <tr className="bg-slate-50/95 backdrop-blur-md text-slate-600 text-xs uppercase tracking-wider font-semibold border-b border-slate-200 shadow-sm">
                  <th className="p-5">Entry Time</th>
                  <th className="p-5">Exit Time</th>
                  <th className="p-5 text-right">Duration</th>
                  <th className="p-5">Direction</th>
                  <th className="p-5 text-right">Lot Size</th>
                  <th className="p-5 text-right">Entry</th>
                  <th className="p-5 text-right">Exit</th>
                  <th className="p-5">Reason</th>
                  <th className="p-5 text-right">Points</th>
                  <th className="p-5 text-right">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {trades.map((trade) => {
                  // The database stores time as UTC: "YYYY-MM-DD HH:MM:SS"
                  let istTime = "";
                  let stockTime = trade.entry_time.split(' ')[1];
                  const dateStr = trade.entry_time.split(' ')[0].slice(5); // MM-DD
                  
                  try {
                    const utcDate = new Date(trade.entry_time.replace(' ', 'T') + 'Z');
                    if (!isNaN(utcDate.getTime())) {
                      istTime = new Intl.DateTimeFormat('en-US', {
                        timeZone: 'Asia/Kolkata',
                        hour: 'numeric',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: true
                      }).format(utcDate);

                      stockTime = new Intl.DateTimeFormat('en-US', {
                        timeZone: 'America/New_York',
                        hour: 'numeric',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: true
                      }).format(utcDate);
                    }
                  } catch {
                    istTime = "Err";
                  }

                  let istExit = "";
                  let stockExit = trade.exit_time ? trade.exit_time.split(' ')[1] : "";
                  try {
                    if (trade.exit_time) {
                      const utcExit = new Date(trade.exit_time.replace(' ', 'T') + 'Z');
                      if (!isNaN(utcExit.getTime())) {
                        istExit = new Intl.DateTimeFormat('en-US', {
                          timeZone: 'Asia/Kolkata',
                          hour: 'numeric',
                          minute: '2-digit',
                          second: '2-digit',
                          hour12: true
                        }).format(utcExit);
                        stockExit = new Intl.DateTimeFormat('en-US', {
                          timeZone: 'America/New_York',
                          hour: 'numeric',
                          minute: '2-digit',
                          second: '2-digit',
                          hour12: true
                        }).format(utcExit);
                      }
                    }
                  } catch {}

                  let displayDuration = trade.duration_seconds ? trade.duration_seconds + "s" : "-";
                  try {
                    if (trade.exit_time && trade.entry_time) {
                      const t1 = new Date(trade.entry_time.replace(' ', 'T') + 'Z').getTime();
                      const t2 = new Date(trade.exit_time.replace(' ', 'T') + 'Z').getTime();
                      if (!isNaN(t1) && !isNaN(t2)) {
                        const diffSecs = Math.round((t2 - t1) / 1000);
                        if (diffSecs >= 0) displayDuration = diffSecs + "s";
                      }
                    }
                  } catch {}

                  return (
                  <tr key={trade.id} className="hover:bg-slate-50 transition-colors group">
                    <td className="p-5 whitespace-nowrap">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-900 font-bold text-sm tracking-wide">{istTime || stockTime}</span>
                          <span className="text-[10px] font-extrabold text-emerald-500 bg-emerald-500/5 px-1 py-0.5 rounded">IST</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-900 font-medium text-xs tracking-wide">{stockTime}</span>
                          <span className="text-[10px] font-bold text-slate-900">NY (EST)</span>
                        </div>
                      </div>
                    </td>
                    <td className="p-5 whitespace-nowrap border-l border-slate-100">
                      {trade.exit_time ? (
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-900 font-bold text-sm tracking-wide">{istExit || stockExit}</span>
                            <span className="text-[10px] font-extrabold text-slate-500 bg-slate-100 px-1 py-0.5 rounded">IST</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-900 font-medium text-xs tracking-wide">{stockExit}</span>
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-400 font-medium text-xs">Active</span>
                      )}
                    </td>
                    <td className="p-5 text-right font-mono whitespace-nowrap">
                      {displayDuration !== "-" ? (
                        <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded-md">
                          {displayDuration}
                        </span>
                      ) : (
                        <span className="text-slate-400 font-medium text-xs">-</span>
                      )}
                    </td>
                    <td className="p-5">
                      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold ${
                        trade.direction === 'BUY' 
                          ? 'bg-emerald-500/5 text-emerald-600 border border-emerald-500/20' 
                          : 'bg-rose-500/5 text-rose-600 border border-rose-500/20'
                      }`}>
                        {trade.direction === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {trade.direction}
                      </div>
                    </td>
                    <td className="p-5 text-right font-mono text-indigo-600 text-sm font-bold">
                      {trade.volume ? trade.volume.toFixed(2) : '-'}
                    </td>
                    <td className="p-5 text-right font-mono text-slate-900 text-sm">{trade.entry_price.toFixed(2)}</td>
                    <td className="p-5 text-right font-mono text-slate-900 text-sm">{trade.exit_price.toFixed(2)}</td>
                    <td className="p-5">
                      <span className="text-xs font-medium text-slate-900 bg-slate-200 text-slate-700 px-2 py-1 rounded">
                        {trade.exit_reason || 'Manual'}
                      </span>
                    </td>
                    <td className={`p-5 text-right font-mono font-medium text-sm ${
                      trade.profit_points > 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}>
                      {trade.profit_points > 0 ? '+' : ''}{trade.profit_points.toFixed(2)}
                    </td>
                    <td className="p-5 text-right">
                      <div className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-bold ${
                        trade.profit_dollars > 0 
                          ? 'bg-emerald-500/5 text-emerald-600' 
                          : 'bg-rose-500/5 text-rose-600'
                      }`}>
                        {trade.profit_dollars > 0 ? '+$' : '-$'}
                        {Math.abs(trade.profit_dollars).toFixed(2)}
                      </div>
                    </td>
                  </tr>
                  );
                })}
                {trades.length === 0 && (
                  <tr>
                    <td colSpan={10} className="p-12 text-center text-slate-900">
                      <Target className="w-12 h-12 mx-auto mb-4 opacity-20" />
                      No trades found for this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

  );
});
