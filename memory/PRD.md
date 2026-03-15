# COSTAR Kotak Neo F&O AlgoTrader - Product Requirements Document

## Original Problem Statement
Build a full-stack algo-trading application for the Kotak NEO platform that provides:
- Real-time market data display with candlestick charts
- 10-indicator confluence signal generation (EMA, RSI, Supertrend, VWAP, MACD, Bollinger, Stochastic, Volume, OBV, Price Action)
- AI-powered signal validation using Claude
- Backtesting capabilities
- Order management and position tracking
- Secure authentication with Kotak NEO (TOTP + MPIN)

## User Personas
1. **Retail F&O Traders** - Need quick signals for index derivatives (NIFTY, BANKNIFTY)
2. **Stock Investors** - Need delivery (CNC) trading capabilities for stocks
3. **Options Traders** - Need options chain analysis, Greeks, and options signal generation
4. **Algorithmic Traders** - Need backtesting and AI validation for strategy refinement

## Core Requirements

### ✅ Completed Features

#### Phase 0: Core Trading Platform (Completed)
- [x] FastAPI backend with all trading endpoints
- [x] React Native / Expo frontend with professional dark theme
- [x] MongoDB integration for data persistence
- [x] Kotak NEO API integration (TOTP + MPIN authentication)
- [x] 10-indicator confluence engine
- [x] Candlestick charting
- [x] Demo mode with market simulation
- [x] Backtesting engine

#### Phase 1: AI Signal Validation (Completed - March 15, 2026)
- [x] Claude AI integration using Emergent LLM Key
- [x] AIValidator class with proper error handling
- [x] Signal validation returns: verdict, quality, confidence, entry_timing, key_risk, adjustment
- [x] Fallback to rule-based validation when AI unavailable

#### Phase 2: Stocks Trading with Signals (Completed - March 15, 2026)
- [x] Added 10 popular stocks: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, TATASTEEL, ITC, WIPRO, AXISBANK
- [x] New API endpoints:
  - GET /api/watchlist/indices - Returns NIFTY, BANKNIFTY (F&O)
  - GET /api/watchlist/stocks - Returns 10 stocks (Cash/CNC)
  - GET /api/stocks/search - Stock search functionality
  - GET /api/instrument/{symbol} - Detailed instrument info
- [x] CNC (Cash-and-Carry) product type support for delivery trading
- [x] Frontend STOCKS tab with watchlist, CNC badges, signal display, order modal

#### Phase 3: Options Chain & Trading (Completed - March 15, 2026)
- [x] Options chain generator using Black-Scholes pricing model approximations
- [x] Options Greeks calculation (Delta, Gamma, Theta, Vega)
- [x] IV Smile modeling for realistic option pricing
- [x] New API endpoints:
  - GET /api/options/expiries/{underlying} - Returns weekly expiry dates
  - GET /api/options/chain/{underlying} - Full options chain with OI, IV, Greeks
  - GET /api/options/signal/{underlying} - PCR-based trading signals
  - GET /api/options/quote/{underlying}/{strike}/{type} - Specific contract quote
  - POST /api/options/order - Options order placement
- [x] Frontend OPTIONS tab with:
  - NIFTY/BANKNIFTY underlying selector
  - Expiry date picker (4 weekly expiries)
  - Chain/Signal view toggle
  - Professional options chain table (Call | Strike | Put format)
  - ATM strike highlighting
  - OI, OI Change, IV, LTP display
  - Order modal with Greeks display and premium calculation

#### Phase 4: Live Price Polling (Completed - March 15, 2026)
- [x] REST-based live price polling (alternative to WebSocket)
- [x] LivePricePoller class with 2-second polling interval
- [x] Auto-starts after MPIN authentication
- [x] Caches NIFTY and BANKNIFTY live prices
- [x] New API endpoints:
  - POST /api/live-prices/start - Start poller
  - POST /api/live-prices/stop - Stop poller
  - GET /api/live-prices/status - Poller statistics
  - GET /api/live-prices/latest - All cached prices
  - GET /api/live-prices/{symbol} - Specific symbol price
- [x] Options chain now uses live spot prices from poller

#### Phase 5: Real Options Data (Completed - March 15, 2026)
- [x] LiveOptionsService for real expiry dates and option prices
- [x] Fetches/calculates real weekly expiry dates (Thursdays)
- [x] Generates correct Kotak option symbols (e.g., NIFTY20MAR23500CE)
- [x] Attempts live option quotes via Kotak Quotes API
- [x] Updated API endpoints:
  - GET /api/options/expiries/{underlying} - Returns real expiries with source indicator
  - GET /api/options/chain/{underlying} - Full chain with is_live indicator
- [x] Auto-refresh UI feature:
  - Options chain refreshes every 5 seconds automatically
  - Live indicator shows LIVE/SIMULATED status
  - Toggle button to enable/disable auto-refresh
  - Last refresh timestamp display

### ⚠️ Known Limitations

