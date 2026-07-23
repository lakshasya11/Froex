'use client';

import React, { useState } from 'react';
import toast from 'react-hot-toast';

interface ManualPanelProps {
  onTradeExecuted: () => void;
}

export default function ManualPanel({ onTradeExecuted }: ManualPanelProps) {
  const [tradeCount, setTradeCount] = useState('1');
  const [lotSize, setLotSize] = useState('0.15');
  const [slPoints, setSlPoints] = useState('2.0');
  const [tpPoints, setTpPoints] = useState('5.0');
  const [manualTimeframe, setManualTimeframe] = useState('M5');
  const [trailTrigger, setTrailTrigger] = useState('2.0');
  const [trailGap, setTrailGap] = useState('1.5');
  const [isTrading, setIsTrading] = useState(false);

  const executeTrade = async (direction: 'BUY' | 'SELL') => {
    if (isTrading) return;
    if (!lotSize || !tradeCount || !slPoints || !tpPoints || !trailTrigger || !trailGap) {
      toast.error('Please fill all fields');
      return;
    }

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
          tp: parseFloat(tpPoints),
          timeframe: manualTimeframe,
          trailTrigger: parseFloat(trailTrigger),
          trailGap: parseFloat(trailGap)
        })
      });
      
      const data = await res.json();
      if (data.success) {
        toast.success(`Success:\n${data.output}`, { id: toastId, duration: 5000 });
        onTradeExecuted();
      } else {
        toast.error(`Failed:\n${data.error || 'Unknown error'}`, { id: toastId, duration: 6000 });
      }
    } catch (err: any) {
      toast.error(`Error:\n${err.message}`, { id: toastId, duration: 6000 });
    } finally {
      setIsTrading(false);
    }
  };

  const executeExit = async (ticket: number | string) => {
    setIsTrading(true);
    const toastId = toast.loading(ticket === 'ALL' ? 'Closing all trades...' : `Closing trade #${ticket}...`);
    
    try {
      const res = await fetch('/api/manual_exit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket })
      });
      
      const data = await res.json();
      if (data.success) {
        toast.success(`Success:\n${data.output}`, { id: toastId, duration: 5000 });
        onTradeExecuted();
      } else {
        toast.error(`Failed:\n${data.error || 'Unknown error'}`, { id: toastId, duration: 6000 });
      }
    } catch (err: any) {
      toast.error(`Error:\n${err.message}`, { id: toastId, duration: 6000 });
    } finally {
      setIsTrading(false);
    }
  };

  return (
    <div className="p-4 overflow-y-auto flex-1 space-y-6 custom-scrollbar pb-32">
      <div className="space-y-3">
        <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest border-b border-slate-100 pb-1">Execution Config</h3>
        
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Lot Size</label>
            <input 
              type="number" step="0.01" 
              value={lotSize} onChange={(e) => setLotSize(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Trades count</label>
            <input 
              type="number" step="1" 
              value={tradeCount} onChange={(e) => setTradeCount(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">SL (Points)</label>
            <input 
              type="number" step="0.1" 
              value={slPoints} onChange={(e) => setSlPoints(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">TP (Points)</label>
            <input 
              type="number" step="0.1" 
              value={tpPoints} onChange={(e) => setTpPoints(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-slate-700">Timeframe</label>
          <select 
            value={manualTimeframe} onChange={(e) => setManualTimeframe(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="M1">M1</option>
            <option value="M5">M5</option>
            <option value="M15">M15</option>
            <option value="M30">M30</option>
            <option value="H1">H1</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Trail Trigger</label>
            <input 
              type="number" step="0.1" 
              value={trailTrigger} onChange={(e) => setTrailTrigger(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Trail Gap</label>
            <input 
              type="number" step="0.1" 
              value={trailGap} onChange={(e) => setTrailGap(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 p-4 bg-white border-t border-slate-200 flex gap-2">
        <button
          disabled={isTrading}
          onClick={() => executeTrade('BUY')}
          className="flex-1 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-bold shadow-lg shadow-blue-500/30 transition-all disabled:opacity-50"
        >
          BUY
        </button>
        <button
          disabled={isTrading}
          onClick={() => executeExit('ALL')}
          className="flex-1 py-3 bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-600 rounded-lg font-bold transition-all disabled:opacity-50 uppercase"
        >
          Close All
        </button>
        <button
          disabled={isTrading}
          onClick={() => executeTrade('SELL')}
          className="flex-1 py-3 bg-fuchsia-500 hover:bg-fuchsia-600 text-white rounded-lg font-bold shadow-lg shadow-fuchsia-500/30 transition-all disabled:opacity-50"
        >
          SELL
        </button>
      </div>
    </div>
  );
}
