from database import TradeDatabase
from formatter import TerminalFormatter
import sys
import sqlite3
import re

LAST_TODAY_COUNT = 20


def parse_today_count(args):
    for arg in args:
        match = re.fullmatch(r"--today(\d+)", arg)
        if match:
            return max(1, int(match.group(1)))
    return None


def print_recent_trades(db, date_filter, limit):
    where = ""
    params = []
    if date_filter:
        where = "WHERE entry_time LIKE ?"
        params.append(f"{date_filter}%")

    conn = sqlite3.connect(db.db_name)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT entry_time, exit_time, direction, entry_price, exit_price,
               exit_reason, profit_points, profit_dollars, result
        FROM trades
        {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    conn.close()

    rows = list(reversed(rows))
    if not rows:
        title = "today" if date_filter else "history"
        print(f"No trades found for {title}.")
        return

    print(f"\nLAST {len(rows)} TRADES")
    print("-" * 92)
    print(
        f"{'Exit Time':19} {'Dir':4} {'Entry':>8} {'Exit':>9}  {'Reason':16} {'Pts':>7} {'P&L':>9} {'Result'}"
    )
    print("-" * 92)
    for row in rows:
        print(
            f"{row['exit_time'][:19]:19} "
            f"{row['direction']:<4} "
            f"{row['entry_price']:>8.2f} "
            f"{row['exit_price']:>9.2f}  "
            f"{row['exit_reason'][:16]:16} "
            f"{row['profit_points']:>+7.2f} "
            f"${row['profit_dollars']:>+8.2f} "
            f"{row['result']}"
        )
    print("-" * 92)


def main():
    db = TradeDatabase()
    db.auto_import_from_csv("trade_journal.csv")

    args = sys.argv[1:]
    today_count = parse_today_count(args)
    today = "--today" in args or today_count is not None
    show_today_trades = today_count is not None

    # Check for --date argument
    date_filter = None
    if today:
        date_filter = "today"
    else:
        for i, arg in enumerate(args):
            if arg.startswith("--date"):
                if len(arg) > 6:
                    # Handle --date2026-06-22
                    date_filter = arg[6:]
                    # Convert DD-MM-YYYY to YYYY-MM-DD if needed
                    if re.match(r"\d{2}-\d{2}-\d{4}", date_filter):
                        parts = date_filter.split("-")
                        date_filter = f"{parts[2]}-{parts[1]}-{parts[0]}"
                elif i + 1 < len(args):
                    # Handle --date 2026-06-22
                    date_filter = args[i + 1]
                    if re.match(r"\d{2}-\d{2}-\d{4}", date_filter):
                        parts = date_filter.split("-")
                        date_filter = f"{parts[2]}-{parts[1]}-{parts[0]}"
                break

    stats = db.get_stats(date_filter=date_filter, limit=today_count)
    if stats:
        TerminalFormatter().print_database_stats(stats, is_today=today)
        if show_today_trades or date_filter:
            limit = (
                today_count
                if today_count
                else stats.get("total_trades", LAST_TODAY_COUNT)
            )
            print_recent_trades(db, stats.get("date_filter"), limit)
    else:
        print("Failed to query statistics.")


if __name__ == "__main__":
    main()
