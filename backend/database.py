import sqlite3
import os
import csv
from datetime import datetime
import queue
import threading
import time


class TradeDatabase:
    """
    Handles the local SQLite storage of all completed trades.
    This allows for rapid statistical analysis (win rate, P&L, etc.) without relying solely on MT5 history.
    """

    def __init__(self, db_name="trade_journal.db"):
        self.db_name = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
        self.write_queue = queue.Queue()
        self.init_db()

        self.worker_thread = threading.Thread(
            target=self._bg_writer_worker, daemon=True
        )
        self.worker_thread.start()

    def _get_connection(self):
        """Returns a configured SQLite connection with WAL mode and connection timeout."""
        # 10s timeout prevents 'database is locked' if a transaction is taking briefly longer
        conn = sqlite3.connect(self.db_name, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self):
        """Create the SQLite database and table if they do not exist"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER UNIQUE,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    sl REAL,
                    tp REAL,
                    entry_velocity REAL,
                    exit_reason TEXT,
                    profit_points REAL NOT NULL,
                    profit_dollars REAL NOT NULL,
                    result TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_state (
                    id INTEGER PRIMARY KEY,
                    balance REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

            # Add ticket column dynamically if database exists but has no ticket column
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN ticket INTEGER")
                conn.commit()
                # Create a unique index for ticket ignoring NULLs (for migration compatibility)
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_ticket ON trades(ticket) WHERE ticket IS NOT NULL"
                )
                conn.commit()
                print("[INFO] [DATABASE] Added ticket column to existing trades table.")
            except sqlite3.OperationalError:
                pass

            # Add volume column
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN volume REAL")
                conn.commit()
                print("[INFO] [DATABASE] Added volume column to existing trades table.")
            except sqlite3.OperationalError:
                pass

            # Add score and excursion columns
            new_cols = [
                ("score_momentum", "REAL"),
                ("score_trend", "REAL"),
                ("score_candle", "REAL"),
                ("score_execution", "REAL"),
                ("score_total", "REAL"),
                ("velocity_consistency", "REAL"),
                ("velocity_acceleration", "REAL"),
                ("score_acceleration", "REAL"),
                ("velocity_std", "REAL"),
                ("velocity_mean", "REAL"),
                ("mfe", "REAL"),
                ("mae", "REAL"),
                ("strategy_version", "TEXT"),
                ("duration_seconds", "INTEGER"),
                ("adx_14", "REAL"),
                ("sideways_score", "INTEGER"),
                ("st_flips_5", "INTEGER"),
                ("bb_bandwidth", "REAL"),
                ("timeframe", "TEXT"),
            ]
            for col, dtype in new_cols:
                try:
                    cursor.execute(f"ALTER TABLE trades ADD COLUMN {col} {dtype}")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluated_setups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candle_time TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    score_momentum REAL,
                    score_trend REAL,
                    score_candle REAL,
                    score_execution REAL,
                    score_total REAL,
                    reject_reason TEXT,
                    decision_stage TEXT,
                    trade_executed INTEGER,
                    ticket INTEGER,
                    bb_angle REAL,
                    instant_velocity REAL,
                    velocity_2s REAL,
                    strategy_version TEXT,
                    UNIQUE(candle_time, direction)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERROR] SQLite Initialization Error: {e}")

    def log_evaluated_setup(self, setup_data):
        setup_data["_type"] = "evaluated_setup"
        self.write_queue.put(setup_data)
        return True

    def save_trade(self, data):
        """
        Non-blocking write handler. Drops the payload into the background
        worker queue and instantly returns control back to the execution loop.
        """
        self.write_queue.put(data)
        return True

    def _bg_writer_worker(self):
        """Isolated background loop running on a dedicated thread to execute writes."""
        conn = self._get_connection()
        print(
            "[INFO] [DB WORKER] Database background writer thread started successfully."
        )

        while True:
            try:
                data = self.write_queue.get()
                if data is None:
                    self.write_queue.task_done()
                    break

                success = False
                for attempt in range(3):
                    try:
                        with conn:
                            ticket_val = data.get("ticket")
                            if ticket_val is not None:
                                try:
                                    ticket_val = int(ticket_val)
                                except (ValueError, TypeError):
                                    ticket_val = None

                            if data.get("_type") == "evaluated_setup":
                                conn.execute(
                                    """
                                    INSERT INTO evaluated_setups (
                                        candle_time, direction, timestamp, score_momentum, score_trend, score_candle, 
                                        score_execution, score_total, reject_reason, decision_stage, trade_executed, 
                                        ticket, bb_angle, instant_velocity, velocity_2s, strategy_version
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(candle_time, direction) DO UPDATE SET
                                        timestamp = excluded.timestamp,
                                        score_momentum = excluded.score_momentum,
                                        score_trend = excluded.score_trend,
                                        score_candle = excluded.score_candle,
                                        score_execution = excluded.score_execution,
                                        score_total = excluded.score_total,
                                        reject_reason = excluded.reject_reason,
                                        decision_stage = excluded.decision_stage,
                                        trade_executed = CASE WHEN excluded.trade_executed = 1 THEN 1 ELSE evaluated_setups.trade_executed END,
                                        ticket = CASE WHEN excluded.ticket IS NOT NULL THEN excluded.ticket ELSE evaluated_setups.ticket END,
                                        bb_angle = excluded.bb_angle,
                                        instant_velocity = excluded.instant_velocity,
                                        velocity_2s = excluded.velocity_2s,
                                        strategy_version = excluded.strategy_version
                                    WHERE excluded.score_total > evaluated_setups.score_total OR excluded.trade_executed = 1
                                    """,
                                    (
                                        data["candle_time"],
                                        data["direction"],
                                        data["timestamp"],
                                        data.get("score_momentum", 0.0),
                                        data.get("score_trend", 0.0),
                                        data.get("score_candle", 0.0),
                                        data.get("score_execution", 0.0),
                                        data.get("score_total", 0.0),
                                        data.get("reject_reason", ""),
                                        data.get("decision_stage", ""),
                                        data.get("trade_executed", 0),
                                        data.get("ticket"),
                                        data.get("bb_angle", 0.0),
                                        data.get("instant_velocity", 0.0),
                                        data.get("velocity_2s", 0.0),
                                        data.get("strategy_version", "unknown"),
                                    ),
                                )
                            else:
                                conn.execute(
                                    """
                                    INSERT OR IGNORE INTO trades (
                                    ticket, entry_time, exit_time, direction, entry_price, exit_price,
                                    sl, tp, entry_velocity, exit_reason, profit_points, profit_dollars, result, volume,
                                    score_momentum, score_trend, score_candle, score_execution, score_total,
                                    velocity_consistency, velocity_acceleration, score_acceleration, velocity_std, velocity_mean, mfe, mae, strategy_version, duration_seconds,
                                    adx_14, sideways_score, st_flips_5, bb_bandwidth, timeframe
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                    (
                                        ticket_val,
                                        data["entry_time"],
                                        data["exit_time"],
                                        data["direction"],
                                        data["entry_price"],
                                        data["exit_price"],
                                        data.get("sl", 0.0),
                                        data.get("tp", 0.0),
                                        data.get("entry_velocity", 0.0),
                                        data.get("exit_reason", "N/A"),
                                        data["profit_points"],
                                        data["profit_dollars"],
                                        data["result"],
                                        data.get("volume", 0.0),
                                        data.get("score_momentum", 0.0),
                                        data.get("score_trend", 0.0),
                                        data.get("score_candle", 0.0),
                                        data.get("score_execution", 0.0),
                                        data.get("score_total", 0.0),
                                        data.get("velocity_consistency", 0.0),
                                        data.get("velocity_acceleration", 0.0),
                                        data.get("score_acceleration", 0.0),
                                        data.get("velocity_std", 0.0),
                                        data.get("velocity_mean", 0.0),
                                        data.get("mfe", 0.0),
                                        data.get("mae", 0.0),
                                        data.get("strategy_version", "unknown"),
                                        data.get("duration_seconds", 0),
                                        data.get("adx_14", 0.0),
                                        data.get("sideways_score", 0),
                                        data.get("st_flips_5", 0),
                                        data.get("bb_bandwidth", 0.0),
                                        data.get("timeframe", "M5"),
                                    ),
                                )
                        success = True
                        break
                    except sqlite3.OperationalError as e:
                        if "locked" in str(e).lower():
                            print(
                                f"[WARNING] [DB WORKER] Database locked. Retrying attempt {attempt+1}/3..."
                            )
                            time.sleep(0.2)
                        else:
                            raise e

                if not success:
                    print(
                        f"[CRITICAL] [DB WORKER] Failed to save trade data for ticket {data.get('ticket')} due to persistent locking."
                    )

                self.write_queue.task_done()

            except Exception as e:
                print(
                    f"[ERROR] [DB WORKER] Exception in background database thread: {e}"
                )

    def save_account_state(self, balance):
        """Immediately update the account state in the DB"""
        try:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO account_state (id, balance, updated_at)
                    VALUES (1, ?, ?)
                """,
                    (balance, datetime.now().isoformat()),
                )
            conn.close()
        except Exception as e:
            pass  # Silent fail to prevent log spam

    def get_stats(self, date_filter=None, limit=None):
        """
        Query the database to calculate statistics:
        - total number of trades
        - win
        - loss
        - winrate
        - total profit (net cumulative)
        - gross profit (sum of winning profit)
        - total losses (gross loss, sum of losing losses)
        Optional: date_filter (e.g. "2026-05-18" or "today")
        Optional: limit (integer, limits stats to the last N trades)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Smart Date Filtering
            sql_where = ""
            params = []
            date_str = None

            if date_filter is not None:
                if date_filter == "today":
                    # Check local date first
                    today_local = datetime.now().strftime("%Y-%m-%d")
                    cursor.execute(
                        "SELECT COUNT(*) FROM trades WHERE entry_time LIKE ?",
                        (f"{today_local}%",),
                    )
                    count = cursor.fetchone()[0]
                    if count > 0:
                        date_str = today_local
                    else:
                        # Fallback to UTC date
                        from datetime import timezone

                        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else:
                    date_str = date_filter

                sql_where = " WHERE entry_time LIKE ?"
                params = [f"{date_str}%"]

            # Total trades count (check if there are any trades at all before applying limit)
            cursor.execute("SELECT COUNT(*) FROM trades" + sql_where, params)
            if cursor.fetchone()[0] == 0:
                conn.close()
                return None

            if limit is not None:
                cte = f"WITH limited_trades AS (SELECT * FROM trades{sql_where} ORDER BY id DESC LIMIT ?)"
                params.append(limit)
                table_name = "limited_trades"
                query_where = ""
            else:
                cte = ""
                table_name = "trades"
                query_where = sql_where

            # Total trades count (after limit)
            cursor.execute(
                f"{cte} SELECT COUNT(*) FROM {table_name}{query_where}", params
            )
            total_trades = cursor.fetchone()[0]

            if total_trades == 0:
                conn.close()
                return None

            # Winning trades count
            cursor.execute(
                f"{cte} SELECT COUNT(*) FROM {table_name}{query_where}"
                + (" AND " if query_where else " WHERE ")
                + "profit_dollars > 0",
                params,
            )
            winning_trades = cursor.fetchone()[0]

            # Losing trades count
            cursor.execute(
                f"{cte} SELECT COUNT(*) FROM {table_name}{query_where}"
                + (" AND " if query_where else " WHERE ")
                + "profit_dollars <= 0",
                params,
            )
            losing_trades = cursor.fetchone()[0]

            # Total profit (Net cumulative profit)
            cursor.execute(
                f"{cte} SELECT SUM(profit_dollars) FROM {table_name}{query_where}",
                params,
            )
            total_profit = cursor.fetchone()[0] or 0.0

            # Gross profit (Sum of all positive winning trades)
            cursor.execute(
                f"{cte} SELECT SUM(profit_dollars) FROM {table_name}{query_where}"
                + (" AND " if query_where else " WHERE ")
                + "profit_dollars > 0",
                params,
            )
            gross_profit = cursor.fetchone()[0] or 0.0

            # Gross loss (Sum of all negative losing trades)
            cursor.execute(
                f"{cte} SELECT SUM(profit_dollars) FROM {table_name}{query_where}"
                + (" AND " if query_where else " WHERE ")
                + "profit_dollars <= 0",
                params,
            )
            total_losses = cursor.fetchone()[0] or 0.0

            # Win Rate (Completed Trades)
            total_completed = winning_trades + losing_trades
            win_rate = (
                (winning_trades / total_completed * 100) if total_completed > 0 else 0.0
            )

            avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
            avg_loss = abs(total_losses) / losing_trades if losing_trades > 0 else 0.0

            # Reward-to-Risk ratio (Avg Win / Avg Loss)
            reward_to_risk = avg_win / avg_loss if avg_loss > 0 else 0.0

            conn.close()

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 2),
                "total_profit": round(total_profit, 2),
                "gross_profit": round(gross_profit, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "reward_to_risk": round(reward_to_risk, 2),
                "total_losses": round(abs(total_losses), 2),
                "date_filter": date_str if date_filter else None,
            }
        except Exception as e:
            print(f"[ERROR] SQLite Error: Failed to calculate statistics: {e}")
            return None

    def auto_import_from_csv(self, csv_path):
        """Automatically import existing trades from CSV if database is empty"""
        resolved_csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), csv_path
        )
        if not os.path.exists(resolved_csv_path):
            return 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if database is already populated
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]
            if count > 0:
                conn.close()
                return 0  # DB already has data, skip import

            print(
                f"\n[INFO] [DATABASE] New SQLite DB detected. Auto-importing history from {csv_path}..."
            )

            def _f(v):
                try:
                    return float(v) if v else 0.0
                except (ValueError, TypeError):
                    return 0.0

            with open(resolved_csv_path, mode="r", encoding="utf-8") as f:
                trades_to_import = []
                for row in csv.DictReader(f):
                    try:
                        ticket_val = (
                            int(row.get("ticket")) if row.get("ticket") else None
                        )
                    except (ValueError, TypeError):
                        ticket_val = None
                    trades_to_import.append(
                        (
                            ticket_val,
                            row.get("entry_time", ""),
                            row.get("exit_time", ""),
                            row.get("direction", ""),
                            _f(row.get("entry_price")),
                            _f(row.get("exit_price")),
                            _f(row.get("sl")),
                            _f(row.get("tp")),
                            _f(row.get("entry_velocity")),
                            row.get("exit_reason", ""),
                            _f(row.get("profit_points")),
                            _f(row.get("profit_dollars")),
                            row.get("result", "LOSS"),
                        )
                    )

                if trades_to_import:
                    cursor.executemany(
                        """
                        INSERT INTO trades (
                            ticket, entry_time, exit_time, direction, entry_price, exit_price,
                            sl, tp, entry_velocity, exit_reason, profit_points, profit_dollars, result
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        trades_to_import,
                    )
                    conn.commit()
                    print(
                        f"[SUCCESS] [DATABASE] Successfully imported {len(trades_to_import)} historical trades into SQLite!\n"
                    )

            conn.close()
            return len(trades_to_import)
        except Exception as e:
            print(f"[WARNING] [DATABASE] Failed to import from CSV: {e}")
            return 0
