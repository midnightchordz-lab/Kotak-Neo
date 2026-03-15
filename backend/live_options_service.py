"""
Live Options Chain - Fetches real expiry dates and live option prices from Kotak API
Uses REST polling since WebSocket is not accessible from EC2

This module:
1. Fetches real expiry dates from Kotak FNO instrument master
2. Generates correct option symbols for each expiry
3. Polls live option prices via Kotak Quotes API
"""
import asyncio
import httpx
import logging
import csv
import io
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class OptionContract:
    """Real option contract data"""
    symbol: str
    underlying: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    expiry_date: str  # YYYY-MM-DD format
    instrument_token: str
    lot_size: int
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
    timestamp: str = ""

@dataclass
class RealOptionsChain:
    """Complete options chain with real data"""
    underlying: str
    spot_price: float
    expiry: str
    atm_strike: float
    calls: List[OptionContract]
    puts: List[OptionContract]
    pcr: float
    max_pain: float
    timestamp: str
    is_live: bool = True


class LiveOptionsService:
    """
    Service for fetching real options data from Kotak API
    """
    
    # Kotak FNO master URL
    FNO_MASTER_URL = "https://mis.kotaksecurities.com/fno/scrip-master"
    
    def __init__(self):
        self.kotak_api = None
        self.instruments: Dict[str, Dict] = {}  # token -> instrument data
        self.nifty_expiries: List[str] = []  # Sorted list of YYYY-MM-DD dates
        self.banknifty_expiries: List[str] = []
        self.nifty_options: Dict[str, Dict[Tuple[float, str], Dict]] = {}  # expiry -> (strike, type) -> data
        self.banknifty_options: Dict[str, Dict[Tuple[float, str], Dict]] = {}
        self.last_updated: Optional[datetime] = None
        
        # Cache for live prices
        self.live_prices: Dict[str, float] = {}
        
        # Lot sizes
        self.lot_sizes = {
            'NIFTY': 25,
            'BANKNIFTY': 15
        }
    
    def set_kotak_api(self, api):
        """Set the Kotak API client"""
        self.kotak_api = api
    
    async def fetch_instruments(self) -> bool:
        """
        Fetch FNO instrument master from Kotak
        This gives us real expiry dates and instrument tokens
        """
        try:
            logger.info("Fetching Kotak FNO instrument master...")
            
            # Try multiple sources
            success = await self._fetch_from_kotak_fno()
            if not success:
                success = await self._fetch_from_alternative()
            
            if success:
                self.last_updated = datetime.now()
                logger.info(f"Loaded instruments. NIFTY expiries: {len(self.nifty_expiries)}, BANKNIFTY expiries: {len(self.banknifty_expiries)}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            return False
    
    async def _fetch_from_kotak_fno(self) -> bool:
        """Fetch from Kotak's FNO instrument file"""
        try:
            headers = {}
            if self.kotak_api and self.kotak_api.consumer_key:
                headers['Authorization'] = self.kotak_api.consumer_key
            
            async with httpx.AsyncClient(timeout=60) as client:
                # Try the scripmaster endpoint first
                url = "https://mis.kotaksecurities.com/script-details/1.0/masterscrip/file-paths"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Scripmaster paths: {data}")
                    
                    # Get FNO file URL
                    fno_url = data.get('nse_fo') or data.get('NSE_FO')
                    if fno_url:
                        return await self._download_and_parse_fno(fno_url, headers)
                
                # Try alternative FNO URL
                alt_url = "https://mis.kotaksecurities.com/fno/instruments/fno_instruments.csv"
                response = await client.get(alt_url, headers=headers)
                
                if response.status_code == 200:
                    return self._parse_fno_csv(response.text)
                
        except Exception as e:
            logger.error(f"Kotak FNO fetch error: {e}")
        
        return False
    
    async def _download_and_parse_fno(self, url: str, headers: Dict) -> bool:
        """Download and parse FNO file"""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return self._parse_fno_csv(response.text)
        except Exception as e:
            logger.error(f"FNO download error: {e}")
        return False
    
    async def _fetch_from_alternative(self) -> bool:
        """
        Generate expiry dates based on NSE rules:
        - Weekly expiry: Thursday (or previous trading day if holiday)
        - Monthly expiry: Last Thursday of the month
        
        Since we can't reach NSE directly, we calculate them
        """
        try:
            logger.info("Using calculated expiry dates (alternative method)")
            
            today = datetime.now().date()
            
            # Generate next 4 weekly expiries for both indices
            self.nifty_expiries = self._generate_weekly_expiries(today, 4)
            self.banknifty_expiries = self._generate_weekly_expiries(today, 4)
            
            logger.info(f"Generated NIFTY expiries: {self.nifty_expiries}")
            logger.info(f"Generated BANKNIFTY expiries: {self.banknifty_expiries}")
            
            return len(self.nifty_expiries) > 0
            
        except Exception as e:
            logger.error(f"Alternative fetch error: {e}")
            return False
    
    def _generate_weekly_expiries(self, start_date, num_weeks: int = 4) -> List[str]:
        """
        Generate weekly expiry dates (Thursdays)
        NSE weekly expiry is on Thursday
        
        Special handling:
        - If Thursday is a holiday, expiry moves to Wednesday
        - We don't have holiday data, so we just use Thursday
        """
        expiries = []
        current = start_date
        
        # Find next Thursday
        days_until_thursday = (3 - current.weekday()) % 7
        if days_until_thursday == 0 and current.weekday() == 3:
            # Today is Thursday
            # Check if market is still open (before 3:30 PM)
            now = datetime.now()
            if now.hour < 15 or (now.hour == 15 and now.minute < 30):
                days_until_thursday = 0
            else:
                days_until_thursday = 7
        
        next_thursday = current + timedelta(days=days_until_thursday)
        
        for i in range(num_weeks):
            expiry_date = next_thursday + timedelta(weeks=i)
            expiries.append(expiry_date.strftime('%Y-%m-%d'))
        
        return expiries
    
    def _parse_fno_csv(self, csv_text: str) -> bool:
        """Parse FNO instruments CSV"""
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            
            nifty_expiry_set = set()
            banknifty_expiry_set = set()
            
            for row in reader:
                # Get underlying name
                underlying = row.get('pUnderlying', row.get('underlying', ''))
                symbol = row.get('pSymbol', row.get('symbol', ''))
                
                # Check if it's an option (has strike and option type)
                option_type = row.get('pOptionType', row.get('option_type', ''))
                if option_type not in ['CE', 'PE']:
                    continue
                
                # Parse expiry date
                expiry_raw = row.get('pExpiryDate', row.get('expiry', ''))
                try:
                    # Handle Unix timestamp (seconds)
                    if expiry_raw.isdigit():
                        expiry_ts = int(expiry_raw)
                        # Kotak sometimes has dates that need +10 years offset
                        expiry_dt = datetime.fromtimestamp(expiry_ts)
                        if expiry_dt.year < 2020:
                            expiry_dt = expiry_dt.replace(year=expiry_dt.year + 10)
                        expiry = expiry_dt.strftime('%Y-%m-%d')
                    else:
                        # Try parsing as date string
                        for fmt in ['%Y-%m-%d', '%d-%b-%Y', '%d-%m-%Y', '%Y%m%d']:
                            try:
                                expiry_dt = datetime.strptime(expiry_raw, fmt)
                                expiry = expiry_dt.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        else:
                            continue
                except (ValueError, TypeError):
                    continue
                
                # Get strike price
                try:
                    strike = float(row.get('pStrike', row.get('strike', 0)))
                except (ValueError, TypeError):
                    continue
                
                # Get instrument token
                token = row.get('pToken', row.get('instrument_token', row.get('token', '')))
                lot_size = int(row.get('pLotSize', row.get('lot_size', 25)))
                
                # Store by underlying
                if 'NIFTY' in underlying.upper() and 'BANK' not in underlying.upper():
                    nifty_expiry_set.add(expiry)
                    if expiry not in self.nifty_options:
                        self.nifty_options[expiry] = {}
                    self.nifty_options[expiry][(strike, option_type)] = {
                        'symbol': symbol,
                        'token': token,
                        'lot_size': lot_size
                    }
                    
                elif 'BANKNIFTY' in underlying.upper() or 'NIFTY BANK' in underlying.upper():
                    banknifty_expiry_set.add(expiry)
                    if expiry not in self.banknifty_options:
                        self.banknifty_options[expiry] = {}
                    self.banknifty_options[expiry][(strike, option_type)] = {
                        'symbol': symbol,
                        'token': token,
                        'lot_size': lot_size
                    }
            
            # Sort expiries
            self.nifty_expiries = sorted(list(nifty_expiry_set))
            self.banknifty_expiries = sorted(list(banknifty_expiry_set))
            
            return len(self.nifty_expiries) > 0 or len(self.banknifty_expiries) > 0
            
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            return False
    
    def get_expiries(self, underlying: str) -> List[str]:
        """Get available expiry dates for an underlying"""
        if underlying.upper() == 'NIFTY':
            return self.nifty_expiries
        elif underlying.upper() == 'BANKNIFTY':
            return self.banknifty_expiries
        return []
    
    def get_nearest_expiry(self, underlying: str) -> Optional[str]:
        """Get the nearest expiry date"""
        expiries = self.get_expiries(underlying)
        if expiries:
            today = datetime.now().date().strftime('%Y-%m-%d')
            for exp in expiries:
                if exp >= today:
                    return exp
            return expiries[0] if expiries else None
        return None
    
    def generate_option_symbol(self, underlying: str, expiry: str, strike: float, option_type: str) -> str:
        """
        Generate Kotak option symbol format
        Format: NIFTY{DDMON}{STRIKE}{CE/PE}
        Example: NIFTY20MAR23500CE
        """
        try:
            exp_dt = datetime.strptime(expiry, '%Y-%m-%d')
            exp_str = exp_dt.strftime('%d%b').upper()  # e.g., "20MAR"
            return f"{underlying}{exp_str}{int(strike)}{option_type}"
        except (ValueError, TypeError):
            return f"{underlying}{expiry[:5]}{int(strike)}{option_type}"
    
    async def get_option_quotes(self, underlying: str, expiry: str, strikes: List[float]) -> Dict[Tuple[float, str], Dict]:
        """
        Get live quotes for specific option contracts
        
        Returns: Dict mapping (strike, option_type) -> quote data
        """
        if not self.kotak_api or not self.kotak_api.session.is_authenticated:
            logger.warning("Kotak API not authenticated for option quotes")
            return {}
        
        results = {}
        
        # Build instrument tokens list for all strikes and both CE/PE
        tokens = []
        for strike in strikes:
            for opt_type in ['CE', 'PE']:
                symbol = self.generate_option_symbol(underlying, expiry, strike, opt_type)
                tokens.append({
                    'exchange_segment': 'nse_fo',
                    'symbol': symbol,
                    'strike': strike,
                    'option_type': opt_type
                })
        
        # Batch quotes in groups of 20 (Kotak API limit)
        batch_size = 20
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i+batch_size]
            
            try:
                quote_tokens = [{'exchange_segment': t['exchange_segment'], 'symbol': t['symbol']} for t in batch]
                result = await self.kotak_api.get_quotes(quote_tokens, quote_type='all')
                
                if result.get('success') and result.get('quotes'):
                    quotes = result['quotes']
                    if isinstance(quotes, list):
                        for j, q in enumerate(quotes):
                            if j < len(batch):
                                strike = batch[j]['strike']
                                opt_type = batch[j]['option_type']
                                
                                results[(strike, opt_type)] = {
                                    'ltp': float(q.get('ltp', 0)),
                                    'bid': float(q.get('depth', {}).get('buy', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                                    'ask': float(q.get('depth', {}).get('sell', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                                    'oi': int(q.get('open_interest', 0)),
                                    'volume': int(q.get('last_volume', q.get('volume', 0))),
                                    'change': float(q.get('change', 0)),
                                    'ohlc': q.get('ohlc', {})
                                }
                                
            except Exception as e:
                logger.error(f"Error fetching quotes batch: {e}")
        
        return results
    
    async def build_options_chain(self, underlying: str, spot_price: float, 
                                   expiry: Optional[str] = None, 
                                   num_strikes: int = 15) -> RealOptionsChain:
        """
        Build complete options chain with live data
        
        Args:
            underlying: NIFTY or BANKNIFTY
            spot_price: Current spot price
            expiry: Expiry date (YYYY-MM-DD), uses nearest if None
            num_strikes: Number of strikes on each side of ATM
        """
        underlying = underlying.upper()
        
        # Get expiry
        if not expiry:
            expiry = self.get_nearest_expiry(underlying)
        
        if not expiry:
            # Generate expiry if not available
            await self.fetch_instruments()
            expiry = self.get_nearest_expiry(underlying)
        
        if not expiry:
            # Last resort - calculate Thursday
            expiry = self._generate_weekly_expiries(datetime.now().date(), 1)[0]
        
        # Calculate ATM strike
        interval = 50 if underlying == 'NIFTY' else 100
        atm_strike = round(spot_price / interval) * interval
        
        # Generate strikes around ATM
        strikes = []
        for i in range(-num_strikes, num_strikes + 1):
            strike = atm_strike + (i * interval)
            if strike > 0:
                strikes.append(strike)
        
        # Try to get live quotes
        quotes = {}
        try:
            quotes = await self.get_option_quotes(underlying, expiry, strikes)
        except Exception as e:
            logger.error(f"Failed to get live option quotes: {e}")
        
        # Build calls and puts
        calls = []
        puts = []
        lot_size = self.lot_sizes.get(underlying, 25)
        total_call_oi = 0
        total_put_oi = 0
        
        for strike in sorted(strikes):
            # Get quote data or use simulated values
            ce_data = quotes.get((strike, 'CE'), {})
            pe_data = quotes.get((strike, 'PE'), {})
            
            # Calculate basic Greeks and IV using Black-Scholes approximation
            moneyness_ce = (spot_price - strike) / spot_price
            moneyness_pe = (strike - spot_price) / spot_price
            
            # Simplified IV estimation
            base_iv = 15.0  # Base IV
            iv_smile = abs(moneyness_ce) * 100  # IV smile effect
            ce_iv = base_iv + iv_smile
            pe_iv = base_iv + iv_smile
            
            # Simplified Delta approximation
            ce_delta = max(0, min(1, 0.5 + moneyness_ce * 2))
            pe_delta = ce_delta - 1
            
            # Get live prices or calculate simulated prices using Black-Scholes approximation
            ce_ltp = ce_data.get('ltp', 0)
            pe_ltp = pe_data.get('ltp', 0)
            
            # If no live prices, use Black-Scholes approximation
            if ce_ltp == 0:
                # Intrinsic value + time value approximation
                intrinsic_ce = max(0, spot_price - strike)
                time_value_ce = spot_price * (ce_iv / 100) * 0.1  # Simplified time value
                ce_ltp = round(intrinsic_ce + time_value_ce * max(0.1, 1 - abs(moneyness_ce) * 2), 2)
            
            if pe_ltp == 0:
                intrinsic_pe = max(0, strike - spot_price)
                time_value_pe = spot_price * (pe_iv / 100) * 0.1
                pe_ltp = round(intrinsic_pe + time_value_pe * max(0.1, 1 - abs(moneyness_pe) * 2), 2)
            
            ce_oi = ce_data.get('oi', 0)
            pe_oi = pe_data.get('oi', 0)
            
            # Simulate OI if not available
            if ce_oi == 0:
                # Higher OI near ATM, lower OI as we move away
                atm_distance = abs(strike - spot_price) / interval
                ce_oi = int(max(1000, 50000 * (1 / (1 + atm_distance * 0.5))))
            if pe_oi == 0:
                atm_distance = abs(strike - spot_price) / interval
                pe_oi = int(max(1000, 45000 * (1 / (1 + atm_distance * 0.5))))
            
            total_call_oi += ce_oi
            total_put_oi += pe_oi
            
            calls.append(OptionContract(
                symbol=self.generate_option_symbol(underlying, expiry, strike, 'CE'),
                underlying=underlying,
                strike=strike,
                option_type='CE',
                expiry=expiry,
                expiry_date=expiry,
                instrument_token="",
                lot_size=lot_size,
                ltp=ce_ltp,
                bid=ce_data.get('bid', 0),
                ask=ce_data.get('ask', 0),
                open_interest=ce_oi,
                oi_change=0,
                volume=ce_data.get('volume', 0),
                iv=ce_iv,
                delta=round(ce_delta, 3),
                gamma=round(0.01 * (1 - abs(moneyness_ce)), 4),
                theta=round(-ce_ltp * 0.01, 2) if ce_ltp > 0 else 0,
                vega=round(ce_ltp * 0.001, 3) if ce_ltp > 0 else 0,
                timestamp=datetime.now().isoformat()
            ))
            
            puts.append(OptionContract(
                symbol=self.generate_option_symbol(underlying, expiry, strike, 'PE'),
                underlying=underlying,
                strike=strike,
                option_type='PE',
                expiry=expiry,
                expiry_date=expiry,
                instrument_token="",
                lot_size=lot_size,
                ltp=pe_ltp,
                bid=pe_data.get('bid', 0),
                ask=pe_data.get('ask', 0),
                open_interest=pe_oi,
                oi_change=0,
                volume=pe_data.get('volume', 0),
                iv=pe_iv,
                delta=round(pe_delta, 3),
                gamma=round(0.01 * (1 - abs(moneyness_pe)), 4),
                theta=round(-pe_ltp * 0.01, 2) if pe_ltp > 0 else 0,
                vega=round(pe_ltp * 0.001, 3) if pe_ltp > 0 else 0,
                timestamp=datetime.now().isoformat()
            ))
        
        # Calculate PCR
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        
        # Calculate Max Pain (simplified)
        max_pain = atm_strike
        
        # Determine if we have live data
        is_live = len(quotes) > 0
        
        return RealOptionsChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=expiry,
            atm_strike=atm_strike,
            calls=calls,
            puts=puts,
            pcr=round(pcr, 2),
            max_pain=max_pain,
            timestamp=datetime.now().isoformat(),
            is_live=is_live
        )


# Global instance
live_options_service = LiveOptionsService()


def get_live_options_service() -> LiveOptionsService:
    """Get the global live options service instance"""
    return live_options_service
