"""
Backtesting Engine
Runs historical simulation using the confluence scoring engine
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from indicators import Candle
from confluence import ConfluenceEngine, SignalResult
import logging

logger = logging.getLogger(__name__)

@dataclass
class BacktestTrade:
    entry_price: float
    exit_price: float
    direction: str
    entry_bar: int
    exit_bar: int
    pnl: float
    pnl_percent: float
    score: float
    indicators_agreeing: int
    win: bool

@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    total_pnl: float = 0
    avg_pnl: float = 0
    max_drawdown: float = 0
    profit_factor: float = 0
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    score_breakdown: Dict[str, Dict] = field(default_factory=dict)

class Backtester:
    """
    Backtesting engine for the confluence scoring system
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            'initial_capital': 100000,
            'position_size': 1,  # Number of lots
            'lot_size': 25,  # NIFTY lot size
            'use_trailing_stop': False,
            'trail_atr_mult': 2.0,
            'min_score': 3.0,
            'min_agree': 5
        }
        self.confluence_engine = ConfluenceEngine({
            'min_score': self.config['min_score'],
            'min_agree': self.config['min_agree'],
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'stoch_oversold': 20,
            'stoch_overbought': 80,
            'volume_spike_mult': 1.8,
            'sl_atr_mult': 1.5,
            'tp_atr_mult': 3.0,
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
        })
    
    def run(self, candles: List[Candle], lookback: int = 50) -> BacktestResult:
        """
        Run backtest over historical candles
        
        Args:
            candles: List of historical candles
            lookback: Minimum candles needed before generating signals
        
        Returns:
            BacktestResult with all trades and statistics
        """
        if len(candles) < lookback + 10:
            return BacktestResult()
        
        result = BacktestResult()
        equity = self.config['initial_capital']
        result.equity_curve.append(equity)
        
        position = None  # Current position: {'direction', 'entry_price', 'entry_bar', 'sl', 'tp', 'score', 'agreeing'}
        peak_equity = equity
        max_dd = 0
        gross_profit = 0
        gross_loss = 0
        
        # Score breakdown tracking
        score_levels = {3: {'trades': 0, 'wins': 0}, 4: {'trades': 0, 'wins': 0}, 
                       5: {'trades': 0, 'wins': 0}, 6: {'trades': 0, 'wins': 0},
                       7: {'trades': 0, 'wins': 0}, 8: {'trades': 0, 'wins': 0}}
        
        for i in range(lookback, len(candles)):
            current_candle = candles[i]
            historical_candles = candles[:i+1]
            
            # Check for exit if in position
            if position:
                exit_triggered = False
                exit_price = 0
                exit_reason = ''
                
                if position['direction'] == 'BUY':
                    # Check stop loss
                    if current_candle.low <= position['sl']:
                        exit_triggered = True
                        exit_price = position['sl']
                        exit_reason = 'SL'
                    # Check take profit
                    elif current_candle.high >= position['tp']:
                        exit_triggered = True
                        exit_price = position['tp']
                        exit_reason = 'TP'
                else:  # SELL
                    # Check stop loss
                    if current_candle.high >= position['sl']:
                        exit_triggered = True
                        exit_price = position['sl']
                        exit_reason = 'SL'
                    # Check take profit
                    elif current_candle.low <= position['tp']:
                        exit_triggered = True
                        exit_price = position['tp']
                        exit_reason = 'TP'
                
                if exit_triggered:
                    # Calculate P&L
                    if position['direction'] == 'BUY':
                        pnl = (exit_price - position['entry_price']) * self.config['position_size'] * self.config['lot_size']
                    else:
                        pnl = (position['entry_price'] - exit_price) * self.config['position_size'] * self.config['lot_size']
                    
                    pnl_percent = (pnl / (position['entry_price'] * self.config['position_size'] * self.config['lot_size'])) * 100
                    is_win = pnl > 0
                    
                    # Record trade
                    trade = BacktestTrade(
                        entry_price=position['entry_price'],
                        exit_price=exit_price,
                        direction=position['direction'],
                        entry_bar=position['entry_bar'],
                        exit_bar=i,
                        pnl=round(pnl, 2),
                        pnl_percent=round(pnl_percent, 2),
                        score=position['score'],
                        indicators_agreeing=position['agreeing'],
                        win=is_win
                    )
                    result.trades.append(trade)
                    
                    # Update statistics
                    result.total_trades += 1
                    if is_win:
                        result.winning_trades += 1
                        gross_profit += pnl
                    else:
                        result.losing_trades += 1
                        gross_loss += abs(pnl)
                    
                    # Update score breakdown
                    for level in score_levels:
                        if position['score'] >= level:
                            score_levels[level]['trades'] += 1
                            if is_win:
                                score_levels[level]['wins'] += 1
                    
                    equity += pnl
                    result.equity_curve.append(equity)
                    
                    # Update drawdown
                    if equity > peak_equity:
                        peak_equity = equity
                    dd = (peak_equity - equity) / peak_equity * 100
                    if dd > max_dd:
                        max_dd = dd
                    
                    position = None
            
            # Check for entry if not in position
            if not position:
                signal = self.confluence_engine.score_signal(historical_candles[-lookback:])
                
                if signal.direction in ['BUY', 'SELL']:
                    position = {
                        'direction': signal.direction,
                        'entry_price': current_candle.close,
                        'entry_bar': i,
                        'sl': signal.stop_loss,
                        'tp': signal.take_profit,
                        'score': signal.net_score,
                        'agreeing': signal.indicators_agreeing
                    }
        
        # Close any remaining position at last candle
        if position:
            last_price = candles[-1].close
            if position['direction'] == 'BUY':
                pnl = (last_price - position['entry_price']) * self.config['position_size'] * self.config['lot_size']
            else:
                pnl = (position['entry_price'] - last_price) * self.config['position_size'] * self.config['lot_size']
            
            pnl_percent = (pnl / (position['entry_price'] * self.config['position_size'] * self.config['lot_size'])) * 100
            is_win = pnl > 0
            
            trade = BacktestTrade(
                entry_price=position['entry_price'],
                exit_price=last_price,
                direction=position['direction'],
                entry_bar=position['entry_bar'],
                exit_bar=len(candles) - 1,
                pnl=round(pnl, 2),
                pnl_percent=round(pnl_percent, 2),
                score=position['score'],
                indicators_agreeing=position['agreeing'],
                win=is_win
            )
            result.trades.append(trade)
            
            result.total_trades += 1
            if is_win:
                result.winning_trades += 1
                gross_profit += pnl
            else:
                result.losing_trades += 1
                gross_loss += abs(pnl)
            
            equity += pnl
            result.equity_curve.append(equity)
        
        # Calculate final statistics
        if result.total_trades > 0:
            result.win_rate = (result.winning_trades / result.total_trades) * 100
            result.total_pnl = sum(t.pnl for t in result.trades)
            result.avg_pnl = result.total_pnl / result.total_trades
            result.max_drawdown = max_dd
            result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate score breakdown win rates
        for level, data in score_levels.items():
            if data['trades'] > 0:
                data['win_rate'] = round((data['wins'] / data['trades']) * 100, 1)
            else:
                data['win_rate'] = 0
        
        result.score_breakdown = score_levels
        
        return result
