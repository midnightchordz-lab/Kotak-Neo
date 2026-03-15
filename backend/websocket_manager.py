"""
WebSocket Manager for Real-time Market Data Streaming
Provides live price updates, signals, and notifications
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)

class SubscriptionType(Enum):
    QUOTES = "quotes"
    CANDLES = "candles"
    SIGNALS = "signals"
    OPTIONS = "options"
    POSITIONS = "positions"
    ORDERS = "orders"

@dataclass
class WebSocketMessage:
    """Standard WebSocket message format"""
    type: str
    data: Any
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))

class ConnectionManager:
    """
    Manages WebSocket connections and subscriptions
    Handles real-time data broadcasting to connected clients
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Subscription mapping: symbol -> set of websockets
        self.quote_subscriptions: Dict[str, Set[WebSocket]] = {}
        self.signal_subscriptions: Dict[str, Set[WebSocket]] = {}
        self.options_subscriptions: Dict[str, Set[WebSocket]] = {}
        
        # Global subscriptions (positions, orders)
        self.position_subscribers: Set[WebSocket] = set()
        self.order_subscribers: Set[WebSocket] = set()
        
        # Broadcasting task
        self._broadcast_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        
        # Send welcome message
        welcome = WebSocketMessage(
            type="connected",
            data={"message": "Connected to COSTAR real-time stream"}
        )
        await websocket.send_text(welcome.to_json())
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        self.active_connections.discard(websocket)
        
        # Remove from all subscriptions
        for symbol_subs in self.quote_subscriptions.values():
            symbol_subs.discard(websocket)
        for symbol_subs in self.signal_subscriptions.values():
            symbol_subs.discard(websocket)
        for symbol_subs in self.options_subscriptions.values():
            symbol_subs.discard(websocket)
        
        self.position_subscribers.discard(websocket)
        self.order_subscribers.discard(websocket)
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, subscription_type: str, 
                       symbols: Optional[list] = None):
        """Subscribe to a data stream"""
        if subscription_type == "quotes" and symbols:
            for symbol in symbols:
                if symbol not in self.quote_subscriptions:
                    self.quote_subscriptions[symbol] = set()
                self.quote_subscriptions[symbol].add(websocket)
            logger.info(f"Subscribed to quotes: {symbols}")
            
        elif subscription_type == "signals" and symbols:
            for symbol in symbols:
                if symbol not in self.signal_subscriptions:
                    self.signal_subscriptions[symbol] = set()
                self.signal_subscriptions[symbol].add(websocket)
            logger.info(f"Subscribed to signals: {symbols}")
            
        elif subscription_type == "options" and symbols:
            for symbol in symbols:
                if symbol not in self.options_subscriptions:
                    self.options_subscriptions[symbol] = set()
                self.options_subscriptions[symbol].add(websocket)
            logger.info(f"Subscribed to options: {symbols}")
            
        elif subscription_type == "positions":
            self.position_subscribers.add(websocket)
            logger.info("Subscribed to positions")
            
        elif subscription_type == "orders":
            self.order_subscribers.add(websocket)
            logger.info("Subscribed to orders")
        
        # Send confirmation
        confirm = WebSocketMessage(
            type="subscribed",
            data={"subscription": subscription_type, "symbols": symbols or []}
        )
        await websocket.send_text(confirm.to_json())
    
    async def unsubscribe(self, websocket: WebSocket, subscription_type: str,
                         symbols: Optional[list] = None):
        """Unsubscribe from a data stream"""
        if subscription_type == "quotes" and symbols:
            for symbol in symbols:
                if symbol in self.quote_subscriptions:
                    self.quote_subscriptions[symbol].discard(websocket)
                    
        elif subscription_type == "signals" and symbols:
            for symbol in symbols:
                if symbol in self.signal_subscriptions:
                    self.signal_subscriptions[symbol].discard(websocket)
                    
        elif subscription_type == "options" and symbols:
            for symbol in symbols:
                if symbol in self.options_subscriptions:
                    self.options_subscriptions[symbol].discard(websocket)
                    
        elif subscription_type == "positions":
            self.position_subscribers.discard(websocket)
            
        elif subscription_type == "orders":
            self.order_subscribers.discard(websocket)
    
    async def broadcast_quote(self, symbol: str, quote_data: Dict):
        """Broadcast quote update to subscribers"""
        subscribers = self.quote_subscriptions.get(symbol, set())
        if not subscribers:
            return
        
        message = WebSocketMessage(
            type="quote",
            data={"symbol": symbol, **quote_data}
        )
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def broadcast_signal(self, symbol: str, signal_data: Dict):
        """Broadcast signal update to subscribers"""
        subscribers = self.signal_subscriptions.get(symbol, set())
        if not subscribers:
            return
        
        message = WebSocketMessage(
            type="signal",
            data={"symbol": symbol, **signal_data}
        )
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def broadcast_options(self, symbol: str, options_data: Dict):
        """Broadcast options chain update to subscribers"""
        subscribers = self.options_subscriptions.get(symbol, set())
        if not subscribers:
            return
        
        message = WebSocketMessage(
            type="options",
            data={"symbol": symbol, **options_data}
        )
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def broadcast_positions(self, positions_data: list):
        """Broadcast positions update to subscribers"""
        if not self.position_subscribers:
            return
        
        message = WebSocketMessage(
            type="positions",
            data={"positions": positions_data}
        )
        await self._broadcast_to_subscribers(self.position_subscribers, message)
    
    async def broadcast_orders(self, orders_data: list):
        """Broadcast orders update to subscribers"""
        if not self.order_subscribers:
            return
        
        message = WebSocketMessage(
            type="orders",
            data={"orders": orders_data}
        )
        await self._broadcast_to_subscribers(self.order_subscribers, message)
    
    async def broadcast_notification(self, notification: Dict):
        """Broadcast notification to all connected clients"""
        message = WebSocketMessage(
            type="notification",
            data=notification
        )
        await self._broadcast_to_all(message)
    
    async def _broadcast_to_subscribers(self, subscribers: Set[WebSocket], 
                                        message: WebSocketMessage):
        """Send message to a set of subscribers"""
        disconnected = set()
        message_text = message.to_json()
        
        for websocket in subscribers:
            try:
                await websocket.send_text(message_text)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(ws)
    
    async def _broadcast_to_all(self, message: WebSocketMessage):
        """Send message to all connected clients"""
        await self._broadcast_to_subscribers(self.active_connections.copy(), message)
    
    async def handle_message(self, websocket: WebSocket, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "subscribe":
                await self.subscribe(
                    websocket,
                    data.get("type", "quotes"),
                    data.get("symbols", [])
                )
            elif action == "unsubscribe":
                await self.unsubscribe(
                    websocket,
                    data.get("type", "quotes"),
                    data.get("symbols", [])
                )
            elif action == "ping":
                pong = WebSocketMessage(type="pong", data={})
                await websocket.send_text(pong.to_json())
            else:
                error = WebSocketMessage(
                    type="error",
                    data={"message": f"Unknown action: {action}"}
                )
                await websocket.send_text(error.to_json())
                
        except json.JSONDecodeError:
            error = WebSocketMessage(
                type="error",
                data={"message": "Invalid JSON message"}
            )
            await websocket.send_text(error.to_json())
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error = WebSocketMessage(
                type="error",
                data={"message": str(e)}
            )
            await websocket.send_text(error.to_json())
    
    def get_stats(self) -> Dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "quote_subscriptions": {
                symbol: len(subs) for symbol, subs in self.quote_subscriptions.items()
            },
            "signal_subscriptions": {
                symbol: len(subs) for symbol, subs in self.signal_subscriptions.items()
            },
            "options_subscriptions": {
                symbol: len(subs) for symbol, subs in self.options_subscriptions.items()
            },
            "position_subscribers": len(self.position_subscribers),
            "order_subscribers": len(self.order_subscribers)
        }


# Global connection manager instance
ws_manager = ConnectionManager()
