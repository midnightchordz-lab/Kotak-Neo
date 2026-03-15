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
3. **Algorithmic Traders** - Need backtesting and AI validation for strategy refinement

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
- [x] Fallback to default validation when AI unavailable

#### Phase 2: Stocks Trading with Signals (Completed - March 15, 2026)
- [x] Added 10 popular stocks to simulator: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, TATASTEEL, ITC, WIPRO, AXISBANK
- [x] New API endpoints:
  - GET /api/watchlist/indices - Returns NIFTY, BANKNIFTY (F&O)
  - GET /api/watchlist/stocks - Returns 10 stocks (Cash/CNC)
  - GET /api/stocks/search - Stock search functionality
  - GET /api/instrument/{symbol} - Detailed instrument info
- [x] CNC (Cash-and-Carry) product type support for delivery trading
- [x] Frontend STOCKS tab with:
  - Stocks watchlist showing 10 stocks
  - CNC badges on stock cards
  - Signal display on selected stock
  - Order modal with quantity input and estimated value
  - BUY/SELL buttons for stock trading

### 🔮 Future Tasks

#### P2: Options Chain & Trading (Phase 3)
- [ ] Fetch options chain for NIFTY/BANKNIFTY
- [ ] Display strikes, premiums, Open Interest
- [ ] Options signal generation strategy
- [ ] Options order placement

#### P3: Enhanced UI (Phase 4)
- [ ] Dedicated Stocks tab improvements
- [ ] Options Chain viewer
- [ ] Advanced charting features
- [ ] Mobile-first UI optimization

#### P4: Production Deployment Enhancements
- [ ] Custom domain with SSL (HTTPS)
- [ ] WebSocket integration for live streaming
- [ ] Performance optimization

## Technical Architecture

### Backend (Python/FastAPI)
```
/app/backend/
├── server.py          # Main FastAPI app with all routes
├── kotak_api.py       # Kotak NEO API client (v2)
├── ai_validator.py    # Claude AI signal validation
├── confluence.py      # 10-indicator scoring engine
├── indicators.py      # Technical indicators
├── simulator.py       # Market data simulation
├── backtester.py      # Strategy backtesting
└── requirements.txt
```

### Frontend (React Native/Expo)
```
/app/frontend/
├── app/
│   └── index.tsx      # Main dashboard with tabs
├── src/
│   ├── components/
│   │   ├── StocksTab.tsx         # NEW: Stocks trading tab
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
EXPO_PUBLIC_BACKEND_URL="https://neo-trader-sandbox.preview.emergentagent.com"
```

## Deployment
- **Preview Environment**: https://neo-trader-sandbox.preview.emergentagent.com
- **Production (AWS EC2)**: http://ec2-51-20-66-73.eu-north-1.compute.amazonaws.com

## Testing Status
- Backend: 17/17 tests passed (100%)
- Frontend: All flows tested successfully
- Demo mode: Fully functional
- Live trading: Authentication working (requires user credentials)

## Last Updated
March 15, 2026
