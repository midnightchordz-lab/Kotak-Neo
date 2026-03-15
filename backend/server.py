"""
COSTAR Kotak Neo F&O Algo Trader - API Server
Professional-grade intraday trading application for NSE F&O
"""
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
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
from dataclasses import asdict

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
from options_chain import options_chain_generator, OptionsChain
from websocket_manager import ws_manager

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
websocket_broadcast_task = None

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
    product_type: str = "MIS"  # MIS for intraday F&O, CNC for delivery stocks, NRML for carry forward

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
    global simulation_active, websocket_broadcast_task
    
    if simulation_active:
        return {"message": "Simulation already running"}
    
    simulation_active = True
    background_tasks.add_task(run_simulation_loop)
    background_tasks.add_task(broadcast_market_data)
    
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
    symbol_upper = symbol.upper()
    
    # Try live API first if authenticated
    if kotak_api and kotak_api.session.is_authenticated:
        # Determine if this is an index
        is_index = symbol_upper in ['NIFTY', 'BANKNIFTY', 'NIFTY 50', 'NIFTY BANK']
        
        if is_index:
            result = await kotak_api.get_index_quote(symbol_upper)
        else:
            # For stocks, use pSymbol from instrument list
            result = await kotak_api.get_quotes(
                [{"exchange_segment": "nse_cm", "symbol": symbol_upper}],
                quote_type='all',
                is_index=False
            )
        
        if result.get('success') and result.get('quotes'):
            quotes = result['quotes']
            # Parse the Kotak response format (array of quote objects)
            if isinstance(quotes, list) and len(quotes) > 0:
                q = quotes[0]
                ohlc = q.get('ohlc', {})
                return {
                    "success": True,
                    "quote": {
                        "symbol": symbol_upper,
                        "ltp": float(q.get('ltp', 0)),
                        "open": float(ohlc.get('open', 0)) if ohlc else 0,
                        "high": float(ohlc.get('high', 0)) if ohlc else 0,
                        "low": float(ohlc.get('low', 0)) if ohlc else 0,
                        "close": float(ohlc.get('close', 0)) if ohlc else 0,
                        "volume": int(q.get('last_volume', 0)),
                        "change": float(q.get('change', 0)),
                        "change_percent": float(q.get('per_change', 0)),
                        "bid": float(q.get('depth', {}).get('buy', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                        "ask": float(q.get('depth', {}).get('sell', [{}])[0].get('price', 0)) if q.get('depth') else 0,
                        "total_buy": int(q.get('total_buy', 0)),
                        "total_sell": int(q.get('total_sell', 0)),
                    },
                    "mode": "live"
                }
    
    # Fall back to simulation
    quote = simulator.get_quote(symbol_upper)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    return {"success": True, "quote": quote, "mode": "simulation"}

@api_router.get("/market/candles/{symbol}")
async def get_candles(symbol: str, count: int = 100):
    """Get historical candles for a symbol"""
    symbol_upper = symbol.upper()
    
    # Get live price to scale candles appropriately
    live_price = None
    if kotak_api and kotak_api.session.is_authenticated:
        is_index = symbol_upper in ['NIFTY', 'BANKNIFTY']
        if is_index:
            result = await kotak_api.get_index_quote(symbol_upper)
        else:
            result = await kotak_api.get_quotes(
                [{"exchange_segment": "nse_cm", "symbol": symbol_upper}],
                quote_type='all',
                is_index=False
            )
        if result.get('success') and result.get('quotes'):
            quotes = result['quotes']
            if isinstance(quotes, list) and len(quotes) > 0:
                live_price = float(quotes[0].get('ltp', 0))
    
    candles = simulator.get_candles(symbol_upper)
    
    if not candles:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    # If we have live price, scale the candles to match
    candles_data = []
    if live_price and live_price > 0:
        # Get the last simulated price and calculate scale factor
        last_sim_price = candles[-1].close if candles else 24500
        scale_factor = live_price / last_sim_price
        
        for c in candles[-count:]:
            candles_data.append({
                "open": round(c.open * scale_factor, 2),
                "high": round(c.high * scale_factor, 2),
                "low": round(c.low * scale_factor, 2),
                "close": round(c.close * scale_factor, 2),
                "volume": c.volume,
                "timestamp": c.timestamp
            })
    else:
        # No live price, use simulation data as-is
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
        "symbol": symbol_upper,
        "candles": candles_data,
        "count": len(candles_data),
        "mode": "live_scaled" if live_price else "simulation"
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
    symbol_upper = request.symbol.upper()
    
    # Get instrument info for proper product type
    instrument = simulator.instruments.get(symbol_upper)
    if not instrument:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol_upper} not found")
    
    # Determine exchange segment and product type
    segment = instrument.get('segment', 'nse_fo')
    default_product = instrument.get('product_type', 'MIS')
    product_type = request.product_type or default_product
    
    # Try live API first
    if kotak_api and kotak_api.session.is_authenticated:
        order_data = {
            "exchange_segment": segment,
            "trading_symbol": symbol_upper,
            "transaction_type": "B" if request.side == "BUY" else "S",
            "quantity": str(request.quantity),
            "product": product_type,
            "order_type": request.order_type,
            "price": str(request.price) if request.order_type != "MKT" else "0",
            "trigger_price": str(request.trigger_price) if request.order_type == "SL" else "0",
            "validity": "DAY",
            "amo": "NO"
        }
        result = await kotak_api.place_order(order_data)
        return result
    
    # Use simulation
    result = simulator.place_order(
        symbol=symbol_upper,
        side=request.side.upper(),
        quantity=request.quantity,
        order_type=request.order_type.upper(),
        price=request.price
    )
    result["mode"] = "simulation"
    result["product_type"] = product_type
    result["segment"] = segment
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
            "change_percent": round(quote.get('change_percent', 0), 2),
            "segment": config.get('segment', 'nse_fo'),
            "product_type": config.get('product_type', 'MIS')
        })
    return {"success": True, "watchlist": watchlist}

