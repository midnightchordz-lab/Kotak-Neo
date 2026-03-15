"""
Kotak Neo HSM (High Speed Market) WebSocket Connection
Real-time market data streaming for live quotes, indices, and market depth

Uses raw websockets for Kotak's market feed based on:
wss://wstreamer.kotaksecurities.com/feed/?EIO=3&transport=websocket&access_token=TOKEN

Connection methods:
1. Use session edit_token directly (from MPIN validation)
2. Get separate WebSocket token from /feed/auth/token (using consumer key/secret)
"""
import asyncio
import json
import logging
import websockets
import httpx
import base64
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
    WS_AUTH_URL = "https://wstreamer.kotaksecurities.com/feed/auth/token"
    
    def __init__(self, access_token: str, sid: str = "", server_id: str = "", 
                 consumer_key: str = "", consumer_secret: str = ""):
        """
        Initialize HSM WebSocket
        
        Args:
            access_token: Session token from MPIN validation (edit_token)
            sid: Session ID
            server_id: HSM Server ID
            consumer_key: API consumer key (optional, for alternative auth)
            consumer_secret: API consumer secret (optional, for alternative auth)
        """
        self.access_token = access_token
        self.sid = sid
        self.server_id = server_id
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        
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
    
    async def get_ws_token(self) -> Optional[str]:
        """
        Get WebSocket-specific token from the auth endpoint
        
        Uses consumer_key and consumer_secret to authenticate
        POST to https://wstreamer.kotaksecurities.com/feed/auth/token
        """
        if not self.consumer_key or not self.consumer_secret:
            logger.warning("Consumer key/secret not provided for WS auth")
            return None
        
        try:
            auth_str = f"{self.consumer_key}:{self.consumer_secret}"
            auth_base64 = base64.b64encode(auth_str.encode()).decode()
            
            payload = {"authentication": auth_base64}
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.WS_AUTH_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                logger.info(f"WS Auth Response Status: {response.status_code}")
                logger.info(f"WS Auth Response: {response.text[:200]}")
                
                if response.status_code == 200:
                    data = response.json()
                    ws_token = data.get('token', data.get('access_token', ''))
                    if ws_token:
                        logger.info("Got WebSocket-specific token!")
                        return ws_token
                        
        except Exception as e:
            logger.error(f"Error getting WS token: {e}")
        
        return None
    
    async def connect(self, max_retries: int = 3) -> bool:
        """
        Connect to Kotak HSM WebSocket
        
        Note: If welcome message is received as "broadcast" event (not "message"),
        we need to disconnect and reconnect (per Kotak documentation)
        """
        for attempt in range(max_retries):
            try:
                # Build WebSocket URL with access token only
                # According to howutrade.github.io/kotak-websocket/
                # The URL only needs access_token (the session token)
                ws_url = f"{self.WS_BASE}?EIO=3&transport=websocket&access_token={self.access_token}"
                
                logger.info(f"Connecting to HSM WebSocket (attempt {attempt + 1}/{max_retries})...")
                logger.info(f"URL: {ws_url[:80]}...")
                
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
                
                # Wait for initial messages
                # We expect: "0{sid...}" then "40" then "42[...]"
                welcome_received = False
                message_type_welcome = False
                
                for i in range(5):  # Read up to 5 messages to find welcome
                    try:
                        msg = await asyncio.wait_for(self.ws.recv(), timeout=5)
                        logger.info(f"HSM Message {i+1}: {msg[:150] if len(msg) > 150 else msg}")
                        
                        # Check for "message" event (good - we can proceed)
                        if '42["message"' in msg.lower():
                            logger.info("Received 'message' type welcome - connection good!")
                            welcome_received = True
                            message_type_welcome = True
                            break
                        
                        # Check for "broadcast" event (need to retry per documentation)
                        if '42["broadcast"' in msg.lower():
                            logger.warning("Received 'broadcast' type welcome - will retry connection")
                            welcome_received = True
                            message_type_welcome = False
                            break
                            
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for message {i+1}")
                        break
                
                # If we got broadcast, close and retry
                if welcome_received and not message_type_welcome:
                    await self.ws.close()
                    await asyncio.sleep(1)
                    continue
                
                # If we got here, we either have a good connection or no welcome at all
                # Try proceeding anyway (some versions don't send message welcome)
                self.is_connected = True
                
                # Start ping task (every 10 seconds)
                self._ping_task = asyncio.create_task(self._ping_loop())
                
                # Start receive task
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                logger.info("HSM WebSocket connected successfully!")
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"HSM connection timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"HSM connection error (attempt {attempt + 1}): {e}")
            
            await asyncio.sleep(1)  # Wait before retry
        
        logger.error(f"HSM connection failed after {max_retries} attempts")
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
