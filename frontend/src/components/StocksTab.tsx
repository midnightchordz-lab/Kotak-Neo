import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Modal,
  Alert,
} from 'react-native';
import { colors, spacing } from '../theme/colors';
import { useTradingStore, WatchlistItem } from '../store/tradingStore';

interface StocksTabProps {
  appMode: 'demo' | 'live';
}

export const StocksTab: React.FC<StocksTabProps> = ({ appMode }) => {
  const {
    stocksWatchlist,
    selectedSymbol,
    signal,
    quote,
    isLoading,
    setSelectedSymbol,
    fetchStocksWatchlist,
    fetchQuote,
    fetchSignal,
    fetchCandles,
    placeOrder,
  } = useTradingStore();

  const [selectedStock, setSelectedStock] = useState<WatchlistItem | null>(null);
  const [orderModalVisible, setOrderModalVisible] = useState(false);
  const [orderQuantity, setOrderQuantity] = useState('1');
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');

  useEffect(() => {
    fetchStocksWatchlist();
  }, []);

  const handleStockSelect = (stock: WatchlistItem) => {
    setSelectedStock(stock);
    setSelectedSymbol(stock.symbol);
    setTimeout(() => {
      fetchQuote();
      fetchSignal();
      fetchCandles();
    }, 100);
  };

  const handlePlaceOrder = async () => {
    if (!selectedStock) return;

    const qty = parseInt(orderQuantity) || 1;
    
    if (appMode === 'live') {
      Alert.alert(
        `Confirm ${orderSide} Order`,
        `Place ${orderSide} order for ${qty} shares of ${selectedStock.symbol}?\n\nThis is a LIVE CNC (delivery) order!`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Confirm',
            style: orderSide === 'BUY' ? 'default' : 'destructive',
            onPress: async () => {
              try {
                const result = await placeOrder(orderSide, qty, 'MKT', 0, 'CNC');
                Alert.alert('Order Placed', `Order ID: ${result.order_id}`);
                setOrderModalVisible(false);
              } catch (error: any) {
                Alert.alert('Order Failed', error.message);
              }
            },
          },
        ]
      );
    } else {
      try {
        const result = await placeOrder(orderSide, qty, 'MKT', 0, 'CNC');
        Alert.alert('Demo Order Placed', `Order ID: ${result.order_id}\n\nThis is a simulated CNC order.`);
        setOrderModalVisible(false);
      } catch (error: any) {
        Alert.alert('Order Failed', error.message);
      }
    }
  };

  const getSignalColor = (direction: string) => {
    if (direction === 'BUY') return colors.bullish;
    if (direction === 'SELL') return colors.bearish;
    return colors.neutral;
  };

  const renderStockCard = (stock: WatchlistItem) => {
    const isSelected = selectedSymbol === stock.symbol;
    const changeColor = stock.change_percent >= 0 ? colors.bullish : colors.bearish;

    return (
      <TouchableOpacity
        key={stock.symbol}
        style={[styles.stockCard, isSelected && styles.stockCardSelected]}
        onPress={() => handleStockSelect(stock)}
        data-testid={`stock-card-${stock.symbol.toLowerCase()}`}
      >
        <View style={styles.stockHeader}>
          <Text style={styles.stockSymbol}>{stock.symbol}</Text>
          <View style={[styles.productBadge, { backgroundColor: colors.primary }]}>
            <Text style={styles.productBadgeText}>CNC</Text>
          </View>
        </View>
        
        <View style={styles.stockPriceRow}>
          <Text style={styles.stockPrice}>₹{stock.ltp.toFixed(2)}</Text>
          <Text style={[styles.stockChange, { color: changeColor }]}>
            {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent.toFixed(2)}%
          </Text>
        </View>

        {isSelected && signal && (
          <View style={styles.signalRow}>
            <View style={[styles.signalBadge, { backgroundColor: getSignalColor(signal.direction) }]}>
              <Text style={styles.signalText}>{signal.direction}</Text>
            </View>
            <Text style={styles.signalScore}>Score: {signal.score}</Text>
          </View>
        )}

        {isSelected && (
          <View style={styles.actionButtons}>
            <TouchableOpacity
              style={[styles.actionBtn, styles.buyBtn]}
              onPress={() => {
                setOrderSide('BUY');
                setOrderModalVisible(true);
              }}
              data-testid={`buy-btn-${stock.symbol.toLowerCase()}`}
            >
              <Text style={styles.actionBtnText}>BUY</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionBtn, styles.sellBtn]}
              onPress={() => {
                setOrderSide('SELL');
                setOrderModalVisible(true);
              }}
              data-testid={`sell-btn-${stock.symbol.toLowerCase()}`}
            >
              <Text style={styles.actionBtnText}>SELL</Text>
            </TouchableOpacity>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container} data-testid="stocks-tab">
      <View style={styles.header}>
        <Text style={styles.title}>Stocks Watchlist</Text>
        <TouchableOpacity 
          style={styles.refreshBtn}
          onPress={fetchStocksWatchlist}
          data-testid="refresh-stocks-btn"
        >
          <Text style={styles.refreshBtnText}>Refresh</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.subtitle}>
        {stocksWatchlist.length} stocks available for CNC (delivery) trading
      </Text>

      {isLoading && stocksWatchlist.length === 0 ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <ScrollView 
          style={styles.stocksList}
          showsVerticalScrollIndicator={false}
        >
          {stocksWatchlist.map(renderStockCard)}
          <View style={{ height: 20 }} />
        </ScrollView>
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
              {orderSide} {selectedStock?.symbol}
            </Text>
            
            <View style={styles.modalInfo}>
              <Text style={styles.modalInfoLabel}>Current Price</Text>
              <Text style={styles.modalInfoValue}>₹{selectedStock?.ltp.toFixed(2)}</Text>
            </View>

            <View style={styles.modalInfo}>
              <Text style={styles.modalInfoLabel}>Product Type</Text>
              <Text style={styles.modalInfoValue}>CNC (Delivery)</Text>
            </View>

            <View style={styles.quantityContainer}>
              <Text style={styles.quantityLabel}>Quantity</Text>
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
                  data-testid="order-quantity-input"
                />
                <TouchableOpacity
                  style={styles.quantityBtn}
                  onPress={() => setOrderQuantity(String(parseInt(orderQuantity) + 1))}
                >
                  <Text style={styles.quantityBtnText}>+</Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.estimateContainer}>
              <Text style={styles.estimateLabel}>Estimated Value</Text>
              <Text style={styles.estimateValue}>
                ₹{((selectedStock?.ltp || 0) * (parseInt(orderQuantity) || 0)).toFixed(2)}
              </Text>
            </View>

            {signal && signal.direction !== 'NEUTRAL' && (
              <View style={[styles.signalHint, { backgroundColor: getSignalColor(signal.direction) + '20' }]}>
                <Text style={[styles.signalHintText, { color: getSignalColor(signal.direction) }]}>
                  Signal: {signal.direction} (Score: {signal.score}, Confidence: {signal.confidence}%)
                </Text>
              </View>
            )}

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.cancelBtn]}
                onPress={() => setOrderModalVisible(false)}
                data-testid="cancel-order-btn"
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.modalBtn,
                  orderSide === 'BUY' ? styles.confirmBuyBtn : styles.confirmSellBtn
                ]}
                onPress={handlePlaceOrder}
                data-testid="confirm-order-btn"
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
    padding: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 12,
    marginBottom: spacing.md,
  },
  refreshBtn: {
    backgroundColor: colors.bgTertiary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
  },
  refreshBtnText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
  },
  stocksList: {
    flex: 1,
  },
  stockCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  stockCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.bgSecondary,
  },
  stockHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  stockSymbol: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  productBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  productBadgeText: {
    color: 'white',
    fontSize: 10,
    fontWeight: '600',
  },
  stockPriceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  stockPrice: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
    fontFamily: 'monospace',
    marginRight: spacing.sm,
  },
  stockChange: {
    fontSize: 14,
    fontWeight: '600',
  },
  signalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  signalBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
    marginRight: spacing.sm,
  },
  signalText: {
    color: 'white',
    fontSize: 11,
    fontWeight: '700',
  },
  signalScore: {
    color: colors.textSecondary,
    fontSize: 12,
  },
  actionButtons: {
    flexDirection: 'row',
    marginTop: spacing.md,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 6,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  buyBtn: {
    backgroundColor: colors.bullish,
  },
  sellBtn: {
    backgroundColor: colors.bearish,
  },
  actionBtnText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '700',
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
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  modalInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  modalInfoLabel: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  modalInfoValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  quantityContainer: {
    marginVertical: spacing.md,
  },
  quantityLabel: {
    color: colors.textSecondary,
    fontSize: 14,
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
    fontSize: 24,
    fontWeight: '600',
  },
  quantityTextInput: {
    flex: 1,
    color: colors.text,
    fontSize: 20,
    fontWeight: '600',
    textAlign: 'center',
    paddingVertical: 10,
  },
  estimateContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: spacing.sm,
  },
  estimateLabel: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  estimateValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  signalHint: {
    padding: spacing.sm,
    borderRadius: 6,
    marginVertical: spacing.sm,
  },
  signalHintText: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  modalButtons: {
    flexDirection: 'row',
    marginTop: spacing.lg,
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
