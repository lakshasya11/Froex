import pandas as pd
import MetaTrader5 as mt5
import math
import numpy as _np
import time
import config


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
        last_closed = df.iloc[-2]  # previous closed candle
        current_open = current_candle["open"]
        current_price = tick.bid

        # Body-based structure detection (ignore wicks)
        prev_body_high = max(last_closed["open"], last_closed["close"])
        prev_body_low = min(last_closed["open"], last_closed["close"])

        is_higher = current_price > prev_body_high
        is_lower = current_price < prev_body_low

        # Candle colors — BID based
        candle_color = (
            "GREEN"
            if current_price > current_open
            else "RED" if current_price < current_open else "UNKNOWN"
        )

        prev_candle_color = (
            "GREEN"
            if last_closed["close"] > last_closed["open"]
            else "RED" if last_closed["close"] < last_closed["open"] else "UNKNOWN"
        )

        prev_body_size = abs(last_closed["close"] - last_closed["open"])

        recent_10 = df.iloc[-11:-1]
        recent_strong_body = any(
            abs(c["close"] - c["open"]) >= 0.30 for _, c in recent_10.iterrows()
        )

        recent_5 = df.iloc[-6:-1]
        recent_colors = [
            (
                "GREEN"
                if r["close"] > r["open"]
                else "RED" if r["close"] < r["open"] else "UNKNOWN"
            )
            for _, r in recent_5.iterrows()
        ]
        recent_green_count = sum(1 for c in recent_colors if c == "GREEN")
        recent_red_count = sum(1 for c in recent_colors if c == "RED")
        recent_body_avg = (
            float(
                recent_5.apply(
                    lambda r: abs(float(r["close"]) - float(r["open"])), axis=1
                ).mean()
            )
            if len(recent_5)
            else 0.0
        )

        current_high = float(current_candle["high"])
        current_low = float(current_candle["low"])
        current_body_high = max(float(current_open), float(current_price))
        current_body_low = min(float(current_open), float(current_price))
        current_body_size = abs(float(current_price) - float(current_open))
        current_upper_wick = max(0.0, current_high - current_body_high)
        current_lower_wick = max(0.0, current_body_low - current_low)

        # Last 5 same-color closed candle bodies (for weak-prev-body fallback)
        green_bodies = [
            abs(float(r["close"]) - float(r["open"]))
            for _, r in recent_10.iterrows()
            if r["close"] > r["open"]
        ][-5:]
        red_bodies = [
            abs(float(r["close"]) - float(r["open"]))
            for _, r in recent_10.iterrows()
            if r["close"] < r["open"]
        ][-5:]

        # ── TRUE RANGE & ATR ──
        df_closed = df.iloc[:-1].copy()
        _n = len(df_closed)
        _cv = df_closed["close"].values
        _hv = df_closed["high"].values
        _lv = df_closed["low"].values

        # True Range via pandas (handles first row cleanly)
        _tr = pd.concat(
            [
                df_closed["high"] - df_closed["low"],
                (df_closed["high"] - df_closed["close"].shift(1)).abs(),
                (df_closed["low"] - df_closed["close"].shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        # Seed the first value of TR to be High - Low to avoid NA issues
        _tr.iloc[0] = _hv[0] - _lv[0]
        _atr_50_series = _tr.ewm(span=50, adjust=False).mean().values

        # ── SUPERTREND (period=10, multiplier=0.9) ──
        # 'Change ATR Calculation Method? = true' usually implies SMA instead of Wilder's RMA
        _atr = _tr.rolling(window=10).mean().values
        _atr = _np.nan_to_num(_atr, nan=0.0) # Handle initial NaNs
        
        # Fallback for initial values before rolling window is full
        for i in range(10):
            if _atr[i] == 0.0 and i > 0:
                _atr[i] = _tr.iloc[:i+1].mean()
                
        _hl2 = (_hv + _lv) / 2.0
        _UBb = _hl2 + 0.9 * _atr  # basic upper band
        _LBb = _hl2 - 0.9 * _atr  # basic lower band
        _UB = _UBb.copy()
        _LB = _LBb.copy()
        _STL = _np.empty(_n)  # SuperTrend line
        _SDir = _np.ones(_n, dtype=int)  # 1=BULL, -1=BEAR
        _STL[0] = _LBb[0]

        for _i in range(1, _n):
            _UB[_i] = (
                _UBb[_i]
                if (_UBb[_i] < _UB[_i - 1] or _cv[_i - 1] > _UB[_i - 1])
                else _UB[_i - 1]
            )
            _LB[_i] = (
                _LBb[_i]
                if (_LBb[_i] > _LB[_i - 1] or _cv[_i - 1] < _LB[_i - 1])
                else _LB[_i - 1]
            )
            if _SDir[_i - 1] == 1:  # was BULL
                if _cv[_i] < _LB[_i]:
                    _SDir[_i] = -1
                    _STL[_i] = _UB[_i]
                else:
                    _SDir[_i] = 1
                    _STL[_i] = _LB[_i]
            else:  # was BEAR
                if _cv[_i] > _UB[_i]:
                    _SDir[_i] = 1
                    _STL[_i] = _LB[_i]
                else:
                    _SDir[_i] = -1
                    _STL[_i] = _UB[_i]

        _st_dir_now = int(_SDir[-1])  # 1=BULL, -1=BEAR
        _prev_st_dir = int(_SDir[-2]) if len(_SDir) > 1 else _st_dir_now
        _st_value = float(_STL[-1])

        _st_flips_5 = 0
        if len(_SDir) >= 6:
            for i in range(1, 6):
                if _SDir[-i] != _SDir[-i-1]:
                    _st_flips_5 += 1

        # ── BOLLINGER BANDS (period=20, std=2.0) ──
        # A volatility indicator. The middle band is a 20-period Simple Moving Average (SMA).
        # Upper and lower bands are 2 standard deviations away. Useful for detecting sideways chop (flat angle).
        _bb_mid_s = df_closed["close"].rolling(window=20).mean()
        _bb_std_s = df_closed["close"].rolling(window=20).std()
        _bb_mid_v = float(_bb_mid_s.iloc[-1])
        _bb_sd = float(_bb_std_s.iloc[-1])
        _bb_sd = _bb_sd if not math.isnan(_bb_sd) else 0.0
        _bb_up = _bb_mid_v + 2.0 * _bb_sd
        _bb_lo = _bb_mid_v - 2.0 * _bb_sd
        _bb_bw = _bb_up - _bb_lo
        
        _bb_bw_s = (_bb_mid_s + 2.0 * _bb_std_s) - (_bb_mid_s - 2.0 * _bb_std_s)
        _bb_bw_min_20 = float(_bb_bw_s.rolling(window=20).min().iloc[-1]) if len(_bb_bw_s) >= 20 else _bb_bw
        
        _bb_pos = float((current_price - _bb_lo) / _bb_bw) if _bb_bw > 0 else 0.5
        # BB angle in degrees — using atan2 formula
        _bb_arr = [x for x in _bb_mid_s.values[-7:] if not math.isnan(x)]
        _bb_ang = 0.0
        _prev_bb_ang = 0.0
        if len(_bb_arr) >= 6:
            _bb_ang = math.degrees(math.atan2(_bb_arr[-1] - _bb_arr[-6], 5))
            _prev_bb_ang = math.degrees(math.atan2(_bb_arr[-2] - _bb_arr[-7], 5))
        elif len(_bb_arr) >= 2:
            lookback = len(_bb_arr) - 1
            _bb_ang = math.degrees(math.atan2(_bb_arr[-1] - _bb_arr[0], lookback))
            _prev_bb_ang = _bb_ang

        # ── ADX (Average Directional Index) ──
        adx_period = getattr(config, "ADX_PERIOD", 14)
        up_move = df_closed["high"] - df_closed["high"].shift(1)
        down_move = df_closed["low"].shift(1) - df_closed["low"]

        plus_dm = _np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = _np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        plus_dm_series = pd.Series(plus_dm)
        minus_dm_series = pd.Series(minus_dm)

        # Wilder's Smoothing (alpha = 1 / period)
        tr_smooth = _tr.ewm(alpha=1/adx_period, adjust=False).mean()
        plus_di = 100 * (plus_dm_series.ewm(alpha=1/adx_period, adjust=False).mean() / tr_smooth)
        minus_di = 100 * (minus_dm_series.ewm(alpha=1/adx_period, adjust=False).mean() / tr_smooth)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx_series = dx.ewm(alpha=1/adx_period, adjust=False).mean()
        
        current_adx = float(adx_series.iloc[-1]) if not math.isnan(adx_series.iloc[-1]) else 0.0

        struct_curr_h = (
            float(df_closed["high"].iloc[-1]) if len(df_closed) >= 1 else 0.0
        )
        struct_curr_l = float(df_closed["low"].iloc[-1]) if len(df_closed) >= 1 else 0.0
        struct_prev_h = (
            float(df_closed["high"].iloc[-2]) if len(df_closed) >= 2 else struct_curr_h
        )
        struct_prev_l = (
            float(df_closed["low"].iloc[-2]) if len(df_closed) >= 2 else struct_curr_l
        )

        return {
            "close": current_price,
            "open": current_open,
            "prev_open": float(last_closed["open"]),
            "prev_close": float(last_closed["close"]),
            "candle_color": candle_color,
            "prev_color": prev_candle_color,
            "prev_body": prev_body_size,
            "is_lower": is_lower,
            "is_higher": is_higher,
            "time": current_candle["time"],
            "recent_strong_body": recent_strong_body,
            "prev_body_high": prev_body_high,
            "prev_body_low": prev_body_low,
            "recent_green_bodies": green_bodies,
            "recent_red_bodies": red_bodies,
            "recent_green_count": recent_green_count,
            "recent_red_count": recent_red_count,
            "recent_body_avg": recent_body_avg,
            "current_body_size": current_body_size,
            "current_upper_wick": current_upper_wick,
            "current_lower_wick": current_lower_wick,
            "st_direction": _st_dir_now,  # 1 = BULL, -1 = BEAR
            "prev_st_direction": _prev_st_dir,
            "st_value": _st_value,
            "atr_50": float(_atr_50_series[-1]),
            # Bollinger Bands
            "bb_mid": _bb_mid_v,
            "bb_upper": _bb_up,
            "bb_lower": _bb_lo,
            "bb_bandwidth": _bb_bw,
            "bb_position": _bb_pos,  # 0.0=lower band, 1.0=upper band
            "bb_angle": _bb_ang,  # degrees: >+15=up-trend, <-15=down-trend
            "prev_bb_angle": _prev_bb_ang,
            # Market Structure
            "struct_current_high": struct_curr_h,
            "struct_current_low": struct_curr_l,
            "struct_prev_high": struct_prev_h,
            "struct_prev_low": struct_prev_l,
            "st_flips_5": _st_flips_5,
            "bb_bandwidth_min_20": _bb_bw_min_20,
            "adx_14": current_adx,
        }
