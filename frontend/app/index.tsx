import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  SafeAreaView,
  StatusBar,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import { useTradingStore } from '../src/store/tradingStore';
import { colors, spacing } from '../src/theme/colors';
import { CandlestickChart } from '../src/components/CandlestickChart';
import { ConfluenceGauge } from '../src/components/ConfluenceGauge';
import { IndicatorBreakdown } from '../src/components/IndicatorBreakdown';
import { QuotePanel } from '../src/components/QuotePanel';
import { RiskRewardPanel } from '../src/components/RiskRewardPanel';
import { AIValidationPanel } from '../src/components/AIValidationPanel';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

type TabType = 'signal' | 'positions' | 'orders' | 'backtest';

export default function TradingDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('signal');
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const {
    selectedSymbol,
    quote,
    candles,
    signal,
    positions,
    orders,
    limits,
    isLoading,
    simulationActive,
    fetchQuote,
    fetchCandles,
    fetchSignal,
    fetchPositions,
    fetchOrders,
    fetchLimits,
    refreshAll,
    startSimulation,
    stopSimulation,
    setSelectedSymbol,
  } = useTradingStore();

  // Initial data load
  useEffect(() => {
    refreshAll();
  }, []);

  // Auto refresh every 3 seconds when enabled
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchQuote();
        fetchCandles();
        if (activeTab === 'signal') {
          fetchSignal();
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, activeTab]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refreshAll();
    setRefreshing(false);
  }, []);

  const handleSymbolChange = (symbol: string) => {
    setSelectedSymbol(symbol);
    setTimeout(() => {
      fetchQuote();
      fetchCandles();
      fetchSignal();
    }, 100);
  };

  const renderTabs = () => (
    <View style={styles.tabBar}>
      {(['signal', 'positions', 'orders', 'backtest'] as TabType[]).map((tab) => (
        <TouchableOpacity
          key={tab}
          style={[styles.tab, activeTab === tab && styles.activeTab]}
          onPress={() => {
            setActiveTab(tab);
            if (tab === 'positions') fetchPositions();
            if (tab === 'orders') fetchOrders();
          }}
        >
          <Text style={[styles.tabText, activeTab === tab && styles.activeTabText]}>
            {tab.toUpperCase()}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderHeader = () => (
    <View style={styles.header}>
      <View>
        <Text style={styles.headerTitle}>COSTAR AlgoTrader</Text>
        <Text style={styles.headerSubtitle}>
          {simulationActive ? 'DEMO MODE - LIVE' : 'DEMO MODE'}
        </Text>
      </View>
      <View style={styles.headerRight}>
        <TouchableOpacity
          style={[
            styles.simButton,
            simulationActive && styles.simButtonActive,
          ]}
          onPress={() => simulationActive ? stopSimulation() : startSimulation()}
        >
          <Text style={styles.simButtonText}>
            {simulationActive ? 'STOP' : 'START'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.autoRefreshBtn, autoRefresh && styles.autoRefreshActive]}
          onPress={() => setAutoRefresh(!autoRefresh)}
        >
          <Text style={styles.autoRefreshText}>
            {autoRefresh ? 'AUTO' : 'MANUAL'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderSymbolSelector = () => (
    <View style={styles.symbolSelector}>
      {['NIFTY', 'BANKNIFTY'].map((symbol) => (
        <TouchableOpacity
          key={symbol}
          style={[
            styles.symbolButton,
            selectedSymbol === symbol && styles.symbolButtonActive,
          ]}
          onPress={() => handleSymbolChange(symbol)}
        >
          <Text
            style={[
              styles.symbolText,
              selectedSymbol === symbol && styles.symbolTextActive,
            ]}
          >
            {symbol}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderLimitsBar = () => (
    <View style={styles.limitsBar}>
      <View style={styles.limitItem}>
        <Text style={styles.limitLabel}>Available</Text>
        <Text style={styles.limitValue}>
          ₹{limits?.available_margin?.toLocaleString() || '0'}
        </Text>
      </View>
      <View style={styles.limitItem}>
        <Text style={styles.limitLabel}>Used</Text>
        <Text style={styles.limitValue}>
          ₹{limits?.used_margin?.toLocaleString() || '0'}
        </Text>
      </View>
      <View style={styles.limitItem}>
        <Text style={styles.limitLabel}>Unrealized</Text>
        <Text
          style={[
            styles.limitValue,
            {
              color:
                (limits?.unrealized_pnl || 0) >= 0
                  ? colors.bullish
                  : colors.bearish,
            },
          ]}
        >
          ₹{limits?.unrealized_pnl?.toLocaleString() || '0'}
        </Text>
      </View>
      <View style={styles.limitItem}>
        <Text style={styles.limitLabel}>Realized</Text>
        <Text
          style={[
            styles.limitValue,
            {
              color:
                (limits?.realized_pnl || 0) >= 0
                  ? colors.bullish
                  : colors.bearish,
            },
          ]}
        >
          ₹{limits?.realized_pnl?.toLocaleString() || '0'}
        </Text>
      </View>
    </View>
  );

  const renderSignalTab = () => (
    <View style={styles.signalContainer}>
      {/* Chart Section */}
      <View style={styles.chartSection}>
        <CandlestickChart candles={candles} height={250} />
      </View>

      {/* Quote and Signal Section */}
      <View style={styles.row}>
        <View style={styles.halfColumn}>
          <QuotePanel quote={quote} onRefresh={() => fetchQuote()} />
        </View>
        <View style={styles.halfColumn}>
          {signal && (
            <ConfluenceGauge
              score={signal.score}
              direction={signal.direction}
              confidence={signal.confidence}
              indicatorsAgreeing={signal.indicators_agreeing}
              totalIndicators={signal.total_indicators}
            />
          )}
        </View>
      </View>

      {/* Risk Reward Section */}
      {signal && signal.direction !== 'NEUTRAL' && (
        <View style={styles.section}>
          <RiskRewardPanel
            entryPrice={signal.entry_price}
            stopLoss={signal.stop_loss}
            takeProfit={signal.take_profit}
            riskReward={signal.risk_reward}
            atr={signal.atr}
            direction={signal.direction}
          />
        </View>
      )}

      {/* AI Validation Section */}
      {signal && (
        <View style={styles.section}>
          <AIValidationPanel validation={signal.ai_validation} />
        </View>
      )}

      {/* Indicator Breakdown */}
      {signal && (
        <View style={[styles.section, { minHeight: 300 }]}>
          <IndicatorBreakdown votes={signal.votes} />
        </View>
      )}
    </View>
  );

  const renderPositionsTab = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>Open Positions</Text>
      {positions.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No open positions</Text>
        </View>
      ) : (
        positions.map((pos, index) => (
          <View key={index} style={styles.positionCard}>
            <View style={styles.positionHeader}>
              <Text style={styles.positionSymbol}>{pos.symbol}</Text>
              <Text
                style={[
                  styles.positionQty,
                  { color: pos.quantity > 0 ? colors.bullish : colors.bearish },
                ]}
              >
                {pos.quantity > 0 ? 'LONG' : 'SHORT'} {Math.abs(pos.quantity)}
              </Text>
            </View>
            <View style={styles.positionDetails}>
              <View style={styles.positionItem}>
                <Text style={styles.positionLabel}>Avg Price</Text>
                <Text style={styles.positionValue}>{pos.avg_price.toFixed(2)}</Text>
              </View>
              <View style={styles.positionItem}>
                <Text style={styles.positionLabel}>Current</Text>
                <Text style={styles.positionValue}>
                  {pos.current_price.toFixed(2)}
                </Text>
              </View>
              <View style={styles.positionItem}>
                <Text style={styles.positionLabel}>P&L</Text>
                <Text
                  style={[
                    styles.positionValue,
                    { color: pos.pnl >= 0 ? colors.bullish : colors.bearish },
                  ]}
                >
                  {pos.pnl >= 0 ? '+' : ''}
                  {pos.pnl.toFixed(2)} ({pos.pnl_percent.toFixed(2)}%)
                </Text>
              </View>
            </View>
          </View>
        ))
      )}
    </View>
  );

  const renderOrdersTab = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>Order Book</Text>
      {orders.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No orders</Text>
        </View>
      ) : (
        orders.map((order, index) => (
          <View key={index} style={styles.orderCard}>
            <View style={styles.orderHeader}>
              <Text style={styles.orderSymbol}>{order.symbol}</Text>
              <View
                style={[
                  styles.orderStatusBadge,
                  {
                    backgroundColor:
                      order.status === 'EXECUTED'
                        ? colors.bullish
                        : order.status === 'PENDING'
                        ? colors.warning
                        : colors.bearish,
                  },
                ]}
              >
                <Text style={styles.orderStatusText}>{order.status}</Text>
              </View>
            </View>
            <View style={styles.orderDetails}>
              <Text
                style={[
                  styles.orderSide,
                  { color: order.side === 'BUY' ? colors.bullish : colors.bearish },
                ]}
              >
                {order.side} {order.quantity}
              </Text>
              <Text style={styles.orderType}>{order.order_type}</Text>
              <Text style={styles.orderPrice}>
                {order.fill_price > 0
                  ? `Filled @ ${order.fill_price.toFixed(2)}`
                  : order.price > 0
                  ? `@ ${order.price.toFixed(2)}`
                  : 'MKT'}
              </Text>
            </View>
          </View>
        ))
      )}
    </View>
  );

  const renderBacktestTab = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>Backtesting</Text>
      <BacktestPanel />
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
      {renderHeader()}
      {renderSymbolSelector()}
      {renderLimitsBar()}
      {renderTabs()}

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {isLoading && !refreshing && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color={colors.primary} />
          </View>
        )}

        {activeTab === 'signal' && renderSignalTab()}
        {activeTab === 'positions' && renderPositionsTab()}
        {activeTab === 'orders' && renderOrdersTab()}
        {activeTab === 'backtest' && renderBacktestTab()}

        <View style={{ height: 50 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// Backtest Panel Component
function BacktestPanel() {
  const { selectedSymbol, backtestResult, isLoading, runBacktest } = useTradingStore();
  const [minScore, setMinScore] = useState(3);
  const [minAgree, setMinAgree] = useState(5);

  const handleRunBacktest = () => {
    runBacktest({
      symbol: selectedSymbol,
      candles: 200,
      min_score: minScore,
      min_agree: minAgree,
      lot_size: selectedSymbol === 'NIFTY' ? 25 : 15,
      position_size: 1,
    });
  };

  return (
    <View style={btStyles.container}>
      <View style={btStyles.configRow}>
        <View style={btStyles.configItem}>
          <Text style={btStyles.configLabel}>Min Score</Text>
          <View style={btStyles.stepper}>
            <TouchableOpacity
              style={btStyles.stepperBtn}
              onPress={() => setMinScore(Math.max(1, minScore - 0.5))}
            >
              <Text style={btStyles.stepperText}>-</Text>
            </TouchableOpacity>
            <Text style={btStyles.stepperValue}>{minScore}</Text>
            <TouchableOpacity
              style={btStyles.stepperBtn}
              onPress={() => setMinScore(Math.min(8, minScore + 0.5))}
            >
              <Text style={btStyles.stepperText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={btStyles.configItem}>
          <Text style={btStyles.configLabel}>Min Agree</Text>
          <View style={btStyles.stepper}>
            <TouchableOpacity
              style={btStyles.stepperBtn}
              onPress={() => setMinAgree(Math.max(1, minAgree - 1))}
            >
              <Text style={btStyles.stepperText}>-</Text>
            </TouchableOpacity>
            <Text style={btStyles.stepperValue}>{minAgree}</Text>
            <TouchableOpacity
              style={btStyles.stepperBtn}
              onPress={() => setMinAgree(Math.min(10, minAgree + 1))}
            >
              <Text style={btStyles.stepperText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      <TouchableOpacity
        style={[btStyles.runButton, isLoading && btStyles.runButtonDisabled]}
        onPress={handleRunBacktest}
        disabled={isLoading}
      >
        {isLoading ? (
          <ActivityIndicator size="small" color="white" />
        ) : (
          <Text style={btStyles.runButtonText}>RUN BACKTEST</Text>
        )}
      </TouchableOpacity>

      {backtestResult && (
        <View style={btStyles.results}>
          <Text style={btStyles.resultsTitle}>Backtest Results</Text>

          <View style={btStyles.statsGrid}>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Total Trades</Text>
              <Text style={btStyles.statValue}>{backtestResult.total_trades}</Text>
            </View>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Win Rate</Text>
              <Text
                style={[
                  btStyles.statValue,
                  {
                    color:
                      backtestResult.win_rate >= 50
                        ? colors.bullish
                        : colors.bearish,
                  },
                ]}
              >
                {backtestResult.win_rate.toFixed(1)}%
              </Text>
            </View>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Total P&L</Text>
              <Text
                style={[
                  btStyles.statValue,
                  {
                    color:
                      backtestResult.total_pnl >= 0
                        ? colors.bullish
                        : colors.bearish,
                  },
                ]}
              >
                ₹{backtestResult.total_pnl.toLocaleString()}
              </Text>
            </View>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Max DD</Text>
              <Text style={[btStyles.statValue, { color: colors.bearish }]}>
                {backtestResult.max_drawdown.toFixed(1)}%
              </Text>
            </View>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Profit Factor</Text>
              <Text style={btStyles.statValue}>
                {typeof backtestResult.profit_factor === 'number'
                  ? backtestResult.profit_factor.toFixed(2)
                  : backtestResult.profit_factor}
              </Text>
            </View>
            <View style={btStyles.statItem}>
              <Text style={btStyles.statLabel}>Avg P&L</Text>
              <Text
                style={[
                  btStyles.statValue,
                  {
                    color:
                      backtestResult.avg_pnl >= 0
                        ? colors.bullish
                        : colors.bearish,
                  },
                ]}
              >
                ₹{backtestResult.avg_pnl.toFixed(0)}
              </Text>
            </View>
          </View>

          <View style={btStyles.breakdown}>
            <Text style={btStyles.breakdownLabel}>Win/Loss</Text>
            <Text style={btStyles.breakdownValue}>
              <Text style={{ color: colors.bullish }}>
                {backtestResult.winning_trades}W
              </Text>
              {' / '}
              <Text style={{ color: colors.bearish }}>
                {backtestResult.losing_trades}L
              </Text>
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.bgSecondary,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  headerSubtitle: {
    color: colors.warning,
    fontSize: 10,
    fontWeight: '600',
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  simButton: {
    backgroundColor: colors.bgTertiary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
    marginRight: 8,
  },
  simButtonActive: {
    backgroundColor: colors.bullish,
  },
  simButtonText: {
    color: colors.text,
    fontSize: 11,
    fontWeight: '600',
  },
  autoRefreshBtn: {
    backgroundColor: colors.bgTertiary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 4,
  },
  autoRefreshActive: {
    backgroundColor: colors.primary,
  },
  autoRefreshText: {
    color: colors.text,
    fontSize: 10,
    fontWeight: '600',
  },
  symbolSelector: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.bgSecondary,
  },
  symbolButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginRight: 8,
    borderRadius: 4,
    backgroundColor: colors.bgTertiary,
  },
  symbolButtonActive: {
    backgroundColor: colors.primary,
  },
  symbolText: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  symbolTextActive: {
    color: colors.text,
  },
  limitsBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.bgCard,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  limitItem: {
    alignItems: 'center',
  },
  limitLabel: {
    color: colors.textMuted,
    fontSize: 9,
  },
  limitValue: {
    color: colors.text,
    fontSize: 11,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.bgSecondary,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  activeTab: {
    borderBottomColor: colors.primary,
  },
  tabText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  activeTabText: {
    color: colors.primary,
  },
  content: {
    flex: 1,
  },
  loadingOverlay: {
    padding: 20,
    alignItems: 'center',
  },
  signalContainer: {
    padding: spacing.md,
  },
  chartSection: {
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  halfColumn: {
    flex: 1,
    marginRight: spacing.sm,
  },
  section: {
    marginBottom: spacing.md,
  },
  tabContent: {
    padding: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
    marginBottom: spacing.md,
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: 8,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 14,
  },
  positionCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  positionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  positionSymbol: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  positionQty: {
    fontSize: 14,
    fontWeight: '600',
  },
  positionDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  positionItem: {
    alignItems: 'center',
  },
  positionLabel: {
    color: colors.textMuted,
    fontSize: 10,
  },
  positionValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '500',
    fontFamily: 'monospace',
  },
  orderCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  orderSymbol: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  orderStatusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  orderStatusText: {
    color: 'white',
    fontSize: 10,
    fontWeight: '600',
  },
  orderDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  orderSide: {
    fontSize: 12,
    fontWeight: '600',
  },
  orderType: {
    color: colors.textSecondary,
    fontSize: 12,
  },
  orderPrice: {
    color: colors.text,
    fontSize: 12,
    fontFamily: 'monospace',
  },
});

const btStyles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: spacing.md,
  },
  configRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: spacing.md,
  },
  configItem: {
    alignItems: 'center',
  },
  configLabel: {
    color: colors.textSecondary,
    fontSize: 12,
    marginBottom: 8,
  },
  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgTertiary,
    borderRadius: 4,
  },
  stepperBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepperText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  stepperValue: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
    minWidth: 40,
    textAlign: 'center',
  },
  runButton: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: 6,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  runButtonDisabled: {
    opacity: 0.6,
  },
  runButtonText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '700',
  },
  results: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  resultsTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: spacing.md,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  statItem: {
    width: '30%',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: 2,
  },
  statValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  breakdown: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  breakdownLabel: {
    color: colors.textSecondary,
    fontSize: 12,
    marginRight: 8,
  },
  breakdownValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
});
