import sys
import MetaTrader5 as mt5
import config
from indicators import TechnicalIndicators

def main():
    if len(sys.argv) < 2:
        print("Usage: python manual.py buy [count] [lot_size]")
        print("Example: python manual.py buy 1 0.20")
        return

    direction = sys.argv[1].upper()
    if direction not in ["BUY", "SELL"]:
        print("❌ Invalid direction. Use 'buy' or 'sell'.")
        return

    num_trades = 1
    if len(sys.argv) >= 3:
        try:
            num_trades = int(sys.argv[2])
        except ValueError:
            print("❌ Invalid number of trades. Using 1.")
            num_trades = 1

    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        return

    symbol = "XAUUSD"
    volume = getattr(config, 'LOT_SIZE', 0.10)
    if len(sys.argv) >= 4:
        try:
            volume = float(sys.argv[3])
        except ValueError:
            print(f"❌ Invalid lot size. Using default: {volume}")
    
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"❌ Failed to get live price for {symbol}")
        mt5.shutdown()
        return

    price = tick.ask if direction == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    
    symbol_info = mt5.symbol_info(symbol)
    type_filling = 0
    tick_size = 0.01
    digits = 2
    if symbol_info:
        filling_mode = symbol_info.filling_mode
        if filling_mode & 1:   type_filling = 0
        elif filling_mode & 2: type_filling = 1
        else:                  type_filling = 2
        tick_size = symbol_info.trade_tick_size if symbol_info.trade_tick_size > 0 else 0.01
        digits = symbol_info.digits

    dynamic_tp = getattr(config, 'TP_MODERATE', 3.00)
    risk_pts   = getattr(config, 'HARD_STOP_LOSS', 2.00)
    
    if getattr(config, 'ENABLE_DYNAMIC_SL_TP', False):
        analysis = TechnicalIndicators.analyze_basic_timeframe(symbol, mt5.TIMEFRAME_M5, bars=100)
        atr_50 = analysis.get('atr_50', 2.50)
        if atr_50 > 0:
            dynamic_tp = max(dynamic_tp, atr_50 * getattr(config, 'DYNAMIC_TP_BASE_MULTIPLIER', 2.0))
            calc_sl = atr_50 * getattr(config, 'DYNAMIC_SL_ATR_MULTIPLIER', 1.5)
            min_sl = getattr(config, 'MIN_DYNAMIC_SL', 2.00)
            max_sl = getattr(config, 'MAX_DYNAMIC_SL', 8.00)
            risk_pts = max(min_sl, min(calc_sl, max_sl))

    risk_pts = min(risk_pts, round(dynamic_tp * getattr(config, 'MAX_RISK_TO_TP_RATIO', 1.0), 2))

    # User requested exactly 10.00 points SL for manual trades by default
    risk_pts = 10.00
    
    # Override from UI/CLI if provided
    if len(sys.argv) >= 5:
        try:
            risk_pts = float(sys.argv[4])
        except ValueError:
            pass
            
    if len(sys.argv) >= 6:
        try:
            dynamic_tp = float(sys.argv[5])
        except ValueError:
            pass
    hard_sl = round(
        round((price - risk_pts if direction == "BUY" else price + risk_pts) / tick_size) * tick_size,
        digits
    )

    broker_tp = round(
        round((price + dynamic_tp if direction == "BUY" else price - dynamic_tp) / tick_size) * tick_size,
        digits
    )

    if symbol_info:
        min_dist = round(
            (symbol_info.trade_stops_level * symbol_info.point) + (symbol_info.point * 15),
            digits
        )
        if direction == "BUY":
            sl_limit = round(price - min_dist, digits)
            tp_limit = round(price + min_dist, digits)
            if hard_sl != 0.0 and hard_sl > sl_limit: hard_sl = sl_limit
            if broker_tp != 0.0 and broker_tp < tp_limit: broker_tp = tp_limit
        else:
            sl_limit = round(price + min_dist, digits)
            tp_limit = round(price - min_dist, digits)
            if hard_sl != 0.0 and hard_sl < sl_limit: hard_sl = sl_limit
            if broker_tp != 0.0 and broker_tp > tp_limit: broker_tp = tp_limit

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": hard_sl,
        "tp": broker_tp,
        "magic": 123456,
        "comment": f"MANUAL_{direction}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }
    
    print(f"⏳ Sending {num_trades} MANUAL {direction}(s) for {volume} {symbol} @ {price:.2f}...")
    
    for i in range(num_trades):
        result = mt5.order_send(request)
        if result is None:
            print(f"❌ Order {i+1} failed: mt5.order_send returned None")
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order {i+1} failed! MT5 Retcode: {result.retcode}")
        else:
            print(f"✅ MANUAL {direction} {i+1}/{num_trades} PLACED! (Ticket: {result.order})")
            
    print(">> Look at your main bot terminal — it should instantly detect this and apply the Trailing SL!")
    mt5.shutdown()

if __name__ == "__main__":
    main()
