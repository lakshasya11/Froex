import pandas as pd
import MetaTrader5 as mt5
import math
import numpy as _np
import time

class TechnicalIndicators:
    """
    A utility class that calculates technical indicators (SuperTrend, Bollinger Bands, etc.)
    using pandas dataframes and MetaTrader5 rate history.
    """
    _rate_cache = {}

    @staticmethod
    def analyze_basic_timeframe(symbol: str, timeframe, bars: int = 100) -> dict:
        """
        Fetches the last N bars for a given timeframe, computes candle structures, 
        and calculates SuperTrend and Bollinger Bands. Returns a dictionary of indicators.
        """
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {}

        cache_key = (symbol, timeframe, bars)
        now_time = time.time()
        
        rates = None
        if cache_key in TechnicalIndicators._rate_cache:
            last_time, cached_rates = TechnicalIndicators._rate_cache[cache_key]
            if now_time - last_time < 0.25:  # 250ms cache
                rates = cached_rates

        if rates is None:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is not None and len(rates) >= 20:
                TechnicalIndicators._rate_cache[cache_key] = (now_time, rates)

        if rates is None or len(rates) < 20:
            return {}

        df = pd.DataFrame(rates)
        current_candle = df.iloc[-1]
        last_closed    = df.iloc[-2]   # previous closed candle
        current_open   = current_candle['open']
        current_price  = tick.bid

        # Body-based structure detection (ignore wicks)
        prev_body_high = max(last_closed['open'], last_closed['close'])
        prev_body_low  = min(last_closed['open'], last_closed['close'])

        is_higher = current_price > prev_body_high
        is_lower  = current_price < prev_body_low

        # Candle colors — BID based
        candle_color = ('GREEN' if current_price > current_open
                        else 'RED' if current_price < current_open
                        else 'UNKNOWN')

        prev_candle_color = ('GREEN' if last_closed['close'] > last_closed['open']
                             else 'RED' if last_closed['close'] < last_closed['open']
                             else 'UNKNOWN')

        prev_body_size = abs(last_closed['close'] - last_closed['open'])

        recent_10 = df.iloc[-11:-1]
        recent_strong_body = any(
            abs(c['close'] - c['open']) >= 0.30
            for _, c in recent_10.iterrows()
        )

        recent_5 = df.iloc[-6:-1]
        recent_colors = [
            'GREEN' if r['close'] > r['open'] else 'RED' if r['close'] < r['open'] else 'UNKNOWN'
            for _, r in recent_5.iterrows()
        ]
        recent_green_count = sum(1 for c in recent_colors if c == 'GREEN')
        recent_red_count = sum(1 for c in recent_colors if c == 'RED')
        recent_body_avg = float(
            recent_5.apply(lambda r: abs(float(r['close']) - float(r['open'])), axis=1).mean()
        ) if len(recent_5) else 0.0

        current_high = float(current_candle['high'])
        current_low = float(current_candle['low'])
        current_body_high = max(float(current_open), float(current_price))
        current_body_low = min(float(current_open), float(current_price))
        current_body_size = abs(float(current_price) - float(current_open))
        current_upper_wick = max(0.0, current_high - current_body_high)
        current_lower_wick = max(0.0, current_body_low - current_low)

        # Last 5 same-color closed candle bodies (for weak-prev-body fallback)
        green_bodies = [
            abs(float(r['close']) - float(r['open']))
            for _, r in recent_10.iterrows()
            if r['close'] > r['open']
        ][-5:]
        red_bodies = [
            abs(float(r['close']) - float(r['open']))
            for _, r in recent_10.iterrows()
            if r['close'] < r['open']
        ][-5:]

        # ── TRUE RANGE & ATR ──
        _n  = len(df)
        _cv = df['close'].values
        _hv = df['high'].values
        _lv = df['low'].values

        # True Range via pandas (handles first row cleanly)
        _tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low']  - df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        # Seed the first value of TR to be High - Low to avoid NA issues
        _tr.iloc[0] = _hv[0] - _lv[0]
        _atr_50_series = _tr.ewm(span=50, adjust=False).mean().values

        # ── SUPERTREND (period=10, multiplier=0.9) ──
        _atr = _tr.ewm(span=10, adjust=False).mean().values
        _hl2 = (_hv + _lv) / 2.0
        _UBb = _hl2 + 0.9 * _atr   # basic upper band
        _LBb = _hl2 - 0.9 * _atr   # basic lower band
        _UB  = _UBb.copy()
        _LB  = _LBb.copy()
        _STL = _np.empty(_n)        # SuperTrend line
        _SDir = _np.ones(_n, dtype=int)  # 1=BULL, -1=BEAR
        _STL[0] = _LBb[0]

        for _i in range(1, _n):
            _UB[_i] = _UBb[_i] if (_UBb[_i] < _UB[_i-1] or _cv[_i-1] > _UB[_i-1]) else _UB[_i-1]
            _LB[_i] = _LBb[_i] if (_LBb[_i] > _LB[_i-1] or _cv[_i-1] < _LB[_i-1]) else _LB[_i-1]
            if _SDir[_i-1] == 1:                   # was BULL
                if _cv[_i] < _LB[_i]:  _SDir[_i] = -1; _STL[_i] = _UB[_i]
                else:                   _SDir[_i] =  1; _STL[_i] = _LB[_i]
            else:                                   # was BEAR
                if _cv[_i] > _UB[_i]:  _SDir[_i] =  1; _STL[_i] = _LB[_i]
                else:                   _SDir[_i] = -1; _STL[_i] = _UB[_i]

        _st_dir_now = int(_SDir[-1])               # 1=BULL, -1=BEAR

        # ── BOLLINGER BANDS (period=20, std=2.0) ──
        # A volatility indicator. The middle band is a 20-period Simple Moving Average (SMA).
        # Upper and lower bands are 2 standard deviations away. Useful for detecting sideways chop (flat angle).
        _bb_mid_s = df['close'].rolling(window=20).mean()
        _bb_std_s = df['close'].rolling(window=20).std()
        _bb_mid_v = float(_bb_mid_s.iloc[-1])
        _bb_sd    = float(_bb_std_s.iloc[-1])
        _bb_sd    = _bb_sd if not math.isnan(_bb_sd) else 0.0
        _bb_up    = _bb_mid_v + 2.0 * _bb_sd
        _bb_lo    = _bb_mid_v - 2.0 * _bb_sd
        _bb_bw    = _bb_up - _bb_lo
        _bb_pos   = float((current_price - _bb_lo) / _bb_bw) if _bb_bw > 0 else 0.5
        # BB angle in degrees — using atan2 formula
        _bb_arr = [x for x in _bb_mid_s.values[-6:] if not math.isnan(x)]
        if len(_bb_arr) >= 2:
            lookback = len(_bb_arr) - 1
            bb_mid_current = _bb_arr[-1]
            bb_mid_prev = _bb_arr[0]
            _bb_ang = math.degrees(math.atan2(bb_mid_current - bb_mid_prev, lookback))
        else:
            _bb_ang = 0.0

        return {
            'close':          current_price,
            'open':           current_open,
            'candle_color':   candle_color,
            'prev_color':     prev_candle_color,
            'prev_body':      prev_body_size,
            'is_lower':       is_lower,
            'is_higher':      is_higher,
            'time':           current_candle['time'],
            'recent_strong_body': recent_strong_body,
            'prev_body_high': prev_body_high,
            'prev_body_low':  prev_body_low,
            'recent_green_bodies': green_bodies,
            'recent_red_bodies':   red_bodies,
            'recent_green_count':  recent_green_count,
            'recent_red_count':    recent_red_count,
            'recent_body_avg':     recent_body_avg,
            'current_body_size':   current_body_size,
            'current_upper_wick':  current_upper_wick,
            'current_lower_wick':  current_lower_wick,
            'st_direction':  _st_dir_now,   # 1 = BULL, -1 = BEAR
            'atr_50':        float(_atr_50_series[-1]),
            # Bollinger Bands
            'bb_mid':        _bb_mid_v,
            'bb_upper':      _bb_up,
            'bb_lower':      _bb_lo,
            'bb_bandwidth':  _bb_bw,
            'bb_position':   _bb_pos,        # 0.0=lower band, 1.0=upper band
            'bb_angle':      _bb_ang,         # degrees: >+15=up-trend, <-15=down-trend
        }
