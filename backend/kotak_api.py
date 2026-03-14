"""
Kotak NEO Trade API Client
Implements the 3-step TOTP-based authentication and all trading endpoints
"""
import os
import httpx
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@dataclass
class KotakSession:
    """Session data after successful authentication"""
    access_token: str = ''
    sid: str = ''
    auth_token: str = ''
    neo_fin_key: str = ''
    base_url: str = ''
    user_id: str = ''
    is_authenticated: bool = False
    
class KotakNeoAPI:
    """
    Kotak NEO Trade API v2 Client
    
    Authentication Flow:
    1. POST /login/otp with TOTP -> sid
    2. POST /login/mpin with MPIN -> Auth, neo-fin-key, baseUrl
    3. Use Auth + Sid + neo-fin-key for all subsequent calls
    """
    
    BASE_URL = 'https://neotradeapi.kotaksecurities.com'
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('KOTAK_ACCESS_TOKEN', '')
        self.session = KotakSession(access_token=self.access_token)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers for authenticated API calls"""
        return {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Auth': self.session.auth_token,
            'Sid': self.session.sid,
            'neo-fin-key': self.session.neo_fin_key
        }
    
    def _get_quote_headers(self) -> Dict[str, str]:
        """Get headers for quote/scripmaster API calls"""
        return {
            'Content-Type': 'application/json',
            'Authorization': self.session.access_token
        }
    
    # ==================== AUTHENTICATION ====================
    
    async def login_step1_totp(self, totp: str) -> Dict:
        """
        Step 1: Validate TOTP and get SID
        
        POST /login/otp
        Body: jData={"accessToken": "...", "otp": "..."}
        Returns: sid
        """
        url = f'{self.BASE_URL}/login/otp'
        payload = {
            'jData': json.dumps({
                'accessToken': self.access_token,
                'otp': totp
            })
        }
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            data = response.json()
            
            if data.get('stat') == 'Ok' and data.get('sid'):
                self.session.sid = data['sid']
                logger.info('Step 1 TOTP validation successful')
                return {'success': True, 'sid': data['sid'], 'message': 'TOTP validated'}
            else:
                error = data.get('message', 'Unknown error')
                logger.error(f'Step 1 TOTP validation failed: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f'Step 1 TOTP error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def login_step2_mpin(self, mpin: str) -> Dict:
        """
        Step 2: Validate MPIN and get Auth token + base URL
        
        POST /login/mpin
        Body: jData={"sid": "...", "mpin": "..."}
        Returns: Auth, neo-fin-key, baseUrl
        """
        if not self.session.sid:
            return {'success': False, 'error': 'No SID. Complete Step 1 first.'}
        
        url = f'{self.BASE_URL}/login/mpin'
        payload = {
            'jData': json.dumps({
                'sid': self.session.sid,
                'mpin': mpin
            })
        }
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                self.session.auth_token = data.get('Auth', '')
                self.session.neo_fin_key = data.get('neo-fin-key', '')
                self.session.base_url = data.get('baseUrl', '')
                self.session.user_id = data.get('userId', '')
                self.session.is_authenticated = True
                
                logger.info('Step 2 MPIN validation successful')
                return {
                    'success': True,
                    'message': 'Authentication complete',
                    'userId': self.session.user_id,
                    'baseUrl': self.session.base_url
                }
            else:
                error = data.get('message', 'Unknown error')
                logger.error(f'Step 2 MPIN validation failed: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f'Step 2 MPIN error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== ORDER MANAGEMENT ====================
    
    async def place_order(self, order_data: Dict) -> Dict:
        """
        Place a new order
        
        Required fields:
        - es: Exchange Segment (nse_fo)
        - ts: Trading Symbol
        - tt: Transaction Type (B/S)
        - qt: Quantity
        - pt: Product Type (MIS for intraday)
        - pc: Price Type (MKT/L/SL)
        - pr: Price (for limit orders)
        - tp: Trigger Price (for SL orders)
        - am: AMO (Y/N)
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/placeorder'
        payload = {'jData': json.dumps(order_data)}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {
                    'success': True,
                    'order_no': data.get('nOrdNo'),
                    'message': 'Order placed successfully'
                }
            else:
                return {'success': False, 'error': data.get('message', 'Order failed')}
        except Exception as e:
            logger.error(f'Place order error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def modify_order(self, order_no: str, modifications: Dict) -> Dict:
        """
        Modify an existing order
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/modifyorder'
        modifications['no'] = order_no
        payload = {'jData': json.dumps(modifications)}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'message': 'Order modified successfully'}
            else:
                return {'success': False, 'error': data.get('message', 'Modification failed')}
        except Exception as e:
            logger.error(f'Modify order error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def cancel_order(self, order_no: str, exchange_segment: str = 'nse_fo') -> Dict:
        """
        Cancel an existing order
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/cancelorder'
        payload = {
            'jData': json.dumps({
                'on': order_no,
                'es': exchange_segment
            })
        }
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'message': 'Order cancelled successfully'}
            else:
                return {'success': False, 'error': data.get('message', 'Cancellation failed')}
        except Exception as e:
            logger.error(f'Cancel order error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== PORTFOLIO ====================
    
    async def get_positions(self) -> Dict:
        """Get current positions"""
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/positions'
        payload = {'jData': json.dumps({})}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'positions': data.get('data', [])}
            else:
                return {'success': True, 'positions': []}
        except Exception as e:
            logger.error(f'Get positions error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_order_book(self) -> Dict:
        """Get order book"""
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/orderbook'
        payload = {'jData': json.dumps({})}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'orders': data.get('data', [])}
            else:
                return {'success': True, 'orders': []}
        except Exception as e:
            logger.error(f'Get order book error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_trade_book(self) -> Dict:
        """Get trade book"""
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/tradebook'
        payload = {'jData': json.dumps({})}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'trades': data.get('data', [])}
            else:
                return {'success': True, 'trades': []}
        except Exception as e:
            logger.error(f'Get trade book error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_holdings(self) -> Dict:
        """Get holdings"""
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/holdings'
        payload = {'jData': json.dumps({})}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'holdings': data.get('data', [])}
            else:
                return {'success': True, 'holdings': []}
        except Exception as e:
            logger.error(f'Get holdings error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_limits(self) -> Dict:
        """Get account limits/margins"""
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/limits'
        payload = {'jData': json.dumps({})}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {
                    'success': True,
                    'limits': {
                        'total_cash': float(data.get('cash', 0)),
                        'available_margin': float(data.get('marginAvailable', 0)),
                        'used_margin': float(data.get('marginUsed', 0)),
                        'unrealized_pnl': float(data.get('unrealizedPnl', 0)),
                        'realized_pnl': float(data.get('realizedPnl', 0))
                    }
                }
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get limits')}
        except Exception as e:
            logger.error(f'Get limits error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== MARKET DATA ====================
    
    async def get_quotes(self, instruments: list) -> Dict:
        """
        Get real-time quotes for instruments
        instruments: [{"exchange_segment": "nse_fo", "token": "..."}]
        """
        url = f'{self.BASE_URL}/quotes'
        
        try:
            response = await self.client.post(
                url,
                json={'instruments': instruments},
                headers=self._get_quote_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'quotes': data.get('data', [])}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get quotes')}
        except Exception as e:
            logger.error(f'Get quotes error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_scripmaster(self, exchange_segment: str = 'nse_fo') -> Dict:
        """
        Get scripmaster data for an exchange segment
        """
        url = f'{self.BASE_URL}/scripmaster'
        
        try:
            response = await self.client.get(
                url,
                params={'exchange_segment': exchange_segment},
                headers=self._get_quote_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {'success': True, 'scripts': data.get('data', [])}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get scripmaster')}
        except Exception as e:
            logger.error(f'Get scripmaster error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== MARGIN CHECK ====================
    
    async def margin_check(self, order_data: Dict) -> Dict:
        """
        Check margin requirement for an order
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        url = f'{self.session.base_url}/margincheck'
        payload = {'jData': json.dumps(order_data)}
        
        try:
            response = await self.client.post(
                url,
                data=payload,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if data.get('stat') == 'Ok':
                return {
                    'success': True,
                    'margin_required': float(data.get('marginRequired', 0)),
                    'available_margin': float(data.get('marginAvailable', 0)),
                    'can_trade': data.get('canTrade', False)
                }
            else:
                return {'success': False, 'error': data.get('message', 'Margin check failed')}
        except Exception as e:
            logger.error(f'Margin check error: {e}')
            return {'success': False, 'error': str(e)}
