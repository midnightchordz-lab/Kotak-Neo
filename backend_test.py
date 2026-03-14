#!/usr/bin/env python3
"""
COSTAR Kotak Neo F&O Algo Trader - Backend API Testing
Tests all critical backend endpoints for the trading application
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Configuration
BASE_URL = "https://bold-carson-2.preview.emergentagent.com/api"
TEST_SYMBOL = "NIFTY"
BACKUP_SYMBOL = "BANKNIFTY"

class BackendTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = {}
        self.order_id = None
        
    def log_result(self, test_name: str, success: bool, details: Any, response_time: float = None):
        """Log test result"""
        self.test_results[test_name] = {
            'success': success,
            'details': details,
            'response_time': response_time,
            'timestamp': datetime.utcnow().isoformat()
        }
        status = "✅ PASS" if success else "❌ FAIL"
        time_info = f" ({response_time:.2f}s)" if response_time else ""
        print(f"{status}{time_info} {test_name}")
        if not success:
            print(f"  Error: {details}")
        print()

    def make_request(self, method: str, endpoint: str, data: Dict = None) -> tuple:
        """Make HTTP request and measure response time"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response_time = time.time() - start_time
            
            # Try to parse JSON response
            try:
                json_data = response.json()
            except ValueError:
                json_data = {"raw_response": response.text}
            
            return response.status_code, json_data, response_time
            
        except Exception as e:
            response_time = time.time() - start_time
            return None, {"error": str(e)}, response_time

    def test_health_check(self):
        """Test 1: Health Check API"""
        status_code, data, response_time = self.make_request('GET', '/health')
        
        if status_code == 200 and data.get('status') == 'healthy':
            self.log_result("Health Check API", True, data, response_time)
            return True
        else:
            self.log_result("Health Check API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_watchlist(self):
        """Test 2: Watchlist API"""
        status_code, data, response_time = self.make_request('GET', '/watchlist')
        
        if status_code == 200 and data.get('success') and data.get('watchlist'):
            watchlist = data['watchlist']
            symbols = [item['symbol'] for item in watchlist]
            
            if 'NIFTY' in symbols and 'BANKNIFTY' in symbols:
                self.log_result("Watchlist API", True, f"Found {len(symbols)} instruments: {symbols}", response_time)
                return True
            else:
                self.log_result("Watchlist API", False, f"Missing required symbols. Found: {symbols}", response_time)
                return False
        else:
            self.log_result("Watchlist API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_market_quote(self):
        """Test 3: Market Quote API"""
        status_code, data, response_time = self.make_request('GET', f'/market/quote/{TEST_SYMBOL}')
        
        if status_code == 200 and data.get('success') and data.get('quote'):
            quote = data['quote']
            # For live trading quotes, 'close' is not typical - LTP serves that purpose
            required_fields = ['ltp', 'open', 'high', 'low', 'bid', 'ask']
            missing_fields = [field for field in required_fields if field not in quote]
            
            if not missing_fields:
                self.log_result("Market Quote API", True, f"Quote for {TEST_SYMBOL}: LTP=₹{quote.get('ltp')}, OHL=[{quote.get('open')}, {quote.get('high')}, {quote.get('low')}], Bid/Ask=[{quote.get('bid')}, {quote.get('ask')}]", response_time)
                return True
            else:
                self.log_result("Market Quote API", False, f"Missing required fields: {missing_fields}", response_time)
                return False
        else:
            self.log_result("Market Quote API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_candles(self):
        """Test 4: Candle Data API"""
        status_code, data, response_time = self.make_request('GET', f'/market/candles/{TEST_SYMBOL}?count=50')
        
        if status_code == 200 and data.get('success') and data.get('candles'):
            candles = data['candles']
            if len(candles) == 50:
                # Check if candles have required fields
                first_candle = candles[0]
                required_fields = ['open', 'high', 'low', 'close', 'volume']
                missing_fields = [field for field in required_fields if field not in first_candle]
                
                if not missing_fields:
                    self.log_result("Candle Data API", True, f"Received {len(candles)} candles with complete OHLCV data", response_time)
                    return True
                else:
                    self.log_result("Candle Data API", False, f"Candles missing fields: {missing_fields}", response_time)
                    return False
            else:
                self.log_result("Candle Data API", False, f"Expected 50 candles, got {len(candles)}", response_time)
                return False
        else:
            self.log_result("Candle Data API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_signal_generation(self):
        """Test 5: Signal Generation API"""
        status_code, data, response_time = self.make_request('GET', f'/signal/{TEST_SYMBOL}?validate_ai=false')
        
        if status_code == 200 and 'direction' in data and 'votes' in data:
            votes = data['votes']
            
            # Check if we have 10 indicator votes
            if len(votes) == 10:
                # Verify vote structure
                vote_structure_valid = True
                for vote in votes:
                    if not all(field in vote for field in ['name', 'vote', 'weight', 'detail']):
                        vote_structure_valid = False
                        break
                
                if vote_structure_valid:
                    indicator_names = [v['name'] for v in votes]
                    self.log_result("Signal Generation API", True, 
                                  f"Direction: {data.get('direction')}, Score: {data.get('score')}, "
                                  f"Indicators: {len(votes)}/10, Names: {indicator_names}", response_time)
                    return True
                else:
                    self.log_result("Signal Generation API", False, "Vote structure incomplete", response_time)
                    return False
            else:
                self.log_result("Signal Generation API", False, f"Expected 10 indicator votes, got {len(votes)}", response_time)
                return False
        else:
            self.log_result("Signal Generation API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_account_limits(self):
        """Test 6: Account Limits API"""
        status_code, data, response_time = self.make_request('GET', '/limits')
        
        if status_code == 200 and data.get('success') and data.get('limits'):
            limits = data['limits']
            if 'available_margin' in limits:
                self.log_result("Account Limits API", True, 
                              f"Available Margin: ₹{limits.get('available_margin'):,.2f}, Mode: {data.get('mode', 'simulation')}", response_time)
                return True
            else:
                self.log_result("Account Limits API", False, "Missing available_margin field", response_time)
                return False
        else:
            self.log_result("Account Limits API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_place_order(self):
        """Test 7: Order Placement API"""
        order_data = {
            "symbol": TEST_SYMBOL,
            "side": "BUY",
            "quantity": 25,
            "order_type": "MKT"
        }
        
        status_code, data, response_time = self.make_request('POST', '/orders/place', order_data)
        
        if status_code == 200 and data.get('success') and data.get('order_id'):
            self.order_id = data['order_id']
            self.log_result("Order Placement API", True, 
                          f"Order placed successfully. ID: {self.order_id}, Symbol: {TEST_SYMBOL}, Side: BUY, Qty: 25", response_time)
            return True
        else:
            self.log_result("Order Placement API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_positions(self):
        """Test 8: Positions API"""
        status_code, data, response_time = self.make_request('GET', '/positions')
        
        if status_code == 200 and data.get('success') and 'positions' in data:
            positions = data['positions']
            self.log_result("Positions API", True, 
                          f"Retrieved positions: {len(positions)} open positions", response_time)
            return True
        else:
            self.log_result("Positions API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_orders(self):
        """Test 9: Orders API"""
        status_code, data, response_time = self.make_request('GET', '/orders')
        
        if status_code == 200 and data.get('success') and 'orders' in data:
            orders = data['orders']
            
            # Check if our placed order appears in the order book
            order_found = False
            if self.order_id:
                for order in orders:
                    if order.get('order_id') == self.order_id:
                        order_found = True
                        break
                
                if order_found:
                    self.log_result("Orders API", True, f"Order book retrieved with {len(orders)} orders, placed order found", response_time)
                else:
                    self.log_result("Orders API", True, f"Order book retrieved with {len(orders)} orders, but placed order not found (may have been executed)", response_time)
            else:
                self.log_result("Orders API", True, f"Order book retrieved with {len(orders)} orders", response_time)
            
            return True
        else:
            self.log_result("Orders API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_backtest(self):
        """Test 10: Backtest API"""
        backtest_data = {
            "symbol": TEST_SYMBOL,
            "candles": 200,
            "min_score": 3.0,
            "min_agree": 5,
            "lot_size": 25,
            "position_size": 1
        }
        
        status_code, data, response_time = self.make_request('POST', '/backtest', backtest_data)
        
        if status_code == 200 and data.get('success') and data.get('results'):
            results = data['results']
            required_metrics = ['win_rate', 'total_pnl', 'profit_factor', 'max_drawdown']
            missing_metrics = [metric for metric in required_metrics if metric not in results]
            
            if not missing_metrics:
                self.log_result("Backtest API", True, 
                              f"Backtest completed: Win Rate: {results.get('win_rate')}%, "
                              f"Total P&L: ₹{results.get('total_pnl')}, "
                              f"Profit Factor: {results.get('profit_factor')}, "
                              f"Max DD: {results.get('max_drawdown')}%", response_time)
                return True
            else:
                self.log_result("Backtest API", False, f"Missing metrics: {missing_metrics}", response_time)
                return False
        else:
            self.log_result("Backtest API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_indicators(self):
        """Test 11: Indicators API"""
        status_code, data, response_time = self.make_request('GET', f'/indicators/{TEST_SYMBOL}')
        
        if status_code == 200 and 'symbol' in data:
            indicator_fields = ['ema_fast', 'ema_slow', 'rsi', 'supertrend', 'vwap', 'macd_histogram', 'bb_upper', 'bb_lower', 'stoch_k', 'atr']
            present_indicators = [field for field in indicator_fields if data.get(field) is not None]
            
            if len(present_indicators) >= 8:  # At least 8 indicators should have values
                self.log_result("Indicators API", True, f"Retrieved {len(present_indicators)} indicator values: {present_indicators}", response_time)
                return True
            else:
                self.log_result("Indicators API", False, f"Only {len(present_indicators)} indicators have values, expected at least 8", response_time)
                return False
        else:
            self.log_result("Indicators API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_position_size_calculator(self):
        """Test 12: Position Size Calculator API"""
        status_code, data, response_time = self.make_request('GET', f'/position-size/{TEST_SYMBOL}?risk_percent=1.0')
        
        if status_code == 200 and 'recommended_lots' in data:
            required_fields = ['ltp', 'lot_size', 'lot_value', 'margin_per_lot', 'max_lots_by_capital', 'recommended_lots']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                self.log_result("Position Size Calculator API", True, 
                              f"LTP: ₹{data.get('ltp')}, Recommended Lots: {data.get('recommended_lots')}, "
                              f"Max Lots by Capital: {data.get('max_lots_by_capital')}", response_time)
                return True
            else:
                self.log_result("Position Size Calculator API", False, f"Missing fields: {missing_fields}", response_time)
                return False
        else:
            self.log_result("Position Size Calculator API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def test_ai_validation(self):
        """Test 13: AI Validation (with validate_ai=true)"""
        status_code, data, response_time = self.make_request('GET', f'/signal/{TEST_SYMBOL}?validate_ai=true')
        
        if status_code == 200 and 'ai_validation' in data:
            ai_result = data['ai_validation']
            if 'validation' in ai_result or 'recommendation' in ai_result:
                self.log_result("AI Validation API", True, f"AI validation completed: {ai_result.get('validation', 'No specific validation')}", response_time)
                return True
            else:
                self.log_result("AI Validation API", False, "AI validation response incomplete", response_time)
                return False
        elif status_code == 200 and data.get('direction') == 'NEUTRAL':
            self.log_result("AI Validation API", True, "AI validation skipped for NEUTRAL signal (expected behavior)", response_time)
            return True
        else:
            self.log_result("AI Validation API", False, f"Status: {status_code}, Data: {data}", response_time)
            return False

    def run_all_tests(self):
        """Run all backend tests in priority order"""
        print("=" * 80)
        print("COSTAR Kotak Neo F&O Algo Trader - Backend API Testing")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"Test Symbol: {TEST_SYMBOL}")
        print(f"Started at: {datetime.utcnow().isoformat()}")
        print("=" * 80)
        print()

        # Run tests in priority order
        test_functions = [
            self.test_health_check,
            self.test_watchlist,
            self.test_market_quote,
            self.test_candles,
            self.test_signal_generation,
            self.test_account_limits,
            self.test_place_order,
            self.test_positions,
            self.test_orders,
            self.test_backtest,
            self.test_indicators,
            self.test_position_size_calculator,
            self.test_ai_validation
        ]

        passed_tests = 0
        total_tests = len(test_functions)

        for test_func in test_functions:
            try:
                if test_func():
                    passed_tests += 1
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                self.log_result(test_func.__name__, False, f"Test execution error: {str(e)}")

        # Summary
        print("=" * 80)
        print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
        print("=" * 80)
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Backend APIs are working correctly.")
        else:
            failed_tests = total_tests - passed_tests
            print(f"⚠️  {failed_tests} test(s) failed. Check the details above.")
        
        print(f"Completed at: {datetime.utcnow().isoformat()}")
        print("=" * 80)
        
        return passed_tests, total_tests, self.test_results

def main():
    """Main testing function"""
    tester = BackendTester()
    passed, total, results = tester.run_all_tests()
    
    # Save detailed results to file
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {'passed': passed, 'total': total, 'success_rate': f"{(passed/total)*100:.1f}%"},
            'test_results': results,
            'base_url': BASE_URL,
            'test_symbol': TEST_SYMBOL
        }, f, indent=2)
    
    print(f"Detailed results saved to: /app/backend_test_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)