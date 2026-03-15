"""
Live Price Poller - REST API based real-time price updates
Polls Kotak quotes API every 2 seconds for live market data
Alternative to WebSocket when HSM is not accessible
"""
import asyncio
import logging
from typing import Dict, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class LivePrice:
    """Live price data structure"""
    symbol: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    change: float
    change_percent: float
    volume: int
    timestamp: str
    bid: float = 0
    ask: float = 0


class LivePricePoller:
    """
    Polls Kotak REST API for live prices
    Provides near-real-time market data without WebSocket
    """
    
    def __init__(self, poll_interval: float = 2.0):
        """
        Initialize the poller
        
        Args:
            poll_interval: Seconds between polls (default 2 seconds)
        """
        self.poll_interval = poll_interval
        self.is_running = False
        self._poll_task: Optional[asyncio.Task] = None
        
        # Symbols to poll
        self.index_symbols = ['NIFTY', 'BANKNIFTY']
        self.stock_symbols: List[str] = []
        
        # Latest prices cache
        self.latest_prices: Dict[str, LivePrice] = {}
        
        # Callbacks
        self.on_price_update: Optional[Callable[[LivePrice], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Reference to kotak_api (set externally)
        self.kotak_api = None
        
        # Stats
        self.poll_count = 0
        self.last_poll_time: Optional[datetime] = None
        self.errors_count = 0
    
    def set_kotak_api(self, api):
        """Set the Kotak API client reference"""
        self.kotak_api = api
    
    def add_symbol(self, symbol: str):
        """Add a symbol to poll"""
        symbol_upper = symbol.upper()
        if symbol_upper not in self.stock_symbols and symbol_upper not in self.index_symbols:
            self.stock_symbols.append(symbol_upper)
            logger.info(f"Added symbol to poll: {symbol_upper}")
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from polling"""
        symbol_upper = symbol.upper()
        if symbol_upper in self.stock_symbols:
            self.stock_symbols.remove(symbol_upper)
            logger.info(f"Removed symbol from poll: {symbol_upper}")
    
    async def start(self):
        """Start the polling loop"""
        if self.is_running:
            logger.warning("Poller already running")
            return
        
        if not self.kotak_api:
            logger.error("Kotak API not set. Call set_kotak_api() first.")
            return
        
        self.is_running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Live price poller started (interval: {self.poll_interval}s)")
    
    async def stop(self):
        """Stop the polling loop"""
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Live price poller stopped")
    
    async def _poll_loop(self):
        """Main polling loop"""
        while self.is_running:
            try:
                await self._poll_prices()
                self.poll_count += 1
                self.last_poll_time = datetime.now()
            except Exception as e:
                self.errors_count += 1
                logger.error(f"Poll error: {e}")
                if self.on_error:
                    self.on_error(str(e))
            
            await asyncio.sleep(self.poll_interval)
    
    async def _poll_prices(self):
        """Poll prices for all subscribed symbols"""
        if not self.kotak_api or not self.kotak_api.session.is_authenticated:
            return
        
        # Poll indices
        for symbol in self.index_symbols:
            try:
                result = await self.kotak_api.get_index_quote(symbol)
                if result.get('success') and result.get('quotes'):
                    quotes = result['quotes']
                    if isinstance(quotes, list) and len(quotes) > 0:
                        q = quotes[0]
                        ohlc = q.get('ohlc', {})
                        
                        price = LivePrice(
                            symbol=symbol,
                            ltp=float(q.get('ltp', 0)),
                            open=float(ohlc.get('open', 0)) if ohlc else 0,
                            high=float(ohlc.get('high', 0)) if ohlc else 0,
                            low=float(ohlc.get('low', 0)) if ohlc else 0,
                            close=float(ohlc.get('close', 0)) if ohlc else 0,
                            change=float(q.get('change', 0)),
                            change_percent=float(q.get('per_change', 0)),
                            volume=int(q.get('last_volume', 0)),
                            timestamp=datetime.now().isoformat(),
                            bid=float(q.get('depth', {}).get('buy', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                            ask=float(q.get('depth', {}).get('sell', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                        )
                        
                        self.latest_prices[symbol] = price
                        
                        if self.on_price_update:
                            self.on_price_update(price)
                            
            except Exception as e:
                logger.error(f"Error polling {symbol}: {e}")
        
        # Poll stocks (if any added)
        for symbol in self.stock_symbols:
            try:
                result = await self.kotak_api.get_quotes(
                    [{"exchange_segment": "nse_cm", "symbol": symbol}],
                    quote_type='all',
                    is_index=False
                )
                if result.get('success') and result.get('quotes'):
                    quotes = result['quotes']
                    if isinstance(quotes, list) and len(quotes) > 0:
                        q = quotes[0]
                        ohlc = q.get('ohlc', {})
                        
                        price = LivePrice(
                            symbol=symbol,
                            ltp=float(q.get('ltp', 0)),
                            open=float(ohlc.get('open', 0)) if ohlc else 0,
                            high=float(ohlc.get('high', 0)) if ohlc else 0,
                            low=float(ohlc.get('low', 0)) if ohlc else 0,
                            close=float(ohlc.get('close', 0)) if ohlc else 0,
                            change=float(q.get('change', 0)),
                            change_percent=float(q.get('per_change', 0)),
                            volume=int(q.get('last_volume', 0)),
                            timestamp=datetime.now().isoformat(),
                        )
                        
                        self.latest_prices[symbol] = price
                        
                        if self.on_price_update:
                            self.on_price_update(price)
                            
            except Exception as e:
                logger.error(f"Error polling stock {symbol}: {e}")
    
    def get_price(self, symbol: str) -> Optional[LivePrice]:
        """Get latest cached price for a symbol"""
        return self.latest_prices.get(symbol.upper())
    
    def get_all_prices(self) -> Dict[str, LivePrice]:
        """Get all cached prices"""
        return self.latest_prices.copy()
    
    def get_ltp(self, symbol: str) -> float:
        """Get just the LTP for a symbol"""
        price = self.latest_prices.get(symbol.upper())
        return price.ltp if price else 0.0
    
    def get_stats(self) -> Dict:
        """Get poller statistics"""
        return {
            "is_running": self.is_running,
            "poll_interval": self.poll_interval,
            "poll_count": self.poll_count,
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "errors_count": self.errors_count,
            "subscribed_indices": self.index_symbols,
            "subscribed_stocks": self.stock_symbols,
            "cached_prices": {k: v.ltp for k, v in self.latest_prices.items()}
        }


# Global instance
live_price_poller = LivePricePoller()


def get_live_poller() -> LivePricePoller:
    """Get the global live price poller instance"""
    return live_price_poller
