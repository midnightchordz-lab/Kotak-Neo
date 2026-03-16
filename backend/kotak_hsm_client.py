"""
Kotak NEO HSM WebSocket Client for Live Market Data
Based on official Kotak WebSocket library (hslib.js, demo.js)

HSM = High Speed Market data streaming
URL: wss://mlhsm.kotaksecurities.com
"""

import asyncio
import json
import struct
import logging
from typing import Dict, Optional, Callable, List, Any
from datetime import datetime
import websockets

logger = logging.getLogger(__name__)

# Constants from hslib.js
class ReqType:
    CONNECTION = "cn"
    SCRIP_SUBS = "mws"      # Market Watch Subscribe
    SCRIP_UNSUBS = "mwu"    # Market Watch Unsubscribe
    INDEX_SUBS = "ifs"      # Index Feed Subscribe
    INDEX_UNSUBS = "ifu"    # Index Feed Unsubscribe
    DEPTH_SUBS = "dps"      # Depth Subscribe
    DEPTH_UNSUBS = "dpu"    # Depth Unsubscribe
    HEARTBEAT = "ti"        # Throttling Interval (heartbeat)


class BinRespType:
    CONNECTION = 1
    THROTTLING = 2
    ACK = 3
    SUBSCRIBE = 4
    UNSUBSCRIBE = 5
    DATA = 6
    CH_PAUSE = 7
    CH_RESUME = 8
    SNAPSHOT = 9


# Field mappings from hslib.js SCRIP_MAPPING
SCRIP_FIELDS = {
    0: ("ftm0", "date"),
    1: ("dtm1", "date"),
    2: ("fdtm", "date"),
    3: ("ltt", "date"),      # Last Trade Time
    4: ("v", "long"),        # Volume
    5: ("ltp", "float"),     # Last Traded Price
    6: ("ltq", "long"),      # Last Traded Quantity
    7: ("tbq", "long"),      # Total Buy Quantity
    8: ("tsq", "long"),      # Total Sell Quantity
    9: ("bp", "float"),      # Best Bid Price
    10: ("sp", "float"),     # Best Ask Price
    11: ("bq", "long"),      # Best Bid Quantity
    12: ("bs", "long"),      # Best Ask Quantity (sell)
    13: ("ap", "float"),     # Average Price (VWAP)
    14: ("lo", "float"),     # Low
    15: ("h", "float"),      # High
    16: ("lcl", "float"),    # Lower Circuit Limit
    17: ("ucl", "float"),    # Upper Circuit Limit
    18: ("yh", "float"),     # Year High
    19: ("yl", "float"),     # Year Low
    20: ("op", "float"),     # Open Price
    21: ("c", "float"),      # Close Price
    22: ("oi", "long"),      # Open Interest
    23: ("mul", "long"),     # Multiplier
    24: ("prec", "long"),    # Precision
    25: ("cng", "float"),    # Change
    26: ("nc", "string"),    # Percent Change
    27: ("to", "float"),     # Turnover
    51: ("name", "string"),
    52: ("tk", "string"),    # Token/Symbol
    53: ("e", "string"),     # Exchange
    54: ("ts", "string"),    # Trading Symbol
}

INDEX_FIELDS = {
    0: ("ftm0", "date"),
    1: ("dtm1", "date"),
    2: ("iv", "float"),      # Index Value (LTP)
    3: ("ic", "float"),      # Index Close
    4: ("tvalue", "date"),
    5: ("highPrice", "float"),
    6: ("lowPrice", "float"),
    7: ("openingPrice", "float"),
    8: ("mul", "long"),
    9: ("prec", "long"),
    10: ("cng", "float"),    # Change
    11: ("nc", "string"),    # Percent Change
    51: ("name", "string"),
    52: ("tk", "string"),
    53: ("e", "string"),
    54: ("ts", "string"),
}


