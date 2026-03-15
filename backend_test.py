#!/usr/bin/env python3
"""
Backend API Testing Suite for COSTAR AlgoTrader Options Features
Tests all NEW Options endpoints as specified in the review request
"""
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

class OptionsAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api"
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'COSTAR-Options-Tester/1.0'
        })
        
        self.test_results = []
        
    def log_result(self, endpoint: str, status: str, details: str, response_data: Optional[Dict] = None):
        """Log test result with timestamp"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'status': status,
            'details': details,
            'response_data': response_data
        }
        self.test_results.append(result)
        print(f"[{status}] {endpoint}: {details}")
        
    def test_options_expiries(self) -> bool:
        """Test Options Expiries endpoints for NIFTY and BANKNIFTY"""
        print("\n=== TESTING OPTIONS EXPIRIES ===")
        
        for underlying in ['NIFTY', 'BANKNIFTY']:
            try:
                url = f"{self.api_base}/options/expiries/{underlying}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'expiries' in data:
                        expiries = data['expiries']
                        if len(expiries) >= 4:  # Should return 4 expiry dates
                            self.log_result(
                                f"GET /api/options/expiries/{underlying}",
                                "✅ PASS",
                                f"Returns {len(expiries)} expiry dates as expected",
                                {'expiry_count': len(expiries), 'expiries': expiries[:4]}
                            )
                        else:
                            self.log_result(
                                f"GET /api/options/expiries/{underlying}",
                                "❌ FAIL",
                                f"Expected 4+ expiries, got {len(expiries)}",
                                data
                            )
                            return False
                    else:
                        self.log_result(
                            f"GET /api/options/expiries/{underlying}",
                            "❌ FAIL",
                            "Invalid response structure",
                            data
                        )
                        return False
                else:
                    self.log_result(
                        f"GET /api/options/expiries/{underlying}",
                        "❌ FAIL",
                        f"HTTP {response.status_code}: {response.text[:100]}",
                        {'status_code': response.status_code}
                    )
                    return False
                    
            except Exception as e:
                self.log_result(
                    f"GET /api/options/expiries/{underlying}",
                    "❌ ERROR",
                    f"Exception: {str(e)}",
                    {'error': str(e)}
                )
                return False
        
        return True
    
    def test_options_chain(self) -> bool:
        """Test Options Chain endpoints"""
        print("\n=== TESTING OPTIONS CHAIN ===")
        
        test_cases = [
            {'underlying': 'NIFTY', 'strikes': 10, 'expected_structure': ['spot_price', 'atm_strike', 'pcr', 'calls', 'puts']},
            {'underlying': 'BANKNIFTY', 'strikes': 5, 'expected_structure': ['spot_price', 'atm_strike', 'pcr', 'calls', 'puts']}
        ]
        
        for test_case in test_cases:
            try:
                underlying = test_case['underlying']
                strikes = test_case['strikes']
                url = f"{self.api_base}/options/chain/{underlying}?strikes={strikes}"
                
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        # Check required fields
                        required_fields = test_case['expected_structure']
                        missing_fields = [field for field in required_fields if field not in data]
                        
                        if not missing_fields:
                            # Validate data structure
                            spot_price = data.get('spot_price')
                            atm_strike = data.get('atm_strike')
                            pcr = data.get('pcr')
                            calls = data.get('calls', [])
                            puts = data.get('puts', [])
                            
                            # Validate calls structure
                            calls_valid = True
                            if calls and len(calls) > 0:
                                first_call = calls[0]
                                required_call_fields = ['ltp', 'iv', 'open_interest', 'delta', 'theta']
                                missing_call_fields = [field for field in required_call_fields if field not in first_call]
                                if missing_call_fields:
                                    calls_valid = False
                            
                            # Validate puts structure
                            puts_valid = True
                            if puts and len(puts) > 0:
                                first_put = puts[0]
                                required_put_fields = ['ltp', 'iv', 'open_interest', 'delta', 'theta']
                                missing_put_fields = [field for field in required_put_fields if field not in first_put]
                                if missing_put_fields:
                                    puts_valid = False
                            
                            if calls_valid and puts_valid and isinstance(spot_price, (int, float)) and isinstance(atm_strike, (int, float)) and isinstance(pcr, (int, float)):
                                self.log_result(
                                    f"GET /api/options/chain/{underlying}?strikes={strikes}",
                                    "✅ PASS",
                                    f"Complete chain data: spot={spot_price}, atm={atm_strike}, pcr={pcr}, calls={len(calls)}, puts={len(puts)}",
                                    {
                                        'spot_price': spot_price,
                                        'atm_strike': atm_strike,
                                        'pcr': pcr,
                                        'calls_count': len(calls),
                                        'puts_count': len(puts)
                                    }
                                )
                            else:
                                self.log_result(
                                    f"GET /api/options/chain/{underlying}?strikes={strikes}",
                                    "❌ FAIL",
                                    f"Invalid data structure. Calls valid: {calls_valid}, Puts valid: {puts_valid}",
                                    data
                                )
                                return False
                        else:
                            self.log_result(
                                f"GET /api/options/chain/{underlying}?strikes={strikes}",
                                "❌ FAIL",
                                f"Missing required fields: {missing_fields}",
                                data
                            )
                            return False
                    else:
                        self.log_result(
                            f"GET /api/options/chain/{underlying}?strikes={strikes}",
                            "❌ FAIL",
                            "Success=false in response",
                            data
                        )
                        return False
                else:
                    self.log_result(
                        f"GET /api/options/chain/{underlying}?strikes={strikes}",
                        "❌ FAIL",
                        f"HTTP {response.status_code}: {response.text[:100]}",
                        {'status_code': response.status_code}
                    )
                    return False
                    
            except Exception as e:
                self.log_result(
                    f"GET /api/options/chain/{underlying}?strikes={strikes}",
                    "❌ ERROR",
                    f"Exception: {str(e)}",
                    {'error': str(e)}
                )
                return False
        
        return True
    
    def test_options_signal(self) -> bool:
        """Test Options Signal endpoint"""
        print("\n=== TESTING OPTIONS SIGNAL ===")
        
        try:
            url = f"{self.api_base}/options/signal/NIFTY"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Check required fields
                    required_fields = ['direction', 'confidence', 'pcr', 'support', 'resistance', 'recommendation']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if not missing_fields:
                        direction = data.get('direction')
                        confidence = data.get('confidence')
                        pcr = data.get('pcr')
                        support = data.get('support')
                        resistance = data.get('resistance')
                        recommendation = data.get('recommendation')
                        
                        # Validate direction
                        valid_directions = ['BULLISH', 'BEARISH', 'NEUTRAL']
                        direction_valid = direction in valid_directions
                        
                        # Validate recommendation structure
                        recommendation_valid = isinstance(recommendation, dict) and 'primary' in recommendation
                        
                        if direction_valid and isinstance(confidence, (int, float)) and isinstance(pcr, (int, float)) and recommendation_valid:
                            self.log_result(
                                "GET /api/options/signal/NIFTY",
                                "✅ PASS",
                                f"Signal: {direction}, Confidence: {confidence}, PCR: {pcr}, Support: {support}, Resistance: {resistance}",
                                {
                                    'direction': direction,
                                    'confidence': confidence,
                                    'pcr': pcr,
                                    'support': support,
                                    'resistance': resistance,
                                    'recommendation': recommendation
                                }
                            )
                        else:
                            self.log_result(
                                "GET /api/options/signal/NIFTY",
                                "❌ FAIL",
                                f"Invalid data types. Direction valid: {direction_valid}, Recommendation valid: {recommendation_valid}",
                                data
                            )
                            return False
                    else:
                        self.log_result(
                            "GET /api/options/signal/NIFTY",
                            "❌ FAIL",
                            f"Missing required fields: {missing_fields}",
                            data
                        )
                        return False
                else:
                    self.log_result(
                        "GET /api/options/signal/NIFTY",
                        "❌ FAIL",
                        "Success=false in response",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "GET /api/options/signal/NIFTY",
                    "❌ FAIL",
                    f"HTTP {response.status_code}: {response.text[:100]}",
                    {'status_code': response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_result(
                "GET /api/options/signal/NIFTY",
                "❌ ERROR",
                f"Exception: {str(e)}",
                {'error': str(e)}
            )
            return False
        
        return True
    
    def test_options_quote(self) -> bool:
        """Test Options Quote endpoints"""
        print("\n=== TESTING OPTIONS QUOTE ===")
        
        test_cases = [
            {'underlying': 'NIFTY', 'strike': 24850, 'option_type': 'CE'},
            {'underlying': 'NIFTY', 'strike': 24850, 'option_type': 'PE'}
        ]
        
        for test_case in test_cases:
            try:
                underlying = test_case['underlying']
                strike = test_case['strike']
                option_type = test_case['option_type']
                url = f"{self.api_base}/options/quote/{underlying}/{strike}/{option_type}"
                
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'contract' in data and 'spot_price' in data:
                        contract = data['contract']
                        spot_price = data['spot_price']
                        
                        # Check contract structure
                        if 'strike' in contract and contract['strike'] == strike:
                            self.log_result(
                                f"GET /api/options/quote/{underlying}/{strike}/{option_type}",
                                "✅ PASS",
                                f"Contract details received for {underlying} {strike} {option_type}, spot: {spot_price}",
                                {
                                    'strike': contract.get('strike'),
                                    'ltp': contract.get('ltp'),
                                    'spot_price': spot_price
                                }
                            )
                        else:
                            self.log_result(
                                f"GET /api/options/quote/{underlying}/{strike}/{option_type}",
                                "❌ FAIL",
                                "Invalid contract structure or mismatched strike",
                                data
                            )
                            return False
                    else:
                        self.log_result(
                            f"GET /api/options/quote/{underlying}/{strike}/{option_type}",
                            "❌ FAIL",
                            "Missing contract or spot_price in response",
                            data
                        )
                        return False
                else:
                    self.log_result(
                        f"GET /api/options/quote/{underlying}/{strike}/{option_type}",
                        "❌ FAIL",
                        f"HTTP {response.status_code}: {response.text[:100]}",
                        {'status_code': response.status_code}
                    )
                    return False
                    
            except Exception as e:
                self.log_result(
                    f"GET /api/options/quote/{underlying}/{strike}/{option_type}",
                    "❌ ERROR",
                    f"Exception: {str(e)}",
                    {'error': str(e)}
                )
                return False
        
        return True
    
    def test_options_order(self) -> bool:
        """Test Options Order placement"""
        print("\n=== TESTING OPTIONS ORDER ===")
        
        try:
            order_data = {
                "underlying": "NIFTY",
                "strike": 24850,
                "option_type": "CE",
                "side": "BUY",
                "quantity": 1
            }
            
            url = f"{self.api_base}/options/order"
            response = self.session.post(url, json=order_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'order_id' in data and 'mode' in data:
                    order_id = data.get('order_id')
                    mode = data.get('mode')
                    
                    if mode == "simulation":
                        self.log_result(
                            "POST /api/options/order",
                            "✅ PASS",
                            f"Options order placed successfully. Order ID: {order_id}, Mode: {mode}",
                            {
                                'order_id': order_id,
                                'mode': mode,
                                'details': data.get('details', {})
                            }
                        )
                    else:
                        self.log_result(
                            "POST /api/options/order",
                            "❌ FAIL",
                            f"Unexpected mode: {mode}. Expected simulation",
                            data
                        )
                        return False
                else:
                    self.log_result(
                        "POST /api/options/order",
                        "❌ FAIL",
                        "Missing order_id or mode in response",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/options/order",
                    "❌ FAIL",
                    f"HTTP {response.status_code}: {response.text[:100]}",
                    {'status_code': response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/options/order",
                "❌ ERROR",
                f"Exception: {str(e)}",
                {'error': str(e)}
            )
            return False
        
        return True
    
    def test_websocket_stats(self) -> bool:
        """Test WebSocket Stats endpoint"""
        print("\n=== TESTING WEBSOCKET STATS ===")
        
        try:
            url = f"{self.api_base}/ws/stats"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'stats' in data:
                    stats = data['stats']
                    self.log_result(
                        "GET /api/ws/stats",
                        "✅ PASS",
                        f"WebSocket stats retrieved successfully",
                        {
                            'stats': stats
                        }
                    )
                else:
                    self.log_result(
                        "GET /api/ws/stats",
                        "❌ FAIL",
                        "Missing success or stats in response",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "GET /api/ws/stats",
                    "❌ FAIL",
                    f"HTTP {response.status_code}: {response.text[:100]}",
                    {'status_code': response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_result(
                "GET /api/ws/stats",
                "❌ ERROR",
                f"Exception: {str(e)}",
                {'error': str(e)}
            )
            return False
        
        return True
    
    def run_all_tests(self) -> Dict:
        """Run all options API tests"""
        print("🚀 STARTING COSTAR OPTIONS API TESTING")
        print(f"📡 Target URL: {self.base_url}")
        print("=" * 60)
        
        test_results = {
            'options_expiries': self.test_options_expiries(),
            'options_chain': self.test_options_chain(), 
            'options_signal': self.test_options_signal(),
            'options_quote': self.test_options_quote(),
            'options_order': self.test_options_order(),
            'websocket_stats': self.test_websocket_stats()
        }
        
        passed = sum(test_results.values())
        total = len(test_results)
        
        print("\n" + "=" * 60)
        print("📊 FINAL TEST RESULTS")
        print("=" * 60)
        
        for test_name, passed_test in test_results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            print(f"{status} {test_name}")
        
        print(f"\n🏆 Overall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Options API is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return {
            'total_tests': total,
            'passed_tests': passed,
            'failed_tests': total - passed,
            'success_rate': (passed/total)*100,
            'test_results': test_results,
            'detailed_results': self.test_results
        }

def main():
    """Main testing function"""
    # Use the specific URL from the review request
    base_url = "https://neo-trader-sandbox.preview.emergentagent.com"
    
    tester = OptionsAPITester(base_url)
    results = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/options_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: /app/options_test_results.json")
    return results

if __name__ == "__main__":
    main()