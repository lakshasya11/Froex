import sys
import MetaTrader5 as mt5


def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_exit.py [ticket]")
        return

    try:
        ticket = int(sys.argv[1])
    except ValueError:
        print("❌ Invalid ticket")
        return

    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        return

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        print(f"❌ Position with ticket {ticket} not found")
        mt5.shutdown()
        return

    pos = positions[0]
    symbol_info = mt5.symbol_info(pos.symbol)
    tick = mt5.symbol_info_tick(pos.symbol)

    if not symbol_info or not tick:
        print(f"⚠️ Cannot close {ticket}: missing data.")
        mt5.shutdown()
        return

    filling_mode = symbol_info.filling_mode
    type_filling = 0 if filling_mode & 1 else 1

    price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
    order_type = (
        mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    )

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": pos.ticket,
        "price": price,
        "magic": pos.magic,
        "comment": "MANUAL_EXIT",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }

    print(f"⏳ Sending MANUAL EXIT for ticket {ticket}...")
    result = mt5.order_send(request)

    if result is None:
        print("⚠️ Close attempt failed. Retrying alternate filling mode...")
        request["type_filling"] = 1 if type_filling != 1 else 0
        result = mt5.order_send(request)

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ MANUAL EXIT PLACED! (Ticket: {ticket})")
    else:
        retcode = result.retcode if result else "N/A"
        print(f"❌ CLOSE CRITICAL FAILURE | Ticket:{ticket} | Code:{retcode}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
