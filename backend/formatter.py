import os
import sys
from datetime import datetime

class TerminalFormatter:
    def __init__(self):
        os.environ['FORCE_COLOR'] = '1'
        os.environ['TERM'] = 'xterm-256color'

        # Reconfigure stdout/stderr to UTF-8 to prevent UnicodeEncodeError on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except Exception:
                pass
        if hasattr(sys.stderr, 'reconfigure'):
            try:
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        self.CYAN = '\033[96m'
        self.GREEN = '\033[92m'
        self.RED = '\033[91m'
        self.YELLOW = '\033[93m'
        self.MAGENTA = '\033[95m'
        self.WHITE = '\033[97m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'

    def _box(self, title, rows, color):
        W     = 52
        inner = W - 6
        c     = color
        R     = self.RESET
        B     = self.BOLD
        top   = c + "╔" + "═" * (W-2) + "╗" + R
        mid   = c + "╠" + "═" * (W-2) + "╣" + R
        sgl   = c + "╟" + "─" * (W-2) + "╢" + R
        bot   = c + "╚" + "═" * (W-2) + "╝" + R

        def L(visible, colored=None):
            if colored is None: colored = visible
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

    def print_trade_entry(self, trade_type, entry_price, volume, sl, tp, ticket, conditions, capital, trades_today, risk_pts):
        ts  = datetime.now().strftime("%H:%M:%S")
        vel = conditions.split('| V: ')[1] if '| V: ' in conditions else 'N/A'
        G   = self.GREEN
        R   = self.RESET
        B   = self.BOLD
        d_color = G if trade_type == "BUY" else self.RED

        self._box(f"TRADE ENTERED  #{ticket}", [
            (f"Type: {trade_type}     Time: {ts}",
             f"Type: {d_color}{B}{trade_type}{R}     Time: {ts}"),
            (f"Entry: {entry_price:.2f}     Lot: {volume:.2f}",
             f"Entry: {B}{entry_price:.2f}{R}     Lot: {volume:.2f}"),
            "---",
            (f"TP:  {tp:.2f}     SL:  {sl:.2f}",
             f"TP:  {G}{tp:.2f}{R}     SL:  {self.RED}{sl:.2f}{R}"),
            (f"Risk: {risk_pts:.2f} pts",
             f"Risk: {self.YELLOW}{risk_pts:.2f} pts{R}"),
            "---",
            (f"Velocity: {vel}",
             f"Velocity: {vel}"),
            (f"Trades: {trades_today}     Balance: ${capital:,.0f}",
             f"Trades: {B}{trades_today}{R}     Balance: ${capital:,.0f}"),
        ], self.CYAN)

    def print_news_calendar(self, events):
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        
        B = self.BOLD
        R = self.RESET
        Y = self.YELLOW
        C = self.CYAN
        G = self.GREEN

        rows = []
        if not events:
            rows.append((
                "No High-Impact USD News This Week",
                f"{G}{B}No High-Impact USD News This Week{R}"
            ))
        else:
            sorted_events = sorted(events, key=lambda x: x['time'])
            
            from datetime import timedelta
            ist_tz = timezone(timedelta(hours=5, minutes=30))

            for e in sorted_events:
                local_time = e['time'].astimezone(ist_tz).strftime("%b %d  %H:%M")
                title = e.get('title', 'News Event')
                if len(title) > 28:
                    title = title[:25] + "..."
                
                if e['time'] < now_utc:
                    status_col = f"{self.CYAN}[PASSED]{R}"
                    status_vis = "[PASSED]"
                else:
                    mins_away = int((e['time'] - now_utc).total_seconds() / 60)
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

                vis_str = f"{local_time}  {title:<28} {status_vis}"
                col_str = f"{Y}{local_time}{R}  {title:<28} {status_col}"
                rows.append((vis_str, col_str))

        self._box("THIS WEEK'S ECONOMIC CALENDAR", rows, self.YELLOW)

    def print_trade_exit_with_condition(self, direction, entry_price, exit_price, duration, ticket,
                                          total_closed, win_rate, capital, total_profit, exit_condition,
                                          trade_profit=0.0, v_entry=0.0, tp_target=2.0, peak=0.0):
        profit_pts = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
        is_win     = profit_pts >= 0
        c          = self.GREEN if is_win else self.RED
        result     = "WIN" if is_win else "LOSS"
        p_color    = self.GREEN if profit_pts >= 0 else self.RED
        wr_color   = self.GREEN if win_rate >= 60 else self.YELLOW if win_rate >= 45 else self.RED
        R          = self.RESET
        B          = self.BOLD
        d_color    = self.GREEN if direction == "BUY" else self.RED

        self._box(f"TRADE CLOSED  #{ticket}  [{result}]", [
            (f"Dir: {direction}     Duration: {duration}",
             f"Dir: {d_color}{B}{direction}{R}     Duration: {duration}"),
            (f"Entry: {entry_price:.2f}  ->  Exit: {exit_price:.2f}",
             f"Entry: {entry_price:.2f}  ->  Exit: {B}{exit_price:.2f}{R}"),
            (f"P/L: {profit_pts:+.2f} pts    (${trade_profit:+.2f})",
             f"P/L: {p_color}{B}{profit_pts:+.2f} pts{R}    {p_color}(${trade_profit:+.2f}){R}"),
            "---",
            (f"Reason: {exit_condition}",
             f"Reason: {exit_condition}"),
            (f"Peak: {peak:+.2f} pts     Vel: {v_entry:+.2f}",
             f"Peak: {peak:+.2f} pts     Vel: {v_entry:+.2f}"),
            "===",
            (f"Trades: {total_closed}   WR: {win_rate:.1f}%   Session: ${total_profit:+.2f}",
             f"Trades: {B}{total_closed}{R}   WR: {wr_color}{B}{win_rate:.1f}%{R}   Session: ${total_profit:+.2f}"),
        ], c)

    def print_database_stats(self, db_stats, is_today=False):
        if not db_stats:
            return

        total = db_stats.get('total_trades', 0)
        if total == 0:
            print(f"\nNo trades found for {db_stats.get('date_filter', 'this period')}.")
            return

        wr      = db_stats.get('win_rate', 0.0)
        wins    = db_stats.get('winning_trades', 0)
        losses  = db_stats.get('losing_trades', 0)
        gross_p = db_stats.get('gross_profit', 0.0)
        gross_l = db_stats.get('total_losses', 0.0)
        net     = db_stats.get('total_profit', 0.0)
        avg_win = db_stats.get('avg_win', 0.0)
        avg_loss = db_stats.get('avg_loss', 0.0)
        reward_to_risk = db_stats.get('reward_to_risk', 0.0)

        wr_color  = self.GREEN if wr >= 60 else self.YELLOW if wr >= 45 else self.RED
        net_color = self.GREEN if net >= 0 else self.RED
        net_label = "PROFIT" if net >= 0 else "LOSS"

        filled    = int(wr / 100 * 24)
        bar_plain = "█" * filled + "░" * (24 - filled)
        bar_color = self.GREEN + "█" * filled + self.RED + "░" * (24 - filled) + self.RESET

        if is_today:
            date_str = db_stats.get('date_filter') or datetime.now().strftime("%Y-%m-%d")
            title = f"TODAY'S STATS  ({date_str})"
        elif db_stats.get('date_filter'):
            title = f"STATS FOR {db_stats['date_filter']}"
        else:
            title = "LIFETIME STATS"

        W     = 52
        inner = W - 6       # usable text width = 48
        c     = self.CYAN
        R     = self.RESET
        B     = self.BOLD

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
        print(L(title,                     f"{B}{self.WHITE}{title}{R}"))
        print(mid)
        print(L(f"Total Trades    {total}", f"Total Trades    {B}{total}{R}"))
        print(L(f"Wins  {wins}    Losses  {losses}",
                f"Wins  {self.GREEN}{B}{wins}{R}    Losses  {self.RED}{B}{losses}{R}"))
        print(L(f"Win Rate  {wr:.1f}%",    f"Win Rate  {wr_color}{B}{wr:.1f}%{R}"))
        print(L(f"  {bar_plain}",           f"  {bar_color}"))
        print(mid)
        print(L(f"Gross Profit    ${gross_p:>+,.2f}",
                f"Gross Profit    {self.GREEN}${gross_p:>+,.2f}{R}"))
        print(L(f"Gross Losses    -${gross_l:>,.2f}",
                f"Gross Losses    {self.RED}-${gross_l:>,.2f}{R}"))
        print(L(f"Avg Win         ${avg_win:>,.2f}",
                f"Avg Win         {self.GREEN}${avg_win:>,.2f}{R}"))
        print(L(f"Avg Loss        -${avg_loss:>,.2f}",
                f"Avg Loss        {self.RED}-${avg_loss:>,.2f}{R}"))
        print(L(f"Reward/Risk     {reward_to_risk:>.2f}:1",
                f"Reward/Risk     {self.YELLOW}{reward_to_risk:>.2f}:1{R}"))
        print(mid)
        net_vis = f"Net P&L    ${net:>+,.2f}    [{net_label}]"
        net_col = f"{B}Net P&L    {net_color}${net:>+,.2f}{R}    {net_color}{B}[{net_label}]{R}"
        print(L(net_vis, net_col))
        print(f"{bot}\n")

    def print_startup(self, symbol, timeframe, balance, currency, stops_level, point):
        W     = 52
        inner = W - 6
        c     = self.CYAN
        R     = self.RESET
        B     = self.BOLD
        G     = self.GREEN

        top = c + "╔" + "═" * (W - 2) + "╗" + R
        mid = c + "╠" + "═" * (W - 2) + "╣" + R
        bot = c + "╚" + "═" * (W - 2) + "╝" + R

        def L(visible, colored=None):
            if colored is None: colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad,0)}  {c}║{R}"

        title   = "XAUUSD MOMENTUM SCALPING BOT"
        bal_str = f"${balance:,.2f} {currency}"

        print(f"\n{top}")
        print(L(title, f"{B}{self.WHITE}{title}{R}"))
        print(mid)
        print(L(f"Symbol      {symbol}    Timeframe  {timeframe}",
                f"Symbol      {G}{B}{symbol}{R}    Timeframe  {G}{B}{timeframe}{R}"))
        print(L(f"Balance     {bal_str}",
                f"Balance     {G}{B}{bal_str}{R}"))
        print(L(f"Stops Level {stops_level}    Point      {point}",
                f"Stops Level {stops_level}    Point      {point}"))
        print(L("Status      Connected to MT5",
                f"Status      {G}Connected to MT5{R}"))
        print(f"{bot}\n")

    def print_tick_context(self, label, ticks, direction):
        if not ticks:
            return
        W     = 52
        inner = W - 6
        c     = self.CYAN if "PRE" in label else self.YELLOW
        d_c   = self.GREEN if direction == "BUY" else self.RED
        R     = self.RESET
        B     = self.BOLD
        top   = c + "╔" + "═" * (W-2) + "╗" + R
        bot   = c + "╚" + "═" * (W-2) + "╝" + R
        sgl   = c + "╟" + "─" * (W-2) + "╢" + R

        def L(visible, colored=None):
            if colored is None: colored = visible
            pad = inner - len(visible)
            return f"{c}║{R}  {colored}{' ' * max(pad,0)}  {c}║{R}"

        title = f"{'PRE' if 'PRE' in label else 'POST'}-ENTRY  {direction}  ({len(ticks)} ticks)"
        print(f"\n{top}")
        print(L(title, f"{B}{d_c}{title}{R}"))
        print(sgl)
        for i, t in enumerate(ticks):
            avg_str = f"{t['avg_vel']:+.2f}" if t['avg_vel'] is not None else " N/A"
            ts  = datetime.fromtimestamp(t['time']).strftime("%H:%M:%S.%f")[:-4]
            vis = f"[{i+1:02d}] {ts}  {t['bid']:.2f}  v:{t['velocity']:+.3f}  a:{avg_str}"
            print(L(vis))
        print(f"{bot}{R}\n")
