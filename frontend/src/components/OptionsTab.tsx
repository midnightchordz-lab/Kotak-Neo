import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Modal,
  TextInput,
  Alert,
} from 'react-native';
import { colors, spacing } from '../theme/colors';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Auto-refresh interval in milliseconds (5 seconds)
const AUTO_REFRESH_INTERVAL = 5000;

interface OptionContract {
  underlying: string;
  strike: number;
  option_type: string;
  expiry: string;
  ltp: number;
  change: number;
  change_percent: number;
  open_interest: number;
  oi_change: number;
  volume: number;
  bid: number;
  ask: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
}

interface OptionsChainData {
  underlying: string;
  spot_price: number;
  price_source: string;
  expiry: string;
  atm_strike: number;
  pcr: number;
  max_pain: number;
  is_live: boolean;
  calls: OptionContract[];
  puts: OptionContract[];
}

interface OptionsSignal {
  direction: string;
  confidence: number;
  pcr: number;
  support: number;
  resistance: number;
  recommendation: {
    primary: string;
    alternative: string;
    strategy: string;
  };
}

interface OptionsTabProps {
  appMode: 'demo' | 'live';
}

export const OptionsTab: React.FC<OptionsTabProps> = ({ appMode }) => {
  const [underlying, setUnderlying] = useState('NIFTY');
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string>('');
  const [chain, setChain] = useState<OptionsChainData | null>(null);
  const [signal, setSignal] = useState<OptionsSignal | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedContract, setSelectedContract] = useState<OptionContract | null>(null);
  const [orderModalVisible, setOrderModalVisible] = useState(false);
  const [orderQuantity, setOrderQuantity] = useState('1');
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');
  const [viewMode, setViewMode] = useState<'chain' | 'signal'>('chain');
  
  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchExpiries();
  }, [underlying]);

  useEffect(() => {
    if (selectedExpiry) {
      fetchOptionsChain();
      fetchOptionsSignal();
    }
  }, [selectedExpiry, underlying]);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh && selectedExpiry && !loading) {
      // Clear any existing interval
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
      
      // Set up new interval
      refreshIntervalRef.current = setInterval(() => {
        silentRefresh();
      }, AUTO_REFRESH_INTERVAL);
      
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    }
  }, [autoRefresh, selectedExpiry, underlying]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);

  const silentRefresh = useCallback(async () => {
    if (isRefreshing || !selectedExpiry) return;
    
    setIsRefreshing(true);
    try {
      const response = await axios.get(
        `${API_URL}/api/options/chain/${underlying}?expiry=${selectedExpiry}&strikes=10`
      );
      if (response.data.success) {
        setChain(response.data);
        setLastRefreshTime(new Date());
      }
    } catch (error) {
      console.error('Silent refresh error:', error);
    }
    setIsRefreshing(false);
  }, [underlying, selectedExpiry, isRefreshing]);

  const fetchExpiries = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/options/expiries/${underlying}`);
      if (response.data.success) {
        setExpiries(response.data.expiries);
        if (!selectedExpiry && response.data.expiries.length > 0) {
          setSelectedExpiry(response.data.expiries[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching expiries:', error);
    }
  };

  const fetchOptionsChain = async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API_URL}/api/options/chain/${underlying}?expiry=${selectedExpiry}&strikes=10`
      );
      if (response.data.success) {
        setChain(response.data);
        setLastRefreshTime(new Date());
      }
    } catch (error) {
      console.error('Error fetching options chain:', error);
    }
    setLoading(false);
  };

  const fetchOptionsSignal = async () => {
    try {
      const response = await axios.get(
        `${API_URL}/api/options/signal/${underlying}?expiry=${selectedExpiry}`
      );
      if (response.data.success) {
        setSignal(response.data);
      }
    } catch (error) {
      console.error('Error fetching options signal:', error);
    }
  };

  const handlePlaceOrder = async () => {
    if (!selectedContract) return;

    const payload = {
      underlying,
      strike: selectedContract.strike,
      option_type: selectedContract.option_type,
      side: orderSide,
      quantity: parseInt(orderQuantity) || 1,
      expiry: selectedExpiry,
    };

    if (appMode === 'live') {
      Alert.alert(
        `Confirm ${orderSide} Order`,
        `Place ${orderSide} order for ${payload.quantity} lots of ${underlying} ${selectedContract.strike} ${selectedContract.option_type}?\n\nThis is a LIVE order!`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Confirm',
            style: orderSide === 'BUY' ? 'default' : 'destructive',
            onPress: async () => {
              try {
                const response = await axios.post(`${API_URL}/api/options/order`, payload);
                Alert.alert('Order Placed', `Order ID: ${response.data.order_id}`);
                setOrderModalVisible(false);
              } catch (error: any) {
                Alert.alert('Order Failed', error.response?.data?.detail || error.message);
              }
            },
          },
        ]
      );
    } else {
      try {
        const response = await axios.post(`${API_URL}/api/options/order`, payload);
        const details = response.data.details;
        Alert.alert(
          'Demo Order Placed',
          `Order ID: ${response.data.order_id}\n\nSymbol: ${details.symbol}\nSide: ${details.side}\nLots: ${details.lots}\nPremium: ₹${details.premium.toFixed(2)}`
        );
        setOrderModalVisible(false);
      } catch (error: any) {
        Alert.alert('Order Failed', error.response?.data?.detail || error.message);
      }
    }
  };

  const getChangeColor = (value: number) => {
    if (value > 0) return colors.bullish;
    if (value < 0) return colors.bearish;
    return colors.text;
  };

  const formatNumber = (num: number) => {
    if (num >= 100000) return `${(num / 100000).toFixed(1)}L`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const renderOptionRow = (call: OptionContract, put: OptionContract) => {
    const isATM = chain && call.strike === chain.atm_strike;
    const isITMCall = chain && call.strike < chain.spot_price;
    const isITMPut = chain && put.strike > chain.spot_price;

    return (
      <View
        key={call.strike}
        style={[styles.optionRow, isATM && styles.atmRow]}
      >
        {/* Call Side */}
        <TouchableOpacity
          style={[styles.callSide, isITMCall && styles.itmSide]}
          onPress={() => {
            setSelectedContract(call);
            setOrderModalVisible(true);
          }}
          data-testid={`call-${call.strike}`}
        >
          <Text style={styles.oiText}>{formatNumber(call.open_interest)}</Text>
          <Text style={[styles.oiChange, { color: getChangeColor(call.oi_change) }]}>
            {call.oi_change > 0 ? '+' : ''}{formatNumber(call.oi_change)}
          </Text>
          <Text style={styles.ivText}>{call.iv.toFixed(1)}%</Text>
          <Text style={styles.ltpText}>₹{call.ltp.toFixed(2)}</Text>
        </TouchableOpacity>

        {/* Strike */}
        <View style={[styles.strikeCell, isATM && styles.atmStrike]}>
          <Text style={[styles.strikeText, isATM && styles.atmStrikeText]}>
            {call.strike}
          </Text>
          {isATM && <Text style={styles.atmLabel}>ATM</Text>}
        </View>

        {/* Put Side */}
        <TouchableOpacity
          style={[styles.putSide, isITMPut && styles.itmSide]}
          onPress={() => {
            setSelectedContract(put);
            setOrderModalVisible(true);
          }}
          data-testid={`put-${put.strike}`}
        >
          <Text style={styles.ltpText}>₹{put.ltp.toFixed(2)}</Text>
          <Text style={styles.ivText}>{put.iv.toFixed(1)}%</Text>
          <Text style={[styles.oiChange, { color: getChangeColor(put.oi_change) }]}>
            {put.oi_change > 0 ? '+' : ''}{formatNumber(put.oi_change)}
          </Text>
          <Text style={styles.oiText}>{formatNumber(put.open_interest)}</Text>
        </TouchableOpacity>
      </View>
    );
  };

  const renderSignalView = () => {
    if (!signal) return null;

    const directionColor = signal.direction === 'BULLISH' ? colors.bullish :
      signal.direction === 'BEARISH' ? colors.bearish : colors.neutral;

    return (
      <View style={styles.signalContainer}>
        <View style={styles.signalHeader}>
          <View style={[styles.directionBadge, { backgroundColor: directionColor }]}>
            <Text style={styles.directionText}>{signal.direction}</Text>
          </View>
          <Text style={styles.confidenceText}>{signal.confidence.toFixed(1)}% Confidence</Text>
        </View>

        <View style={styles.signalMetrics}>
          <View style={styles.metricCard}>
            <Text style={styles.metricLabel}>PCR</Text>
            <Text style={styles.metricValue}>{signal.pcr.toFixed(2)}</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricLabel}>Support</Text>
            <Text style={[styles.metricValue, { color: colors.bullish }]}>{signal.support}</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricLabel}>Resistance</Text>
            <Text style={[styles.metricValue, { color: colors.bearish }]}>{signal.resistance}</Text>
          </View>
        </View>

        {signal.recommendation && (
          <View style={styles.recommendationCard}>
            <Text style={styles.recommendationTitle}>Recommended Trade</Text>
            <Text style={styles.primaryTrade}>{signal.recommendation.primary}</Text>
            <Text style={styles.alternativeTrade}>Alt: {signal.recommendation.alternative}</Text>
            <Text style={styles.strategyText}>{signal.recommendation.strategy}</Text>
          </View>
        )}

        {chain && (
          <View style={styles.spotInfo}>
            <Text style={styles.spotLabel}>Spot Price</Text>
            <Text style={styles.spotValue}>₹{chain.spot_price.toFixed(2)}</Text>
            <Text style={styles.spotLabel}>Max Pain</Text>
            <Text style={styles.spotValue}>{chain.max_pain}</Text>
          </View>
        )}
      </View>
    );
  };

  return (
    <View style={styles.container} data-testid="options-tab">
      {/* Underlying Selector */}
      <View style={styles.underlyingSelector}>
        {['NIFTY', 'BANKNIFTY'].map((sym) => (
          <TouchableOpacity
            key={sym}
            style={[styles.underlyingBtn, underlying === sym && styles.underlyingBtnActive]}
            onPress={() => setUnderlying(sym)}
            data-testid={`underlying-${sym.toLowerCase()}`}
          >
            <Text style={[styles.underlyingBtnText, underlying === sym && styles.underlyingBtnTextActive]}>
              {sym}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Live Indicator Bar */}
      <View style={styles.liveIndicatorBar}>
        <View style={styles.liveStatusContainer}>
          {chain && (
            <>
              <View style={[styles.liveIndicator, chain.is_live ? styles.liveIndicatorOn : styles.liveIndicatorOff]} />
              <Text style={styles.liveStatusText}>
                {chain.is_live ? 'LIVE' : 'SIMULATED'}
              </Text>
              <Text style={styles.spotPriceText}>
                ₹{chain.spot_price.toFixed(2)}
              </Text>
              {chain.price_source && (
                <Text style={styles.priceSourceText}>
                  ({chain.price_source})
                </Text>
              )}
            </>
          )}
          {isRefreshing && (
            <ActivityIndicator size="small" color={colors.primary} style={styles.refreshingIndicator} />
          )}
        </View>
        
        <TouchableOpacity
          style={[styles.autoRefreshBtn, autoRefresh && styles.autoRefreshBtnActive]}
          onPress={() => setAutoRefresh(!autoRefresh)}
          data-testid="auto-refresh-toggle"
        >
          <Text style={[styles.autoRefreshBtnText, autoRefresh && styles.autoRefreshBtnTextActive]}>
            {autoRefresh ? '⟳ AUTO' : '⟳ OFF'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Last Refresh Time */}
      {lastRefreshTime && (
        <Text style={styles.lastRefreshText}>
          Last update: {lastRefreshTime.toLocaleTimeString()}
        </Text>
      )}

      {/* Expiry Selector */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.expiryScroll}>
        {expiries.map((exp) => (
          <TouchableOpacity
            key={exp}
            style={[styles.expiryBtn, selectedExpiry === exp && styles.expiryBtnActive]}
            onPress={() => setSelectedExpiry(exp)}
            data-testid={`expiry-${exp}`}
          >
            <Text style={[styles.expiryBtnText, selectedExpiry === exp && styles.expiryBtnTextActive]}>
              {new Date(exp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* View Mode Toggle */}
      <View style={styles.viewToggle}>
        <TouchableOpacity
          style={[styles.toggleBtn, viewMode === 'chain' && styles.toggleBtnActive]}
          onPress={() => setViewMode('chain')}
          data-testid="view-chain"
        >
          <Text style={[styles.toggleBtnText, viewMode === 'chain' && styles.toggleBtnTextActive]}>
            Chain
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.toggleBtn, viewMode === 'signal' && styles.toggleBtnActive]}
          onPress={() => setViewMode('signal')}
          data-testid="view-signal"
        >
          <Text style={[styles.toggleBtnText, viewMode === 'signal' && styles.toggleBtnTextActive]}>
            Signal
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : viewMode === 'chain' ? (
        <>
          {/* Chain Header */}
          <View style={styles.chainHeader}>
            <View style={styles.callHeader}>
              <Text style={styles.headerText}>OI</Text>
              <Text style={styles.headerText}>Chg</Text>
              <Text style={styles.headerText}>IV</Text>
              <Text style={styles.headerText}>CE</Text>
            </View>
            <Text style={styles.strikeHeader}>STRIKE</Text>
            <View style={styles.putHeader}>
              <Text style={styles.headerText}>PE</Text>
              <Text style={styles.headerText}>IV</Text>
              <Text style={styles.headerText}>Chg</Text>
              <Text style={styles.headerText}>OI</Text>
            </View>
          </View>

          {/* Options Chain */}
          <ScrollView style={styles.chainScroll}>
            {chain && chain.calls.map((call, idx) => {
              const put = chain.puts[idx];
              if (!put) return null;
              return renderOptionRow(call, put);
            })}
            <View style={{ height: 20 }} />
          </ScrollView>
        </>
      ) : (
        renderSignalView()
      )}

      {/* Order Modal */}
      <Modal
        visible={orderModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setOrderModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>
              {underlying} {selectedContract?.strike} {selectedContract?.option_type}
            </Text>

            <View style={styles.contractInfo}>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>LTP</Text>
                <Text style={styles.infoValue}>₹{selectedContract?.ltp.toFixed(2)}</Text>
              </View>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>IV</Text>
                <Text style={styles.infoValue}>{selectedContract?.iv.toFixed(1)}%</Text>
              </View>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Delta</Text>
                <Text style={styles.infoValue}>{selectedContract?.delta.toFixed(4)}</Text>
              </View>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Theta</Text>
                <Text style={styles.infoValue}>{selectedContract?.theta.toFixed(2)}</Text>
              </View>
            </View>

            <View style={styles.sideSelector}>
              <TouchableOpacity
                style={[styles.sideBtn, orderSide === 'BUY' && styles.buyBtnActive]}
                onPress={() => setOrderSide('BUY')}
                data-testid="side-buy"
              >
                <Text style={[styles.sideBtnText, orderSide === 'BUY' && styles.sideBtnTextActive]}>BUY</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.sideBtn, orderSide === 'SELL' && styles.sellBtnActive]}
                onPress={() => setOrderSide('SELL')}
                data-testid="side-sell"
              >
                <Text style={[styles.sideBtnText, orderSide === 'SELL' && styles.sideBtnTextActive]}>SELL</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.quantityContainer}>
              <Text style={styles.quantityLabel}>Lots</Text>
              <View style={styles.quantityInput}>
                <TouchableOpacity
                  style={styles.quantityBtn}
                  onPress={() => setOrderQuantity(String(Math.max(1, parseInt(orderQuantity) - 1)))}
                >
                  <Text style={styles.quantityBtnText}>-</Text>
                </TouchableOpacity>
                <TextInput
                  style={styles.quantityTextInput}
                  value={orderQuantity}
                  onChangeText={setOrderQuantity}
                  keyboardType="numeric"
                  data-testid="lots-input"
                />
                <TouchableOpacity
                  style={styles.quantityBtn}
                  onPress={() => setOrderQuantity(String(parseInt(orderQuantity) + 1))}
                >
                  <Text style={styles.quantityBtnText}>+</Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.premiumInfo}>
              <Text style={styles.premiumLabel}>Total Premium</Text>
              <Text style={styles.premiumValue}>
                ₹{((selectedContract?.ltp || 0) * (underlying === 'NIFTY' ? 25 : 15) * (parseInt(orderQuantity) || 1)).toFixed(2)}
              </Text>
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.cancelBtn]}
                onPress={() => setOrderModalVisible(false)}
                data-testid="cancel-order"
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, orderSide === 'BUY' ? styles.confirmBuyBtn : styles.confirmSellBtn]}
                onPress={handlePlaceOrder}
                data-testid="confirm-order"
              >
                <Text style={styles.confirmBtnText}>
                  {appMode === 'live' ? `${orderSide} (LIVE)` : `${orderSide} (DEMO)`}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: spacing.sm,
  },
  underlyingSelector: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  underlyingBtn: {
    flex: 1,
    paddingVertical: 10,
    backgroundColor: colors.bgTertiary,
    borderRadius: 6,
    marginHorizontal: 4,
    alignItems: 'center',
  },
  underlyingBtnActive: {
    backgroundColor: colors.primary,
  },
  underlyingBtnText: {
    color: colors.textSecondary,
    fontWeight: '600',
    fontSize: 14,
  },
  underlyingBtnTextActive: {
    color: 'white',
  },
  liveIndicatorBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    padding: spacing.sm,
    borderRadius: 6,
    marginBottom: spacing.xs,
  },
  liveStatusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  liveIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  liveIndicatorOn: {
    backgroundColor: '#22c55e',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 4,
  },
  liveIndicatorOff: {
    backgroundColor: '#f59e0b',
  },
  liveStatusText: {
    color: colors.text,
    fontSize: 10,
    fontWeight: '700',
    marginRight: 8,
  },
  spotPriceText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  priceSourceText: {
    color: colors.textMuted,
    fontSize: 10,
    marginLeft: 4,
  },
  refreshingIndicator: {
    marginLeft: 8,
  },
  autoRefreshBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: colors.bgTertiary,
    borderRadius: 4,
  },
  autoRefreshBtnActive: {
    backgroundColor: colors.primary,
  },
  autoRefreshBtnText: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: '600',
  },
  autoRefreshBtnTextActive: {
    color: 'white',
  },
  lastRefreshText: {
    color: colors.textMuted,
    fontSize: 9,
    textAlign: 'right',
    marginBottom: spacing.xs,
  },
  expiryScroll: {
    marginBottom: spacing.sm,
    maxHeight: 40,
  },
  expiryBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: colors.bgCard,
    borderRadius: 4,
    marginRight: 8,
  },
  expiryBtnActive: {
    backgroundColor: colors.primary,
  },
  expiryBtnText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '500',
  },
  expiryBtnTextActive: {
    color: 'white',
  },
  viewToggle: {
    flexDirection: 'row',
    backgroundColor: colors.bgTertiary,
    borderRadius: 6,
    padding: 2,
    marginBottom: spacing.sm,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 4,
  },
  toggleBtnActive: {
    backgroundColor: colors.bgCard,
  },
  toggleBtnText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  toggleBtnTextActive: {
    color: colors.text,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chainHeader: {
    flexDirection: 'row',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  callHeader: {
    flex: 2,
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  strikeHeader: {
    flex: 1,
    textAlign: 'center',
    color: colors.text,
    fontWeight: '700',
    fontSize: 11,
  },
  putHeader: {
    flex: 2,
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  headerText: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: '600',
    width: 40,
    textAlign: 'center',
  },
  chainScroll: {
    flex: 1,
  },
  optionRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  atmRow: {
    backgroundColor: colors.bgSecondary,
  },
  callSide: {
    flex: 2,
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingVertical: 10,
    backgroundColor: 'rgba(34, 197, 94, 0.05)',
  },
  putSide: {
    flex: 2,
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingVertical: 10,
    backgroundColor: 'rgba(239, 68, 68, 0.05)',
  },
  itmSide: {
    backgroundColor: 'rgba(255, 193, 7, 0.1)',
  },
  strikeCell: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
  },
  atmStrike: {
    backgroundColor: colors.primary,
  },
  strikeText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  atmStrikeText: {
    color: 'white',
  },
  atmLabel: {
    color: 'white',
    fontSize: 8,
    fontWeight: '700',
  },
  oiText: {
    color: colors.textSecondary,
    fontSize: 10,
    width: 40,
    textAlign: 'center',
    fontFamily: 'monospace',
  },
  oiChange: {
    fontSize: 9,
    width: 35,
    textAlign: 'center',
    fontFamily: 'monospace',
  },
  ivText: {
    color: colors.text,
    fontSize: 10,
    width: 35,
    textAlign: 'center',
    fontFamily: 'monospace',
  },
  ltpText: {
    color: colors.text,
    fontSize: 11,
    fontWeight: '600',
    width: 50,
    textAlign: 'center',
    fontFamily: 'monospace',
  },
  signalContainer: {
    flex: 1,
    padding: spacing.md,
  },
  signalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  directionBadge: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
  },
  directionText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '700',
  },
  confidenceText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  signalMetrics: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  metricCard: {
    flex: 1,
    backgroundColor: colors.bgCard,
    padding: spacing.md,
    borderRadius: 8,
    marginHorizontal: 4,
    alignItems: 'center',
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 11,
    marginBottom: 4,
  },
  metricValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  recommendationCard: {
    backgroundColor: colors.bgCard,
    padding: spacing.md,
    borderRadius: 8,
    marginBottom: spacing.md,
  },
  recommendationTitle: {
    color: colors.textMuted,
    fontSize: 11,
    marginBottom: spacing.sm,
  },
  primaryTrade: {
    color: colors.primary,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  alternativeTrade: {
    color: colors.textSecondary,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  strategyText: {
    color: colors.textMuted,
    fontSize: 12,
    fontStyle: 'italic',
  },
  spotInfo: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: colors.bgCard,
    padding: spacing.md,
    borderRadius: 8,
  },
  spotLabel: {
    color: colors.textMuted,
    fontSize: 11,
  },
  spotValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.bgSecondary,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: spacing.lg,
  },
  modalTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  contractInfo: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  infoLabel: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  infoValue: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  sideSelector: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  sideBtn: {
    flex: 1,
    paddingVertical: 12,
    backgroundColor: colors.bgTertiary,
    borderRadius: 6,
    marginHorizontal: 4,
    alignItems: 'center',
  },
  buyBtnActive: {
    backgroundColor: colors.bullish,
  },
  sellBtnActive: {
    backgroundColor: colors.bearish,
  },
  sideBtnText: {
    color: colors.textSecondary,
    fontSize: 14,
    fontWeight: '600',
  },
  sideBtnTextActive: {
    color: 'white',
  },
  quantityContainer: {
    marginBottom: spacing.md,
  },
  quantityLabel: {
    color: colors.textSecondary,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  quantityInput: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgTertiary,
    borderRadius: 8,
  },
  quantityBtn: {
    width: 50,
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quantityBtnText: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '600',
  },
  quantityTextInput: {
    flex: 1,
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
    textAlign: 'center',
  },
  premiumInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginBottom: spacing.sm,
  },
  premiumLabel: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  premiumValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  modalButtons: {
    flexDirection: 'row',
  },
  modalBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  cancelBtn: {
    backgroundColor: colors.bgTertiary,
  },
  cancelBtnText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  confirmBuyBtn: {
    backgroundColor: colors.bullish,
  },
  confirmSellBtn: {
    backgroundColor: colors.bearish,
  },
  confirmBtnText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '700',
  },
});
