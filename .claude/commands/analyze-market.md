# Market Analysis Skill

Perform comprehensive market analysis for cryptocurrency trading decisions.

## Instructions

When invoked, analyze the specified cryptocurrency or market using the following framework:

### 1. Technical Analysis
- **Trend Analysis**: Identify current trend direction (uptrend, downtrend, sideways)
- **Support/Resistance**: Key price levels based on historical data
- **Moving Averages**: 20, 50, 200 period MAs and their crossovers
- **Volume Analysis**: Volume trends and anomalies

### 2. Key Technical Indicators
- **RSI (Relative Strength Index)**: Overbought (>70) / Oversold (<30) conditions
- **MACD**: Trend direction and momentum, crossover signals
- **Bollinger Bands**: Volatility and potential breakout zones
- **ATR (Average True Range)**: Current volatility level

### 3. On-Chain Metrics (Bitcoin/Ethereum)
- **MVRV Ratio**: Market Value / Realized Value - above 3 signals overheated, below 1 signals undervalued
- **SOPR**: Spent Output Profit Ratio - profit-taking or capitulation signals
- **NVT Ratio**: Network Value to Transactions - valuation metric
- **Exchange Flows**: Net inflow/outflow patterns

### 4. Market Cycle Position
- **Bitcoin Halving Cycle**: Current position in the 4-year cycle
- **Historical Comparison**: Similar periods in previous cycles
- **Institutional Activity**: ETF flows, whale movements

### 5. Risk Assessment
- **Current Risk Level**: Low / Medium / High / Extreme
- **Key Risk Factors**: Identify specific risks
- **Recommended Position Size**: Based on volatility

## Output Format

Provide analysis in this structure:
```
## Market Analysis: [Asset]
Date: [Current Date]

### Summary
[1-2 sentence overview]

### Technical Outlook
- Trend: [Bullish/Bearish/Neutral]
- Key Levels: Support [X], Resistance [Y]
- Momentum: [Strong/Weak/Neutral]

### Indicator Signals
| Indicator | Value | Signal |
|-----------|-------|--------|
| RSI | XX | [Overbought/Oversold/Neutral] |
| MACD | XX | [Bullish/Bearish] |
| BB Position | XX% | [Upper/Middle/Lower Band] |

### On-Chain Health (if applicable)
- MVRV: [Value] - [Interpretation]
- SOPR: [Value] - [Interpretation]

### Risk Level: [X/10]

### Actionable Insights
1. [Specific recommendation]
2. [Specific recommendation]
```

## References
- Technical Analysis: [YouHodler Education](https://www.youhodler.com/education/introduction-to-technical-indicators)
- On-Chain Metrics: [CheckOnChain](https://charts.checkonchain.com/)
- MVRV Analysis: [Bitcoin Magazine Pro](https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/)

$ARGUMENTS
