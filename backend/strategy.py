import MetaTrader5 as mt5
from indicators import TechnicalIndicators
import config
from config import (
    ENTRY_VEL_FRESH,
    ENTRY_AVG_FRESH,
    MIN_ENTRY_2S_VEL,
    BB_ANGLE_HARD_BLOCK,
    BB_ANGLE_STRONG,
    BB_ANGLE_VERY_STRONG,
    BB_ANGLE_EXTREME,
    MIN_BODY_SIZE,
    MAX_CONFIRMATION_DRIFT,
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
    bb_score: float = 0.0
    bb_angle: float = 0.0
    st_align_score: float = 0.0
    bb_imprv_score: float = 0.0
    struct_score: float = 0.0
    st_dist_score: float = 0.0
    st_flip_bonus: float = 0.0
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
                        st_dir = tf_analysis.get("st_direction", 0)
                        if st_dir != 1:
                            analysis["mtf_bullish"] = False
                        if st_dir != -1:
                            analysis["mtf_bearish"] = False

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
        score.bb_angle = analysis.get("bb_angle", 0.0)

        if not tick or not analysis:
            score.block_reason = "NO_DATA"
            return score

        # --- EXTRACT METRICS ---
        _curr_color = analysis.get("candle_color", "UNKNOWN")
        _prev_color = analysis.get("prev_color", "UNKNOWN")
        _st_dir = analysis.get("st_direction", 0)  # 1 = BULL, -1 = BEAR
        _bb_ang = analysis.get("bb_angle", 0.0)     # BB Midline Angle
        _bb_mid = analysis.get("bb_mid") or analysis.get("bb_basis") or tick.bid # BB Midline Price (safely handled)
        _curr_price = tick.bid

        _instant_velocity = analysis.get("velocity", 0.0)
        _avg_velocity = analysis.get("avg_velocity", 0.0) or 0.0

        _current_open = analysis.get("open", tick.bid)
        _curr_body = abs(tick.bid - _current_open)
        _prev_body = analysis.get("prev_body", 0.0)

        vel_limit = getattr(config, "ENTRY_VEL_FRESH", 0.05)
        avg_limit = getattr(config, "ENTRY_AVG_FRESH", 0.03)
        bb_ang_limit = getattr(config, "BB_ANGLE_HARD_BLOCK", 5.0)

        is_above_midline = _curr_price > _bb_mid

        # -------------------------------------------------------------------------
        # COMMON RULE: ABSOLUTE BB ANGLE MUST BE AT LEAST 5 DEGREES (ANY DIRECTION)
        # -------------------------------------------------------------------------
        if abs(_bb_ang) < bb_ang_limit:
            score.block_reason = "HARD_RULE_BB_ANGLE"
            return score

        # =========================================================================
        # 🟢 BUY ENTRY CONDITIONS
        # =========================================================================
        if direction == "BUY":
            # 1. SuperTrend Check (Must be BULLISH)
            if _st_dir != 1:
                score.block_reason = "HARD_RULE_ST_DIRECTION"
                return score

            # 2. Velocity Checks
            if _instant_velocity < vel_limit:
                score.block_reason = "HARD_RULE_VELOCITY"
                return score
            if _avg_velocity < avg_limit:
                score.block_reason = "HARD_RULE_AVG_VELOCITY"
                return score

            # 3. Current Candle Color Check
            if _curr_color != "GREEN":
                score.block_reason = "HARD_RULE_CURR_COLOR_MISMATCH"
                return score

            # 4. MIDLINE LOCATION vs PREVIOUS CANDLE RULE
            # Below midline: Current candle is GREEN, but PREV CANDLE MUST ALSO BE GREEN
            if not is_above_midline:
                if _prev_color != "GREEN":
                    score.block_reason = "HARD_RULE_BELOW_MIDLINE_PREV_GREEN_REQUIRED"
                    return score

            # 5. Minimum Body Size
            if _curr_body < 0.10:
                score.block_reason = "HARD_RULE_MIN_BODY_SIZE"
                return score

        # =========================================================================
        # 🔴 SELL ENTRY CONDITIONS
        # =========================================================================
        else:
            # 1. SuperTrend Check (Must be BEARISH)
            if _st_dir != -1:
                score.block_reason = "HARD_RULE_ST_DIRECTION"
                return score

            # 2. Velocity Checks
            if _instant_velocity > -vel_limit:
                score.block_reason = "HARD_RULE_VELOCITY"
                return score
            if _avg_velocity > -avg_limit:
                score.block_reason = "HARD_RULE_AVG_VELOCITY"
                return score

            # 3. Current Candle Color Check
            if _curr_color != "RED":
                score.block_reason = "HARD_RULE_CURR_COLOR_MISMATCH"
                return score

            # 4. MIDLINE LOCATION vs PREVIOUS CANDLE RULE
            # Above midline: Current candle is RED, but PREV CANDLE MUST ALSO BE RED
            if is_above_midline:
                if _prev_color != "RED":
                    score.block_reason = "HARD_RULE_ABOVE_MIDLINE_PREV_RED_REQUIRED"
                    return score

            # 5. Minimum Body Size
            if _curr_body < 0.10:
                score.block_reason = "HARD_RULE_MIN_BODY_SIZE"
                return score

        # All rules validated successfully!
        return score
