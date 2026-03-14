"""
Confluence Scoring Engine
Weighted voting system for 10 technical indicators
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from indicators import (
    Candle, IndicatorEngine, 
    is_bullish_engulfing, is_bearish_engulfing
)
import logging

logger = logging.getLogger(__name__)

@dataclass
class IndicatorVote:
    name: str
    vote: int  # 1 for bullish, -1 for bearish, 0 for neutral
    weight: float
    detail: str
    value: Optional[float] = None

@dataclass
class SignalResult:
    direction: str  # 'BUY', 'SELL', 'NEUTRAL'
    net_score: float
    indicators_agreeing: int
    total_indicators: int
    confidence: float
    votes: List[IndicatorVote] = field(default_factory=list)
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    atr: float = 0.0

class ConfluenceEngine:
    """
    Confluence scoring engine with weighted voting system
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            # Thresholds
            'min_score': 3.0,
            'min_agree': 5,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'stoch_oversold': 20,
            'stoch_overbought': 80,
            'volume_spike_mult': 1.8,
            'sl_atr_mult': 1.5,
            'tp_atr_mult': 3.0,
            
            # Indicator weights (total = 10)
            'weights': {
                'ema_crossover': 1.5,
                'rsi': 1.0,
                'supertrend': 1.5,
                'vwap': 1.0,
                'macd': 1.0,
                'bollinger': 0.75,
                'stochastic': 0.75,
                'volume_spike': 1.0,
                'obv_trend': 0.75,
                'price_action': 0.75
            }
        }
        self.indicator_engine = IndicatorEngine()
    
    def score_signal(self, candles: List[Candle]) -> SignalResult:
        """
        Calculate confluence score based on all 10 indicators
        """
        if len(candles) < 50:
            return SignalResult(
                direction='NEUTRAL',
                net_score=0,
                indicators_agreeing=0,
                total_indicators=10,
                confidence=0,
                votes=[]
            )
        
        # Calculate all indicators
        indicators = self.indicator_engine.calculate_all(candles)
        if not indicators:
            return SignalResult(
                direction='NEUTRAL',
                net_score=0,
                indicators_agreeing=0,
                total_indicators=10,
                confidence=0,
                votes=[]
            )
        
        votes = []
        current_price = candles[-1].close
        
        # 1. EMA Crossover
        vote = self._vote_ema_crossover(indicators)
        votes.append(vote)
        
        # 2. RSI
        vote = self._vote_rsi(indicators)
        votes.append(vote)
        
        # 3. Supertrend
        vote = self._vote_supertrend(indicators, current_price)
        votes.append(vote)
        
        # 4. VWAP
        vote = self._vote_vwap(indicators, current_price)
        votes.append(vote)
        
        # 5. MACD Histogram
        vote = self._vote_macd(indicators)
        votes.append(vote)
        
        # 6. Bollinger Bands
        vote = self._vote_bollinger(indicators, current_price)
        votes.append(vote)
        
        # 7. Stochastic
        vote = self._vote_stochastic(indicators)
        votes.append(vote)
        
        # 8. Volume Spike
        vote = self._vote_volume_spike(indicators, candles)
        votes.append(vote)
        
        # 9. OBV Trend
        vote = self._vote_obv_trend(indicators)
        votes.append(vote)
        
        # 10. Price Action
        vote = self._vote_price_action(candles)
        votes.append(vote)
        
        # Calculate net weighted score
        net_score = sum(v.vote * v.weight for v in votes)
        bullish_count = sum(1 for v in votes if v.vote > 0)
        bearish_count = sum(1 for v in votes if v.vote < 0)
        
        # Determine direction and agreeing count
        if net_score > 0:
            direction = 'BUY'
            indicators_agreeing = bullish_count
        elif net_score < 0:
            direction = 'SELL'
            indicators_agreeing = bearish_count
        else:
            direction = 'NEUTRAL'
            indicators_agreeing = 0
        
        # Calculate confidence
        max_possible_score = sum(self.config['weights'].values())
        confidence = abs(net_score) / max_possible_score * 100
        
        # Calculate SL/TP based on ATR
        atr = indicators['atr'][-1] if indicators.get('atr') else 0
        sl, tp, rr = self._calculate_risk_reward(current_price, atr, direction)
        
        return SignalResult(
            direction=direction if self._signal_fires(net_score, indicators_agreeing) else 'NEUTRAL',
            net_score=round(net_score, 2),
            indicators_agreeing=indicators_agreeing,
            total_indicators=10,
            confidence=round(confidence, 1),
            votes=votes,
            entry_price=current_price,
            stop_loss=round(sl, 2),
            take_profit=round(tp, 2),
            risk_reward=round(rr, 2),
            atr=round(atr, 2)
        )
    
    def _signal_fires(self, score: float, agreeing: int) -> bool:
        """Check if signal meets threshold requirements"""
        return abs(score) >= self.config['min_score'] and agreeing >= self.config['min_agree']
    
    def _calculate_risk_reward(self, price: float, atr: float, direction: str) -> Tuple[float, float, float]:
        """Calculate Stop Loss, Take Profit, and Risk:Reward ratio"""
        if atr == 0:
            return 0, 0, 0
        
        sl_distance = atr * self.config['sl_atr_mult']
        tp_distance = atr * self.config['tp_atr_mult']
        
        if direction == 'BUY':
            sl = price - sl_distance
            tp = price + tp_distance
        elif direction == 'SELL':
            sl = price + sl_distance
            tp = price - tp_distance
        else:
            return 0, 0, 0
        
        rr = tp_distance / sl_distance if sl_distance > 0 else 0
        return sl, tp, rr
    
    def _vote_ema_crossover(self, indicators: Dict) -> IndicatorVote:
        """EMA Crossover: Fast EMA above/below Slow EMA"""
        weight = self.config['weights']['ema_crossover']
        
        ema_fast = indicators.get('ema_fast', [])
        ema_slow = indicators.get('ema_slow', [])
        
        if not ema_fast or not ema_slow:
            return IndicatorVote('EMA Crossover', 0, weight, 'Insufficient data')
        
        # Align lengths
        min_len = min(len(ema_fast), len(ema_slow))
        fast = ema_fast[-min_len:]
        slow = ema_slow[-min_len:]
        
        if len(fast) < 2:
            return IndicatorVote('EMA Crossover', 0, weight, 'Insufficient data')
        
        # Check crossover
        prev_diff = fast[-2] - slow[-2]
        curr_diff = fast[-1] - slow[-1]
        
        if prev_diff < 0 and curr_diff > 0:
            return IndicatorVote('EMA Crossover', 1, weight, f'Bullish crossover (EMA9: {fast[-1]:.2f} > EMA21: {slow[-1]:.2f})', fast[-1])
        elif prev_diff > 0 and curr_diff < 0:
            return IndicatorVote('EMA Crossover', -1, weight, f'Bearish crossover (EMA9: {fast[-1]:.2f} < EMA21: {slow[-1]:.2f})', fast[-1])
        elif curr_diff > 0:
            return IndicatorVote('EMA Crossover', 1, weight, f'Fast EMA above slow (EMA9: {fast[-1]:.2f} > EMA21: {slow[-1]:.2f})', fast[-1])
        else:
            return IndicatorVote('EMA Crossover', -1, weight, f'Fast EMA below slow (EMA9: {fast[-1]:.2f} < EMA21: {slow[-1]:.2f})', fast[-1])
    
    def _vote_rsi(self, indicators: Dict) -> IndicatorVote:
        """RSI: Oversold/Overbought conditions"""
        weight = self.config['weights']['rsi']
        rsi = indicators.get('rsi', [])
        
        if not rsi:
            return IndicatorVote('RSI', 0, weight, 'Insufficient data')
        
        current_rsi = rsi[-1]
        
        if current_rsi < self.config['rsi_oversold']:
            return IndicatorVote('RSI', 1, weight, f'Oversold ({current_rsi:.1f} < {self.config["rsi_oversold"]})', current_rsi)
        elif current_rsi > self.config['rsi_overbought']:
            return IndicatorVote('RSI', -1, weight, f'Overbought ({current_rsi:.1f} > {self.config["rsi_overbought"]})', current_rsi)
        elif current_rsi < 50:
            return IndicatorVote('RSI', 1, weight, f'Below 50 ({current_rsi:.1f})', current_rsi)
        else:
            return IndicatorVote('RSI', -1, weight, f'Above 50 ({current_rsi:.1f})', current_rsi)
    
    def _vote_supertrend(self, indicators: Dict, price: float) -> IndicatorVote:
        """Supertrend: Price above/below supertrend line"""
        weight = self.config['weights']['supertrend']
        st = indicators.get('supertrend', [])
        st_dir = indicators.get('st_direction', [])
        
        if not st or not st_dir:
            return IndicatorVote('Supertrend', 0, weight, 'Insufficient data')
        
        current_st = st[-1]
        current_dir = st_dir[-1]
        
        if current_dir == 1:
            return IndicatorVote('Supertrend', 1, weight, f'Uptrend (Price: {price:.2f} > ST: {current_st:.2f})', current_st)
        else:
            return IndicatorVote('Supertrend', -1, weight, f'Downtrend (Price: {price:.2f} < ST: {current_st:.2f})', current_st)
    
    def _vote_vwap(self, indicators: Dict, price: float) -> IndicatorVote:
        """VWAP: Price above/below VWAP"""
        weight = self.config['weights']['vwap']
        vwap = indicators.get('vwap', [])
        
        if not vwap:
            return IndicatorVote('VWAP', 0, weight, 'Insufficient data')
        
        current_vwap = vwap[-1]
        
        if price > current_vwap:
            return IndicatorVote('VWAP', 1, weight, f'Price above VWAP ({price:.2f} > {current_vwap:.2f})', current_vwap)
        else:
            return IndicatorVote('VWAP', -1, weight, f'Price below VWAP ({price:.2f} < {current_vwap:.2f})', current_vwap)
    
    def _vote_macd(self, indicators: Dict) -> IndicatorVote:
        """MACD: Histogram direction"""
        weight = self.config['weights']['macd']
        macd = indicators.get('macd', {})
        histogram = macd.get('histogram', [])
        
        if not histogram or len(histogram) < 2:
            return IndicatorVote('MACD', 0, weight, 'Insufficient data')
        
        current = histogram[-1]
        prev = histogram[-2]
        
        if current > 0 and current > prev:
            return IndicatorVote('MACD', 1, weight, f'Bullish momentum increasing ({current:.4f})', current)
        elif current > 0:
            return IndicatorVote('MACD', 1, weight, f'Bullish momentum ({current:.4f})', current)
        elif current < 0 and current < prev:
            return IndicatorVote('MACD', -1, weight, f'Bearish momentum increasing ({current:.4f})', current)
        else:
            return IndicatorVote('MACD', -1, weight, f'Bearish momentum ({current:.4f})', current)
    
    def _vote_bollinger(self, indicators: Dict, price: float) -> IndicatorVote:
        """Bollinger Bands: Price relative to middle band"""
        weight = self.config['weights']['bollinger']
        bb = indicators.get('bb', {})
        middle = bb.get('middle', [])
        upper = bb.get('upper', [])
        lower = bb.get('lower', [])
        
        if not middle or not upper or not lower:
            return IndicatorVote('Bollinger', 0, weight, 'Insufficient data')
        
        mid = middle[-1]
        up = upper[-1]
        low = lower[-1]
        
        if price > mid:
            if price > up:
                return IndicatorVote('Bollinger', -1, weight, f'Above upper band ({price:.2f} > {up:.2f})', mid)
            return IndicatorVote('Bollinger', 1, weight, f'Above middle ({price:.2f} > {mid:.2f})', mid)
        else:
            if price < low:
                return IndicatorVote('Bollinger', 1, weight, f'Below lower band ({price:.2f} < {low:.2f})', mid)
            return IndicatorVote('Bollinger', -1, weight, f'Below middle ({price:.2f} < {mid:.2f})', mid)
    
    def _vote_stochastic(self, indicators: Dict) -> IndicatorVote:
        """Stochastic: K/D crossover and levels"""
        weight = self.config['weights']['stochastic']
        stoch = indicators.get('stochastic', {})
        k = stoch.get('k', [])
        d = stoch.get('d', [])
        
        if not k or not d or len(k) < 2:
            return IndicatorVote('Stochastic', 0, weight, 'Insufficient data')
        
        k_val = k[-1]
        d_val = d[-1]
        
        if k_val < self.config['stoch_oversold']:
            return IndicatorVote('Stochastic', 1, weight, f'Oversold (K: {k_val:.1f}, D: {d_val:.1f})', k_val)
        elif k_val > self.config['stoch_overbought']:
            return IndicatorVote('Stochastic', -1, weight, f'Overbought (K: {k_val:.1f}, D: {d_val:.1f})', k_val)
        elif k_val > d_val:
            return IndicatorVote('Stochastic', 1, weight, f'K above D (K: {k_val:.1f} > D: {d_val:.1f})', k_val)
        else:
            return IndicatorVote('Stochastic', -1, weight, f'K below D (K: {k_val:.1f} < D: {d_val:.1f})', k_val)
    
    def _vote_volume_spike(self, indicators: Dict, candles: List[Candle]) -> IndicatorVote:
        """Volume Spike: Volume > 1.8x average with bullish candle"""
        weight = self.config['weights']['volume_spike']
        volume_ma = indicators.get('volume_ma', [])
        
        if not volume_ma or len(candles) < 2:
            return IndicatorVote('Volume Spike', 0, weight, 'Insufficient data')
        
        current_volume = candles[-1].volume
        avg_volume = volume_ma[-1]
        threshold = avg_volume * self.config['volume_spike_mult']
        
        is_spike = current_volume > threshold
        is_bullish_candle = candles[-1].close > candles[-1].open
        is_bearish_candle = candles[-1].close < candles[-1].open
        
        ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        if is_spike and is_bullish_candle:
            return IndicatorVote('Volume Spike', 1, weight, f'Bullish volume spike ({ratio:.1f}x avg)', current_volume)
        elif is_spike and is_bearish_candle:
            return IndicatorVote('Volume Spike', -1, weight, f'Bearish volume spike ({ratio:.1f}x avg)', current_volume)
        else:
            return IndicatorVote('Volume Spike', 0, weight, f'No spike ({ratio:.1f}x avg)', current_volume)
    
    def _vote_obv_trend(self, indicators: Dict) -> IndicatorVote:
        """OBV Trend: Rising or falling over 5 bars"""
        weight = self.config['weights']['obv_trend']
        obv = indicators.get('obv', [])
        
        if len(obv) < 5:
            return IndicatorVote('OBV Trend', 0, weight, 'Insufficient data')
        
        obv_5 = obv[-5:]
        rising = all(obv_5[i] < obv_5[i+1] for i in range(4))
        falling = all(obv_5[i] > obv_5[i+1] for i in range(4))
        
        change = obv_5[-1] - obv_5[0]
        
        if rising:
            return IndicatorVote('OBV Trend', 1, weight, f'Rising OBV (5-bar trend)', obv[-1])
        elif falling:
            return IndicatorVote('OBV Trend', -1, weight, f'Falling OBV (5-bar trend)', obv[-1])
        elif change > 0:
            return IndicatorVote('OBV Trend', 1, weight, f'OBV trending up', obv[-1])
        else:
            return IndicatorVote('OBV Trend', -1, weight, f'OBV trending down', obv[-1])
    
    def _vote_price_action(self, candles: List[Candle]) -> IndicatorVote:
        """Price Action: Engulfing patterns"""
        weight = self.config['weights']['price_action']
        
        if len(candles) < 2:
            return IndicatorVote('Price Action', 0, weight, 'Insufficient data')
        
        if is_bullish_engulfing(candles):
            return IndicatorVote('Price Action', 1, weight, 'Bullish engulfing pattern')
        elif is_bearish_engulfing(candles):
            return IndicatorVote('Price Action', -1, weight, 'Bearish engulfing pattern')
        else:
            # Check if candle is bullish or bearish
            if candles[-1].close > candles[-1].open:
                return IndicatorVote('Price Action', 1, weight, 'Bullish candle')
            else:
                return IndicatorVote('Price Action', -1, weight, 'Bearish candle')
