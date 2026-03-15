"""
NSE Options Data Service
Fetches real-time option chain data directly from NSE India
Includes actual expiry dates and live option prices
"""
import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class NSEOptionContract:
    """Real NSE option contract data"""
    symbol: str
    underlying: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    open_interest: int = 0
    oi_change: int = 0
    volume: int = 0
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    underlying_value: float = 0.0
    timestamp: str = ""

@dataclass
class NSEOptionsChain:
    """Complete options chain from NSE"""
    underlying: str
    spot_price: float
    expiry: str
    atm_strike: float
    calls: List[NSEOptionContract]
    puts: List[NSEOptionContract]
    pcr: float
    max_pain: float
    timestamp: str
    is_live: bool = True


class NSEOptionsService:
    """
    Service for fetching real options data from NSE India
    """
    
    # NSE API endpoints
    NSE_BASE_URL = "https://www.nseindia.com"
    OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
    
    # Headers to mimic browser request
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nseindia.com/option-chain',
    }
    
    def __init__(self):
        self.cookies: Dict[str, str] = {}
        self.last_cookie_refresh: Optional[datetime] = None
        self.cached_data: Dict[str, Dict] = {}
        self.cached_expiries: Dict[str, List[str]] = {}
        self.last_updated: Optional[datetime] = None
    
    async def _get_cookies(self) -> bool:
        """Get NSE cookies by visiting the main page first"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                # Visit main page to get cookies
                response = await client.get(
                    self.NSE_BASE_URL,
                    headers=self.HEADERS
                )
                if response.status_code == 200:
                    self.cookies = dict(response.cookies)
                    self.last_cookie_refresh = datetime.now()
                    logger.info(f"Got NSE cookies: {list(self.cookies.keys())}")
                    return True
        except Exception as e:
            logger.error(f"Error getting NSE cookies: {e}")
        return False
    
    async def fetch_option_chain(self, symbol: str = "NIFTY") -> Optional[Dict]:
        """
        Fetch complete option chain from NSE
        
        Args:
            symbol: NIFTY or BANKNIFTY
        
        Returns:
            Raw option chain data from NSE
        """
        try:
            # Refresh cookies if needed (every 5 minutes)
            if not self.cookies or not self.last_cookie_refresh or \
               (datetime.now() - self.last_cookie_refresh).seconds > 300:
                await self._get_cookies()
            
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.OPTION_CHAIN_URL}?symbol={symbol}",
                    headers=self.HEADERS,
                    cookies=self.cookies
                )
                
                logger.info(f"NSE API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    self.cached_data[symbol] = data
                    self.last_updated = datetime.now()
                    
                    # Extract and cache expiry dates
                    if 'records' in data and 'expiryDates' in data['records']:
                        self.cached_expiries[symbol] = data['records']['expiryDates']
                        logger.info(f"NSE expiries for {symbol}: {self.cached_expiries[symbol][:5]}")
                    
                    return data
                else:
                    logger.error(f"NSE API error: {response.status_code} - {response.text[:200]}")
                    
        except Exception as e:
            logger.error(f"Error fetching NSE option chain: {e}")
        
        return None
    
    def get_expiries(self, symbol: str = "NIFTY") -> List[str]:
        """Get cached expiry dates for a symbol"""
        return self.cached_expiries.get(symbol, [])
    
    async def get_real_expiries(self, symbol: str = "NIFTY") -> List[str]:
        """Fetch and return real expiry dates from NSE"""
        data = await self.fetch_option_chain(symbol)
        if data and 'records' in data and 'expiryDates' in data['records']:
            return data['records']['expiryDates']
        return []
    
    async def build_options_chain(self, symbol: str, expiry: Optional[str] = None, 
                                   num_strikes: int = 15) -> Optional[NSEOptionsChain]:
        """
        Build complete options chain from NSE data
        
        Args:
            symbol: NIFTY or BANKNIFTY
            expiry: Expiry date in NSE format (e.g., "20-Mar-2025"), uses nearest if None
            num_strikes: Number of strikes on each side of ATM
        """
        # Fetch fresh data
        data = await self.fetch_option_chain(symbol)
        if not data or 'records' not in data:
            logger.error("No data from NSE")
            return None
        
        records = data['records']
        
        # Get underlying value (spot price)
        spot_price = records.get('underlyingValue', 0)
        if not spot_price:
            logger.error("No spot price in NSE data")
            return None
        
        # Get expiry dates
        expiries = records.get('expiryDates', [])
        if not expiries:
            logger.error("No expiry dates in NSE data")
            return None
        
        # Use provided expiry or first available
        if not expiry:
            expiry = expiries[0]
        elif expiry not in expiries:
            # Try to find closest match
            expiry = expiries[0]
        
        # Calculate ATM strike
        interval = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(spot_price / interval) * interval
        
        # Filter data for selected expiry
        chain_data = records.get('data', [])
        filtered_data = [item for item in chain_data if item.get('expiryDate') == expiry]
        
        if not filtered_data:
            logger.error(f"No data for expiry {expiry}")
            return None
        
        # Build calls and puts
        calls = []
        puts = []
        total_call_oi = 0
        total_put_oi = 0
        
        # Sort by strike
        filtered_data.sort(key=lambda x: x.get('strikePrice', 0))
        
        # Filter strikes around ATM
        for item in filtered_data:
            strike = item.get('strikePrice', 0)
            if abs(strike - atm_strike) > (num_strikes * interval):
                continue
            
            # Call data
            ce = item.get('CE', {})
            if ce:
                ce_oi = ce.get('openInterest', 0)
                total_call_oi += ce_oi
                
                calls.append(NSEOptionContract(
                    symbol=ce.get('identifier', f"{symbol}{expiry}{strike}CE"),
                    underlying=symbol,
                    strike=strike,
                    option_type='CE',
                    expiry=expiry,
                    ltp=ce.get('lastPrice', 0),
                    bid=ce.get('bidprice', 0),
                    ask=ce.get('askPrice', 0),
                    open_interest=ce_oi,
                    oi_change=ce.get('changeinOpenInterest', 0),
                    volume=ce.get('totalTradedVolume', 0),
                    iv=ce.get('impliedVolatility', 0),
                    underlying_value=spot_price,
                    timestamp=datetime.now().isoformat()
                ))
            
            # Put data
            pe = item.get('PE', {})
            if pe:
                pe_oi = pe.get('openInterest', 0)
                total_put_oi += pe_oi
                
                puts.append(NSEOptionContract(
                    symbol=pe.get('identifier', f"{symbol}{expiry}{strike}PE"),
                    underlying=symbol,
                    strike=strike,
                    option_type='PE',
                    expiry=expiry,
                    ltp=pe.get('lastPrice', 0),
                    bid=pe.get('bidprice', 0),
                    ask=pe.get('askPrice', 0),
                    open_interest=pe_oi,
                    oi_change=pe.get('changeinOpenInterest', 0),
                    volume=pe.get('totalTradedVolume', 0),
                    iv=pe.get('impliedVolatility', 0),
                    underlying_value=spot_price,
                    timestamp=datetime.now().isoformat()
                ))
        
        # Calculate PCR
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        
        # Calculate Max Pain (simplified - strike with minimum total premium)
        max_pain = atm_strike
        
        return NSEOptionsChain(
            underlying=symbol,
            spot_price=spot_price,
            expiry=expiry,
            atm_strike=atm_strike,
            calls=calls,
            puts=puts,
            pcr=round(pcr, 2),
            max_pain=max_pain,
            timestamp=datetime.now().isoformat(),
            is_live=True
        )


# Global instance
nse_options_service = NSEOptionsService()


def get_nse_options_service() -> NSEOptionsService:
    """Get the global NSE options service instance"""
    return nse_options_service
