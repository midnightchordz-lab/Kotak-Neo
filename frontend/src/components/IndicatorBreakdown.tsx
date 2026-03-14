import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { colors } from '../theme/colors';
import { IndicatorVote } from '../store/tradingStore';

interface IndicatorBreakdownProps {
  votes: IndicatorVote[];
}

export const IndicatorBreakdown: React.FC<IndicatorBreakdownProps> = ({ votes }) => {
  if (!votes || votes.length === 0) {
    return (
      <View style={styles.container}>
        <Text style={styles.noData}>No indicator data</Text>
      </View>
    );
  }

  const getVoteColor = (vote: number) => {
    if (vote > 0) return colors.bullish;
    if (vote < 0) return colors.bearish;
    return colors.neutral;
  };

  const getVoteIcon = (vote: number) => {
    if (vote > 0) return '▲';
    if (vote < 0) return '▼';
    return '●';
  };

  const getVoteLabel = (vote: number) => {
    if (vote > 0) return 'BULLISH';
    if (vote < 0) return 'BEARISH';
    return 'NEUTRAL';
  };

  // Sort by weight descending
  const sortedVotes = [...votes].sort((a, b) => b.weight - a.weight);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Indicator Breakdown</Text>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {sortedVotes.map((vote, index) => (
          <View key={index} style={styles.indicatorRow}>
            <View style={styles.indicatorHeader}>
              <View style={styles.nameContainer}>
                <Text style={[styles.icon, { color: getVoteColor(vote.vote) }]}>
                  {getVoteIcon(vote.vote)}
                </Text>
                <Text style={styles.name}>{vote.name}</Text>
              </View>
              <View style={styles.weightBadge}>
                <Text style={styles.weightText}>{vote.weight.toFixed(2)}</Text>
              </View>
            </View>
            
            <View style={styles.barContainer}>
              <View 
                style={[
                  styles.bar,
                  { 
                    backgroundColor: getVoteColor(vote.vote),
                    width: `${Math.abs(vote.vote) * 100}%`
                  }
                ]} 
              />
            </View>
            
            <View style={styles.detailRow}>
              <Text style={[styles.voteLabel, { color: getVoteColor(vote.vote) }]}>
                {getVoteLabel(vote.vote)}
              </Text>
              <Text style={styles.detail} numberOfLines={1}>
                {vote.detail}
              </Text>
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
  scrollView: {
    flex: 1,
  },
  noData: {
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 20,
  },
  indicatorRow: {
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  indicatorHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  nameContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  icon: {
    fontSize: 12,
    marginRight: 6,
  },
  name: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '500',
  },
  weightBadge: {
    backgroundColor: colors.bgTertiary,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  weightText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontFamily: 'monospace',
  },
  barContainer: {
    height: 4,
    backgroundColor: colors.bgTertiary,
    borderRadius: 2,
    overflow: 'hidden',
    marginBottom: 6,
  },
  bar: {
    height: '100%',
    borderRadius: 2,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  voteLabel: {
    fontSize: 10,
    fontWeight: '600',
    marginRight: 8,
    width: 55,
  },
  detail: {
    color: colors.textMuted,
    fontSize: 10,
    flex: 1,
  },
});
