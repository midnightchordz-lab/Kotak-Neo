"""
COSTAR Kotak Neo F&O Algo Trader - API Server
Professional-grade intraday trading application for NSE F&O
"""
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime
import asyncio

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import trading modules
from indicators import Candle, IndicatorEngine
from confluence import ConfluenceEngine, SignalResult
from kotak_api import KotakNeoAPI
from simulator import MarketSimulator
from ai_validator import AIValidator
from backtester import Backtester

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'algo_trader')]

# Create the main app
app = FastAPI(title="COSTAR Kotak Neo F&O Algo Trader")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
simulator = MarketSimulator()
kotak_api = None
ai_validator = AIValidator()
confluence_engine = ConfluenceEngine()
backtester = Backtester()

# Simulation state
simulation_active = False
simulation_task = None

# ==================== MODELS ====================

class LoginTOTPRequest(BaseModel):
    totp: str

class LoginMPINRequest(BaseModel):
    mpin: str

class OrderRequest(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    order_type: str = "MKT"  # MKT, LIMIT, SL
    price: float = 0
    trigger_price: float = 0

class ModifyOrderRequest(BaseModel):
    order_no: str
    quantity: Optional[int] = None
    price: Optional[float] = None
    trigger_price: Optional[float] = None

class CancelOrderRequest(BaseModel):
    order_no: str

class BacktestRequest(BaseModel):
    symbol: str = "NIFTY"
    candles: int = 200
    min_score: float = 3.0
    min_agree: int = 5
    lot_size: int = 25
    position_size: int = 1

class ConfigUpdateRequest(BaseModel):
    min_score: Optional[float] = None
    min_agree: Optional[int] = None
    sl_atr_mult: Optional[float] = None
    tp_atr_mult: Optional[float] = None
    weights: Optional[Dict[str, float]] = None

# ==================== HEALTH & STATUS ====================

@api_router.get("/")
async def root():
    return {"message": "COSTAR Kotak Neo F&O Algo Trader API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "simulation_active": simulation_active,
        "kotak_connected": kotak_api is not None and kotak_api.session.is_authenticated if kotak_api else False
    }

# ==================== AUTHENTICATION ====================

@api_router.post("/auth/totp")
async def login_totp(request: LoginTOTPRequest):
    """Step 1: Validate TOTP"""
    global kotak_api
    
    access_token = os.getenv('KOTAK_ACCESS_TOKEN')
    if not access_token:
        raise HTTPException(status_code=400, detail="Kotak access token not configured")
    
    kotak_api = KotakNeoAPI(access_token)
    result = await kotak_api.login_step1_totp(request.totp)
    
    if not result.get('success'):
        raise HTTPException(status_code=401, detail=result.get('error', 'TOTP validation failed'))
    
    return result

@api_router.post("/auth/mpin")
async def login_mpin(request: LoginMPINRequest):
    """Step 2: Validate MPIN"""
    global kotak_api
    
    if not kotak_api:
        raise HTTPException(status_code=400, detail="Complete TOTP step first")
    
    result = await kotak_api.login_step2_mpin(request.mpin)
    
    if not result.get('success'):
        raise HTTPException(status_code=401, detail=result.get('error', 'MPIN validation failed'))
    
    return result

@api_router.get("/auth/status")
async def auth_status():
    """Check authentication status"""
    if kotak_api and kotak_api.session.is_authenticated:
        return {
            "authenticated": True,
            "mode": "live",
            "user_id": kotak_api.session.user_id
        }
    return {
        "authenticated": False,
        "mode": "demo",
        "message": "Using simulation mode"
    }

# ==================== SIMULATION CONTROL ====================

@api_router.post("/simulation/start")
async def start_simulation(background_tasks: BackgroundTasks):
    """Start market simulation"""
    global simulation_active
    
    if simulation_active:
        return {"message": "Simulation already running"}
    
    simulation_active = True
    background_tasks.add_task(run_simulation_loop)
    
    return {"message": "Simulation started", "status": "running"}

@api_router.post("/simulation/stop")
async def stop_simulation():
    """Stop market simulation"""
    global simulation_active
    simulation_active = False
    return {"message": "Simulation stopped", "status": "stopped"}

@api_router.get("/simulation/status")
async def simulation_status():
    """Get simulation status"""
    return {
        "active": simulation_active,
        "instruments": list(simulator.instruments.keys()),
        "limits": simulator.get_limits()
    }

async def run_simulation_loop():
    """Background task for simulation"""
    global simulation_active
    while simulation_active:
        for symbol in simulator.instruments.keys():
            simulator.tick(symbol)
        await asyncio.sleep(1.5)  # Tick every 1500ms

# ==================== MARKET DATA ====================

@api_router.get("/market/quote/{symbol}")
async def get_quote(symbol: str):
    """Get current quote for a symbol"""
    # Try live API first
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_quotes([{"exchange_segment": "nse_fo", "token": symbol}])
        if result.get('success'):
            return result
    
    # Fall back to simulation
    quote = simulator.get_quote(symbol.upper())
    if not quote:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    return {"success": True, "quote": quote, "mode": "simulation"}

@api_router.get("/market/candles/{symbol}")
async def get_candles(symbol: str, count: int = 100):
    """Get historical candles for a symbol"""
    candles = simulator.get_candles(symbol.upper())
    
    if not candles:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    # Return last N candles
    candles_data = [
        {
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "timestamp": c.timestamp
        }
        for c in candles[-count:]
    ]
    
    return {
        "success": True,
        "symbol": symbol.upper(),
        "candles": candles_data,
        "count": len(candles_data)
    }

@api_router.get("/market/tick/{symbol}")
async def tick_market(symbol: str):
    """Generate a single market tick (for manual triggering)"""
    tick = simulator.tick(symbol.upper())
    if not tick:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return tick

# ==================== SIGNAL GENERATION ====================

@api_router.get("/signal/{symbol}")
async def get_signal(symbol: str, validate_ai: bool = True):
    """Get current trading signal for a symbol"""
    candles = simulator.get_candles(symbol.upper())
    
    if not candles or len(candles) < 50:
        raise HTTPException(status_code=400, detail="Insufficient data for signal generation")
    
    # Calculate signal
    signal = confluence_engine.score_signal(candles)
    
    # Prepare response
    response = {
        "symbol": symbol.upper(),
        "timestamp": datetime.utcnow().isoformat(),
        "ltp": simulator.get_ltp(symbol.upper()),
        "direction": signal.direction,
        "score": signal.net_score,
        "indicators_agreeing": signal.indicators_agreeing,
        "total_indicators": signal.total_indicators,
        "confidence": signal.confidence,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "risk_reward": signal.risk_reward,
        "atr": signal.atr,
        "votes": [
            {
                "name": v.name,
                "vote": v.vote,
                "weight": v.weight,
                "detail": v.detail,
                "value": v.value
            }
            for v in signal.votes
        ]
    }
    
    # AI validation if requested
    if validate_ai and signal.direction != 'NEUTRAL':
        ai_result = await ai_validator.validate_signal({
            "instrument": symbol.upper(),
            "ltp": response["ltp"],
            "direction": signal.direction,
            "score": signal.net_score,
            "indicators_agreeing": signal.indicators_agreeing,
            "confidence": signal.confidence,
            "votes": response["votes"],
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "risk_reward": signal.risk_reward,
            "atr": signal.atr
        })
        response["ai_validation"] = ai_result
    
    return response

@api_router.get("/indicators/{symbol}")
async def get_indicators(symbol: str):
    """Get all indicator values for a symbol"""
    candles = simulator.get_candles(symbol.upper())
    
    if not candles or len(candles) < 50:
        raise HTTPException(status_code=400, detail="Insufficient data")
    
    engine = IndicatorEngine()
    indicators = engine.calculate_all(candles)
    
    # Return latest values
    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.utcnow().isoformat(),
        "ema_fast": indicators['ema_fast'][-1] if indicators.get('ema_fast') else None,
        "ema_slow": indicators['ema_slow'][-1] if indicators.get('ema_slow') else None,
        "rsi": indicators['rsi'][-1] if indicators.get('rsi') else None,
        "supertrend": indicators['supertrend'][-1] if indicators.get('supertrend') else None,
        "supertrend_direction": indicators['st_direction'][-1] if indicators.get('st_direction') else None,
        "vwap": indicators['vwap'][-1] if indicators.get('vwap') else None,
        "macd_histogram": indicators['macd']['histogram'][-1] if indicators.get('macd', {}).get('histogram') else None,
        "bb_upper": indicators['bb']['upper'][-1] if indicators.get('bb', {}).get('upper') else None,
        "bb_middle": indicators['bb']['middle'][-1] if indicators.get('bb', {}).get('middle') else None,
        "bb_lower": indicators['bb']['lower'][-1] if indicators.get('bb', {}).get('lower') else None,
        "stoch_k": indicators['stochastic']['k'][-1] if indicators.get('stochastic', {}).get('k') else None,
        "stoch_d": indicators['stochastic']['d'][-1] if indicators.get('stochastic', {}).get('d') else None,
        "atr": indicators['atr'][-1] if indicators.get('atr') else None
    }

