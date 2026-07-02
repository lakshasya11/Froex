import MetaTrader5 as mt5
import time
import config
from datetime import datetime, timezone
from config import (
    ENTRY_VEL_FRESH, ENTRY_AVG_FRESH,
    MAX_ENTRY_SLIPPAGE,
    MIN_ENTRY_2S_VEL,
    TP_ULTRA_STRONG, TP_STRONG, TP_MODERATE,
    MAX_RISK_TO_TP_RATIO, HARD_STOP_LOSS,
    MAX_CONFIRMATION_DRIFT,
    MAX_DAILY_TRADES,
    MAX_TRADES_PER_CANDLE,
    MAX_LOSSES_PER_CANDLE,
    ENTRY_CONFIRM_TICKS,
    MIN_BODY_SIZE
)


class EntryMixin:



    def check_entry_conditions(self, tick, analysis, positions):
        if not tick or not analysis: return "NONE", "NONE"

        velocity = analysis.get('velocity', 0.0)

        if self.trades_this_candle >= MAX_TRADES_PER_CANDLE:
            self.entry_block_reasons["MAX_TRADES_PER_CANDLE"] += 1
            return "NONE", "NONE"

        if getattr(self, 'losses_this_candle', 0) >= MAX_LOSSES_PER_CANDLE:
            if self.loop_count % 60 == 0:
                self.log(f"🚫 LOSS_LIMIT_CANDLE ({self.losses_this_candle}/{MAX_LOSSES_PER_CANDLE}) — wait next candle", self.Colors.ORANGE)
            self.entry_block_reasons["LOSS_LIMIT_CANDLE"] += 1
            return "NONE", "NONE"

        # FIX #6: Consecutive loss pause — block entries after hitting MAX_CONSEC_LOSSES
        if getattr(self, 'candles_to_pause', 0) > 0:
            if self.loop_count % 60 == 0:
                self.log(f"🚫 CONSEC_LOSS_PAUSE ({self.candles_to_pause} candles remaining) — too many consecutive losses", self.Colors.ORANGE)
            self.entry_block_reasons["CONSEC_LOSS_PAUSE"] += 1
            return "NONE", "NONE"

        # --- DAILY TRADE LIMIT ---
        if getattr(self, 'total_trades_today', 0) >= MAX_DAILY_TRADES:
            if self.loop_count % 60 == 0:
                self.log(f"🚫 DAILY_LIMIT ({self.total_trades_today}/{MAX_DAILY_TRADES})", self.Colors.ORANGE)
            self.entry_block_reasons["DAILY_LIMIT"] += 1
            return "NONE", "NONE"

        if getattr(self, 'final_guard_blocks_this_candle', 0) >= 3:
            self.entry_block_reasons["FINAL_GUARD_PAUSE"] += 1
            return "NONE", "NONE"

        candle_open_time = analysis.get('time', 0)
        seconds_into_candle = int(tick.time) - int(candle_open_time) if candle_open_time else 0

        # --- CANDLE TIMING BLOCKS ---
        if seconds_into_candle < getattr(config, 'CANDLE_ENTRY_START', 10):
            if self.loop_count % 15 == 0:
                self.log(f"🚫 CANDLE_ENTRY_START (wait: {seconds_into_candle}s < {getattr(config, 'CANDLE_ENTRY_START', 10)}s)", self.Colors.ORANGE)
            self.entry_block_reasons["CANDLE_ENTRY_START"] = self.entry_block_reasons.get("CANDLE_ENTRY_START", 0) + 1
            return "NONE", "NONE"

        if seconds_into_candle > getattr(config, 'CANDLE_ENTRY_END', 280):
            if self.loop_count % 15 == 0:
                self.log(f"🚫 CANDLE_ENTRY_END (blocked: {seconds_into_candle}s > {getattr(config, 'CANDLE_ENTRY_END', 280)}s)", self.Colors.ORANGE)
            self.entry_block_reasons["CANDLE_ENTRY_END"] = self.entry_block_reasons.get("CANDLE_ENTRY_END", 0) + 1
            return "NONE", "NONE"

        # ── BOLLINGER BANDS ANGLE PROTECTION ──
        # Block ALL entries when the market is not trending strongly enough.
        _bb_ang      = analysis.get('bb_angle', 0.0)
        _bb_bw       = analysis.get('bb_bandwidth', 0.0)
        _bb_mid      = analysis.get('bb_mid', 0.0)
        
        min_bb_ang = getattr(config, 'MIN_BB_ANGLE_ENTRY', 15.0)

        # Reversal, Structure, and Early Open bypasses have been completely removed
        # per the user's strict 5-rule entry requirement.


        instant_velocity = velocity
        avg_velocity     = analysis.get('avg_velocity')
        velocity_2s      = analysis.get('velocity_2s', 0.0)
        velocity_2s_ready = analysis.get('velocity_2s_ready', False)
        curr_color       = analysis.get('candle_color', 'UNKNOWN')
        current_open     = analysis.get('open', tick.bid)
        prev_body_high   = analysis.get('prev_body_high', 0.0)
        prev_body_low    = analysis.get('prev_body_low', float('inf'))
        st_dir           = analysis.get('st_direction', 0)

        _vel_req = ENTRY_VEL_FRESH
        _avg_req = ENTRY_AVG_FRESH
        _2s_req = MIN_ENTRY_2S_VEL

        # --- DYNAMIC VELOCITY SCALING ---
        if getattr(config, 'ENABLE_DYNAMIC_VELOCITY', False):
            atr_50 = analysis.get('atr_50', getattr(config, 'DYNAMIC_VELOCITY_BASE_ATR', 2.50))
            base_atr = getattr(config, 'DYNAMIC_VELOCITY_BASE_ATR', 2.50)
            multiplier = getattr(config, 'DYNAMIC_VELOCITY_MULTIPLIER', 1.20)
            if base_atr > 0:
                scale_factor = (atr_50 / base_atr) * multiplier
                _vel_req = max(ENTRY_VEL_FRESH, round(ENTRY_VEL_FRESH * scale_factor, 3))
                _avg_req = max(ENTRY_AVG_FRESH, round(ENTRY_AVG_FRESH * scale_factor, 3))
                _2s_req  = max(MIN_ENTRY_2S_VEL, round(MIN_ENTRY_2S_VEL * scale_factor, 3))

        _confirm_req = ENTRY_CONFIRM_TICKS

        # Initialise flags before the side-specific filters run.
        buy_conditions_met = sell_conditions_met = False
        _entry_type = "VELOCITY_PULSE"
        curr_body = abs(tick.bid - current_open)

        if positions and len(positions) >= self.max_simultaneous:
            if self.loop_count % 15 == 0:
                self.log(f"🚫 MAX_POSITIONS ({len(positions)}/{self.max_simultaneous})", self.Colors.ORANGE)
            self.entry_block_reasons["MAX_POSITIONS"] += 1
            return "NONE", "NONE"

        if getattr(self, 'is_executing', False):
            self.entry_block_reasons["IS_EXECUTING"] += 1
            return "NONE", "NONE"

        if instant_velocity >= _vel_req:
            avg_velocity_ok = avg_velocity is not None and avg_velocity >= _avg_req
            if st_dir != 1:
                if self.loop_count % 15 == 0:
                    self.log("🚫 ST_DIRECTION_BLOCK — BUY requires BULL trend", self.Colors.ORANGE)
                self.entry_block_reasons["ST_DIRECTION_BLOCK"] = self.entry_block_reasons.get("ST_DIRECTION_BLOCK", 0) + 1
            elif curr_color != 'GREEN':
                if self.loop_count % 15 == 0:
                    self.log(f"🚫 BUY_COLOR_BLOCK ({curr_color}) — BUY requires GREEN candle", self.Colors.ORANGE)
                self.entry_block_reasons["CANDLE_COLOR_MISMATCH"] += 1
            elif curr_body < MIN_BODY_SIZE:
                if self.loop_count % 15 == 0:
                    self.log(f"🚫 MIN_BODY_BLOCK (body:{curr_body:.2f} < {MIN_BODY_SIZE})", self.Colors.ORANGE)
                self.entry_block_reasons["MIN_BODY_BLOCK"] = self.entry_block_reasons.get("MIN_BODY_BLOCK", 0) + 1
            elif not velocity_2s_ready:
                if self.loop_count % 15 == 0:
                    self.log("🚫 PRICE_2S_NOT_READY", self.Colors.ORANGE)
                self.entry_block_reasons["PRICE_2S_NOT_READY"] += 1
            elif velocity_2s < _2s_req:
                if self.loop_count % 15 == 0:
                    self.log(f"🚫 BUY REJECTED | 2s vel:{velocity_2s:+.2f} < +{_2s_req:.2f}", self.Colors.ORANGE)
                self.entry_block_reasons["PRICE_NOT_RISING"] += 1
            elif not avg_velocity_ok:
                self.log(f"🚫 FAKE_SPIKE_AVG_VEL (avg={avg_velocity:+.2f})", self.Colors.ORANGE)
                self.entry_block_reasons["FAKE_SPIKE_AVG_VEL"] += 1
            else:
                self.log(f"✅ BUY SETUP | 2s:{velocity_2s:+.2f} req:+{_2s_req:.2f}", self.Colors.GREEN)
                buy_conditions_met = True

        if instant_velocity <= -_vel_req:
            avg_velocity_ok = avg_velocity is not None and avg_velocity <= -_avg_req
            if st_dir != -1:
                if self.loop_count % 15 == 0:
                    self.log("🚫 ST_DIRECTION_BLOCK — SELL requires BEAR trend", self.Colors.ORANGE)
                self.entry_block_reasons["ST_DIRECTION_BLOCK"] = self.entry_block_reasons.get("ST_DIRECTION_BLOCK", 0) + 1
            elif curr_color != 'RED':
                if self.loop_count % 15 == 0:
                    self.log(f"\U0001f6ab SELL_COLOR_BLOCK ({curr_color}) \u2014 SELL requires RED candle", self.Colors.ORANGE)
                self.entry_block_reasons["CANDLE_COLOR_MISMATCH"] += 1
            elif curr_body < MIN_BODY_SIZE:
                if self.loop_count % 15 == 0:
                    self.log(f"🚫 MIN_BODY_BLOCK (body:{curr_body:.2f} < {MIN_BODY_SIZE})", self.Colors.ORANGE)
                self.entry_block_reasons["MIN_BODY_BLOCK"] = self.entry_block_reasons.get("MIN_BODY_BLOCK", 0) + 1
            elif not velocity_2s_ready:
                if self.loop_count % 15 == 0:
                    self.log("🚫 PRICE_2S_NOT_READY", self.Colors.ORANGE)
                self.entry_block_reasons["PRICE_2S_NOT_READY"] += 1
            elif velocity_2s > -_2s_req:
                if self.loop_count % 15 == 0:
                    self.log(f"🚫 SELL REJECTED | 2s vel:{velocity_2s:+.2f} > -{_2s_req:.2f}", self.Colors.ORANGE)
                self.entry_block_reasons["PRICE_NOT_FALLING"] += 1
            elif not avg_velocity_ok:
                self.log(f"🚫 FAKE_SPIKE_AVG_VEL (avg={avg_velocity:+.2f})", self.Colors.ORANGE)
                self.entry_block_reasons["FAKE_SPIKE_AVG_VEL"] += 1
            else:
                self.log(f"✅ SELL SETUP | 2s:{velocity_2s:+.2f} req:-{_2s_req:.2f}", self.Colors.GREEN)
                sell_conditions_met = True


        buy_trigger = sell_trigger = False

        # --- INDEPENDENT DRIFT-PROTECTED TICK CONFIRMATION ---
        # To prevent entering on a 1-tick anomaly, the bot requires multiple consecutive ticks (ENTRY_CONFIRM_TICKS)
        # where all conditions remain true. If the price drifts too far during this confirmation window (MAX_CONFIRMATION_DRIFT),
        # the setup is cancelled to prevent late entries.
        if buy_conditions_met:
            self.buy_confirm_count += 1
            if self.buy_confirm_count == 1:
                self.buy_first_confirm_price = tick.ask
            if self.buy_confirm_count >= _confirm_req:
                drift = tick.ask - getattr(self, 'buy_first_confirm_price', tick.ask)
                if abs(drift) > MAX_CONFIRMATION_DRIFT:
                    self.log(f"🚫 BUY CONFIRM DRIFTED TOO FAR ({drift:+.2f} > {MAX_CONFIRMATION_DRIFT}) | Resetting", self.Colors.ORANGE)
                    self.buy_confirm_count = 0
                else:
                    buy_trigger = True
                    self.log(f"✅ BUY CONFIRMED ({self.buy_confirm_count} ticks, Drift: {drift:.2f})", self.Colors.GREEN)
            else:
                self.log(f"⏳ BUY Confirming... (Tick {self.buy_confirm_count}/{_confirm_req} @ {tick.ask:.2f})", self.Colors.YELLOW)
        else:
            if self.buy_confirm_count:
                self.log(f"🚫 BUY CONFIRM_RESET — setup lost", self.Colors.ORANGE)
            self.buy_confirm_count = 0

        if sell_conditions_met:
            self.sell_confirm_count += 1
            if self.sell_confirm_count == 1:
                self.sell_first_confirm_price = tick.bid
            if self.sell_confirm_count >= _confirm_req:
                drift = getattr(self, 'sell_first_confirm_price', tick.bid) - tick.bid
                if abs(drift) > MAX_CONFIRMATION_DRIFT:
                    self.log(f"🚫 SELL CONFIRM DRIFTED TOO FAR ({drift:+.2f} > {MAX_CONFIRMATION_DRIFT}) | Resetting", self.Colors.ORANGE)
                    self.sell_confirm_count = 0
                else:
                    sell_trigger = True
                    self.log(f"✅ SELL CONFIRMED ({self.sell_confirm_count} ticks, Drift: {drift:.2f})", self.Colors.MAGENTA)
            else:
                self.log(f"⏳ SELL Confirming... (Tick {self.sell_confirm_count}/{_confirm_req} @ {tick.bid:.2f})", self.Colors.YELLOW)
        else:
            if self.sell_confirm_count:
                self.log(f"🚫 SELL CONFIRM_RESET — setup lost", self.Colors.ORANGE)
            self.sell_confirm_count = 0

        if buy_trigger or sell_trigger:
            signal    = "BUY" if buy_trigger else "SELL"
            curr_body = abs(tick.bid - analysis.get('open', tick.bid))
            prev_body = analysis.get('prev_body', 0.0)
            avg_str   = f"{avg_velocity:+.2f}" if avg_velocity is not None else "N/A"
            color     = self.Colors.GREEN if buy_trigger else self.Colors.MAGENTA
            self.log(f"🚀 [TRIGGER] {signal} ({_entry_type}) | Body: {prev_body:.2f}→{curr_body:.2f} | Vel:{velocity:+.2f} | Avg:{avg_str}", color)
            if buy_trigger:  self.buy_confirm_count = 0;  self.buy_first_confirm_price = None
            if sell_trigger: self.sell_confirm_count = 0; self.sell_first_confirm_price = None
            return signal, _entry_type

        return "NONE", "NONE"

    def execute_entry(self, signal, tick, analysis, entry_type=""):
        if self.is_executing: return False
        if self.trades_this_candle >= getattr(config, 'MAX_TRADES_PER_CANDLE', 5):
            self.entry_block_reasons["MAX_TRADES_PER_CANDLE"] += 1
            self.log(f"🚫 MAX_TRADES_PER_CANDLE ({self.trades_this_candle}/{getattr(config, 'MAX_TRADES_PER_CANDLE', 5)})", self.Colors.ORANGE)
            return False
        self.is_executing = True
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.log("Failed to get symbol info", self.Colors.RED)
                return False

            fresh_tick = mt5.symbol_info_tick(self.symbol)
            if fresh_tick: tick = fresh_tick

            # Final live guard — positions may have changed since check_entry_conditions ran
            live_positions = mt5.positions_get(symbol=self.symbol)
            live_count = len(live_positions) if live_positions else 0
            if live_count >= self.max_simultaneous:
                self.log(f"🚫 ENTRY ABORTED — live positions ({live_count}) >= max ({self.max_simultaneous})", self.Colors.ORANGE)
                return False

            entry_price = tick.ask if signal == "BUY" else tick.bid
            
            from config import LOT_SIZE
            volume = LOT_SIZE
            self.log(f"⚖️ Lot Size: {volume:.2f}", self.Colors.CYAN)

            spread      = tick.ask - tick.bid
            order_type  = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

            if spread > 0.40:
                self.log(f"🚫 WIDE SPREAD ({spread:.2f}) — skipping entry", self.Colors.ORANGE)
                return False

            filling_mode = symbol_info.filling_mode
            if filling_mode & 1:   type_filling = 0
            elif filling_mode & 2: type_filling = 1
            else:                  type_filling = 2

            tick_size = symbol_info.trade_tick_size

            entry_vel = analysis.get('velocity', 0.0)
            abs_vel   = abs(entry_vel)

            # --- DYNAMIC TP / SL SCALING ---
            _base_tp_mod = TP_MODERATE
            _base_tp_str = TP_STRONG
            _base_tp_ult = TP_ULTRA_STRONG
            _base_sl_cap = HARD_STOP_LOSS
            
            if getattr(config, 'ENABLE_DYNAMIC_SL_TP', False):
                atr_50 = analysis.get('atr_50', 2.50)
                if atr_50 > 0:
                    _base_tp_mod = max(TP_MODERATE, atr_50 * getattr(config, 'DYNAMIC_TP_BASE_MULTIPLIER', 2.0))
                    _base_tp_str = max(TP_STRONG, _base_tp_mod * 1.5)
                    _base_tp_ult = max(TP_ULTRA_STRONG, _base_tp_mod * 2.0)
                    
                    calc_sl = atr_50 * getattr(config, 'DYNAMIC_SL_ATR_MULTIPLIER', 1.5)
                    min_sl = getattr(config, 'MIN_DYNAMIC_SL', 2.00)
                    max_sl = getattr(config, 'MAX_DYNAMIC_SL', 8.00)
                    _base_sl_cap = max(min_sl, min(calc_sl, max_sl))

            entry_type = entry_type or analysis.get('last_entry_type', '')
            if entry_type in ["REVERSAL_HAMMER", "REVERSAL_SHOOTING_STAR"]:
                dynamic_tp = _base_tp_str
                tp_label = "REVERSAL"
                self.log(f"🎯 REVERSAL OVERRIDE: Forcing TP_STRONG ({dynamic_tp:.2f} pts)", self.Colors.GREEN)
            elif abs_vel >= 1.00:
                dynamic_tp = _base_tp_ult
                tp_label = "ULTRA"
            elif abs_vel >= 0.70:
                dynamic_tp = _base_tp_str
                tp_label = "STRONG"
            else:
                dynamic_tp = _base_tp_mod
                tp_label = "MODERATE"

            self.log(f"📊 Dynamic TP: {dynamic_tp} pts [{tp_label}] (vel: {entry_vel:+.2f})", self.Colors.CYAN)

            send_tick = mt5.symbol_info_tick(self.symbol)
            if send_tick:
                tick = send_tick
                entry_price = tick.ask if signal == "BUY" else tick.bid

            current_open = analysis.get('open', tick.bid)
            live_body = tick.bid - current_open
            live_color = 'GREEN' if live_body > 0 else 'RED' if live_body < 0 else 'UNKNOWN'
            prev_body_high = analysis.get('prev_body_high', 0.0)
            prev_body_low = analysis.get('prev_body_low', float('inf'))
            live_higher = tick.bid > prev_body_high if prev_body_high else analysis.get('is_higher', False)
            live_lower = tick.bid < prev_body_low if prev_body_low < float('inf') else analysis.get('is_lower', False)

            if signal == "BUY" and (live_color != 'GREEN' or not live_higher):
                self.entry_block_reasons["FINAL_DIRECTION_GUARD"] += 1
                self.log(
                    f"🚫 FINAL BUY GUARD — color:{live_color} higher:{live_higher}",
                    self.Colors.ORANGE
                )
                self.buy_confirm_count = 0
                self.buy_first_confirm_price = None
                self.final_guard_blocks_this_candle = getattr(self, 'final_guard_blocks_this_candle', 0) + 1
                return False

            if signal == "SELL" and (live_color != 'RED' or not live_lower):
                self.entry_block_reasons["FINAL_DIRECTION_GUARD"] += 1
                self.log(
                    f"🚫 FINAL SELL GUARD — color:{live_color} lower:{live_lower}",
                    self.Colors.ORANGE
                )
                self.sell_confirm_count = 0
                self.sell_first_confirm_price = None
                self.final_guard_blocks_this_candle = getattr(self, 'final_guard_blocks_this_candle', 0) + 1
                return False

            risk_pts = min(_base_sl_cap, round(dynamic_tp * MAX_RISK_TO_TP_RATIO, 2))
            hard_sl = round(
                round((entry_price - risk_pts if signal == "BUY" else entry_price + risk_pts) / tick_size) * tick_size,
                symbol_info.digits
            )
            broker_tp = round(
                round((entry_price + dynamic_tp if signal == "BUY" else entry_price - dynamic_tp) / tick_size) * tick_size,
                symbol_info.digits
            )

            # ── BROKER STOPS-LEVEL ENFORCEMENT ──
            # Broker requires SL & TP to be at least (trade_stops_level * point) away
            # from entry. If our calculated values are too close, clamp them outward.
            # Winprofx XAUUSD: stops_level=50, point=0.01 → min dist = 0.50 pts
            min_dist = round(
                (symbol_info.trade_stops_level * symbol_info.point) + (symbol_info.point * 15),
                symbol_info.digits
            )  # +15 pts buffer on top of minimum to avoid edge rejections
            if signal == "BUY":
                sl_limit = round(entry_price - min_dist, symbol_info.digits)
                tp_limit = round(entry_price + min_dist, symbol_info.digits)
                if hard_sl > sl_limit:          # SL too close above limit → push down
                    self.log(f"⚠️ SL {hard_sl:.2f} too close — clamped to broker min {sl_limit:.2f} (dist:{min_dist:.2f})", self.Colors.YELLOW)
                    hard_sl = sl_limit
                if broker_tp < tp_limit:        # TP too close below limit → push up
                    self.log(f"⚠️ TP {broker_tp:.2f} too close — clamped to broker min {tp_limit:.2f} (dist:{min_dist:.2f})", self.Colors.YELLOW)
                    broker_tp = tp_limit
            else:  # SELL
                sl_limit = round(entry_price + min_dist, symbol_info.digits)
                tp_limit = round(entry_price - min_dist, symbol_info.digits)
                if hard_sl < sl_limit:          # SL too close below limit → push up
                    self.log(f"⚠️ SL {hard_sl:.2f} too close — clamped to broker min {sl_limit:.2f} (dist:{min_dist:.2f})", self.Colors.YELLOW)
                    hard_sl = sl_limit
                if broker_tp > tp_limit:        # TP too close above limit → push down
                    self.log(f"⚠️ TP {broker_tp:.2f} too close — clamped to broker min {tp_limit:.2f} (dist:{min_dist:.2f})", self.Colors.YELLOW)
                    broker_tp = tp_limit

            self.log(f"🛡 HARD SL: {hard_sl:.2f} ({risk_pts:.2f} pts) | TP: {broker_tp:.2f} (target:{dynamic_tp:.2f}) | BrokerMin:{min_dist:.2f}", self.Colors.CYAN)

            request = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": self.symbol,
                "volume": volume, "type": order_type, "price": entry_price,
                "sl": hard_sl, "tp": broker_tp, "magic": 123456,
                "comment": f"{signal}_HardSL", "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }
            if not mt5.terminal_info() or not mt5.terminal_info().connected:
                from connection import MT5Connection
                if not MT5Connection.initialize_mt5():
                    self.log("❌ ORDER ABORTED — MT5 disconnected", self.Colors.RED)
                    return False

            result = mt5.order_send(request)
            if result is None:
                err = mt5.last_error()
                self.log(f"❌ ORDER FAILED — mt5.order_send returned None | MT5 error: {err}", self.Colors.RED)
                time.sleep(0.3)
                result = mt5.order_send(request)

            if result and result.retcode == 10016:
                self.entry_block_reasons["INVALID_STOPS"] += 1
                self.log("🚫 INVALID_STOPS from broker — entry skipped", self.Colors.ORANGE)
                return False

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.total_trades += 1
                self.trades_this_candle += 1

                if result.price:
                    fill_slippage = abs(result.price - entry_price)
                    if fill_slippage >= MAX_ENTRY_SLIPPAGE:
                        self.log(f"⚠️ HIGH SLIPPAGE {fill_slippage:+.2f} — allowing trade to run", self.Colors.ORANGE)
                    entry_price = result.price

                now_entry = time.time()
                self.formatter.print_tick_context("PRE-ENTRY", [t for t in self.pre_entry_ticks if t['time'] >= now_entry - 1.0], signal)

                conditions = f"Type: {analysis.get('last_entry_type','N/A')} | V: {analysis.get('velocity',0.0):+.2f} | PB: {analysis.get('prev_body',0.0):.2f}"
                try:
                    self.formatter.print_trade_entry(signal, entry_price, volume, hard_sl, broker_tp,
                        result.order, conditions, self.session_capital, self.total_trades, risk_pts)
                except Exception:
                    self.log(f"📋 TRADE: {signal} @ {entry_price:.2f} | SL:{hard_sl:.2f}", self.Colors.CYAN)

                actual_ticket = result.order
                unified_pos_data = {
                    'entry_price': entry_price, 'initial_sl': hard_sl, 'initial_tp': broker_tp,
                    'entry_time': datetime.now(timezone.utc), 'entry_candle_time': analysis.get('time'),
                    'direction': signal, 'volume': volume, 'entry_velocity': entry_vel,
                    'initial_tp_pts': dynamic_tp, 'peak_profit': 0.0, 'trail_sl_price': None,
                    'hard_sl_price': hard_sl, 'entry_type': entry_type,
                }
                self.position_data[actual_ticket] = unified_pos_data
                return True
            else:
                self.log(f"❌ ORDER FAILED: {result.comment if result else 'Unknown'} (Retcode: {result.retcode if result else 'N/A'})", self.Colors.RED)
                return False

        except Exception as e:
            self.log(f"❌ Error executing trade: {e}", self.Colors.RED)
            return False
        finally:
            self.is_executing = False

    def _modify_sl(self, pos, new_sl_price):
        guard = getattr(self, '_sl_modify_in_progress', None)
        if guard is not None:
            if pos.ticket in guard:
                return False
            guard.add(pos.ticket)
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            tick = mt5.symbol_info_tick(self.symbol)
            if not symbol_info or not tick: return False

            tick_size = symbol_info.trade_tick_size
            digits    = symbol_info.digits
            safe_dist = symbol_info.trade_stops_level * symbol_info.point + symbol_info.point * 8

            sl_rounded = round(round(new_sl_price / tick_size) * tick_size, digits)

            # Fetch live position to get current broker SL — pos is a stale snapshot
            live_positions = mt5.positions_get(ticket=pos.ticket)
            live_pos = live_positions[0] if live_positions else pos
            current_broker_sl = float(live_pos.sl or 0.0)
            current_broker_tp = float(live_pos.tp or 0.0)

            # Never move SL in the wrong direction
            if current_broker_sl != 0:
                if pos.type == mt5.POSITION_TYPE_BUY  and sl_rounded <= current_broker_sl: return False
                if pos.type == mt5.POSITION_TYPE_SELL and sl_rounded >= current_broker_sl: return False

            # Clamp to broker's minimum distance for the broker request only.
            # Software SL (caller's trail_sl_price) is set before this call and is not affected.
            broker_sl = sl_rounded
            if pos.type == mt5.POSITION_TYPE_BUY:
                max_allowed = tick.bid - safe_dist
                if broker_sl > max_allowed:
                    broker_sl = round(round(max_allowed / tick_size) * tick_size, digits)
            else:
                min_allowed = tick.ask + safe_dist
                if broker_sl < min_allowed:
                    broker_sl = round(round(min_allowed / tick_size) * tick_size, digits)

            # ── BACKWARDS-MOVE GUARD (after clamping) ──
            # Clamping uses live price, so when price reverses the clamped value
            # can push the broker SL backwards (up for SELL, down for BUY).
            # If that happens, skip the broker update — software SL still tracks correctly.
            if current_broker_sl != 0:
                if pos.type == mt5.POSITION_TYPE_BUY  and broker_sl <= current_broker_sl:
                    return sl_rounded   # skip broker update, software SL still advances
                if pos.type == mt5.POSITION_TYPE_SELL and broker_sl >= current_broker_sl:
                    return sl_rounded   # skip broker update, software SL still advances

            # Already at or better — skip broker call
            if current_broker_sl != 0 and abs(broker_sl - current_broker_sl) < (tick_size * 0.5):
                return sl_rounded  # software SL still advances even if broker SL doesn't move


            result = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": self.symbol,
                                     "position": pos.ticket, "sl": broker_sl, "tp": current_broker_tp})
            if result and result.retcode in [mt5.TRADE_RETCODE_DONE, 10025]:
                return sl_rounded  # return intended value, not broker-clamped value
            ret_code = result.retcode if result else "N/A"
            if ret_code == 10016:
                self.log("⚠️ BROKER SL too close (10016) — software SL active", self.Colors.YELLOW)
                return sl_rounded  # software SL still tracks correctly
            elif ret_code not in [10025, 10036]:
                self.log(f"❌ BROKER REJECTED TRAIL SL: {result.comment if result else 'Error'} (Code:{ret_code})", self.Colors.RED)
            return sl_rounded  # always advance software SL regardless of broker response
        except Exception as e:
            self.log(f"❌ SL Modify Exception: {e}", self.Colors.RED)
            return False
        finally:
            if guard is not None:
                guard.discard(pos.ticket)
