"""
Configuration Settings for XAUUSD Momentum Scalping Bot.
This file contains all the hardcoded parameters used by the bot to make trading decisions.
"""

# =============================================================================
# GENERAL TRADING SETTINGS
# =============================================================================
SYMBOL = "XAUUSD"
TIMEFRAME = "M5"
STRATEGY_VERSION = "v1.1.0-ConfidenceAnalyzer"

LOT_SIZE = 0.15  # Fixed lot size for all trades
MAX_SIMULTANEOUS_POSITIONS = 1  # Maximum number of simultaneous trades allowed
MAX_LOSSES_PER_CANDLE = 99999  # Stop trading on this candle if we hit 2 losses
MAX_DAILY_TRADES = 500  # Max 500 trades per calendar day
DAILY_PROFIT_TARGET = 350.0  # Stop trading if daily net profit reaches or exceeds this amount
MAX_CONSEC_LOSSES = 99999  # 100 disables the consecutive loss pause
LOSS_PAUSE_CANDLES = (
    0  # Pause trading for 2 candles after hitting the consecutive loss limit
)

# =============================================================================
# RISK MANAGEMENT & EXECUTION
# =============================================================================
MAX_RISK_TO_TP_RATIO = (
    1.0  # Maximum allowed ratio between Stop Loss risk and Take Profit reward
)
SPREAD_ALLOWANCE = 0.20  # Maximum acceptable spread in points
MAX_ENTRY_SLIPPAGE = 0.20  # Cancel the trade if slippage exceeds 0.20 points

# =============================================================================
# TECHNICAL ENTRY CRITERIA
# =============================================================================
BB_ANGLE_HARD_BLOCK = 5.0
BB_ANGLE_STRONG = 10.0
BB_ANGLE_VERY_STRONG = 15.0
BB_ANGLE_EXTREME = 20.0
ENTRY_VEL_FRESH = 0.05  # Minimum instantaneous velocity required for entry
ENTRY_AVG_FRESH = 0.03  # Minimum average velocity required for entry
MIN_ENTRY_2S_VEL = 0.04  # Minimum 2-second velocity required for entry
MIN_BODY_SIZE = 0.10  # Minimum candle body size required to allow entry
ENTRY_CONFIRM_TICKS = (
    2  # Require 2 consecutive ticks of confirmed conditions before entry
)
MAX_CONFIRMATION_DRIFT = (
    0.60  # Maximum allowed price drift during the confirmation window
)

# =============================================================================
# TRAILING STOP SETTINGS
# =============================================================================
TRAIL_MODIFY_MIN_INTERVAL = (
    0.2  # Only update the trailing stop every 0.2 seconds to avoid API spam
)

# =============================================================================
# SESSION & NEWS
# =============================================================================
ENABLE_SESSION_FILTER = False
SESSION_START_HOUR_UTC = 3  # 03:00 UTC = ~09:00 AM IST (Start of trading session)
SESSION_END_HOUR_UTC = 18  # 18:00 UTC = ~11:30 PM IST (End of trading session)

ENABLE_NEWS_FILTER = True
BLOCK_TRADES_ON_NEWS = False

# =============================================================================
# MULTI-TIMEFRAME ALIGNMENT
# =============================================================================
ENABLE_MTF_ALIGNMENT = False
MTF_TIMEFRAMES = ["M15"]

# =============================================================================
# TIMEFRAME SPECIFIC SETTINGS
# =============================================================================
# These settings override default parameters based on the active timeframe.
# Parameters include: Maximum trades per candle, Take Profit tiers, Hard Stop Loss,
# Trailing Stop triggers, and Profit Lock scaling.
TIMEFRAME_SETTINGS = {
    "M1": {
        "MAX_TRADES_CANDLE": 99999,
        "MAX_CONSEC_LOSSES": 99999,
        "LOSS_PAUSE_CANDLES": 0,
        "TP_STRONG": 3.00,
        "TP_ULTRA_STRONG": 5.00,
        "HARD_STOP_LOSS": 1.00,
        "TRAIL_TRIGGER_PTS": 1.00,
        "TRAIL_GAP_PTS": 0.60,
        "PROFIT_LOCK_STEPS": [(0.80, 0.20)],
    },
    "M5": {
        "MAX_TRADES_CANDLE": 99999,
        "MAX_CONSEC_LOSSES": 99999,
        "LOSS_PAUSE_CANDLES": 0,
        "TP_STRONG": 5.00,
        "TP_ULTRA_STRONG": 8.00,
        "HARD_STOP_LOSS": 2.00,
        "TRAIL_TRIGGER_PTS": 1.80,
        "TRAIL_GAP_PTS": 0.80,
        "PROFIT_LOCK_STEPS": [
            (1.50, 0.50),
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
# NEW FILTERS (CLEAN BREAK, SIDEWAYS SCORE)
# =============================================================================
MIN_ATR = 1.0

CLEAN_BREAK_ATR_FRACTION = 0.20

# Momentum Scoring
MOMENTUM_SCORE_THRESHOLD = 80.0
M1_MOMENTUM_SCORE_THRESHOLD = 80.0

# Score Category Weights (Multipliers to scale category importance)
WEIGHT_MOMENTUM = 1.0   # Max base points: 50.0
WEIGHT_TREND = 1.0      # Max base points: 20.0
WEIGHT_CANDLE = 1.0     # Max base points: 20.0
WEIGHT_EXECUTION = 1.0  # Max base points: 15.0

ACCEL_EXCELLENT = 0.08
ACCEL_GOOD = 0.04
ACCEL_OK = 0.02

DEBUG_SCORING = False

