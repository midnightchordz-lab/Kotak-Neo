#!/usr/bin/env python3
"""
COSTAR AlgoTrader Backend API Comprehensive Test Suite
Tests all backend endpoints against the specifications
"""

import requests
import json
import time
from typing import Dict, Any, List

# Base URL from frontend/.env
BASE_URL = "https://neo-trader-sandbox.preview.emergentagent.com/api"

class COSTARTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, details: str = "", expected: Any = None, actual: Any = None):
        """Log test result"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'expected': expected,
            'actual': actual,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        
    def make_request(self, method: str, endpoint: str, **kwargs) -> tuple:
        """Make HTTP request and return (success, response, error)"""
        try:
            url = f"{BASE_URL}{endpoint}"
            response = self.session.request(method, url, timeout=30, **kwargs)
            return True, response, None
        except Exception as e:
            return False, None, str(e)
    
    def test_health_check(self):
        """Test 1: Health Check API"""
        print("\n🔍 Testing Health Check API...")
        
        success, response, error = self.make_request("GET", "/health")
        
        if not success:
            self.log_result("Health Check", False, f"Request failed: {error}")
            return
            
        if response.status_code != 200:
            self.log_result("Health Check", False, f"HTTP {response.status_code}: {response.text}")
            return
            
        try:
            data = response.json()
            if data.get('status') == 'healthy':
                self.log_result("Health Check", True, "Returns healthy status", 
                              {"status": "healthy"}, data.get('status'))
            else:
                self.log_result("Health Check", False, "Status not healthy", 
                              "healthy", data.get('status'))
        except json.JSONDecodeError:
            self.log_result("Health Check", False, "Invalid JSON response")
    
    def test_watchlist_endpoints(self):
        """Test 2: Watchlist Endpoints"""
        print("\n🔍 Testing Watchlist Endpoints...")
        
        # Test main watchlist (should return 12 instruments)
        success, response, error = self.make_request("GET", "/watchlist")
        
        if not success:
            self.log_result("Watchlist All", False, f"Request failed: {error}")
            return
            
        if response.status_code != 200:
            self.log_result("Watchlist All", False, f"HTTP {response.status_code}: {response.text}")
            return
            
        try:
            data = response.json()
            watchlist = data.get('watchlist', [])
            
            if len(watchlist) == 12:
                # Count indices vs stocks
                indices = [item for item in watchlist if item.get('segment') == 'nse_fo']
                stocks = [item for item in watchlist if item.get('segment') == 'nse_cm']
                
                self.log_result("Watchlist All", True, 
                              f"Returns 12 instruments ({len(indices)} indices, {len(stocks)} stocks)",
                              12, len(watchlist))
            else:
                self.log_result("Watchlist All", False, 
                              f"Expected 12 instruments, got {len(watchlist)}",
                              12, len(watchlist))
                
        except json.JSONDecodeError:
            self.log_result("Watchlist All", False, "Invalid JSON response")
        
        # Test indices watchlist
        success, response, error = self.make_request("GET", "/watchlist/indices")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                indices = data.get('watchlist', [])
                
                expected_symbols = {'NIFTY', 'BANKNIFTY'}
                actual_symbols = {item.get('symbol') for item in indices}
                
                if len(indices) == 2 and actual_symbols == expected_symbols:
                    # Check segment
                    all_nse_fo = all(item.get('segment') == 'nse_fo' for item in indices)
                    if all_nse_fo:
                        self.log_result("Watchlist Indices", True, 
                                      "Returns NIFTY and BANKNIFTY with segment=nse_fo",
                                      expected_symbols, actual_symbols)
                    else:
                        self.log_result("Watchlist Indices", False, 
                                      "Not all indices have segment=nse_fo")
                else:
                    self.log_result("Watchlist Indices", False, 
                                  f"Expected NIFTY+BANKNIFTY, got {actual_symbols}",
                                  expected_symbols, actual_symbols)
            except json.JSONDecodeError:
                self.log_result("Watchlist Indices", False, "Invalid JSON response")
        else:
            self.log_result("Watchlist Indices", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Test stocks watchlist  
        success, response, error = self.make_request("GET", "/watchlist/stocks")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                stocks = data.get('watchlist', [])
                
                if len(stocks) == 10:
                    # Check segment and product_type
                    all_nse_cm = all(item.get('segment') == 'nse_cm' for item in stocks)
                    all_cnc = all(item.get('product_type') == 'CNC' for item in stocks)
                    
                    if all_nse_cm and all_cnc:
                        self.log_result("Watchlist Stocks", True, 
                                      "Returns 10 stocks with segment=nse_cm and product_type=CNC",
                                      10, len(stocks))
                    else:
                        self.log_result("Watchlist Stocks", False, 
                                      "Not all stocks have correct segment/product_type")
                else:
                    self.log_result("Watchlist Stocks", False, 
                                  f"Expected 10 stocks, got {len(stocks)}",
                                  10, len(stocks))
            except json.JSONDecodeError:
                self.log_result("Watchlist Stocks", False, "Invalid JSON response")
        else:
            self.log_result("Watchlist Stocks", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_stock_search(self):
        """Test 3: Stock Search API"""
        print("\n🔍 Testing Stock Search API...")
        
        # Test search without query (should return all 10 stocks)
        success, response, error = self.make_request("GET", "/stocks/search")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                results = data.get('results', [])
                
                if len(results) == 10:
                    self.log_result("Stock Search (All)", True, 
                                  "Returns all 10 stocks when no query",
                                  10, len(results))
                else:
                    self.log_result("Stock Search (All)", False, 
                                  f"Expected 10 stocks, got {len(results)}",
                                  10, len(results))
            except json.JSONDecodeError:
                self.log_result("Stock Search (All)", False, "Invalid JSON response")
        else:
            self.log_result("Stock Search (All)", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Test search with HDFC query
        success, response, error = self.make_request("GET", "/stocks/search?query=HDFC")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                results = data.get('results', [])
                
                # Should find HDFCBANK
                hdfc_symbols = [r.get('symbol') for r in results if 'HDFC' in r.get('symbol', '')]
                
                if 'HDFCBANK' in hdfc_symbols:
                    self.log_result("Stock Search (HDFC)", True, 
                                  f"Returns matching stocks: {hdfc_symbols}")
                else:
                    self.log_result("Stock Search (HDFC)", False, 
                                  f"Expected HDFCBANK in results, got: {hdfc_symbols}")
            except json.JSONDecodeError:
                self.log_result("Stock Search (HDFC)", False, "Invalid JSON response")
        else:
            self.log_result("Stock Search (HDFC)", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_instrument_details(self):
        """Test 4: Instrument Details API"""
        print("\n🔍 Testing Instrument Details API...")
        
        # Test RELIANCE (stock)
        success, response, error = self.make_request("GET", "/instrument/RELIANCE")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                instrument = data.get('instrument', {})
                
                if instrument.get('segment') == 'nse_cm':
                    self.log_result("Instrument RELIANCE", True, 
                                  "Returns stock details with segment=nse_cm",
                                  "nse_cm", instrument.get('segment'))
                else:
                    self.log_result("Instrument RELIANCE", False, 
                                  f"Expected segment=nse_cm, got {instrument.get('segment')}",
                                  "nse_cm", instrument.get('segment'))
            except json.JSONDecodeError:
                self.log_result("Instrument RELIANCE", False, "Invalid JSON response")
        else:
            self.log_result("Instrument RELIANCE", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Test NIFTY (index)
        success, response, error = self.make_request("GET", "/instrument/NIFTY")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                instrument = data.get('instrument', {})
                
                if instrument.get('segment') == 'nse_fo':
                    self.log_result("Instrument NIFTY", True, 
                                  "Returns index details with segment=nse_fo",
                                  "nse_fo", instrument.get('segment'))
                else:
                    self.log_result("Instrument NIFTY", False, 
                                  f"Expected segment=nse_fo, got {instrument.get('segment')}",
                                  "nse_fo", instrument.get('segment'))
            except json.JSONDecodeError:
                self.log_result("Instrument NIFTY", False, "Invalid JSON response")
        else:
            self.log_result("Instrument NIFTY", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_signal_generation(self):
        """Test 5: Signal Generation API"""
        print("\n🔍 Testing Signal Generation API...")
        
        # Test signals for different instruments
        test_symbols = ['RELIANCE', 'TCS', 'NIFTY']
        
        for symbol in test_symbols:
            success, response, error = self.make_request("GET", f"/signal/{symbol}")
            
            if success and response.status_code == 200:
                try:
                    data = response.json()
                    
                    required_fields = ['direction', 'score', 'confidence', 'votes']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if not missing_fields:
                        # Check votes structure
                        votes = data.get('votes', [])
                        vote_structure_valid = all(
                            isinstance(vote, dict) and 
                            'name' in vote and 
                            'vote' in vote and 
                            'weight' in vote and
                            'detail' in vote
                            for vote in votes
                        )
                        
                        if vote_structure_valid:
                            self.log_result(f"Signal {symbol}", True, 
                                          f"Returns signal with direction={data.get('direction')}, score={data.get('score')}, confidence={data.get('confidence')}, votes={len(votes)}")
                        else:
                            self.log_result(f"Signal {symbol}", False, 
                                          "Invalid vote structure in response")
                    else:
                        self.log_result(f"Signal {symbol}", False, 
                                      f"Missing required fields: {missing_fields}")
                except json.JSONDecodeError:
                    self.log_result(f"Signal {symbol}", False, "Invalid JSON response")
            else:
                self.log_result(f"Signal {symbol}", False, 
                              f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_market_data(self):
        """Test 6: Market Data APIs"""
        print("\n🔍 Testing Market Data APIs...")
        
        # Test market quote
        success, response, error = self.make_request("GET", "/market/quote/RELIANCE")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                quote = data.get('quote', {})
                
                required_fields = ['ltp', 'change']
                missing_fields = [f for f in required_fields if f not in quote]
                
                if not missing_fields:
                    self.log_result("Market Quote", True, 
                                  f"Returns quote with ltp={quote.get('ltp')}, change={quote.get('change')}")
                else:
                    self.log_result("Market Quote", False, 
                                  f"Missing required fields: {missing_fields}")
            except json.JSONDecodeError:
                self.log_result("Market Quote", False, "Invalid JSON response")
        else:
            self.log_result("Market Quote", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Test market candles
        success, response, error = self.make_request("GET", "/market/candles/RELIANCE")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                candles = data.get('candles', [])
                
                if len(candles) > 0:
                    # Check candle structure
                    candle = candles[0]
                    required_fields = ['open', 'high', 'low', 'close', 'volume']
                    missing_fields = [f for f in required_fields if f not in candle]
                    
                    if not missing_fields:
                        self.log_result("Market Candles", True, 
                                      f"Returns candles array with {len(candles)} candles")
                    else:
                        self.log_result("Market Candles", False, 
                                      f"Candle missing required fields: {missing_fields}")
                else:
                    self.log_result("Market Candles", False, "Empty candles array")
            except json.JSONDecodeError:
                self.log_result("Market Candles", False, "Invalid JSON response")
        else:
            self.log_result("Market Candles", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_order_placement(self):
        """Test 7: Order Placement API (Demo Mode)"""
        print("\n🔍 Testing Order Placement API...")
        
        order_data = {
            "symbol": "RELIANCE",
            "side": "BUY",
            "quantity": 10,
            "order_type": "MKT",
            "product_type": "CNC"
        }
        
        success, response, error = self.make_request("POST", "/orders/place", 
                                                   json=order_data)
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                
                required_fields = ['order_id', 'mode']
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    if data.get('mode') == 'simulation':
                        self.log_result("Order Placement", True, 
                                      f"Returns order_id={data.get('order_id')} and mode=simulation")
                    else:
                        self.log_result("Order Placement", False, 
                                      f"Expected mode=simulation, got {data.get('mode')}",
                                      "simulation", data.get('mode'))
                else:
                    self.log_result("Order Placement", False, 
                                  f"Missing required fields: {missing_fields}")
            except json.JSONDecodeError:
                self.log_result("Order Placement", False, "Invalid JSON response")
        else:
            self.log_result("Order Placement", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def test_simulation_control(self):
        """Test 8: Simulation Control APIs"""
        print("\n🔍 Testing Simulation Control APIs...")
        
        # Test start simulation
        success, response, error = self.make_request("POST", "/simulation/start")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                if "started" in data.get('message', '').lower():
                    self.log_result("Simulation Start", True, "Simulation started successfully")
                else:
                    self.log_result("Simulation Start", True, f"Message: {data.get('message')}")
            except json.JSONDecodeError:
                self.log_result("Simulation Start", False, "Invalid JSON response")
        else:
            self.log_result("Simulation Start", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Wait a moment for simulation to start
        time.sleep(1)
        
        # Test simulation status
        success, response, error = self.make_request("GET", "/simulation/status")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                if data.get('active') == True:
                    self.log_result("Simulation Status", True, "Shows active=true")
                else:
                    self.log_result("Simulation Status", False, 
                                  f"Expected active=true, got {data.get('active')}")
            except json.JSONDecodeError:
                self.log_result("Simulation Status", False, "Invalid JSON response")
        else:
            self.log_result("Simulation Status", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
        
        # Test stop simulation
        success, response, error = self.make_request("POST", "/simulation/stop")
        
        if success and response.status_code == 200:
            try:
                data = response.json()
                if "stopped" in data.get('message', '').lower():
                    self.log_result("Simulation Stop", True, "Simulation stopped successfully")
                else:
                    self.log_result("Simulation Stop", True, f"Message: {data.get('message')}")
            except json.JSONDecodeError:
                self.log_result("Simulation Stop", False, "Invalid JSON response")
        else:
            self.log_result("Simulation Stop", False, 
                          f"Request failed: {error or f'HTTP {response.status_code}'}")
    
    def run_comprehensive_test(self):
        """Run all tests"""
        print("🚀 Starting COSTAR AlgoTrader Backend API Comprehensive Test")
        print("=" * 60)
        
        # Run all tests
        self.test_health_check()
        self.test_watchlist_endpoints()
        self.test_stock_search()
        self.test_instrument_details()
        self.test_signal_generation()
        self.test_market_data()
        self.test_order_placement()
        self.test_simulation_control()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = len([r for r in self.test_results if r['success']])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        # Show failures
        failures = [r for r in self.test_results if not r['success']]
        if failures:
            print("\n❌ FAILED TESTS:")
            for failure in failures:
                print(f"  - {failure['test']}: {failure['details']}")
        
        return passed == total

if __name__ == "__main__":
    tester = COSTARTester()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 ALL TESTS PASSED! Backend APIs are working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
        exit(1)