# ==================== ORDER MANAGEMENT ====================

@api_router.post("/orders/place")
async def place_order(request: OrderRequest):
    """Place a new order"""
    # Try live API first
    if kotak_api and kotak_api.session.is_authenticated:
        order_data = {
            "es": "nse_fo",
            "ts": request.symbol,
            "tt": "B" if request.side == "BUY" else "S",
            "qt": str(request.quantity),
            "pt": "MIS",
            "pc": request.order_type,
            "pr": str(request.price) if request.order_type != "MKT" else "0",
            "tp": str(request.trigger_price) if request.order_type == "SL" else "0",
            "am": "N"
        }
        result = await kotak_api.place_order(order_data)
        return result
    
    # Use simulation
    result = simulator.place_order(
        symbol=request.symbol.upper(),
        side=request.side.upper(),
        quantity=request.quantity,
        order_type=request.order_type.upper(),
        price=request.price
    )
    result["mode"] = "simulation"
    return result

@api_router.post("/orders/modify")
async def modify_order(request: ModifyOrderRequest):
    """Modify an existing order"""
    if kotak_api and kotak_api.session.is_authenticated:
        modifications = {}
        if request.quantity:
            modifications['qt'] = str(request.quantity)
        if request.price:
            modifications['pr'] = str(request.price)
        if request.trigger_price:
            modifications['tp'] = str(request.trigger_price)
        
        result = await kotak_api.modify_order(request.order_no, modifications)
        return result
    
    raise HTTPException(status_code=400, detail="Order modification not supported in simulation mode")

