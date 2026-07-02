LOT_SIZE                   = 0.10               # Fixed lot size for all trades
MAX_SIMULTANEOUS_POSITIONS = 1 #simultaneous trades 
MAX_TRADES_PER_CANDLE      = 5 #one candle max trades 
MAX_LOSSES_PER_CANDLE      = 2 #one candle max loss ignore next trade 


TP_ULTRA_STRONG = 8.00   # fast spike entry
TP_STRONG       = 5.00   # strong entry
TP_MODERATE     = 3.00   # normal entry

MAX_RISK_TO_TP_RATIO = 1.0

HARD_STOP_LOSS = 2.00
SPREAD_ALLOWANCE = 0.10

TRAIL_TRIGGER_PTS          = 1.50   # start trailing after 1.50 pts profit
TRAIL_GAP_PTS              = 0.80   # minimum trail gap
DYNAMIC_TRAIL_GAP_PERCENT  = 0.20   # trail gap scales to 20% of TP (allows breathing room)
TRAIL_MODIFY_MIN_INTERVAL  = 0.2    # update trail every 0.2 seconds

ENTRY_VEL_FRESH    = 0.15    # Instant Velocity requirement
ENTRY_AVG_FRESH    = 0.10    # Average Velocity requirement
MIN_ENTRY_2S_VEL   = 0.13    # 2s Velocity requirement
MIN_BODY_SIZE      = 0.15    # Minimum candle body size to allow entry

EARLY_ENTRY_SECONDS = 3   # allow early entry up to 3 seconds into candle

MAX_ENTRY_SLIPPAGE = 0.20   # if slippage > 0.20 pts, cancel the trade

ENTRY_CONFIRM_TICKS = 2   # 2 consecutive ticks of confirmed conditions before entry
MAX_DAILY_TRADES = 1000   # 1000 trades per calendar day — no daily limit for demo testing

ENABLE_DYNAMIC_VELOCITY        = False
DYNAMIC_VELOCITY_BASE_ATR      = 2.50   # baseline ATR (normal market)
DYNAMIC_VELOCITY_MULTIPLIER    = 1.10   # scale factor when ATR is above baseline

ENABLE_DYNAMIC_SL_TP           = False
DYNAMIC_SL_ATR_MULTIPLIER      = 1.5
MIN_DYNAMIC_SL                 = 2.00
MAX_DYNAMIC_SL                 = 6.00
DYNAMIC_TP_BASE_MULTIPLIER     = 2.0

ENABLE_NEWS_FILTER       = False
NEWS_BLOCK_PRE_MINUTES   = 15   # pause 15 mins BEFORE news
NEWS_BLOCK_POST_MINUTES  = 10   # pause 10 mins AFTER news (Gold takes longer to settle)
NEWS_TARGET_CURRENCY     = 'USD'
NEWS_IMPACT_LEVEL        = 'High'

ENABLE_MTF_ALIGNMENT = False
MTF_TIMEFRAMES       = ['M15']

ENABLE_SESSION_FILTER  = False
SESSION_START_HOUR_UTC = 3    # 03:00 UTC = ~09:00 AM IST (your start time)
SESSION_END_HOUR_UTC   = 18   # 18:00 UTC = ~11:30 PM IST (your end time)

MAX_CONFIRMATION_DRIFT = 0.40   # 0.40 pts max drift during confirmation window

CANDLE_ENTRY_START = 15      # allow entry from 15s into candle
CANDLE_ENTRY_END   = 280   # block entries after 280s (last 20s of M5 candle = no entry)

MAX_CONSEC_LOSSES  = 999   # 999 disables the consecutive loss pause
LOSS_PAUSE_CANDLES = 3   # pause for 3 candles (= 15 minutes on M5) before trading again


REVERSAL_PREV_BODY_MIN = 0.50

PROFIT_LOCK_STEPS = [
    (5.00, 3.50),   # reach 5.00 → lock 3.50 (1.5 pt room)
    (4.00, 2.50),   # reach 4.00 → lock 2.50 (1.5 pt room)
    (3.00, 1.50),   # reach 3.00 → lock 1.50 (1.5 pt room)
]
