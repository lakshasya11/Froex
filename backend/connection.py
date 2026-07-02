import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

class MT5Connection:
    """
    Manages the connection to the MetaTrader 5 terminal.
    Reads credentials from the .env file and provides automatic reconnection logic if the terminal drops.
    """

    @staticmethod
    def initialize_mt5():
        load_dotenv()
        mt5_path = os.getenv("MT5_PATH")
        mt5_login = os.getenv("MT5_LOGIN")
        mt5_pass = os.getenv("MT5_PASSWORD")
        mt5_server = os.getenv("MT5_SERVER")

        if not all([mt5_path, mt5_login, mt5_pass, mt5_server]):
            print("❌ CRITICAL: .env file is missing MT5 credentials.")
            return False

        try:
            mt5_login = int(mt5_login)
        except ValueError:
            print("❌ CRITICAL: MT5_LOGIN must be a valid integer.")
            return False

        if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_pass, server=mt5_server):
            print(f"❌ MT5 initialization failed: {mt5.last_error()}")
            return False

        print("✅ MT5 connection established successfully.")
        return True

    @staticmethod
    def ensure_connection():
        import time
        import random
        
        info = mt5.terminal_info()
        if info and info.connected:
            return True
            
        print("⚠️ MT5 connection lost. Initiating reconnect sequence with exponential backoff...")
        
        max_backoff = 60
        base_delay = 1
        attempt = 0
        
        while True:
            if MT5Connection.initialize_mt5():
                info = mt5.terminal_info()
                if info and info.connected:
                    print("✅ Connection re-established.")
                    return True
            
            # Exponential backoff: 1, 2, 4, 8... up to 60s
            delay = min(base_delay * (2 ** attempt), max_backoff)
            # Add up to 20% jitter
            jitter = random.uniform(0, 0.2 * delay)
            total_sleep = delay + jitter
            
            print(f"⏳ Reconnect failed. Retrying in {total_sleep:.2f}s (Attempt {attempt + 1})...")
            time.sleep(total_sleep)
            attempt += 1
