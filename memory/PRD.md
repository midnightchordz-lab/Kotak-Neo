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

#### Phase 4: WebSocket Integration (Completed - March 15, 2026)
- [x] WebSocket connection manager for real-time streaming
- [x] Subscription system for quotes, signals, options, positions, orders
- [x] Background broadcast task for live data updates
- [x] WebSocket endpoint: /ws
- [x] Stats endpoint: GET /api/ws/stats
- [x] Notification broadcasting support

### 🔮 Future Tasks

#### P3: Enhanced UI (Phase 5)
- [ ] Mobile-first UI optimization
- [ ] Advanced charting features (drawing tools, indicators overlay)
- [ ] Watchlist customization

#### P4: Production Deployment Enhancements
- [ ] Custom domain with SSL (HTTPS)
- [ ] Performance optimization
- [ ] Rate limiting and security hardening

## Technical Architecture

### Backend (Python/FastAPI)
```
/app/backend/
├── server.py          # Main FastAPI app with all routes (~1000 lines)
├── kotak_api.py       # Kotak NEO API client (v2)
├── ai_validator.py    # Claude AI signal validation
├── confluence.py      # 10-indicator scoring engine
├── indicators.py      # Technical indicators
├── simulator.py       # Market data simulation
├── backtester.py      # Strategy backtesting
├── options_chain.py   # NEW: Options chain generator
├── websocket_manager.py # NEW: WebSocket connection manager
└── requirements.txt
```

### Frontend (React Native/Expo)
```
/app/frontend/
├── app/
│   └── index.tsx      # Main dashboard with 6 tabs
├── src/
│   ├── components/
│   │   ├── StocksTab.tsx         # Stocks trading tab
│   │   ├── OptionsTab.tsx        # NEW: Options trading tab
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
| /api/watchlist | GET | All 12 instruments |
| /api/watchlist/indices | GET | NIFTY, BANKNIFTY |
| /api/watchlist/stocks | GET | 10 stocks for CNC |
| /api/stocks/search | GET | Search stocks |
| /api/signal/{symbol} | GET | Get trading signal |
| /api/options/expiries/{underlying} | GET | Options expiry dates |
| /api/options/chain/{underlying} | GET | Full options chain |
| /api/options/signal/{underlying} | GET | PCR-based signal |
| /api/options/order | POST | Place options order |
| /ws | WebSocket | Real-time streaming |
| /api/ws/stats | GET | WebSocket statistics |
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
- **Production (AWS EC2)**: http://ec2-51-20-66-73.eu-north-1.compute.amazonaws.com

## Testing Status
- Backend: All tests passed (100%)
- Frontend: All flows tested successfully
- Demo mode: Fully functional
- Live trading: Authentication working (requires user credentials)

## Last Updated
March 15, 2026
