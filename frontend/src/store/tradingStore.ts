import { create } from 'zustand';
import axios from 'axios';
import Constants from 'expo-constants';

const API_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Types
export interface Quote {
  symbol: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  change: number;
  change_percent: number;
  volume: number;
  lot_size: number;
  bid: number;
  ask: number;
  bid_qty: number;
  ask_qty: number;
}

export interface Candle {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: number;
}

export interface IndicatorVote {
  name: string;
  vote: number;
  weight: number;
  detail: string;
  value: number | null;
}

export interface Signal {
  symbol: string;
  timestamp: string;
  ltp: number;
  direction: string;
  score: number;
  indicators_agreeing: number;
  total_indicators: number;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  atr: number;
  votes: IndicatorVote[];
  ai_validation?: {
    verdict: string;
    quality: string;
    confidence: number;
    entry_timing: string;
    key_risk: string;
    adjustment: string;
  };
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  pnl: number;
  pnl_percent: number;
}

export interface Order {
  order_id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  order_type: string;
  status: string;
  fill_price: number;
  timestamp: string;
}

export interface Limits {
  total_cash: number;
  available_margin: number;
  used_margin: number;
  unrealized_pnl: number;
  realized_pnl: number;
  net_worth?: number;
}

export interface BacktestResult {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  max_drawdown: number;
  profit_factor: number | string;
}

export interface WatchlistItem {
  symbol: string;
  ltp: number;
  change: number;
  change_percent: number;
  lot_size: number;
  segment: string;
  product_type: string;
}

interface TradingStore {
  // State
  selectedSymbol: string;
  quote: Quote | null;
  candles: Candle[];
  signal: Signal | null;
  positions: Position[];
  orders: Order[];
  limits: Limits | null;
  isLoading: boolean;
  error: string | null;
  mode: 'demo' | 'live';
  simulationActive: boolean;
  backtestResult: BacktestResult | null;
  activeTab: string;
  stocksWatchlist: WatchlistItem[];
  indicesWatchlist: WatchlistItem[];
  
  // Actions
  setSelectedSymbol: (symbol: string) => void;
  setActiveTab: (tab: string) => void;
  fetchQuote: () => Promise<void>;
  fetchCandles: () => Promise<void>;
  fetchSignal: () => Promise<void>;
  fetchPositions: () => Promise<void>;
  fetchOrders: () => Promise<void>;
  fetchLimits: () => Promise<void>;
  fetchStocksWatchlist: () => Promise<void>;
  fetchIndicesWatchlist: () => Promise<void>;
  placeOrder: (side: string, quantity: number, orderType?: string, price?: number, productType?: string) => Promise<any>;
  cancelOrder: (orderId: string) => Promise<any>;
  startSimulation: () => Promise<void>;
  stopSimulation: () => Promise<void>;
  runBacktest: (params: any) => Promise<void>;
  refreshAll: () => Promise<void>;
}

export const useTradingStore = create<TradingStore>((set, get) => ({
  // Initial state
  selectedSymbol: 'NIFTY',
  quote: null,
  candles: [],
  signal: null,
  positions: [],
  orders: [],
  limits: null,
  isLoading: false,
  error: null,
  mode: 'demo',
  simulationActive: false,
  backtestResult: null,
  activeTab: 'signal',
  stocksWatchlist: [],
  indicesWatchlist: [],

  // Actions
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
  setActiveTab: (tab) => set({ activeTab: tab }),

  fetchQuote: async () => {
    try {
      const { selectedSymbol } = get();
      const response = await axios.get(`${API_URL}/api/market/quote/${selectedSymbol}`);
      if (response.data.success) {
        set({ quote: response.data.quote });
      }
    } catch (error: any) {
      console.error('Fetch quote error:', error.message);
    }
  },

  fetchCandles: async () => {
    try {
      const { selectedSymbol } = get();
      const response = await axios.get(`${API_URL}/api/market/candles/${selectedSymbol}?count=100`);
      if (response.data.success) {
        set({ candles: response.data.candles });
      }
    } catch (error: any) {
      console.error('Fetch candles error:', error.message);
    }
  },

  fetchSignal: async () => {
    try {
      set({ isLoading: true, error: null });
      const { selectedSymbol } = get();
      const response = await axios.get(`${API_URL}/api/signal/${selectedSymbol}?validate_ai=true`);
      set({ signal: response.data, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },

  fetchPositions: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/positions`);
      if (response.data.success) {
        set({ positions: response.data.positions });
      }
    } catch (error: any) {
      console.error('Fetch positions error:', error.message);
    }
  },

  fetchOrders: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/orders`);
      if (response.data.success) {
        set({ orders: response.data.orders });
      }
    } catch (error: any) {
      console.error('Fetch orders error:', error.message);
    }
  },

  fetchLimits: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/limits`);
      if (response.data.success) {
        set({ limits: response.data.limits });
      }
    } catch (error: any) {
      console.error('Fetch limits error:', error.message);
    }
  },

  fetchStocksWatchlist: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/watchlist/stocks`);
      if (response.data.success) {
        set({ stocksWatchlist: response.data.watchlist });
      }
    } catch (error: any) {
      console.error('Fetch stocks watchlist error:', error.message);
    }
  },

  fetchIndicesWatchlist: async () => {
    try {
      const response = await axios.get(`${API_URL}/api/watchlist/indices`);
      if (response.data.success) {
        set({ indicesWatchlist: response.data.watchlist });
      }
    } catch (error: any) {
      console.error('Fetch indices watchlist error:', error.message);
    }
  },

  placeOrder: async (side, quantity, orderType = 'MKT', price = 0, productType = 'MIS') => {
    try {
      const { selectedSymbol } = get();
      const response = await axios.post(`${API_URL}/api/orders/place`, {
        symbol: selectedSymbol,
        side,
        quantity,
        order_type: orderType,
        price,
        product_type: productType
      });
      
      // Refresh orders and positions
      get().fetchOrders();
      get().fetchPositions();
      get().fetchLimits();
      
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || error.message);
    }
  },

  cancelOrder: async (orderId) => {
    try {
      const response = await axios.post(`${API_URL}/api/orders/cancel`, {
        order_no: orderId
      });
      get().fetchOrders();
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || error.message);
    }
  },

  startSimulation: async () => {
    try {
      await axios.post(`${API_URL}/api/simulation/start`);
      set({ simulationActive: true });
    } catch (error: any) {
      console.error('Start simulation error:', error.message);
    }
  },

  stopSimulation: async () => {
    try {
      await axios.post(`${API_URL}/api/simulation/stop`);
      set({ simulationActive: false });
    } catch (error: any) {
      console.error('Stop simulation error:', error.message);
    }
  },

  runBacktest: async (params) => {
    try {
      set({ isLoading: true, backtestResult: null });
      const response = await axios.post(`${API_URL}/api/backtest`, params);
      if (response.data.success) {
        set({ backtestResult: response.data.results, isLoading: false });
      }
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },

  refreshAll: async () => {
    const store = get();
    await Promise.all([
      store.fetchQuote(),
      store.fetchCandles(),
      store.fetchSignal(),
      store.fetchPositions(),
      store.fetchOrders(),
      store.fetchLimits()
    ]);
  }
}));
