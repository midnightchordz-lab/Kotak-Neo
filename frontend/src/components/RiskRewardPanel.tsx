import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';

interface RiskRewardPanelProps {
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  atr: number;
  direction: string;
}

export const RiskRewardPanel: React.FC<RiskRewardPanelProps> = ({
  entryPrice,
  stopLoss,
  takeProfit,
  riskReward,
  atr,
  direction
}) => {
  const slDistance = Math.abs(entryPrice - stopLoss);
  const tpDistance = Math.abs(takeProfit - entryPrice);
  const slPercent = (slDistance / entryPrice) * 100;
  const tpPercent = (tpDistance / entryPrice) * 100;

  const isBuy = direction === 'BUY';

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Risk Management</Text>
      
      <View style={styles.visualContainer}>
        {/* Visual representation of SL/Entry/TP */}
        <View style={styles.priceBar}>
          {isBuy ? (
            <>
              <View style={[styles.slZone, { flex: slDistance }]} />
              <View style={styles.entryLine} />
              <View style={[styles.tpZone, { flex: tpDistance }]} />
            </>
          ) : (
            <>
              <View style={[styles.tpZone, { flex: tpDistance }]} />
              <View style={styles.entryLine} />
              <View style={[styles.slZone, { flex: slDistance }]} />
            </>
          )}
        </View>
        
        <View style={styles.labelsRow}>
          <View style={styles.labelItem}>
            <Text style={styles.labelText}>SL</Text>
            <Text style={[styles.labelValue, { color: colors.bearish }]}>
              {stopLoss.toFixed(2)}
            </Text>
            <Text style={styles.labelPercent}>-{slPercent.toFixed(2)}%</Text>
          </View>
          
          <View style={styles.labelItem}>
            <Text style={styles.labelText}>ENTRY</Text>
            <Text style={styles.labelValue}>{entryPrice.toFixed(2)}</Text>
          </View>
          
          <View style={styles.labelItem}>
            <Text style={styles.labelText}>TP</Text>
            <Text style={[styles.labelValue, { color: colors.bullish }]}>
              {takeProfit.toFixed(2)}
            </Text>
            <Text style={[styles.labelPercent, { color: colors.bullish }]}>
              +{tpPercent.toFixed(2)}%
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>R:R Ratio</Text>
          <Text style={[
            styles.statValue,
            { color: riskReward >= 2 ? colors.bullish : riskReward >= 1.5 ? colors.warning : colors.bearish }
          ]}>
            1:{riskReward.toFixed(1)}
          </Text>
        </View>
        
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>ATR</Text>
          <Text style={styles.statValue}>{atr.toFixed(2)}</Text>
        </View>
        
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>SL ATR</Text>
          <Text style={styles.statValue}>{(slDistance / atr).toFixed(1)}x</Text>
        </View>
        
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>TP ATR</Text>
          <Text style={styles.statValue}>{(tpDistance / atr).toFixed(1)}x</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: 8,
    padding: 12,
  },
  title: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
  },
  visualContainer: {
    marginBottom: 12,
  },
  priceBar: {
    flexDirection: 'row',
    height: 24,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 8,
  },
  slZone: {
    backgroundColor: colors.bearish + '40',
  },
  tpZone: {
    backgroundColor: colors.bullish + '40',
  },
  entryLine: {
    width: 3,
    backgroundColor: colors.primary,
  },
  labelsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  labelItem: {
    alignItems: 'center',
  },
  labelText: {
    color: colors.textMuted,
    fontSize: 10,
  },
  labelValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  labelPercent: {
    color: colors.bearish,
    fontSize: 10,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  statBox: {
    alignItems: 'center',
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
    fontFamily: 'monospace',
  },
});
