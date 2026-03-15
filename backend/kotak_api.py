"""
Kotak NEO Trade API Client v2
Based on official Kotak NEO Python SDK: https://github.com/Kotak-Neo/Kotak-neo-api-v2
Implements TOTP-based authentication and all trading endpoints
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
    consumer_key: str = ''  # This is the access_token used as Authorization header
    view_token: str = ''    # Token from TOTP login (step 1)
    sid: str = ''           # Session ID from TOTP login
    edit_token: str = ''    # Token from MPIN validation (step 2)
    edit_sid: str = ''      # Edit session ID from MPIN validation
    rid: str = ''           # Request ID from MPIN validation
    server_id: str = ''     # Server ID for websocket
    neo_fin_key: str = 'neotradeapi'  # Default neo-fin-key
    base_url: str = ''      # Base URL for trading API calls
    data_center: str = ''   # Data center info
    user_id: str = ''
    ucc: str = ''
    is_authenticated: bool = False
    
class KotakNeoAPI:
    """
    Kotak NEO Trade API v2 Client
    Based on official SDK: https://github.com/Kotak-Neo/Kotak-neo-api-v2
    
    Authentication Flow:
    1. POST /login/1.0/tradeApiLogin with mobile, ucc, totp -> view_token, sid
    2. POST /login/1.0/tradeApiValidate with mpin -> edit_token, edit_sid, baseUrl
    3. Use edit_token + edit_sid + neo-fin-key for all subsequent calls
    """
    
    # Base URL for login endpoints (from official SDK urls.py)
    LOGIN_BASE_URL = 'https://mis.kotaksecurities.com'
    
    # Default neo-fin-key for production (from official SDK settings.py)
    DEFAULT_NEO_FIN_KEY = 'neotradeapi'
    
    def __init__(self, consumer_key: Optional[str] = None):
        """
        Initialize the Kotak NEO API client.
        
        Args:
            consumer_key: The access token from Kotak NEO API dashboard.
                         This is used as the Authorization header.
        """
        self.consumer_key = consumer_key or os.getenv('KOTAK_ACCESS_TOKEN', '')
        self.mobile_number = os.getenv('KOTAK_MOBILE', '')
        self.ucc = os.getenv('KOTAK_UCC', '')
        
        self.session = KotakSession(
            consumer_key=self.consumer_key,
            ucc=self.ucc
        )
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    def _get_login_headers(self) -> Dict[str, str]:
        """Get headers for login API calls (TOTP login)"""
        return {
            'Authorization': self.consumer_key,
            'neo-fin-key': self.DEFAULT_NEO_FIN_KEY,
            'Content-Type': 'application/json'
        }
    
    def _get_validate_headers(self) -> Dict[str, str]:
        """Get headers for MPIN validation API call"""
        return {
            'Authorization': self.consumer_key,
            'sid': self.session.sid,
            'Auth': self.session.view_token,
            'neo-fin-key': self.DEFAULT_NEO_FIN_KEY,
            'Content-Type': 'application/json'
        }
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers for authenticated trading API calls"""
        return {
            'Authorization': self.consumer_key,
            'sid': self.session.edit_sid,
            'Auth': self.session.edit_token,
            'neo-fin-key': self.session.neo_fin_key or self.DEFAULT_NEO_FIN_KEY,
            'Content-Type': 'application/json'
        }
    
    def _get_quote_headers(self) -> Dict[str, str]:
        """Get headers for quote/scripmaster API calls"""
        return {
            'Content-Type': 'application/json',
            'Authorization': self.consumer_key
        }
    
    # ==================== AUTHENTICATION ====================
    
    async def login_step1_totp(self, totp: str, mobile_number: Optional[str] = None, ucc: Optional[str] = None) -> Dict:
        """
        Step 1: TOTP Login - Validate TOTP and get view_token + sid
        
        Based on official SDK totp_api.py:
        POST https://mis.kotaksecurities.com/login/1.0/tradeApiLogin
        
        Headers:
            Authorization: <consumer_key>
            neo-fin-key: neotradeapi
            Content-Type: application/json
        
        Body:
            {
                "mobileNumber": "+91XXXXXXXXXX",
                "ucc": "XXXXX",
                "totp": "123456"
            }
        
        Returns:
            view_token (token), sid for use in step 2
        """
        # Use provided values or fall back to environment variables
        mobile = mobile_number or self.mobile_number
        user_ucc = ucc or self.ucc
        
        if not mobile or not user_ucc:
            return {
                'success': False, 
                'error': 'Mobile number and UCC are required. Set KOTAK_MOBILE and KOTAK_UCC environment variables.'
            }
        
        # Endpoint from official SDK: PROD_URL['totp_login'] = 'login/1.0/tradeApiLogin'
        url = f'{self.LOGIN_BASE_URL}/login/1.0/tradeApiLogin'
        
        # Request body as per official SDK totp_api.py
        body = {
            "mobileNumber": mobile,
            "ucc": user_ucc,
            "totp": totp
        }
        
        logger.info(f"TOTP Login Request to: {url}")
        logger.info(f"Mobile: {mobile}, UCC: {user_ucc}")
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_login_headers()
            )
            
            logger.info(f"TOTP Response Status: {response.status_code}")
            logger.info(f"TOTP Response: {response.text}")
            
            data = response.json()
            
            # Check for successful response (status 2xx)
            if 200 <= response.status_code <= 299 and data.get('data'):
                response_data = data.get('data', {})
                self.session.view_token = response_data.get('token', '')
                self.session.sid = response_data.get('sid', '')
                self.session.user_id = response_data.get('ucc', user_ucc)
                
                logger.info('Step 1 TOTP validation successful')
                return {
                    'success': True,
                    'sid': self.session.sid,
                    'message': 'TOTP validated successfully',
                    'data': response_data
                }
            else:
                # Handle error response
                error = data.get('message') or data.get('error') or data.get('Error') or 'Unknown error'
                if isinstance(data.get('error'), list) and len(data['error']) > 0:
                    error = data['error'][0].get('message', error)
                
                logger.error(f'Step 1 TOTP validation failed: {error}')
                logger.error(f'Full response: {data}')
                return {'success': False, 'error': error, 'raw_response': data}
                
        except Exception as e:
            logger.error(f'Step 1 TOTP error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def login_step2_mpin(self, mpin: str) -> Dict:
        """
        Step 2: MPIN Validation - Validate MPIN and get edit_token + baseUrl
        
        Based on official SDK totp_api.py:
        POST https://mis.kotaksecurities.com/login/1.0/tradeApiValidate
        
        Headers:
            Authorization: <consumer_key>
            sid: <from step 1>
            Auth: <view_token from step 1>
            neo-fin-key: neotradeapi
        
        Body:
            {
                "mpin": "123456"
            }
        
        Returns:
            edit_token (token), edit_sid, rid, hsServerId, dataCenter, baseUrl
        """
        if not self.session.sid or not self.session.view_token:
            return {'success': False, 'error': 'No session data. Complete Step 1 (TOTP login) first.'}
        
        # Endpoint from official SDK: PROD_URL['totp_validate'] = 'login/1.0/tradeApiValidate'
        url = f'{self.LOGIN_BASE_URL}/login/1.0/tradeApiValidate'
        
        # Request body as per official SDK totp_api.py
        body = {
            "mpin": mpin
        }
        
        logger.info(f"MPIN Validation Request to: {url}")
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_validate_headers()
            )
            
            logger.info(f"MPIN Response Status: {response.status_code}")
            logger.info(f"MPIN Response: {response.text}")
            
            data = response.json()
            
            # Check for successful response (status 2xx)
            if 200 <= response.status_code <= 299 and data.get('data'):
                response_data = data.get('data', {})
                
                # Store session data as per official SDK
                self.session.edit_token = response_data.get('token', '')
                self.session.edit_sid = response_data.get('sid', '')
                self.session.rid = response_data.get('rid', '')
                self.session.server_id = response_data.get('hsServerId', '')
                self.session.data_center = response_data.get('dataCenter', '')
                self.session.base_url = response_data.get('baseUrl', '')
                self.session.is_authenticated = True
                
                logger.info('Step 2 MPIN validation successful')
                logger.info(f'Base URL for trading: {self.session.base_url}')
                
                return {
                    'success': True,
                    'message': 'Authentication complete',
                    'userId': response_data.get('ucc', ''),
                    'greetingName': response_data.get('greetingName', ''),
                    'baseUrl': self.session.base_url,
                    'dataCenter': self.session.data_center
                }
            else:
                error = data.get('message') or data.get('error') or data.get('Error') or 'Unknown error'
                if isinstance(data.get('error'), list) and len(data['error']) > 0:
                    error = data['error'][0].get('message', error)
                    
                logger.error(f'Step 2 MPIN validation failed: {error}')
                logger.error(f'Full response: {data}')
                return {'success': False, 'error': error, 'raw_response': data}
                
        except Exception as e:
            logger.error(f'Step 2 MPIN error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== ORDER MANAGEMENT ====================
    
    async def place_order(self, order_data: Dict) -> Dict:
        """
        Place a new order using official SDK format.
        
        Based on official SDK OrderAPI:
        POST {baseUrl}/quick/order/rule/ms/place
        
        Required fields (as per SDK):
        - exchange_segment: nse_cm, bse_cm, nse_fo, bse_fo, cde_fo, mcx_fo
        - product: NRML, CNC, MIS, CO, BO, MTF
        - price: scrip price
        - order_type: L, MKT, SL, SL-M
        - quantity: The stock quantity
        - validity: DAY, IOC, GTC, EOS, GTD
        - trading_symbol: scrip trading symbol
        - transaction_type: B, S
        - amo: YES or NO (default NO)
        - disclosed_quantity: default 0
        - market_protection: default 0
        - trigger_price: for SL orders
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated. Complete login first.'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL. Authentication may be incomplete.'}
        
        # Endpoint from official SDK: PROD_URL['place_order'] = 'quick/order/rule/ms/place'
        url = f'{self.session.base_url}/quick/order/rule/ms/place'
        
        logger.info(f"Place order request to: {url}")
        logger.info(f"Order data: {order_data}")
        
        try:
            response = await self.client.post(
                url,
                json=order_data,
                headers=self._get_auth_headers()
            )
            
            logger.info(f"Place order response status: {response.status_code}")
            logger.info(f"Place order response: {response.text}")
            
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {
                    'success': True,
                    'order_no': data.get('nOrdNo') or data.get('orderId'),
                    'message': 'Order placed successfully',
                    'data': data
                }
            else:
                error = data.get('message') or data.get('error') or 'Order failed'
                return {'success': False, 'error': error, 'raw_response': data}
        except Exception as e:
            logger.error(f'Place order error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def modify_order(self, order_id: str, modifications: Dict) -> Dict:
        """
        Modify an existing order.
        
        Based on official SDK:
        POST {baseUrl}/quick/order/vr/modify
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['modify_order'] = 'quick/order/vr/modify'
        url = f'{self.session.base_url}/quick/order/vr/modify'
        modifications['order_id'] = order_id
        
        try:
            response = await self.client.post(
                url,
                json=modifications,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'message': 'Order modified successfully', 'data': data}
            else:
                return {'success': False, 'error': data.get('message', 'Modification failed')}
        except Exception as e:
            logger.error(f'Modify order error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def cancel_order(self, order_id: str, amo: str = 'NO') -> Dict:
        """
        Cancel an existing order.
        
        Based on official SDK:
        POST {baseUrl}/quick/order/cancel
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['cancel_order'] = 'quick/order/cancel'
        url = f'{self.session.base_url}/quick/order/cancel'
        body = {
            'order_id': order_id,
            'amo': amo
        }
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'message': 'Order cancelled successfully', 'data': data}
            else:
                return {'success': False, 'error': data.get('message', 'Cancellation failed')}
        except Exception as e:
            logger.error(f'Cancel order error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== PORTFOLIO ====================
    
    async def get_positions(self) -> Dict:
        """
        Get current positions.
        
        Based on official SDK:
        POST {baseUrl}/quick/user/positions
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['positions'] = 'quick/user/positions'
        url = f'{self.session.base_url}/quick/user/positions'
        
        try:
            response = await self.client.post(
                url,
                json={},
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'positions': data.get('data', []), 'raw_response': data}
            else:
                return {'success': True, 'positions': [], 'message': data.get('message', '')}
        except Exception as e:
            logger.error(f'Get positions error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_order_book(self) -> Dict:
        """
        Get order book.
        
        Based on official SDK:
        POST {baseUrl}/quick/user/orders
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['order_book'] = 'quick/user/orders'
        url = f'{self.session.base_url}/quick/user/orders'
        
        try:
            response = await self.client.post(
                url,
                json={},
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'orders': data.get('data', []), 'raw_response': data}
            else:
                return {'success': True, 'orders': [], 'message': data.get('message', '')}
        except Exception as e:
            logger.error(f'Get order book error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_trade_book(self) -> Dict:
        """
        Get trade book.
        
        Based on official SDK:
        POST {baseUrl}/quick/user/trades
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['trade_report'] = 'quick/user/trades'
        url = f'{self.session.base_url}/quick/user/trades'
        
        try:
            response = await self.client.post(
                url,
                json={},
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'trades': data.get('data', []), 'raw_response': data}
            else:
                return {'success': True, 'trades': [], 'message': data.get('message', '')}
        except Exception as e:
            logger.error(f'Get trade book error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_holdings(self) -> Dict:
        """
        Get portfolio holdings.
        
        Based on official SDK:
        POST {baseUrl}/portfolio/v1/holdings
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['holdings'] = 'portfolio/v1/holdings'
        url = f'{self.session.base_url}/portfolio/v1/holdings'
        
        try:
            response = await self.client.post(
                url,
                json={},
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'holdings': data.get('data', []), 'raw_response': data}
            else:
                return {'success': True, 'holdings': [], 'message': data.get('message', '')}
        except Exception as e:
            logger.error(f'Get holdings error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_limits(self, segment: str = 'ALL', exchange: str = 'ALL', product: str = 'ALL') -> Dict:
        """
        Get account limits/margins.
        
        Based on official SDK:
        POST {baseUrl}/quick/user/limits
        
        Args:
            segment: CASH, CUR, FO, ALL (default ALL)
            exchange: NSE, BSE, ALL (default ALL)
            product: CNC, MIS, NRML, ALL (default ALL)
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['limits'] = 'quick/user/limits'
        url = f'{self.session.base_url}/quick/user/limits'
        
        body = {
            'segment': segment,
            'exchange': exchange,
            'product': product
        }
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {
                    'success': True,
                    'limits': data,
                    'raw_response': data
                }
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get limits')}
        except Exception as e:
            logger.error(f'Get limits error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== MARKET DATA ====================
    
    async def get_quotes(self, instrument_tokens: list, quote_type: str = 'all') -> Dict:
        """
        Get real-time quotes for instruments.
        
        Based on official SDK QuotesAPI:
        This API can be accessed with just the consumer_key (access_token).
        
        Args:
            instrument_tokens: List of dicts with instrument_token and exchange_segment
                Example: [{"instrument_token": "11536", "exchange_segment": "nse_cm"}]
            quote_type: all, depth, ohlc, ltp, oi, 52w, circuit_limits, scrip_details
        """
        # Quotes API endpoint (from official SDK)
        url = f'{self.LOGIN_BASE_URL}/script-details/1.0/quotes/neosymbol'
        
        body = {
            'instrument_tokens': instrument_tokens,
            'quote_type': quote_type or 'all'
        }
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_quote_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'quotes': data.get('data', data), 'raw_response': data}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get quotes')}
        except Exception as e:
            logger.error(f'Get quotes error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def get_scripmaster(self, exchange_segment: str = None) -> Dict:
        """
        Get scripmaster data for an exchange segment.
        
        Based on official SDK ScripMasterAPI:
        GET {baseUrl}/script-details/1.0/masterscrip/file-paths
        
        Args:
            exchange_segment: nse_cm, bse_cm, nse_fo, bse_fo, cde_fo, mcx_fo (optional)
        """
        # Endpoint from official SDK: PROD_URL['scrip_master'] = 'script-details/1.0/masterscrip/file-paths'
        url = f'{self.LOGIN_BASE_URL}/script-details/1.0/masterscrip/file-paths'
        
        params = {}
        if exchange_segment:
            params['exchange_segment'] = exchange_segment
        
        try:
            response = await self.client.get(
                url,
                params=params,
                headers=self._get_quote_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'data': data, 'raw_response': data}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get scripmaster')}
        except Exception as e:
            logger.error(f'Get scripmaster error: {e}')
            return {'success': False, 'error': str(e)}
    
    async def search_scrip(self, exchange_segment: str, symbol: str = '', 
                          expiry: str = None, option_type: str = None, 
                          strike_price: str = None) -> Dict:
        """
        Search for a scrip in the scripmaster.
        
        Based on official SDK ScripSearch.
        
        Args:
            exchange_segment: nse_cm, bse_cm, nse_fo, bse_fo, cde_fo, mcx_fo (required)
            symbol: Trading symbol to search (optional)
            expiry: Expiry date in YYYYMM format (optional)
            option_type: CE or PE (optional)
            strike_price: Strike price (optional)
        """
        if not exchange_segment:
            return {'success': False, 'error': 'Exchange segment is required'}
        
        # This would typically search through the downloaded scripmaster data
        # For now, return a placeholder
        return {
            'success': True,
            'message': 'Search scrip requires scripmaster data to be downloaded first',
            'params': {
                'exchange_segment': exchange_segment,
                'symbol': symbol,
                'expiry': expiry,
                'option_type': option_type,
                'strike_price': strike_price
            }
        }
    
    # ==================== MARGIN CHECK ====================
    
    async def margin_required(self, order_data: Dict) -> Dict:
        """
        Check margin requirement for an order.
        
        Based on official SDK MarginAPI:
        POST {baseUrl}/quick/user/check-margin
        
        Args:
            order_data: Dict containing:
                - exchange_segment: nse_cm, bse_cm, nse_fo, bse_fo, cde_fo, mcx_fo
                - price: scrip price
                - order_type: L, MKT, SL, SL-M
                - product: NRML, CNC, MIS, CO, BO
                - quantity: number of shares/lots
                - instrument_token: token from scripmaster
                - transaction_type: B or S
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['margin'] = 'quick/user/check-margin'
        url = f'{self.session.base_url}/quick/user/check-margin'
        
        try:
            response = await self.client.post(
                url,
                json=order_data,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {
                    'success': True,
                    'margin_data': data,
                    'raw_response': data
                }
            else:
                return {'success': False, 'error': data.get('message', 'Margin check failed')}
        except Exception as e:
            logger.error(f'Margin check error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== ORDER HISTORY ====================
    
    async def get_order_history(self, order_id: str) -> Dict:
        """
        Get history for a specific order.
        
        Based on official SDK OrderHistoryAPI:
        POST {baseUrl}/quick/order/history
        """
        if not self.session.is_authenticated:
            return {'success': False, 'error': 'Not authenticated'}
        
        if not self.session.base_url:
            return {'success': False, 'error': 'No base URL'}
        
        # Endpoint from official SDK: PROD_URL['order_history'] = 'quick/order/history'
        url = f'{self.session.base_url}/quick/order/history'
        
        body = {'order_id': order_id}
        
        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self._get_auth_headers()
            )
            data = response.json()
            
            if 200 <= response.status_code <= 299:
                return {'success': True, 'history': data.get('data', []), 'raw_response': data}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get order history')}
        except Exception as e:
            logger.error(f'Get order history error: {e}')
            return {'success': False, 'error': str(e)}
    
    # ==================== SESSION MANAGEMENT ====================
    
    def is_authenticated(self) -> bool:
        """Check if the session is authenticated."""
        return self.session.is_authenticated
    
    def get_session_info(self) -> Dict:
        """Get current session information."""
        return {
            'is_authenticated': self.session.is_authenticated,
            'user_id': self.session.user_id,
            'ucc': self.session.ucc,
            'base_url': self.session.base_url,
            'data_center': self.session.data_center,
            'has_view_token': bool(self.session.view_token),
            'has_edit_token': bool(self.session.edit_token)
        }
    
    async def logout(self) -> Dict:
        """
        Logout and clear session data.
        """
        self.session = KotakSession(
            consumer_key=self.consumer_key,
            ucc=self.ucc
        )
        return {'success': True, 'message': 'Logged out successfully'}
