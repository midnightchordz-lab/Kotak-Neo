import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';

interface AIValidationPanelProps {
  validation: {
    verdict: string;
    quality: string;
    confidence: number;
    entry_timing: string;
    key_risk: string;
    adjustment: string;
  } | undefined;
}

export const AIValidationPanel: React.FC<AIValidationPanelProps> = ({ validation }) => {
  if (!validation) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>AI Validation</Text>
        <Text style={styles.noData}>Signal not validated</Text>
      </View>
    );
  }

  const getVerdictColor = (verdict: string) => {
    if (verdict.includes('STRONG_BUY')) return colors.bullish;
    if (verdict.includes('BUY')) return colors.bullishLight;
    if (verdict.includes('STRONG_SELL')) return colors.bearish;
    if (verdict.includes('SELL')) return colors.bearishLight;
    return colors.neutral;
  };

  const getQualityColor = (quality: string) => {
    switch (quality) {
      case 'EXCELLENT': return colors.bullish;
      case 'GOOD': return colors.bullishLight;
      case 'FAIR': return colors.warning;
      case 'POOR': return colors.bearish;
      default: return colors.neutral;
    }
  };

  const getTimingColor = (timing: string) => {
    switch (timing) {
      case 'OPTIMAL': return colors.bullish;
      case 'ACCEPTABLE': return colors.warning;
      case 'SUBOPTIMAL': return colors.bearish;
      default: return colors.neutral;
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Validation</Text>
        <View style={[styles.verdictBadge, { backgroundColor: getVerdictColor(validation.verdict) }]}>
          <Text style={styles.verdictText}>{validation.verdict.replace('_', ' ')}</Text>
        </View>
      </View>

      <View style={styles.metricsRow}>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Quality</Text>
          <Text style={[styles.metricValue, { color: getQualityColor(validation.quality) }]}>
            {validation.quality}
          </Text>
        </View>
        
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Confidence</Text>
          <Text style={styles.metricValue}>{validation.confidence}%</Text>
        </View>
        
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>Timing</Text>
          <Text style={[styles.metricValue, { color: getTimingColor(validation.entry_timing) }]}>
            {validation.entry_timing}
          </Text>
        </View>
      </View>

      <View style={styles.infoSection}>
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>Key Risk:</Text>
          <Text style={styles.infoValue}>{validation.key_risk}</Text>
        </View>
        
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>Adjustment:</Text>
          <Text style={styles.infoValue}>{validation.adjustment}</Text>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  noData: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 8,
  },
  verdictBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
  },
  verdictText: {
    color: 'white',
    fontSize: 11,
    fontWeight: '700',
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  metric: {
    alignItems: 'center',
    flex: 1,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: 2,
  },
  metricValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  infoSection: {
    marginTop: 12,
  },
  infoItem: {
    marginBottom: 8,
  },
  infoLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    marginBottom: 2,
  },
  infoValue: {
    color: colors.text,
    fontSize: 12,
  },
});
