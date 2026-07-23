'use client';

import React, { useState, useEffect } from 'react';
import { Play, Square } from 'lucide-react';

export default function SettingsPanel() {
  const [config, setConfig] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/config')
      .then(res => res.json())
      .then(data => {
        // Apply defaults if empty
        setConfig({
          BOT_STATE: 'STOPPED',
          TRADING_MODE: 'Paper Trading',
          TIMEFRAME: 'M5',
          SYMBOL: 'XAUUSD',
          LOT_SIZE: 0.15,
          MAX_DAILY_TRADES: 20,
          DAILY_TAKE_PROFIT: 100,
          DAILY_STOP_LOSS: 50,
          ...data
        });
        setLoading(false);
      });
  }, []);

  const handleSave = async (overrideConfig?: any) => {
    const newConfig = overrideConfig || config;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    });
    setConfig(newConfig);
    if (!overrideConfig) alert('Settings saved successfully!');
  };

  const handleConfigChange = (key: string, value: any) => {
    const newConfig = { ...config, [key]: value };
    setConfig(newConfig);
    // Auto-save silently
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    });
  };

  if (loading) return <div className="p-4 text-slate-500">Loading settings...</div>;

  return (
    <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden h-full flex flex-col relative">
      <div className="bg-slate-900 px-6 py-4 flex justify-between items-center z-10 shadow-md">
        <h2 className="text-white font-bold tracking-wide flex items-center gap-2">
          <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
          Bot Parameters
        </h2>
      </div>
      
      <div className="p-4 overflow-y-auto flex-1 space-y-6 custom-scrollbar pb-32">
        
        {/* Parameters */}
        <div className="space-y-3">
          <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest border-b border-slate-100 pb-1">Parameters</h3>
          
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Symbol</label>
            <input type="text" value={config.SYMBOL || ''} onChange={e => handleConfigChange('SYMBOL', e.target.value)} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-shadow disabled:opacity-60 disabled:cursor-not-allowed" />
          </div>
          
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-slate-700">Timeframe</label>
              <select value={config.TIMEFRAME || 'M5'} onChange={e => handleConfigChange('TIMEFRAME', e.target.value)} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed">
                <option value="M1">M1</option>
                <option value="M5">M5</option>
                <option value="M15">M15</option>
                <option value="M30">M30</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-slate-700">Trading Mode</label>
              <select value={config.TRADING_MODE || 'Paper Trading'} onChange={e => handleConfigChange('TRADING_MODE', e.target.value)} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed">
                <option value="Live">Live</option>
                <option value="Paper Trading">Paper Trading</option>
              </select>
            </div>
          </div>
          
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Lot Size</label>
            <input type="number" step="0.01" value={config.LOT_SIZE ?? ''} onChange={e => handleConfigChange('LOT_SIZE', parseFloat(e.target.value))} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-shadow disabled:opacity-60 disabled:cursor-not-allowed" />
          </div>
        </div>

        {/* Risk Management */}
        <div className="space-y-3">
          <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest border-b border-slate-100 pb-1">Risk Management</h3>
          
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-slate-700">Daily Take Profit ($)</label>
              <input type="number" value={config.DAILY_TAKE_PROFIT ?? ''} onChange={e => handleConfigChange('DAILY_TAKE_PROFIT', parseFloat(e.target.value))} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-shadow disabled:opacity-60 disabled:cursor-not-allowed" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-slate-700">Daily Stop Loss ($)</label>
              <input type="number" value={config.DAILY_STOP_LOSS ?? ''} onChange={e => handleConfigChange('DAILY_STOP_LOSS', parseFloat(e.target.value))} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-shadow disabled:opacity-60 disabled:cursor-not-allowed" />
            </div>
          </div>


          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700">Max Daily Trades</label>
            <input type="number" value={config.MAX_DAILY_TRADES ?? ''} onChange={e => handleConfigChange('MAX_DAILY_TRADES', parseInt(e.target.value))} disabled={config.BOT_STATE === 'RUNNING'} className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-sm font-medium focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-shadow disabled:opacity-60 disabled:cursor-not-allowed" />
          </div>
        </div>
      </div>

      {/* START/STOP Controls */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-white border-t border-slate-200 flex gap-2">
        <button 
          onClick={() => handleConfigChange('BOT_STATE', 'RUNNING')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg font-bold transition-all ${
            config.BOT_STATE === 'RUNNING' 
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
              : 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20'
          }`}
          disabled={config.BOT_STATE === 'RUNNING'}
        >
          <Play className="w-4 h-4" /> Start Bot
        </button>
        <button 
          onClick={() => handleConfigChange('BOT_STATE', 'STOPPED')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg font-bold transition-all ${
            config.BOT_STATE === 'STOPPED' 
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
              : 'bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20'
          }`}
          disabled={config.BOT_STATE === 'STOPPED'}
        >
          <Square className="w-4 h-4" /> Stop Bot
        </button>
      </div>

    </div>
  );
}
