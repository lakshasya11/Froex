import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import MetaTrader5 as mt5
import time
import os
import json
from datetime import datetime, timezone
import collections
from strategy import EnhancedTradingStrategy
from formatter import TerminalFormatter, Colors
from connection import MT5Connection
from entry import EntryMixin
from exit import ExitMixin
from news import NewsFilter
import config
from config import (
    MAX_SIMULTANEOUS_POSITIONS,
    MAX_LOSSES_PER_CANDLE,
    MAX_CONSEC_LOSSES,
    LOSS_PAUSE_CANDLES,
)

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7
        )
    except OSError:
        pass

os.environ["FORCE_COLOR"] = "1"


class TradingBot(EntryMixin, ExitMixin):
    """
    The main orchestrator for the XAUUSD Momentum Scalping Bot.

    Architecture:
        This class uses a Mixin architecture. It inherits from `EntryMixin` and `ExitMixin`
        to modularize the logic. The `TradingBot` itself manages the infinite loop, MetaTrader 5
        connections, state management (like tracking current candle time, active positions),
        and printing the terminal user interface.

    Responsibilities:
        - Maintain MT5 connection and retrieve real-time ticks.
        - Run technical analysis via `EnhancedTradingStrategy`.
        - Render the live terminal dashboard.
        - Route market data to Entry/Exit mixins to evaluate trading signals.
        - Execute and log the trades.
    """

    Colors = Colors  # expose to mixins via self.Colors

    def __init__(self, symbol="XAUUSD", timeframe="M5"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = EnhancedTradingStrategy(symbol, timeframe)
        self.formatter = TerminalFormatter()
        self.news_filter = NewsFilter()

        self.position_data = {}
        symbol_info = mt5.symbol_info(self.symbol)
        self.contract_size = symbol_info.trade_contract_size if symbol_info else 100.0

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0

        account_info = mt5.account_info()
        self.session_capital = account_info.balance if account_info else 10000.0
        self._symbol_info_startup = symbol_info
        self._account_info_startup = account_info

        self.max_simultaneous = MAX_SIMULTANEOUS_POSITIONS
        tf_settings = getattr(config, "TIMEFRAME_SETTINGS", {}).get(
            self.timeframe, getattr(config, "TIMEFRAME_SETTINGS", {}).get("M5", {})
        )
        self.max_trades_candle = tf_settings.get("MAX_TRADES_CANDLE", 6)

        self.trades_this_candle = 0
        self.losses_this_candle = 0
        self.current_candle_time = None
        self.is_executing = False
        self.loop_count = 0
        self._last_display_time = 0.0
        self.journal_file = "trade_journal.csv"
        self.total_trades_today = 0
        self.scaled_in_tickets = (
            set()
        )  # Track which positions have already been scaled in



        from database import TradeDatabase

        self.db = TradeDatabase()
        self.db.auto_import_from_csv(self.journal_file)

        db_stats = self.db.get_stats()
        if db_stats and db_stats["total_trades"] > 0:
            self.total_trades = db_stats["total_trades"]
            self.winning_trades = db_stats["winning_trades"]
            self.losing_trades = db_stats["losing_trades"]
            self.total_profit = db_stats["total_profit"]

        today_stats = self.db.get_stats(date_filter="today")
        self.today_profit = 0.0
        if today_stats:
            self.total_trades_today = today_stats.get("total_trades", 0)
            self.today_profit = today_stats.get("total_profit", 0.0)
        self.is_executing = False
        self.last_trade_history = None
        self.price_history = collections.deque(maxlen=25)
        self.velocity_buffer = collections.deque(maxlen=10)  # ~3s of samples at 0.3s/tick

        self.pre_entry_ticks = collections.deque(maxlen=50)  # ~1s of ticks before entry
        self.last_trend = "NONE"
        self.last_tick_time = None

        self.entry_block_reasons = collections.Counter()
        self._sl_modify_in_progress = set()

        self.buy_confirm_count = 0
        self.sell_confirm_count = 0
        self.buy_first_confirm_price = None
        self.sell_first_confirm_price = None
        self.last_entry_tick = 0
        self.last_entry_time = 0.0
        self.last_entry_price = None
        self.last_entry_dir = None
        self.last_exit_price = None
        self.last_exit_result = None  # "WIN" or "LOSS"
        self.candle_open_color = None  # color of the candle at open time

        # Consecutive loss tracking
        self.consec_losses = 0
        self.candles_to_pause = 0  # candles remaining before entries re-open

    def save_to_journal(self, data):
        import csv

        file_exists = os.path.isfile(self.journal_file)

        try:
            with open(self.journal_file, mode="a", newline="") as f:
                fieldnames = [
                    "entry_time",
                    "exit_time",
                    "direction",
                    "entry_price",
                    "exit_price",
                    "sl",
                    "tp",
                    "entry_velocity",
                    "exit_reason",
                    "profit_points",
                    "profit_dollars",
                    "result",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                if not file_exists:
                    writer.writeheader()
                writer.writerow(data)
        except Exception as e:
            self.log(f"⚠️ Failed to write to journal: {e}", Colors.RED)

    def log(self, message, color=Colors.RESET):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {color}{message}{Colors.RESET}"
        print(msg)

    def get_market_data(self):
        """
        Fetches the current tick, recent price history, and updates the velocity buffer.
        Velocity is the speed of price movement per second, used to detect momentum breakouts.
        """
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return None, None

        # Check for time gaps or startup sync jumps
        if self.last_tick_time is not None:
            gap = tick.time - self.last_tick_time
            if gap > 5.0 or gap < 0:
                self.log(
                    f"Price sync/gap detected ({gap:.0f}s), resetting velocity buffer.",
                    Colors.YELLOW,
                )
                self.price_history.clear()
                self.velocity_buffer.clear()

        self.last_tick_time = tick.time

        now = time.time()
        self.price_history.append((now, tick.bid))
        cutoff = now - 8
        while self.price_history and self.price_history[0][0] < cutoff:
            self.price_history.popleft()

        analysis = self.strategy.analyze_timeframe(self.timeframe)
        if not analysis:
            return None, None

        current_price = tick.bid

        price_1s = None
        for t, p in reversed(self.price_history):
            if t <= now - 1.0:
                price_1s = p
                break

        price_2s = None
        for t, p in reversed(self.price_history):
            if t <= now - 2.0:
                price_2s = p
                break

        oldest = self.price_history[0][1] if self.price_history else None
        if price_1s is None:
            price_1s = oldest

        if price_1s is not None and price_2s is not None:
            velocity_2s = current_price - price_2s
            velocity_2s_ready = True
            smooth_velocity = ((current_price - price_1s) + velocity_2s / 2.0) / 2.0
        elif price_1s is not None:
            velocity_2s = 0.0
            velocity_2s_ready = False
            smooth_velocity = current_price - price_1s
        else:
            velocity_2s = 0.0
            velocity_2s_ready = False
            smooth_velocity = 0.0

        analysis["velocity"] = smooth_velocity
        analysis["velocity_2s"] = velocity_2s
        analysis["velocity_2s_ready"] = velocity_2s_ready

        self.velocity_buffer.append(smooth_velocity)
        if len(self.velocity_buffer) >= 3:
            # Exponential Weighted Moving Average (EWMA) — recent ticks count more.
            # alpha=0.4 means the most recent tick contributes ~40% of the average,
            # preventing slow ticks from masking strong momentum spikes.
            v_list = list(self.velocity_buffer)
            alpha = 0.4
            ewma = v_list[0]
            for v in v_list[1:]:
                ewma = alpha * v + (1 - alpha) * ewma
            analysis["avg_velocity"] = ewma

            # Velocity Consistency: Avg change between consecutive samples
            changes = [abs(v_list[i] - v_list[i - 1]) for i in range(1, len(v_list))]
            analysis["velocity_avg_change"] = (
                sum(changes) / len(changes) if changes else 0.0
            )

            # Momentum Acceleration: Average of the last two raw velocity deltas
            raw_accels = [v_list[i] - v_list[i - 1] for i in range(1, len(v_list))]
            if len(raw_accels) >= 2:
                analysis["velocity_acceleration"] = sum(raw_accels[-2:]) / 2.0
            elif raw_accels:
                analysis["velocity_acceleration"] = raw_accels[-1]
            else:
                analysis["velocity_acceleration"] = 0.0
        else:
            analysis["avg_velocity"] = None
            analysis["velocity_avg_change"] = 0.0
            analysis["velocity_acceleration"] = 0.0

        current_open = analysis.get("open", 0)
        if current_open > 0:
            live_mom = tick.bid - current_open
            if live_mom > 0:
                analysis["current_candle"] = "GREEN"
            elif live_mom < 0:
                analysis["current_candle"] = "RED"
            else:
                analysis["current_candle"] = "UNKNOWN"
            analysis["candle_color"] = analysis["current_candle"]

        # Override is_higher / is_lower using main tick so both sides
        # use the same price reference — the analysis tick can differ slightly
        prev_body_high = analysis.get("prev_body_high", 0.0)
        prev_body_low = analysis.get("prev_body_low", float("inf"))
        if prev_body_high and prev_body_low < float("inf"):
            analysis["is_higher"] = tick.bid > prev_body_high
            analysis["is_lower"] = tick.bid < prev_body_low

        self.pre_entry_ticks.append(
            {
                "time": now,
                "bid": tick.bid,
                "ask": tick.ask,
                "velocity": analysis.get("velocity", 0.0),
                "avg_vel": analysis.get("avg_velocity"),
            }
        )

        return tick, analysis

    def recover_position_data(self, pos):
        ticket = pos.ticket
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

        rates = mt5.copy_rates_from_pos(
            self.symbol, self.strategy.TIMEFRAMES[self.timeframe], 0, 100
        )
        entry_candle_time = datetime.fromtimestamp(pos.time, tz=timezone.utc)

        if rates is not None:
            entry_timestamp = pos.time
            for rate in reversed(rates):
                if rate["time"] <= entry_timestamp:
                    entry_candle_time = rate["time"]
                    break
            else:
                entry_candle_time = entry_timestamp

        pos_sl = float(pos.sl or 0.0)
        pos_tp = float(pos.tp or 0.0)
        entry_price = float(pos.price_open or 0.0)
        initial_tp_pts = (
            abs(pos_tp - entry_price) if pos_tp > 0 and entry_price > 0 else 2.0
        )

        tick = mt5.symbol_info_tick(self.symbol)
        current_broker_time = tick.time if tick else pos.time
        duration_so_far = current_broker_time - pos.time
        entry_time_ts = time.time() - duration_so_far

        unified_pos_data = {
            "entry_price": entry_price,
            "entry_time": datetime.fromtimestamp(entry_time_ts, tz=timezone.utc),
            "entry_time_ts": entry_time_ts,
            "direction": direction,
            "volume": pos.volume,
            "peak_profit": 0.0,
            "trail_sl_price": None,
            "hard_sl_price": pos_sl if pos_sl > 0 else None,
            "initial_sl": pos_sl if pos_sl > 0 else None,
            "initial_tp": pos_tp if pos_tp > 0 else None,
            "initial_tp_pts": initial_tp_pts,
            "is_manual": True,
        }

        self.position_data[ticket] = unified_pos_data

        self.log(
            f"Recovered data for position #{ticket} ({direction}) @ {entry_candle_time}",
            Colors.YELLOW,
        )
        return unified_pos_data

    def run(self):
        """
        The core execution loop of the bot.

        This loop continuously fetches the latest tick data, computes technical indicators,
        evaluates open positions for exits, and checks for new entry opportunities.
        It runs infinitely until the script is interrupted.
        """
        si = self._symbol_info_startup
        ai = self._account_info_startup
        self.formatter.print_startup(
            symbol=self.symbol,
            timeframe=self.timeframe,
            balance=self.session_capital,
            currency=ai.currency if ai else "USD",
            stops_level=si.trade_stops_level if si else 0,
            point=si.point if si else 0.01,
        )

        if self.news_filter and getattr(config, "ENABLE_NEWS_FILTER", False):
            self.formatter.print_news_calendar(self.news_filter.events)

        db_stats = self.db.get_stats(date_filter="today")
        if db_stats and db_stats["total_trades"] > 0:
            self.formatter.print_database_stats(db_stats, is_today=True)

        previous_positions = set()

        # Prevent the news calendar from printing twice on the first tick
        self.last_news_print_time = time.time()

        try:
            import importlib
            while True:
                try:
                    if getattr(config, "__spec__", None) is not None:
                        importlib.reload(config)
                except Exception:
                    pass
                
                MT5Connection.ensure_connection()

                tick, analysis = self.get_market_data()
                if not tick or not analysis:
                    time.sleep(1)
                    continue

                if analysis.get("is_higher"):
                    self.last_trend = "UP"
                elif analysis.get("is_lower"):
                    self.last_trend = "DOWN"
                else:
                    # Fallback: if price is inside the previous body (consolidating),
                    # use EMA 9 vs EMA 21 alignment to keep the trend label alive.
                    # This prevents a single pullback candle from triggering SIDEWAY_TREND.
                    _ema9 = analysis.get("ema_9")
                    _ema21 = analysis.get("ema_21")
                    if _ema9 is not None and _ema21 is not None:
                        if _ema9 > _ema21:
                            self.last_trend = "UP"
                        elif _ema9 < _ema21:
                            self.last_trend = "DOWN"
                        else:
                            self.last_trend = "NONE"
                    else:
                        self.last_trend = "NONE"

                self.loop_count += 1

                # Save live balance to DB for frontend every ~2-3 seconds
                if self.loop_count % 20 == 0:
                    ai = mt5.account_info()
                    if ai:
                        self.db.save_account_state(ai.balance)

                current_positions = mt5.positions_get(symbol=self.symbol) or ()

                # RECONCILIATION: Check for untracked / ghost orders filled during disconnect
                for pos in current_positions:
                    if pos.ticket not in self.position_data:
                        self.log(
                            f"State Desync: Recovering untracked position #{pos.ticket}",
                            self.Colors.YELLOW,
                        )
                        self.recover_position_data(pos)

                _now = time.time()
                if _now - self._last_display_time >= 1.0:
                    self.formatter.print_tick_status(
                        self, tick, analysis, current_positions
                    )
                    self._last_display_time = _now

                candle_time = analysis.get("time")
                if candle_time and candle_time != self.current_candle_time:
                    is_startup = self.current_candle_time is None
                    self.current_candle_time = candle_time
                    self.trades_this_candle = 0
                    self.losses_this_candle = 0
                    
                    if not is_startup:
                        self.log(
                            f"CANDLE RESET | New {self.timeframe} Candle: {candle_time}",
                            Colors.CYAN,
                        )
                        
                        prev_h = analysis.get("struct_current_high", 0.0)
                        prev_l = analysis.get("struct_current_low", 0.0)
                        prev_o = analysis.get("prev_open", 0.0)
                        prev_c = analysis.get("prev_close", 0.0)
                        prev_body = analysis.get("prev_body", 0.0)
                        candle_range = abs(prev_h - prev_l)
                        
                        no_trade_reason = "Trades Taken"
                        if self.trades_this_candle == 0:
                            if self.entry_block_reasons:
                                top_reason = self.entry_block_reasons.most_common(1)[0][0]
                                no_trade_reason = f"Blocked by {top_reason}"
                            else:
                                no_trade_reason = "No Valid Setup"
                                
                        if candle_range > 0:
                            _today = self.db.get_stats(date_filter="today") or {}
                            self.formatter.print_candle_movement(
                                self.timeframe, candle_range, prev_body,
                                prev_o, prev_h, prev_l, prev_c, no_trade_reason,
                                win_rate=_today.get("win_rate", 0.0),
                                net_pnl=_today.get("total_profit", 0.0),
                                total_trades=_today.get("total_trades", 0),
                            )
                            
                    self.entry_block_reasons.clear()

                    if self.news_filter and getattr(
                        config, "ENABLE_NEWS_FILTER", False
                    ):
                        if _now - self.last_news_print_time >= 3600:
                            self.formatter.print_news_calendar(self.news_filter.events)
                            self.last_news_print_time = _now

                    # Countdown the consecutive loss pause each new candle
                    if getattr(self, "candles_to_pause", 0) > 0:
                        self.candles_to_pause -= 1
                        self.log(
                            f"CONSEC LOSS PAUSE: {self.candles_to_pause} candle(s) remaining before entries re-open",
                            Colors.YELLOW,
                        )
                    self.buy_confirm_count = 0
                    self.sell_confirm_count = 0
                    self.last_entry_tick = 0
                    self.last_entry_time = 0.0
                    self.last_entry_price = None
                    self.last_entry_dir = None
                    self.last_exit_price = None
                    self.last_exit_result = None
                current_positions_raw = mt5.positions_get(symbol=self.symbol)
                if current_positions_raw is None:
                    err = mt5.last_error()
                    if err[0] != mt5.RES_S_OK:
                        self.log(f"⚠️ mt5.positions_get failed: {err} — skipping reconciliation to prevent false closes", Colors.YELLOW)
                        continue
                    else:
                        current_positions = ()
                else:
                    current_positions = current_positions_raw

                current_tickets = set(pos.ticket for pos in current_positions)

                closed_tickets = previous_positions - current_tickets
                for ticket in closed_tickets:
                    if ticket in self.position_data:
                        pos_data = self.position_data[ticket]

                        entry_time_ts = pos_data.get("entry_time_ts", time.time())
                        duration_seconds = int(time.time() - entry_time_ts)
                        
                        hours, remainder = divmod(duration_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            duration_str = f"{hours}h {minutes}m {seconds}s"
                        elif minutes > 0:
                            duration_str = f"{minutes}m {seconds}s"
                        else:
                            duration_str = f"{seconds}s"
                            
                        direction = pos_data.get("direction", "UNKNOWN")
                        entry_price = pos_data.get("entry_price", 0)

                        volume = pos_data.get("volume", 1.0)

                        # Use last known profit if history is delayed
                        last_known_profit = pos_data.get("last_profit_pts", 0)

                        deals = mt5.history_deals_get(position=ticket)
                        exit_price = entry_price  # fallback

                        if deals and len(deals) > 1:
                            exit_price = deals[-1].price
                            profit_points = (
                                (exit_price - entry_price)
                                if direction == "BUY"
                                else (entry_price - exit_price)
                            )
                            profit_dollars = profit_points * volume * self.contract_size
                        else:
                            profit_points = last_known_profit
                            exit_price = (
                                (entry_price + last_known_profit)
                                if direction == "BUY"
                                else (entry_price - last_known_profit)
                            )
                            profit_dollars = profit_points * volume * self.contract_size

                        # SAFETY CHECK: Ignore massive calculation errors (e.g. entry_price=0)
                        if abs(profit_dollars) > (self.session_capital * 2):
                            self.log(
                                f"⚠️ IGNORED BUGGY PROFIT: ${profit_dollars:.2f} (Entry: {entry_price})",
                                Colors.YELLOW,
                            )
                            profit_dollars = 0

                        self.total_profit += profit_dollars
                        self.today_profit += profit_dollars

                        # Use only actual profit_points — last_known_profit is stale (0.3s old)
                        # and can wrongly count a TP win as a loss if price briefly dipped before close
                        if profit_points < -0.01:
                            self.losing_trades += 1
                        else:
                            self.winning_trades += 1

                        total_closed = self.winning_trades + self.losing_trades
                        win_rate = (
                            (self.winning_trades / total_closed * 100)
                            if total_closed > 0
                            else 0
                        )

                        exit_condition = pos_data.get("exit_reason")
                        if not exit_condition:
                            trail_sl = pos_data.get("trail_sl_price")
                            profit_lock_sl = pos_data.get("price_lock_sl_price")
                            hard_sl = pos_data.get(
                                "hard_sl_price", pos_data.get("initial_sl", 0.0)
                            )
                            initial_tp = pos_data.get("initial_tp")

                            # Give a small slippage allowance of 0.5 points for exact matching
                            slippage_allowance = 0.5

                            if (
                                initial_tp
                                and abs(exit_price - initial_tp) <= slippage_allowance
                            ):
                                exit_condition = "TP"
                            elif (
                                trail_sl
                                and abs(exit_price - trail_sl) <= slippage_allowance
                            ):
                                exit_condition = "Trailing SL"
                            elif (
                                profit_lock_sl
                                and abs(exit_price - profit_lock_sl)
                                <= slippage_allowance
                            ):
                                exit_condition = "Profit Lock"
                            elif (
                                hard_sl
                                and abs(exit_price - hard_sl) <= slippage_allowance
                                and profit_points <= 0.0  # Mathematically block Hard SL on winners
                            ):
                                exit_condition = "Hard SL"
                            elif profit_points > 0.0:
                                exit_condition = "Trailing SL" # Fallback for profitable slip
                            else:
                                exit_condition = "UNKNOWN_BROKER_EXIT"

                        peak = pos_data.get("peak_profit", 0.0)
                        v_entry = pos_data.get("entry_velocity", 0.0)
                        tp_target = pos_data.get("initial_tp_pts", 0.0)
                        
                        self.last_trade_history = {
                            "direction": direction,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "profit_points": profit_points
                        }
                        self._last_exit_time = time.time()

                        journal_data = {
                            "ticket": ticket,
                            "entry_time": pos_data.get(
                                "entry_time", datetime.now(timezone.utc)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "exit_time": datetime.now(timezone.utc).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "ticket": ticket,
                            "direction": direction,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "sl": (
                                pos_data.get("trail_sl_price")
                                or pos_data.get("price_lock_sl_price")
                                or pos_data.get("hard_sl_price")
                                or pos_data.get("initial_sl", 0.0)
                            ),
                            "tp": pos_data.get("initial_tp_pts", 0.0),
                            "entry_velocity": v_entry,
                            "exit_reason": exit_condition,
                            "profit_points": round(float(profit_points or 0), 2),
                            "profit_dollars": round(float(profit_dollars or 0), 2),
                            "result": "WIN" if profit_points > 0 else "LOSS",
                            "volume": volume,
                            "timeframe": self.timeframe,
                            "score_momentum": pos_data.get("score_momentum", 0.0),
                            "score_trend": pos_data.get("score_trend", 0.0),
                            "score_candle": pos_data.get("score_candle", 0.0),
                            "score_execution": pos_data.get("score_execution", 0.0),
                            "score_total": pos_data.get("score_total", 0.0),
                            "velocity_consistency": pos_data.get(
                                "velocity_consistency", 0.0
                            ),
                            "velocity_acceleration": pos_data.get(
                                "velocity_acceleration", 0.0
                            ),
                            "score_acceleration": pos_data.get(
                                "score_acceleration", 0.0
                            ),
                            "velocity_std": pos_data.get("velocity_std", 0.0),
                            "velocity_mean": pos_data.get("velocity_mean", 0.0),
                            "mfe": pos_data.get("mfe", 0.0),
                            "mae": pos_data.get("mae", 0.0),
                            "strategy_version": getattr(
                                config, "STRATEGY_VERSION", "unknown"
                            ),
                            "duration_seconds": duration_seconds,
                            "adx_14": pos_data.get("adx_14", 0.0),
                            "sideways_score": pos_data.get("sideways_score", 0),
                            "st_flips_5": pos_data.get("st_flips_5", 0),
                            "bb_bandwidth": pos_data.get("bb_bandwidth", 0.0),
                        }
                        if getattr(self, "db", None):
                            self.save_to_journal(journal_data)
                        self.db.save_trade(journal_data)

                        db_stats = self.db.get_stats(date_filter="today")
                        if db_stats and db_stats["total_trades"] > 0:
                            today_trades = db_stats["total_trades"]
                            today_wr = db_stats["win_rate"]
                            today_profit = db_stats["total_profit"]
                        else:
                            today_trades = total_closed
                            today_wr = win_rate
                            today_profit = self.total_profit

                        self.formatter.print_trade_exit_with_condition(
                            direction,
                            entry_price,
                            exit_price,
                            duration_str,
                            ticket,
                            today_trades,
                            today_wr,
                            self.session_capital,
                            today_profit,
                            exit_condition,
                            trade_profit=profit_dollars,
                        v_entry=v_entry,
                            tp_target=tp_target,
                            peak=peak,
                        )

                        if db_stats:
                            self.formatter.print_database_stats(db_stats, is_today=True)

                        self.total_trades_today += 1
                        if profit_points > 0:
                            self.log(
                                f"PROFITABLE EXIT: {direction} at {exit_price:.2f} (+{profit_points:.2f}pts)",
                                Colors.GREEN,
                            )
                            self.consec_losses = 0
                            self.last_exit_price = exit_price
                            self.last_exit_result = "WIN"
                        elif profit_points < -0.01:
                            self.losses_this_candle += 1
                            self.consec_losses += 1
                            self.log(
                                f"LOSS #{self.losses_this_candle}/{MAX_LOSSES_PER_CANDLE} this candle | Consec: {self.consec_losses}/{MAX_CONSEC_LOSSES}",
                                Colors.ORANGE,
                            )
                            if self.consec_losses >= MAX_CONSEC_LOSSES:
                                self.candles_to_pause = max(getattr(self, "candles_to_pause", 0), LOSS_PAUSE_CANDLES)
                                self.log(
                                    f"🚨 CONSEC_LOSS_LIMIT HIT ({self.consec_losses}) — pausing entries for {LOSS_PAUSE_CANDLES} candles",
                                    Colors.RED,
                                )
                            self.last_exit_price = exit_price
                            self.last_exit_result = "LOSS"

                        del self.position_data[ticket]

                previous_positions = current_tickets

                if current_positions:
                    self.check_exit_conditions(tick, analysis, current_positions)
                    # Refresh after exit checks — a position may have just been closed
                    current_positions = mt5.positions_get(symbol=self.symbol) or ()



                # Check for News Block (but allow exits)
                is_news_blocked, news_title = self.news_filter.is_news_block_active()

                # Allow entry even with open positions (up to MAX_SIMULTANEOUS_POSITIONS)
                # but enforce a 2-second gap after the last entry, and require price
                # to have moved at least 0.30 pts favorably past the last entry price
                ticks_since_last_entry = self.loop_count - self.last_entry_tick
                time_since_last_entry = time.time() - self.last_entry_time
                price_moved_ok = True
                if self.last_entry_price and self.last_entry_dir:
                    if self.last_entry_dir == "BUY":
                        price_moved_ok = tick.bid >= self.last_entry_price - 0.10
                    else:
                        price_moved_ok = tick.bid <= self.last_entry_price + 0.10

                # --- POST-EXIT / PREV TRADE PRICE GUARDS ---
                # REMOVED: Sequential price guards forced the bot to buy at worse prices after a stop-out.
                # We now rely purely on MAX_LOSSES_PER_CANDLE and time/candle momentum rules.
                re_entry_ok = True

                if (
                    len(current_positions) < self.max_simultaneous
                    and ticks_since_last_entry >= 1
                    and time_since_last_entry >= 0.5
                    and price_moved_ok
                    and re_entry_ok
                    and self.losses_this_candle < MAX_LOSSES_PER_CANDLE
                ):
                    if is_news_blocked and getattr(config, "BLOCK_TRADES_ON_NEWS", True):
                        if self.loop_count % 15 == 0:
                            self.log(
                                f"NEWS BLOCK ACTIVE: {news_title} (Entries Paused)",
                                self.Colors.YELLOW,
                            )
                    else:
                        # ── SESSION HOURS GATE ────────────────────────────────────────
                        # Block NEW entries outside configured session window.
                        # Exits on open positions are always allowed regardless of session.
                        _can_enter = True
                        if (
                            getattr(config, "ENABLE_SESSION_FILTER", False)
                            and not current_positions
                        ):
                            _utc_hour = datetime.now(timezone.utc).hour
                            _sess_start = getattr(config, "SESSION_START_HOUR_UTC", 7)
                            _sess_end = getattr(config, "SESSION_END_HOUR_UTC", 21)

                            max_allowed = getattr(
                                config, "MAX_SIMULTANEOUS_POSITIONS", 2
                            )
                            if (
                                len(current_positions) if current_positions else 0
                            ) >= max_allowed:
                                _can_enter = False

                            if not (_sess_start <= _utc_hour < _sess_end):
                                _can_enter = False
                                if self.loop_count % 60 == 0:
                                    self.log(
                                        f"SESSION FILTER: Outside trading hours "
                                        f"(UTC {_utc_hour:02d}:xx — allowed {_sess_start:02d}:00–{_sess_end:02d}:00)",
                                        self.Colors.YELLOW,
                                    )

                        if _can_enter:
                            entry_signal, entry_type, score = (
                                self.check_entry_conditions(
                                    tick, analysis, current_positions
                                )
                            )
                            analysis["last_entry_type"] = entry_type
                            if entry_signal in ["BUY", "SELL"]:
                                if self.execute_entry(
                                    entry_signal,
                                    tick,
                                    analysis,
                                    entry_type=entry_type,
                                    score=score,
                                ):
                                    self.last_entry_tick = self.loop_count
                                    self.last_entry_time = time.time()
                                    self.last_entry_price = (
                                        tick.ask if entry_signal == "BUY" else tick.bid
                                    )
                                    self.last_entry_dir = entry_signal

                try:

                    def safe_replace(src, dst):
                        for _ in range(10):
                            try:
                                os.replace(src, dst)
                                return
                            except PermissionError:
                                time.sleep(0.01)
                        os.replace(src, dst)

                    # Compute current block reason for the frontend
                    _live_buy_score = self.strategy.calculate_momentum_score("BUY", tick, analysis, {})
                    _live_sell_score = self.strategy.calculate_momentum_score("SELL", tick, analysis, {})
                    _live_block = _live_buy_score.block_reason or _live_sell_score.block_reason or ""

                    # Top candle-level block reason (from entry guards like SIDEWAY_TREND, DAILY_LIMIT etc.)
                    _top_guard_reason = ""
                    if self.entry_block_reasons:
                        _top_guard_reason = self.entry_block_reasons.most_common(1)[0][0]

                    market_state = {
                        "trend_label": getattr(self, "last_trend", "NONE"),
                        "timeframe": self.timeframe,
                        "timestamp": int(time.time() * 1000),
                        "current_price": tick.bid if tick else 0,
                        "spread": round((tick.ask - tick.bid) * 100, 1) if tick else 0,
                        # Live entry analysis for frontend status panel
                        "block_reason": _top_guard_reason or _live_block,
                        "ema_9": round(analysis.get("ema_9") or 0, 2) if analysis else 0,
                        "ema_21": round(analysis.get("ema_21") or 0, 2) if analysis else 0,
                        "ema_9_angle": round(analysis.get("ema_9_angle") or 0, 1) if analysis else 0,
                        "ema_21_angle": round(analysis.get("ema_21_angle") or 0, 1) if analysis else 0,
                        "atr_14": round(analysis.get("atr_14") or 0, 2) if analysis else 0,
                        "velocity": round(analysis.get("velocity") or 0, 3) if analysis else 0,
                        "avg_velocity": round(analysis.get("avg_velocity") or 0, 3) if analysis else 0,
                        "candle_color": analysis.get("candle_color", "UNKNOWN") if analysis else "UNKNOWN",
                        "buy_score": round(analysis.get("buy_score_total") or 0, 1) if analysis else 0,
                        "sell_score": round(analysis.get("sell_score_total") or 0, 1) if analysis else 0,
                        "seconds_into_candle": int(tick.time) - int(analysis.get("time", tick.time)) if analysis and analysis.get("time") else 0,
                    }

                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    temp_market = os.path.join(base_dir, "market_state_tmp.json")
                    target_market = os.path.join(base_dir, "market_state.json")
                    with open(temp_market, "w") as f:
                        json.dump(market_state, f)
                    safe_replace(temp_market, target_market)

                    active_trades_list = []
                    if current_positions:
                        for p in current_positions:
                            direction = (
                                "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                            )
                            profit = p.profit
                            profit_pts = (
                                (p.price_current - p.price_open)
                                if direction == "BUY"
                                else (p.price_open - p.price_current)
                            )
                            active_trades_list.append(
                                {
                                    "ticket": p.ticket,
                                    "direction": direction,
                                    "entry_price": p.price_open,
                                    "current_price": p.price_current,
                                    "profit_points": profit_pts,
                                    "profit_dollars": profit,
                                    "volume": p.volume,
                                    "trend_label": getattr(self, "last_trend", "NONE"),
                                    "timeframe": self.timeframe,
                                    "timestamp": int(time.time() * 1000),
                                    "sl": p.sl,
                                    "tp": p.tp,
                                    "open_time": int(time.time()) - max(0, int(mt5.symbol_info_tick(self.symbol).time) - int(p.time)) if mt5.symbol_info_tick(self.symbol) else int(time.time()),
                                    "spread": 0,
                                }
                            )
                    temp_trade = os.path.join(base_dir, "active_trade_tmp.json")
                    target_trade = os.path.join(base_dir, "active_trade.json")
                    with open(temp_trade, "w") as f:
                        json.dump(active_trades_list, f)
                    safe_replace(temp_trade, target_trade)
                except Exception as ex:
                    print(f"Error writing live state: {ex}")

                time.sleep(0.05 if current_positions else 0.3)

        except KeyboardInterrupt:
            today = self.db.get_stats(date_filter="today")
            if today and today["total_trades"] > 0:
                self.log(
                    f">> Bot stopped | Today — Trades:{today['total_trades']} W:{today['winning_trades']} L:{today['losing_trades']} WR:{today['win_rate']:.1f}% P&L:${today['total_profit']:.2f}",
                    Colors.YELLOW,
                )
            else:
                self.log(">> Bot stopped | No trades today.", Colors.YELLOW)

        except Exception as e:
            self.log(f">> Critical error: {e}", Colors.RED)
        finally:
            mt5.shutdown()


def main():
    if not MT5Connection.initialize_mt5():
        return
    TradingBot(config.SYMBOL, config.TIMEFRAME).run()


if __name__ == "__main__":
    main()
