import MetaTrader5 as mt5
import time
import collections

mt5.initialize()
symbol = 'XAUUSD'

price_history = collections.deque(maxlen=25)
velocity_buffer = collections.deque(maxlen=10)  # NEW: 10 ticks

alpha = 0.4  # EWMA alpha

print("Live velocity test (8 seconds) — comparing OLD vs NEW avg_velocity\n")
print(f"{'Tick':>4} | {'Bid':>8} | {'Velocity':>10} | {'OLD (mean)':>11} | {'NEW (EWMA)':>11} | Threshold?")
print("-" * 75)

simple_buf = collections.deque(maxlen=10)

for i in range(8):
    tick = mt5.symbol_info_tick(symbol)
    now = time.time()
    price_history.append((now, tick.bid))

    cutoff = now - 8
    while price_history and price_history[0][0] < cutoff:
        price_history.popleft()

    price_1s = None
    for t, p in reversed(price_history):
        if t <= now - 1.0:
            price_1s = p
            break

    price_2s = None
    for t, p in reversed(price_history):
        if t <= now - 2.0:
            price_2s = p
            break

    oldest = price_history[0][1] if price_history else None
    if price_1s is None:
        price_1s = oldest

    if price_1s is not None and price_2s is not None:
        velocity_2s = tick.bid - price_2s
        smooth_velocity = ((tick.bid - price_1s) + velocity_2s / 2.0) / 2.0
    elif price_1s is not None:
        smooth_velocity = tick.bid - price_1s
    else:
        smooth_velocity = 0.0

    # OLD: simple mean
    simple_buf.append(smooth_velocity)
    old_avg = sum(simple_buf) / len(simple_buf) if len(simple_buf) >= 3 else None

    # NEW: EWMA
    velocity_buffer.append(smooth_velocity)
    v_list = list(velocity_buffer)
    if len(v_list) >= 3:
        ewma = v_list[0]
        for v in v_list[1:]:
            ewma = alpha * v + (1 - alpha) * ewma
        new_avg = ewma
    else:
        new_avg = None

    old_str = f"{old_avg:+.4f}" if old_avg is not None else "   N/A"
    new_str = f"{new_avg:+.4f}" if new_avg is not None else "   N/A"

    threshold = 0.03
    old_pass = abs(old_avg) >= threshold if old_avg is not None else False
    new_pass = abs(new_avg) >= threshold if new_avg is not None else False
    pass_str = f"OLD={'PASS' if old_pass else 'FAIL'}  NEW={'PASS' if new_pass else 'FAIL'}"

    print(f"  [{i+1}] | {tick.bid:>8.2f} | {smooth_velocity:>+10.4f} | {old_str:>11} | {new_str:>11} | {pass_str}")
    time.sleep(1)

print()
print("ENTRY_AVG_FRESH threshold = 0.03 pts")
print("ENTRY_VEL_FRESH threshold = 0.05 pts")
