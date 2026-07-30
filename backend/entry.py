import MetaTrader5 as mt5
import time
import config
from datetime import datetime, timezone


class EntryMixin:
    """
    Mixin class that provides the entry logic for the trading bot.
    It evaluates market ticks against a set of strict criteria (guards) to determine if a new trade should be opened.
    """

    def normalize_volume(self, symbol_info, volume: float) -> float:
        """
        Normalizes and clamps the volume (lot size) according to the broker's step size, minimum, and maximum limits.
        """
        step = symbol_info.volume_step
        vol = round(round(volume / step) * step, 2)
        return max(symbol_info.volume_min, min(symbol_info.volume_max, vol))

    def check_entry_conditions(self, tick, analysis, positions):
        """
        Evaluates the current market tick and technical analysis to determine if a BUY or SELL signal is present.

        Args:
            tick: The current tick from MetaTrader 5 containing bid/ask prices and time.
            analysis: A dictionary containing pre-calculated technical indicators (e.g., Bollinger Bands, Supertrend, Velocity).
            positions: A list of currently open positions.

        Returns:
            tuple: (entry_signal, entry_type, score) where entry_signal is "BUY", "SELL", or "NONE".
                   entry_type describes the reason for the entry (e.g., "Standard", "Re-entry").
                   score is the momentum score object if a signal is generated, else None.
            """
        if not tick or not analysis:
            return "NONE", "NONE", None

        # Prevent re-entering at the exact same price zone after a loss
        last_trade = getattr(self, "last_trade_history", None)
        if last_trade and last_trade.get("profit_points", 0) < 0:
            last_entry = last_trade.get("entry_price")
            if last_entry is not None:
                min_re_entry_dist = self.strategy.get_setting("RE_ENTRY_DISTANCE", 0.50)
                if abs(tick.bid - last_entry) < min_re_entry_dist: # Must move away
                    if getattr(self, "loop_count", 0) % 60 == 0:
                        self.log(f"RE_ENTRY_GUARD: Price too close to last loss ({last_entry:.2f})", self.Colors.ORANGE)
                    self.entry_block_reasons["RE_ENTRY_GUARD"] = self.entry_block_reasons.get("RE_ENTRY_GUARD", 0) + 1
                    return "NONE", "NONE", None

        # --- BROKER SYNC COOLDOWN ---
        # Prevent analyzing new setups for 2 seconds after a trade fires.
        # This gives MT5 time to update positions_get(), preventing the engine from starting
        # a new confirmation loop for a trade that is already executing.

        cooldown_secs = self.strategy.get_setting("EXECUTION_COOLDOWN_SECS", 2.0)
        if time.time() - getattr(self, "_last_signal_time", 0) < cooldown_secs:
            return "NONE", "NONE", None
            
        if time.time() - getattr(self, "_last_exit_time", 0) < cooldown_secs:
            return "NONE", "NONE", None

        # GUARD: First 5 seconds AND last N seconds of candle — no entries allowed on any timeframe
        candle_open_time = analysis.get("time", 0)
        seconds_into_candle = (int(tick.time) - int(candle_open_time)) if candle_open_time else 0
        tf_duration_map = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800}
        tf_secs = tf_duration_map.get(getattr(self, "timeframe", "M5"), 300)
        start_block_secs = self.strategy.get_setting("CANDLE_START_BLOCK_SECS", 5)
        end_block_secs = self.strategy.get_setting("CANDLE_END_BLOCK_SECS", 5 if getattr(self, "timeframe", "M1") == "M1" else 10)
        if seconds_into_candle < start_block_secs:
            self.entry_block_reasons["CANDLE_ENTRY_START"] = self.entry_block_reasons.get("CANDLE_ENTRY_START", 0) + 1
            return "NONE", "NONE", None
        if seconds_into_candle > (tf_secs - end_block_secs):
            self.entry_block_reasons["CANDLE_ENTRY_END"] = self.entry_block_reasons.get("CANDLE_ENTRY_END", 0) + 1
            return "NONE", "NONE", None

        # GUARD: Sideway Trend Block
        # Allow entry if last_trend is UP or DOWN, OR if two consecutive candles are aligned (RED+RED or GREEN+GREEN)
        # NEW LOGIC: If colors are opposite, check if the current body engulfs (is larger than) the previous body.
        curr_color = analysis.get("candle_color", "UNKNOWN")
        prev_color = analysis.get("prev_color", "UNKNOWN")
        is_pullback_setup = (curr_color == "RED" and prev_color == "RED") or (curr_color == "GREEN" and prev_color == "GREEN")

        is_engulfing_trend = False
        if not is_pullback_setup:
            curr_body = analysis.get("current_body_size", 0.0)
            prev_body = analysis.get("prev_body", 0.0)
            if curr_body > prev_body:
                is_engulfing_trend = True

        if getattr(self, "last_trend", "NONE") == "NONE" and not is_pullback_setup and not is_engulfing_trend:
            if getattr(self, "loop_count", 0) % 60 == 0:
                self.log("SIDEWAY_TREND_GUARD: Waiting for established trend", self.Colors.ORANGE)
            self.entry_block_reasons["SIDEWAY_TREND"] = self.entry_block_reasons.get("SIDEWAY_TREND", 0) + 1
            return "NONE", "NONE", None

        # GUARD: Prevent over-trading by capping the total number of entries per single candle
        if self.trades_this_candle >= getattr(self, "max_trades_candle", 6):
            self.entry_block_reasons["MAX_TRADES_PER_CANDLE"] += 1
            return "NONE", "NONE", None

        # GUARD: Hard stop if we hit the maximum allowed losses in a single candle
        max_losses_candle = self.strategy.get_setting("MAX_LOSSES_PER_CANDLE", 2)
        if getattr(self, "losses_this_candle", 0) >= max_losses_candle:
            if self.loop_count % 60 == 0:
                self.log(
                    f"LOSS_LIMIT_CANDLE ({self.losses_this_candle}/{max_losses_candle}) — wait next candle",
                    self.Colors.ORANGE,
                )
            self.entry_block_reasons["LOSS_LIMIT_CANDLE"] += 1
            return "NONE", "NONE", None

        # Block entries if consecutive loss limit is reached
        if getattr(self, "candles_to_pause", 0) > 0:
            if self.loop_count % 60 == 0:
                self.log(
                    f"CONSEC_LOSS_PAUSE ({self.candles_to_pause} candles remaining) — too many consecutive losses",
                    self.Colors.ORANGE,
                )
            self.entry_block_reasons["CONSEC_LOSS_PAUSE"] += 1
            return "NONE", "NONE", None

        # --- DAILY PROFIT TARGET ---
        daily_target = self.strategy.get_setting("DAILY_PROFIT_TARGET", 500.0)
        if getattr(self, "today_profit", 0.0) >= daily_target:
            if self.loop_count % 30 == 0:
                self.log(
                    f"DAILY_PROFIT_TARGET REACHED (${getattr(self, 'today_profit', 0.0):.2f} / ${daily_target:.2f})",
                    self.Colors.GREEN,
                )
            self.entry_block_reasons["DAILY_PROFIT_TARGET"] += 1
            return "NONE", "NONE", None

        # --- DAILY TRADE LIMIT ---
        max_daily_trades = self.strategy.get_setting("MAX_DAILY_TRADES", 6)
        if getattr(self, "total_trades_today", 0) >= max_daily_trades:
            if self.loop_count % 30 == 0:
                self.log(
                    f"DAILY_LIMIT ({self.total_trades_today}/{max_daily_trades})",
                    self.Colors.ORANGE,
                )
            self.entry_block_reasons["DAILY_LIMIT"] += 1
            return "NONE", "NONE", None

        # Filter active positions matching this symbol
        live_positions = [p for p in positions if p.symbol == self.symbol]
        live_count = len(live_positions)
        
        # Split positions by direction
        buy_positions = [p for p in live_positions if p.type == mt5.POSITION_TYPE_BUY]
        sell_positions = [p for p in live_positions if p.type == mt5.POSITION_TYPE_SELL]
        
        # --- TIME OVERRIDES ---
        tf_settings = getattr(config, "TIMEFRAME_SETTINGS", {}).get(
            getattr(self, "timeframe", "M5"),
            getattr(config, "TIMEFRAME_SETTINGS", {}).get("M5", {}),
        )
        max_allowed_buy = tf_settings.get("MAX_TRADES_CANDLE", 3)
        max_allowed_sell = tf_settings.get("MAX_TRADES_CANDLE", 3)
        
        # If scale-in exists, we handle positioning differently.
        # Check active trades count to ensure we don't breach max cap.
        max_positions = self.strategy.get_setting("MAX_SIMULTANEOUS_POSITIONS", 1)
        if live_count >= max_positions:
            # We check if scale-in is possible
            if getattr(config, "ENABLE_SCALE_IN", False) and live_count == 1 and not self.scaled_in_tickets:
                parent_pos = live_positions[0]
                parent_ticket = parent_pos.ticket
                if parent_ticket in self.position_data:
                    parent_data = self.position_data[parent_ticket]
                    parent_profit = parent_data.get("last_profit_pts", 0.0)
                    if parent_profit >= getattr(config, "SCALE_IN_TRIGGER_PTS", 1.00):
                        # Proceed to check scale-in
                        self.execute_scale_in(parent_pos, parent_data, tick, live_count, analysis)
                        return "NONE", "NONE", None
            
            # Standard block
            if self.loop_count % 60 == 0:
                self.log(
                    f"MAX_POSITIONS REACHED ({live_count}/{max_positions})",
                    self.Colors.YELLOW,
                )
            self.entry_block_reasons["MAX_POSITIONS"] += 1
            return "NONE", "NONE", None

        # --- EVALUATE STRATEGY SCORES ---
        buy_score = self.strategy.calculate_momentum_score("BUY", tick, analysis, {})
        sell_score = self.strategy.calculate_momentum_score("SELL", tick, analysis, {})

        # Update analysis logs for DB/Dashboard visibility
        analysis["buy_score_total"] = buy_score.total
        analysis["sell_score_total"] = sell_score.total

        # Log rejects to the DB (sampled to prevent excessive logging)
        for direction, s_obj in [("BUY", buy_score), ("SELL", sell_score)]:
            if s_obj.block_reason:
                # Log to DB if this is a fresh setup or loop_count is high
                if self.loop_count % 40 == 0:
                    setup_log = {
                        "candle_time": str(analysis.get("time", "")),
                        "direction": direction,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "score_momentum": s_obj.momentum,
                        "score_trend": s_obj.trend,
                        "score_candle": s_obj.candle,
                        "score_execution": s_obj.execution,
                        "score_total": s_obj.total,
                        "reject_reason": s_obj.block_reason,
                        "decision_stage": (
                            "PASSED" if not s_obj.block_reason else "REJECTED"
                        ),
                        "trade_executed": 0,
                        "ticket": None,
                        "instant_velocity": analysis.get("velocity", 0.0),
                        "velocity_2s": analysis.get("velocity_2s", 0.0),
                        "strategy_version": getattr(
                            config, "STRATEGY_VERSION", "unknown"
                        ),
                    }
                    self.db.log_evaluated_setup(setup_log)

        buy_threshold = buy_score.required_score
        sell_threshold = sell_score.required_score

        if live_count >= max_allowed_buy and not buy_score.block_reason:
            buy_score.block_reason = "MAX_POSITIONS"

        if live_count >= max_allowed_sell and not sell_score.block_reason:
            sell_score.block_reason = "MAX_POSITIONS"

        buy_conditions_met = False
        if buy_score and not buy_score.block_reason:
            buy_conditions_met = True
        elif buy_score and buy_score.block_reason:
            self.entry_block_reasons[buy_score.block_reason] = (
                self.entry_block_reasons.get(buy_score.block_reason, 0) + 1
            )

        sell_conditions_met = False
        if sell_score and not sell_score.block_reason:
            sell_conditions_met = True
        elif sell_score and sell_score.block_reason:
            if sell_score.block_reason == "FAKE_SPIKE_AVG_VEL":
                pass
            self.entry_block_reasons[sell_score.block_reason] = (
                self.entry_block_reasons.get(sell_score.block_reason, 0) + 1
            )

        _entry_type = "PULLBACK"
        _confirm_req = self.strategy.get_setting("ENTRY_CONFIRM_TICKS", 2)

        # Determine final signal
        buy_trigger = buy_conditions_met
        sell_trigger = sell_conditions_met

        # Log details on success triggers
        if buy_trigger or sell_trigger:
            signal = "BUY" if buy_trigger else "SELL"
            avg_velocity = analysis.get("avg_velocity")
            avg_str = f"{avg_velocity:+.2f}" if avg_velocity is not None else "N/A"
            self.log(
                f"[TRIGGER] {signal} ({_entry_type}) | Body: {analysis.get('prev_body', 0.0):.2f}→{abs(tick.bid - (analysis.get('open') or tick.bid)):.2f} | Vel:{analysis.get('velocity', 0.0):+.2f} | Avg:{avg_str}",
                self.Colors.CYAN,
            )
            if buy_trigger:
                self.buy_confirm_count = 0
            if sell_trigger:
                self.sell_confirm_count = 0
            return signal, _entry_type, (buy_score if buy_trigger else sell_score)

        return "NONE", "NONE", None

    def execute_entry(self, signal, tick, analysis, entry_type="", score=None):
        if self.is_executing:
            return False
        if self.trades_this_candle >= getattr(self, "max_trades_candle", 6):
            self.entry_block_reasons["MAX_TRADES_PER_CANDLE"] += 1
            self.log(
                f"MAX_TRADES_PER_CANDLE ({self.trades_this_candle}/{getattr(self, 'max_trades_candle', 6)})",
                self.Colors.ORANGE,
            )
            return False
        self.is_executing = True
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.log("Failed to get symbol info", self.Colors.RED)
                return False

            fresh_tick = mt5.symbol_info_tick(self.symbol)
            if fresh_tick:
                tick = fresh_tick

            # Final live guard — positions may have changed since check_entry_conditions ran
            live_positions = mt5.positions_get(symbol=self.symbol)
            live_count = len(live_positions) if live_positions else 0

            max_allowed = self.strategy.get_setting("MAX_SIMULTANEOUS_POSITIONS", 1)

            if live_count >= max_allowed:
                self.log(
                    f"ENTRY ABORTED — live positions ({live_count}) >= max_allowed ({max_allowed})",
                    self.Colors.ORANGE,
                )
                return False

            entry_price = tick.ask if signal == "BUY" else tick.bid

            _ema_9 = analysis.get("ema_9")
            _ema_21 = analysis.get("ema_21")
            is_pullback = False
            if _ema_9 is not None and _ema_21 is not None:
                if signal == "BUY" and _ema_9 <= _ema_21:
                    is_pullback = True
                elif signal == "SELL" and _ema_9 >= _ema_21:
                    is_pullback = True

            base_volume = self.strategy.get_setting("LOT_SIZE", 0.10)
            volume = self.normalize_volume(symbol_info, base_volume)
            self.log(f"Lot Size (Standard): {volume:.2f}", self.Colors.CYAN)

            order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

            # Double check spread allowance
            max_spread = self.strategy.get_setting("SPREAD_ALLOWANCE", 0.20)
            if hasattr(tick, "ask") and hasattr(tick, "bid"):
                spread = round(tick.ask - tick.bid, 5)
                if spread > max_spread:
                    self.log(
                        f"WIDE SPREAD ({spread:.2f} > {max_spread:.2f}) — skipping entry",
                        self.Colors.ORANGE,
                    )
                    return False

            filling_mode = symbol_info.filling_mode
            if filling_mode & 1:
                type_filling = 0
            elif filling_mode & 2:
                type_filling = 1
            else:
                type_filling = 2

            tick_size = symbol_info.trade_tick_size

            entry_vel = analysis.get("velocity", 0.0)
            abs_vel = abs(entry_vel)

            # --- DYNAMIC TP / SL SCALING ---
            tf_settings = getattr(config, "TIMEFRAME_SETTINGS", {}).get(
                getattr(self, "timeframe", "M5"),
                getattr(config, "TIMEFRAME_SETTINGS", {}).get("M5", {}),
            )
            cfg_tp_mod = tf_settings.get("TP_MODERATE", 3.00)
            cfg_tp_str = tf_settings.get("TP_STRONG", 5.00)
            cfg_tp_ult = tf_settings.get("TP_ULTRA_STRONG", 8.00)
            cfg_hard_sl = tf_settings.get("HARD_STOP_LOSS", 2.00)

            _base_tp_mod = cfg_tp_mod
            _base_tp_str = cfg_tp_str
            _base_tp_ult = cfg_tp_ult
            _base_sl_cap = cfg_hard_sl

            enable_dynamic_sl_tp = self.strategy.get_setting("ENABLE_DYNAMIC_SL_TP", False)
            if enable_dynamic_sl_tp:
                atr_50 = analysis.get("atr_50", 2.50)
                if atr_50 > 0:
                    tp_base_mult = self.strategy.get_setting("DYNAMIC_TP_BASE_MULTIPLIER", 2.0)
                    _base_tp_mod = max(
                        cfg_tp_mod,
                        atr_50 * tp_base_mult,
                    )
                    _base_tp_str = max(cfg_tp_str, _base_tp_mod * 1.5)
                    _base_tp_ult = max(cfg_tp_ult, _base_tp_mod * 2.0)

                    sl_atr_mult = self.strategy.get_setting("DYNAMIC_SL_ATR_MULTIPLIER", 1.5)
                    calc_sl = atr_50 * sl_atr_mult
                    min_sl = self.strategy.get_setting("MIN_DYNAMIC_SL", 2.00)
                    max_sl = self.strategy.get_setting("MAX_DYNAMIC_SL", 8.00)
                    _base_sl_cap = max(min_sl, min(calc_sl, max_sl))

            entry_type = entry_type or analysis.get("last_entry_type", "")
            if entry_type in ["REVERSAL_HAMMER", "REVERSAL_SHOOTING_STAR"]:
                dynamic_tp = _base_tp_str
                tp_label = "REVERSAL"
                self.log(
                    f"🎯 REVERSAL OVERRIDE: Forcing TP_STRONG ({dynamic_tp:.2f} pts)",
                    self.Colors.GREEN,
                )
            elif abs_vel >= 1.00:
                dynamic_tp = _base_tp_ult
                tp_label = "ULTRA"
            elif abs_vel >= 0.70:
                dynamic_tp = _base_tp_str
                tp_label = "STRONG"
            else:
                dynamic_tp = _base_tp_mod
                tp_label = "MODERATE"

            self.log(
                f"Dynamic TP: {dynamic_tp} pts [{tp_label}] (vel: {entry_vel:+.2f})",
                self.Colors.CYAN,
            )

            send_tick = mt5.symbol_info_tick(self.symbol)
            if send_tick:
                tick = send_tick
                entry_price = tick.ask if signal == "BUY" else tick.bid

            current_open = analysis.get("open") or tick.bid
            live_body = tick.bid - current_open
            live_color = (
                "GREEN" if live_body > 0 else "RED" if live_body < 0 else "UNKNOWN"
            )

            # Use HARD_STOP_LOSS from config directly — fixed SL distance always
            risk_pts = round(_base_sl_cap, 2)  # e.g. 2.00 pts for M5
            hard_sl = round(
                round(
                    (
                        entry_price - risk_pts
                        if signal == "BUY"
                        else entry_price + risk_pts
                    )
                    / tick_size
                )
                * tick_size,
                symbol_info.digits,
            )
            broker_tp = round(
                round(
                    (
                        entry_price + dynamic_tp
                        if signal == "BUY"
                        else entry_price - dynamic_tp
                    )
                    / tick_size
                )
                * tick_size,
                symbol_info.digits,
            )

            # ── BROKER STOPS-LEVEL ENFORCEMENT ──
            # Broker requires SL & TP to be at least (trade_stops_level * point) away
            # from entry. If our calculated values are too close, clamp them outward.
            min_dist = round(
                (symbol_info.trade_stops_level * symbol_info.point)
                + (symbol_info.point * 2),
                symbol_info.digits,
            )  # +2 pts buffer on top of minimum to avoid edge rejections
            if signal == "BUY":
                sl_limit = round(
                    round((entry_price - min_dist) / tick_size) * tick_size,
                    symbol_info.digits,
                )
                tp_limit = round(
                    round((entry_price + min_dist) / tick_size) * tick_size,
                    symbol_info.digits,
                )
                if hard_sl > sl_limit:  # SL too close above limit → push down
                    self.log(
                        f"⚠️ SL {hard_sl:.2f} too close — clamped to broker min {sl_limit:.2f} (dist:{min_dist:.2f})",
                        self.Colors.YELLOW,
                    )
                    hard_sl = sl_limit
                if broker_tp < tp_limit:  # TP too close below limit → push up
                    self.log(
                        f"⚠️ TP {broker_tp:.2f} too close — clamped to broker min {tp_limit:.2f} (dist:{min_dist:.2f})",
                        self.Colors.YELLOW,
                    )
                    broker_tp = tp_limit
            else:  # SELL
                sl_limit = round(
                    round((entry_price + min_dist) / tick_size) * tick_size,
                    symbol_info.digits,
                )
                tp_limit = round(
                    round((entry_price - min_dist) / tick_size) * tick_size,
                    symbol_info.digits,
                )
                if hard_sl < sl_limit:  # SL too close below limit → push up
                    self.log(
                        f"⚠️ SL {hard_sl:.2f} too close — clamped to broker min {sl_limit:.2f} (dist:{min_dist:.2f})",
                        self.Colors.YELLOW,
                    )
                    hard_sl = sl_limit
                if broker_tp > tp_limit:  # TP too close above limit → push down
                    self.log(
                        f"⚠️ TP {broker_tp:.2f} too close — clamped to broker min {tp_limit:.2f} (dist:{min_dist:.2f})",
                        self.Colors.YELLOW,
                    )
                    broker_tp = tp_limit

            self.log(
                f"HARD SL: {hard_sl:.2f} ({risk_pts:.2f} pts) | TP: {broker_tp:.2f} (target:{dynamic_tp:.2f}) | BrokerMin:{min_dist:.2f}",
                self.Colors.CYAN,
            )

            max_slippage = self.strategy.get_setting("MAX_ENTRY_SLIPPAGE", 0.20)
            comment_str = f"{signal}_Pullback" if is_pullback else f"{signal}_HardSL"
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": entry_price,
                "sl": hard_sl,
                "tp": broker_tp,
                "magic": getattr(self, "magic", 123456),
                "deviation": int(max_slippage / symbol_info.point),
                "comment": comment_str,
                "type_time": mt5.ORDER_TIME_GTC,
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
                self.log(
                    f"❌ ORDER FAILED — mt5.order_send returned None | MT5 error: {err}",
                    self.Colors.RED,
                )
                time.sleep(0.3)
                result = mt5.order_send(request)

            if result and result.retcode == 10016:
                self.entry_block_reasons["INVALID_STOPS"] += 1
                self.log(
                    "INVALID_STOPS from broker — entry skipped", self.Colors.ORANGE
                )
                return False

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.total_trades += 1
                self.trades_this_candle += 1

                if getattr(self, "db", None) and score:
                    strat_ver = self.strategy.get_setting("STRATEGY_VERSION", "unknown")
                    setup_log = {
                        "candle_time": str(analysis.get("time", "")),
                        "direction": signal,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "score_momentum": score.momentum,
                        "score_trend": score.trend,
                        "score_candle": score.candle,
                        "score_execution": score.execution,
                        "score_total": score.total,
                        "reject_reason": score.block_reason,
                        "decision_stage": "EXECUTED",
                        "trade_executed": 1,
                        "ticket": result.order,
                        "instant_velocity": analysis.get("velocity", 0.0),
                        "velocity_2s": analysis.get("velocity_2s", 0.0),
                        "strategy_version": strat_ver,
                    }
                    self.db.log_evaluated_setup(setup_log)

                if result.price:
                    fill_slippage = abs(result.price - entry_price)
                    if fill_slippage >= max_slippage:
                        self.log(
                            f"⚠️ HIGH SLIPPAGE {fill_slippage:+.2f} — allowing trade to run",
                            self.Colors.ORANGE,
                        )
                    entry_price = result.price

                now_entry = time.time()
                self.formatter.print_tick_context(
                    "PRE-ENTRY",
                    [t for t in self.pre_entry_ticks if t["time"] >= now_entry - 1.0],
                    signal,
                )

                conditions = f"Type: {analysis.get('last_entry_type','N/A')} | V: {analysis.get('velocity',0.0):+.2f} | PB: {analysis.get('prev_body',0.0):.2f}"
                try:
                    self.formatter.print_trade_entry(
                        signal,
                        entry_price,
                        volume,
                        hard_sl,
                        broker_tp,
                        result.order,
                        conditions,
                        self.session_capital,
                        self.total_trades,
                        risk_pts,
                        score=score,
                    )
                except Exception:
                    self.log(
                        f"📋 TRADE: {signal} @ {entry_price:.2f} | SL:{hard_sl:.2f}",
                        self.Colors.CYAN,
                    )

                actual_ticket = result.order
                unified_pos_data = {
                    "entry_price": entry_price,
                    "initial_sl": hard_sl,
                    "initial_tp": broker_tp,
                    "entry_time": datetime.now(timezone.utc),
                    "entry_time_ts": time.time(),
                    "entry_candle_time": analysis.get("time"),
                    "direction": signal,
                    "volume": volume,
                    "entry_velocity": entry_vel,
                    "initial_tp_pts": dynamic_tp,
                    "peak_profit": 0.0,
                    "trail_sl_price": None,
                    "hard_sl_price": hard_sl,
                    "entry_type": entry_type,
                    "is_pullback": is_pullback,
                    "score_momentum": score.momentum if score else 0.0,
                    "score_trend": score.trend if score else 0.0,
                    "score_candle": score.candle if score else 0.0,
                    "score_execution": score.execution if score else 0.0,
                    "score_total": score.total if score else 0.0,
                    "velocity_consistency": score.velocity_avg_change if score else 0.0,
                    "velocity_acceleration": (
                        score.velocity_acceleration if score else 0.0
                    ),
                    "score_acceleration": score.accel_score if score else 0.0,
                    "velocity_std": 0.0,
                    "velocity_mean": 0.0,
                    "mfe": 0.0,
                    "mae": 0.0,
                    "adx_14": analysis.get("adx_14", 0.0),
                    "sideways_score": score.sideways_score if score else 0,
                }
                self.position_data[actual_ticket] = unified_pos_data
                self._last_signal_time = time.time()
                return True
            else:
                self.log(
                    f"❌ ORDER FAILED: {result.comment if result else 'Unknown'} (Retcode: {result.retcode if result else 'N/A'})",
                    self.Colors.RED,
                )
                return False

        except Exception as e:
            self.log(f"❌ Error executing trade: {e}", self.Colors.RED)
            return False
        finally:
            self.is_executing = False

    def _modify_sl(self, pos, new_sl_price):
        guard = getattr(self, "_sl_modify_in_progress", None)
        if guard is not None:
            if pos.ticket in guard:
                return False
            guard.add(pos.ticket)
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            tick = mt5.symbol_info_tick(self.symbol)
            if not symbol_info or not tick:
                return False

            tick_size = symbol_info.trade_tick_size
            digits = symbol_info.digits
            stops_level = symbol_info.trade_stops_level
            if stops_level == 0:
                spread = tick.ask - tick.bid
                safe_dist = spread + (symbol_info.point * 8)
            else:
                safe_dist = (stops_level * symbol_info.point) + (symbol_info.point * 8)

            sl_rounded = round(round(new_sl_price / tick_size) * tick_size, digits)

            # Fetch live position to get current broker SL — pos is a stale snapshot
            live_positions = mt5.positions_get(ticket=pos.ticket)
            live_pos = live_positions[0] if live_positions else pos
            current_broker_sl = float(live_pos.sl or 0.0)
            current_broker_tp = float(live_pos.tp or 0.0)

            # Never move SL in the wrong direction
            if current_broker_sl != 0:
                if (
                    pos.type == mt5.POSITION_TYPE_BUY
                    and sl_rounded <= current_broker_sl
                ):
                    return False
                if (
                    pos.type == mt5.POSITION_TYPE_SELL
                    and sl_rounded >= current_broker_sl
                ):
                    return False

            # Clamp to broker's minimum distance for the broker request only.
            # Software SL (caller's trail_sl_price) is set before this call and is not affected.
            broker_sl = sl_rounded
            if pos.type == mt5.POSITION_TYPE_BUY:
                max_allowed = tick.bid - safe_dist
                if broker_sl > max_allowed:
                    broker_sl = round(
                        round(max_allowed / tick_size) * tick_size, digits
                    )
            else:
                min_allowed = tick.ask + safe_dist
                if broker_sl < min_allowed:
                    broker_sl = round(
                        round(min_allowed / tick_size) * tick_size, digits
                    )

            # ── BACKWARDS-MOVE GUARD (after clamping) ──
            # Clamping uses live price, so when price reverses the clamped value
            # can push the broker SL backwards (up for SELL, down for BUY).
            # If that happens, skip the broker update — software SL still tracks correctly.
            if current_broker_sl != 0:
                if pos.type == mt5.POSITION_TYPE_BUY and broker_sl <= current_broker_sl:
                    return False  # skip broker update, software SL still advances
                if (
                    pos.type == mt5.POSITION_TYPE_SELL
                    and broker_sl >= current_broker_sl
                ):
                    return False  # skip broker update, software SL still advances

            # Already at or better — skip broker call
            if current_broker_sl != 0 and abs(broker_sl - current_broker_sl) < (
                tick_size * 0.5
            ):
                return (
                    False  # software SL still advances even if broker SL doesn't move
                )

            result = mt5.order_send(
                {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": self.symbol,
                    "position": pos.ticket,
                    "sl": broker_sl,
                    "tp": current_broker_tp,
                }
            )
            if result and result.retcode in [mt5.TRADE_RETCODE_DONE, 10025]:
                return sl_rounded  # return intended value, not broker-clamped value
            ret_code = result.retcode if result else "N/A"
            if ret_code == 10016:
                self.log(
                    "⚠️ BROKER SL too close (10016) — software SL active",
                    self.Colors.YELLOW,
                )
                return False  # software SL still tracks correctly
            elif ret_code == 10036:
                self.log(
                    f"⚠️ TRAIL SL IGNORED: Position {pos.ticket} already closed on broker (10036)",
                    self.Colors.YELLOW,
                )
                return False
            elif ret_code != 10025:
                self.log(
                    f"❌ BROKER REJECTED TRAIL SL: {result.comment if result else 'Error'} (Code:{ret_code})",
                    self.Colors.RED,
                )
            return False  # always advance software SL regardless of broker response
        except Exception as e:
            self.log(f"❌ SL Modify Exception: {e}", self.Colors.RED)
            return False
        finally:
            if guard is not None:
                guard.discard(pos.ticket)

    def execute_scale_in(
        self, parent_pos, parent_data, tick, current_live_count, analysis
    ):
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            self.log("Failed to get symbol info for scale-in", self.Colors.RED)
            return False

        scale_vol = self.strategy.get_setting("LOT_SIZE", 0.10)
        scale_vol = self.normalize_volume(symbol_info, scale_vol)
        parent_vol = round(parent_pos.volume, 2)
        signal = "BUY" if parent_pos.type == mt5.ORDER_TYPE_BUY else "SELL"

        self.log(
            f"Scale-In Lot Sizing (Trade {current_live_count + 1}) → Lot: {scale_vol:.2f}",
            self.Colors.CYAN,
        )
        self.log(
            f"SCALE-IN TRIGGERED: {signal} at +1.00 pt profit. Parent Vol:{parent_vol} → Scale Vol:{scale_vol}",
            self.Colors.CYAN,
        )

        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        entry_price = tick.ask if signal == "BUY" else tick.bid
        filling_mode = symbol_info.filling_mode
        if filling_mode & 1:
            type_filling = 0
        elif filling_mode & 2:
            type_filling = 1
        else:
            type_filling = 2

        tick_size = symbol_info.trade_tick_size
        hard_sl = (
            round(
                (entry_price - 2.00 if signal == "BUY" else entry_price + 2.00)
                / tick_size
            )
            * tick_size
        )

        dynamic_tp = parent_data.get("initial_tp_pts", 3.00)
        broker_tp = (
            round(
                (
                    entry_price + dynamic_tp
                    if signal == "BUY"
                    else entry_price - dynamic_tp
                )
                / tick_size
            )
            * tick_size
        )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": scale_vol,
            "type": order_type,
            "price": entry_price,
            "sl": hard_sl,
            "tp": broker_tp,
            "deviation": 20,
            "magic": 234000,
            "comment": "Scale-In",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.log(f"SCALE-IN FAILED: {result.comment}", self.Colors.RED)
            return False

        self.log(
            f"SCALE-IN EXECUTED: {signal} {scale_vol} lots @ {result.price}",
            self.Colors.GREEN,
        )

        self.position_data[result.order] = {
            "entry_time": datetime.now(timezone.utc),
            "direction": signal,
            "entry_price": result.price,
            "initial_sl": hard_sl,
            "hard_sl_price": hard_sl,
            "initial_tp": broker_tp,
            "initial_tp_pts": dynamic_tp,
            "trail_sl_price": None,
            "price_lock_sl_price": None,
            "peak_profit": 0.0,
            "last_profit_pts": 0.0,
            "entry_velocity": parent_data.get("entry_velocity", 0.0),
            "volume": scale_vol,
        }
        self.scaled_in_tickets.add(result.order)  # don't scale-in off a scale-in
        self.trades_this_candle += 1
        return True
