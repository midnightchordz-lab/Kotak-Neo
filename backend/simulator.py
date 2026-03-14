"""
Demo Simulation Mode
Simulates live price ticks and order execution without API connection
"""
import random
import math
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
from indicators import Candle

@dataclass
class SimulatedOrder:
    order_id: str
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    price: float
    order_type: str  # MKT, LIMIT, SL
    status: str  # PENDING, EXECUTED, CANCELLED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    fill_price: float = 0.0

@dataclass
class SimulatedPosition:
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    pnl: float = 0.0
    pnl_percent: float = 0.0

class MarketSimulator:
    """
    Simulates market data and order execution for demo mode
    """
    
    def __init__(self, initial_capital: float = 500000):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.available_margin = initial_capital
        self.used_margin = 0
        self.unrealized_pnl = 0
        self.realized_pnl = 0
        
        # Initialize with NIFTY and BANKNIFTY
        self.instruments = {
            'NIFTY': {
                'base_price': 24500,
                'volatility': 0.001,
                'lot_size': 25,
                'token': 'NIFTY'
            },
            'BANKNIFTY': {
                'base_price': 52000,
                'volatility': 0.0015,
                'lot_size': 15,
                'token': 'BANKNIFTY'
            }
        }
        
        self.current_prices: Dict[str, float] = {}
        self.candle_history: Dict[str, List[Candle]] = {}
        self.orders: List[SimulatedOrder] = []
        self.positions: Dict[str, SimulatedPosition] = {}
        self.trade_history: List[Dict] = []
        
        self._initialize_data()
    
    def _initialize_data(self):
        """Initialize historical candle data"""
        for symbol, config in self.instruments.items():
            self.current_prices[symbol] = config['base_price']
            self.candle_history[symbol] = self._generate_historical_candles(
                symbol,
                config['base_price'],
                config['volatility'],
                200  # Generate 200 candles of history
            )
    
    def _generate_historical_candles(self, symbol: str, base_price: float, volatility: float, count: int) -> List[Candle]:
        """Generate realistic historical OHLCV data"""
        candles = []
        current_price = base_price
        base_volume = 100000
        
        start_time = datetime.utcnow() - timedelta(minutes=count * 5)
        
        for i in range(count):
            # Simulate price movement with trend and noise
            trend = math.sin(i / 20) * 0.001  # Slight trending behavior
            noise = random.gauss(0, volatility)
            
            open_price = current_price
            change = (trend + noise) * current_price
            
            # Generate realistic OHLC
            high = max(open_price, open_price + change) + abs(random.gauss(0, volatility * current_price * 0.5))
            low = min(open_price, open_price + change) - abs(random.gauss(0, volatility * current_price * 0.5))
            close = open_price + change + random.gauss(0, volatility * current_price * 0.3)
            
            # Ensure OHLC integrity
            high = max(high, open_price, close)
            low = min(low, open_price, close)
            
            # Volume with spikes
            volume_multiplier = 1 + random.expovariate(3)
            if random.random() < 0.1:  # 10% chance of volume spike
                volume_multiplier *= 2
            volume = base_volume * volume_multiplier
            
            candles.append(Candle(
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=round(volume),
                timestamp=int((start_time + timedelta(minutes=i * 5)).timestamp() * 1000)
            ))
            
            current_price = close
        
        self.current_prices[symbol] = current_price
        return candles
    
    def tick(self, symbol: str) -> Dict:
        """
        Generate a new price tick and update candle
        Called every 1500ms in simulation mode
        """
        if symbol not in self.instruments:
            return {}
        
        config = self.instruments[symbol]
        current_price = self.current_prices[symbol]
        volatility = config['volatility']
        
        # Generate new tick
        change = random.gauss(0, volatility * current_price)
        new_price = current_price + change
        new_price = max(new_price, current_price * 0.95)  # Prevent crash
        new_price = min(new_price, current_price * 1.05)  # Prevent spike
        new_price = round(new_price, 2)
        
        self.current_prices[symbol] = new_price
        
        # Update current candle
        candles = self.candle_history[symbol]
        if candles:
            current_candle = candles[-1]
            current_candle.high = max(current_candle.high, new_price)
            current_candle.low = min(current_candle.low, new_price)
            current_candle.close = new_price
            current_candle.volume += random.randint(100, 1000)
        
        # Check if we need to create new candle (every 5 minutes)
        if candles:
            last_timestamp = datetime.fromtimestamp(candles[-1].timestamp / 1000)
            now = datetime.utcnow()
            if (now - last_timestamp).seconds >= 300:  # 5 minutes
                new_candle = Candle(
                    open=new_price,
                    high=new_price,
                    low=new_price,
                    close=new_price,
                    volume=random.randint(10000, 50000),
                    timestamp=int(now.timestamp() * 1000)
                )
                candles.append(new_candle)
                # Keep only last 200 candles
                if len(candles) > 200:
                    candles.pop(0)
        
        # Update positions P&L
        self._update_positions_pnl()
        
        # Check pending orders
        self._check_pending_orders(symbol, new_price)
        
        return {
            'symbol': symbol,
            'ltp': new_price,
            'change': change,
            'change_percent': (change / current_price) * 100,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_candles(self, symbol: str) -> List[Candle]:
        """Get candle history for a symbol"""
        return self.candle_history.get(symbol, [])
    
    def get_ltp(self, symbol: str) -> float:
        """Get last traded price"""
        return self.current_prices.get(symbol, 0)
    
    def place_order(self, symbol: str, side: str, quantity: int, 
                   order_type: str = 'MKT', price: float = 0) -> Dict:
        """
        Place a simulated order
        """
        if symbol not in self.instruments:
            return {'success': False, 'error': 'Invalid symbol'}
        
        config = self.instruments[symbol]
        ltp = self.current_prices[symbol]
        lot_size = config['lot_size']
        
        # Calculate margin required
        margin_required = ltp * quantity * 0.1  # 10% margin for F&O
        
        if margin_required > self.available_margin:
            return {'success': False, 'error': 'Insufficient margin'}
        
        order_id = f'SIM{datetime.utcnow().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'
        
        order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price if order_type != 'MKT' else ltp,
            order_type=order_type,
            status='PENDING' if order_type != 'MKT' else 'EXECUTED',
            fill_price=ltp if order_type == 'MKT' else 0
        )
        
        self.orders.append(order)
        
        # For market orders, execute immediately
        if order_type == 'MKT':
            self._execute_order(order, ltp)
        
        return {
            'success': True,
            'order_id': order_id,
            'message': f'Order {"executed" if order_type == "MKT" else "placed"} successfully'
        }
    
    def _execute_order(self, order: SimulatedOrder, fill_price: float):
        """Execute an order and update positions"""
        order.status = 'EXECUTED'
        order.fill_price = fill_price
        
        symbol = order.symbol
        config = self.instruments[symbol]
        
        # Calculate margin
        margin_used = fill_price * order.quantity * 0.1
        self.used_margin += margin_used
        self.available_margin -= margin_used
        
        # Update position
        if symbol in self.positions:
            pos = self.positions[symbol]
            if (order.side == 'BUY' and pos.quantity >= 0) or (order.side == 'SELL' and pos.quantity <= 0):
                # Adding to position
                total_value = pos.avg_price * abs(pos.quantity) + fill_price * order.quantity
                new_qty = pos.quantity + (order.quantity if order.side == 'BUY' else -order.quantity)
                if new_qty != 0:
                    pos.avg_price = total_value / abs(new_qty)
                pos.quantity = new_qty
            else:
                # Closing/reversing position
                close_qty = min(abs(pos.quantity), order.quantity)
                pnl = (fill_price - pos.avg_price) * close_qty * (1 if pos.quantity > 0 else -1)
                self.realized_pnl += pnl
                
                remaining = order.quantity - close_qty
                pos.quantity += (order.quantity if order.side == 'BUY' else -order.quantity)
                
                if pos.quantity != 0 and remaining > 0:
                    pos.avg_price = fill_price
        else:
            # New position
            self.positions[symbol] = SimulatedPosition(
                symbol=symbol,
                quantity=order.quantity if order.side == 'BUY' else -order.quantity,
                avg_price=fill_price,
                current_price=fill_price
            )
        
        # Add to trade history
        self.trade_history.append({
            'order_id': order.order_id,
            'symbol': symbol,
            'side': order.side,
            'quantity': order.quantity,
            'price': fill_price,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def _update_positions_pnl(self):
        """Update unrealized P&L for all positions"""
        self.unrealized_pnl = 0
        for symbol, pos in self.positions.items():
            if pos.quantity == 0:
                continue
            pos.current_price = self.current_prices.get(symbol, pos.avg_price)
            pos.pnl = (pos.current_price - pos.avg_price) * pos.quantity
            pos.pnl_percent = ((pos.current_price - pos.avg_price) / pos.avg_price) * 100 if pos.avg_price > 0 else 0
            self.unrealized_pnl += pos.pnl
    
    def _check_pending_orders(self, symbol: str, current_price: float):
        """Check and execute pending limit/SL orders"""
        for order in self.orders:
            if order.symbol != symbol or order.status != 'PENDING':
                continue
            
            execute = False
            if order.order_type == 'LIMIT':
                if order.side == 'BUY' and current_price <= order.price:
                    execute = True
                elif order.side == 'SELL' and current_price >= order.price:
                    execute = True
            elif order.order_type == 'SL':
                if order.side == 'BUY' and current_price >= order.price:
                    execute = True
                elif order.side == 'SELL' and current_price <= order.price:
                    execute = True
            
            if execute:
                self._execute_order(order, current_price)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order"""
        for order in self.orders:
            if order.order_id == order_id:
                if order.status == 'PENDING':
                    order.status = 'CANCELLED'
                    return {'success': True, 'message': 'Order cancelled'}
                else:
                    return {'success': False, 'error': f'Order already {order.status}'}
        return {'success': False, 'error': 'Order not found'}
    
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        return [
            {
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'pnl': round(pos.pnl, 2),
                'pnl_percent': round(pos.pnl_percent, 2)
            }
            for pos in self.positions.values() if pos.quantity != 0
        ]
    
    def get_orders(self) -> List[Dict]:
        """Get all orders"""
        return [
            {
                'order_id': o.order_id,
                'symbol': o.symbol,
                'side': o.side,
                'quantity': o.quantity,
                'price': o.price,
                'order_type': o.order_type,
                'status': o.status,
                'fill_price': o.fill_price,
                'timestamp': o.timestamp.isoformat()
            }
            for o in self.orders
        ]
    
    def get_trades(self) -> List[Dict]:
        """Get trade history"""
        return self.trade_history
    
    def get_limits(self) -> Dict:
        """Get account limits"""
        return {
            'total_cash': self.initial_capital,
            'available_margin': round(self.available_margin, 2),
            'used_margin': round(self.used_margin, 2),
            'unrealized_pnl': round(self.unrealized_pnl, 2),
            'realized_pnl': round(self.realized_pnl, 2),
            'net_worth': round(self.initial_capital + self.realized_pnl + self.unrealized_pnl, 2)
        }
    
    def get_quote(self, symbol: str) -> Dict:
        """Get current quote for a symbol"""
        if symbol not in self.instruments:
            return {}
        
        ltp = self.current_prices[symbol]
        config = self.instruments[symbol]
        candles = self.candle_history.get(symbol, [])
        
        open_price = candles[0].open if candles else ltp
        high = max(c.high for c in candles[-50:]) if candles else ltp
        low = min(c.low for c in candles[-50:]) if candles else ltp
        
        return {
            'symbol': symbol,
            'ltp': ltp,
            'open': open_price,
            'high': high,
            'low': low,
            'change': ltp - open_price,
            'change_percent': ((ltp - open_price) / open_price) * 100 if open_price > 0 else 0,
            'volume': sum(c.volume for c in candles[-50:]) if candles else 0,
            'lot_size': config['lot_size'],
            'bid': round(ltp - 0.05, 2),
            'ask': round(ltp + 0.05, 2),
            'bid_qty': random.randint(100, 1000),
            'ask_qty': random.randint(100, 1000)
        }
