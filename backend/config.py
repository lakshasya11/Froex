"""
Configuration Settings for XAUUSD Momentum Scalping Bot.
This file contains all the hardcoded parameters used by the bot to make trading decisions.
"""

# =============================================================================
# 1. GENERAL TRADING SETTINGS
# =============================================================================
SYMBOL = "XAUUSD"
TIMEFRAME = "M5"
STRATEGY_VERSION = "v1.1.0-ConfidenceAnalyzer"

LOT_SIZE = 0.10  # Fixed lot size for all trades
MAX_SIMULTANEOUS_POSITIONS = 1  # Maximum number of simultaneous trades allowed
MAX_LOSSES_PER_CANDLE = 99999  # Stop trading on this candle if we hit 2 losses
MAX_DAILY_TRADES = 500  # Max 500 trades per calendar day
DAILY_PROFIT_TARGET = 350.0  # Stop trading if daily net profit reaches or exceeds this amount
MAX_CONSEC_LOSSES = 99999  # 100 disables the consecutive loss pause
LOSS_PAUSE_CANDLES = 0  # Pause trading for N candles after hitting the consecutive loss limit

# =============================================================================
# 2. RISK MANAGEMENT & EXECUTION
# =============================================================================
MAX_RISK_TO_TP_RATIO = 1.0  # Maximum allowed ratio between Stop Loss risk and Take Profit reward
SPREAD_ALLOWANCE = 0.20  # Maximum acceptable spread in points
MAX_ENTRY_SLIPPAGE = 0.10  # Cancel the trade if slippage exceeds 0.10 points


# =============================================================================
# 3. TECHNICAL ENTRY CRITERIA (HARD RULES)
# =============================================================================
MIN_ATR_THRESHOLD = 1.20     # Minimum ATR(14) required to confirm volatility
MIN_EMA_GAP_PTS = 0.35       # Minimum point gap between EMA 9 and EMA 21
EMA9_ANGLE_THRESHOLD = 8.0   # Minimum EMA 9 angle required for trend strength
EMA21_ANGLE_THRESHOLD = 4.0  # Minimum EMA 21 angle required for baseline trend

# Candle Structure Guards
MIN_BODY_SIZE = 0.10         # Lower body size threshold for candles
MIN_CANDLE_RANGE = 0.10      # Minimum overall candle range (High - Low) required
CANDLE_RANGE_ATR_MULT = 0.30 # Candle range must also be at least this fraction of ATR

# =============================================================================
# 4. VELOCITY / MOMENTUM FILTERS
# =============================================================================
ENTRY_VEL_FRESH = 0.05       # Velocity threshold for tick momentum
ENTRY_AVG_FRESH = 0.03       # Average velocity threshold
MIN_ENTRY_2S_VEL = 0.02      # Minimum 2-second velocity required for entry
ENTRY_CONFIRM_TICKS = 2      # Tick confirmation window
MAX_CONFIRMATION_DRIFT = 0.60 # Maximum allowed price drift during confirmation window

# =============================================================================
# 5. TRAILING STOP SETTINGS
# =============================================================================
TRAIL_MODIFY_MIN_INTERVAL = 0.2  # Only update the trailing stop every 0.2 seconds to avoid API spam

# =============================================================================
# 6. SESSION & NEWS
# =============================================================================
ENABLE_SESSION_FILTER = False
SESSION_START_HOUR_UTC = 3  # 03:00 UTC = ~09:00 AM IST (Start of trading session)
SESSION_END_HOUR_UTC = 18  # 18:00 UTC = ~11:30 PM IST (End of trading session)

ENABLE_NEWS_FILTER = True
BLOCK_TRADES_ON_NEWS = False

# =============================================================================
# 7. MULTI-TIMEFRAME ALIGNMENT
# =============================================================================
ENABLE_MTF_ALIGNMENT = False
MTF_TIMEFRAMES = ["M15"]

