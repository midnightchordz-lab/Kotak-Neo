"""
Kotak Neo HSM (High Speed Market) WebSocket Connection
Real-time market data streaming for live quotes, indices, and market depth

Uses raw websockets for Kotak's market feed based on:
wss://wstreamer.kotaksecurities.com/feed/?EIO=3&transport=websocket&access_token=TOKEN
"""
import asyncio
import json
import logging
import websockets
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
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
    oi: int = 0

class KotakHSMWebSocket:
    """
    Kotak Neo HSM WebSocket client using raw websockets
    
    Based on: https://howutrade.github.io/kotak-websocket/
    
    Connection flow:
    1. Connect to wss://wstreamer.kotaksecurities.com/feed/?EIO=3&transport=websocket&access_token=TOKEN
    2. Wait for welcome message
    3. Send subscription: 42["pageload", {"inputtoken":"nse_cm|Nifty 50"}]
    4. Receive market data
    5. Send ping "3" every 10 seconds
    """
    
    # WebSocket URL
    WS_BASE = "wss://wstreamer.kotaksecurities.com/feed/"
    
    def __init__(self, access_token: str, sid: str = "", server_id: str = ""):
        """Initialize HSM WebSocket"""
        self.access_token = access_token
        self.sid = sid
        self.server_id = server_id
        
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.subscribed_scrips: List[str] = []
        self.subscribed_indices: List[str] = []
        self.latest_ticks: Dict[str, MarketTick] = {}
        
        # Background tasks
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.on_tick: Optional[Callable[[MarketTick], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    async def connect(self) -> bool:
        """Connect to Kotak HSM WebSocket"""
        try:
            # Build WebSocket URL with ALL required parameters
            # According to Kotak documentation, we need: access_token, sid, AND server_id
            ws_url = f"{self.WS_BASE}?EIO=3&transport=websocket&access_token={self.access_token}"
            
            # Add SID if available
            if self.sid:
                ws_url += f"&sid={self.sid}"
            
            # Add Server ID if available (critical for HSM connection)
            if self.server_id:
                ws_url += f"&server_id={self.server_id}"
            
            logger.info(f"Connecting to HSM WebSocket...")
            logger.info(f"URL params - access_token: {self.access_token[:20]}..., sid: {self.sid[:20] if self.sid else 'N/A'}..., server_id: {self.server_id or 'N/A'}")
            
            # Connect with longer timeout
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    ws_url,
                    ping_interval=None,  # We'll handle pings manually
                    ping_timeout=None,
                    close_timeout=10
                ),
                timeout=30
            )
            
            logger.info("WebSocket connected, waiting for welcome...")
            
            # Wait for welcome message
            welcome = await asyncio.wait_for(self.ws.recv(), timeout=10)
            logger.info(f"Received: {welcome[:100] if len(welcome) > 100 else welcome}")
            
            # Check for broadcast (error) message
            if "broadcast" in str(welcome).lower():
                logger.error("Received broadcast message - authentication failed")
                await self.ws.close()
                return False
            
            self.is_connected = True
            
            # Start ping task (every 10 seconds)
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info("HSM WebSocket connected successfully!")
            return True
            
        except asyncio.TimeoutError:
            logger.error("HSM connection timeout")
            return False
        except Exception as e:
            logger.error(f"HSM connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.is_connected = False
        
        if self._ping_task:
            self._ping_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        if self.ws:
            await self.ws.close()
        
        logger.info("HSM WebSocket disconnected")
    
    async def _ping_loop(self):
        """Send ping every 10 seconds to keep connection alive"""
        while self.is_connected:
            try:
                await asyncio.sleep(10)
                if self.ws and self.is_connected:
                    await self.ws.send("3")  # Engine.IO ping
                    logger.debug("Sent ping")
            except Exception as e:
                logger.error(f"Ping error: {e}")
                break
    
    async def _receive_loop(self):
        """Receive and process messages"""
        while self.is_connected and self.ws:
            try:
                message = await self.ws.recv()
                await self._process_message(message)
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            # Engine.IO messages start with a number
            # 0 = open, 2 = ping, 3 = pong, 4 = message
            # 42 = Socket.IO event message
            
            if message.startswith("42"):
                # Parse Socket.IO event
                data = json.loads(message[2:])
                event_name = data[0] if isinstance(data, list) else None
                event_data = data[1] if isinstance(data, list) and len(data) > 1 else data
                
                if event_name == "stock" or event_name == "sf":
                    tick = self._parse_tick(event_data)
                    if tick:
                        self.latest_ticks[tick.symbol] = tick
                        if self.on_tick:
                            self.on_tick(tick)
                            
                elif event_name == "index" or event_name == "if":
                    tick = self._parse_tick(event_data, is_index=True)
                    if tick:
                        self.latest_ticks[tick.symbol] = tick
                        if self.on_tick:
                            self.on_tick(tick)
                            
                elif event_name == "depth" or event_name == "dp":
                    logger.debug(f"Depth update: {event_data}")
                    
            elif message == "3":
                # Pong response, ignore
                pass
            elif message.startswith("0"):
                # Open/handshake
                logger.info("Handshake received")
                
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON message: {message[:50]}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    def _parse_tick(self, data: Any, is_index: bool = False) -> Optional[MarketTick]:
        """Parse tick data from WebSocket message"""
        try:
            if isinstance(data, dict):
                ltp = float(data.get('iv', data.get('ltp', data.get('lastPrice', 0))))
                prev_close = float(data.get('ic', data.get('close', data.get('previousClose', ltp))))
                
                change = ltp - prev_close
                change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                
                return MarketTick(
                    symbol=data.get('tk', data.get('symbol', data.get('tradingSymbol', 'UNKNOWN'))),
                    exchange=data.get('e', data.get('exchange', 'nse_cm')),
                    ltp=ltp,
                    open=float(data.get('openPrice', data.get('open', ltp))),
                    high=float(data.get('highPrice', data.get('high', ltp))),
                    low=float(data.get('lowPrice', data.get('low', ltp))),
                    close=prev_close,
                    volume=int(data.get('vol', data.get('volume', data.get('totalTradedVolume', 0)))),
                    change=round(change, 2),
                    change_percent=round(change_pct, 2),
                    timestamp=str(data.get('tvalue', data.get('lastUpdateTime', datetime.utcnow().isoformat()))),
                    bid=float(data.get('bp', data.get('bidPrice', 0))),
                    ask=float(data.get('sp', data.get('askPrice', 0))),
                    oi=int(data.get('oi', data.get('openInterest', 0)))
                )
        except Exception as e:
            logger.error(f"Error parsing tick: {e}")
        return None
    
    async def subscribe_index(self, indices: str) -> bool:
        """
        Subscribe to index feeds
        
        Args:
            indices: Format "nse_cm|Nifty 50&nse_cm|Nifty Bank&"
        """
        if not self.is_connected or not self.ws:
            logger.warning("Not connected")
            return False
        
        try:
            # Format: 42["pageload", {"inputtoken": "nse_cm|Nifty 50&"}]
            msg = json.dumps(["pageload", {"inputtoken": indices}])
            await self.ws.send(f"42{msg}")
            
            self.subscribed_indices.append(indices)
            logger.info(f"Subscribed to indices: {indices}")
            return True
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False
    
    async def subscribe_scrip(self, scrips: str) -> bool:
        """
        Subscribe to scrip/stock feeds
        
        Args:
            scrips: Format "nse_cm|11536&nse_fo|43651&"
        """
        if not self.is_connected or not self.ws:
            logger.warning("Not connected")
            return False
        
        try:
            msg = json.dumps(["pageload", {"inputtoken": scrips}])
            await self.ws.send(f"42{msg}")
            
            self.subscribed_scrips.append(scrips)
            logger.info(f"Subscribed to scrips: {scrips}")
            return True
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False
    
    async def unsubscribe(self, tokens: str) -> bool:
        """Unsubscribe from feeds"""
        if not self.is_connected or not self.ws:
            return False
        
        try:
            msg = json.dumps(["pageunload", {"inputtoken": tokens}])
            await self.ws.send(f"42{msg}")
            logger.info(f"Unsubscribed: {tokens}")
            return True
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return False
    
    def get_latest_tick(self, symbol: str) -> Optional[MarketTick]:
        """Get latest cached tick"""
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
