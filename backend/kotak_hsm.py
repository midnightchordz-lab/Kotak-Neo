"""
Kotak Neo HSM (High Speed Market) WebSocket Connection
Real-time market data streaming for live quotes, indices, and market depth
"""
import asyncio
import json
import logging
import socketio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MarketTick:
    """Represents a single market tick"""
    symbol: str
    exchange: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float
    change_percent: float
    timestamp: str
    bid: float = 0
    ask: float = 0
    oi: int = 0  # Open Interest for F&O

class KotakHSMWebSocket:
    """
    Kotak Neo HSM WebSocket client for real-time market data
    
    Usage:
        hsm = KotakHSMWebSocket(access_token, sid, server_id)
        await hsm.connect()
        await hsm.subscribe_index("nse_cm|Nifty 50&nse_cm|Nifty Bank&")
        await hsm.subscribe_scrip("nse_cm|11536&")
    """
    
    # WebSocket URLs
    WS_URL = "wss://wstreamer.kotaksecurities.com/feed/"
    
    def __init__(self, access_token: str, sid: str, server_id: str):
        """
        Initialize HSM WebSocket connection
        
        Args:
            access_token: Session token from login
            sid: Session ID from login
            server_id: Data center/server ID
        """
        self.access_token = access_token
        self.sid = sid
        self.server_id = server_id
        
        # Socket.IO client
        self.sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            logger=False,
            engineio_logger=False
        )
        
        # Callbacks
        self.on_tick: Optional[Callable[[MarketTick], None]] = None
        self.on_index_tick: Optional[Callable[[MarketTick], None]] = None
        self.on_depth: Optional[Callable[[Dict], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        
        # State
        self.is_connected = False
        self.subscribed_scrips: List[str] = []
        self.subscribed_indices: List[str] = []
        
        # Latest ticks cache
        self.latest_ticks: Dict[str, MarketTick] = {}
        
        # Setup event handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup Socket.IO event handlers"""
        
        @self.sio.event
        async def connect():
            logger.info("HSM WebSocket connected")
            self.is_connected = True
            if self.on_connect:
                self.on_connect()
        
        @self.sio.event
        async def disconnect():
            logger.info("HSM WebSocket disconnected")
            self.is_connected = False
            if self.on_disconnect:
                self.on_disconnect()
        
        @self.sio.event
        async def connect_error(data):
            logger.error(f"HSM WebSocket connection error: {data}")
            if self.on_error:
                self.on_error(str(data))
        
        # Market feed events
        @self.sio.on('stock')
        async def on_stock_feed(data):
            """Handle stock/scrip feed"""
            try:
                tick = self._parse_tick(data, is_index=False)
                if tick:
                    self.latest_ticks[tick.symbol] = tick
                    if self.on_tick:
                        self.on_tick(tick)
            except Exception as e:
                logger.error(f"Error parsing stock feed: {e}")
        
        @self.sio.on('index')
        async def on_index_feed(data):
            """Handle index feed (NIFTY, BANKNIFTY)"""
            try:
                tick = self._parse_tick(data, is_index=True)
                if tick:
                    self.latest_ticks[tick.symbol] = tick
                    if self.on_index_tick:
                        self.on_index_tick(tick)
                    elif self.on_tick:
                        self.on_tick(tick)
            except Exception as e:
                logger.error(f"Error parsing index feed: {e}")
        
        @self.sio.on('depth')
        async def on_depth_feed(data):
            """Handle market depth feed"""
            try:
                if self.on_depth:
                    self.on_depth(data)
            except Exception as e:
                logger.error(f"Error parsing depth feed: {e}")
        
        @self.sio.on('error')
        async def on_ws_error(data):
            """Handle WebSocket errors"""
            logger.error(f"HSM WebSocket error: {data}")
            if self.on_error:
                self.on_error(str(data))
    
    def _parse_tick(self, data: Dict, is_index: bool = False) -> Optional[MarketTick]:
        """Parse raw WebSocket tick data into MarketTick object"""
        try:
            # Kotak feed format
            # iv = LTP, ic = prev close, highPrice = high, lowPrice = low
            # openPrice = open, tvalue = timestamp, vol = volume
            ltp = float(data.get('iv', data.get('ltp', 0)))
            prev_close = float(data.get('ic', data.get('close', ltp)))
            
            change = ltp - prev_close
            change_percent = (change / prev_close * 100) if prev_close > 0 else 0
            
            symbol = data.get('tk', data.get('symbol', 'UNKNOWN'))
            exchange = data.get('e', data.get('exchange', 'nse_cm'))
            
            return MarketTick(
                symbol=symbol,
                exchange=exchange,
                ltp=ltp,
                open=float(data.get('openPrice', data.get('open', ltp))),
                high=float(data.get('highPrice', data.get('high', ltp))),
                low=float(data.get('lowPrice', data.get('low', ltp))),
                close=prev_close,
                volume=int(data.get('vol', data.get('volume', 0))),
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                timestamp=data.get('tvalue', datetime.utcnow().isoformat()),
                bid=float(data.get('bp', data.get('bid', 0))),
                ask=float(data.get('sp', data.get('ask', 0))),
                oi=int(data.get('oi', 0))
            )
        except Exception as e:
            logger.error(f"Error parsing tick: {e}, data: {data}")
            return None
    
    async def connect(self) -> bool:
        """
        Connect to Kotak HSM WebSocket
        
        Returns:
            True if connected successfully
        """
        try:
            # Use Socket.IO connection with proper URL format
            # URL: https://wstreamer.kotaksecurities.com?access_token=TOKEN
            # Path: /feed/
            ws_url = f"https://wstreamer.kotaksecurities.com?access_token={self.access_token}"
            
            logger.info(f"Connecting to HSM WebSocket at: {ws_url[:50]}...")
            logger.info(f"Using SID: {self.sid}, Server ID: {self.server_id}")
            
            await self.sio.connect(
                ws_url,
                socketio_path='/feed/',
                transports=['websocket', 'polling']
            )
            
            self.is_connected = True
            logger.info("HSM WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to HSM WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        try:
            await self.sio.disconnect()
            self.is_connected = False
            logger.info("HSM WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    async def subscribe_scrip(self, scrips: str):
        """
        Subscribe to scrip/stock feeds
        
        Args:
            scrips: Format "exchange|token&exchange|token&"
                   Example: "nse_cm|11536&nse_fo|43651&"
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot subscribe")
            return False
        
        try:
            # Emit subscription message
            await self.sio.emit('pageload', {'inputtoken': scrips})
            self.subscribed_scrips.append(scrips)
            logger.info(f"Subscribed to scrips: {scrips}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to scrips: {e}")
            return False
    
    async def subscribe_index(self, indices: str):
        """
        Subscribe to index feeds (NIFTY, BANKNIFTY)
        
        Args:
            indices: Format "exchange|indexname&exchange|indexname&"
                    Example: "nse_cm|Nifty 50&nse_cm|Nifty Bank&"
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot subscribe")
            return False
        
        try:
            await self.sio.emit('pageload', {'inputtoken': indices, 'isIndex': True})
            self.subscribed_indices.append(indices)
            logger.info(f"Subscribed to indices: {indices}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to indices: {e}")
            return False
    
    async def subscribe_depth(self, scrips: str):
        """
        Subscribe to market depth (order book)
        
        Args:
            scrips: Format "exchange|token&"
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot subscribe")
            return False
        
        try:
            await self.sio.emit('depthsub', {'inputtoken': scrips})
            logger.info(f"Subscribed to depth: {scrips}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to depth: {e}")
            return False
    
    async def unsubscribe(self, scrips: str):
        """Unsubscribe from feeds"""
        try:
            await self.sio.emit('pageunload', {'inputtoken': scrips})
            logger.info(f"Unsubscribed from: {scrips}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
    
    def get_latest_tick(self, symbol: str) -> Optional[MarketTick]:
        """Get the latest cached tick for a symbol"""
        return self.latest_ticks.get(symbol)
    
    def get_all_ticks(self) -> Dict[str, MarketTick]:
        """Get all cached ticks"""
        return self.latest_ticks.copy()


# Global HSM instance
hsm_client: Optional[KotakHSMWebSocket] = None

def get_hsm_client() -> Optional[KotakHSMWebSocket]:
    """Get the global HSM client instance"""
    return hsm_client

def set_hsm_client(client: KotakHSMWebSocket):
    """Set the global HSM client instance"""
    global hsm_client
    hsm_client = client