@api_router.get("/watchlist/indices")
async def get_indices_watchlist():
    """Get index instruments (NIFTY, BANKNIFTY for F&O)"""
    watchlist = []
    for symbol, config in simulator.instruments.items():
        if config.get('segment') == 'nse_fo':
            quote = simulator.get_quote(symbol)
            watchlist.append({
                "symbol": symbol,
                "lot_size": config['lot_size'],
                "ltp": quote.get('ltp', 0),
                "change": quote.get('change', 0),
                "change_percent": round(quote.get('change_percent', 0), 2),
                "segment": config.get('segment', 'nse_fo'),
                "product_type": config.get('product_type', 'MIS')
            })
    return {"success": True, "watchlist": watchlist}

@api_router.get("/watchlist/stocks")
async def get_stocks_watchlist():
    """Get stock instruments (Cash segment for CNC trading)"""
    watchlist = []
    for symbol, config in simulator.instruments.items():
        if config.get('segment') == 'nse_cm':
            quote = simulator.get_quote(symbol)
            watchlist.append({
                "symbol": symbol,
                "lot_size": config['lot_size'],
                "ltp": quote.get('ltp', 0),
                "change": quote.get('change', 0),
                "change_percent": round(quote.get('change_percent', 0), 2),
                "segment": config.get('segment', 'nse_cm'),
                "product_type": config.get('product_type', 'CNC')
            })
    return {"success": True, "watchlist": watchlist}

