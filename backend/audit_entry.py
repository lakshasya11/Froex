import MetaTrader5 as mt5
import time, json, os, collections, math
import config

mt5.initialize()
symbol = getattr(config, "SYMBOL", "XAUUSD")
tf_str = getattr(config, "TIMEFRAME", "M5")
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30}
tf = TF_MAP.get(tf_str, mt5.TIMEFRAME_M5)

print("=" * 65)
print(f"  FULL ENTRY CONDITION AUDIT — {symbol} {tf_str}")
print("=" * 65)

# ── 1. Market Data
tick = mt5.symbol_info_tick(symbol)
rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
sym = mt5.symbol_info(symbol)
print(f"\n[1] MARKET DATA")
print(f"    bid={tick.bid:.2f}  ask={tick.ask:.2f}  spread={tick.ask-tick.bid:.3f} pts")
spread_ok = (tick.ask - tick.bid) <= getattr(config, "SPREAD_ALLOWANCE", 0.20)
print(f"    SPREAD_ALLOWANCE={getattr(config,'SPREAD_ALLOWANCE',0.20)} → {'✅ PASS' if spread_ok else '❌ FAIL (BLOCKING ENTRY)'}")

# ── 2. Candle timing
import pandas as pd
df = pd.DataFrame(rates)
current_candle = df.iloc[-1]
last_closed    = df.iloc[-2]
candle_open_time = int(current_candle["time"])
seconds_into = int(tick.time) - candle_open_time
tf_secs = {"M1":60,"M5":300,"M15":900,"M30":1800}.get(tf_str, 300)
start_w = 5
end_w   = tf_secs - 10
print(f"\n[2] CANDLE TIMING ({tf_str}={tf_secs}s)")
print(f"    seconds_into_candle={seconds_into}s  window=[{start_w}s – {end_w}s]")
time_ok = start_w <= seconds_into < end_w
print(f"    → {'✅ PASS' if time_ok else '❌ FAIL (BLOCKING ENTRY)'}")

# ── 3. EMA
close_series = df["close"]
ema9  = close_series.ewm(span=9,  adjust=False).mean()
ema21 = close_series.ewm(span=21, adjust=False).mean()
e9  = float(ema9.iloc[-1])
e21 = float(ema21.iloc[-1])
e9_prev  = float(ema9.iloc[-2])
e21_prev = float(ema21.iloc[-2])
lb = 3
e9_lb  = float(ema9.iloc[-(lb+1)])
e21_lb = float(ema21.iloc[-(lb+1)])
e9_angle  = math.degrees(math.atan((e9 - e9_lb) / lb))
e21_angle = math.degrees(math.atan((e21 - e21_lb) / lb))
ema_gap = abs(e9 - e21)
print(f"\n[3] EMA ALIGNMENT")
print(f"    EMA9={e9:.3f}  EMA21={e21:.3f}  gap={ema_gap:.3f}pts")
print(f"    EMA9_angle={e9_angle:+.1f}°  EMA21_angle={e21_angle:+.1f}°")
trend = "UP" if e9 > e21 else "DOWN" if e9 < e21 else "FLAT"
print(f"    EMA trend: {trend}")

ema_gap_ok = ema_gap >= getattr(config, "MIN_EMA_GAP_PTS", 0.35)
ema9_angle_ok = abs(e9_angle) >= getattr(config, "EMA_ANGLE_THRESHOLD", 8.0)
ema21_angle_ok = abs(e21_angle) >= getattr(config, "EMA21_ANGLE_THRESHOLD", 4.0)
print(f"    MIN_EMA_GAP={getattr(config,'MIN_EMA_GAP_PTS',0.35)} → {'✅' if ema_gap_ok else '❌ FAIL'}")
print(f"    EMA9_ANGLE_THRESHOLD={getattr(config,'EMA_ANGLE_THRESHOLD',8.0)} → {'✅' if ema9_angle_ok else '❌ FAIL'}")
print(f"    EMA21_ANGLE_THRESHOLD={getattr(config,'EMA21_ANGLE_THRESHOLD',4.0)} → {'✅' if ema21_angle_ok else '❌ FAIL'}")

# ── 4. ATR
high = df["high"].astype(float)
low  = df["low"].astype(float)
close= df["close"].astype(float)
prev_close = close.shift(1)
tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
atr14 = float(tr.ewm(span=14, adjust=False).mean().iloc[-1])
atr_ok = atr14 >= getattr(config, "MIN_ATR_THRESHOLD", 1.20)
print(f"\n[4] VOLATILITY")
print(f"    ATR(14)={atr14:.3f}  MIN_ATR={getattr(config,'MIN_ATR_THRESHOLD',1.20)}")
print(f"    → {'✅ PASS' if atr_ok else '❌ FAIL (BLOCKING ENTRY)'}")

