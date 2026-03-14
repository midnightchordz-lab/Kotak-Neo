import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors } from '../theme/colors';
import { Quote } from '../store/tradingStore';

interface QuotePanelProps {
  quote: Quote | null;
  onRefresh?: () => void;
}

export const QuotePanel: React.FC<QuotePanelProps> = ({ quote, onRefresh }) => {
  if (!quote) {
    return (
      <View style={styles.container}>
        <Text style={styles.noData}>Loading quote...</Text>
      </View>
    );
  }

  const isPositive = quote.change >= 0;
  const changeColor = isPositive ? colors.bullish : colors.bearish;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.symbol}>{quote.symbol}</Text>
        <View style={[styles.lotBadge, { backgroundColor: colors.bgTertiary }]}>
          <Text style={styles.lotText}>Lot: {quote.lot_size}</Text>
        </View>
      </View>

      <View style={styles.priceRow}>
        <Text style={styles.ltp}>{quote.ltp.toFixed(2)}</Text>
        <View style={styles.changeContainer}>
          <Text style={[styles.change, { color: changeColor }]}>
            {isPositive ? '+' : ''}{quote.change.toFixed(2)}
          </Text>
          <Text style={[styles.changePercent, { color: changeColor }]}>
            ({isPositive ? '+' : ''}{quote.change_percent.toFixed(2)}%)
          </Text>
        </View>
      </View>

      <View style={styles.statsGrid}>
        <View style={styles.statItem}>
          <Text style={styles.statLabel}>Open</Text>
          <Text style={styles.statValue}>{quote.open.toFixed(2)}</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.statLabel}>High</Text>
          <Text style={[styles.statValue, { color: colors.bullish }]}>
            {quote.high.toFixed(2)}
          </Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.statLabel}>Low</Text>
          <Text style={[styles.statValue, { color: colors.bearish }]}>
            {quote.low.toFixed(2)}
          </Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.statLabel}>Volume</Text>
          <Text style={styles.statValue}>
            {(quote.volume / 1000).toFixed(0)}K
          </Text>
        </View>
      </View>

      <View style={styles.bidAskContainer}>
        <View style={styles.bidAskItem}>
          <Text style={styles.bidLabel}>BID</Text>
          <Text style={[styles.bidValue, { color: colors.bullish }]}>
            {quote.bid.toFixed(2)}
          </Text>
          <Text style={styles.bidQty}>{quote.bid_qty}</Text>
        </View>
        <View style={styles.spread}>
          <Text style={styles.spreadLabel}>SPREAD</Text>
          <Text style={styles.spreadValue}>
            {(quote.ask - quote.bid).toFixed(2)}
          </Text>
        </View>
        <View style={styles.bidAskItem}>
          <Text style={styles.askLabel}>ASK</Text>
          <Text style={[styles.askValue, { color: colors.bearish }]}>
            {quote.ask.toFixed(2)}
          </Text>
          <Text style={styles.bidQty}>{quote.ask_qty}</Text>
        </View>
      </View>

      {onRefresh && (
        <TouchableOpacity style={styles.refreshBtn} onPress={onRefresh}>
          <Text style={styles.refreshText}>↻ Refresh</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: 12,
  },
  noData: {
    color: colors.textMuted,
    textAlign: 'center',
    padding: 20,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  symbol: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  lotBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  lotText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontFamily: 'monospace',
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 12,
  },
  ltp: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  changeContainer: {
    flexDirection: 'row',
    marginLeft: 12,
  },
  change: {
    fontSize: 14,
    fontWeight: '600',
  },
  changePercent: {
    fontSize: 14,
    marginLeft: 4,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  statItem: {
    alignItems: 'center',
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: 2,
  },
  statValue: {
    color: colors.text,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  bidAskContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
  },
  bidAskItem: {
    alignItems: 'center',
    flex: 1,
  },
  bidLabel: {
    color: colors.bullish,
    fontSize: 10,
    fontWeight: '600',
  },
  askLabel: {
    color: colors.bearish,
    fontSize: 10,
    fontWeight: '600',
  },
  bidValue: {
    fontSize: 14,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  askValue: {
    fontSize: 14,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  bidQty: {
    color: colors.textMuted,
    fontSize: 10,
  },
  spread: {
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  spreadLabel: {
    color: colors.textMuted,
    fontSize: 9,
  },
  spreadValue: {
    color: colors.textSecondary,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  refreshBtn: {
    marginTop: 12,
    alignItems: 'center',
  },
  refreshText: {
    color: colors.primary,
    fontSize: 12,
  },
});
