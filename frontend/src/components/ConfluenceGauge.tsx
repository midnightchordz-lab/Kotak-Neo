import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import Svg, { Path, Circle, G, Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';
import { colors } from '../theme/colors';

interface ConfluenceGaugeProps {
  score: number;
  direction: string;
  confidence: number;
  indicatorsAgreeing: number;
  totalIndicators: number;
}

export const ConfluenceGauge: React.FC<ConfluenceGaugeProps> = ({
  score,
  direction,
  confidence,
  indicatorsAgreeing,
  totalIndicators
}) => {
  const size = 180;
  const strokeWidth = 15;
  const radius = (size - strokeWidth) / 2;
  const centerX = size / 2;
  const centerY = size / 2;
  
  // Arc from 135 degrees to 405 degrees (270 degree sweep)
  const startAngle = 135;
  const endAngle = 405;
  const totalAngle = endAngle - startAngle;
  
  // Calculate the arc path
  const polarToCartesian = (angle: number) => {
    const angleInRadians = ((angle - 90) * Math.PI) / 180;
    return {
      x: centerX + radius * Math.cos(angleInRadians),
      y: centerY + radius * Math.sin(angleInRadians)
    };
  };
  
  const describeArc = (startAng: number, endAng: number) => {
    const start = polarToCartesian(endAng);
    const end = polarToCartesian(startAng);
    const largeArcFlag = endAng - startAng <= 180 ? 0 : 1;
    
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
  };
  
  // Normalize score to 0-100 for gauge
  // Score ranges from -10 to +10, map to 0-100
  const normalizedScore = ((score + 10) / 20) * 100;
  const clampedScore = Math.max(0, Math.min(100, normalizedScore));
  const progressAngle = startAngle + (clampedScore / 100) * totalAngle;
  
  // Determine color based on direction
  const getColor = () => {
    if (direction === 'BUY') return colors.bullish;
    if (direction === 'SELL') return colors.bearish;
    return colors.neutral;
  };
  
  const mainColor = getColor();
  
  // Score indicator position
  const indicatorPos = polarToCartesian(progressAngle);

  return (
    <View style={styles.container}>
      <Svg width={size} height={size}>
        <Defs>
          <LinearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <Stop offset="0%" stopColor={colors.bearish} />
            <Stop offset="50%" stopColor={colors.neutral} />
            <Stop offset="100%" stopColor={colors.bullish} />
          </LinearGradient>
        </Defs>
        
        {/* Background arc */}
        <Path
          d={describeArc(startAngle, endAngle)}
          stroke={colors.bgTertiary}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
        />
        
        {/* Progress arc */}
        <Path
          d={describeArc(startAngle, progressAngle)}
          stroke={mainColor}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
        />
        
        {/* Center circle */}
        <Circle
          cx={centerX}
          cy={centerY}
          r={radius - 30}
          fill={colors.bgSecondary}
        />
        
        {/* Score indicator dot */}
        <Circle
          cx={indicatorPos.x}
          cy={indicatorPos.y}
          r={8}
          fill={mainColor}
          stroke={colors.bg}
          strokeWidth={2}
        />
        
        {/* Center text - Direction */}
        <SvgText
          x={centerX}
          y={centerY - 15}
          fill={mainColor}
          fontSize={24}
          fontWeight="bold"
          textAnchor="middle"
        >
          {direction}
        </SvgText>
        
        {/* Center text - Score */}
        <SvgText
          x={centerX}
          y={centerY + 15}
          fill={colors.text}
          fontSize={28}
          fontWeight="bold"
          textAnchor="middle"
        >
          {score.toFixed(1)}
        </SvgText>
        
        {/* Indicators agreeing */}
        <SvgText
          x={centerX}
          y={centerY + 40}
          fill={colors.textSecondary}
          fontSize={12}
          textAnchor="middle"
        >
          {indicatorsAgreeing}/{totalIndicators} agree
        </SvgText>
        
        {/* Labels */}
        <SvgText x={25} y={size - 10} fill={colors.bearish} fontSize={10}>
          SELL
        </SvgText>
        <SvgText x={size - 35} y={size - 10} fill={colors.bullish} fontSize={10}>
          BUY
        </SvgText>
      </Svg>
      
      {/* Confidence bar */}
      <View style={styles.confidenceContainer}>
        <Text style={styles.confidenceLabel}>Confidence: {confidence.toFixed(0)}%</Text>
        <View style={styles.confidenceBarBg}>
          <View 
            style={[
              styles.confidenceBar, 
              { width: `${confidence}%`, backgroundColor: mainColor }
            ]} 
          />
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    padding: 16,
  },
  confidenceContainer: {
    width: '100%',
    marginTop: 8,
  },
  confidenceLabel: {
    color: colors.textSecondary,
    fontSize: 12,
    marginBottom: 4,
    textAlign: 'center',
  },
  confidenceBarBg: {
    height: 6,
    backgroundColor: colors.bgTertiary,
    borderRadius: 3,
    overflow: 'hidden',
  },
  confidenceBar: {
    height: '100%',
    borderRadius: 3,
  },
});
