"""
Technical Indicators Engine
Implements all 10 indicators from scratch for the confluence scoring system
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return []
    
    ema = []
    multiplier = 2 / (period + 1)
    
    # First EMA is SMA
    sma = sum(prices[:period]) / period
    ema.append(sma)
    
    for i in range(period, len(prices)):
        current_ema = (prices[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(current_ema)
    
    return ema

def calculate_sma(prices: List[float], period: int) -> List[float]:
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return []
    return [sum(prices[i-period:i]) / period for i in range(period, len(prices) + 1)]

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return []
    
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [max(0, c) for c in changes]
    losses = [abs(min(0, c)) for c in changes]
    
    rsi_values = []
    
    # First RSI calculation with SMA
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi_values.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    
    # Subsequent RSI calculations with smoothed averages
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi_values.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    
    return rsi_values

def calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
    """Calculate Average True Range"""
    if len(candles) < period + 1:
        return []
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i-1].close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    atr_values = []
    first_atr = sum(true_ranges[:period]) / period
    atr_values.append(first_atr)
    
    for i in range(period, len(true_ranges)):
        current_atr = (atr_values[-1] * (period - 1) + true_ranges[i]) / period
        atr_values.append(current_atr)
    
    return atr_values

def calculate_supertrend(candles: List[Candle], period: int = 10, multiplier: float = 3.0) -> Tuple[List[float], List[int]]:
    """Calculate Supertrend indicator
    Returns: (supertrend_values, direction) where direction is 1 for uptrend, -1 for downtrend
    """
    if len(candles) < period + 1:
        return [], []
    
    atr_values = calculate_atr(candles, period)
    if not atr_values:
        return [], []
    
    supertrend = []
    direction = []
    
    # Calculate basic upper and lower bands
    offset = len(candles) - len(atr_values)
    
    for i, atr in enumerate(atr_values):
        candle_idx = i + offset
        hl2 = (candles[candle_idx].high + candles[candle_idx].low) / 2
        
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr
        
        if i == 0:
            final_upper = basic_upper
            final_lower = basic_lower
            st = final_lower if candles[candle_idx].close > final_lower else final_upper
            d = 1 if candles[candle_idx].close > st else -1
        else:
            prev_close = candles[candle_idx - 1].close
            prev_upper = supertrend[-1] if direction[-1] == -1 else basic_upper
            prev_lower = supertrend[-1] if direction[-1] == 1 else basic_lower
            
            final_upper = basic_upper if basic_upper < prev_upper or prev_close > prev_upper else prev_upper
            final_lower = basic_lower if basic_lower > prev_lower or prev_close < prev_lower else prev_lower
            
            close = candles[candle_idx].close
            if direction[-1] == 1:
                st = final_lower if close > final_lower else final_upper
                d = 1 if close > final_lower else -1
            else:
                st = final_upper if close < final_upper else final_lower
                d = -1 if close < final_upper else 1
        
        supertrend.append(st)
        direction.append(d)
    
    return supertrend, direction

def calculate_vwap(candles: List[Candle]) -> List[float]:
    """Calculate Volume Weighted Average Price"""
    if not candles:
        return []
    
    vwap_values = []
    cumulative_tp_volume = 0
    cumulative_volume = 0
    
    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / 3
        cumulative_tp_volume += typical_price * candle.volume
        cumulative_volume += candle.volume
        
        if cumulative_volume > 0:
            vwap_values.append(cumulative_tp_volume / cumulative_volume)
        else:
            vwap_values.append(typical_price)
    
    return vwap_values

def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
    """Calculate MACD, Signal line, and Histogram"""
    if len(prices) < slow + signal:
        return {'macd': [], 'signal': [], 'histogram': []}
    
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    
    # Align EMAs
    offset = len(ema_fast) - len(ema_slow)
    ema_fast_aligned = ema_fast[offset:]
    
    macd_line = [f - s for f, s in zip(ema_fast_aligned, ema_slow)]
    signal_line = calculate_ema(macd_line, signal)
    
    # Align MACD and signal
    offset = len(macd_line) - len(signal_line)
    macd_aligned = macd_line[offset:]
    
    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]
    
    return {
        'macd': macd_aligned,
        'signal': signal_line,
        'histogram': histogram
    }

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return {'upper': [], 'middle': [], 'lower': []}
    
    middle = calculate_sma(prices, period)
    
    upper = []
    lower = []
    
    for i in range(len(middle)):
        idx = i + period - 1
        slice_prices = prices[idx - period + 1:idx + 1]
        std = np.std(slice_prices)
        upper.append(middle[i] + std_dev * std)
        lower.append(middle[i] - std_dev * std)
    
    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }

def calculate_stochastic(candles: List[Candle], k_period: int = 14, d_period: int = 3) -> Dict:
    """Calculate Stochastic K and D"""
    if len(candles) < k_period + d_period:
        return {'k': [], 'd': []}
    
    k_values = []
    
    for i in range(k_period - 1, len(candles)):
        slice_candles = candles[i - k_period + 1:i + 1]
        highest_high = max(c.high for c in slice_candles)
        lowest_low = min(c.low for c in slice_candles)
        
        current_close = candles[i].close
        
        if highest_high == lowest_low:
            k_values.append(50)
        else:
            k = 100 * (current_close - lowest_low) / (highest_high - lowest_low)
            k_values.append(k)
    
    d_values = calculate_sma(k_values, d_period)
    
    return {
        'k': k_values[d_period - 1:],
        'd': d_values
    }

def calculate_obv(candles: List[Candle]) -> List[float]:
    """Calculate On-Balance Volume"""
    if not candles:
        return []
    
    obv = [candles[0].volume]
    
    for i in range(1, len(candles)):
        if candles[i].close > candles[i-1].close:
            obv.append(obv[-1] + candles[i].volume)
        elif candles[i].close < candles[i-1].close:
            obv.append(obv[-1] - candles[i].volume)
        else:
            obv.append(obv[-1])
    
    return obv

def calculate_volume_ma(candles: List[Candle], period: int = 20) -> List[float]:
    """Calculate Volume Moving Average"""
    volumes = [c.volume for c in candles]
    return calculate_sma(volumes, period)

def is_bullish_engulfing(candles: List[Candle]) -> bool:
    """Check if last two candles form bullish engulfing pattern"""
    if len(candles) < 2:
        return False
    
    prev = candles[-2]
    curr = candles[-1]
    
    # Previous candle is bearish, current is bullish
    prev_bearish = prev.close < prev.open
    curr_bullish = curr.close > curr.open
    
    # Current body engulfs previous body
    engulfs = curr.open <= prev.close and curr.close >= prev.open
    
    return prev_bearish and curr_bullish and engulfs

def is_bearish_engulfing(candles: List[Candle]) -> bool:
    """Check if last two candles form bearish engulfing pattern"""
    if len(candles) < 2:
        return False
    
    prev = candles[-2]
    curr = candles[-1]
    
    # Previous candle is bullish, current is bearish
    prev_bullish = prev.close > prev.open
    curr_bearish = curr.close < curr.open
    
    # Current body engulfs previous body
    engulfs = curr.open >= prev.close and curr.close <= prev.open
    
    return prev_bullish and curr_bearish and engulfs

class IndicatorEngine:
    """Main indicator calculation engine"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            'ema_fast': 9,
            'ema_slow': 21,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'supertrend_period': 10,
            'supertrend_multiplier': 3.0,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2.0,
            'stoch_k': 14,
            'stoch_d': 3,
            'volume_ma_period': 20,
            'volume_spike_multiplier': 1.8,
            'atr_period': 14
        }
    
    def calculate_all(self, candles: List[Candle]) -> Dict:
        """Calculate all indicators"""
        if len(candles) < 50:  # Need minimum data
            return {}
        
        closes = [c.close for c in candles]
        
        # EMA
        ema_fast = calculate_ema(closes, self.config['ema_fast'])
        ema_slow = calculate_ema(closes, self.config['ema_slow'])
        
        # RSI
        rsi = calculate_rsi(closes, self.config['rsi_period'])
        
        # Supertrend
        supertrend, st_direction = calculate_supertrend(
            candles, 
            self.config['supertrend_period'],
            self.config['supertrend_multiplier']
        )
        
        # VWAP
        vwap = calculate_vwap(candles)
        
        # MACD
        macd = calculate_macd(
            closes,
            self.config['macd_fast'],
            self.config['macd_slow'],
            self.config['macd_signal']
        )
        
        # Bollinger Bands
        bb = calculate_bollinger_bands(
            closes,
            self.config['bb_period'],
            self.config['bb_std']
        )
        
        # Stochastic
        stoch = calculate_stochastic(
            candles,
            self.config['stoch_k'],
            self.config['stoch_d']
        )
        
        # OBV
        obv = calculate_obv(candles)
        
        # Volume MA
        volume_ma = calculate_volume_ma(candles, self.config['volume_ma_period'])
        
        # ATR
        atr = calculate_atr(candles, self.config['atr_period'])
        
        return {
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'rsi': rsi,
            'supertrend': supertrend,
            'st_direction': st_direction,
            'vwap': vwap,
            'macd': macd,
            'bb': bb,
            'stochastic': stoch,
            'obv': obv,
            'volume_ma': volume_ma,
            'atr': atr,
            'candles': candles
        }
