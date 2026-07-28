"use client";

import React, { useEffect, useState } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import CountUp from 'react-countup';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Area, AreaChart, ComposedChart, Bar, BarChart, Legend, ReferenceLine } from 'recharts';

import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  DollarSign, 
  Target, 
  ShieldAlert,
  Clock,
  Calendar,
  Globe,
  AlertCircle,
  Copy,
  Moon,
  Sun,
  User,
  ArrowRight
} from 'lucide-react';

interface Trade {
  id: number;
  ticket: number;
  entry_time: string;
  exit_time: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  sl: number;
  tp: number;
  volume: number;
  entry_velocity: number;
  exit_reason: string;
  profit_points: number;
  profit_dollars: number;
  result: string;
}

interface Stats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  net_profit: number;
}

interface ActiveTrade {
  ticket: number;
  direction: string;
  entry_price: number;
  current_price: number;
  profit_points: number;
  profit_dollars: number;
  volume: number;
  is_higher: boolean;
  is_lower: boolean;
  sl: number;
  tp: number;
  open_time: number;
  spread: number;
}

interface NewsData {
  enabled: boolean;
  status: string;
  isBlocked: boolean;
  reason: string;
  nextEvent: any;
  events: any[];
}

const LiveTimer = ({ openTime }: { openTime: number }) => {
  const [duration, setDuration] = useState('');
  useEffect(() => {
    if (!openTime || isNaN(openTime)) {
      setDuration('--m --s');
      return;
    }
    const update = () => {
      const diff = Math.floor(Date.now() / 1000) - openTime;
      if (diff < 0) return;
      const m = Math.floor(diff / 60);
      const s = diff % 60;
      setDuration(`${m}m ${s.toString().padStart(2, '0')}s`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [openTime]);
  return <span className="font-mono text-slate-800 dark:text-slate-200 font-bold">{duration}</span>;
};

const CandleTimer = ({ timeframe = 'M5' }: { timeframe?: string }) => {
  const [duration, setDuration] = useState('');
  useEffect(() => {
    let tfMinutes = 5; // default M5
    if (timeframe.startsWith('M')) {
      tfMinutes = parseInt(timeframe.substring(1)) || 5;
    } else if (timeframe.startsWith('H')) {
      tfMinutes = (parseInt(timeframe.substring(1)) || 1) * 60;
    }
    const update = () => {
      const now = new Date();
      // Calculate how many minutes past the hour we are
      const currentMin = now.getMinutes();
      const currentSec = now.getSeconds();
      const totalSec = (currentMin % tfMinutes) * 60 + currentSec;
      
      const tfSec = tfMinutes * 60;
      const remSec = tfSec - totalSec;
      
      const m = Math.floor(remSec / 60);
      const s = remSec % 60;
      setDuration(`${m}m ${s.toString().padStart(2, '0')}s`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [timeframe]);
  return <span className="font-mono text-[11px] font-bold opacity-80">{duration}</span>;
};

const ProgressBar = ({ entry, current, sl, tp, direction }: any) => {
  const totalDist = Math.abs(tp - sl);
  if (totalDist === 0) return null;
  const currentDist = Math.abs(current - sl);
  const pct = Math.min(100, Math.max(0, (currentDist / totalDist) * 100));
  
  return (
    <div className="w-full mt-4">
      <div className="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400 mb-1">
        <span>SL: {sl.toFixed(5)}</span>
        <span>TP: {tp.toFixed(5)}</span>
      </div>
      <div className="h-1.5 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden relative">
        <div className={`absolute top-0 left-0 h-full transition-all duration-1000 ${pct > 50 ? 'bg-emerald-500' : 'bg-red-500'}`} style={{ width: `${pct}%` }}></div>
      </div>
    </div>
  );
};

export default function Home() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [dbSessionStats, setDbSessionStats] = useState<any[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [news, setNews] = useState<NewsData | null>(null);
  const [activeTrades, setActiveTrades] = useState<ActiveTrade[]>([]);
  const [marketState, setMarketState] = useState<{trend_label: string, timeframe?: string, timestamp?: number, spread?: number, current_price?: number} | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  useEffect(() => {
    if (marketState?.timestamp) {
      setIsOffline(Date.now() - marketState.timestamp > 15000);
    } else {
      setIsOffline(false);
    }
  }, [marketState?.timestamp]);
  // Filtering state
  const [filterType, setFilterType] = useState('today');
  const [customDate, setCustomDate] = useState('');
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (localStorage.theme === 'dark') {
        document.documentElement.classList.add('dark');
        setIsDarkMode(true);
      } else {
        document.documentElement.classList.remove('dark');
        setIsDarkMode(false);
      }
    }
  }, []);

  const toggleDarkMode = () => {
    if (isDarkMode) {
      document.documentElement.classList.remove('dark');
      localStorage.theme = 'light';
      setIsDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      localStorage.theme = 'dark';
      setIsDarkMode(true);
    }
  };
  const [viewMode, setViewMode] = useState<'trades' | 'news' | 'manual' | 'history'>('trades');
  const [newsFilter, setNewsFilter] = useState<'upcoming' | 'past'>('upcoming');
  
  // Trade type filters
  const [dirFilter, setDirFilter] = useState('ALL'); // ALL, BUY, SELL
  const [resultFilter, setResultFilter] = useState('ALL'); // ALL, WIN, LOSS

  // Manual Trading State
  const [lotSize, setLotSize] = useState('0.05');
  const [tradeCount, setTradeCount] = useState('1');
  const [slPoints, setSlPoints] = useState('10.00');
  const [tpPoints, setTpPoints] = useState('3.00');
  const [manualTimeframe, setManualTimeframe] = useState('M5');
  const [isTrading, setIsTrading] = useState(false);
  
  // Apply frontend filters (MUST BE BEFORE EARLY RETURN)
  const filteredTrades = React.useMemo(() => trades.filter(t => {
    if (dirFilter === 'BUY' && t.direction !== 'BUY') return false;
    if (dirFilter === 'SELL' && t.direction !== 'SELL') return false;
    if (resultFilter === 'WIN' && t.profit_dollars <= 0) return false;
    if (resultFilter === 'LOSS' && t.profit_dollars > 0) return false;
    return true;
  }), [trades, dirFilter, resultFilter]);

  const chartData = React.useMemo(() => {
    let currentPnL = 0;
    const items = [...filteredTrades].reverse();
    const result = [];
    for (let i = 0; i < items.length; i++) {
      const t = items[i];
      currentPnL += t.profit_dollars;
      result.push({
        name: t.ticket,
        pnl: currentPnL,
        profit: t.profit_dollars,
        date: t.entry_time.split(' ')[0],
        time: t.entry_time.split(' ')[1]
      });
    }
    return result;
  }, [filteredTrades]);

  const currentStreak = React.useMemo(() => {
    if (!filteredTrades || filteredTrades.length === 0) return { type: 'NONE', count: 0 };
    // Sort by most recent first
    const sorted = [...filteredTrades].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    let type = sorted[0].profit_dollars > 0 ? 'WIN' : 'LOSS';
    let count = 0;
    for (const trade of sorted) {
      const isWin = trade.profit_dollars > 0;
      if (type === 'WIN' && isWin) count++;
      else if (type === 'LOSS' && !isWin) count++;
      else break;
    }
    return { type, count };
  }, [filteredTrades]);

  const sessionData = React.useMemo(() => {
    const sessionMap: Record<string, {wins: number, losses: number, profit: number, lossAmount: number}> = {
      Asian: { wins: 0, losses: 0, profit: 0, lossAmount: 0 },
      UK: { wins: 0, losses: 0, profit: 0, lossAmount: 0 },
      US: { wins: 0, losses: 0, profit: 0, lossAmount: 0 },
    };
    dbSessionStats.forEach(s => {
      if (sessionMap[s.session_name]) {
        sessionMap[s.session_name].wins = s.wins;
        sessionMap[s.session_name].losses = s.losses;
        sessionMap[s.session_name].profit = s.profit;
        sessionMap[s.session_name].lossAmount = s.lossAmount;
      }
    });

    return [
      { 
        name: 'Asian', 
        session: 'Asian',
        Win: sessionMap.Asian.wins, 
        Loss: sessionMap.Asian.losses,
        profit: sessionMap.Asian.profit,
        lossAmount: sessionMap.Asian.lossAmount,
        absLossAmount: Math.abs(sessionMap.Asian.lossAmount),
        winRate: (sessionMap.Asian.profit + Math.abs(sessionMap.Asian.lossAmount)) > 0 ? (sessionMap.Asian.profit / (sessionMap.Asian.profit + Math.abs(sessionMap.Asian.lossAmount)) * 100).toFixed(1) : '0.0'
      },
      { 
        name: 'UK', 
        session: 'UK',
        Win: sessionMap.UK.wins, 
        Loss: sessionMap.UK.losses,
        profit: sessionMap.UK.profit,
        lossAmount: sessionMap.UK.lossAmount,
        absLossAmount: Math.abs(sessionMap.UK.lossAmount),
        winRate: (sessionMap.UK.profit + Math.abs(sessionMap.UK.lossAmount)) > 0 ? (sessionMap.UK.profit / (sessionMap.UK.profit + Math.abs(sessionMap.UK.lossAmount)) * 100).toFixed(1) : '0.0'
      },
      { 
        name: 'US', 
        session: 'US',
        Win: sessionMap.US.wins, 
        Loss: sessionMap.US.losses,
        profit: sessionMap.US.profit,
        lossAmount: sessionMap.US.lossAmount,
        absLossAmount: Math.abs(sessionMap.US.lossAmount),
        winRate: (sessionMap.US.profit + Math.abs(sessionMap.US.lossAmount)) > 0 ? (sessionMap.US.profit / (sessionMap.US.profit + Math.abs(sessionMap.US.lossAmount)) * 100).toFixed(1) : '0.0'
      }
    ];
  }, [dbSessionStats]);

  const handleCopyTrades = () => {
    if (!filteredTrades || filteredTrades.length === 0) {
      toast.error("No trades to copy");
      return;
    }
    const header = "TIME\tDIRECTION\tLOT SIZE\tENTRY\tEXIT\tREASON\tPOINTS\tP&L";
    const rows = filteredTrades.map(trade => {
      const utcDate = new Date(trade.entry_time.replace(' ', 'T') + 'Z');
      const timeStr = !isNaN(utcDate.getTime()) 
        ? new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }).format(utcDate)
        : trade.entry_time;
      return `${timeStr}\t${trade.direction}\t${trade.volume.toFixed(2)}\t${trade.entry_price.toFixed(2)}\t${trade.exit_price.toFixed(2)}\t${trade.exit_reason}\t${trade.profit_points > 0 ? '+' : ''}${trade.profit_points.toFixed(2)}\t${trade.profit_dollars > 0 ? '+$' : '-$'}${Math.abs(trade.profit_dollars).toFixed(2)}`;
    });
    const copyText = [header, ...rows].join("\n");
    navigator.clipboard.writeText(copyText)
      .then(() => toast.success("Trade data copied!"))
      .catch(() => toast.error("Failed to copy trades"));
  };

  const executeTrade = async (direction: string) => {
    // First/Last 15 seconds safety check
    const timeframe = manualTimeframe;
    let tfMinutes = 5;
    if (timeframe.startsWith('M')) tfMinutes = parseInt(timeframe.substring(1)) || 5;
    else if (timeframe.startsWith('H')) tfMinutes = (parseInt(timeframe.substring(1)) || 1) * 60;
    
    const now = new Date();
    const currentMin = now.getMinutes();
    const currentSec = now.getSeconds();
    const totalSec = (currentMin % tfMinutes) * 60 + currentSec;
    const tfSec = tfMinutes * 60;
    const remSec = tfSec - totalSec;
    
    if (totalSec <= 30 || remSec <= 30) {
      const confirmEntry = window.confirm(`WARNING: You are entering a trade in the very first or last 30 seconds of the candle.\n\nAre you sure you want to proceed?`);
      if (!confirmEntry) return;
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
          timeframe: manualTimeframe
        })
      });
      
      const data = await res.json();
      if (data.success) {
        toast.success(`Success:\n${data.output}`, { id: toastId, duration: 5000 });
        fetchTrades(); // instantly fetch new trades
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
        fetchTrades(); // instantly fetch new trades
      } else {
        toast.error(`Failed:\n${data.error || 'Unknown error'}`, { id: toastId, duration: 6000 });
      }
    } catch (err: any) {
      toast.error(`Error:\n${err.message}`, { id: toastId, duration: 6000 });
    } finally {
      setIsTrading(false);
    }
  };


  const fetchTrades = React.useCallback(async () => {
    try {
      setLoading(true);
      const url = new URL('/api/trades', window.location.origin);
      url.searchParams.set('filter', filterType);
      if (customDate) {
        url.searchParams.set('date', customDate);
      }
      
      url.searchParams.set('t', Date.now().toString());
      const res = await fetch(url.toString(), { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      if (data.success) {
        setTrades(data.trades);
        setStats(data.stats);
        if (data.sessionStats) setDbSessionStats(data.sessionStats);
        setBalance(data.balance);
      }

      // Fetch news data
      try {
        const newsRes = await fetch('/api/news');
        if (!newsRes.ok) throw new Error(`HTTP error! status: ${newsRes.status}`);
        const newsData = await newsRes.json();
        if (newsData.success) {
          setNews(newsData);
        }
      } catch (e) {
        console.error("Failed to fetch news", e);
      }
      
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch trades', err);
    } finally {
      setLoading(false);
    }
  }, [filterType, customDate]);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 30000); // Poll every 30s to save CPU
    return () => clearInterval(interval);
  }, [fetchTrades]);

  useEffect(() => {
    const fetchActiveTrade = async () => {
      try {
        const res = await fetch('/api/active?t=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) return;
        const data = await res.json();
        if (data.success) {
          if (data.marketState) setMarketState(data.marketState);
          const tradeData = data.activeTrade;
          if (Array.isArray(tradeData)) {
            setActiveTrades(tradeData);
          } else if (tradeData && typeof tradeData === 'object') {
            setActiveTrades([tradeData]);
          } else {
            setActiveTrades([]);
          }
        }
      } catch {
        // silently ignore
      }
    };
    fetchActiveTrade();
    const interval = setInterval(fetchActiveTrade, 1000); // Poll active trade every 1s
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="relative flex justify-center items-center">
          <div className="absolute animate-ping w-16 h-16 rounded-full bg-emerald-500/30"></div>
          <Activity className="w-8 h-8 text-emerald-600 animate-pulse" />
        </div>
      </div>
    );
  }

  // (Filters moved to top level to obey Rules of Hooks)

  const nowMs = new Date().getTime();
  const displayedNews = news ? news.events.filter(ev => {
    const evTime = new Date(ev.date).getTime();
    if (newsFilter === 'upcoming') {
      return evTime >= nowMs - (60 * 60 * 1000); // include events from the last hour as 'upcoming' context, or strictly future
    } else {
      return evTime < nowMs - (60 * 60 * 1000); // events older than 1 hour are strictly past
    }
  }).sort((a, b) => {
    if (newsFilter === 'past') {
      return new Date(b.date).getTime() - new Date(a.date).getTime(); // newest first
    }
    return new Date(a.date).getTime() - new Date(b.date).getTime(); // oldest first
  }) : [];

  const displayTotal = filteredTrades.length;
  const displayWins = filteredTrades.filter(t => t.profit_dollars > 0).length;
  const displayLosses = filteredTrades.filter(t => t.profit_dollars <= 0).length;
  const displayPnL = filteredTrades.reduce((acc, t) => acc + t.profit_dollars, 0);
  
  const grossProfit = filteredTrades.filter(t => t.profit_dollars > 0).reduce((acc, t) => acc + t.profit_dollars, 0);
  const grossLoss = filteredTrades.filter(t => t.profit_dollars <= 0).reduce((acc, t) => acc + t.profit_dollars, 0);
  
  const absLoss = Math.abs(grossLoss);
  const displayWinRate = (grossProfit + absLoss) > 0 ? ((grossProfit / (grossProfit + absLoss)) * 100).toFixed(1) : '0.0';

  const avgWin = displayWins > 0 ? grossProfit / displayWins : 0;
  const avgLoss = displayLosses > 0 ? grossLoss / displayLosses : 0;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 p-6 md:p-12 font-sans selection:bg-emerald-500/30 relative overflow-hidden">
      <Toaster position="bottom-right" />
      {/* AMBIENT BACKGROUND GLOWS */}
      <div className="absolute top-[-10%] left-[-5%] w-[40rem] h-[40rem] bg-emerald-500/5 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-5%] w-[40rem] h-[40rem] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none"></div>
      
      <div className="max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-[30%_1fr] gap-6 relative z-10">
        
        {/* LEFT SIDEBAR */}
        <div className="flex flex-col gap-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm border border-slate-200 dark:border-slate-700">
             <div className="flex justify-between items-center mb-4">
               <h2 className="font-bold text-lg text-slate-800 dark:text-slate-100">Live Status</h2>
               <button onClick={toggleDarkMode} className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                 {isDarkMode ? <Sun className="w-4 h-4 text-slate-400" /> : <Moon className="w-4 h-4 text-slate-500" />}
               </button>
             </div>


             {/* Trading Account Login */}
             <div className="bg-[#3B82F6] rounded-xl p-4 text-white shadow-lg shadow-blue-500/20 mb-4">
               <div className="text-[10px] font-bold uppercase tracking-wider mb-1 opacity-90">ACCOUNT / LOGIN</div>
               <div className="font-black text-xl tracking-tight uppercase">{process.env.NEXT_PUBLIC_MT5_LOGIN || '30217238'}</div>
             </div>

             {/* Symbol Price & Spread */}
             <div className="bg-[#1E40AF] rounded-xl p-4 text-white shadow-lg shadow-blue-500/20 mb-4 flex justify-between items-end">
               <div>
                 <div className="text-[10px] font-bold uppercase tracking-wider mb-1 opacity-90">XAUUSD</div>
                 <div className="font-black text-3xl tracking-tight leading-none">
                   {activeTrades.length > 0 
                      ? activeTrades[0].current_price.toFixed(2) 
                      : (marketState?.current_price ? marketState.current_price.toFixed(2) : (marketState?.timestamp ? 'WAITING' : 'LOADING'))}
                 </div>
               </div>
               {marketState?.spread !== undefined && (
                 <div className="flex flex-col items-end">
                   <div className="text-[9px] font-bold uppercase tracking-wider mb-1 opacity-70">SPREAD (PTS)</div>
                   <div className="font-black text-lg text-emerald-400 leading-none">{marketState.spread}</div>
                 </div>
               )}
             </div>

             {/* DETAILED STATS ROW - SIDEBAR VERSION */}
             <div className="grid grid-cols-2 gap-3 w-full mb-4">
               {/* Total Trades */}
               <div className="relative p-3 rounded-xl bg-gradient-to-br from-indigo-500/5 to-blue-500/5 border border-indigo-500/20 backdrop-blur-xl shadow-sm overflow-hidden group">
                 <div className="absolute -bottom-2 -right-2 p-2 opacity-5"><Activity className="w-16 h-16" /></div>
                 <div className="flex items-center gap-2 mb-2 relative z-10">
                   <div className="p-1.5 bg-indigo-500/10 rounded-md text-indigo-600 dark:text-indigo-400"><Activity className="w-3.5 h-3.5" /></div>
                   <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Total Trades</span>
                 </div>
                 <div className="text-xl font-black text-slate-900 dark:text-slate-100 relative z-10">{displayTotal}</div>
               </div>
               
               {/* Win Rate */}
               <div className="relative p-3 rounded-xl bg-gradient-to-br from-emerald-500/5 to-teal-500/5 border border-emerald-500/20 backdrop-blur-xl shadow-sm overflow-hidden group">
                 <div className="absolute -bottom-2 -right-2 p-2 opacity-5"><Target className="w-16 h-16" /></div>
                 <div className="flex items-center gap-2 mb-2 relative z-10">
                   <div className="p-1.5 bg-emerald-500/10 rounded-md text-emerald-600 dark:text-emerald-400"><Target className="w-3.5 h-3.5" /></div>
                   <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Win Rate</span>
                 </div>
                 <div className="text-xl font-black text-emerald-600 relative z-10">
                   {displayWinRate}%
                 </div>
               </div>
               
               {/* Net P&L */}
               <div className="relative p-3 rounded-xl bg-gradient-to-br from-blue-500/5 to-cyan-500/5 border border-blue-500/20 backdrop-blur-xl shadow-sm overflow-hidden group">
                 <div className="absolute -bottom-2 -right-2 p-2 opacity-5"><DollarSign className="w-16 h-16" /></div>
                 <div className="flex items-center gap-2 mb-2 relative z-10">
                   <div className="p-1.5 bg-blue-500/10 rounded-md text-blue-600 dark:text-blue-400"><DollarSign className="w-3.5 h-3.5" /></div>
                   <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Net P&L</span>
                 </div>
                 <div className={`text-xl font-black relative z-10 ${displayPnL >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                   {displayPnL >= 0 ? '+' : ''}${displayPnL.toFixed(2)}
                 </div>
               </div>
               
               {/* Win / Loss */}
               <div className="relative p-3 rounded-xl bg-gradient-to-br from-purple-500/5 to-pink-500/5 border border-purple-500/20 backdrop-blur-xl shadow-sm overflow-hidden group">
                 <div className="absolute -bottom-2 -right-2 p-2 opacity-5"><TrendingUp className="w-16 h-16" /></div>
                 <div className="flex items-center gap-2 mb-2 relative z-10">
                   <div className="p-1.5 bg-purple-500/10 rounded-md text-purple-600 dark:text-purple-400"><TrendingUp className="w-3.5 h-3.5" /></div>
                   <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Win / Loss</span>
                 </div>
                 <div className="text-xl font-black text-slate-900 dark:text-slate-100 relative z-10 flex items-baseline gap-1.5">
                   <span className="text-emerald-600">{displayWins}</span>
                   <span className="text-sm text-slate-300 dark:text-slate-600">/</span>
                   <span className="text-red-500">{displayLosses}</span>
                 </div>
               </div>
             </div>

             {/* Trend */}
             <div className="flex justify-between items-center pb-4 mb-4 border-b border-slate-100 dark:border-slate-700">
               <span className="font-bold text-sm text-slate-700 dark:text-slate-300">Trend:</span>
               <span className={`font-black uppercase flex items-center gap-1 text-sm ${marketState?.trend_label === 'UP' ? 'text-emerald-500' : marketState?.trend_label === 'DOWN' ? 'text-rose-500' : 'text-slate-500'}`}>
                 {marketState?.trend_label === 'UP' ? <TrendingUp className="w-4 h-4" /> : marketState?.trend_label === 'DOWN' ? <TrendingDown className="w-4 h-4" /> : <ArrowRight className="w-4 h-4" />}
                 {marketState?.trend_label === 'UP' ? 'UPTREND' : marketState?.trend_label === 'DOWN' ? 'DOWNTREND' : 'SIDEWAY'}
               </span>
             </div>

             {/* Streak */}
             <div className="flex justify-between items-center pb-4 mb-4 border-b border-slate-100 dark:border-slate-700">
               <span className="font-bold text-sm text-slate-700 dark:text-slate-300">Streak:</span>
               <span className={`font-black uppercase flex items-center gap-1 text-sm ${currentStreak.type === 'WIN' ? 'text-emerald-500' : currentStreak.type === 'LOSS' ? 'text-rose-500' : 'text-slate-500'}`}>
                 {currentStreak.type === 'WIN' ? `🔥 ${currentStreak.count} WINS` : currentStreak.type === 'LOSS' ? `❄️ ${currentStreak.count} LOSSES` : 'NONE'}
               </span>
             </div>

             {/* Candle Timer */}
              <div className="flex justify-between items-center">
                <span className="font-bold text-slate-700 dark:text-slate-300 text-sm flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  Option Expiry
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-black uppercase text-blue-500 bg-blue-500/10 px-1.5 py-0.5 rounded">{marketState?.timeframe || 'M5'}</span>
                  <span className="font-black text-sm text-slate-900 dark:text-slate-100">
                    <CandleTimer timeframe={marketState?.timeframe || 'M5'} />
                  </span>
                </div>
              </div>
          </div>

          {/* LIVE ENTRY STATUS / BLOCK REASON PANEL */}
          {activeTrades.length === 0 && (() => {
            const blockRaw: string = (marketState as any)?.block_reason || '';
            const ema9Angle: number = (marketState as any)?.ema_9_angle ?? 0;
            const ema21Angle: number = (marketState as any)?.ema_21_angle ?? 0;
            const atr14: number = (marketState as any)?.atr_14 ?? 0;
            const velocity: number = (marketState as any)?.velocity ?? 0;
            const avgVelocity: number = (marketState as any)?.avg_velocity ?? 0;
            const candleColor: string = (marketState as any)?.candle_color || 'UNKNOWN';
            const buyScore: number = (marketState as any)?.buy_score ?? 0;
            const sellScore: number = (marketState as any)?.sell_score ?? 0;
            const secIntoCandle: number = (marketState as any)?.seconds_into_candle ?? 0;

            // Human-readable mapping for block reasons
            const blockLabels: Record<string, { label: string; icon: string; color: string }> = {
              'SIDEWAY_TREND':             { label: 'Trend is Sideways',         icon: '↔️', color: 'text-yellow-500' },
              'HARD_RULE_ATR_TOO_LOW':     { label: 'ATR Too Low (Low Volatility)', icon: '📉', color: 'text-yellow-500' },
              'HARD_RULE_EMA_GAP_TOO_SMALL': { label: 'EMA 9/21 Gap Too Small',  icon: '📏', color: 'text-orange-400' },
              'HARD_RULE_EMA9_BELOW_EMA21':  { label: 'EMA 9 Below EMA 21',      icon: '🔻', color: 'text-rose-500' },
              'HARD_RULE_EMA9_ABOVE_EMA21':  { label: 'EMA 9 Above EMA 21',      icon: '🔺', color: 'text-rose-500' },
              'HARD_RULE_EMA21_ANGLE_WEAK':  { label: 'EMA 21 Angle Too Flat',   icon: '📐', color: 'text-orange-400' },
              'HARD_RULE_EMA9_ANGLE_WEAK':   { label: 'EMA 9 Angle Too Flat',    icon: '📐', color: 'text-orange-400' },
              'HARD_RULE_CURR_COLOR_MISMATCH': { label: 'Candle Color Mismatch', icon: '🕯️', color: 'text-yellow-500' },
              'HARD_RULE_MIN_BODY_SIZE':    { label: 'Candle Body Too Small',     icon: '🕯️', color: 'text-yellow-500' },
              'HARD_RULE_VELOCITY':         { label: 'Velocity Too Slow',          icon: '⚡', color: 'text-orange-400' },
              'HARD_RULE_AVG_VELOCITY':     { label: 'Avg Velocity Too Slow',      icon: '⚡', color: 'text-orange-400' },
              'HARD_RULE_NOT_AT_HIGH':      { label: 'Price Not at Candle High',   icon: '🎯', color: 'text-yellow-500' },
              'HARD_RULE_NOT_AT_LOW':       { label: 'Price Not at Candle Low',    icon: '🎯', color: 'text-yellow-500' },
              'HARD_RULE_PRICE_BELOW_OPEN': { label: 'Price Below Candle Open',    icon: '🔻', color: 'text-rose-500' },
              'HARD_RULE_PRICE_ABOVE_OPEN': { label: 'Price Above Candle Open',    icon: '🔺', color: 'text-rose-500' },
              'HARD_RULE_EMA9_PULLBACK_PREV_RED':   { label: 'Pullback: Prev Candle Red', icon: '↩️', color: 'text-rose-500' },
              'HARD_RULE_EMA9_PULLBACK_PREV_GREEN': { label: 'Pullback: Prev Candle Green', icon: '↩️', color: 'text-rose-500' },
              'CANDLE_ENTRY_START':         { label: 'Waiting: Candle Just Opened', icon: '⏳', color: 'text-blue-400' },
              'CANDLE_ENTRY_END':           { label: 'Window Closed: Candle Ending', icon: '⌛', color: 'text-blue-400' },
              'MAX_TRADES_PER_CANDLE':      { label: 'Max Trades This Candle',     icon: '🚫', color: 'text-rose-500' },
              'LOSS_LIMIT_CANDLE':          { label: 'Loss Limit Hit This Candle', icon: '🛑', color: 'text-rose-500' },
              'CONSEC_LOSS_PAUSE':          { label: 'Consecutive Loss Pause',     icon: '⏸️', color: 'text-rose-500' },
              'DAILY_LIMIT':               { label: 'Daily Trade Limit Reached',  icon: '📅', color: 'text-rose-500' },
              'DAILY_PROFIT_TARGET':        { label: 'Daily Profit Target Hit!',   icon: '🎉', color: 'text-emerald-500' },
              'NEWS_BLOCK':                 { label: 'News Event Blocking Entry',  icon: '📰', color: 'text-yellow-500' },
              'MAX_POSITIONS':              { label: 'Max Positions Open',         icon: '🔒', color: 'text-rose-500' },
              'NO_DATA':                    { label: 'Waiting for Market Data',    icon: '📡', color: 'text-slate-400' },
            };

            const mapped = blockLabels[blockRaw];
            const blockLabel = mapped?.label || (blockRaw ? blockRaw.replace(/_/g, ' ') : 'Scanning for Setup…');
            const blockIcon = mapped?.icon || '🔍';
            const blockColor = mapped?.color || 'text-slate-400';

            return (
              <div className="w-full mb-4 animate-in fade-in duration-300">
                <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-4">
                  {/* Header */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    <span className="text-xs font-black uppercase tracking-widest text-slate-500 dark:text-slate-400">Live Analysis</span>
                  </div>

                  {/* Block Reason */}
                  <div className="flex items-center gap-2 mb-3 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-700/50">
                    <span className="text-base">{blockIcon}</span>
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">Status</div>
                      <div className={`text-sm font-black ${blockColor}`}>{blockLabel}</div>
                    </div>
                  </div>

                  {/* Indicator Grid */}
                  <div className="grid grid-cols-2 gap-1.5">
                    {/* EMA 9 Angle */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">EMA 9 Angle</div>
                      <div className={`text-sm font-black ${Math.abs(ema9Angle) >= 8 ? 'text-emerald-500' : 'text-orange-400'}`}>
                        {ema9Angle >= 0 ? '+' : ''}{ema9Angle.toFixed(1)}°
                      </div>
                    </div>
                    {/* EMA 21 Angle */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">EMA 21 Angle</div>
                      <div className={`text-sm font-black ${Math.abs(ema21Angle) >= 4 ? 'text-emerald-500' : 'text-orange-400'}`}>
                        {ema21Angle >= 0 ? '+' : ''}{ema21Angle.toFixed(1)}°
                      </div>
                    </div>
                    {/* ATR */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">ATR(14)</div>
                      <div className={`text-sm font-black ${atr14 >= 1.20 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {atr14.toFixed(2)}
                      </div>
                    </div>
                    {/* Velocity */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">Velocity</div>
                      <div className={`text-sm font-black ${Math.abs(velocity) >= 0.05 ? 'text-emerald-500' : 'text-orange-400'}`}>
                        {velocity >= 0 ? '+' : ''}{velocity.toFixed(3)}
                      </div>
                    </div>
                    {/* Candle */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">Candle</div>
                      <div className={`text-sm font-black ${candleColor === 'GREEN' ? 'text-emerald-500' : candleColor === 'RED' ? 'text-rose-500' : 'text-slate-400'}`}>
                        {candleColor === 'GREEN' ? '▲' : candleColor === 'RED' ? '▼' : '—'} {candleColor}
                      </div>
                    </div>
                    {/* Score */}
                    <div className="bg-slate-50 dark:bg-slate-900/40 rounded-lg p-2 border border-slate-100 dark:border-slate-700/40">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">Score</div>
                      <div className={`text-sm font-black ${Math.max(buyScore, sellScore) >= 80 ? 'text-emerald-500' : Math.max(buyScore, sellScore) >= 60 ? 'text-orange-400' : 'text-rose-500'}`}>
                        {candleColor === 'GREEN' ? buyScore.toFixed(0) : sellScore.toFixed(0)}/100
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ACTIVE TRADE DISPLAY BOX (SIDEBAR) */}
          {activeTrades.length > 0 && activeTrades.map((activeTrade, idx) => (
            <div key={activeTrade.ticket || idx} className="w-full mb-4 relative z-10 animate-in fade-in slide-in-from-top-4 duration-500">
              <div className={`p-5 rounded-2xl border backdrop-blur-xl shadow-lg dark:shadow-none relative overflow-hidden ${
                activeTrade.profit_dollars >= 0 
                  ? 'bg-emerald-500/5 border-emerald-500/30 shadow-[0_0_30px_rgba(16,185,129,0.15)]' 
                  : 'bg-red-500/10 border-red-500/30 shadow-[0_0_30px_rgba(239,68,68,0.15)]'
              }`}>
                <div className="absolute top-0 left-0 w-full h-1">
                  <div className={`h-full w-full animate-pulse ${activeTrade.profit_dollars >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
                </div>
                
                <div className="flex flex-col items-center gap-4">
                  
                  {/* Profit Tracking */}
                  <div className="flex flex-col items-center w-full text-center">
                    <div className={`text-4xl font-black tracking-tighter ${
                      activeTrade.profit_dollars >= 0 ? 'text-emerald-600' : 'text-red-600'
                    }`}>
                      {activeTrade.profit_dollars >= 0 ? '+' : ''}${activeTrade.profit_dollars.toFixed(2)}
                    </div>
                    <div className={`text-xs font-bold flex flex-col items-center gap-1 mt-1 ${
                      activeTrade.profit_dollars >= 0 ? 'text-emerald-600/80' : 'text-red-600/80'
                    }`}>
                      <span>{activeTrade.profit_points >= 0 ? '+' : ''}{activeTrade.profit_points.toFixed(1)} pts</span>
                      <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                        <Clock className="w-3.5 h-3.5" />
                        <LiveTimer openTime={activeTrade.open_time} />
                      </div>
                    </div>
                    
                    {activeTrade.sl !== undefined && activeTrade.sl > 0 && activeTrade.tp > 0 && (
                      <div className="w-full mt-3">
                        <ProgressBar 
                          entry={activeTrade.entry_price} 
                          current={activeTrade.current_price} 
                          sl={activeTrade.sl} 
                          tp={activeTrade.tp} 
                          direction={activeTrade.direction} 
                        />
                      </div>
                    )}
                  </div>
                  
                  {/* Metrics Grid */}
                  <div className="grid grid-cols-2 gap-2 w-full">
                    <div className="bg-white dark:bg-slate-800/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center text-center">
                      <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-0.5">Direction</span>
                      <span className={`text-base font-bold ${activeTrade.direction === 'BUY' ? 'text-emerald-600' : 'text-red-600'}`}>{activeTrade.direction}</span>
                    </div>
                    <div className="bg-white dark:bg-slate-800/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center text-center">
                      <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-0.5">Lot Size</span>
                      <span className="text-base font-bold text-slate-900 dark:text-slate-100">{activeTrade.volume.toFixed(2)}</span>
                    </div>
                    <div className="bg-white dark:bg-slate-800/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center text-center">
                      <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-0.5">Entry</span>
                      <span className="text-base font-bold text-slate-900 dark:text-slate-100">{activeTrade.entry_price.toFixed(2)}</span>
                    </div>
                    <div className="bg-white dark:bg-slate-800/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center text-center">
                      <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-0.5">Take Profit</span>
                      <span className="text-base font-bold text-emerald-600">{activeTrade.tp !== undefined && activeTrade.tp > 0 ? activeTrade.tp.toFixed(2) : 'NONE'}</span>
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-800/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center text-center w-full">
                    <span className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-0.5 leading-tight">Stoploss / Trailing SL</span>
                    <span className={`text-base font-bold mt-0.5 ${
                      activeTrade.sl !== undefined && activeTrade.sl > 0 && (
                        (activeTrade.direction === 'BUY' && activeTrade.sl > activeTrade.entry_price) || 
                        (activeTrade.direction === 'SELL' && activeTrade.sl < activeTrade.entry_price)
                      ) ? 'text-emerald-500' : 'text-rose-600'
                    }`}>
                      {activeTrade.sl !== undefined && activeTrade.sl > 0 ? activeTrade.sl.toFixed(2) : 'NONE'}
                    </span>
                  </div>
                  
                  {/* Exit Button */}
                  <div className="w-full mt-1">
                    <button onClick={() => executeExit(activeTrade.ticket)} disabled={isTrading} className="p-3 rounded-xl bg-slate-900 border border-slate-800 hover:bg-rose-600 hover:border-rose-500 text-emerald-500 hover:text-white flex items-center justify-center font-bold text-xs tracking-widest transition-all duration-300 group disabled:opacity-50 shadow-lg dark:shadow-none hover:shadow-rose-500/20 w-full min-h-[48px]">
                      <div className="w-2 h-2 rounded-full bg-emerald-400 group-hover:hidden mr-2 animate-ping"></div>
                      <span className="group-hover:hidden">LIVE TRADE</span>
                      <span className="hidden group-hover:block text-white uppercase">Close Trade</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )) }
        </div>

        {/* RIGHT MAIN AREA */}
        <div className="flex flex-col gap-6 min-w-0">


      {/* P&L EQUITY CURVE & SESSION STATS */}
      {(viewMode === 'trades' || viewMode === 'history') && filteredTrades.length > 0 && (
        <div className="w-full mb-8 relative z-10 grid grid-cols-1 xl:grid-cols-[57%_43%] gap-6">
          <div className="bg-blue-50 dark:bg-slate-800 shadow-xl shadow-blue-100 dark:shadow-none rounded-2xl border border-blue-200 dark:border-slate-700 p-6">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              Equity Curve (Net P&L)
            </h3>
            <div className="h-[300px] w-full">
              {(() => {
                
                // Equity curve code ignores sessionStats because it was unused here anyway.

                
                const dataMax = Math.max(0, ...chartData.map(d => d.pnl));
                const dataMin = Math.min(0, ...chartData.map(d => d.pnl));
                const off = dataMax <= 0 ? 0 : dataMin >= 0 ? 1 : dataMax / (dataMax - dataMin);
                
                return (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={chartData}
                      margin={{ top: 20, right: 10, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
                          <stop offset={off} stopColor="#10b981" stopOpacity={1} />
                          <stop offset={off} stopColor="#ef4444" stopOpacity={1} />
                        </linearGradient>
                        <linearGradient id="splitFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset={off} stopColor="#10b981" stopOpacity={0.15} />
                          <stop offset={off} stopColor="#ef4444" stopOpacity={0.15} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} tickMargin={10} minTickGap={30} tickFormatter={(val) => val ? val.substring(0, 5) : ''} />
                      <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(val) => `$${val}`} />
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: isDarkMode ? '#1e293b' : 'white', borderRadius: '12px', border: isDarkMode ? '1px solid #334155' : '1px solid #e2e8f0', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}
                        itemStyle={{ color: isDarkMode ? '#f1f5f9' : '#0f172a', fontWeight: 'bold' }}
                        labelStyle={{ color: '#64748b', marginBottom: '4px' }}
                        formatter={(value: any, name: any) => {
                          const labelText = name === 'pnl' ? 'Net P&L' : name === 'profit' ? 'Trade Profit' : name;
                          return [`$${Number(value).toFixed(2)}`, labelText];
                        }}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="pnl" 
                        stroke="url(#splitColor)" 
                        fill="url(#splitFill)"
                        strokeWidth={2} 
                        dot={false}
                        activeDot={{ r: 6, fill: '#ffffff', stroke: '#10b981', strokeWidth: 2 }} 
                      />
                      <ReferenceLine 
                        y={Math.max(...chartData.map(d => d.pnl))} 
                        label={{ position: 'top', value: `High: $${Math.max(...chartData.map(d => d.pnl)).toFixed(2)}`, fill: '#10b981', fontSize: 12, fontWeight: 'bold' }} 
                        stroke="#10b981" 
                        strokeDasharray="3 3" 
                        opacity={0.5} 
                      />
                      <ReferenceLine 
                        y={Math.min(...chartData.map(d => d.pnl))} 
                        label={{ position: 'bottom', value: `Low: $${Math.min(...chartData.map(d => d.pnl)).toFixed(2)}`, fill: '#ef4444', fontSize: 12, fontWeight: 'bold' }} 
                        stroke="#ef4444" 
                        strokeDasharray="3 3" 
                        opacity={0.5} 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                );
              })()}
            </div>
          </div>
          
          {/* SESSION BAR GRAPH */}
          <div className="bg-blue-50 dark:bg-slate-800 shadow-xl shadow-blue-100 dark:shadow-none rounded-2xl border border-blue-200 dark:border-slate-700 p-6">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              Session Performance
            </h3>
            <div className="h-[300px] w-full">
              {(() => {

                const CustomXAxisTick = ({ x, y, payload }: { x?: number, y?: number, payload?: any }) => {
                  let brokerTime = '';
                  let istTime = '';
                  if (payload.value === 'Asian') { brokerTime = '00:00 - 08:59'; istTime = '05:30 - 14:29 IST'; }
                  else if (payload.value === 'UK') { brokerTime = '09:00 - 14:59'; istTime = '14:30 - 20:29 IST'; }
                  else if (payload.value === 'US') { brokerTime = '15:00 - 23:59'; istTime = '20:30 - 05:29 IST'; }
                  
                  return (
                    <g transform={`translate(${x},${y})`}>
                      <text x={0} y={0} dy={14} textAnchor="middle" fill="#64748b" className="text-xs font-bold">{payload.value}</text>
                      <text x={0} y={0} dy={28} textAnchor="middle" fill="#94a3b8" className="text-[10px]">{brokerTime}</text>
                      <text x={0} y={0} dy={40} textAnchor="middle" fill="#94a3b8" className="text-[10px]">{istTime}</text>
                    </g>
                  );
                };
                
                const CustomSessionTooltip = ({ active, payload }: { active?: boolean, payload?: any }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.1)] border border-slate-200 dark:border-slate-700 z-50 relative">
                        <p className="font-bold text-slate-800 dark:text-slate-200 mb-2">{data.session} Session</p>
                        <div className="space-y-1 text-sm">
                          <p className="text-emerald-600 font-semibold flex justify-between gap-4">
                            <span>Win: {data.Win}</span>
                            <span>+${data.profit.toFixed(2)}</span>
                          </p>
                          <p className="text-red-500 font-semibold flex justify-between gap-4">
                            <span>Loss: {data.Loss}</span>
                            <span>-${data.lossAmount.toFixed(2)}</span>
                          </p>
                          <div className="pt-2 mt-2 border-t border-slate-100 dark:border-slate-700 flex justify-between gap-4 font-bold text-slate-600 dark:text-slate-400">
                            <span>Profit Rate</span>
                            <span>{data.winRate}%</span>
                          </div>
                        </div>
                      </div>
                    );
                  }
                  return null;
                };

                return (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={sessionData} margin={{ top: 20, right: 10, left: 0, bottom: 30 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickMargin={10} tick={<CustomXAxisTick />} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <RechartsTooltip content={<CustomSessionTooltip />} cursor={{fill: 'rgba(241, 245, 249, 0.5)'}} />
                      <Bar dataKey="profit" fill="#10b981" radius={[4, 4, 0, 0]} barSize={30} />
                      <Bar dataKey="absLossAmount" fill="#ef4444" radius={[4, 4, 0, 0]} barSize={30} />
                    </BarChart>
                  </ResponsiveContainer>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* RECENT TRADES / NEWS TABLE */}
      <div className="w-full relative z-10">
        <div className="flex flex-col gap-6 mb-6">
          
          {/* Top Section: Title & Tabs */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-4">
              <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Clock className="w-5 h-5 text-slate-900 dark:text-slate-100" />
                Activity
              </h3>
              
              <div className="flex flex-wrap bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700">
                <button
                  onClick={() => setViewMode('trades')}
                  className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all ${viewMode === 'trades' ? 'bg-blue-600 text-white shadow-lg dark:shadow-none' : 'text-slate-900 dark:text-slate-100 hover:text-slate-900 dark:text-slate-100'}`}
                >
                  Trades
                </button>
                <button
                  onClick={() => setViewMode('news')}
                  className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all flex items-center gap-1.5 ${viewMode === 'news' ? 'bg-indigo-600 text-white shadow-lg dark:shadow-none' : 'text-slate-900 dark:text-slate-100 hover:text-slate-900 dark:text-slate-100'}`}
                >
                  <Globe className="w-4 h-4" /> News
                </button>
                <button
                  onClick={() => setViewMode('manual')}
                  className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all flex items-center gap-1.5 ${viewMode === 'manual' ? 'bg-rose-600 text-white shadow-lg dark:shadow-none' : 'text-slate-900 dark:text-slate-100 hover:text-slate-900 dark:text-slate-100'}`}
                >
                  <Target className="w-4 h-4" /> Manual Trade
                </button>
                <button
                  onClick={() => setViewMode('history')}
                  className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all flex items-center gap-1.5 ${viewMode === 'history' ? 'bg-purple-600 text-white shadow-lg dark:shadow-none' : 'text-slate-900 dark:text-slate-100 hover:text-slate-900 dark:text-slate-100'}`}
                >
                  <Clock className="w-4 h-4" /> History
                </button>
              </div>
            </div>

            {/* Table Filters (BUY / SELL / COPY) - Placed top right to save space */}
            {(viewMode === 'trades' || viewMode === 'history') && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-slate-500 uppercase mr-1 tracking-wider hidden xl:block">Table Filters:</span>
                <button
                  onClick={() => setDirFilter(dirFilter === 'BUY' ? 'ALL' : 'BUY')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${dirFilter === 'BUY' ? 'bg-blue-50 dark:bg-slate-8000/20 text-blue-600 border-blue-500/50 shadow-[0_0_10px_rgba(59,130,246,0.2)]' : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'}`}
                >
                  BUY
                </button>
                <button
                  onClick={() => setDirFilter(dirFilter === 'SELL' ? 'ALL' : 'SELL')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${dirFilter === 'SELL' ? 'bg-fuchsia-500/20 text-fuchsia-600 border-fuchsia-500/50 shadow-[0_0_10px_rgba(217,70,239,0.2)]' : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'}`}
                >
                  SELL
                </button>
                
                <div className="w-px h-5 bg-slate-300 dark:bg-slate-600 mx-1"></div>
                
                <button
                  onClick={() => setResultFilter(resultFilter === 'WIN' ? 'ALL' : 'WIN')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${resultFilter === 'WIN' ? 'bg-emerald-500/20 text-emerald-600 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.2)]' : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'}`}
                >
                  WIN
                </button>
                <button
                  onClick={() => setResultFilter(resultFilter === 'LOSS' ? 'ALL' : 'LOSS')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${resultFilter === 'LOSS' ? 'bg-rose-500/20 text-rose-600 border-rose-500/50 shadow-[0_0_10px_rgba(244,63,94,0.2)]' : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'}`}
                >
                  LOSS
                </button>

                <div className="w-px h-5 bg-slate-300 dark:bg-slate-600 mx-1 hidden sm:block"></div>

                <button
                  onClick={handleCopyTrades}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800 hover:text-slate-900 dark:text-slate-100 flex items-center gap-1.5"
                  title="Copy Trade Data"
                >
                  <Copy className="w-3.5 h-3.5" /> Copy
                </button>
              </div>
            )}
          </div>

          {/* Bottom Section: History Date Filters */}
          {viewMode === 'history' && (
            <div className="flex flex-col gap-2">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Date Range:</span>
              <div className="flex flex-wrap items-center gap-2">
                {['today', 'yesterday', 'this-week', 'last-week', 'this-month', 'last-month', 'last-6-months', 'all', 'custom'].map((f) => (
                  <button
                    key={f}
                    onClick={() => { setFilterType(f); if (f !== 'custom') setCustomDate(''); }}
                    className={`px-4 py-2 rounded-lg text-xs font-bold uppercase transition-all shadow-sm ${filterType === f ? 'bg-blue-600 text-white shadow-blue-500/25 border border-blue-600' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700'}`}
                  >
                    {f === 'all' ? 'All Time' : f === 'custom' ? 'Custom Date' : f.replace(/-/g, ' ')}
                  </button>
                ))}
                
                {filterType === 'custom' && (
                  <input 
                    type="date"
                    value={customDate}
                    onChange={(e) => setCustomDate(e.target.value)}
                    className="px-3 py-1.5 rounded-lg text-sm font-bold bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                )}
              </div>
            </div>
          )}
        </div>
        
      {/* MANUAL TRADING TERMINAL */}
      {viewMode === 'manual' && (
        <div className="max-w-7xl mx-auto mb-12 relative z-10">
          <div className="bg-white dark:bg-slate-800 shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl dark:shadow-none p-6 backdrop-blur-xl">
          <div className="flex flex-col gap-6">
            
            {/* Top Row: Title & Action Buttons */}
            <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6">
              <div className="flex-1">
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1 flex items-center gap-2">
                  <Target className="w-5 h-5 text-emerald-600" />
                  Manual Execution Terminal
                </h3>
                <p className="text-sm text-slate-900 dark:text-slate-100">Execute instant MT5 trades with bot trailing-stop handoff.</p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  disabled={isTrading}
                  onClick={() => executeTrade('BUY')}
                  className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-black shadow-lg shadow-blue-500/30 transition-all disabled:opacity-50 tracking-wider"
                >
                  BUY
                </button>
                <button
                  disabled={isTrading}
                  onClick={() => executeTrade('SELL')}
                  className="px-8 py-3 bg-fuchsia-600 hover:bg-fuchsia-700 text-white rounded-xl font-black shadow-lg shadow-fuchsia-500/30 transition-all disabled:opacity-50 tracking-wider"
                >
                  SELL
                </button>
                <button
                  disabled={isTrading}
                  onClick={() => executeExit('ALL')}
                  className="px-6 py-3 bg-rose-100 dark:bg-rose-500/10 hover:bg-rose-200 dark:hover:bg-rose-500/20 text-rose-600 border border-rose-500/30 rounded-xl font-black transition-all disabled:opacity-50 uppercase tracking-wider ml-2"
                >
                  Exit Trade
                </button>
              </div>
            </div>

            {/* Bottom Row: Settings Grid */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 bg-slate-50 dark:bg-slate-900/50 p-5 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Lot Size</label>
                <input 
                  type="number" step="0.01" 
                  value={lotSize} onChange={(e) => setLotSize(e.target.value)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 dark:text-slate-100 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>
              
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Trades</label>
                <input 
                  type="number" step="1" 
                  value={tradeCount} onChange={(e) => setTradeCount(e.target.value)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 dark:text-slate-100 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">SL (Pts)</label>
                <input 
                  type="number" step="0.1" 
                  value={slPoints} onChange={(e) => setSlPoints(e.target.value)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 dark:text-slate-100 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">TP (Pts)</label>
                <input 
                  type="number" step="0.1" 
                  value={tpPoints} onChange={(e) => setTpPoints(e.target.value)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 dark:text-slate-100 outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Timeframe</label>
                <select 
                  value={manualTimeframe} onChange={(e) => setManualTimeframe(e.target.value)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 dark:text-slate-100 outline-none focus:border-emerald-500/50 transition-colors appearance-none"
                >
                  <option value="M1">M1</option>
                  <option value="M5">M5</option>
                  <option value="M15">M15</option>
                  <option value="M30">M30</option>
                  <option value="H1">H1</option>
                </select>
              </div>
            </div>
          </div>
          

        </div>
      </div>
      )}

        {viewMode === 'news' && news ? (
          <div className="space-y-6">
            <div className={`p-5 rounded-2xl border shadow-xl flex flex-col md:flex-row items-center justify-between gap-4 transition-colors duration-500 ${
              news.isBlocked 
                ? 'bg-rose-50 dark:bg-rose-900/20 border-rose-200' 
                : !news.enabled 
                  ? 'bg-white dark:bg-slate-800 shadow-xl shadow-slate-200/50 border-slate-200 dark:border-slate-700' 
                  : 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200'
            }`}>
              <div className="flex items-center gap-4">
                <div className="flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <Globe className={`w-6 h-6 ${news.isBlocked ? 'text-rose-500' : !news.enabled ? 'text-slate-900 dark:text-slate-100' : 'text-emerald-500'}`} />
                </div>
                <div>
                  <h3 className="text-slate-900 dark:text-slate-100 font-bold text-lg flex items-center gap-2">
                    Forex News Filter
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                      news.isBlocked ? 'bg-rose-500/20 text-rose-600' : !news.enabled ? 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400' : 'bg-emerald-500/20 text-emerald-600'
                    }`}>
                      {news.status}
                    </span>
                  </h3>
                  <p className="text-sm text-slate-900 dark:text-slate-100 mt-0.5">
                    {news.isBlocked ? (
                      <span className="text-rose-600 font-medium">Trading Paused: {news.reason}</span>
                    ) : !news.enabled ? (
                      <span>News filter is currently disabled in config.</span>
                    ) : (
                      <span>Trading Active. Scanning for high-impact USD events.</span>
                    )}
                  </p>
                </div>
              </div>

              {news.nextEvent && (
                <div className="bg-slate-50 dark:bg-slate-900 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col items-end shadow-inner">
                  <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wider mb-1">Next High Impact Event</span>
                  <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{news.nextEvent.title}</span>
                  <span className="text-xs font-medium text-amber-500 mt-0.5">
                    {new Date(news.nextEvent.date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ({(new Date(news.nextEvent.date).getTime() - new Date().getTime() > 0) ? Math.round((new Date(news.nextEvent.date).getTime() - new Date().getTime()) / 60000) : 0} mins away)
                  </span>
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-1.5 justify-end">
              <button
                onClick={() => setNewsFilter('upcoming')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${
                  newsFilter === 'upcoming' 
                    ? 'bg-blue-50 dark:bg-slate-8000/20 text-blue-600 border-blue-500/50 shadow-[0_0_10px_rgba(59,130,246,0.2)]'
                    : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'
                }`}
              >
                UPCOMING
              </button>
              <button
                onClick={() => setNewsFilter('past')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 border ${
                  newsFilter === 'past' 
                    ? 'bg-amber-500/20 text-amber-600 border-amber-500/50 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                    : 'bg-white dark:bg-slate-800 shadow-sm dark:shadow-none text-slate-900 dark:text-slate-100 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800'
                }`}
              >
                PAST
              </button>
            </div>

            <div className="bg-white dark:bg-slate-800 shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden backdrop-blur-xl">
              <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
                <table className="w-full text-left border-collapse relative">
                  <thead className="bg-white dark:bg-slate-800/95 text-slate-900 dark:text-slate-100 text-xs uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700 sticky top-0 z-20 backdrop-blur-sm">
                    <tr>
                      <th className="p-5">Time</th>
                      <th className="p-5">Impact</th>
                      <th className="p-5">Event</th>
                      <th className="p-5 text-right">Forecast</th>
                      <th className="p-5 text-right">Previous</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                  {displayedNews.map((ev, i) => (
                    <tr key={i} className="hover:bg-slate-50 dark:bg-slate-900 transition-colors">
                      <td className="p-5 whitespace-nowrap">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-900 dark:text-slate-100 font-bold text-sm tracking-wide">
                              {new Date(ev.date).toLocaleTimeString('en-US', {timeZone: 'Asia/Kolkata', hour: 'numeric', minute:'2-digit', hour12: true})}
                            </span>
                            <span className="text-[10px] font-extrabold text-emerald-500 bg-emerald-500/5 px-1 py-0.5 rounded">IST</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-900 dark:text-slate-100 font-medium text-xs tracking-wide">
                              {new Date(ev.date).toLocaleTimeString('en-US', {timeZone: 'America/New_York', hour: 'numeric', minute:'2-digit', hour12: true})}
                            </span>
                            <span className="text-[10px] font-bold text-slate-900 dark:text-slate-100">US Stock Time</span>
                            <span className="text-slate-500 dark:text-slate-400 font-bold text-[11px] ml-1 tracking-wider">
                              ({new Date(ev.date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'})})
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="p-5">
                        <span className={`px-2 py-1 rounded text-[10px] font-black uppercase ${
                          ev.impact === 'High' ? 'bg-rose-500/20 text-rose-600' : ev.impact === 'Medium' ? 'bg-amber-500/20 text-amber-600' : 'bg-yellow-500/20 text-yellow-600'
                        }`}>
                          {ev.impact}
                        </span>
                      </td>
                      <td className="p-5 text-sm font-bold text-slate-900 dark:text-slate-100">{ev.title}</td>
                      <td className="p-5 text-right text-sm text-slate-900 dark:text-slate-100">{ev.forecast || '-'}</td>
                      <td className="p-5 text-right text-sm text-slate-900 dark:text-slate-100">{ev.previous || '-'}</td>
                    </tr>
                  ))}
                  {displayedNews.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-12 text-center text-slate-900 dark:text-slate-100">
                        No {newsFilter} USD news events found for today.
                      </td>
                    </tr>
                  )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
        <div className="bg-white dark:bg-slate-800 shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl dark:shadow-none overflow-hidden backdrop-blur-xl">
          <div className="overflow-x-auto overflow-y-auto max-h-[600px]">
            <table className="w-full text-left border-collapse relative">
              <thead className="sticky top-0 z-20">
                <tr className="bg-slate-50 dark:bg-slate-900/95 backdrop-blur-md text-slate-600 dark:text-slate-400 text-xs uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
                  <th className="p-5">Time</th>
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
                {filteredTrades.map((trade) => {
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
                        timeZone: 'UTC',
                        hour: 'numeric',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: true
                      }).format(utcDate);
                    }
                  } catch {
                    istTime = "Err";
                  }

                  return (
                  <tr key={trade.id} className="hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group">
                    <td className="p-5 whitespace-nowrap">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-900 dark:text-slate-100 font-bold text-sm tracking-wide">{istTime || stockTime}</span>
                          <span className="text-[10px] font-extrabold text-emerald-500 bg-emerald-500/5 px-1 py-0.5 rounded">IST</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-900 dark:text-slate-100 font-medium text-xs tracking-wide">{stockTime}</span>
                          <span className="text-[10px] font-bold text-slate-900 dark:text-slate-100">STOCK</span>
                          <span className="text-slate-500 dark:text-slate-400 font-bold text-[11px] ml-1 tracking-wider">({dateStr})</span>
                        </div>
                      </div>
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
                    <td className="p-5 text-right font-mono text-slate-900 dark:text-slate-100 text-sm">{trade.entry_price.toFixed(2)}</td>
                    <td className="p-5 text-right font-mono text-slate-900 dark:text-slate-100 text-sm">{trade.exit_price.toFixed(2)}</td>
                    <td className="p-5">
                      <span className="text-xs font-medium text-slate-900 dark:text-slate-100 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 px-2 py-1 rounded">
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
                {filteredTrades.length === 0 && (
                  <tr>
                    <td colSpan={8} className="p-12 text-center text-slate-900 dark:text-slate-100">
                      <Target className="w-12 h-12 mx-auto mb-4 opacity-20" />
                      No trades found for this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        )}
      </div>
      </div>
      </div>
      </div>
  );
}
