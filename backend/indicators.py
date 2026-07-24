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

        # ── EMA 9 ──
        ema_9_series = df_closed["close"].ewm(span=9, adjust=False).mean()
        current_ema_9 = float(ema_9_series.iloc[-1]) if len(ema_9_series) > 0 else current_price
        prev_ema_9 = float(ema_9_series.iloc[-2]) if len(ema_9_series) > 1 else current_ema_9
        
        # Calculate angle using inverse tangent over a 5 bar lookback window
        lookback_bars = 5
        ema_9_lookback = float(ema_9_series.iloc[-(lookback_bars + 1)]) if len(ema_9_series) > lookback_bars else current_ema_9
        ema_9_angle = math.degrees(math.atan((current_ema_9 - ema_9_lookback) / lookback_bars))

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
            "atr_50": float(_atr_50_series[-1]),
            # Market Structure
            "struct_current_high": struct_curr_h,
            "struct_current_low": struct_curr_l,
            "struct_prev_high": struct_prev_h,
            "struct_prev_low": struct_prev_l,
            "adx_14": current_adx,
            "ema_9": current_ema_9,
            "prev_ema_9": prev_ema_9,
            "ema_9_angle": ema_9_angle,
        }
