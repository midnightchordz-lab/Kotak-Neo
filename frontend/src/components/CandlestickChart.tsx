import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import Svg, { Path, Line, Rect, Circle, G, Text as SvgText } from 'react-native-svg';
import { colors } from '../theme/colors';
import { Candle } from '../store/tradingStore';

interface CandlestickChartProps {
  candles: Candle[];
  width?: number;
  height?: number;
  ema9?: number[];
  ema21?: number[];
  vwap?: number[];
  showVolume?: boolean;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  candles,
  width = Dimensions.get('window').width - 32,
  height = 300,
  ema9,
  ema21,
  vwap,
  showVolume = true
}) => {
  if (!candles || candles.length === 0) {
    return (
      <View style={[styles.container, { width, height }]}>
        <Text style={styles.noData}>No chart data available</Text>
      </View>
    );
  }

  const padding = { top: 20, right: 60, bottom: showVolume ? 60 : 30, left: 10 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const volumeHeight = showVolume ? 40 : 0;
  const priceChartHeight = chartHeight - volumeHeight;

  // Calculate price range
  const prices = candles.flatMap(c => [c.high, c.low]);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = maxPrice - minPrice || 1;
  const pricePadding = priceRange * 0.05;

  // Scale functions
  const scaleX = (index: number) => padding.left + (index / (candles.length - 1 || 1)) * chartWidth;
  const scaleY = (price: number) => 
    padding.top + ((maxPrice + pricePadding - price) / (priceRange + pricePadding * 2)) * priceChartHeight;

  // Volume scale
  const volumes = candles.map(c => c.volume);
  const maxVolume = Math.max(...volumes) || 1;
  const scaleVolume = (vol: number) => 
    height - padding.bottom + volumeHeight - (vol / maxVolume) * volumeHeight;

  const candleWidth = Math.max(2, (chartWidth / candles.length) * 0.7);

  // Generate candle paths
  const renderCandles = () => {
    return candles.map((candle, i) => {
      const x = scaleX(i);
      const isBullish = candle.close >= candle.open;
      const color = isBullish ? colors.bullish : colors.bearish;
      
      const bodyTop = scaleY(Math.max(candle.open, candle.close));
      const bodyBottom = scaleY(Math.min(candle.open, candle.close));
      const bodyHeight = Math.max(1, bodyBottom - bodyTop);
      
      return (
        <G key={i}>
          {/* Wick */}
          <Line
            x1={x}
            y1={scaleY(candle.high)}
            x2={x}
            y2={scaleY(candle.low)}
            stroke={color}
            strokeWidth={1}
          />
          {/* Body */}
          <Rect
            x={x - candleWidth / 2}
            y={bodyTop}
            width={candleWidth}
            height={bodyHeight}
            fill={isBullish ? color : color}
            stroke={color}
            strokeWidth={0.5}
          />
        </G>
      );
    });
  };

  // Generate EMA line
  const renderLine = (data: number[] | undefined, color: string, dashArray?: string) => {
    if (!data || data.length === 0) return null;
    
    const offset = candles.length - data.length;
    const points = data.map((val, i) => {
      const x = scaleX(i + offset);
      const y = scaleY(val);
      return `${i === 0 ? 'M' : 'L'}${x},${y}`;
    }).join(' ');

    return (
      <Path
        d={points}
        stroke={color}
        strokeWidth={1.5}
        fill="none"
        strokeDasharray={dashArray}
      />
    );
  };

  // Volume bars
  const renderVolume = () => {
    if (!showVolume) return null;
    
    return candles.map((candle, i) => {
      const x = scaleX(i);
      const isBullish = candle.close >= candle.open;
      const barHeight = (candle.volume / maxVolume) * volumeHeight;
      
      return (
        <Rect
          key={`vol-${i}`}
          x={x - candleWidth / 2}
          y={height - padding.bottom - barHeight + volumeHeight}
          width={candleWidth}
          height={barHeight}
          fill={isBullish ? colors.bullish : colors.bearish}
          opacity={0.3}
        />
      );
    });
  };

  // Price labels
  const priceLabels = [];
  const numLabels = 5;
  for (let i = 0; i <= numLabels; i++) {
    const price = minPrice + (priceRange * i) / numLabels;
    priceLabels.push(
      <SvgText
        key={`price-${i}`}
        x={width - padding.right + 5}
        y={scaleY(price) + 4}
        fill={colors.textSecondary}
        fontSize={10}
        fontFamily="monospace"
      >
        {price.toFixed(2)}
      </SvgText>
    );
  }

  // Current price line
  const lastCandle = candles[candles.length - 1];
  const currentPriceY = scaleY(lastCandle.close);
  const priceColor = lastCandle.close >= lastCandle.open ? colors.bullish : colors.bearish;

  return (
    <View style={[styles.container, { width, height }]}>
      <Svg width={width} height={height}>
        {/* Grid lines */}
        {[...Array(5)].map((_, i) => (
          <Line
            key={`grid-${i}`}
            x1={padding.left}
            y1={padding.top + (priceChartHeight * i) / 4}
            x2={width - padding.right}
            y2={padding.top + (priceChartHeight * i) / 4}
            stroke={colors.border}
            strokeWidth={0.5}
            strokeDasharray="3,3"
          />
        ))}

        {/* Candles */}
        {renderCandles()}
        
        {/* EMA lines */}
        {renderLine(ema9, colors.ema9)}
        {renderLine(ema21, colors.ema21)}
        {renderLine(vwap, colors.vwap, '5,3')}

        {/* Current price line */}
        <Line
          x1={padding.left}
          y1={currentPriceY}
          x2={width - padding.right}
          y2={currentPriceY}
          stroke={priceColor}
          strokeWidth={1}
          strokeDasharray="2,2"
        />
        <Rect
          x={width - padding.right}
          y={currentPriceY - 10}
          width={55}
          height={20}
          fill={priceColor}
          rx={3}
        />
        <SvgText
          x={width - padding.right + 5}
          y={currentPriceY + 4}
          fill="white"
          fontSize={10}
          fontFamily="monospace"
          fontWeight="bold"
        >
          {lastCandle.close.toFixed(2)}
        </SvgText>

        {/* Price labels */}
        {/* {priceLabels} */}

        {/* Volume */}
        {renderVolume()}
      </Svg>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgSecondary,
    borderRadius: 8,
    overflow: 'hidden',
  },
  noData: {
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 100,
  },
});
