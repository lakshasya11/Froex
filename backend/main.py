import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
import time
import os
from datetime import datetime, timezone
import collections
from strategy import EnhancedTradingStrategy
from formatter import TerminalFormatter
from connection import MT5Connection
from entry import EntryMixin
from exit import ExitMixin
from news import NewsFilter
import config
from config import (
    LOT_SIZE, MAX_SIMULTANEOUS_POSITIONS,
    TP_ULTRA_STRONG, TP_STRONG, TP_MODERATE, MAX_RISK_TO_TP_RATIO, HARD_STOP_LOSS,
    ENTRY_VEL_FRESH, ENTRY_AVG_FRESH,
    MAX_TRADES_PER_CANDLE, MAX_LOSSES_PER_CANDLE,
    MIN_ENTRY_2S_VEL, CANDLE_ENTRY_END,
    MAX_CONSEC_LOSSES, LOSS_PAUSE_CANDLES   # FIX #6
)

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except OSError:
        pass

os.environ['FORCE_COLOR'] = '1'

class Colors:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'
    ORANGE  = '\033[38;5;208m'

    @staticmethod
    def get_candle_color(candle_type):
        return Colors.GREEN if candle_type == 'GREEN' else Colors.RED

class TradingBot(EntryMixin, ExitMixin):
    """
    The main Trading Bot class. It combines Entry logic (EntryMixin) and Exit logic (ExitMixin).
    It runs an infinite loop checking market conditions and managing open positions.
    """
    Colors = Colors  # expose to mixins via self.Colors

    def __init__(self, symbol="XAUUSD", timeframe="M5"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = EnhancedTradingStrategy(symbol, timeframe)
        self.tick_count = 0
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
        self.trades_this_candle = 0
        self.losses_this_candle = 0
        self.current_candle_time = None
        self.is_executing = False
        self.loop_count = 0
        self._last_display_time = 0.0
        self.journal_file = "trade_journal.csv"
        self.total_trades_today = 0
        self.scaled_in_tickets = set()  # Track which positions have already been scaled in

        from database import TradeDatabase
        self.db = TradeDatabase()
        self.db.auto_import_from_csv(self.journal_file)

        db_stats = self.db.get_stats()
        if db_stats and db_stats['total_trades'] > 0:
            self.total_trades = db_stats['total_trades']
            self.winning_trades = db_stats['winning_trades']
            self.losing_trades = db_stats['losing_trades']
            self.total_profit = db_stats['total_profit']

        today_stats = self.db.get_stats(date_filter="today")
        if today_stats:
            self.total_trades_today = today_stats.get('total_trades', 0)

        self.price_history = collections.deque(maxlen=25)
        self.velocity_buffer = collections.deque(maxlen=5)

        self.pre_entry_ticks = collections.deque(maxlen=50)  # ~1s of ticks before entry
        self.last_trend = "NONE"
        self.last_tick_time = None

        self.entry_block_reasons = collections.Counter()
        self._sl_modify_in_progress = set()

        self.buy_confirm_count = 0
        self.sell_confirm_count = 0
        self.buy_first_confirm_price = None
        self.sell_first_confirm_price = None
        self.last_entry_tick  = 0
        self.last_entry_time  = 0.0
        self.last_entry_price = None
        self.last_entry_dir   = None
        self.last_exit_price  = None
        self.last_exit_result = None  # "WIN" or "LOSS"
        self.candle_open_color = None  # color of the candle at open time
        self.last_candle_trade = {}

        # FIX #6: Consecutive loss tracking
        self.consec_losses   = 0   # rolling consecutive loss counter
        self.candles_to_pause = 0  # candles remaining before entries re-open

    def save_to_journal(self, data):
        import csv
        file_exists = os.path.isfile(self.journal_file)

        try:
            with open(self.journal_file, mode='a', newline='') as f:
                fieldnames = [
                    'entry_time', 'exit_time', 'direction', 'entry_price',
                    'exit_price', 'sl', 'tp', 'entry_velocity',
                    'exit_reason', 'profit_points', 'profit_dollars', 'result'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
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
                self.log(f"🔄 Price sync/gap detected ({gap:.0f}s), resetting velocity buffer.", Colors.YELLOW)
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
        
        self.last_analysis = analysis

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
        if price_1s is None: price_1s = oldest

        if price_1s is not None and price_2s is not None:
            velocity_2s     = current_price - price_2s
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

        analysis['velocity']    = smooth_velocity
        analysis['velocity_2s'] = velocity_2s
        analysis['velocity_2s_ready'] = velocity_2s_ready

        self.velocity_buffer.append(smooth_velocity)
        if len(self.velocity_buffer) >= 3:
            analysis['avg_velocity'] = sum(self.velocity_buffer) / len(self.velocity_buffer)
        else:
            analysis['avg_velocity'] = None

        current_open = analysis.get('open', 0)
        if current_open > 0:
            live_mom = tick.bid - current_open
            if live_mom > 0:
                analysis['current_candle'] = 'GREEN'
            elif live_mom < 0:
                analysis['current_candle'] = 'RED'
            else:
                analysis['current_candle'] = 'UNKNOWN'
            analysis['candle_color'] = analysis['current_candle']

        # Override is_higher / is_lower using main tick so both sides
        # use the same price reference — the analysis tick can differ slightly
        prev_body_high = analysis.get('prev_body_high', 0.0)
        prev_body_low  = analysis.get('prev_body_low', float('inf'))
        if prev_body_high and prev_body_low < float('inf'):
            analysis['is_higher'] = tick.bid > prev_body_high
            analysis['is_lower']  = tick.bid < prev_body_low

        self.pre_entry_ticks.append({
            'time': now,
            'bid': tick.bid,
            'ask': tick.ask,
            'velocity': analysis.get('velocity', 0.0),
            'avg_vel': analysis.get('avg_velocity')
        })

        return tick, analysis

    def recover_position_data(self, pos):
        ticket = pos.ticket
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

        rates = mt5.copy_rates_from_pos(self.symbol, self.strategy.TIMEFRAMES[self.timeframe], 0, 100)
        entry_candle_time = datetime.fromtimestamp(pos.time, tz=timezone.utc)

        if rates is not None:
            entry_timestamp = pos.time
            for rate in reversed(rates):
                if rate['time'] <= entry_timestamp:
                    entry_candle_time = rate['time']
                    break
            else:
                entry_candle_time = entry_timestamp

        pos_sl = float(pos.sl or 0.0)
        pos_tp = float(pos.tp or 0.0)
        entry_price = float(pos.price_open or 0.0)
        initial_tp_pts = abs(pos_tp - entry_price) if pos_tp > 0 and entry_price > 0 else 2.0

        unified_pos_data = {
            'entry_price': entry_price,
            'entry_time': datetime.fromtimestamp(pos.time, tz=timezone.utc),
            'direction': direction,
            'volume': pos.volume,
            'peak_profit': 0.0,
            'trail_sl_price': None,
            'hard_sl_price': pos_sl if pos_sl > 0 else None,
            'initial_sl': pos_sl if pos_sl > 0 else None,
            'initial_tp': pos_tp if pos_tp > 0 else None,
            'initial_tp_pts': initial_tp_pts,
        }

        self.position_data[ticket] = unified_pos_data

        self.log(f"🔄 Recovered data for position #{ticket} ({direction}) @ {entry_candle_time}", Colors.YELLOW)
        return unified_pos_data


    def display_status(self, tick, analysis, positions):
        self.tick_count += 1
        time_str = datetime.now().strftime("%H:%M:%S")

        candle_open_time = analysis.get('time', 0)
        seconds_into_candle = int(tick.time) - int(candle_open_time) if candle_open_time else 0

        curr_candle = analysis.get('current_candle', '???')

        cc_color = Colors.get_candle_color(curr_candle)

        prev_body = analysis.get('prev_body', 0.0)
        is_lower  = analysis.get('is_lower', False)
        is_higher = analysis.get('is_higher', False)

        st_dir = analysis.get('st_direction', 0)
        current_open = analysis.get('open', tick.bid)
        current_body = tick.bid - current_open if tick.bid > current_open else current_open - tick.bid
        
        if not is_higher and not is_lower:
            if current_body >= 0.70:
                if tick.bid > current_open:
                    is_higher = True
                elif tick.bid < current_open:
                    is_lower = True
            elif st_dir == 1:
                is_higher = True
            elif st_dir == -1:
                is_lower = True

        seq_status = "HIGH" if is_higher else "LOW" if is_lower else f"MIX({self.last_trend})"
        seq_color = Colors.GREEN if is_higher else Colors.RED if is_lower else Colors.YELLOW

        is_mixed = (not is_higher and not is_lower)
        avg_v_raw = analysis.get('avg_velocity')
        vsm       = analysis.get('velocity', 0.0)
        velocity_2s = analysis.get('velocity_2s', 0.0)
        velocity_2s_ready = analysis.get('velocity_2s_ready', False)
        current_open = analysis.get('open', tick.bid)
        
        bb_ang = analysis.get('bb_angle', 0.0)
        st_ang = analysis.get('st_angle', 0.0)
        st_dir = analysis.get('st_direction', 0)
        st_label = "BULL" if st_dir == 1 else ("BEAR" if st_dir == -1 else "FLAT")

        if positions:
            pos = positions[0]
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            profit_pts = (tick.bid - pos.price_open) if direction == "BUY" else (pos.price_open - tick.ask)
            profit_val = profit_pts * pos.volume * self.contract_size
            p_color = Colors.GREEN if profit_val >= 0 else Colors.RED
            status = f"{Colors.BOLD}{direction}{Colors.RESET} {p_color}${profit_val:+.2f}{Colors.RESET}"
        else:
            if seconds_into_candle > CANDLE_ENTRY_END:
                status = f"{Colors.YELLOW}⏳ TIME WINDOW CLOSED ({max(0, 300 - seconds_into_candle)}s){Colors.RESET}"
            elif self.trades_this_candle >= MAX_TRADES_PER_CANDLE:
                status = f"{Colors.YELLOW}⏳ TRADE DONE THIS CANDLE ({self.trades_this_candle}/{MAX_TRADES_PER_CANDLE}){Colors.RESET}"
            elif is_mixed:
                status = ""
            elif curr_candle == 'GREEN':
                _v_req = ENTRY_VEL_FRESH
                _a_req = ENTRY_AVG_FRESH
                _vel_ok = vsm >= _v_req
                _avg_ok = avg_v_raw is not None and avg_v_raw >= _a_req
                st_dir = analysis.get('st_direction', 0)
                
                if not _vel_ok:
                    status = f"{Colors.CYAN}🔭 BUY  vel:{vsm:+.2f} < +{_v_req}{Colors.RESET}"
                elif st_dir != 1:
                    status = f"{Colors.ORANGE}🔭 BUY  st_dir != BULL{Colors.RESET}"
                elif not velocity_2s_ready:
                    status = f"{Colors.ORANGE}🔭 BUY  2s not ready{Colors.RESET}"
                elif velocity_2s < MIN_ENTRY_2S_VEL:
                    status = f"{Colors.ORANGE}🔭 BUY  2s:{velocity_2s:+.2f} < +{MIN_ENTRY_2S_VEL:.2f}{Colors.RESET}"
                elif not _avg_ok:
                    status = f"{Colors.YELLOW}🔭 BUY  avg:{avg_v_raw:+.2f} < +{_a_req}{Colors.RESET}"
                else:
                    status = f"{Colors.CYAN}🔭 BUY  ✓ vel:{vsm:+.2f} avg:{avg_v_raw:+.2f}{Colors.RESET}"
                    
            elif curr_candle == 'RED':
                _v_req = ENTRY_VEL_FRESH
                _a_req = ENTRY_AVG_FRESH
                _vel_ok = vsm <= -_v_req
                _avg_ok = avg_v_raw is not None and avg_v_raw <= -_a_req
                st_dir = analysis.get('st_direction', 0)
                
                if not _vel_ok:
                    status = f"{Colors.MAGENTA}🔭 SELL vel:{vsm:+.2f} > -{_v_req}{Colors.RESET}"
                elif st_dir != -1:
                    status = f"{Colors.ORANGE}🔭 SELL st_dir != BEAR{Colors.RESET}"
                elif not velocity_2s_ready:
                    status = f"{Colors.ORANGE}🔭 SELL 2s not ready{Colors.RESET}"
                elif velocity_2s > -MIN_ENTRY_2S_VEL:
                    status = f"{Colors.ORANGE}🔭 SELL 2s:{velocity_2s:+.2f} > -{MIN_ENTRY_2S_VEL:.2f}{Colors.RESET}"
                elif not _avg_ok:
                    status = f"{Colors.YELLOW}🔭 SELL avg:{avg_v_raw:+.2f} > -{_a_req}{Colors.RESET}"
                else:
                    status = f"{Colors.MAGENTA}🔭 SELL ✓ vel:{vsm:+.2f} avg:{avg_v_raw:+.2f}{Colors.RESET}"
            else:
                status = f"{Colors.YELLOW}🔭 Wait: No Direction{Colors.RESET}"

        avg_v_str = f"{avg_v_raw:+.2f}" if avg_v_raw is not None else " N/A"
        v_color   = Colors.GREEN if vsm >= 0 else Colors.RED
        st_color  = Colors.GREEN if st_dir == 1 else Colors.RED if st_dir == -1 else Colors.YELLOW

        arrow = "▲" if curr_candle == 'GREEN' else "▼" if curr_candle == 'RED' else "─"

        T  = Colors.RESET
        DIM = '\033[2m'

        t_part  = f"{DIM}{time_str}{T}"
        m, s = divmod(seconds_into_candle, 60)
        candle_time_str = f"{m:02d}:{s:02d}/05:00"
        if seconds_into_candle >= 280:
            time_color = Colors.RED
        else:
            time_color = Colors.GREEN
        tk_part = f"{time_color}{Colors.BOLD}[{candle_time_str}]{T}"
        p_part  = f"{cc_color}{Colors.BOLD}{tick.bid:.2f}{T}"
        c_part  = f"{cc_color}{arrow} {curr_candle:<5}{T}"
        s_part  = f"{seq_color}{seq_status:<9}{T}"
        pb_part = f"{DIM}PB{T}:{Colors.BOLD}{prev_body:.2f}{T}"
        v_part  = f"{DIM}V{T}:{v_color}{vsm:+.2f}{T} {DIM}A{T}:{avg_v_str}"
        ind_part = f"{DIM}ST:{T}{st_color}{st_label:<4}{T} {DIM}BB:{T}{bb_ang:>+5.1f}°"

        print(f"{t_part}  {tk_part}  {p_part}  {c_part}  {s_part}  {pb_part}  {ind_part}  {v_part}  {status}")


    def calculate_volume(self, current_price):
        return getattr(config, 'LOT_SIZE', 0.10)

    def run(self):
        """
        The core infinite loop of the bot.
        It continuously pulls new market data, checks exit conditions for open trades,
        and checks entry conditions to open new trades.
        """
        si = self._symbol_info_startup
        ai = self._account_info_startup
        self.formatter.print_startup(
            symbol      = self.symbol,
            timeframe   = self.timeframe,
            balance     = self.session_capital,
            currency    = ai.currency if ai else "USD",
            stops_level = si.trade_stops_level if si else 0,
            point       = si.point if si else 0.01
        )

        if self.news_filter and getattr(config, 'ENABLE_NEWS_FILTER', False):
            self.formatter.print_news_calendar(self.news_filter.events)

        db_stats = self.db.get_stats(date_filter="today")
        if db_stats and db_stats['total_trades'] > 0:
            self.formatter.print_database_stats(db_stats, is_today=True)

        previous_positions = set()
        
        # Prevent the news calendar from printing twice on the first tick
        self.last_news_print_time = time.time()

        try:
            while True:
                MT5Connection.ensure_connection()

                tick, analysis = self.get_market_data()
                if not tick or not analysis:
                    time.sleep(1)
                    continue

                if analysis.get('is_higher'): self.last_trend = "UP"
                elif analysis.get('is_lower'): self.last_trend = "DOWN"

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
                        self.log(f"🔄 State Desync: Recovering untracked position #{pos.ticket}", self.Colors.YELLOW)
                        self.recover_position_data(pos)

                _now = time.time()
                if _now - self._last_display_time >= 1.0:
                    self.display_status(tick, analysis, current_positions)
                    self._last_display_time = _now
                

                candle_time = analysis.get('time')
                if candle_time and candle_time != self.current_candle_time:
                    self.current_candle_time = candle_time
                    self.trades_this_candle = 0
                    self.losses_this_candle = 0
                    self.log(f"🔄 CANDLE RESET | New {self.timeframe} Candle: {candle_time}", Colors.CYAN)
                    
                    if self.news_filter and getattr(config, 'ENABLE_NEWS_FILTER', False):
                        if _now - self.last_news_print_time >= 3600:
                            self.formatter.print_news_calendar(self.news_filter.events)
                            self.last_news_print_time = _now

                    # FIX #6: Countdown the consecutive loss pause each new candle
                    if self.candles_to_pause > 0:
                        self.candles_to_pause -= 1
                        self.log(f"⏸️ CONSEC LOSS PAUSE: {self.candles_to_pause} candle(s) remaining before entries re-open", Colors.YELLOW)
                    self.buy_confirm_count = 0
                    self.sell_confirm_count = 0
                    self.buy_first_confirm_price = None
                    self.sell_first_confirm_price = None
                    self.last_entry_tick  = 0
                    self.last_entry_time  = 0.0
                    self.last_entry_price = None
                    self.last_entry_dir   = None
                    self.last_exit_price  = None
                    self.last_exit_result = None
                    self.candle_open_color = None  # track color at candle open
                    self.last_candle_trade = {}
                current_tickets = set(pos.ticket for pos in current_positions)

                closed_tickets = previous_positions - current_tickets
                for ticket in closed_tickets:
                    if ticket in self.position_data:
                        pos_data = self.position_data[ticket]

                        entry_time = pos_data.get('entry_time', datetime.now(timezone.utc))
                        duration = str(datetime.now(timezone.utc) - entry_time).split('.')[0]
                        direction = pos_data.get('direction', 'UNKNOWN')
                        entry_price = pos_data.get('entry_price', 0)

                        volume = pos_data.get('volume', 1.0)

                        # Use last known profit if history is delayed
                        last_known_profit = pos_data.get('last_profit_pts', 0)

                        deals = mt5.history_deals_get(position=ticket)
                        exit_price = entry_price  # fallback

                        if deals and len(deals) > 1:
                            exit_price = deals[-1].price
                            profit_points = (exit_price - entry_price) if direction == 'BUY' else (entry_price - exit_price)
                            profit_dollars = profit_points * volume * self.contract_size
                        else:
                            profit_points = last_known_profit
                            exit_price = (entry_price + last_known_profit) if direction == "BUY" else (entry_price - last_known_profit)
                            profit_dollars = profit_points * volume * self.contract_size

                        # SAFETY CHECK: Ignore massive calculation errors (e.g. entry_price=0)
                        if abs(profit_dollars) > (self.session_capital * 2):
                            self.log(f"⚠️ IGNORED BUGGY PROFIT: ${profit_dollars:.2f} (Entry: {entry_price})", Colors.YELLOW)
                            profit_dollars = 0

                        self.total_profit += profit_dollars

                        # Use only actual profit_points — last_known_profit is stale (0.3s old)
                        # and can wrongly count a TP win as a loss if price briefly dipped before close
                        if profit_points < -0.01:
                            self.losing_trades += 1
                        else:
                            self.winning_trades += 1

                        total_closed = self.winning_trades + self.losing_trades
                        win_rate = (self.winning_trades / total_closed * 100) if total_closed > 0 else 0

                        exit_condition = pos_data.get('exit_reason')
                        if not exit_condition:
                            trail_sl    = pos_data.get('trail_sl_price')
                            profit_lock_sl = pos_data.get('price_lock_sl_price')
                            initial_tp  = pos_data.get('initial_tp')
                            tp_pts_stored = pos_data.get('initial_tp_pts', 2.0)
                            # TP detection: check price-level match OR profit >= TP pts
                            tp_hit = (
                                (initial_tp is not None and abs(exit_price - initial_tp) < 0.50) or
                                profit_points >= tp_pts_stored * 0.80
                            )
                            profit_lock_hit = (
                                profit_lock_sl is not None and (
                                    (direction == 'BUY'  and exit_price <= profit_lock_sl + 1.0) or
                                    (direction == 'SELL' and exit_price >= profit_lock_sl - 1.0)
                                )
                            )
                            # Trail SL: exit near or past the trail level (slippage can carry
                            # price well beyond the SL on fast spikes — use 1.0 pt tolerance).
                            trail_hit = (
                                trail_sl is not None and (
                                    (direction == 'BUY'  and exit_price <= trail_sl + 1.0) or
                                    (direction == 'SELL' and exit_price >= trail_sl - 1.0)
                                )
                            )
                            if tp_hit:
                                exit_condition = "Dynamic TP"
                            elif profit_lock_hit:
                                exit_condition = "Profit Lock"
                            elif trail_hit:
                                exit_condition = "Trailing SL"
                            else:
                                exit_condition = "Hard SL"

                        peak      = pos_data.get('peak_profit', 0.0)
                        v_entry   = pos_data.get('entry_velocity', 0.0)
                        tp_target = pos_data.get('initial_tp_pts', 0.0)

                        journal_data = {
                            'ticket': ticket,
                            'entry_time': pos_data.get('entry_time', datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S"),
                            'exit_time': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'sl': (
                                pos_data.get('trail_sl_price') or
                                pos_data.get('price_lock_sl_price') or
                                pos_data.get('hard_sl_price') or
                                pos_data.get('initial_sl', 0.0)
                            ),
                            'tp': pos_data.get('initial_tp_pts', 0.0),
                            'entry_velocity': v_entry,
                            'exit_reason': exit_condition,
                            'profit_points': round(float(profit_points or 0), 2),
                            'profit_dollars': round(float(profit_dollars or 0), 2),
                            'result': "WIN" if profit_points > 0 else "LOSS",
                            'volume': volume
                        }
                        self.save_to_journal(journal_data)
                        self.db.save_trade(journal_data)

                        self.last_candle_trade = {
                            'direction': direction,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'profit_points': profit_points
                        }

                        db_stats = self.db.get_stats(date_filter="today")
                        if db_stats and db_stats['total_trades'] > 0:
                            today_trades  = db_stats['total_trades']
                            today_wr      = db_stats['win_rate']
                            today_profit  = db_stats['total_profit']
                        else:
                            today_trades  = total_closed
                            today_wr      = win_rate
                            today_profit  = self.total_profit

                        self.formatter.print_trade_exit_with_condition(
                            direction, entry_price, exit_price, duration, ticket,
                            today_trades, today_wr, self.session_capital, today_profit, exit_condition,
                            trade_profit=profit_dollars, v_entry=v_entry, tp_target=tp_target, peak=peak
                        )

                        if db_stats:
                            self.formatter.print_database_stats(db_stats, is_today=True)

                        self.total_trades_today += 1
                        if profit_points > 0:
                            self.log(f"✅ PROFITABLE EXIT: {direction} at {exit_price:.2f} (+{profit_points:.2f}pts)", Colors.GREEN)
                            self.consec_losses = 0   # FIX #6: reset streak on any win
                            self.last_exit_price  = exit_price
                            self.last_exit_result = "WIN"
                        elif profit_points < -0.01:
                            self.losses_this_candle += 1
                            self.consec_losses += 1   # FIX #6: track streak
                            self.log(f"🚫 LOSS #{self.losses_this_candle}/{MAX_LOSSES_PER_CANDLE} this candle | Consec: {self.consec_losses}/{MAX_CONSEC_LOSSES}", Colors.ORANGE)
                            if self.consec_losses >= MAX_CONSEC_LOSSES:
                                self.candles_to_pause = LOSS_PAUSE_CANDLES
                                self.log(f"🚨 CONSEC_LOSS_LIMIT HIT ({self.consec_losses}) — pausing entries for {LOSS_PAUSE_CANDLES} candles", Colors.RED)
                            self.last_exit_price  = exit_price
                            self.last_exit_result = "LOSS"

                        del self.position_data[ticket]

                previous_positions = current_tickets

                if current_positions:
                    self.check_exit_conditions(tick, analysis, current_positions)
                    # Refresh after exit checks — a position may have just been closed
                    current_positions = mt5.positions_get(symbol=self.symbol) or ()

                    # ── SCALE-IN MONITOR ──
                    for pos in current_positions:
                        if pos.ticket not in self.scaled_in_tickets and pos.ticket in self.position_data:
                            pos_data = self.position_data[pos.ticket]
                            profit_pts = pos_data.get('last_profit_pts', 0)
                            if profit_pts >= 1.00:
                                current_live_count = len(mt5.positions_get(symbol=self.symbol) or ())
                                if current_live_count < MAX_SIMULTANEOUS_POSITIONS:
                                    self.execute_scale_in(pos, pos_data, tick, current_live_count, analysis)
                                self.scaled_in_tickets.add(pos.ticket)
                                break  # Only scale in once per tick to avoid double-firing

                # Check for News Block (but allow exits)
                is_news_blocked, news_title = self.news_filter.is_news_block_active()

                # Allow entry even with open positions (up to MAX_SIMULTANEOUS_POSITIONS)
                # but enforce a 2-second gap after the last entry, and require price
                # to have moved at least 0.30 pts favorably past the last entry price
                ticks_since_last_entry = self.loop_count - self.last_entry_tick
                time_since_last_entry  = time.time() - self.last_entry_time
                price_moved_ok = True
                if self.last_entry_price and self.last_entry_dir:
                    if self.last_entry_dir == 'BUY':
                        price_moved_ok = tick.bid >= self.last_entry_price - 0.10
                    else:
                        price_moved_ok = tick.bid <= self.last_entry_price + 0.10

                # Post-exit re-entry guard
                re_entry_ok = True
                candle_open = analysis.get('open', 0.0)
                curr_candle_color = analysis.get('candle_color', 'UNKNOWN')

                # Track the opening color of this candle (set once on first tick)
                if not getattr(self, 'candle_open_color', None) and curr_candle_color in ('GREEN', 'RED'):
                    self.candle_open_color = curr_candle_color

                # Candle color reversal bypass: if candle has completely flipped from its
                # opening color, clear any sequencer block (WIN exit guard or LOSS guard)
                candle_reversed = (
                    self.candle_open_color == 'RED'  and curr_candle_color == 'GREEN' or
                    self.candle_open_color == 'GREEN' and curr_candle_color == 'RED'
                )

                if not candle_reversed:
                    if self.last_exit_result == "WIN" and self.last_exit_price is not None:
                        if self.last_entry_dir == 'BUY' and tick.bid <= self.last_exit_price:
                            re_entry_ok = False
                        elif self.last_entry_dir == 'SELL' and tick.bid >= self.last_exit_price:
                            re_entry_ok = False
                    elif self.last_exit_result == "LOSS" and candle_open > 0:
                        if self.last_entry_dir == 'BUY' and tick.bid <= candle_open:
                            re_entry_ok = False
                        elif self.last_entry_dir == 'SELL' and tick.bid >= candle_open:
                            re_entry_ok = False
                else:
                    # Log once when the bypass first activates (there was an active block to clear)
                    if self.last_exit_result in ("WIN", "LOSS") and not getattr(self, '_reversal_override_logged', False):
                        self.log(
                            f"🔄 CANDLE REVERSAL OVERRIDE — {self.candle_open_color}→{curr_candle_color} bypass sequencer block",
                            self.Colors.CYAN
                        )
                        self._reversal_override_logged = True

                if not re_entry_ok:
                    self.entry_block_reasons["SEQUENCE_GUARD"] += 1

                if len(current_positions) < self.max_simultaneous and ticks_since_last_entry >= 1 and time_since_last_entry >= 0.5 and price_moved_ok and re_entry_ok and self.losses_this_candle < MAX_LOSSES_PER_CANDLE:
                    if is_news_blocked:
                        if self.loop_count % 15 == 0:
                            self.log(f"⏸ NEWS BLOCK ACTIVE: {news_title} (Entries Paused)", self.Colors.YELLOW)
                    else:
                        # ── SESSION HOURS GATE ────────────────────────────────────────
                        # Block NEW entries outside configured session window.
                        # Exits on open positions are always allowed regardless of session.
                        _can_enter = True
                        if getattr(config, 'ENABLE_SESSION_FILTER', False) and not current_positions:
                            _utc_hour   = datetime.now(timezone.utc).hour
                            _sess_start = getattr(config, 'SESSION_START_HOUR_UTC', 7)
                            _sess_end   = getattr(config, 'SESSION_END_HOUR_UTC', 21)
                            if not (_sess_start <= _utc_hour < _sess_end):
                                _can_enter = False
                                if self.loop_count % 60 == 0:
                                    self.log(
                                        f"⏸ SESSION FILTER: Outside trading hours "
                                        f"(UTC {_utc_hour:02d}:xx — allowed {_sess_start:02d}:00–{_sess_end:02d}:00)",
                                        self.Colors.YELLOW
                                    )

                        if _can_enter:
                            entry_signal, entry_type = self.check_entry_conditions(tick, analysis, current_positions)
                            analysis['last_entry_type'] = entry_type
                            if entry_signal in ["BUY", "SELL"]:
                                if self.execute_entry(entry_signal, tick, analysis, entry_type=entry_type):
                                    self.last_entry_tick  = self.loop_count
                                    self.last_entry_time  = time.time()
                                    self.last_entry_price = tick.ask if entry_signal == "BUY" else tick.bid
                                    self.last_entry_dir   = entry_signal

                try:
                    import json
                    import os
                    
                    st_str = "WAITING"
                    if analysis.get('is_higher'): st_str = "BUY"
                    elif analysis.get('is_lower'): st_str = "SELL"
                    
                    bb_ang = analysis.get("bb_angle", 0.0)
                    if bb_ang is None: bb_ang = 0.0
                    
                    market_state = {
                        "supertrend": st_str,
                        "bb_angle": round(float(bb_ang), 2),
                        "timeframe": self.timeframe,
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    with open(os.path.join(base_dir, "market_state.json"), "w") as f:
                        json.dump(market_state, f)
                        
                    active_trades_list = []
                    if current_positions:
                        for p in current_positions:
                            direction = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
                            profit = p.profit
                            profit_pts = (p.price_current - p.price_open) if direction == 'BUY' else (p.price_open - p.price_current)
                            active_trades_list.append({
                                "ticket": p.ticket,
                                "direction": direction,
                                "entry_price": p.price_open,
                                "current_price": p.price_current,
                                "profit_points": profit_pts,
                                "profit_dollars": profit,
                                "volume": p.volume,
                                "bb_angle": round(float(bb_ang), 2),
                                "supertrend": st_str,
                                "sl": p.sl,
                                "tp": p.tp,
                                "open_time": p.time,
                                "spread": 0
                            })
                    with open(os.path.join(base_dir, "active_trade.json"), "w") as f:
                        json.dump(active_trades_list, f)
                except Exception as ex:
                    print(f"Error writing live state: {ex}")

                time.sleep(0.05 if current_positions else 0.3)

        except KeyboardInterrupt:
            today = self.db.get_stats(date_filter="today")
            if today and today['total_trades'] > 0:
                self.log(f">> Bot stopped | Today — Trades:{today['total_trades']} W:{today['winning_trades']} L:{today['losing_trades']} WR:{today['win_rate']:.1f}% P&L:${today['total_profit']:.2f}", Colors.YELLOW)
            else:
                self.log(">> Bot stopped | No trades today.", Colors.YELLOW)

        except Exception as e:
            self.log(f">> Critical error: {e}", Colors.RED)
        finally:
            mt5.shutdown()

    def execute_scale_in(self, parent_pos, parent_data, tick, current_live_count, analysis):
        scale_vol = getattr(config, 'LOT_SIZE', 0.10)
        parent_vol = round(parent_pos.volume, 2)
        signal = "BUY" if parent_pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        
        self.log(f"⚖️ Scale-In Lot Sizing (Trade {current_live_count + 1}) → Lot: {scale_vol:.2f}", self.Colors.CYAN)
        self.log(f"📈 SCALE-IN TRIGGERED: {signal} at +1.00 pt profit. Parent Vol:{parent_vol} → Scale Vol:{scale_vol}", self.Colors.CYAN)
        
        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        entry_price = tick.ask if signal == "BUY" else tick.bid
        
        symbol_info = mt5.symbol_info(self.symbol)
        filling_mode = symbol_info.filling_mode
        if filling_mode & 1:   type_filling = 0
        elif filling_mode & 2: type_filling = 1
        else:                  type_filling = 2
        
        tick_size = symbol_info.trade_tick_size
        hard_sl = round((entry_price - 2.00 if signal == "BUY" else entry_price + 2.00) / tick_size) * tick_size
        
        dynamic_tp = parent_data.get('initial_tp_pts', 3.00)
        broker_tp = round((entry_price + dynamic_tp if signal == "BUY" else entry_price - dynamic_tp) / tick_size) * tick_size
        
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
            self.log(f"🚫 SCALE-IN FAILED: {result.comment}", self.Colors.RED)
            return False
            
        self.log(f"✅ SCALE-IN EXECUTED: {signal} {scale_vol} lots @ {result.price}", self.Colors.GREEN)
        
        self.position_data[result.order] = {
            'entry_time': datetime.now(timezone.utc),
            'direction': signal,
            'entry_price': result.price,
            'initial_sl': hard_sl,
            'hard_sl_price': hard_sl,
            'initial_tp': broker_tp,
            'initial_tp_pts': dynamic_tp,
            'trail_sl_price': None,
            'price_lock_sl_price': None,
            'peak_profit': 0.0,
            'last_profit_pts': 0.0,
            'entry_velocity': parent_data.get('entry_velocity', 0.0),
            'volume': scale_vol
        }
        self.scaled_in_tickets.add(result.order) # don't scale-in off a scale-in
        self.trades_this_candle += 1
        return True

def main():
    if not MT5Connection.initialize_mt5():
        return
    TradingBot("XAUUSD", "M5").run()

if __name__ == "__main__":
    main()
