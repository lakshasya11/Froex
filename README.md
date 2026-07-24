# XAUUSD M5 Momentum Scalping Bot

Automated trading bot for XAUUSD (Gold) on the M5 timeframe. Detects live breakouts using velocity-based momentum, Supertrend alignment, and Bollinger Band structural rules. Manages trades with a multi-stage exit system.

---

## How to Run

**1. One-Click Start (Recommended)**
Simply double-click the master `start.bat` located in the root folder. 
This will automatically launch both the **MT5 Python Bot** and the **Next.js Web Dashboard** simultaneously in separate windows. 
You can stop both instantly by running the master `stop.bat`.

**2. Manual Start**
If you prefer to run them separately:
- **Web Dashboard:** `cd frontend` then `npm run dev` (Access at http://localhost:3000)
- **Trading Bot:** `cd backend` then `start.bat` (or `python main.py`)

---

## Architecture & File Structure

The project is cleanly separated into a full-stack trading application:

### `/frontend` (Next.js Web Dashboard)
A React-based UI (http://localhost:3000) that provides a live dashboard of your algorithm's performance, win rates, and recent trades. It also features a **Manual Execution Terminal** that allows you to specify Lot Size, SL, and TP, and instantly fire trades directly into MT5 by communicating with the Python backend.

### `/backend` (Python Trading Bot)
Contains the core algorithmic trading engine that connects to MetaTrader 5.

| File | Purpose |
|---|---|
| `main.py` | Main bot — runs the automated momentum algorithm |
| `manual.py` | Bridge script for UI manual trades |
| `entry.py` | Execution blocks and tick confirmations |
| `strategy.py` | Momentum Score calculation, Supertrend & BB logic |
| `exit.py` | Exit conditions and position management |
| `config.py` | All settings and thresholds (edit here to tune) |
| `indicators.py` | Price action calculations |
| `connection.py` | MT5 connection and reconnection |
| `formatter.py` | Terminal display formatting |
| `database.py` | SQLite trade journal |
| `stats.py` | View trading statistics from CLI |
| `start.bat` / `stop.bat` | Start/stop the backend specifically |

---

## Entry Conditions (Multi-Factor Scoring)

Entries require a minimum Momentum Score of **80.0** and must pass ALL of the following hard rules:

1. **EMA 9 Angle & Trend Filter:** 
   - **BUY:** EMA 9 angle must be sloping UP ($\ge +10^\circ$).
   - **SELL:** EMA 9 angle must be sloping DOWN ($\le -10^\circ$).
2. **Structure & EMA 9 Position:**
   - **BUY:** Active candle must be GREEN. If price is *below* the EMA 9 (Pullback), the *previous* closed candle must also be GREEN.
   - **SELL:** Active candle must be RED. If price is *above* the EMA 9 (Pullback), the *previous* closed candle must also be RED.
3. **Velocity Minimums:** Instant velocity $\ge 0.04$, Average velocity $\ge 0.02$, and 2-Second velocity $\ge 0.04$.
4. **Body Size:** Minimum candle body must be $\ge 0.10$ points.
5. **Tick Confirmation:** All conditions must hold true for **2 consecutive ticks** without the price drifting more than 0.60 points.
6. **Candle Window:** Excludes the first 15 seconds and last 20 seconds of the 5-minute candle to avoid erratic volatility.
7. **Re-entry Protection:** Price must move at least 0.50 points away from a previous losing entry price before trying again.

---

## Key Thresholds (edit in `config.py`)

| Setting | M5 Timeframe Value |
|---|---|
| Instant Velocity Threshold | 0.05 |
| Average Velocity Threshold | 0.03 |
| Minimum Body Size | 0.10 pts |
| Hard Stop Loss | 2.00 pts |
| Take Profit (Moderate) | 3.00 pts |
| Take Profit (Strong) | 5.00 pts |
| Take Profit (Ultra Strong) | 8.00 pts |
| Max Daily Trades | 500 |
| Daily Profit Target | $350.00 |

---

## Exit System (4-Tier Framework)

1. **Profit Lock (Breakeven System):** Ratchets the SL into profit. E.g., for M5, locks +0.50 pts of profit when the trade reaches +1.50 pts.
2. **Hard SL Fallback:** Immediate closure if price hits the structural Hard Stop Loss (2.00 pts).
3. **Dynamic Take Profit:** Targets are set at entry based on velocity (Moderate, Strong, Ultra). Reaching the target instantly closes the trade.
4. **Volatility Trailing Stop:** Activates at +1.80 pts of profit and trails at a gap of 0.80 pts behind the peak price.

---

## Requirements

```bash
pip install -r requirements.txt
```

MT5 credentials go in `.env`:
```
MT5_PATH=C:\Path\To\terminal64.exe
MT5_LOGIN=12345678
MT5_PASSWORD=yourpassword
MT5_SERVER=BrokerName-Server
```

---

## Disclaimer

Test on a demo account before running live. Past performance does not guarantee future results.