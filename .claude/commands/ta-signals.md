# Technical Analysis Signals Skill

Generate actionable trading signals using key technical indicators.

## Instructions

When invoked, analyze the specified asset using the three-indicator framework (RSI, MACD, Bollinger Bands) and provide clear trading signals.

### Core Indicator Framework

#### 1. RSI (Relative Strength Index)
- **Period**: Standard 14-period
- **Overbought**: Above 70 (potential sell signal)
- **Oversold**: Below 30 (potential buy signal)
- **Neutral**: 30-70
- **Bullish Momentum**: RSI crossing above 50
- **Bearish Momentum**: RSI crossing below 50

**RSI Divergence Signals**:
- Bullish Divergence: Price makes lower low, RSI makes higher low
- Bearish Divergence: Price makes higher high, RSI makes lower high

#### 2. MACD (Moving Average Convergence Divergence)
- **MACD Line**: 12-day EMA - 26-day EMA
- **Signal Line**: 9-day EMA of MACD Line
- **Histogram**: MACD Line - Signal Line

**Signal Types**:
- **Bullish Crossover**: MACD crosses above Signal Line (BUY)
- **Bearish Crossover**: MACD crosses below Signal Line (SELL)
- **Zero Line Cross Up**: MACD crosses above zero (trend confirmation)
- **Zero Line Cross Down**: MACD crosses below zero (trend confirmation)

#### 3. Bollinger Bands
- **Middle Band**: 20-period SMA
- **Upper Band**: Middle Band + 2 Standard Deviations
- **Lower Band**: Middle Band - 2 Standard Deviations

**Signal Types**:
- **Band Touch (Upper)**: Potential overbought, watch for reversal
- **Band Touch (Lower)**: Potential oversold, watch for reversal
- **Squeeze**: Bands contracting = low volatility, breakout incoming
- **Expansion**: Bands widening = trend strengthening

### Combined Signal Strategy

**HIGH CONFIDENCE SIGNALS (All 3 align)**:

**Strong Buy Signal**:
- RSI < 30 or crossing above 50
- MACD bullish crossover or positive histogram growing
- Price near lower Bollinger Band or bouncing off it

**Strong Sell Signal**:
- RSI > 70 or crossing below 50
- MACD bearish crossover or negative histogram growing
- Price near upper Bollinger Band or rejected from it

**MEDIUM CONFIDENCE (2 of 3 align)**:
- Use smaller position size
- Tighter stop loss
- Wait for confirmation

**LOW CONFIDENCE (1 or 0 align)**:
- No trade or paper trade only
- Wait for better setup

### Additional Indicators (Support)

- **Volume**: Confirm signals with above-average volume
- **ATR**: Measure volatility for stop loss placement
- **Moving Averages**: 20/50/200 SMA for trend context

## Output Format

```
## Technical Analysis Signals: [Asset]
Timeframe: [1H/4H/1D/1W]
Date: [Current Date]

### Indicator Status
| Indicator | Value | Signal | Strength |
|-----------|-------|--------|----------|
| RSI (14) | [XX] | [Buy/Sell/Neutral] | [Strong/Weak] |
| MACD | [XX] | [Bullish/Bearish] | [Strong/Weak] |
| BB Position | [XX%] | [Buy/Sell/Neutral] | [Strong/Weak] |

### Signal Alignment: [X/3]

### Overall Signal
**[STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL]**

### Key Levels
- Entry Zone: $[X] - $[Y]
- Stop Loss: $[X] (ATR-based)
- Target 1: $[X] (1:1 R:R)
- Target 2: $[X] (1:2 R:R)
- Target 3: $[X] (1:3 R:R)

### Divergence Check
- RSI Divergence: [None/Bullish/Bearish]
- MACD Divergence: [None/Bullish/Bearish]

### Volume Confirmation
[Above/Below average, supports/contradicts signal]

### Trade Setup Quality: [A/B/C/D]
- A: All conditions met, high conviction
- B: Most conditions met, good setup
- C: Some conditions met, lower conviction
- D: Conditions not met, no trade

### Notes
[Any additional observations or warnings]
```

## Important Reminders

1. **No indicator is 100% accurate** - always use stop losses
2. **Higher timeframes = more reliable signals**
3. **Combine with support/resistance levels**
4. **Volume confirms price action**
5. **Don't fight the trend** - trade with the larger trend

## References
- RSI, MACD, BB Guide: [Gate.io Crypto Wiki](https://web3.gate.com/crypto-wiki/article/how-to-use-macd-rsi-and-bollinger-bands-for-crypto-trading-success-a-complete-technical-indicators-guide-20260126)
- Hybrid Strategy: [Medium - Sword Red](https://medium.com/@redsword_23261/rsi-macd-bollinger-bands-and-volume-based-hybrid-trading-strategy-fb1ecfd58e1b)
- Technical Indicators: [YouHodler Education](https://www.youhodler.com/education/introduction-to-technical-indicators)

$ARGUMENTS