@api_router.get("/stocks/search")
async def search_stocks(query: str = "", limit: int = 20):
    """Search for stocks by name or symbol"""
    if not query:
        # Return all available stocks
        stocks = []
        for symbol, config in simulator.instruments.items():
            if config.get('segment') == 'nse_cm':
                quote = simulator.get_quote(symbol)
                stocks.append({
                    "symbol": symbol,
                    "name": symbol,
                    "ltp": quote.get('ltp', 0),
                    "change": quote.get('change', 0),
                    "change_percent": round(quote.get('change_percent', 0), 2),
                    "segment": config.get('segment'),
                    "product_type": config.get('product_type', 'CNC')
                })
        return {"success": True, "results": stocks[:limit]}
    
    # Filter stocks by query
    query_upper = query.upper()
    results = []
    for symbol, config in simulator.instruments.items():
        if config.get('segment') == 'nse_cm' and query_upper in symbol:
            quote = simulator.get_quote(symbol)
            results.append({
                "symbol": symbol,
                "name": symbol,
                "ltp": quote.get('ltp', 0),
                "change": quote.get('change', 0),
                "change_percent": round(quote.get('change_percent', 0), 2),
                "segment": config.get('segment'),
                "product_type": config.get('product_type', 'CNC')
            })
    
    return {"success": True, "results": results[:limit], "query": query}

@api_router.get("/instrument/{symbol}")
async def get_instrument_details(symbol: str):
    """Get detailed information about an instrument"""
    symbol_upper = symbol.upper()
    if symbol_upper not in simulator.instruments:
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found")
    
    config = simulator.instruments[symbol_upper]
    quote = simulator.get_quote(symbol_upper)
    
    return {
        "success": True,
        "instrument": {
            "symbol": symbol_upper,
            "segment": config.get('segment', 'nse_fo'),
            "product_type": config.get('product_type', 'MIS'),
            "lot_size": config['lot_size'],
            "token": config.get('token', symbol_upper),
            "ltp": quote.get('ltp', 0),
            "open": quote.get('open', 0),
            "high": quote.get('high', 0),
            "low": quote.get('low', 0),
            "change": quote.get('change', 0),
            "change_percent": round(quote.get('change_percent', 0), 2),
            "volume": quote.get('volume', 0)
        }
    }

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

# ==================== OPTIONS CHAIN ====================

@api_router.get("/options/expiries/{underlying}")
async def get_options_expiries(underlying: str):
    """Get available expiry dates for options"""
    underlying_upper = underlying.upper()
    if underlying_upper not in ['NIFTY', 'BANKNIFTY']:
        raise HTTPException(status_code=400, detail="Options available only for NIFTY and BANKNIFTY")
    
    expiries = options_chain_generator.generate_expiries()
    return {
        "success": True,
        "underlying": underlying_upper,
        "expiries": expiries
    }

@api_router.get("/options/chain/{underlying}")
async def get_options_chain(underlying: str, expiry: Optional[str] = None, strikes: int = 15):
    """
    Get complete options chain for an underlying
    
    Args:
        underlying: NIFTY or BANKNIFTY
        expiry: Expiry date (YYYY-MM-DD format), uses nearest if not provided
        strikes: Number of strikes on each side of ATM (default 15)
    """
    underlying_upper = underlying.upper()
    if underlying_upper not in ['NIFTY', 'BANKNIFTY']:
        raise HTTPException(status_code=400, detail="Options available only for NIFTY and BANKNIFTY")
    
    # Try to get LIVE spot price first
    spot_price = None
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_index_quote(underlying_upper)
        if result.get('success') and result.get('quotes'):
            quotes = result['quotes']
            if isinstance(quotes, list) and len(quotes) > 0:
                spot_price = float(quotes[0].get('ltp', 0))
                logger.info(f"Using LIVE spot price for {underlying_upper}: {spot_price}")
    
    # Fallback to simulation price
    if not spot_price or spot_price <= 0:
        spot_price = simulator.get_ltp(underlying_upper)
        logger.info(f"Using SIMULATION spot price for {underlying_upper}: {spot_price}")
    
    if not spot_price:
        raise HTTPException(status_code=400, detail=f"No price data for {underlying_upper}")
    
    # Generate options chain with the spot price
    chain = options_chain_generator.generate_chain(
        underlying=underlying_upper,
        spot_price=spot_price,
        expiry_date=expiry,
        num_strikes=strikes
    )
    
    # Convert to dict format
    return {
        "success": True,
        "underlying": chain.underlying,
        "spot_price": chain.spot_price,
        "expiry": chain.expiry,
        "atm_strike": chain.atm_strike,
        "pcr": chain.pcr,
        "max_pain": chain.max_pain,
        "timestamp": chain.timestamp,
        "calls": [asdict(c) for c in chain.calls],
        "puts": [asdict(p) for p in chain.puts]
    }

