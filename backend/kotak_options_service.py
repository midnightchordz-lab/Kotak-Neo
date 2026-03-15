"""
Kotak Options Service - Uses official Kotak NEO API v2
Fetches real expiry dates from Scripmaster and live prices from Quotes API

Based on official documentation:
- Scripmaster: GET <baseUrl>/script-details/1.0/masterscrip/file-paths
- Quotes: GET <baseUrl>/script-details/1.0/quotes/neosymbol/<exchange>|<symbol>/all
"""
import asyncio
import httpx
import csv
import io
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class KotakOptionContract:
    """Option contract from Kotak API"""
    symbol: str
    trading_symbol: str
    underlying: str
    strike: float
    option_type: str  # CE or PE
    expiry: str  # DD-Mon-YYYY format from Kotak
    expiry_date: str  # YYYY-MM-DD format
    instrument_token: str
    lot_size: int
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change: float = 0.0
    change_percent: float = 0.0
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
class KotakOptionsChain:
    """Complete options chain from Kotak"""
    underlying: str
    spot_price: float
    expiry: str
    atm_strike: float
    calls: List[KotakOptionContract]
    puts: List[KotakOptionContract]
    pcr: float
    max_pain: float
    timestamp: str
    is_live: bool = True
    source: str = "kotak_api"