#### HSM WebSocket Not Available from EC2
- Kotak's HSM WebSocket server (`wstreamer.kotaksecurities.com`) is not reachable from AWS EC2
- Connection times out at TCP level (likely IP block on financial data streams)
- **Workaround**: REST-based polling implemented as alternative (2-second interval)

#### Options Chain Data - Partial Live
- Expiry dates now use calculated Thursdays (correct for NSE weekly expiry)
- Spot price uses LIVE data from price poller
- Option prices attempt live quotes but may fall back to Black-Scholes simulation
- OI and Greeks are simulated when live data unavailable
- **Note**: Response includes `is_live` field to indicate data source

### 🔮 Future Tasks

#### P1: Full Live Option Prices
- [ ] Subscribe to individual option contracts via Kotak Quotes API
- [ ] Cache and refresh option prices periodically
- [ ] Display real OI and volume data

#### P2: Enhanced UI (Phase 6)
- [ ] Mobile-first UI optimization
- [ ] Advanced charting features (drawing tools, indicators overlay)
- [ ] Watchlist customization

#### P3: Production Deployment Enhancements
- [ ] Custom domain with SSL (HTTPS)
- [ ] Performance optimization
- [ ] Rate limiting and security hardening

## Technical Architecture

### Backend (Python/FastAPI)
```
/app/backend/
├── server.py              # Main FastAPI app with all routes
├── kotak_api.py           # Kotak NEO API client (v2)
├── ai_validator.py        # Claude AI signal validation
├── confluence.py          # 10-indicator scoring engine
├── indicators.py          # Technical indicators
├── simulator.py           # Market data simulation
├── backtester.py          # Strategy backtesting
├── options_chain.py       # Options chain generator (simulated)
├── websocket_manager.py   # WebSocket connection manager
├── live_price_poller.py   # NEW: REST-based live price polling
├── kotak_hsm.py          # HSM WebSocket client (not working from EC2)
├── kotak_scrip_master.py # Scrip master fetcher
└── requirements.txt
```

### Frontend (React Native/Expo)
```
/app/frontend/
├── app/
│   └── index.tsx      # Main dashboard with tabs
├── src/
│   ├── components/
│   │   ├── StocksTab.tsx         # Stocks trading tab
│   │   ├── OptionsTab.tsx        # Options trading tab
│   │   ├── CandlestickChart.tsx
│   │   ├── ConfluenceGauge.tsx
│   │   ├── AIValidationPanel.tsx
│   │   └── ...
│   ├── store/
│   │   └── tradingStore.ts       # Zustand state management
│   └── theme/
│       └── colors.ts
└── package.json
```

### Key API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/health | GET | Health check |
| /api/auth/totp | POST | TOTP authentication |
| /api/auth/mpin | POST | MPIN authentication |
| /api/auth/status | GET | Auth status with session info |
| /api/live-prices/status | GET | Live poller statistics |
| /api/live-prices/latest | GET | All cached live prices |
| /api/live-prices/{symbol} | GET | Live price for symbol |
| /api/watchlist | GET | All 12 instruments |
| /api/watchlist/indices | GET | NIFTY, BANKNIFTY |
| /api/watchlist/stocks | GET | 10 stocks for CNC |
| /api/stocks/search | GET | Search stocks |
| /api/signal/{symbol} | GET | Get trading signal |
| /api/options/expiries/{underlying} | GET | Options expiry dates |
| /api/options/chain/{underlying} | GET | Full options chain |
| /api/options/signal/{underlying} | GET | PCR-based signal |
| /api/options/order | POST | Place options order |
| /api/market/quote/{symbol} | GET | Current quote |
| /api/market/candles/{symbol} | GET | OHLCV candles |
| /api/orders/place | POST | Place order |
| /api/positions | GET | Open positions |
| /api/orders | GET | Order book |
| /api/backtest | POST | Run backtest |

### Database
- **Database**: MongoDB
- **Database Name**: algo_trader
- **Collections**: trades, backtest_results (implicit)

## Environment Variables
```
# Backend (.env)
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
EMERGENT_LLM_KEY="sk-emergent-xxx"
KOTAK_ACCESS_TOKEN="xxx"
KOTAK_MOBILE="+91xxx"
KOTAK_UCC="XCB4O"

# Frontend (.env)
EXPO_PUBLIC_BACKEND_URL="https://options-chain.preview.emergentagent.com"
```

## Deployment
- **Preview Environment**: https://options-chain.preview.emergentagent.com
- **Production (AWS EC2)**: http://51.20.66.73 (user's EC2 instance)
  - Backend: pm2 managed, port 8001
  - Frontend: Nginx serving static build
  - Python venv: /home/ubuntu/Kotak-Neo/backend/venv/

## Testing Status
- Backend: All tests passed (100%)
- Frontend: All flows tested successfully
- Demo mode: Fully functional
- Live trading: Authentication working, live prices polling working
- HSM WebSocket: NOT WORKING from EC2 (network block)

## Last Updated
March 15, 2026
