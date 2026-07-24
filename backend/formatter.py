from config import ENTRY_VEL_FRESH, ENTRY_AVG_FRESH, MIN_ENTRY_2S_VEL
import os
import sys
from datetime import datetime
import MetaTrader5 as mt5


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    ORANGE = "\033[38;5;208m"

    @staticmethod
    def get_candle_color(candle_type):
        return Colors.GREEN if candle_type == "GREEN" else Colors.RED


class TerminalFormatter:
    def __init__(self):
        os.environ["FORCE_COLOR"] = "1"
        os.environ["TERM"] = "xterm-256color"

        # Reconfigure stdout/stderr to UTF-8 to prevent UnicodeEncodeError on Windows
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        self.CYAN = "\033[96m"
        self.GREEN = "\033[92m"
        self.RED = "\033[91m"
        self.YELLOW = "\033[93m"
        self.MAGENTA = "\033[95m"
        self.WHITE = "\033[97m"
        self.RESET = "\033[0m"
        self.BOLD = "\033[1m"

    def _box(self, title, rows, color, W=52):
        inner = W - 6
        c = color
        R = self.RESET
        B = self.BOLD
        top = c + "╔" + "═" * (W - 2) + "╗" + R
        mid = c + "╠" + "═" * (W - 2) + "╣" + R
        sgl = c + "╟" + "─" * (W - 2) + "╢" + R
        bot = c + "╚" + "═" * (W - 2) + "╝" + R

        def L(visible, colored=None):
            if colored is None:
                colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad,0)}  {c}║{R}"

        print(f"\n{top}")
        print(L(title, f"{B}{self.WHITE}{title}{R}"))
        for item in rows:
            if item == "---":
                print(sgl)
            elif item == "===":
                print(mid)
            else:
                visible, colored = item if isinstance(item, tuple) else (item, item)
                print(L(visible, colored))
        print(f"{bot}{R}\n")

    def print_trade_entry(
        self,
        trade_type,
        entry_price,
        volume,
        sl,
        tp,
        ticket,
        conditions,
        capital,
        trades_today,
        risk_pts,
        score=None,
    ):
        ts = datetime.now().strftime("%H:%M:%S")
        vel = conditions.split("| V: ")[1] if "| V: " in conditions else "N/A"
        G = self.GREEN
        R = self.RESET
        B = self.BOLD
        d_color = G if trade_type == "BUY" else self.RED

        self._box(
            f"TRADE ENTERED  #{ticket}",
            [
                (
                    f"Type: {trade_type}     Time: {ts}",
                    f"Type: {d_color}{B}{trade_type}{R}     Time: {ts}",
                ),
                (
                    f"Entry: {entry_price:.2f}     Lot: {volume:.2f}",
                    f"Entry: {B}{entry_price:.2f}{R}     Lot: {volume:.2f}",
                ),
                "---",
                (
                    f"TP:  {tp:.2f}     SL:  {sl:.2f}",
                    f"TP:  {G}{tp:.2f}{R}     SL:  {self.RED}{sl:.2f}{R}",
                ),
                (
                    f"Risk: {risk_pts:.2f} pts",
                    f"Risk: {self.YELLOW}{risk_pts:.2f} pts{R}",
                ),
                "---",
                (f"Velocity: {vel}", f"Velocity: {vel}"),
                (
                    f"Trades: {trades_today}     Balance: ${capital:,.0f}",
                    f"Trades: {B}{trades_today}{R}     Balance: ${capital:,.0f}",
                ),
            ],
            self.CYAN,
        )

        if score:
            import backend.config as config
            w_m = getattr(config, "WEIGHT_MOMENTUM", 1.0)
            w_t = getattr(config, "WEIGHT_TREND", 1.0)
            w_c = getattr(config, "WEIGHT_CANDLE", 1.0)
            w_e = getattr(config, "WEIGHT_EXECUTION", 1.0)
            
            self._box(
                f"SETUP SCORE: {score.total:.1f}",
                [
                    (
                        f"Momentum:  {score.momentum:.1f} / {50.0 * w_m:.1f}",
                        f"Momentum:  {B}{score.momentum:.1f}{R} / {50.0 * w_m:.1f}",
                    ),
                    (
                        f"Trend:     {score.trend:.1f} / {20.0 * w_t:.1f}",
                        f"Trend:     {B}{score.trend:.1f}{R} / {20.0 * w_t:.1f}",
                    ),
                    (
                        f"Candle:    {score.candle:.1f} / {20.0 * w_c:.1f}",
                        f"Candle:    {B}{score.candle:.1f}{R} / {20.0 * w_c:.1f}",
                    ),
                    (
                        f"Execution: {score.execution:.1f} / {15.0 * w_e:.1f}",
                        f"Execution: {B}{score.execution:.1f}{R} / {15.0 * w_e:.1f}",
                    ),
                ],
                self.MAGENTA,
            )

    def print_news_calendar(self, events):
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc)

        B = self.BOLD
        R = self.RESET
        Y = self.YELLOW
        G = self.GREEN

        rows = []
        if not events:
            rows.append(
                (
                    "No High-Impact USD News This Week",
                    f"{G}{B}No High-Impact USD News This Week{R}",
                )
            )
        else:
            sorted_events = sorted(events, key=lambda x: x["time"])
            from datetime import timedelta
            ist_tz = timezone(timedelta(hours=5, minutes=30))

            header_vis = f"{'DATE/TIME':<13} {'IMP':<4} {'EVENT':<28} {'FCST':<6} {'PREV':<6} {'STATUS'}"
            header_col = f"{B}{self.WHITE}{'DATE/TIME':<13} {'IMP':<4} {'EVENT':<28} {'FCST':<6} {'PREV':<6} {'STATUS'}{R}"
            rows.append((header_vis, header_col))
            rows.append("---")

            for e in sorted_events:
                local_time = e["time"].astimezone(ist_tz).strftime("%b %d %H:%M")
                title = e.get("title", "News Event")
                if len(title) > 26:
                    title = title[:24] + ".."
                
                impact = e.get("impact", "LOW")
                if impact.upper() == "HIGH":
                    imp_col = f"{self.RED}{'HIGH':<4}{R}"
                    imp_vis = "HIGH"
                elif impact.upper() == "MEDIUM":
                    imp_col = f"{self.YELLOW}{'MED':<4}{R}"
                    imp_vis = "MED "
                else:
                    imp_col = f"{self.CYAN}{'LOW':<4}{R}"
                    imp_vis = "LOW "

                fcst = str(e.get("forecast", "")) or "-"
                prev = str(e.get("previous", "")) or "-"

                if len(fcst) > 6: fcst = fcst[:6]
                if len(prev) > 6: prev = prev[:6]

                if e["time"] < now_utc:
                    status_col = f"{self.CYAN}[PASSED]{R}"
                    status_vis = "[PASSED]"
                else:
                    mins_away = int((e["time"] - now_utc).total_seconds() / 60)
                    if mins_away <= 60:
                        status_col = f"{self.RED}[{mins_away}m]{R}"
                        status_vis = f"[{mins_away}m]"
                    else:
                        hours = mins_away // 60
                        days = hours // 24
                        if days > 0:
                            status_col = f"{self.YELLOW}[{days}d {hours%24}h]{R}"
                            status_vis = f"[{days}d {hours%24}h]"
                        else:
                            status_col = f"{self.YELLOW}[{hours}h]{R}"
                            status_vis = f"[{hours}h]"

                vis_str = f"{local_time:<13} {imp_vis:<4} {title:<28} {fcst:<6} {prev:<6} {status_vis}"
                col_str = f"{Y}{local_time:<13}{R} {imp_col} {title:<28} {fcst:<6} {prev:<6} {status_col}"
                rows.append((vis_str, col_str))

        self._box("THIS WEEK'S ECONOMIC CALENDAR", rows, self.YELLOW, W=82)

    def print_trade_exit_with_condition(
        self,
        direction,
        entry_price,
        exit_price,
        duration,
        ticket,
        total_closed,
        win_rate,
        capital,
        total_profit,
        exit_condition,
        trade_profit=0.0,
        v_entry=0.0,
        tp_target=2.0,
        peak=0.0,
    ):
        profit_pts = (
            (exit_price - entry_price)
            if direction == "BUY"
            else (entry_price - exit_price)
        )
        is_win = profit_pts >= 0
        c = self.GREEN if is_win else self.RED
        result = "WIN" if is_win else "LOSS"
        p_color = self.GREEN if profit_pts >= 0 else self.RED
        wr_color = (
            self.GREEN
            if win_rate >= 60
            else self.YELLOW if win_rate >= 45 else self.RED
        )
        R = self.RESET
        B = self.BOLD
        d_color = self.GREEN if direction == "BUY" else self.RED

        self._box(
            f"TRADE CLOSED  #{ticket}  [{result}]",
            [
                (
                    f"Dir: {direction}     Duration: {duration}",
                    f"Dir: {d_color}{B}{direction}{R}     Duration: {duration}",
                ),
                (
                    f"Entry: {entry_price:.2f}  ->  Exit: {exit_price:.2f}",
                    f"Entry: {entry_price:.2f}  ->  Exit: {B}{exit_price:.2f}{R}",
                ),
                (
                    f"P/L: {profit_pts:+.2f} pts    (${trade_profit:+.2f})",
                    f"P/L: {p_color}{B}{profit_pts:+.2f} pts{R}    {p_color}(${trade_profit:+.2f}){R}",
                ),
                "---",
                (f"Reason: {exit_condition}", f"Reason: {exit_condition}"),
                (
                    f"Peak: {peak:+.2f} pts     Vel: {v_entry:+.2f}",
                    f"Peak: {peak:+.2f} pts     Vel: {v_entry:+.2f}",
                ),
                "===",
                (
                    f"Trades: {total_closed}   WR: {win_rate:.1f}%   Session: ${total_profit:+.2f}",
                    f"Trades: {B}{total_closed}{R}   WR: {wr_color}{B}{win_rate:.1f}%{R}   Session: ${total_profit:+.2f}",
                ),
            ],
            c,
        )

    def print_database_stats(self, db_stats, is_today=False):
        if not db_stats:
            return

        total = db_stats.get("total_trades", 0)
        if total == 0:
            print(
                f"\nNo trades found for {db_stats.get('date_filter', 'this period')}."
            )
            return

        wr = db_stats.get("win_rate", 0.0)
        wins = db_stats.get("winning_trades", 0)
        losses = db_stats.get("losing_trades", 0)
        gross_p = db_stats.get("gross_profit", 0.0)
        gross_l = db_stats.get("total_losses", 0.0)
        net = db_stats.get("total_profit", 0.0)
        avg_win = db_stats.get("avg_win", 0.0)
        avg_loss = db_stats.get("avg_loss", 0.0)
        reward_to_risk = db_stats.get("reward_to_risk", 0.0)

        wr_color = self.GREEN if wr >= 60 else self.YELLOW if wr >= 45 else self.RED
        net_color = self.GREEN if net >= 0 else self.RED
        net_label = "PROFIT" if net >= 0 else "LOSS"

        filled = int(wr / 100 * 24)
        bar_plain = "█" * filled + "░" * (24 - filled)
        bar_color = (
            self.GREEN + "█" * filled + self.RED + "░" * (24 - filled) + self.RESET
        )

        if is_today:
            date_str = db_stats.get("date_filter") or datetime.now().strftime(
                "%Y-%m-%d"
            )
            title = f"TODAY'S STATS  ({date_str})"
        elif db_stats.get("date_filter"):
            title = f"STATS FOR {db_stats['date_filter']}"
        else:
            title = "LIFETIME STATS"

        W = 52
        inner = W - 6  # usable text width = 48
        c = self.CYAN
        R = self.RESET
        B = self.BOLD

        top = c + "╔" + "═" * (W - 2) + "╗" + R
        mid = c + "╠" + "═" * (W - 2) + "╣" + R
        bot = c + "╚" + "═" * (W - 2) + "╝" + R

        # Build a line: visible = plain text (for length), colored = ansi version
        def L(visible, colored=None):
            if colored is None:
                colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad, 0)}  {c}║{R}"

        print(f"\n{top}")
        print(L(title, f"{B}{self.WHITE}{title}{R}"))
        print(mid)
        print(L(f"Total Trades    {total}", f"Total Trades    {B}{total}{R}"))
        print(
            L(
                f"Wins  {wins}    Losses  {losses}",
                f"Wins  {self.GREEN}{B}{wins}{R}    Losses  {self.RED}{B}{losses}{R}",
            )
        )
        print(L(f"Win Rate  {wr:.1f}%", f"Win Rate  {wr_color}{B}{wr:.1f}%{R}"))
        print(L(f"  {bar_plain}", f"  {bar_color}"))
        print(mid)
        print(
            L(
                f"Gross Profit    ${gross_p:>+,.2f}",
                f"Gross Profit    {self.GREEN}${gross_p:>+,.2f}{R}",
            )
        )
        print(
            L(
                f"Gross Losses    -${gross_l:>,.2f}",
                f"Gross Losses    {self.RED}-${gross_l:>,.2f}{R}",
            )
        )
        print(
            L(
                f"Avg Win         ${avg_win:>,.2f}",
                f"Avg Win         {self.GREEN}${avg_win:>,.2f}{R}",
            )
        )
        print(
            L(
                f"Avg Loss        -${avg_loss:>,.2f}",
                f"Avg Loss        {self.RED}-${avg_loss:>,.2f}{R}",
            )
        )
        print(
            L(
                f"Reward/Risk     {reward_to_risk:>.2f}:1",
                f"Reward/Risk     {self.YELLOW}{reward_to_risk:>.2f}:1{R}",
            )
        )
        print(mid)
        net_vis = f"Net P&L    ${net:>+,.2f}    [{net_label}]"
        net_col = f"{B}Net P&L    {net_color}${net:>+,.2f}{R}    {net_color}{B}[{net_label}]{R}"
        print(L(net_vis, net_col))
        print(f"{bot}\n")

    def print_startup(self, symbol, timeframe, balance, currency, stops_level, point):
        W = 52
        inner = W - 6
        c = self.CYAN
        R = self.RESET
        B = self.BOLD
        G = self.GREEN

        top = c + "╔" + "═" * (W - 2) + "╗" + R
        mid = c + "╠" + "═" * (W - 2) + "╣" + R
        bot = c + "╚" + "═" * (W - 2) + "╝" + R

        def L(visible, colored=None):
            if colored is None:
                colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad,0)}  {c}║{R}"

        title = "XAUUSD MOMENTUM SCALPING BOT"
        bal_str = f"${balance:,.2f} {currency}"

        print(f"\n{top}")
        print(L(title, f"{B}{self.WHITE}{title}{R}"))
        print(mid)
        print(
            L(
                f"Symbol      {symbol}    Timeframe  {timeframe}",
                f"Symbol      {G}{B}{symbol}{R}    Timeframe  {G}{B}{timeframe}{R}",
            )
        )
        print(L(f"Balance     {bal_str}", f"Balance     {G}{B}{bal_str}{R}"))
        print(
            L(
                f"Stops Level {stops_level}    Point      {point}",
                f"Stops Level {stops_level}    Point      {point}",
            )
        )
        print(L("Status      Connected to MT5", f"Status      {G}Connected to MT5{R}"))
        print(f"{bot}\n")

    def print_tick_context(self, label, ticks, direction):
        if not ticks:
            return
        W = 52
        inner = W - 6
        c = self.CYAN if "PRE" in label else self.YELLOW
        d_c = self.GREEN if direction == "BUY" else self.RED
        R = self.RESET
        B = self.BOLD
        top = c + "╔" + "═" * (W - 2) + "╗" + R
        bot = c + "╚" + "═" * (W - 2) + "╝" + R
        sgl = c + "╟" + "─" * (W - 2) + "╢" + R

        def L(visible, colored=None):
            if colored is None:
                colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad,0)}  {c}║{R}"

        title = f"{'PRE' if 'PRE' in label else 'POST'}-ENTRY  {direction}  ({len(ticks)} ticks)"
        print(f"\n{top}")
        print(L(title, f"{B}{d_c}{title}{R}"))
        print(sgl)
        for i, t in enumerate(ticks):
            avg_str = f"{t['avg_vel']:+.2f}" if t["avg_vel"] is not None else " N/A"
            ts = datetime.fromtimestamp(t["time"]).strftime("%H:%M:%S.%f")[:-4]
            vis = (
                f"[{i+1:02d}] {ts}  {t['bid']:.2f}  v:{t['velocity']:+.3f}  a:{avg_str}"
            )
            print(L(vis))
        print(f"{bot}{R}\n")

    def print_tick_status(self, bot, tick, analysis, positions):
        time_str = datetime.now().strftime("%H:%M:%S")

        candle_open_time = analysis.get("time", 0)
        seconds_into_candle = (
            int(tick.time) - int(candle_open_time) if candle_open_time else 0
        )

        curr_candle = analysis.get("current_candle", "")

        cc_color = Colors.get_candle_color(curr_candle)

        prev_body = analysis.get("prev_body", 0.0)
        is_lower = analysis.get("is_lower", False)
        is_higher = analysis.get("is_higher", False)

        current_open = analysis.get("open", tick.bid)
        current_body = (
            tick.bid - current_open
            if tick.bid > current_open
            else current_open - tick.bid
        )

        if not is_higher and not is_lower:
            if current_body >= 0.70:
                if tick.bid > current_open:
                    is_higher = True
                elif tick.bid < current_open:
                    is_lower = True

        seq_status = (
            "HIGH" if is_higher else "LOW" if is_lower else f"MIX({bot.last_trend})"
        )
        seq_color = (
            Colors.GREEN if is_higher else Colors.RED if is_lower else Colors.YELLOW
        )

        is_mixed = not is_higher and not is_lower
        avg_v_raw = analysis.get("avg_velocity")
        vsm = analysis.get("velocity", 0.0)
        velocity_2s = analysis.get("velocity_2s", 0.0)
        velocity_2s_ready = analysis.get("velocity_2s_ready", False)
        current_open = analysis.get("open", tick.bid)



        tf_secs = 300
        if bot.timeframe == "M1":
            tf_secs = 60
        elif bot.timeframe == "M5":
            tf_secs = 300
        elif bot.timeframe == "M15":
            tf_secs = 900
        elif bot.timeframe == "M30":
            tf_secs = 1800

        if bot.timeframe == "M1":
            start_window = 5
            end_window = tf_secs - 5
        else:
            start_window = 15
            end_window = tf_secs - 20

        if positions:
            pos = positions[0]
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            profit_pts = (
                (tick.bid - pos.price_open)
                if direction == "BUY"
                else (pos.price_open - tick.ask)
            )
            profit_val = profit_pts * pos.volume * bot.contract_size
            p_color = Colors.GREEN if profit_val >= 0 else Colors.RED
            status = f"{Colors.BOLD}{direction}{Colors.RESET} {p_color}${profit_val:+.2f}{Colors.RESET}"
        else:
            if seconds_into_candle < start_window:
                status = f"{Colors.GREEN}WAITING FOR CANDLE START ({start_window - seconds_into_candle}s){Colors.RESET}"
            elif seconds_into_candle > end_window:
                status = f"{Colors.YELLOW}TIME WINDOW CLOSED ({max(0, tf_secs - seconds_into_candle)}s){Colors.RESET}"
            elif bot.trades_this_candle >= bot.max_trades_candle:
                status = f"{Colors.YELLOW}TRADE DONE THIS CANDLE ({bot.trades_this_candle}/{bot.max_trades_candle}){Colors.RESET}"
            elif is_mixed:
                status = ""
            elif curr_candle == "GREEN":
                _v_req = ENTRY_VEL_FRESH
                _a_req = ENTRY_AVG_FRESH
                _vel_ok = abs(vsm) >= _v_req
                _avg_ok = avg_v_raw is not None and abs(avg_v_raw) >= _a_req

                score = bot.strategy.calculate_momentum_score("BUY", tick, analysis, {})
                block = score.block_reason

                if not _vel_ok:
                    status = f"{Colors.CYAN}BUY  vel:{abs(vsm):.2f} < {_v_req}{Colors.RESET}"
                elif not velocity_2s_ready:
                    status = f"{Colors.ORANGE}BUY  2s not ready{Colors.RESET}"
                elif abs(velocity_2s) < MIN_ENTRY_2S_VEL:
                    status = f"{Colors.ORANGE}BUY  2s:{abs(velocity_2s):.2f} < {MIN_ENTRY_2S_VEL:.2f}{Colors.RESET}"
                elif not _avg_ok:
                    status = f"{Colors.YELLOW}BUY  avg:{abs(avg_v_raw):.2f} < {_a_req}{Colors.RESET}"
                elif block:
                    status = f"{Colors.YELLOW}BUY  ✓ vel:{abs(vsm):.2f} avg:{abs(avg_v_raw):.2f} {Colors.RED}[{block}]{Colors.RESET}"
                else:
                    status = f"{Colors.CYAN}BUY  ✓ vel:{abs(vsm):.2f} avg:{abs(avg_v_raw):.2f}{Colors.RESET}"

            elif curr_candle == "RED":
                _v_req = ENTRY_VEL_FRESH
                _a_req = ENTRY_AVG_FRESH
                _vel_ok = abs(vsm) >= _v_req
                _avg_ok = avg_v_raw is not None and abs(avg_v_raw) >= _a_req

                score = bot.strategy.calculate_momentum_score("SELL", tick, analysis, {})
                block = score.block_reason

                if not _vel_ok:
                    status = f"{Colors.MAGENTA}SELL vel:{abs(vsm):.2f} < {_v_req}{Colors.RESET}"
                elif not velocity_2s_ready:
                    status = f"{Colors.ORANGE}SELL 2s not ready{Colors.RESET}"
                elif abs(velocity_2s) < MIN_ENTRY_2S_VEL:
                    status = f"{Colors.ORANGE}SELL 2s:{abs(velocity_2s):.2f} < {MIN_ENTRY_2S_VEL:.2f}{Colors.RESET}"
                elif not _avg_ok:
                    status = f"{Colors.YELLOW}SELL avg:{abs(avg_v_raw):.2f} < {_a_req}{Colors.RESET}"
                elif block:
                    status = f"{Colors.YELLOW}SELL ✓ vel:{abs(vsm):.2f} avg:{abs(avg_v_raw):.2f} {Colors.RED}[{block}]{Colors.RESET}"
                else:
                    status = f"{Colors.MAGENTA}SELL ✓ vel:{abs(vsm):.2f} avg:{abs(avg_v_raw):.2f}{Colors.RESET}"
            else:
                status = f"{Colors.YELLOW}Wait: No Direction{Colors.RESET}"

        avg_v_str = f"{avg_v_raw:+.2f}" if avg_v_raw is not None else " N/A"
        v_color = Colors.GREEN if vsm >= 0 else Colors.RED


        arrow = "" if curr_candle == "GREEN" else "" if curr_candle == "RED" else "─"

        T = Colors.RESET
        DIM = "\033[2m"

        time_display = f"{DIM}{time_str}{T}"

        m, s = divmod(seconds_into_candle, 60)
        candle_time_str = f"{m:02d}:{s:02d}/{tf_secs//60:02d}:{tf_secs%60:02d}"
        if seconds_into_candle >= (tf_secs - 20):
            time_color = Colors.RED
        else:
            time_color = Colors.GREEN

        # Display components
        tick_display = f"{time_color}{Colors.BOLD}[{candle_time_str}]{T}"
        price_display = f"{cc_color}{Colors.BOLD}{tick.bid:.2f}{T}"
        candle_display = f"{cc_color}{arrow} {curr_candle:<5}{T}"
        sequence_display = f"{seq_color}{seq_status:<9}{T}"
        prev_body_display = f"{DIM}PB{T}:{Colors.BOLD}{prev_body:.2f}{T}"
        velocity_display = f"{DIM}V{T}:{v_color}{vsm:+.2f}{T} {DIM}A{T}:{avg_v_str}"
        trend_color = (
            Colors.GREEN
            if bot.last_trend == "UP"
            else Colors.RED if bot.last_trend == "DOWN" else Colors.YELLOW
        )
        display_trend = "SIDE" if bot.last_trend == "NONE" else bot.last_trend
        
        ema_angle = analysis.get("ema_9_angle", 0.0) if analysis else 0.0
        angle_color = Colors.GREEN if ema_angle >= 10 else Colors.RED if ema_angle <= -10 else Colors.YELLOW
        
        indicators_display = f"{DIM}TR:{T}{trend_color}{display_trend:<4}{T} {DIM}EMA∠:{T}{angle_color}{ema_angle:+.1f}°{T}"

        # Score display removed since momentum scoring is disabled

        print(
            f"{time_display}  {tick_display}  {price_display}  {candle_display}  {sequence_display}  {prev_body_display}  {indicators_display}  {velocity_display}  {status}"
        )

    def print_candle_movement(self, timeframe, candle_range, body_size, o, h, l, c, block_reason):
        title = f"{timeframe} CANDLE COMPLETED"
        rows = [
            (
                f"Total Movement: ${candle_range:.2f}",
                f"Total Movement: {self.BOLD}${candle_range:.2f}{self.RESET}"
            ),
            (
                f"Body Size:      ${body_size:.2f}",
                f"Body Size:      {self.BOLD}${body_size:.2f}{self.RESET}"
            ),
            "---",
            (
                f"O: {o:.2f}  H: {h:.2f}  L: {l:.2f}  C: {c:.2f}",
                f"O:{self.BOLD}{o:.2f}{self.RESET}  H:{self.BOLD}{h:.2f}{self.RESET}  L:{self.BOLD}{l:.2f}{self.RESET}  C:{self.BOLD}{c:.2f}{self.RESET}"
            ),
            "---",
            (
                f"Status: {block_reason}",
                f"Status: {self.YELLOW}{block_reason}{self.RESET}" if block_reason != "Trades Taken" else f"Status: {self.GREEN}{block_reason}{self.RESET}"
            )
        ]
        self._box(title, rows, self.MAGENTA)