@api_router.get("/options/signal/{underlying}")
async def get_options_signal(underlying: str, expiry: Optional[str] = None):
    """
    Get trading signal based on options chain analysis
    Analyzes PCR, OI buildup, and max pain
    """
    underlying_upper = underlying.upper()
    if underlying_upper not in ['NIFTY', 'BANKNIFTY']:
        raise HTTPException(status_code=400, detail="Options available only for NIFTY and BANKNIFTY")
    
    # Try to get LIVE spot price first
    spot_price = None
    if kotak_api and kotak_api.session.is_authenticated:
        result = await kotak_api.get_index_quote(underlying_upper)
        if result.get('success') and result.get('quotes'):
            quotes = result['quotes']
            if isinstance(quotes, list) and len(quotes) > 0:
                spot_price = float(quotes[0].get('ltp', 0))
    
    # Fallback to simulation price
    if not spot_price or spot_price <= 0:
        spot_price = simulator.get_ltp(underlying_upper)
    
    if not spot_price:
        raise HTTPException(status_code=400, detail=f"No price data for {underlying_upper}")
    
    chain = options_chain_generator.generate_chain(
        underlying=underlying_upper,
        spot_price=spot_price,
        expiry_date=expiry
    )
    
    signal = options_chain_generator.get_option_signal(chain)
    
    return {
        "success": True,
        "underlying": underlying_upper,
        "spot_price": spot_price,
        "expiry": chain.expiry,
        **signal
    }

@api_router.get("/options/quote/{underlying}/{strike}/{option_type}")
async def get_option_quote(underlying: str, strike: float, option_type: str, 
                          expiry: Optional[str] = None):
    """
    Get quote for a specific option contract
    
    Args:
        underlying: NIFTY or BANKNIFTY
        strike: Strike price
        option_type: CE or PE
    """
    underlying_upper = underlying.upper()
    option_type_upper = option_type.upper()
    
    if underlying_upper not in ['NIFTY', 'BANKNIFTY']:
        raise HTTPException(status_code=400, detail="Options available only for NIFTY and BANKNIFTY")
    
    if option_type_upper not in ['CE', 'PE']:
        raise HTTPException(status_code=400, detail="Option type must be CE or PE")
    
    spot_price = simulator.get_ltp(underlying_upper)
    chain = options_chain_generator.generate_chain(
        underlying=underlying_upper,
        spot_price=spot_price,
        expiry_date=expiry
    )
    
    # Find the option contract
    options = chain.calls if option_type_upper == 'CE' else chain.puts
    contract = next((o for o in options if o.strike == strike), None)
    
    if not contract:
        raise HTTPException(status_code=404, detail=f"Option contract not found: {underlying_upper} {strike} {option_type_upper}")
    
    return {
        "success": True,
        "contract": asdict(contract),
        "spot_price": spot_price
    }

class OptionsOrderRequest(BaseModel):
    underlying: str
    strike: float
    option_type: str  # CE or PE
    side: str  # BUY or SELL
    quantity: int
    order_type: str = "MKT"
    price: float = 0
    expiry: Optional[str] = None