@api_router.post("/orders/cancel")
async def cancel_order(request: CancelOrderRequest):
    """Cancel an existing order"""
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.cancel_order(request.order_no)
        return result
    
    # Use simulation
    result = simulator.cancel_order(request.order_no)
    result["mode"] = "simulation"
    return result

@api_router.get("/orders")
async def get_orders():
    """Get order book"""
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_order_book()
        return result
    
    # Use simulation
    return {
        "success": True,
        "orders": simulator.get_orders(),
        "mode": "simulation"
    }

# ==================== PORTFOLIO ====================

@api_router.get("/positions")
async def get_positions():
    """Get current positions"""
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_positions()
        return result
    
    # Use simulation
    return {
        "success": True,
        "positions": simulator.get_positions(),
        "mode": "simulation"
    }

@api_router.get("/trades")
async def get_trades():
    """Get trade history"""
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_trade_book()
        return result
    
    # Use simulation
    return {
        "success": True,
        "trades": simulator.get_trades(),
        "mode": "simulation"
    }

@api_router.get("/limits")
async def get_limits():
    """Get account limits/margins"""
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_limits()
        return result
    
    # Use simulation
    return {
        "success": True,
        "limits": simulator.get_limits(),
        "mode": "simulation"
    }

# ==================== BACKTESTING ====================

@api_router.post("/backtest")
async def run_backtest(request: BacktestRequest):
    """Run backtest on historical data"""
    candles = simulator.get_candles(request.symbol.upper())
    
    if not candles or len(candles) < request.candles:
        raise HTTPException(status_code=400, detail="Insufficient data for backtesting")
    
    # Configure backtester
    bt = Backtester({
        'initial_capital': 100000,
        'position_size': request.position_size,
        'lot_size': request.lot_size,
        'min_score': request.min_score,
        'min_agree': request.min_agree
    })
    
    # Run backtest
    result = bt.run(candles[-request.candles:])
    
    return {
        "success": True,
        "symbol": request.symbol.upper(),
        "candles_tested": request.candles,
        "results": {
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": round(result.win_rate, 2),
            "total_pnl": round(result.total_pnl, 2),
            "avg_pnl": round(result.avg_pnl, 2),
            "max_drawdown": round(result.max_drawdown, 2),
            "profit_factor": round(result.profit_factor, 2) if result.profit_factor != float('inf') else "N/A"
        },
        "score_breakdown": result.score_breakdown,
        "equity_curve": result.equity_curve,
        "trades": [
            {
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "direction": t.direction,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "score": t.score,
                "win": t.win
            }
            for t in result.trades
        ]
    }

