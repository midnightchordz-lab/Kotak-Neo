"""
Options Chain Module
Generates and manages options chain data for NIFTY and BANKNIFTY
"""
import random
import math
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

class OptionType(Enum):
    CALL = "CE"
    PUT = "PE"

@dataclass
class OptionContract:
    """Represents a single option contract"""
    underlying: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    ltp: float
    change: float
    change_percent: float
    open_interest: int
    oi_change: int
    volume: int
    bid: float
    ask: float
    bid_qty: int
    ask_qty: int
    iv: float  # Implied Volatility
    delta: float
    gamma: float
    theta: float
    vega: float

@dataclass 
class OptionsChain:
    """Complete options chain for an underlying"""
    underlying: str
    spot_price: float
    expiry: str
    atm_strike: float
    calls: List[OptionContract]
    puts: List[OptionContract]
    pcr: float  # Put-Call Ratio
    max_pain: float
    timestamp: str

class OptionsChainGenerator:
    """
    Generates realistic options chain data for simulation
    Based on Black-Scholes model approximations
    """
    
    # Strike intervals
    STRIKE_INTERVALS = {
        'NIFTY': 50,
        'BANKNIFTY': 100
    }
    
    # Lot sizes
    LOT_SIZES = {
        'NIFTY': 25,
        'BANKNIFTY': 15
    }
    
    def __init__(self):
        self.risk_free_rate = 0.065  # 6.5% risk-free rate
        self.base_iv = {
            'NIFTY': 0.12,  # 12% base IV
            'BANKNIFTY': 0.15  # 15% base IV (more volatile)
        }
    
    def generate_expiries(self) -> List[str]:
        """Generate list of upcoming expiry dates (weekly + monthly)"""
        today = datetime.now()
        expiries = []
        
        # Find next 4 Thursdays (weekly expiry)
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and today.hour >= 15:
            days_until_thursday = 7
        
        for i in range(4):
            expiry_date = today + timedelta(days=days_until_thursday + (i * 7))
            expiries.append(expiry_date.strftime("%Y-%m-%d"))
        
        return expiries
    
    def get_atm_strike(self, spot_price: float, underlying: str) -> float:
        """Get At-The-Money strike price"""
        interval = self.STRIKE_INTERVALS.get(underlying, 50)
        return round(spot_price / interval) * interval
    
    def calculate_option_price(self, spot: float, strike: float, 
                                days_to_expiry: int, iv: float, 
                                option_type: str) -> float:
        """
        Simplified option pricing using approximation
        """
        if days_to_expiry <= 0:
            # At expiry
            if option_type == "CE":
                return max(0, spot - strike)
            else:
                return max(0, strike - spot)
        
        t = days_to_expiry / 365
        
        # Intrinsic value
        if option_type == "CE":
            intrinsic = max(0, spot - strike)
        else:
            intrinsic = max(0, strike - spot)
        
        # Time value approximation
        moneyness = (spot - strike) / spot if option_type == "CE" else (strike - spot) / spot
        time_value = spot * iv * math.sqrt(t) * math.exp(-abs(moneyness) * 2)
        
        # Add some randomness for realism
        noise = random.gauss(0, spot * 0.001)
        
        return max(0.05, round(intrinsic + time_value + noise, 2))
    
    def calculate_greeks(self, spot: float, strike: float, 
                         days_to_expiry: int, iv: float, 
                         option_type: str) -> Dict[str, float]:
        """Calculate option Greeks (simplified)"""
        if days_to_expiry <= 0:
            return {'delta': 1.0 if option_type == "CE" else -1.0, 
                    'gamma': 0, 'theta': 0, 'vega': 0}
        
        t = days_to_expiry / 365
        moneyness = (spot - strike) / (spot * iv * math.sqrt(t))
        
        # Simplified delta
        if option_type == "CE":
            delta = 0.5 + 0.4 * math.tanh(moneyness)
        else:
            delta = -0.5 + 0.4 * math.tanh(moneyness)
        
        # Simplified gamma (highest at ATM)
        gamma = 0.01 * math.exp(-moneyness ** 2 / 2)
        
        # Simplified theta (time decay)
        theta = -spot * iv / (2 * math.sqrt(t * 365)) * 0.01
        
        # Simplified vega
        vega = spot * math.sqrt(t) * 0.01 * math.exp(-moneyness ** 2 / 2)
        
        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 6),
            'theta': round(theta, 2),
            'vega': round(vega, 2)
        }
    
    def generate_iv_smile(self, atm_iv: float, strike: float, 
                          atm_strike: float, spot: float) -> float:
        """Generate IV smile - higher IV for OTM options"""
        moneyness = abs(strike - atm_strike) / spot
        # IV increases for away-from-money strikes (volatility smile)
        iv_adjustment = moneyness * 0.5  # 0.5% IV increase per 1% OTM
        return atm_iv * (1 + iv_adjustment + random.gauss(0, 0.01))
    
    def generate_chain(self, underlying: str, spot_price: float, 
                       expiry_date: Optional[str] = None,
                       num_strikes: int = 15) -> OptionsChain:
        """
        Generate complete options chain for an underlying
        
        Args:
            underlying: NIFTY or BANKNIFTY
            spot_price: Current spot price
            expiry_date: Expiry date (uses nearest if not provided)
            num_strikes: Number of strikes on each side of ATM
        """
        if expiry_date is None:
            expiries = self.generate_expiries()
            expiry_date = expiries[0]
        
        # Calculate days to expiry
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        days_to_expiry = max(0, (expiry - datetime.now()).days)
        
        interval = self.STRIKE_INTERVALS.get(underlying, 50)
        atm_strike = self.get_atm_strike(spot_price, underlying)
        base_iv = self.base_iv.get(underlying, 0.12)
        
        calls = []
        puts = []
        total_call_oi = 0
        total_put_oi = 0
        
        # Generate strikes around ATM
        for i in range(-num_strikes, num_strikes + 1):
            strike = atm_strike + (i * interval)
            if strike <= 0:
                continue
            
            # Generate IV with smile
            iv = self.generate_iv_smile(base_iv, strike, atm_strike, spot_price)
            
            # Calculate call option
            call_price = self.calculate_option_price(spot_price, strike, 
                                                      days_to_expiry, iv, "CE")
            call_greeks = self.calculate_greeks(spot_price, strike, 
                                                 days_to_expiry, iv, "CE")
            
            # Generate OI (higher for ATM, lower for deep ITM/OTM)
            distance_from_atm = abs(strike - atm_strike) / interval
            base_oi = random.randint(50000, 200000)
            call_oi = int(base_oi * math.exp(-distance_from_atm * 0.3))
            call_oi_change = random.randint(-int(call_oi * 0.1), int(call_oi * 0.1))
            
            call = OptionContract(
                underlying=underlying,
                strike=strike,
                option_type="CE",
                expiry=expiry_date,
                ltp=call_price,
                change=round(random.gauss(0, call_price * 0.05), 2),
                change_percent=round(random.gauss(0, 5), 2),
                open_interest=call_oi,
                oi_change=call_oi_change,
                volume=random.randint(1000, 50000),
                bid=round(call_price - 0.5, 2),
                ask=round(call_price + 0.5, 2),
                bid_qty=random.randint(100, 1000),
                ask_qty=random.randint(100, 1000),
                iv=round(iv * 100, 2),
                **call_greeks
            )
            calls.append(call)
            total_call_oi += call_oi
            
            # Calculate put option
            put_price = self.calculate_option_price(spot_price, strike, 
                                                     days_to_expiry, iv, "PE")
            put_greeks = self.calculate_greeks(spot_price, strike, 
                                                days_to_expiry, iv, "PE")
            
            put_oi = int(base_oi * math.exp(-distance_from_atm * 0.25))
            put_oi_change = random.randint(-int(put_oi * 0.1), int(put_oi * 0.1))
            
            put = OptionContract(
                underlying=underlying,
                strike=strike,
                option_type="PE",
                expiry=expiry_date,
                ltp=put_price,
                change=round(random.gauss(0, put_price * 0.05), 2),
                change_percent=round(random.gauss(0, 5), 2),
                open_interest=put_oi,
                oi_change=put_oi_change,
                volume=random.randint(1000, 50000),
                bid=round(put_price - 0.5, 2),
                ask=round(put_price + 0.5, 2),
                bid_qty=random.randint(100, 1000),
                ask_qty=random.randint(100, 1000),
                iv=round(iv * 100, 2),
                **put_greeks
            )
            puts.append(put)
            total_put_oi += put_oi
        
        # Calculate PCR
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
        
        # Calculate Max Pain (simplified - strike with max writer profit)
        max_pain = atm_strike  # Simplified: assume max pain is at ATM
        
        return OptionsChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=expiry_date,
            atm_strike=atm_strike,
            calls=sorted(calls, key=lambda x: x.strike),
            puts=sorted(puts, key=lambda x: x.strike),
            pcr=pcr,
            max_pain=max_pain,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def get_option_signal(self, chain: OptionsChain) -> Dict:
        """
        Generate trading signal based on options chain data
        Analyzes PCR, OI buildup, and max pain
        """
        spot = chain.spot_price
        pcr = chain.pcr
        
        # Find strikes with highest OI
        max_call_oi_strike = max(chain.calls, key=lambda x: x.open_interest).strike
        max_put_oi_strike = max(chain.puts, key=lambda x: x.open_interest).strike
        
        # Analyze signal
        signals = []
        
        # PCR Analysis
        if pcr > 1.2:
            signals.append(("BULLISH", "High PCR indicates more put writing (bullish)"))
        elif pcr < 0.8:
            signals.append(("BEARISH", "Low PCR indicates more call writing (bearish)"))
        else:
            signals.append(("NEUTRAL", "PCR near 1 indicates balanced sentiment"))
        
        # OI Concentration Analysis
        if max_call_oi_strike > spot:
            signals.append(("RESISTANCE", f"Heavy call OI at {max_call_oi_strike} acts as resistance"))
        if max_put_oi_strike < spot:
            signals.append(("SUPPORT", f"Heavy put OI at {max_put_oi_strike} acts as support"))
        
        # Overall direction
        if pcr > 1.1 and max_put_oi_strike < spot:
            direction = "BULLISH"
            confidence = min(90, 50 + (pcr - 1) * 30)
        elif pcr < 0.9 and max_call_oi_strike > spot:
            direction = "BEARISH"
            confidence = min(90, 50 + (1 - pcr) * 30)
        else:
            direction = "NEUTRAL"
            confidence = 50
        
        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "pcr": pcr,
            "support": max_put_oi_strike,
            "resistance": max_call_oi_strike,
            "max_pain": chain.max_pain,
            "signals": signals,
            "recommendation": self._get_recommendation(direction, spot, chain)
        }
    
    def _get_recommendation(self, direction: str, spot: float, 
                            chain: OptionsChain) -> Dict:
        """Generate trading recommendation based on options analysis"""
        atm = chain.atm_strike
        interval = self.STRIKE_INTERVALS.get(chain.underlying, 50)
        
        if direction == "BULLISH":
            # Recommend buying ATM call or selling OTM put
            call_strike = atm
            put_strike = atm - (2 * interval)
            return {
                "primary": f"BUY {chain.underlying} {call_strike} CE",
                "alternative": f"SELL {chain.underlying} {put_strike} PE",
                "strategy": "Bull Call Spread or Cash Secured Put"
            }
        elif direction == "BEARISH":
            # Recommend buying ATM put or selling OTM call
            put_strike = atm
            call_strike = atm + (2 * interval)
            return {
                "primary": f"BUY {chain.underlying} {put_strike} PE",
                "alternative": f"SELL {chain.underlying} {call_strike} CE",
                "strategy": "Bear Put Spread or Covered Call"
            }
        else:
            # Recommend iron condor or straddle
            return {
                "primary": f"SELL {chain.underlying} {atm} STRADDLE",
                "alternative": f"IRON CONDOR around {atm}",
                "strategy": "Range-bound strategy - Collect premium"
            }


# Singleton instance
options_chain_generator = OptionsChainGenerator()