# ── 5. Candle structure
curr_open  = float(current_candle["open"])
curr_high  = float(current_candle["high"])
curr_low   = float(current_candle["low"])
curr_price = tick.bid
curr_body  = abs(curr_price - curr_open)
candle_color = "GREEN" if curr_price > curr_open else "RED" if curr_price < curr_open else "UNKNOWN"
dist_high = curr_high - curr_price
dist_low  = curr_price - curr_low
print(f"\n[5] CANDLE STRUCTURE")
print(f"    open={curr_open:.2f}  high={curr_high:.2f}  low={curr_low:.2f}  bid={curr_price:.2f}")
print(f"    color={candle_color}  body={curr_body:.3f}pts")
print(f"    dist_to_high={dist_high:.3f}  dist_to_low={dist_low:.3f}")
body_ok = curr_body >= getattr(config, "MIN_BODY_SIZE", 0.10)
print(f"    MIN_BODY_SIZE={getattr(config,'MIN_BODY_SIZE',0.10)} → {'✅' if body_ok else '❌ FAIL'}")
at_high_ok = dist_high <= 0.05
at_low_ok  = dist_low  <= 0.05
if candle_color == "GREEN":
    print(f"    BUY needs price at candle HIGH (dist≤0.05) → {'✅ PASS' if at_high_ok else f'❌ FAIL  dist={dist_high:.3f}'}")
elif candle_color == "RED":
    print(f"    SELL needs price at candle LOW (dist≤0.05) → {'✅ PASS' if at_low_ok else f'❌ FAIL  dist={dist_low:.3f}'}")

# ── 6. Velocity (simulate 3s of data)
print(f"\n[6] VELOCITY (reading from market_state.json)")
ms_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_state.json")
if os.path.exists(ms_path):
    with open(ms_path) as f:
        ms = json.load(f)
    vel     = ms.get("velocity", 0)
    avg_vel = ms.get("avg_velocity", 0)
    vel_ok  = abs(vel) >= getattr(config, "ENTRY_VEL_FRESH", 0.05)
    avg_ok  = abs(avg_vel) >= getattr(config, "ENTRY_AVG_FRESH", 0.03)
    print(f"    velocity={vel:+.4f}  ENTRY_VEL_FRESH={getattr(config,'ENTRY_VEL_FRESH',0.05)} → {'✅ PASS' if vel_ok else '❌ FAIL'}")
    print(f"    avg_velocity={avg_vel:+.4f}  ENTRY_AVG_FRESH={getattr(config,'ENTRY_AVG_FRESH',0.03)} → {'✅ PASS' if avg_ok else '❌ FAIL'}")
    print(f"    block_reason from bot: {ms.get('block_reason','N/A')}")
else:
    print("    market_state.json not found — bot not running!")

# ── 7. Session / Daily limits
print(f"\n[7] SESSION / DAILY LIMITS")
session_on = getattr(config, "ENABLE_SESSION_FILTER", False)
print(f"    ENABLE_SESSION_FILTER={session_on}")
if session_on:
    from datetime import datetime, timezone
    utc_h = datetime.now(timezone.utc).hour
    s_start = getattr(config, "SESSION_START_HOUR_UTC", 7)
    s_end   = getattr(config, "SESSION_END_HOUR_UTC", 21)
    sess_ok = s_start <= utc_h < s_end
    print(f"    UTC hour={utc_h}  window={s_start}–{s_end} → {'✅ PASS' if sess_ok else '❌ FAIL (OUTSIDE SESSION)'}")

# ── 8. Summary
print(f"\n{'='*65}")
print(f"  SUMMARY")
print(f"{'='*65}")

checks = {
    "Spread OK":         spread_ok,
    "Candle Time OK":    time_ok,
    "EMA Gap OK":        ema_gap_ok,
    "EMA9 Angle OK":     ema9_angle_ok,
    "EMA21 Angle OK":    ema21_angle_ok,
    "ATR OK":            atr_ok,
    "Body Size OK":      body_ok,
}
for name, ok in checks.items():
    print(f"  {'✅' if ok else '❌'} {name}")

failures = [n for n, ok in checks.items() if not ok]
if not failures:
    print(f"\n  ✅ All structural checks PASS — entry should fire on next momentum spike!")
else:
    print(f"\n  ❌ {len(failures)} check(s) FAILING → bot will NOT enter until fixed")
    for f in failures:
        print(f"     → {f}")
