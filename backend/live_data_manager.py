"""
Live Data Manager - Integrates Kotak HSM WebSocket for real-time market data

This service manages the WebSocket connection and provides live data to the application.
It automatically subscribes to indices and options when authenticated.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime

from kotak_hsm_client import KotakHSMClient, create_hsm_client, get_hsm_client

logger = logging.getLogger(__name__)


class LiveDataManager:
    """
    Manages live market data via WebSocket connection
    
    Features:
    - Auto-connect on authentication
    - Auto-subscribe to indices (NIFTY, BANKNIFTY)
    - Subscribe to option instruments on demand
    - Callback-based data updates
    - Reconnection handling
    """
    
    def __init__(self):
        self.hsm_client: Optional[KotakHSMClient] = None
        self.is_connected = False
        self.token: Optional[str] = None
        self.sid: Optional[str] = None
        
        # Live data stores
        self.index_data: Dict[str, Dict] = {}  # symbol -> quote data
        self.option_data: Dict[str, Dict] = {}  # symbol -> quote data
        
        # Subscribed instruments
        self.subscribed_indices: List[str] = []
        self.subscribed_options: List[str] = []
        
        # Callbacks
        self._data_callbacks: List[Callable[[str, Dict], None]] = []
        self._connection_callbacks: List[Callable[[bool], None]] = []
        
        # Background task
        self._reconnect_task: Optional[asyncio.Task] = None
        
    def on_data_update(self, callback: Callable[[str, Dict], None]):
        """Register callback for data updates"""
        self._data_callbacks.append(callback)
        
    def on_connection_change(self, callback: Callable[[bool], None]):
        """Register callback for connection status changes"""
        self._connection_callbacks.append(callback)
    
    async def initialize(self, token: str, sid: str) -> bool:
        """
        Initialize the live data manager with Kotak credentials
        
        Args:
            token: Session token from Kotak login
            sid: Session ID from Kotak login
            
        Returns:
            True if connection successful
        """
        self.token = token
        self.sid = sid
        
        logger.info("Initializing Live Data Manager with HSM WebSocket")
        
        # Create HSM client
        self.hsm_client = create_hsm_client(token, sid)
        
        # Setup callbacks
        self.hsm_client.on_data(self._handle_data)
        self.hsm_client.on_connect(self._handle_connect)
        self.hsm_client.on_disconnect(self._handle_disconnect)
        self.hsm_client.on_error(self._handle_error)
        
        # Connect
        success = await self.hsm_client.connect()
        
        if success:
            self.is_connected = True
            logger.info("HSM WebSocket connected successfully")
            
            # Auto-subscribe to indices
            await self._subscribe_default_indices()
            
            # Notify callbacks
            for cb in self._connection_callbacks:
                try:
                    cb(True)
                except Exception as e:
                    logger.error(f"Connection callback error: {e}")
                    
            return True
        else:
            logger.error("Failed to connect to HSM WebSocket")
            return False
    
    async def _subscribe_default_indices(self):
        """Subscribe to default indices (NIFTY, BANKNIFTY)"""
        if not self.hsm_client:
            return
            
        default_indices = [
            "nse_cm|Nifty 50",
            "nse_cm|Nifty Bank"
        ]
        
        try:
            await self.hsm_client.subscribe_index(default_indices)
            self.subscribed_indices = default_indices
            logger.info(f"Subscribed to default indices: {default_indices}")
        except Exception as e:
            logger.error(f"Failed to subscribe to indices: {e}")
    
    async def subscribe_options(self, instruments: List[str]) -> bool:
        """
        Subscribe to option instruments for live data
        
        Args:
            instruments: List of instrument identifiers like ["nse_fo|53290", "nse_fo|53291"]
            
        Returns:
            True if subscription successful
        """
        if not self.hsm_client or not self.is_connected:
            logger.warning("Cannot subscribe - not connected to HSM")
            return False
            
        try:
            # Filter out already subscribed
            new_instruments = [i for i in instruments if i not in self.subscribed_options]
            
            if not new_instruments:
                logger.debug("All instruments already subscribed")
                return True
                
            # Subscribe in batches of 100 (HSM limit)
            batch_size = 100
            for i in range(0, len(new_instruments), batch_size):
                batch = new_instruments[i:i+batch_size]
                await self.hsm_client.subscribe_scrip(batch)
                self.subscribed_options.extend(batch)
                
            logger.info(f"Subscribed to {len(new_instruments)} option instruments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to options: {e}")
            return False
    
    async def unsubscribe_options(self, instruments: List[str]) -> bool:
        """Unsubscribe from option instruments"""
        if not self.hsm_client or not self.is_connected:
            return False
            
        try:
            await self.hsm_client.unsubscribe_scrip(instruments)
            for i in instruments:
                if i in self.subscribed_options:
                    self.subscribed_options.remove(i)
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    def get_index_ltp(self, symbol: str) -> Optional[float]:
        """Get latest LTP for an index"""
        # Try direct lookup
        if symbol in self.index_data:
            return self.index_data[symbol].get("ltp")
            
        # Try with Nifty 50 / Nifty Bank naming
        for key, data in self.index_data.items():
            if symbol.upper() in key.upper() or key.upper() in symbol.upper():
                return data.get("ltp")
                
        return None
    
    def get_option_ltp(self, instrument_token: str) -> Optional[float]:
        """Get latest LTP for an option by instrument token"""
        if instrument_token in self.option_data:
            return self.option_data[instrument_token].get("ltp")
        return None
    
    def get_option_quote(self, instrument_token: str) -> Optional[Dict]:
        """Get full quote data for an option"""
        return self.option_data.get(instrument_token)
    
    def get_all_index_data(self) -> Dict[str, Dict]:
        """Get all index data"""
        return self.index_data.copy()
    
    def get_all_option_data(self) -> Dict[str, Dict]:
        """Get all option data"""
        return self.option_data.copy()
    
    def _handle_data(self, symbol: str, data: Dict):
        """Handle incoming market data"""
        try:
            # Determine if index or scrip
            data_type = data.get("_type", "sf")
            
            if data_type == "if" or "Nifty" in symbol:
                self.index_data[symbol] = data
                logger.debug(f"Index update: {symbol} LTP={data.get('ltp')}")
            else:
                self.option_data[symbol] = data
                logger.debug(f"Option update: {symbol} LTP={data.get('ltp')}")
            
            # Notify callbacks
            for cb in self._data_callbacks:
                try:
                    cb(symbol, data)
                except Exception as e:
                    logger.error(f"Data callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Handle data error: {e}")
    
    def _handle_connect(self):
        """Handle connection established"""
        self.is_connected = True
        logger.info("HSM WebSocket connection established")
    
    def _handle_disconnect(self):
        """Handle disconnection"""
        self.is_connected = False
        logger.warning("HSM WebSocket disconnected")
        
        # Notify callbacks
        for cb in self._connection_callbacks:
            try:
                cb(False)
            except Exception as e:
                logger.error(f"Connection callback error: {e}")
        
        # Start reconnection task
        if self.token and self.sid:
            self._start_reconnect()
    
    def _handle_error(self, error: str):
        """Handle WebSocket error"""
        logger.error(f"HSM WebSocket error: {error}")
    
    def _start_reconnect(self):
        """Start reconnection task"""
        if self._reconnect_task and not self._reconnect_task.done():
            return
            
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self):
        """Reconnection loop with exponential backoff"""
        retry_count = 0
        max_retries = 5
        base_delay = 5
        
        while retry_count < max_retries and not self.is_connected:
            delay = base_delay * (2 ** retry_count)
            logger.info(f"Attempting HSM reconnection in {delay}s (attempt {retry_count + 1}/{max_retries})")
            
            await asyncio.sleep(delay)
            
            if await self.initialize(self.token, self.sid):
                logger.info("HSM reconnection successful")
                
                # Resubscribe to options
                if self.subscribed_options:
                    await self.subscribe_options(self.subscribed_options)
                    
                return
                
            retry_count += 1
        
        logger.error("HSM reconnection failed after max retries")
    
    async def disconnect(self):
        """Disconnect from HSM"""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            
        if self.hsm_client:
            await self.hsm_client.disconnect()
            
        self.is_connected = False
        self.index_data.clear()
        self.option_data.clear()
        self.subscribed_indices.clear()
        self.subscribed_options.clear()
        
        logger.info("Live Data Manager disconnected")
    
    def get_status(self) -> Dict:
        """Get current status of live data manager"""
        return {
            "connected": self.is_connected,
            "subscribed_indices": len(self.subscribed_indices),
            "subscribed_options": len(self.subscribed_options),
            "index_quotes": len(self.index_data),
            "option_quotes": len(self.option_data),
            "last_update": datetime.now().isoformat()
        }


# Singleton instance
_live_data_manager: Optional[LiveDataManager] = None


def get_live_data_manager() -> LiveDataManager:
    """Get the singleton LiveDataManager instance"""
    global _live_data_manager
    if _live_data_manager is None:
        _live_data_manager = LiveDataManager()
    return _live_data_manager


async def init_live_data(token: str, sid: str) -> bool:
    """Initialize live data with credentials"""
    manager = get_live_data_manager()
    return await manager.initialize(token, sid)