@api_router.post("/options/order")
async def place_options_order(request: OptionsOrderRequest):
    """Place an options order"""
    underlying_upper = request.underlying.upper()
    option_type_upper = request.option_type.upper()
    
    if underlying_upper not in ['NIFTY', 'BANKNIFTY']:
        raise HTTPException(status_code=400, detail="Options available only for NIFTY and BANKNIFTY")
    
    # Get lot size
    lot_size = options_chain_generator.LOT_SIZES.get(underlying_upper, 25)
    
    # Generate trading symbol
    expiries = options_chain_generator.generate_expiries()
    expiry = request.expiry or expiries[0]
    trading_symbol = f"{underlying_upper}{expiry.replace('-', '')}{int(request.strike)}{option_type_upper}"
    
    # Try live API first
    if kotak_api and kotak_api.session.is_authenticated:
        order_data = {
            "exchange_segment": "nse_fo",
            "trading_symbol": trading_symbol,
            "transaction_type": "B" if request.side.upper() == "BUY" else "S",
            "quantity": str(request.quantity * lot_size),
            "product": "NRML",
            "order_type": request.order_type,
            "price": str(request.price) if request.order_type != "MKT" else "0",
            "validity": "DAY",
            "amo": "NO"
        }
        result = await kotak_api.place_order(order_data)
        return result
    
    # Simulation mode
    spot_price = simulator.get_ltp(underlying_upper)
    chain = options_chain_generator.generate_chain(
        underlying=underlying_upper,
        spot_price=spot_price,
        expiry_date=expiry
    )
    
    options = chain.calls if option_type_upper == 'CE' else chain.puts
    contract = next((o for o in options if o.strike == request.strike), None)
    
    if not contract:
        raise HTTPException(status_code=404, detail="Option contract not found")
    
    order_id = f'OPT{datetime.utcnow().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:4].upper()}'
    
    return {
        "success": True,
        "order_id": order_id,
        "mode": "simulation",
        "details": {
            "symbol": trading_symbol,
            "strike": request.strike,
            "option_type": option_type_upper,
            "side": request.side.upper(),
            "quantity": request.quantity,
            "lots": request.quantity,
            "lot_size": lot_size,
            "price": contract.ltp,
            "premium": contract.ltp * lot_size * request.quantity
        }
    }

# ==================== WEBSOCKET ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data streaming
    
    Client can send:
    - {"action": "subscribe", "type": "quotes", "symbols": ["NIFTY", "BANKNIFTY"]}
    - {"action": "subscribe", "type": "signals", "symbols": ["NIFTY"]}
    - {"action": "subscribe", "type": "options", "symbols": ["NIFTY"]}
    - {"action": "subscribe", "type": "positions"}
    - {"action": "subscribe", "type": "orders"}
    - {"action": "unsubscribe", "type": "quotes", "symbols": ["NIFTY"]}
    - {"action": "ping"}
    
    Server sends:
    - {"type": "quote", "data": {...}, "timestamp": "..."}
    - {"type": "signal", "data": {...}, "timestamp": "..."}
    - {"type": "options", "data": {...}, "timestamp": "..."}
    - {"type": "positions", "data": {...}, "timestamp": "..."}
    - {"type": "orders", "data": {...}, "timestamp": "..."}
    - {"type": "notification", "data": {...}, "timestamp": "..."}
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await ws_manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)

@api_router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return {
        "success": True,
        "stats": ws_manager.get_stats()
    }

# ==================== WEBSOCKET BROADCAST ====================

async def broadcast_market_data():
    """Background task to broadcast market data via WebSocket"""
    global websocket_broadcast_task
    while simulation_active:
        try:
            # Broadcast quotes for all instruments
            for symbol in simulator.instruments.keys():
                quote = simulator.get_quote(symbol)
                if quote:
                    await ws_manager.broadcast_quote(symbol, quote)
            
            # Broadcast positions and orders
            positions = simulator.get_positions()
            await ws_manager.broadcast_positions(positions)
            
            orders = simulator.get_orders()
            await ws_manager.broadcast_orders(orders)
            
            await asyncio.sleep(1)  # Broadcast every second
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(1)

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
