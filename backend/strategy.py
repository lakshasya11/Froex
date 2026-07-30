import MetaTrader5 as mt5
from indicators import TechnicalIndicators
import config
from dataclasses import dataclass


@dataclass
class MomentumScore:
    total: float = 0.0
    momentum: float = 0.0
    trend: float = 0.0
    candle: float = 0.0
    execution: float = 0.0
    grade: str = "C"
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


@dataclass
class SignalValidationResult:
    blocked: bool
    block_reason: str = ""
    context: dict = None  # Holds pre-computed metrics for scoring


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
                        pass

        return analysis

    def get_setting(self, key: str, default_val: float) -> float:
        st_settings = getattr(config, "SYMBOL_TIMEFRAME_SETTINGS", {}).get(self.symbol, {}).get(self.base_timeframe, {})
        if key in st_settings:
            return st_settings[key]
        s_settings = getattr(config, "SYMBOL_SETTINGS", {}).get(self.symbol, {})
        if key in s_settings:
            return s_settings[key]
        return getattr(config, key, default_val)

    def validate_signal(self, direction: str, tick, analysis: dict) -> SignalValidationResult:
        if not tick or not analysis:
            return SignalValidationResult(blocked=True, block_reason="NO_DATA")

        _curr_color = analysis.get("candle_color", "UNKNOWN")
        _prev_color = analysis.get("prev_color", "UNKNOWN")
        
        fallback_price = TechnicalIndicators.get_effective_price(tick)
        _curr_price = analysis.get("close", fallback_price)

        _instant_velocity = analysis.get("velocity", 0.0)
        _avg_velocity = analysis.get("avg_velocity", 0.0) or 0.0

        _current_open = analysis.get("open", _curr_price)
        _curr_body = abs(_curr_price - _current_open)
        _ema_9 = analysis.get("ema_9")
        _ema_9_angle = analysis.get("ema_9_angle", 0.0)

        _ema_21 = analysis.get("ema_21")
        _ema_21_angle = analysis.get("ema_21_angle", 0.0)

        _atr_14 = analysis.get("atr_14", 0.0)
        _current_high = analysis.get("current_high", _curr_price)
        _current_low = analysis.get("current_low", _curr_price)
        _candle_range = _current_high - _current_low
        dist_to_high = _current_high - _curr_price
        dist_to_low = _curr_price - _current_low
        
        spread = 0.0
        if tick.ask > 0.0 and tick.bid > 0.0:
            spread = tick.ask - tick.bid

        vel_limit = getattr(config, "ENTRY_VEL_FRESH", 0.05)
        avg_limit = getattr(config, "ENTRY_AVG_FRESH", 0.03)

        base_wick_tolerance = self.get_setting("BASE_WICK_TOLERANCE", 0.50)
        wick_atr_mult = self.get_setting("WICK_ATR_MULT", 0.20)
        wick_tolerance = max(base_wick_tolerance, _atr_14 * wick_atr_mult)

        min_atr = self.get_setting("MIN_ATR_THRESHOLD", 1.20)
        min_ema_gap = self.get_setting("MIN_EMA_GAP_PTS", 0.35)
        ema21_angle_thresh = self.get_setting("EMA21_ANGLE_THRESHOLD", 4.0)
        ema9_angle_thresh = self.get_setting("EMA9_ANGLE_THRESHOLD", 8.0)
        

        
        min_body_size = self.get_setting("MIN_BODY_SIZE", 0.10)
        max_spread = self.get_setting("SPREAD_ALLOWANCE", 0.20)

        ema_gap = abs(_ema_9 - _ema_21) if _ema_9 is not None and _ema_21 is not None else 0.0

        context = {
            "curr_price": _curr_price,
            "instant_velocity": _instant_velocity,
            "avg_velocity": _avg_velocity,
            "curr_body": _curr_body,
            "candle_range": _candle_range,
            "atr_14": _atr_14,
            "ema_9_angle": _ema_9_angle,
            "ema_21_angle": _ema_21_angle,
            "spread": spread,
            "vel_limit": vel_limit,
            "avg_limit": avg_limit,
            "dist_to_high": dist_to_high,
            "dist_to_low": dist_to_low,
            "wick_tolerance": wick_tolerance,
            "ema_gap": ema_gap,
            "min_ema_gap": min_ema_gap,
            "ema9_angle_min": ema9_angle_thresh,
            "ema21_angle_min": ema21_angle_thresh,
        }

        def block(reason: str) -> SignalValidationResult:
            return SignalValidationResult(blocked=True, block_reason=reason, context=context)

        if spread > 0.0 and spread > max_spread:
            return block(f"HARD_RULE_SPREAD_TOO_HIGH ({spread:.2f} > {max_spread:.2f})")

        if _atr_14 < min_atr:
            return block("HARD_RULE_ATR_TOO_LOW")

        if _ema_9 is not None and _ema_21 is not None:
            if abs(_ema_9 - _ema_21) < min_ema_gap:
                return block("HARD_RULE_EMA_GAP_TOO_SMALL")

        # Check if EMA angles meet the minimum steepness thresholds for strong trends
        if abs(_ema_21_angle) < ema21_angle_thresh:
            return block("HARD_RULE_EMA21_ANGLE_WEAK")
        if abs(_ema_9_angle) < ema9_angle_thresh:
            return block("HARD_RULE_EMA9_ANGLE_WEAK")

        if direction == "BUY":

            if _curr_color != "GREEN":
                return block("HARD_RULE_CURR_COLOR_MISMATCH")
            if _curr_body < min_body_size:
                return block("HARD_RULE_MIN_BODY_SIZE")
            if _ema_9 is not None and _curr_price < _ema_9:
                if _prev_color != "GREEN":
                    return block("HARD_RULE_EMA9_PULLBACK_PREV_GREEN")
            if (_curr_price - _current_open) <= 0:
                return block("HARD_RULE_PRICE_BELOW_OPEN")
            dist_to_high = _current_high - _curr_price
            if dist_to_high > wick_tolerance:
                return block("HARD_RULE_NOT_AT_HIGH")
            if abs(_instant_velocity) < vel_limit:
                return block("HARD_RULE_VELOCITY")
            if abs(_avg_velocity) < avg_limit:
                return block("HARD_RULE_AVG_VELOCITY")
        else:


            if _curr_color != "RED":
                return block("HARD_RULE_CURR_COLOR_MISMATCH")
            if _curr_body < min_body_size:
                return block("HARD_RULE_MIN_BODY_SIZE")
            if _ema_9 is not None and _curr_price > _ema_9:
                if _prev_color != "RED":
                    return block("HARD_RULE_EMA9_PULLBACK_PREV_RED")
            if (_curr_price - _current_open) >= 0:
                return block("HARD_RULE_PRICE_ABOVE_OPEN")
            sell_wick_mult = self.get_setting("SELL_WICK_MULT", 1.25)
            sell_wick_tolerance = wick_tolerance * sell_wick_mult
            if dist_to_low > sell_wick_tolerance:
                return block("HARD_RULE_NOT_AT_LOW")
            # --- FIXED: Use abs() so positive and negative velocity magnitudes work cleanly ---
            if abs(_instant_velocity) < vel_limit:
                return block("HARD_RULE_VELOCITY")
            if abs(_avg_velocity) < avg_limit:
                return block("HARD_RULE_AVG_VELOCITY")

        return SignalValidationResult(blocked=False, context=context)

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
        score.required_score = self.get_setting("MOMENTUM_SCORE_THRESHOLD", 80.0)

        validation_result = self.validate_signal(direction, tick, analysis)
        if validation_result.blocked:
            score.block_reason = validation_result.block_reason
            return score
            
        ctx = validation_result.context
        
        score.total = 100.0

        vel_penalty_factor = self.get_setting("VEL_PENALTY_FACTOR", 1.5)
        vel_bonus_factor = self.get_setting("VEL_BONUS_FACTOR", 2.0)
        wick_penalty_factor = self.get_setting("WICK_PENALTY_FACTOR", 0.5)
        wick_bonus_factor = self.get_setting("WICK_BONUS_FACTOR", 0.2)
        ema_angle_bonus_mult = self.get_setting("EMA_ANGLE_BONUS_MULT", 2.0)
        ema_gap_bonus_mult = self.get_setting("EMA_GAP_BONUS_MULT", 1.5)

        # --- Velocity quality ---
        vel = abs(ctx["instant_velocity"])
        vel_limit = ctx["vel_limit"]
        
        avg_vel = abs(ctx["avg_velocity"])
        avg_limit = ctx["avg_limit"]

        # --- FIXED: Evaluated on magnitude (abs) for both BUY and SELL ---
        if vel_limit <= vel < vel_limit * vel_penalty_factor:
            score.total -= 10
            score.vel_score = 90
        elif vel >= vel_limit * vel_bonus_factor:
            score.total += 5
            score.vel_score = 105
            
        if avg_limit <= avg_vel < avg_limit * vel_penalty_factor:
            score.total -= 5
            score.vel_score -= 5
        elif avg_vel >= avg_limit * vel_bonus_factor:
            score.total += 5
            score.vel_score += 5

        # --- Wick & close quality ---
        dist_to_extreme = ctx["dist_to_high"] if direction == "BUY" else ctx["dist_to_low"]
        wick_tol = ctx["wick_tolerance"]

        if dist_to_extreme > wick_tol * wick_penalty_factor:
            score.total -= 5
            score.cons_score = 95
        elif dist_to_extreme <= wick_tol * wick_bonus_factor:
            score.total += 5
            score.cons_score = 105

        # --- Trend quality (EMA angles & gap) ---
        ema9_angle = ctx["ema_9_angle"]
        ema21_angle = ctx["ema_21_angle"]
        ema_gap = ctx["ema_gap"]
        min_gap = ctx["min_ema_gap"]

        if abs(ema9_angle) > ctx["ema9_angle_min"] * ema_angle_bonus_mult:
            score.total += 5
            score.trend = 105
        if ema_gap > min_gap * ema_gap_bonus_mult:
            score.total += 5

        # Clamp and grade
        score.total = max(0.0, min(100.0, score.total))

        if score.total >= 100:
            score.grade = "A+"
        elif score.total >= 90:
            score.grade = "A"
        elif score.total >= 80:
            score.grade = "B"
        else:
            score.grade = "C"
        
        if score.total < score.required_score:
            score.block_reason = f"SCORE_TOO_LOW ({score.total:.1f} < {score.required_score:.1f})"

        return score