# ==================== CONFIGURATION ====================

@api_router.get("/config")
async def get_config():
    """Get current configuration"""
    return {
        "confluence": confluence_engine.config,
        "indicators": confluence_engine.indicator_engine.config
    }

@api_router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration"""
    if request.min_score is not None:
        confluence_engine.config['min_score'] = request.min_score
    if request.min_agree is not None:
        confluence_engine.config['min_agree'] = request.min_agree
    if request.sl_atr_mult is not None:
        confluence_engine.config['sl_atr_mult'] = request.sl_atr_mult
    if request.tp_atr_mult is not None:
        confluence_engine.config['tp_atr_mult'] = request.tp_atr_mult
    if request.weights is not None:
        confluence_engine.config['weights'].update(request.weights)
    
    return {"success": True, "config": confluence_engine.config}

# ==================== WATCHLIST ====================

@api_router.get("/watchlist")
async def get_watchlist():
    """Get available instruments"""
    watchlist = []
    for symbol, config in simulator.instruments.items():
        quote = simulator.get_quote(symbol)
        watchlist.append({
            "symbol": symbol,
            "lot_size": config['lot_size'],
            "ltp": quote.get('ltp', 0),
            "change": quote.get('change', 0),
            "change_percent": round(quote.get('change_percent', 0), 2)
        })
    return {"success": True, "watchlist": watchlist}

# ==================== API LOGS ====================

api_logs = []

@api_router.get("/logs")
async def get_api_logs(limit: int = 50):
    """Get recent API logs"""
    return {"logs": api_logs[-limit:]}

@api_router.delete("/logs")
async def clear_api_logs():
    """Clear API logs"""
    api_logs.clear()
    return {"success": True, "message": "Logs cleared"}

# ==================== POSITION SIZER ====================

@api_router.get("/position-size/{symbol}")
async def calculate_position_size(symbol: str, risk_percent: float = 1.0, capital: Optional[float] = None):
    """Calculate recommended position size based on risk"""
    quote = simulator.get_quote(symbol.upper())
    if not quote:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    limits = simulator.get_limits()
    account_capital = capital or limits['available_margin']
    
    ltp = quote['ltp']
    lot_size = quote['lot_size']
    lot_value = ltp * lot_size
    
    # Get ATR for risk calculation
    candles = simulator.get_candles(symbol.upper())
    engine = IndicatorEngine()
    indicators = engine.calculate_all(candles)
    atr = indicators['atr'][-1] if indicators.get('atr') else ltp * 0.01
    
    # Calculate max lots by capital (10% margin requirement)
    margin_per_lot = lot_value * 0.1
    max_lots_by_capital = int(account_capital / margin_per_lot)
    
    # Calculate recommended lots based on risk
    risk_amount = account_capital * (risk_percent / 100)
    sl_distance = atr * 1.5
    risk_per_lot = sl_distance * lot_size
    recommended_lots = max(1, int(risk_amount / risk_per_lot)) if risk_per_lot > 0 else 1
    
    return {
        "symbol": symbol.upper(),
        "ltp": ltp,
        "lot_size": lot_size,
        "lot_value": round(lot_value, 2),
        "margin_per_lot": round(margin_per_lot, 2),
        "max_lots_by_capital": max_lots_by_capital,
        "recommended_lots": min(recommended_lots, max_lots_by_capital),
        "risk_percent": risk_percent,
        "atr": round(atr, 2),
        "sl_distance": round(sl_distance, 2),
        "risk_per_lot": round(risk_per_lot, 2)
    }

# Include the router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("COSTAR Kotak Neo F&O Algo Trader starting up...")
    # Initialize simulation with some ticks
    for _ in range(10):
        for symbol in simulator.instruments.keys():
            simulator.tick(symbol)

@app.on_event("shutdown")
async def shutdown_db_client():
    global simulation_active
    simulation_active = False
    if kotak_api:
        await kotak_api.close()
    client.close()