class KotakHSMClient:
    """
    WebSocket client for Kotak NEO HSM (High Speed Market data)
    
    Usage:
        client = KotakHSMClient(token, sid)
        await client.connect()
        await client.subscribe_index(["nse_cm|Nifty 50", "nse_cm|Nifty Bank"])
        await client.subscribe_scrip(["nse_fo|53290"])  # Use instrument tokens
    """
    
    HSM_URL = "wss://mlhsm.kotaksecurities.com"
    HEARTBEAT_INTERVAL = 30  # seconds
    
    def __init__(self, token: str, sid: str):
        self.token = token
        self.sid = sid
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.subscriptions: Dict[str, List[str]] = {
            "scrip": [],
            "index": [],
            "depth": []
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, Callable] = {}
        self._latest_data: Dict[str, Dict] = {}
        self._ack_num = 0
        self._counter = 0
        
    def on_data(self, callback: Callable[[str, Dict], None]):
        """Register callback for market data updates"""
        self._callbacks["data"] = callback
        
    def on_connect(self, callback: Callable[[], None]):
        """Register callback for connection events"""
        self._callbacks["connect"] = callback
        
    def on_disconnect(self, callback: Callable[[], None]):
        """Register callback for disconnection events"""
        self._callbacks["disconnect"] = callback
        
    def on_error(self, callback: Callable[[str], None]):
        """Register callback for errors"""
        self._callbacks["error"] = callback
    
    async def connect(self) -> bool:
        """Connect to Kotak HSM WebSocket"""
        try:
            logger.info(f"Connecting to Kotak HSM: {self.HSM_URL}")
            
            self.ws = await websockets.connect(
                self.HSM_URL,
                ping_interval=None,  # We handle our own heartbeat
                ping_timeout=None,
                close_timeout=10
            )
            
            # Send connection request
            conn_req = {
                "type": ReqType.CONNECTION,
                "Authorization": self.token,
                "Sid": self.sid
            }
            await self.ws.send(json.dumps(conn_req))
            logger.info("Sent connection request to HSM")
            
            # Wait for connection response
            response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            
            # Parse response (could be binary or JSON)
            if isinstance(response, bytes):
                result = self._parse_binary_response(response)
                if result and result.get("stat") == "Ok":
                    self.connected = True
                    logger.info("HSM connection successful")
                else:
                    logger.error(f"HSM connection failed: {result}")
                    return False
            else:
                result = json.loads(response)
                logger.info(f"HSM connection response: {result}")
                self.connected = True
            
            # Start heartbeat and receive tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            if "connect" in self._callbacks:
                self._callbacks["connect"]()
                
            return True
            
        except asyncio.TimeoutError:
            logger.error("HSM connection timeout")
            return False
        except Exception as e:
            logger.error(f"HSM connection error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def disconnect(self):
        """Disconnect from HSM"""
        self.connected = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        if self._receive_task:
            self._receive_task.cancel()
            
        if self.ws:
            await self.ws.close()
            self.ws = None
            
        if "disconnect" in self._callbacks:
            self._callbacks["disconnect"]()
            
        logger.info("Disconnected from HSM")
    
    async def subscribe_index(self, indices: List[str], channel: int = 1):
        """
        Subscribe to index feeds
        
        Args:
            indices: List of index identifiers like ["nse_cm|Nifty 50", "nse_cm|Nifty Bank"]
            channel: Channel number (1-10)
        """
        if not self.connected or not self.ws:
            logger.error("Not connected to HSM")
            return False
            
        scrips = "&".join(indices) + "&"
        req = {
            "type": ReqType.INDEX_SUBS,
            "scrips": scrips,
            "channelnum": channel
        }
        
        await self.ws.send(json.dumps(req))
        self.subscriptions["index"].extend(indices)
        logger.info(f"Subscribed to indices: {indices}")
        return True
    
    async def subscribe_scrip(self, scrips: List[str], channel: int = 1):
        """
        Subscribe to scrip/option feeds
        
        Args:
            scrips: List of scrip identifiers like ["nse_fo|53290", "nse_fo|53291"]
            channel: Channel number (1-10)
        """
        if not self.connected or not self.ws:
            logger.error("Not connected to HSM")
            return False
            
        scrips_str = "&".join(scrips) + "&"
        req = {
            "type": ReqType.SCRIP_SUBS,
            "scrips": scrips_str,
            "channelnum": channel
        }
        
        await self.ws.send(json.dumps(req))
        self.subscriptions["scrip"].extend(scrips)
        logger.info(f"Subscribed to scrips: {scrips[:5]}... (total: {len(scrips)})")
        return True
    
    async def subscribe_depth(self, scrips: List[str], channel: int = 1):
        """Subscribe to market depth"""
        if not self.connected or not self.ws:
            return False
            
        scrips_str = "&".join(scrips) + "&"
        req = {
            "type": ReqType.DEPTH_SUBS,
            "scrips": scrips_str,
            "channelnum": channel
        }
        
        await self.ws.send(json.dumps(req))
        self.subscriptions["depth"].extend(scrips)
        logger.info(f"Subscribed to depth: {scrips}")
        return True
    
    async def unsubscribe_scrip(self, scrips: List[str], channel: int = 1):
        """Unsubscribe from scrip feeds"""
        if not self.connected or not self.ws:
            return False
            
        scrips_str = "&".join(scrips) + "&"
        req = {
            "type": ReqType.SCRIP_UNSUBS,
            "scrips": scrips_str,
            "channelnum": channel
        }
        
        await self.ws.send(json.dumps(req))
        for s in scrips:
            if s in self.subscriptions["scrip"]:
                self.subscriptions["scrip"].remove(s)
        return True
    
    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """Get latest data for a symbol"""
        return self._latest_data.get(symbol)
    
    def get_all_latest_data(self) -> Dict[str, Dict]:
        """Get all latest data"""
        return self._latest_data.copy()
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to keep connection alive"""
        while self.connected and self.ws:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                if self.ws:
                    heartbeat = {"type": ReqType.HEARTBEAT, "scrips": ""}
                    await self.ws.send(json.dumps(heartbeat))
                    logger.debug("Sent HSM heartbeat")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _receive_loop(self):
        """Receive and process messages from HSM"""
        while self.connected and self.ws:
            try:
                message = await self.ws.recv()
                
                if isinstance(message, bytes):
                    # Binary market data
                    parsed = self._parse_binary_response(message)
                    if parsed:
                        self._process_parsed_data(parsed)
                else:
                    # JSON response
                    data = json.loads(message)
                    logger.debug(f"HSM JSON response: {data}")
                    
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("HSM connection closed")
                self.connected = False
                if "disconnect" in self._callbacks:
                    self._callbacks["disconnect"]()
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                if "error" in self._callbacks:
                    self._callbacks["error"](str(e))
    
    def _parse_binary_response(self, data: bytes) -> Optional[Dict]:
        """Parse binary response from HSM based on hslib.js protocol"""
        try:
            if len(data) < 4:
                return None
                
            pos = 0
            
            # Read message length (2 bytes)
            msg_len = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            # Read response type (1 byte)
            resp_type = data[pos]
            pos += 1
            
            if resp_type == BinRespType.CONNECTION:
                return self._parse_connection_response(data, pos)
            elif resp_type == BinRespType.DATA:
                return self._parse_data_response(data, pos)
            elif resp_type == BinRespType.SUBSCRIBE:
                return self._parse_subscribe_response(data, pos)
            else:
                logger.debug(f"Unknown response type: {resp_type}")
                return {"type": resp_type, "raw": data.hex()}
                
        except Exception as e:
            logger.error(f"Binary parse error: {e}")
            return None
    
    def _parse_connection_response(self, data: bytes, pos: int) -> Dict:
        """Parse connection response"""
        try:
            # Skip version bytes
            pos += 2
            
            # Read field count
            field_count = data[pos]
            pos += 1
            
            result = {"type": "connection"}
            
            if field_count >= 1:
                # Read status field
                fid = data[pos]
                pos += 1
                val_len = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2
                status = data[pos:pos+val_len].decode('utf-8')
                pos += val_len
                
                if status == 'K':
                    result["stat"] = "Ok"
                    result["msg"] = "connected"
                else:
                    result["stat"] = "NotOk"
                    result["msg"] = "connection failed"
                    
                # Read ack count if present
                if field_count >= 2:
                    fid = data[pos]
                    pos += 1
                    val_len = struct.unpack('>H', data[pos:pos+2])[0]
                    pos += 2
                    self._ack_num = struct.unpack('>I', data[pos:pos+val_len].ljust(4, b'\x00'))[0]
                    
            return result
            
        except Exception as e:
            logger.error(f"Connection response parse error: {e}")
            return {"stat": "NotOk", "msg": str(e)}
    
    def _parse_data_response(self, data: bytes, pos: int) -> Dict:
        """Parse market data response"""
        try:
            result = {"type": "data", "quotes": []}
            
            # Skip ack number if present
            if self._ack_num > 0:
                self._counter += 1
                msg_num = struct.unpack('>I', data[pos:pos+4])[0]
                pos += 4
                
                # Send acknowledgement periodically
                if self._counter >= self._ack_num:
                    self._counter = 0
                    # Would send ack here
            
            # Read number of quotes
            if pos + 2 > len(data):
                return result
                
            num_quotes = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            for _ in range(num_quotes):
                if pos >= len(data):
                    break
                    
                quote, pos = self._parse_single_quote(data, pos)
                if quote:
                    result["quotes"].append(quote)
                    
            return result
            
        except Exception as e:
            logger.error(f"Data response parse error: {e}")
            return {"type": "data", "quotes": [], "error": str(e)}
    
    def _parse_single_quote(self, data: bytes, pos: int) -> tuple:
        """Parse a single quote from binary data"""
        try:
            quote = {}
            
            # Read topic type (2 bytes - sf, if, dp)
            if pos + 2 > len(data):
                return None, pos
                
            topic_type = data[pos:pos+2].decode('utf-8')
            pos += 2
            quote["_type"] = topic_type
            
            # Determine field mapping based on type
            if topic_type == "sf":  # Scrip feed
                field_map = SCRIP_FIELDS
            elif topic_type == "if":  # Index feed
                field_map = INDEX_FIELDS
            else:
                field_map = SCRIP_FIELDS  # Default
            
            # Read number of fields
            if pos >= len(data):
                return quote, pos
                
            num_fields = data[pos]
            pos += 1
            
            for _ in range(num_fields):
                if pos + 3 > len(data):
                    break
                    
                # Read field ID
                fid = data[pos]
                pos += 1
                
                # Read value length
                val_len = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2
                
                if pos + val_len > len(data):
                    break
                    
                # Get field info
                field_info = field_map.get(fid, (f"field_{fid}", "bytes"))
                field_name, field_type = field_info
                
                # Parse value based on type
                val_bytes = data[pos:pos+val_len]
                pos += val_len
                
                if field_type == "float":
                    if val_len == 4:
                        quote[field_name] = struct.unpack('>f', val_bytes)[0]
                    elif val_len == 8:
                        quote[field_name] = struct.unpack('>d', val_bytes)[0]
                elif field_type == "long":
                    if val_len <= 4:
                        quote[field_name] = struct.unpack('>I', val_bytes.rjust(4, b'\x00'))[0]
                    else:
                        quote[field_name] = struct.unpack('>Q', val_bytes.rjust(8, b'\x00'))[0]
                elif field_type == "string":
                    quote[field_name] = val_bytes.decode('utf-8', errors='ignore')
                elif field_type == "date":
                    if val_len >= 4:
                        timestamp = struct.unpack('>I', val_bytes[:4])[0]
                        quote[field_name] = timestamp
                else:
                    quote[field_name] = val_bytes.hex()
            
            return quote, pos
            
        except Exception as e:
            logger.error(f"Quote parse error: {e}")
            return None, pos
    
    def _parse_subscribe_response(self, data: bytes, pos: int) -> Dict:
        """Parse subscription response"""
        try:
            result = {"type": "subscribe", "stat": "Ok"}
            return result
        except Exception as e:
            return {"type": "subscribe", "stat": "NotOk", "error": str(e)}
    
    def _process_parsed_data(self, parsed: Dict):
        """Process parsed data and update latest data store"""
        if parsed.get("type") == "data" and "quotes" in parsed:
            for quote in parsed["quotes"]:
                # Use symbol/token as key
                symbol = quote.get("tk") or quote.get("ts") or quote.get("name", "unknown")
                
                # Update latest data
                self._latest_data[symbol] = {
                    "symbol": symbol,
                    "trading_symbol": quote.get("ts", ""),
                    "exchange": quote.get("e", ""),
                    "ltp": quote.get("ltp") or quote.get("iv", 0),
                    "open": quote.get("op") or quote.get("openingPrice", 0),
                    "high": quote.get("h") or quote.get("highPrice", 0),
                    "low": quote.get("lo") or quote.get("lowPrice", 0),
                    "close": quote.get("c") or quote.get("ic", 0),
                    "change": quote.get("cng", 0),
                    "change_percent": quote.get("nc", "0"),
                    "volume": quote.get("v", 0),
                    "open_interest": quote.get("oi", 0),
                    "bid_price": quote.get("bp", 0),
                    "ask_price": quote.get("sp", 0),
                    "bid_qty": quote.get("bq", 0),
                    "ask_qty": quote.get("bs", 0),
                    "vwap": quote.get("ap", 0),
                    "last_trade_time": quote.get("ltt", 0),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Call data callback
                if "data" in self._callbacks:
                    self._callbacks["data"](symbol, self._latest_data[symbol])


# Singleton instance
_hsm_client: Optional[KotakHSMClient] = None


def get_hsm_client() -> Optional[KotakHSMClient]:
    """Get the singleton HSM client instance"""
    return _hsm_client


def create_hsm_client(token: str, sid: str) -> KotakHSMClient:
    """Create and return a new HSM client instance"""
    global _hsm_client
    _hsm_client = KotakHSMClient(token, sid)
    return _hsm_client


async def test_hsm_connection(token: str, sid: str):
    """Test HSM connection"""
    client = KotakHSMClient(token, sid)
    
    def on_data(symbol, data):
        print(f"[DATA] {symbol}: LTP={data.get('ltp')}, Change={data.get('change_percent')}%")
    
    def on_connect():
        print("[CONNECTED] HSM connection established")
    
    def on_disconnect():
        print("[DISCONNECTED] HSM connection closed")
    
    client.on_data(on_data)
    client.on_connect(on_connect)
    client.on_disconnect(on_disconnect)
    
    if await client.connect():
        # Subscribe to NIFTY and BANKNIFTY indices
        await client.subscribe_index(["nse_cm|Nifty 50", "nse_cm|Nifty Bank"])
        
        # Keep running for 60 seconds
        await asyncio.sleep(60)
        
        await client.disconnect()
    else:
        print("Failed to connect to HSM")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        token = sys.argv[1]
        sid = sys.argv[2]
        asyncio.run(test_hsm_connection(token, sid))
    else:
        print("Usage: python kotak_hsm_client.py <token> <sid>")