# =============================================================================
# 8. TIMEFRAME SPECIFIC SETTINGS
# =============================================================================
# These settings override default parameters based on the active timeframe.
# Parameters include: Maximum trades per candle, Take Profit tiers, Hard Stop Loss,
# Trailing Stop triggers, and Profit Lock scaling.
TIMEFRAME_SETTINGS = {
    "M1": {
        "MAX_TRADES_CANDLE": 2,
        "MAX_CONSEC_LOSSES": 99999,
        "LOSS_PAUSE_CANDLES": 0,
        "TP_STRONG": 3.00,
        "TP_ULTRA_STRONG": 5.00,
        "HARD_STOP_LOSS": 2.00,
        "TRAIL_TRIGGER_PTS": 0.80,     # Activate trailing stop early
        "TRAIL_GAP_PTS": 0.40,         # Tight trailing gap
        "PROFIT_LOCK_STEPS": [],       # Removed profit lock for M1
    },
    "M5": {
        "MAX_TRADES_CANDLE": 3,
        "MAX_CONSEC_LOSSES": 99999,
        "LOSS_PAUSE_CANDLES": 0,
        "TP_STRONG": 5.00,
        "TP_ULTRA_STRONG": 8.00,
        "HARD_STOP_LOSS": 2.00,
        "TRAIL_TRIGGER_PTS": 1.80,
        "TRAIL_GAP_PTS": 0.80,
        "PROFIT_LOCK_STEPS": [
            (1.20, 0.50),
        ],
    },
    "M15": {
        "MAX_TRADES_CANDLE": 7,
        "MAX_CONSEC_LOSSES": 4,
        "LOSS_PAUSE_CANDLES": 3,
        "TP_STRONG": 8.00,
        "TP_ULTRA_STRONG": 12.00,
        "HARD_STOP_LOSS": 3.00,
        "TRAIL_TRIGGER_PTS": 2.50,
        "TRAIL_GAP_PTS": 1.20,
        "PROFIT_LOCK_STEPS": [(2.00, 0.80)],
    },
    "M30": {
        "MAX_TRADES_CANDLE": 10,
        "MAX_CONSEC_LOSSES": 5,
        "LOSS_PAUSE_CANDLES": 4,
        "TP_STRONG": 12.00,
        "TP_ULTRA_STRONG": 18.00,
        "HARD_STOP_LOSS": 5.00,
        "TRAIL_TRIGGER_PTS": 4.00,
        "TRAIL_GAP_PTS": 2.00,
        "PROFIT_LOCK_STEPS": [(3.00, 1.00)],
    },
}

# =============================================================================
# 9. SYMBOL & TIMEFRAME SPECIFIC PROFILE OVERRIDES (3-TIER CASCADE)
# =============================================================================
SYMBOL_TIMEFRAME_SETTINGS = {
    "XAUUSD": {
        "M1": {
            "MIN_ATR_THRESHOLD": 0.80,
            "MIN_EMA_GAP_PTS": 0.20,
            "EMA9_ANGLE_THRESHOLD": 6.0,
            "EMA21_ANGLE_THRESHOLD": 3.0,
            "MOMENTUM_SCORE_THRESHOLD": 90.0, # Stricter threshold for noisier M1
        },
        "M5": {
            "MIN_ATR_THRESHOLD": 1.20,
            "MIN_EMA_GAP_PTS": 0.35,
            "EMA9_ANGLE_THRESHOLD": 8.0,
            "EMA21_ANGLE_THRESHOLD": 4.0,
            "MOMENTUM_SCORE_THRESHOLD": 80.0,
        },
        "M15": {
            "MIN_ATR_THRESHOLD": 1.50,
            "MIN_EMA_GAP_PTS": 0.50,
            "EMA9_ANGLE_THRESHOLD": 8.0,
            "EMA21_ANGLE_THRESHOLD": 4.0,
            "MOMENTUM_SCORE_THRESHOLD": 80.0,
        }
    }
}

# Symbol-wide defaults (fallback if timeframe-specific isn't found)
SYMBOL_SETTINGS = {
    "XAUUSD": {
        "SPREAD_ALLOWANCE": 0.20
    }
}

# =============================================================================
# 10. SOFT SCORING CALIBRATION
# =============================================================================
MOMENTUM_SCORE_THRESHOLD = 80.0
M1_MOMENTUM_SCORE_THRESHOLD = 80.0

# Penalty & Bonus Modifiers for Soft Scoring
VEL_PENALTY_FACTOR = 1.5     # Barely above minimum velocity threshold multiplier (penalty zone)
VEL_BONUS_FACTOR = 2.0       # Dynamic threshold multiplier for extra strong velocity (bonus zone)
WICK_PENALTY_FACTOR = 0.5    # Distance to extreme high/low must be under this fraction of wick tolerance to avoid penalty
WICK_BONUS_FACTOR = 0.2      # Distance to extreme high/low must be under this fraction of wick tolerance to get bonus
EMA_ANGLE_BONUS_MULT = 2.0   # EMA 9 angle must be this multiple of minimum required angle to get trend bonus
EMA_GAP_BONUS_MULT = 1.5     # EMA Gap must be this multiple of minimum gap to get gap bonus

# Score Category Weights (Multipliers to scale category importance)
WEIGHT_MOMENTUM = 1.0   # Max base points: 50.0
WEIGHT_TREND = 1.0      # Max base points: 20.0
WEIGHT_CANDLE = 1.0     # Max base points: 20.0
WEIGHT_EXECUTION = 1.0  # Max base points: 15.0

# Volatility acceleration benchmarks
ACCEL_EXCELLENT = 0.08
ACCEL_GOOD = 0.04
ACCEL_OK = 0.02

# =============================================================================
# 11. STRATEGY SPECIFIC FILTERS & DEBUG
# =============================================================================
MIN_ATR = 1.0
CLEAN_BREAK_ATR_FRACTION = 0.20
DEBUG_SCORING = False
