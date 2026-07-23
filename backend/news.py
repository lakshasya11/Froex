import urllib.request
import json
from datetime import datetime, timezone
import threading
import time
import os
import config


class NewsFilter:
    """
    Fetches the live economic calendar from ForexFactory (FairEconomy).
    Automatically parses the event times and determines if the bot is currently
    inside a high-impact news blackout window.
    """

    def __init__(self):
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.events = []
        self._lock = threading.Lock()  # Protects self.events across threads

        # Check cache age to avoid 429 Too Many Requests when restarting frequently
        cache_file = "news_cache.json"
        self.last_successful_fetch = 0
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 21600:  # 6 hours
                self.last_successful_fetch = (
                    time.time()
                )  # Pretend we just fetched it to delay next fetch
                # Preload the cache so len(self.events) > 0, which stops the background thread from pinging the API
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    target_currency = getattr(config, "NEWS_TARGET_CURRENCY", "USD")
                    impact_level = getattr(config, "NEWS_IMPACT_LEVEL", "High")

                    parsed_events = []
                    if isinstance(data, list):
                        for event in data:
                            if (
                                event.get("country") == target_currency
                                and event.get("impact") == impact_level
                            ):
                                dt_str = event.get("date")
                                if dt_str:
                                    dt = datetime.fromisoformat(
                                        dt_str.replace("Z", "+00:00")
                                    )
                                    parsed_events.append(
                                        {
                                            "title": event.get("title"),
                                            "time": dt,
                                            "date": dt_str,
                                            "impact": event.get("impact"),
                                            "country": event.get("country"),
                                            "forecast": event.get("forecast", ""),
                                            "previous": event.get("previous", ""),
                                        }
                                    )
                    self.events = parsed_events
                except Exception:
                    pass

        if getattr(config, "ENABLE_NEWS_FILTER", False):
            # Start background loop immediately (avoids sync blocking on startup)
            self.thread = threading.Thread(target=self._background_fetch, daemon=True)
            self.thread.start()

    def _fetch_data(self):
        cache_file = "news_cache.json"
        data = None

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }
            req = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(
                req, timeout=10
            ) as response:  # Added timeout to prevent hanging
                raw_body = response.read().decode("utf-8")
                data = json.loads(raw_body)

            # ONLY write to cache if we got a valid payload
            if isinstance(data, list):
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                self.last_successful_fetch = time.time()

        except Exception as e:
            print(
                f"[WARNING] [NEWS FILTER] API Fetch failed ({e}). Attempting to load from local cache..."
            )
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # DO NOT modify self.last_successful_fetch here anymore.
                    # The cache contains weekly data that remains structurally valid.
                    print("[INFO] [NEWS FILTER] Loaded fallback news from local cache.")
                except Exception as cache_e:
                    print(f"[ERROR] [NEWS FILTER] Cache load failed: {cache_e}")
            else:
                print(
                    "[ERROR] [NEWS FILTER] No local cache available. Filter temporarily disabled."
                )

        if not data or not isinstance(data, list):
            return

        try:
            target_currency = getattr(config, "NEWS_TARGET_CURRENCY", "USD")
            impact_level = getattr(config, "NEWS_IMPACT_LEVEL", "High")

            parsed_events = []
            for event in data:
                if (
                    event.get("country") == target_currency
                    and event.get("impact") == impact_level
                ):
                    try:
                        dt_str = event.get("date")
                        if dt_str:
                            # Parse and strictly enforce UTC timezone awareness
                            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)

                            parsed_events.append({
                                "title": event.get("title"), 
                                "time": dt,
                                "date": dt_str,
                                "impact": event.get("impact"),
                                "country": event.get("country"),
                                "forecast": event.get("forecast", ""),
                                "previous": event.get("previous", ""),
                            })
                    except Exception:
                        pass

            # Thread-safe swap
            with self._lock:
                self.events = parsed_events

            if parsed_events:
                print(
                    f"[INFO] [NEWS FILTER] Successfully loaded {len(parsed_events)} high-impact {target_currency} events for the week."
                )
        except Exception as e:
            print(f"[ERROR] [NEWS FILTER] Failed to parse news data: {e}")

    def _background_fetch(self):
        # Fetch immediately on thread start, then enter loop
        self._fetch_data()
        while True:
            # Sleep for 12 hours, then fetch again to keep the week updated
            time.sleep(12 * 3600)
            self._fetch_data()

    def is_news_block_active(self) -> tuple:
        """Returns (bool, event_title) indicating if we are in a news block."""
        with self._lock:
            # Cache local reference to avoid keeping lock during computation
            current_events = list(self.events)

        if not getattr(config, "ENABLE_NEWS_FILTER", False) or not current_events:
            return False, ""

        now = datetime.now(timezone.utc)

        # Stale data block: if data is older than 24 hours, pause entries for safety
        if time.time() - self.last_successful_fetch > 86400:
            return True, "[STALE DATA] News fetch offline >24h"

        pre_mins = getattr(config, "NEWS_BLOCK_PRE_MINUTES", 15)
        post_mins = getattr(config, "NEWS_BLOCK_POST_MINUTES", 5)

        for event in current_events:
            event_time = event["time"]
            diff_seconds = (now - event_time).total_seconds()

            # Event is in the future
            if diff_seconds < 0:
                if abs(diff_seconds) <= pre_mins * 60:
                    return True, event["title"]
            # Event is in the past
            else:
                if diff_seconds <= post_mins * 60:
                    return True, event["title"]

        return False, ""