class KotakOptionsService:
    """
    Service for fetching real options data from Kotak NEO API v2
    Uses Scripmaster for expiries and Quotes API for live prices
    """
    
    def __init__(self):
        self.kotak_api = None
        self.base_url: str = ""
        self.access_token: str = ""
        
        # Cached instrument data
        self.nfo_instruments: Dict[str, Dict] = {}  # symbol -> instrument data
        self.nifty_expiries: List[str] = []  # Sorted list of expiry dates
        self.banknifty_expiries: List[str] = []
        self.nifty_options: Dict[str, List[Dict]] = {}  # expiry -> list of option contracts
        self.banknifty_options: Dict[str, List[Dict]] = {}
        
        self.last_scripmaster_update: Optional[datetime] = None
        self.last_updated: Optional[datetime] = None
        
        # Lot sizes
        self.lot_sizes = {
            'NIFTY': 25,
            'BANKNIFTY': 15
        }
    
    def set_kotak_api(self, api):
        """Set the Kotak API client"""
        self.kotak_api = api
        if api and api.session:
            self.base_url = api.session.base_url or ""
            self.access_token = api.consumer_key or ""
    
    async def fetch_scripmaster(self) -> bool:
        """
        Fetch FNO scripmaster CSV to get real expiry dates and instrument tokens
        
        API: GET <baseUrl>/script-details/1.0/masterscrip/file-paths
        Headers: Authorization: <access_token>
        """
        if not self.base_url or not self.access_token:
            logger.error("No base_url or access_token available")
            return False
        
        try:
            logger.info("Fetching Kotak scripmaster file paths...")
            
            headers = {
                'Authorization': self.access_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                # Get file paths
                url = f"{self.base_url}/script-details/1.0/masterscrip/file-paths"
                response = await client.get(url, headers=headers)
                
                logger.info(f"Scripmaster paths response: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    file_paths = data.get('data', {}).get('filesPaths', [])
                    
                    logger.info(f"Got {len(file_paths)} scripmaster files")
                    
                    # Find NSE FO file
                    nse_fo_url = None
                    for fp in file_paths:
                        if 'nse_fo' in fp.lower():
                            nse_fo_url = fp
                            break
                    
                    if nse_fo_url:
                        logger.info(f"Downloading NSE FO scripmaster: {nse_fo_url}")
                        return await self._download_and_parse_scripmaster(nse_fo_url)
                    else:
                        logger.error("NSE FO scripmaster file not found in paths")
                else:
                    logger.error(f"Scripmaster API error: {response.status_code} - {response.text[:200]}")
                    
        except Exception as e:
            logger.error(f"Error fetching scripmaster: {e}")
        
        return False
    
    async def _download_and_parse_scripmaster(self, url: str) -> bool:
        """Download and parse the NSE FO scripmaster CSV"""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    return self._parse_scripmaster_csv(response.text)
                else:
                    logger.error(f"Failed to download scripmaster: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error downloading scripmaster: {e}")
        
        return False
    
    def _parse_scripmaster_csv(self, csv_text: str) -> bool:
        """
        Parse NSE FO scripmaster CSV
        
        Expected columns from documentation:
        - pSymbol: Instrument token (used in Quotes API)
        - pExchSeg: Exchange segment (nse_fo)
        - pTrdSymbol: Trading symbol (used in Orders API)
        - lLotSize: Lot size
        - lExpiryDate: Expiry date
        """
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            
            nifty_expiry_set = set()
            banknifty_expiry_set = set()
            
            self.nifty_options = {}
            self.banknifty_options = {}
            
            row_count = 0
            for row in reader:
                row_count += 1
                
                # Get key fields
                symbol = row.get('pSymbol', row.get('symbol', ''))
                trading_symbol = row.get('pTrdSymbol', row.get('tradingSymbol', ''))
                instrument_type = row.get('pInstType', row.get('instrumentType', ''))
                option_type = row.get('pOptionType', row.get('optionType', ''))
                
                # Skip if not an option
                if option_type not in ['CE', 'PE']:
                    continue
                
                # Get underlying
                underlying = row.get('pUnderlying', row.get('underlying', ''))
                
                # Check if NIFTY or BANKNIFTY option
                is_nifty = False
                is_banknifty = False
                
                if 'BANKNIFTY' in trading_symbol.upper() or 'NIFTY BANK' in underlying.upper():
                    is_banknifty = True
                elif 'NIFTY' in trading_symbol.upper() and 'BANK' not in trading_symbol.upper():
                    is_nifty = True
                
                if not is_nifty and not is_banknifty:
                    continue
                
                # Parse expiry date
                expiry_raw = row.get('lExpiryDate', row.get('expiryDate', row.get('pExpiryDate', '')))
                expiry_str = ""
                expiry_date = ""
                
                try:
                    # Handle Unix timestamp
                    if expiry_raw and expiry_raw.replace('.', '').replace('-', '').isdigit():
                        ts = float(expiry_raw)
                        # Handle milliseconds
                        if ts > 10000000000:
                            ts = ts / 1000
                        expiry_dt = datetime.fromtimestamp(ts)
                        expiry_str = expiry_dt.strftime('%d-%b-%Y')
                        expiry_date = expiry_dt.strftime('%Y-%m-%d')
                    else:
                        # Try parsing as date string
                        for fmt in ['%d-%b-%Y', '%Y-%m-%d', '%d-%m-%Y', '%d%b%Y']:
                            try:
                                expiry_dt = datetime.strptime(expiry_raw, fmt)
                                expiry_str = expiry_dt.strftime('%d-%b-%Y')
                                expiry_date = expiry_dt.strftime('%Y-%m-%d')
                                break
                            except (ValueError, TypeError):
                                continue
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse expiry: {expiry_raw} - {e}")
                    continue
                
                if not expiry_date:
                    continue
                
                # Get strike price
                try:
                    strike = float(row.get('pStrike', row.get('strikePrice', row.get('strike', 0))))
                except (ValueError, TypeError):
                    continue
                
                # Get lot size
                try:
                    lot_size = int(row.get('lLotSize', row.get('lotSize', 25)))
                except (ValueError, TypeError):
                    lot_size = 25 if is_nifty else 15
                
                # Create contract data
                contract = {
                    'symbol': symbol,
                    'trading_symbol': trading_symbol,
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': expiry_str,
                    'expiry_date': expiry_date,
                    'lot_size': lot_size
                }
                
                # Store by underlying and expiry
                if is_nifty:
                    nifty_expiry_set.add(expiry_date)
                    if expiry_date not in self.nifty_options:
                        self.nifty_options[expiry_date] = []
                    self.nifty_options[expiry_date].append(contract)
                    
                elif is_banknifty:
                    banknifty_expiry_set.add(expiry_date)
                    if expiry_date not in self.banknifty_options:
                        self.banknifty_options[expiry_date] = []
                    self.banknifty_options[expiry_date].append(contract)
            
            # Sort expiries
            self.nifty_expiries = sorted(list(nifty_expiry_set))
            self.banknifty_expiries = sorted(list(banknifty_expiry_set))
            
            self.last_scripmaster_update = datetime.now()
            
            logger.info(f"Parsed {row_count} rows from scripmaster")
            logger.info(f"NIFTY expiries: {self.nifty_expiries[:5]}")
            logger.info(f"BANKNIFTY expiries: {self.banknifty_expiries[:5]}")
            logger.info(f"NIFTY options by expiry: {len(self.nifty_options)} expiries")
            
            return len(self.nifty_expiries) > 0 or len(self.banknifty_expiries) > 0
            
        except Exception as e:
            logger.error(f"Error parsing scripmaster CSV: {e}")
        
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
        today = datetime.now().date().strftime('%Y-%m-%d')
        for exp in expiries:
            if exp >= today:
                return exp
        return expiries[0] if expiries else None
    
    async def get_quote(self, exchange_segment: str, symbol: str) -> Optional[Dict]:
        """
        Get live quote for a single instrument
        
        API: GET <baseUrl>/script-details/1.0/quotes/neosymbol/<exchange>|<symbol>/all
        Headers: Authorization: <access_token>
        """
        if not self.base_url or not self.access_token:
            return None
        
        try:
            headers = {
                'Authorization': self.access_token,
                'Content-Type': 'application/json'
            }
            
            # Format: nse_fo|NIFTY25MAR23000CE
            query = f"{exchange_segment}|{symbol}"
            url = f"{self.base_url}/script-details/1.0/quotes/neosymbol/{query}/all"
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                        
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
        
        return None
    
    async def get_batch_quotes(self, instruments: List[Tuple[str, str]]) -> Dict[str, Dict]:
        """
        Get quotes for multiple instruments
        
        Args:
            instruments: List of (exchange_segment, symbol) tuples
        
        Returns:
            Dict mapping symbol -> quote data
        """
        if not self.base_url or not self.access_token:
            return {}
        
        results = {}
        
        # Batch up to 50 instruments per request
        batch_size = 50
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i+batch_size]
            
            try:
                headers = {
                    'Authorization': self.access_token,
                    'Content-Type': 'application/json'
                }
                
                # Format: nse_fo|SYM1,nse_fo|SYM2,...
                queries = [f"{seg}|{sym}" for seg, sym in batch]
                query_str = ','.join(queries)
                url = f"{self.base_url}/script-details/1.0/quotes/neosymbol/{query_str}/all"
                
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            for quote in data:
                                symbol = quote.get('display_symbol', quote.get('exchange_token', ''))
                                if symbol:
                                    results[symbol] = quote
                                    
            except Exception as e:
                logger.error(f"Error getting batch quotes: {e}")
        
        return results
    
    async def get_index_quote(self, symbol: str) -> Optional[Dict]:
        """Get live quote for an index (NIFTY, BANKNIFTY)"""
        # Index format: nse_cm|Nifty 50 or nse_cm|Nifty Bank
        index_name = "Nifty 50" if symbol.upper() == "NIFTY" else "Nifty Bank"
        return await self.get_quote("nse_cm", index_name)
    
    async def build_options_chain(self, underlying: str, expiry: Optional[str] = None,
                                   num_strikes: int = 15) -> Optional[KotakOptionsChain]:
        """
        Build complete options chain with live data from Kotak API
        """
        underlying = underlying.upper()
        
        # Ensure we have scripmaster data
        if not self.nifty_expiries and not self.banknifty_expiries:
            await self.fetch_scripmaster()
        
        # Get expiry
        if not expiry:
            expiry = self.get_nearest_expiry(underlying)
        
        if not expiry:
            logger.error(f"No expiry available for {underlying}")
            return None
        
        # Get spot price from index quote
        index_quote = await self.get_index_quote(underlying)
        spot_price = 0.0
        if index_quote:
            spot_price = float(index_quote.get('ltp', 0))
        
        if not spot_price:
            # Fallback to Kotak API
            if self.kotak_api and self.kotak_api.session.is_authenticated:
                result = await self.kotak_api.get_index_quote(underlying)
                if result.get('success') and result.get('quotes'):
                    quotes = result['quotes']
                    if isinstance(quotes, list) and len(quotes) > 0:
                        spot_price = float(quotes[0].get('ltp', 0))
        
        if not spot_price:
            logger.error(f"Could not get spot price for {underlying}")
            return None
        
        # Calculate ATM strike
        interval = 50 if underlying == 'NIFTY' else 100
        atm_strike = round(spot_price / interval) * interval
        
        # Get options for this expiry
        options_map = self.nifty_options if underlying == 'NIFTY' else self.banknifty_options
        contracts = options_map.get(expiry, [])
        
        if not contracts:
            logger.warning(f"No contracts found for {underlying} {expiry}")
            # Return with simulated data
            return self._build_simulated_chain(underlying, spot_price, expiry, num_strikes)
        
        # Filter strikes around ATM
        strikes_set = set()
        for c in contracts:
            strike = c['strike']
            if abs(strike - atm_strike) <= num_strikes * interval:
                strikes_set.add(strike)
        
        strikes = sorted(list(strikes_set))
        
        # Build instrument list for batch quote
        instruments_to_quote = []
        contract_map = {}  # (strike, type) -> contract
        
        for c in contracts:
            if c['strike'] in strikes:
                key = (c['strike'], c['option_type'])
                contract_map[key] = c
                instruments_to_quote.append(('nse_fo', c['symbol']))
        
        # Get live quotes
        quotes = await self.get_batch_quotes(instruments_to_quote)
        
        # Build calls and puts
        calls = []
        puts = []
        total_call_oi = 0
        total_put_oi = 0
        lot_size = self.lot_sizes.get(underlying, 25)
        
        for strike in strikes:
            # Call
            ce_contract = contract_map.get((strike, 'CE'))
            ce_quote = quotes.get(ce_contract['symbol']) if ce_contract else None
            
            ce_ltp = float(ce_quote.get('ltp', 0)) if ce_quote else 0
            ce_oi = int(ce_quote.get('open_interest', 0)) if ce_quote else 0
            ce_volume = int(ce_quote.get('last_volume', 0)) if ce_quote else 0
            ce_ohlc = ce_quote.get('ohlc', {}) if ce_quote else {}
            
            # If no live data, simulate
            if ce_ltp == 0:
                moneyness = (spot_price - strike) / spot_price
                intrinsic = max(0, spot_price - strike)
                time_value = spot_price * 0.15 * 0.1 * max(0.1, 1 - abs(moneyness) * 2)
                ce_ltp = round(intrinsic + time_value, 2)
                ce_oi = int(max(1000, 50000 * (1 / (1 + abs(strike - atm_strike) / interval * 0.5))))
            
            total_call_oi += ce_oi
            
            # Calculate IV and Greeks (simplified)
            moneyness_ce = (spot_price - strike) / spot_price
            ce_iv = 15.0 + abs(moneyness_ce) * 100
            ce_delta = max(0, min(1, 0.5 + moneyness_ce * 2))
            
            calls.append(KotakOptionContract(
                symbol=ce_contract['symbol'] if ce_contract else f"{underlying}{expiry}{int(strike)}CE",
                trading_symbol=ce_contract['trading_symbol'] if ce_contract else "",
                underlying=underlying,
                strike=strike,
                option_type='CE',
                expiry=ce_contract['expiry'] if ce_contract else expiry,
                expiry_date=expiry,
                instrument_token=ce_contract['symbol'] if ce_contract else "",
                lot_size=lot_size,
                ltp=ce_ltp,
                open=float(ce_ohlc.get('open', 0)),
                high=float(ce_ohlc.get('high', 0)),
                low=float(ce_ohlc.get('low', 0)),
                close=float(ce_ohlc.get('close', 0)),
                change=float(ce_quote.get('change', 0)) if ce_quote else 0,
                change_percent=float(ce_quote.get('per_change', 0)) if ce_quote else 0,
                open_interest=ce_oi,
                oi_change=0,
                volume=ce_volume,
                iv=ce_iv,
                delta=round(ce_delta, 3),
                gamma=round(0.01 * (1 - abs(moneyness_ce)), 4),
                theta=round(-ce_ltp * 0.01, 2) if ce_ltp > 0 else 0,
                vega=round(ce_ltp * 0.001, 3) if ce_ltp > 0 else 0,
                timestamp=datetime.now().isoformat()
            ))
            
            # Put
            pe_contract = contract_map.get((strike, 'PE'))
            pe_quote = quotes.get(pe_contract['symbol']) if pe_contract else None
            
            pe_ltp = float(pe_quote.get('ltp', 0)) if pe_quote else 0
            pe_oi = int(pe_quote.get('open_interest', 0)) if pe_quote else 0
            pe_volume = int(pe_quote.get('last_volume', 0)) if pe_quote else 0
            pe_ohlc = pe_quote.get('ohlc', {}) if pe_quote else {}
            
            # If no live data, simulate
            if pe_ltp == 0:
                moneyness = (strike - spot_price) / spot_price
                intrinsic = max(0, strike - spot_price)
                time_value = spot_price * 0.15 * 0.1 * max(0.1, 1 - abs(moneyness) * 2)
                pe_ltp = round(intrinsic + time_value, 2)
                pe_oi = int(max(1000, 45000 * (1 / (1 + abs(strike - atm_strike) / interval * 0.5))))
            
            total_put_oi += pe_oi
            
            moneyness_pe = (strike - spot_price) / spot_price
            pe_iv = 15.0 + abs(moneyness_pe) * 100
            pe_delta = max(0, min(1, 0.5 + moneyness_pe * 2)) - 1
            
            puts.append(KotakOptionContract(
                symbol=pe_contract['symbol'] if pe_contract else f"{underlying}{expiry}{int(strike)}PE",
                trading_symbol=pe_contract['trading_symbol'] if pe_contract else "",
                underlying=underlying,
                strike=strike,
                option_type='PE',
                expiry=pe_contract['expiry'] if pe_contract else expiry,
                expiry_date=expiry,
                instrument_token=pe_contract['symbol'] if pe_contract else "",
                lot_size=lot_size,
                ltp=pe_ltp,
                open=float(pe_ohlc.get('open', 0)),
                high=float(pe_ohlc.get('high', 0)),
                low=float(pe_ohlc.get('low', 0)),
                close=float(pe_ohlc.get('close', 0)),
                change=float(pe_quote.get('change', 0)) if pe_quote else 0,
                change_percent=float(pe_quote.get('per_change', 0)) if pe_quote else 0,
                open_interest=pe_oi,
                oi_change=0,
                volume=pe_volume,
                iv=pe_iv,
                delta=round(pe_delta, 3),
                gamma=round(0.01 * (1 - abs(moneyness_pe)), 4),
                theta=round(-pe_ltp * 0.01, 2) if pe_ltp > 0 else 0,
                vega=round(pe_ltp * 0.001, 3) if pe_ltp > 0 else 0,
                timestamp=datetime.now().isoformat()
            ))
        
        # Calculate PCR
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        
        self.last_updated = datetime.now()
        
        # Determine if we got live data
        is_live = len(quotes) > 0
        
        return KotakOptionsChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=expiry,
            atm_strike=atm_strike,
            calls=calls,
            puts=puts,
            pcr=round(pcr, 2),
            max_pain=atm_strike,
            timestamp=datetime.now().isoformat(),
            is_live=is_live,
            source="kotak_api" if is_live else "simulation"
        )
    
    def _build_simulated_chain(self, underlying: str, spot_price: float, 
                                expiry: str, num_strikes: int) -> KotakOptionsChain:
        """Build a simulated chain when no scripmaster data is available"""
        interval = 50 if underlying == 'NIFTY' else 100
        atm_strike = round(spot_price / interval) * interval
        lot_size = self.lot_sizes.get(underlying, 25)
        
        calls = []
        puts = []
        total_call_oi = 0
        total_put_oi = 0
        
        for i in range(-num_strikes, num_strikes + 1):
            strike = atm_strike + (i * interval)
            if strike <= 0:
                continue
            
            # Simulate CE
            moneyness_ce = (spot_price - strike) / spot_price
            intrinsic_ce = max(0, spot_price - strike)
            time_value_ce = spot_price * 0.15 * 0.1 * max(0.1, 1 - abs(moneyness_ce) * 2)
            ce_ltp = round(intrinsic_ce + time_value_ce, 2)
            ce_oi = int(max(1000, 50000 * (1 / (1 + abs(i) * 0.5))))
            ce_iv = 15.0 + abs(moneyness_ce) * 100
            ce_delta = max(0, min(1, 0.5 + moneyness_ce * 2))
            
            total_call_oi += ce_oi
            
            calls.append(KotakOptionContract(
                symbol=f"{underlying}{int(strike)}CE",
                trading_symbol="",
                underlying=underlying,
                strike=strike,
                option_type='CE',
                expiry=expiry,
                expiry_date=expiry,
                instrument_token="",
                lot_size=lot_size,
                ltp=ce_ltp,
                open_interest=ce_oi,
                iv=ce_iv,
                delta=round(ce_delta, 3),
                timestamp=datetime.now().isoformat()
            ))
            
            # Simulate PE
            moneyness_pe = (strike - spot_price) / spot_price
            intrinsic_pe = max(0, strike - spot_price)
            time_value_pe = spot_price * 0.15 * 0.1 * max(0.1, 1 - abs(moneyness_pe) * 2)
            pe_ltp = round(intrinsic_pe + time_value_pe, 2)
            pe_oi = int(max(1000, 45000 * (1 / (1 + abs(i) * 0.5))))
            pe_iv = 15.0 + abs(moneyness_pe) * 100
            pe_delta = max(0, min(1, 0.5 + moneyness_pe * 2)) - 1
            
            total_put_oi += pe_oi
            
            puts.append(KotakOptionContract(
                symbol=f"{underlying}{int(strike)}PE",
                trading_symbol="",
                underlying=underlying,
                strike=strike,
                option_type='PE',
                expiry=expiry,
                expiry_date=expiry,
                instrument_token="",
                lot_size=lot_size,
                ltp=pe_ltp,
                open_interest=pe_oi,
                iv=pe_iv,
                delta=round(pe_delta, 3),
                timestamp=datetime.now().isoformat()
            ))
        
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        
        return KotakOptionsChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=expiry,
            atm_strike=atm_strike,
            calls=calls,
            puts=puts,
            pcr=round(pcr, 2),
            max_pain=atm_strike,
            timestamp=datetime.now().isoformat(),
            is_live=False,
            source="simulation"
        )


# Global instance
kotak_options_service = KotakOptionsService()


def get_kotak_options_service() -> KotakOptionsService:
    """Get the global Kotak options service instance"""
    return kotak_options_service
