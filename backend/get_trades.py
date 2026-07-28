import sqlite3
import json
import sys
import os
from datetime import datetime, timezone


def get_trades(filter_type, custom_date):
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "trade_journal.db"
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where_clause = ""
    params = []

    if filter_type != "all":
        if filter_type == "custom" and custom_date:
            where_clause = "WHERE date(entry_time) = ?"
            params.append(custom_date)
        elif filter_type == "today":
            target_date = datetime.now().strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) = ?"
            params.append(target_date)
        elif filter_type == "yesterday":
            import datetime as dt
            target_date = (dt.datetime.now() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) = ?"
            params.append(target_date)
        elif filter_type == "this-week":
            import datetime as dt
            today = dt.datetime.now()
            start_of_week = (today - dt.timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) >= ?"
            params.append(start_of_week)
        elif filter_type == "last-week":
            import datetime as dt
            today = dt.datetime.now()
            start_of_last_week = (today - dt.timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")
            end_of_last_week = (today - dt.timedelta(days=today.weekday() + 1)).strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) BETWEEN ? AND ?"
            params.extend([start_of_last_week, end_of_last_week])
        elif filter_type == "this-month":
            import datetime as dt
            today = dt.datetime.now()
            start_of_month = today.replace(day=1).strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) >= ?"
            params.append(start_of_month)
        elif filter_type == "last-month":
            import datetime as dt
            today = dt.datetime.now()
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - dt.timedelta(days=1)
            start_of_last_month = last_day_last_month.replace(day=1).strftime("%Y-%m-%d")
            end_of_last_month = last_day_last_month.strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) BETWEEN ? AND ?"
            params.extend([start_of_last_month, end_of_last_month])
        elif filter_type == "last-6-months":
            import datetime as dt
            today = dt.datetime.now()
            month = today.month - 6
            year = today.year
            if month <= 0:
                month += 12
                year -= 1
            start_of_6_months = today.replace(year=year, month=month, day=1).strftime("%Y-%m-%d")
            where_clause = "WHERE date(entry_time) >= ?"
            params.append(start_of_6_months)
        elif custom_date:
            where_clause = "WHERE date(entry_time) = ?"
            params.append(custom_date)

    trades_query = f"SELECT * FROM trades {where_clause} ORDER BY id DESC"
    cursor.execute(trades_query, params)
    trades = [dict(row) for row in cursor.fetchall()]

    stats_query = f"""
      SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN profit_dollars > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN profit_dollars <= 0 THEN 1 ELSE 0 END) as losing_trades,
        SUM(profit_dollars) as net_profit,
        SUM(CASE WHEN profit_dollars > 0 THEN profit_dollars ELSE 0 END) as gross_profit,
        SUM(CASE WHEN profit_dollars < 0 THEN ABS(profit_dollars) ELSE 0 END) as gross_loss
      FROM trades {where_clause}
    """
    cursor.execute(stats_query, params)
    stats = dict(cursor.fetchone() or {})

    session_query = f"""
      SELECT 
        CASE 
          WHEN CAST(substr(entry_time, 12, 2) AS INTEGER) >= 0 AND CAST(substr(entry_time, 12, 2) AS INTEGER) < 9 THEN 'Asian'
          WHEN CAST(substr(entry_time, 12, 2) AS INTEGER) >= 9 AND CAST(substr(entry_time, 12, 2) AS INTEGER) < 15 THEN 'UK'
          ELSE 'US'
        END as session_name,
        SUM(CASE WHEN profit_dollars >= 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN profit_dollars < 0 THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN profit_dollars >= 0 THEN profit_dollars ELSE 0 END) as profit,
        SUM(CASE WHEN profit_dollars < 0 THEN ABS(profit_dollars) ELSE 0 END) as lossAmount
      FROM trades {where_clause}
      GROUP BY session_name
    """
    cursor.execute(session_query, params)
    session_stats = [dict(row) for row in cursor.fetchall()]

    balance = None
    try:
        cursor.execute("SELECT balance FROM account_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            balance = row["balance"]
    except:
        pass

    conn.close()

    return {
        "success": True,
        "stats": stats,
        "sessionStats": session_stats,
        "balance": balance,
        "trades": trades,
    }


if __name__ == "__main__":
    f_type = sys.argv[1] if len(sys.argv) > 1 else "today"
    c_date = sys.argv[2] if len(sys.argv) > 2 else ""
    result = get_trades(f_type, c_date)
    print(json.dumps(result))
