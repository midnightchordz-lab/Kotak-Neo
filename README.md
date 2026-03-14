# COSTAR Kotak Neo F&O Algo Trader

Professional-grade intraday trading application for NSE F&O (NIFTY and BANKNIFTY) with multi-indicator confluence scoring, AI signal validation, and automated trading via Kotak NEO API.

## Features

### Trading Engine
- **10 Technical Indicators Confluence System**
  - EMA Crossover (9/21)
  - RSI (14-period)
  - Supertrend (10, 3.0)
  - VWAP
  - MACD Histogram
  - Bollinger Bands (20, 2.0)
  - Stochastic K/D (14, 3)
  - Volume Spike Detection
  - OBV Trend
  - Price Action Patterns

- **Weighted Voting System** - Each indicator contributes to a confluence score
- **ATR-based Risk Management** - Automatic SL/TP calculation
- **AI Signal Validation** - Claude AI validates signals before trading

### Trading Modes
- **Demo Mode** - Paper trading with simulated market data
- **Live Mode** - Real trading via Kotak NEO API

### Backtesting
- Historical simulation with configurable parameters
- Win rate, profit factor, max drawdown analysis
- Score breakdown by threshold levels

## Tech Stack

- **Frontend**: React Native (Expo) - Works on Web, iOS, Android
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **AI**: Claude API via Emergent Integrations

## Local Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB (local or Atlas)
- Kotak NEO Trading Account

### 1. Clone/Download the Code

```bash
git clone <your-repo-url>
cd costar-algo-trader
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

Edit `.env` with your credentials:
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="algo_trader"
EMERGENT_LLM_KEY="your-emergent-llm-key"  # Get from Emergent Profile > Universal Key
KOTAK_ACCESS_TOKEN="your-kotak-access-token"  # From Kotak NEO API portal
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install
# or: npm install

# Create .env file
echo 'EXPO_PUBLIC_BACKEND_URL=http://localhost:8001' > .env
```

### 4. Start MongoDB

```bash
# If using local MongoDB
mongod --dbpath /path/to/data

# Or use MongoDB Atlas connection string in .env
```

### 5. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
yarn start
# or: npx expo start
```

### 6. Access the App

- **Web**: http://localhost:3000 (or press 'w' in Expo CLI)
- **iOS**: Scan QR code with Camera app
- **Android**: Scan QR code with Expo Go app

## Kotak NEO API Setup

### Getting Your Access Token

1. Log in to [Kotak NEO API Portal](https://neotradeapi.kotaksecurities.com)
2. Go to API Keys section
3. Generate/Copy your Access Token
4. Add to backend `.env` as `KOTAK_ACCESS_TOKEN`

### Authentication Flow

The app uses 3-step authentication:
1. **Access Token** - Pre-configured in .env
2. **TOTP** - 6-digit code from your authenticator app
3. **MPIN** - 4-digit trading PIN

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/auth/totp` | POST | Step 1: TOTP verification |
| `/api/auth/mpin` | POST | Step 2: MPIN verification |
| `/api/auth/status` | GET | Check auth status |
| `/api/market/quote/{symbol}` | GET | Get real-time quote |
| `/api/market/candles/{symbol}` | GET | Get historical candles |
| `/api/signal/{symbol}` | GET | Get trading signal |
| `/api/indicators/{symbol}` | GET | Get indicator values |
| `/api/orders/place` | POST | Place order |
| `/api/orders` | GET | Get order book |
| `/api/positions` | GET | Get positions |
| `/api/limits` | GET | Get account limits |
| `/api/backtest` | POST | Run backtest |
| `/api/simulation/start` | POST | Start demo simulation |
| `/api/simulation/stop` | POST | Stop demo simulation |

## Configuration

### Confluence Thresholds

Edit in `backend/confluence.py`:
```python
config = {
    'min_score': 3.0,      # Minimum weighted score to generate signal
    'min_agree': 5,        # Minimum indicators agreeing
    'sl_atr_mult': 1.5,    # Stop loss = ATR * 1.5
    'tp_atr_mult': 3.0,    # Take profit = ATR * 3.0
}
```

### Indicator Weights

```python
weights = {
    'ema_crossover': 1.5,
    'rsi': 1.0,
    'supertrend': 1.5,
    'vwap': 1.0,
    'macd': 1.0,
    'bollinger': 0.75,
    'stochastic': 0.75,
    'volume_spike': 1.0,
    'obv_trend': 0.75,
    'price_action': 0.75
}
```

## Project Structure

```
/app
├── backend/
│   ├── server.py           # FastAPI main server
│   ├── indicators.py       # Technical indicators engine
│   ├── confluence.py       # Confluence scoring system
│   ├── kotak_api.py        # Kotak NEO API client
│   ├── simulator.py        # Demo mode simulation
│   ├── ai_validator.py     # Claude AI validation
│   ├── backtester.py       # Backtesting engine
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── app/
│   │   └── index.tsx       # Main trading dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── CandlestickChart.tsx
│   │   │   ├── ConfluenceGauge.tsx
│   │   │   ├── IndicatorBreakdown.tsx
│   │   │   ├── QuotePanel.tsx
│   │   │   ├── RiskRewardPanel.tsx
│   │   │   └── AIValidationPanel.tsx
│   │   ├── store/
│   │   │   └── tradingStore.ts
│   │   └── theme/
│   │       └── colors.ts
│   ├── package.json
│   └── .env
│
└── README.md
```

## Risk Disclaimer

⚠️ **IMPORTANT**: This software is for educational purposes. Trading in F&O involves substantial risk of loss. Past performance is not indicative of future results. Always:

- Test thoroughly in Demo Mode first
- Start with small position sizes
- Never risk more than you can afford to lose
- Understand the confluence signals before trading

## License

MIT License - Use at your own risk.

## Support

For issues with:
- **Kotak NEO API**: Contact Kotak Securities support
- **Application bugs**: Create an issue in the repository
