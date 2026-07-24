import MetaTrader5 as mt5
from indicators import TechnicalIndicators
import config
from config import (
    ENTRY_VEL_FRESH,
    ENTRY_AVG_FRESH,
    MIN_ENTRY_2S_VEL,
    MIN_BODY_SIZE,
    MAX_CONFIRMATION_DRIFT,
    EMA_ANGLE_THRESHOLD,
)
from dataclasses import dataclass


@dataclass
class MomentumScore:
    total: float
    momentum: float
    trend: float
    candle: float
    execution: float
    grade: str
    block_reason: str = ""
    # Momentum Breakdown Sub-scores
    vel_score: float = 0.0
    v2s_score: float = 0.0
    avg_score: float = 0.0
    cons_score: float = 0.0
    accel_score: float = 0.0
    velocity_avg_change: float = 0.0
    velocity_acceleration: float = 0.0
    trend_state: str = "WAITING"
    sideways_score: int = 0
    required_score: float = 80.0


class EnhancedTradingStrategy:

    TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
    }

    def __init__(self, symbol: str, base_timeframe: str = "M5"):
        self.symbol = symbol
        self.base_timeframe = base_timeframe

    def analyze_timeframe(self, timeframe: str) -> dict:
        analysis = TechnicalIndicators.analyze_basic_timeframe(
            self.symbol, self.TIMEFRAMES[timeframe], bars=100
        )
        if not analysis:
            return {}

        analysis["current_candle"] = analysis.get("candle_color", "UNKNOWN")

        # --- MULTI-TIMEFRAME ALIGNMENT ---
        if (
            getattr(config, "ENABLE_MTF_ALIGNMENT", False)
            and timeframe == self.base_timeframe
        ):
            analysis["mtf_bullish"] = True
            analysis["mtf_bearish"] = True
            mtfs = getattr(config, "MTF_TIMEFRAMES", ["M15", "H1"])
            for tf in mtfs:
                if tf in self.TIMEFRAMES:
                    tf_analysis = TechnicalIndicators.analyze_basic_timeframe(
                        self.symbol, self.TIMEFRAMES[tf], bars=100
                    )
                    if tf_analysis:
                        # MTF alignment disabled or replaced
                        pass

        return analysis

    def calculate_momentum_score(
        self, direction: str, tick, analysis: dict, state: dict
    ) -> MomentumScore:
        score = MomentumScore(
            total=100.0,
            momentum=100.0,
            trend=100.0,
            candle=100.0,
            execution=100.0,
            grade="A+",
            block_reason="",
        )
        score.required_score = 100.0

        if not tick or not analysis:
            score.block_reason = "NO_DATA"
            return score

        # --- EXTRACT METRICS ---
        _curr_color = analysis.get("candle_color", "UNKNOWN")
        _prev_color = analysis.get("prev_color", "UNKNOWN")
        _curr_price = tick.bid

        _instant_velocity = analysis.get("velocity", 0.0)
        _avg_velocity = analysis.get("avg_velocity", 0.0) or 0.0

        _current_open = analysis.get("open", tick.bid)
        _curr_body = abs(tick.bid - _current_open)
        _prev_body = analysis.get("prev_body", 0.0)
        _ema_9 = analysis.get("ema_9")
        _prev_ema_9 = analysis.get("prev_ema_9")
        _ema_9_angle = analysis.get("ema_9_angle", 0.0)

        vel_limit = getattr(config, "ENTRY_VEL_FRESH", 0.05)
        avg_limit = getattr(config, "ENTRY_AVG_FRESH", 0.03)
        avg_limit = getattr(config, "ENTRY_AVG_FRESH", 0.03)


        # =========================================================================
        # 🟢 BUY ENTRY CONDITIONS
        # =========================================================================
        if direction == "BUY":

            # 1. Velocity Checks
            if _instant_velocity < vel_limit:
                score.block_reason = "HARD_RULE_VELOCITY"
                return score
            if _avg_velocity < avg_limit:
                score.block_reason = "HARD_RULE_AVG_VELOCITY"
                return score

            # 2. Current Candle Color Check
            if _curr_color != "GREEN":
                score.block_reason = "HARD_RULE_CURR_COLOR_MISMATCH"
                return score

            # 3. Minimum Body Size
            if _curr_body < 0.10:
                score.block_reason = "HARD_RULE_MIN_BODY_SIZE"
                return score

            # 4. EMA 9 Angle Filter
            if abs(_ema_9_angle) < EMA_ANGLE_THRESHOLD:
                score.block_reason = "HARD_RULE_EMA9_ANGLE_WEAK"
                return score

            # 5. EMA 9 Logic
            if _ema_9 is not None:
                if _curr_price > _ema_9:
                    # Case 1: Direct Buy - Valid
                    pass
                elif _curr_price < _ema_9:
                    # Case 2: Reversal / Pullback Buy
                    if _prev_color != "GREEN":
                        score.block_reason = "HARD_RULE_EMA9_PULLBACK_PREV_RED"
                        return score

        # =========================================================================
        # 🔴 SELL ENTRY CONDITIONS
        # =========================================================================
        else:

            # 1. Velocity Checks
            if _instant_velocity > -vel_limit:
                score.block_reason = "HARD_RULE_VELOCITY"
                return score
            if _avg_velocity > -avg_limit:
                score.block_reason = "HARD_RULE_AVG_VELOCITY"
                return score

            # 2. Current Candle Color Check
            if _curr_color != "RED":
                score.block_reason = "HARD_RULE_CURR_COLOR_MISMATCH"
                return score

            # 3. Minimum Body Size
            if _curr_body < 0.10:
                score.block_reason = "HARD_RULE_MIN_BODY_SIZE"
                return score

            # 4. EMA 9 Angle Filter
            if abs(_ema_9_angle) < EMA_ANGLE_THRESHOLD:
                score.block_reason = "HARD_RULE_EMA9_ANGLE_WEAK"
                return score

            # 5. EMA 9 Logic
            if _ema_9 is not None:
                if _curr_price < _ema_9:
                    # Case 1: Direct Sell - Valid
                    pass
                elif _curr_price > _ema_9:
                    # Case 2: Reversal / Pullback Sell
                    if _prev_color != "RED":
                        score.block_reason = "HARD_RULE_EMA9_PULLBACK_PREV_GREEN"
                        return score

        # All rules validated successfully!
        return score
