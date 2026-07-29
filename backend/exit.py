import MetaTrader5 as mt5
import time
import config


class ExitMixin:
    """
    Mixin class that provides the exit logic and position management for the trading bot.
    It continuously monitors open positions and applies dynamic stop losses, trailing stops,
    profit locks, take profit targets, and technical crossover exits to manage risk.
    """

    def check_exit_conditions(self, tick, analysis, positions):
        """
        Evaluates open positions against technical indicators and price action to determine
        if any positions should be closed or have their stop-loss levels updated.

        Args:
            tick: The current tick from MetaTrader 5 containing live bid/ask prices.
            analysis: A dictionary containing pre-calculated technical indicators.
            positions: A list of currently open positions retrieved from MetaTrader 5.
        """
        if not positions or not analysis:
            return

        # Extract live EMAs for crossover exit check
        ema_9 = analysis.get("ema_9")
        ema_21 = analysis.get("ema_21")

        # Resolve config parameters via dynamic 3-tier settings lookup
        spread_allowance = self.strategy.get_setting("SPREAD_ALLOWANCE", 0.20)
        trail_modify_min_interval = self.strategy.get_setting("TRAIL_MODIFY_MIN_INTERVAL", 0.2)

        for pos in positions:
            ticket = pos.ticket
            if ticket not in self.position_data:
                self.recover_position_data(pos)

            pos_data = self.position_data[ticket]

            if pos_data.get("_closing", False):
                continue

            direction = pos_data.get("direction")
            entry_price = pos_data.get("entry_price")
            if not entry_price or not direction:
                continue

            symbol_info = mt5.symbol_info(self.symbol)
            tick_size = 0.01
            digits = 2
            if symbol_info:
                tick_size = symbol_info.trade_tick_size
                digits = symbol_info.digits

            current_profit = (
                (tick.bid - entry_price)
                if direction == "BUY"
                else (entry_price - tick.ask)
            )
            tp_pts = pos_data.get("initial_tp_pts", 2.0) - spread_allowance
            pos_data["last_profit_pts"] = current_profit

            if current_profit > (pos_data.get("peak_profit") or 0.0):
                pos_data["peak_profit"] = current_profit
            peak_profit = pos_data.get("peak_profit", 0.0)

            # Track MFE/MAE
            pos_data["mfe"] = max(pos_data.get("mfe", 0.0), current_profit)
            pos_data["mae"] = min(pos_data.get("mae", 0.0), current_profit)

            if pos_data.get("is_manual", False):
                if current_profit >= tp_pts:
                    self.log(f"⚠️ MANUAL TRADE TP HIT #{ticket} | TP={tp_pts:.2f}", self.Colors.GREEN)
                    pos_data["_closing"] = True
                    if not self.close_position(pos, "TP (Manual)"):
                        pos_data["_closing"] = False
                continue

            # ── SYSTEM 1: EMA CROSSOVER EXIT ──
            # Closes the trade if the short-term EMA 9 crosses back over EMA 21 against the trade direction.
            # Bypass this exit if the trade is a counter-trend pullback trade.
            if not pos_data.get("is_pullback", False) and ema_9 is not None and ema_21 is not None:
                ema_cross_exit = False
                if direction == "BUY" and ema_9 < ema_21:
                    ema_cross_exit = True
                    reason_msg = "EMA Cross Exit (EMA 9 < EMA 21)"
                elif direction == "SELL" and ema_9 > ema_21:
                    ema_cross_exit = True
                    reason_msg = "EMA Cross Exit (EMA 9 > EMA 21)"

                if ema_cross_exit:
                    self.log(
                        f"🚨 {reason_msg} #{ticket} | Closing {direction} position",
                        self.Colors.ORANGE,
                    )
                    pos_data["_closing"] = True
                    if not self.close_position(pos, "EMA Cross Exit"):
                        pos_data["_closing"] = False
                    continue

            # ── SYSTEM 2: PROFIT LOCKS (Breakeven System) ──
            locked_sl_price = None

            tf_settings = getattr(config, "TIMEFRAME_SETTINGS", {}).get(
                getattr(self, "timeframe", "M5"),
                getattr(config, "TIMEFRAME_SETTINGS", {}).get("M5", {}),
            )
            cfg_profit_lock_steps = tf_settings.get("PROFIT_LOCK_STEPS", [])
            cfg_trail_trigger = tf_settings.get("TRAIL_TRIGGER_PTS", 1.50)
            cfg_trail_gap = tf_settings.get("TRAIL_GAP_PTS", 0.80)

            for trigger_pts, lock_pts in cfg_profit_lock_steps:
                if peak_profit >= trigger_pts:
                    if direction == "BUY":
                        locked_sl_price = entry_price + lock_pts
                    else:
                        locked_sl_price = entry_price - lock_pts
                    break

            if locked_sl_price is not None:
                lock_price_rounded = round(
                    round(locked_sl_price / tick_size) * tick_size, digits
                )
                prev_lock = pos_data.get("price_lock_sl_price")
                is_valid_ratchet = (
                    prev_lock is None
                    or (direction == "BUY" and lock_price_rounded > prev_lock)
                    or (direction == "SELL" and lock_price_rounded < prev_lock)
                )
                if is_valid_ratchet:
                    pos_data["price_lock_sl_price"] = lock_price_rounded
                    if prev_lock != lock_price_rounded:
                        self.log(
                            f"PROFIT LOCK ENGAGED #{ticket} | Lock SL: {lock_price_rounded:.2f}",
                            self.Colors.CYAN,
                        )
                        self._modify_sl(pos, lock_price_rounded)

            price_lock_sl = pos_data.get("price_lock_sl_price")
            if price_lock_sl is not None:
                lock_hit = (direction == "BUY" and tick.bid <= price_lock_sl) or (
                    direction == "SELL" and tick.ask >= price_lock_sl
                )
                if lock_hit:
                    self.log(
                        f"PRICE LOCK BREACHED #{ticket} | Exiting at {price_lock_sl:.2f}",
                        self.Colors.ORANGE,
                    )
                    pos_data["_closing"] = True
                    if not self.close_position(pos, "Profit Lock"):
                        pos_data["_closing"] = False
                    continue

            # ── SYSTEM 3: HARD STOP LOSS FALLBACK ──
            hard_sl_sw = pos_data.get("hard_sl_price") or pos_data.get("initial_sl")
            if hard_sl_sw is not None and hard_sl_sw != 0.0:
                if (direction == "BUY" and tick.bid <= hard_sl_sw) or (
                    direction == "SELL" and tick.ask >= hard_sl_sw
                ):
                    self.log(
                        f"⚠️ HARD SL HIT #{ticket} (SW) | SL={hard_sl_sw:.2f}",
                        self.Colors.ORANGE,
                    )
                    pos_data["_closing"] = True
                    if not self.close_position(pos, "Hard SL"):
                        pos_data["_closing"] = False
                    continue

            # ── SYSTEM 4: DYNAMIC TAKE PROFIT ──
            if current_profit >= tp_pts:
                self.log(f"TP #{ticket} (+{current_profit:.2f}pts)", self.Colors.GREEN)
                pos_data["_closing"] = True
                if not self.close_position(pos, "Dynamic TP"):
                    pos_data["_closing"] = False
                continue

            # ── SYSTEM 5: VOLATILITY TRAILING STOP ──
            _tp_target = pos_data.get("initial_tp_pts", cfg_trail_trigger)
            _trail_trigger = cfg_trail_trigger
            _trail_gap = cfg_trail_gap

            if peak_profit >= _trail_trigger:
                pos_data["live_trail_active"] = True

            intended = None
            if pos_data.get("live_trail_active", False):
                if not pos_data.get("_trail_logged", False):
                    self.log(
                        f"TRAIL ACTIVE | trigger:{_trail_trigger:.2f} gap:{_trail_gap:.2f} "
                        f"(TP:{_tp_target:.2f} pts)",
                        self.Colors.GREEN,
                    )
                    pos_data["_trail_logged"] = True

                calculated_trail_pts = peak_profit - _trail_gap
                target_price = (
                    (entry_price + calculated_trail_pts)
                    if direction == "BUY"
                    else (entry_price - calculated_trail_pts)
                )
                intended = round(round(target_price / tick_size) * tick_size, digits)

            if intended is not None:
                software_cur = pos_data.get("trail_sl_price")
                is_better = (
                    direction == "BUY"
                    and (software_cur is None or intended > software_cur)
                ) or (
                    direction == "SELL"
                    and (software_cur is None or intended < software_cur)
                )
                if is_better:
                    pos_data["trail_sl_price"] = intended

            trail_sl = pos_data.get("trail_sl_price")

            if trail_sl is not None:
                last_modify = pos_data.get("last_sl_modify_time", 0.0)
                now_t = time.time()
                if (now_t - last_modify) >= trail_modify_min_interval:
                    trail_sl_rounded = round(
                        round(trail_sl / tick_size) * tick_size, digits
                    )

                    _live_pos_list = mt5.positions_get(ticket=pos.ticket)
                    _live_sl = (
                        float(_live_pos_list[0].sl)
                        if _live_pos_list
                        else float(pos.sl or 0)
                    )

                    needs_update = True
                    if _live_sl != 0:
                        if abs(trail_sl_rounded - _live_sl) < (tick_size * 0.5):
                            needs_update = False
                        elif direction == "BUY" and trail_sl_rounded <= _live_sl:
                            needs_update = False
                        elif direction == "SELL" and trail_sl_rounded >= _live_sl:
                            needs_update = False

                    if needs_update:
                        pos_data["last_sl_modify_time"] = now_t
                        actual_sl = self._modify_sl(pos, trail_sl)
                        if actual_sl:
                            last_sent = pos_data.get("last_sent_broker_sl", 0.0)
                            if abs(actual_sl - last_sent) >= (tick_size * 0.5):
                                self.log(
                                    f"TRAIL SL MT5 Sync → {actual_sl:.2f}",
                                    (
                                        self.Colors.CYAN
                                        if direction == "BUY"
                                        else self.Colors.MAGENTA
                                    ),
                                )
                                pos_data["last_sent_broker_sl"] = actual_sl

                if (direction == "BUY" and tick.bid <= trail_sl) or (
                    direction == "SELL" and tick.ask >= trail_sl
                ):
                    self.log(
                        f"⚠️ TRAIL SL HIT #{ticket} | SL={trail_sl:.2f}",
                        self.Colors.ORANGE,
                    )
                    pos_data["_closing"] = True
                    if not self.close_position(pos, "Trailing SL"):
                        pos_data["_closing"] = False
                    continue

    def close_position(self, pos, reason):
        symbol_info = mt5.symbol_info(self.symbol)
        tick = mt5.symbol_info_tick(self.symbol)
        if not symbol_info or not tick:
            self.log(f"⚠️ Cannot close {pos.ticket}: missing data.", self.Colors.YELLOW)
            return False

        exit_comment = f"Ex_{str(reason)[:25]}"[:31]
        self.log(
            f"📤 CLOSE REQUEST | Ticket:{pos.ticket} | Reason:{reason}",
            self.Colors.CYAN,
        )

        filling_mode = symbol_info.filling_mode
        type_filling = 0 if filling_mode & 1 else 1

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": pos.volume,
            "type": (
                mt5.ORDER_TYPE_SELL
                if pos.type == mt5.POSITION_TYPE_BUY
                else mt5.ORDER_TYPE_BUY
            ),
            "position": pos.ticket,
            "price": tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "magic": 123456,
            "comment": exit_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }
        result = mt5.order_send(request)

        if result is None:
            self.log(
                "⚠️ Close attempt failed. Retrying alternate filling mode...",
                self.Colors.YELLOW,
            )
            request["type_filling"] = 1 if type_filling != 1 else 0
            result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.log(
                f"CLOSE SUCCESS | Ticket:{pos.ticket} | Reason:{reason}",
                self.Colors.GREEN,
            )
            if pos.ticket in self.position_data:
                self.position_data[pos.ticket]["exit_reason"] = reason
            return True

        retcode = result.retcode if result else "N/A"
        if retcode in [10036, 10013, 10018]:
            self.log(
                f"Ticket {pos.ticket} already handled by server.", self.Colors.YELLOW
            )
            if pos.ticket in self.position_data:
                self.position_data[pos.ticket]["exit_reason"] = reason
            return True

        self.log(
            f"❌ CLOSE CRITICAL FAILURE | Ticket:{pos.ticket} | Code:{retcode}",
            self.Colors.RED,
        )
        return False
