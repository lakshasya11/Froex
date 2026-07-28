import config

print("=== ENTRY THRESHOLDS ===")
print("EMA9 angle threshold:", getattr(config, "EMA_ANGLE_THRESHOLD", 10.0))
print("EMA21 angle threshold:", getattr(config, "EMA21_ANGLE_THRESHOLD", 5.0))
print("MIN_EMA_GAP_PTS:", getattr(config, "MIN_EMA_GAP_PTS", 0.35))
print("MIN_ATR_THRESHOLD:", getattr(config, "MIN_ATR_THRESHOLD", 1.20))
print("ENTRY_VEL_FRESH:", getattr(config, "ENTRY_VEL_FRESH", 0.05))
print("ENTRY_AVG_FRESH:", getattr(config, "ENTRY_AVG_FRESH", 0.03))
print("MIN_ENTRY_2S_VEL:", getattr(config, "MIN_ENTRY_2S_VEL", 0.04))
print("ENTRY_CONFIRM_TICKS:", getattr(config, "ENTRY_CONFIRM_TICKS", 2))
print("SPREAD_ALLOWANCE:", getattr(config, "SPREAD_ALLOWANCE", 0.20))
print("MAX_ENTRY_SLIPPAGE:", getattr(config, "MAX_ENTRY_SLIPPAGE", 0.20))
print("MAX_DAILY_TRADES:", getattr(config, "MAX_DAILY_TRADES", 6))
print("MAX_SIMULTANEOUS_POSITIONS:", getattr(config, "MAX_SIMULTANEOUS_POSITIONS", 1))
print("ENABLE_SESSION_FILTER:", getattr(config, "ENABLE_SESSION_FILTER", False))
if getattr(config, "ENABLE_SESSION_FILTER", False):
    print("  SESSION_START_HOUR_UTC:", getattr(config, "SESSION_START_HOUR_UTC", 7))
    print("  SESSION_END_HOUR_UTC:", getattr(config, "SESSION_END_HOUR_UTC", 21))
print()
print("=== M5 TIMEFRAME SETTINGS ===")
m5 = config.TIMEFRAME_SETTINGS.get("M5", {})
for k, v in m5.items():
    print(f"  {k}: {v}")

# Now simulate current live market
print()
print("=== LIVE MARKET STATE ===")
import json, os
market_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_state.json")
if os.path.exists(market_path):
    with open(market_path) as f:
        ms = json.load(f)
    print("trend_label:", ms.get("trend_label"))
    print("candle_color:", ms.get("candle_color"))
    print("ema_9_angle:", ms.get("ema_9_angle"))
    print("ema_21_angle:", ms.get("ema_21_angle"))
    print("atr_14:", ms.get("atr_14"))
    print("velocity:", ms.get("velocity"))
    print("avg_velocity:", ms.get("avg_velocity"))
    print("block_reason:", ms.get("block_reason"))
    print("buy_score:", ms.get("buy_score"))
    print("sell_score:", ms.get("sell_score"))
    print("seconds_into_candle:", ms.get("seconds_into_candle"))
    print("spread:", ms.get("spread"))
else:
    print("market_state.json not found — bot not running")
