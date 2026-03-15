"""
Kotak Scrip Master - Fetches and parses instrument data from Kotak
Provides real instrument tokens for options, stocks, and indices
"""
import httpx
import logging
import csv
import io
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OptionInstrument:
    """Represents an option instrument from scrip master"""
    instrument_token: str
    trading_symbol: str
    underlying: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    lot_size: int
    exchange_segment: str

class KotakScripMaster:
    """
    Fetches and parses Kotak scrip master data
    Provides instrument tokens for options subscription
    """
    
    # Scrip master URLs
    SCRIP_MASTER_BASE = "https://mis.kotaksecurities.com/fno/instruments"
    
    # Alternative URLs
    NSE_FO_URL = "https://mis.kotaksecurities.com/fno/instruments/fno_instruments.csv"
    NSE_CM_URL = "https://mis.kotaksecurities.com/fno/instruments/cash_instruments.csv"
    
    def __init__(self):
        self.fno_instruments: List[Dict] = []
        self.cash_instruments: List[Dict] = []
        self.nifty_options: Dict[str, List[OptionInstrument]] = {}  # expiry -> list of options
        self.banknifty_options: Dict[str, List[OptionInstrument]] = {}
        self.last_updated: Optional[datetime] = None
    
    async def fetch_scrip_master(self, access_token: str) -> bool:
        """
        Fetch scrip master from Kotak API
        
        Args:
            access_token: Authorization token from login
        """
        try:
            headers = {
                'Authorization': access_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                # Try to fetch F&O instruments
                logger.info("Fetching F&O scrip master...")
                response = await client.get(self.NSE_FO_URL, headers=headers)
                
                if response.status_code == 200:
                    self._parse_fno_csv(response.text)
                    self.last_updated = datetime.now()
                    logger.info(f"Loaded {len(self.fno_instruments)} F&O instruments")
                    return True
                else:
                    logger.warning(f"Failed to fetch scrip master: {response.status_code}")
                    # Try alternative method
                    return await self._fetch_from_alternative()
                    
        except Exception as e:
            logger.error(f"Error fetching scrip master: {e}")
            return False
    
    async def _fetch_from_alternative(self) -> bool:
        """Fetch scrip master from alternative source"""
        try:
            # Try NSE bhav copy or similar
            url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    self._parse_nse_option_chain(data)
                    return True
        except Exception as e:
            logger.error(f"Alternative fetch failed: {e}")
        return False
    
    def _parse_fno_csv(self, csv_text: str):
        """Parse F&O instruments CSV"""
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            self.fno_instruments = []
            
            for row in reader:
                self.fno_instruments.append(row)
                
                # Extract NIFTY and BANKNIFTY options
                symbol = row.get('pSymbol', row.get('symbol', ''))
                underlying = row.get('pUnderlying', row.get('underlying', ''))
                
                if 'NIFTY' in underlying and 'BANK' not in underlying:
                    self._add_option(row, 'NIFTY')
                elif 'BANKNIFTY' in underlying or 'NIFTY BANK' in underlying:
                    self._add_option(row, 'BANKNIFTY')
                    
        except Exception as e:
            logger.error(f"Error parsing FNO CSV: {e}")
    
    def _add_option(self, row: Dict, underlying: str):
        """Add an option instrument to the cache"""
        try:
            token = row.get('pToken', row.get('instrument_token', row.get('token', '')))
            symbol = row.get('pSymbol', row.get('trading_symbol', ''))
            strike = float(row.get('pStrike', row.get('strike', 0)))
            option_type = row.get('pOptionType', row.get('option_type', ''))
            expiry = row.get('pExpiryDate', row.get('expiry', ''))
            lot_size = int(row.get('pLotSize', row.get('lot_size', 25 if underlying == 'NIFTY' else 15)))
            
            if not option_type or option_type not in ['CE', 'PE']:
                return
            
            option = OptionInstrument(
                instrument_token=str(token),
                trading_symbol=symbol,
                underlying=underlying,
                strike=strike,
                option_type=option_type,
                expiry=expiry,
                lot_size=lot_size,
                exchange_segment='nse_fo'
            )
            
            options_dict = self.nifty_options if underlying == 'NIFTY' else self.banknifty_options
            if expiry not in options_dict:
                options_dict[expiry] = []
            options_dict[expiry].append(option)
            
        except Exception as e:
            logger.error(f"Error adding option: {e}")
    
    def _parse_nse_option_chain(self, data: Dict):
        """Parse NSE option chain data (alternative source)"""
        try:
            records = data.get('records', {})
            expiry_dates = records.get('expiryDates', [])
            option_data = records.get('data', [])
            
            self.nifty_options = {}
            
            for record in option_data:
                expiry = record.get('expiryDate', '')
                strike = record.get('strikePrice', 0)
                
                # CE data
                ce = record.get('CE', {})
                if ce:
                    option = OptionInstrument(
                        instrument_token=str(ce.get('identifier', '')),
                        trading_symbol=ce.get('identifier', ''),
                        underlying='NIFTY',
                        strike=float(strike),
                        option_type='CE',
                        expiry=expiry,
                        lot_size=25,
                        exchange_segment='nse_fo'
                    )
                    if expiry not in self.nifty_options:
                        self.nifty_options[expiry] = []
                    self.nifty_options[expiry].append(option)
                
                # PE data
                pe = record.get('PE', {})
                if pe:
                    option = OptionInstrument(
                        instrument_token=str(pe.get('identifier', '')),
                        trading_symbol=pe.get('identifier', ''),
                        underlying='NIFTY',
                        strike=float(strike),
                        option_type='PE',
                        expiry=expiry,
                        lot_size=25,
                        exchange_segment='nse_fo'
                    )
                    self.nifty_options[expiry].append(option)
                    
            logger.info(f"Parsed {sum(len(v) for v in self.nifty_options.values())} NIFTY options from NSE")
            
        except Exception as e:
            logger.error(f"Error parsing NSE option chain: {e}")
    
    def get_expiries(self, underlying: str = 'NIFTY') -> List[str]:
        """Get available expiry dates for an underlying"""
        options_dict = self.nifty_options if underlying == 'NIFTY' else self.banknifty_options
        return sorted(options_dict.keys())
    
    def get_options_for_expiry(self, underlying: str, expiry: str) -> List[OptionInstrument]:
        """Get all options for a specific expiry"""
        options_dict = self.nifty_options if underlying == 'NIFTY' else self.banknifty_options
        return options_dict.get(expiry, [])
    
    def get_options_around_strike(self, underlying: str, expiry: str, 
                                   atm_strike: float, num_strikes: int = 10) -> List[OptionInstrument]:
        """Get options around a specific strike price"""
        all_options = self.get_options_for_expiry(underlying, expiry)
        
        # Get unique strikes
        strikes = sorted(set(opt.strike for opt in all_options))
        
        # Find ATM index
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - atm_strike), default=0)
        
        # Get strikes around ATM
        start_idx = max(0, atm_idx - num_strikes)
        end_idx = min(len(strikes), atm_idx + num_strikes + 1)
        selected_strikes = set(strikes[start_idx:end_idx])
        
        # Filter options
        return [opt for opt in all_options if opt.strike in selected_strikes]
    
    def get_subscription_tokens(self, underlying: str, expiry: str, 
                                 atm_strike: float, num_strikes: int = 10) -> str:
        """
        Get HSM subscription string for options
        
        Returns format: "nse_fo|token1&nse_fo|token2&..."
        """
        options = self.get_options_around_strike(underlying, expiry, atm_strike, num_strikes)
        
        if not options:
            logger.warning(f"No options found for {underlying} expiry {expiry}")
            return ""
        
        tokens = [f"nse_fo|{opt.instrument_token}" for opt in options]
        return "&".join(tokens) + "&"
    
    def generate_option_symbols(self, underlying: str, spot_price: float, 
                                  expiry_date: str, num_strikes: int = 10) -> List[Dict]:
        """
        Generate option symbol format for Kotak API when scrip master is not available
        
        Format: NIFTY{DDMON}{STRIKE}{CE/PE}
        Example: NIFTY19MAR23150CE
        """
        options = []
        
        # Calculate strike interval
        interval = 50 if underlying == 'NIFTY' else 100
        atm_strike = round(spot_price / interval) * interval
        
        # Parse expiry date
        try:
            if '-' in expiry_date:
                exp = datetime.strptime(expiry_date, '%Y-%m-%d')
            else:
                exp = datetime.strptime(expiry_date, '%d-%b-%Y')
            exp_str = exp.strftime('%d%b').upper()  # e.g., "19MAR"
        except:
            exp_str = expiry_date[:5].upper()
        
        # Generate strikes
        for i in range(-num_strikes, num_strikes + 1):
            strike = int(atm_strike + (i * interval))
            
            for opt_type in ['CE', 'PE']:
                symbol = f"{underlying}{exp_str}{strike}{opt_type}"
                options.append({
                    'symbol': symbol,
                    'underlying': underlying,
                    'strike': strike,
                    'option_type': opt_type,
                    'expiry': expiry_date,
                    'exchange_segment': 'nse_fo'
                })
        
        return options


# Global instance
scrip_master = KotakScripMaster()
