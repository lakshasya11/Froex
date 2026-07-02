import MetaTrader5 as mt5
from indicators import TechnicalIndicators
import config

class EnhancedTradingStrategy:

    TIMEFRAMES = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1':  mt5.TIMEFRAME_H1,
        'H4':  mt5.TIMEFRAME_H4,
        'D1':  mt5.TIMEFRAME_D1
    }

    def __init__(self, symbol: str, base_timeframe: str = 'M5'):
        self.symbol = symbol
        self.base_timeframe = base_timeframe

    def analyze_timeframe(self, timeframe: str) -> dict:
        analysis = TechnicalIndicators.analyze_basic_timeframe(
            self.symbol, self.TIMEFRAMES[timeframe], bars=100
        )
        if not analysis:
            return {}

        analysis['current_candle'] = analysis.get('candle_color', 'UNKNOWN')

        # --- MULTI-TIMEFRAME ALIGNMENT ---
        if getattr(config, 'ENABLE_MTF_ALIGNMENT', False) and timeframe == self.base_timeframe:
            analysis['mtf_bullish'] = True
            analysis['mtf_bearish'] = True
            mtfs = getattr(config, 'MTF_TIMEFRAMES', ['M15', 'H1'])
            for tf in mtfs:
                if tf in self.TIMEFRAMES:
                    tf_analysis = TechnicalIndicators.analyze_basic_timeframe(
                        self.symbol, self.TIMEFRAMES[tf], bars=100
                    )
                    if tf_analysis:
                        st_dir = tf_analysis.get('st_direction', 0)
                        if st_dir != 1:
                            analysis['mtf_bullish'] = False
                        if st_dir != -1:
                            analysis['mtf_bearish'] = False

        return analysis
