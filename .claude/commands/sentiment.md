# Market Sentiment Analysis Skill

Analyze market sentiment and psychological indicators for trading decisions.

## Instructions

When invoked, provide comprehensive sentiment analysis using multiple data sources and psychological frameworks.

### 1. Fear & Greed Index Analysis

**Index Scale (0-100)**:
| Range | Sentiment | Trading Implication |
|-------|-----------|---------------------|
| 0-24 | Extreme Fear | Potential buying opportunity (contrarian) |
| 25-44 | Fear | Accumulation zone consideration |
| 45-55 | Neutral | Wait for directional clarity |
| 56-74 | Greed | Caution, reduce position sizes |
| 75-100 | Extreme Greed | Potential selling opportunity (contrarian) |

**Index Components**:
- Price Momentum (25%): Top 10 crypto performance
- Volatility (25%): BTC/ETH forward-looking volatility
- Derivatives (25%): Put/Call ratios in options
- Market Composition (15%): Bitcoin dominance
- Social Trends (10%): Search volume, engagement

### 2. Contrarian Strategy Framework

**"Be fearful when others are greedy, and greedy when others are fearful"** - Warren Buffett

**Application**:
- Extreme Fear (0-20): Consider DCA buying, increase exposure gradually
- Extreme Greed (80-100): Consider taking profits, tighten stops
- Historical correlation: Extreme fear has preceded recoveries 70%+ of time

**IMPORTANT LIMITATIONS**:
- Sentiment can stay extreme for extended periods
- Not a timing tool, describes current state
- Use with technical analysis for confirmation

### 3. Social Sentiment Indicators

**Metrics to Monitor**:
- Twitter/X crypto mentions and sentiment
- Reddit activity (r/cryptocurrency, r/bitcoin)
- YouTube video sentiment (bullish/bearish ratio)
- Google Trends for crypto terms
- Telegram/Discord group activity

**Contrarian Signals**:
- "Everyone talking about crypto" = potential top
- "Crypto is dead" headlines = potential bottom
- Mass retail FOMO = distribution phase
- Mass retail panic = accumulation phase

### 4. On-Chain Sentiment Metrics

**Holder Behavior**:
- Long-term holder accumulation/distribution
- Exchange inflows (selling pressure)
- Exchange outflows (accumulation)
- Stablecoin reserves on exchanges (buying power)

**Whale Activity**:
- Large transaction volume
- Whale wallet movements
- Institutional fund flows (ETF data)

### 5. Market Psychology Phases

**Market Cycle Psychology**:
```
Disbelief → Hope → Optimism → Belief → Thrill → Euphoria (TOP)
    ↑                                                    ↓
Capitulation ← Anger ← Denial ← Anxiety ← Complacency (FALL)
```

**Identifying Current Phase**:
- Euphoria: "This time is different", mainstream media coverage
- Complacency: "Just a dip", buying the dip aggressively
- Anxiety: "Should I sell?", uncertainty
- Denial: "It will come back", holding losses
- Panic: Forced selling, margin calls
- Capitulation: "I'm done with crypto", mass exits
- Disbelief: "Dead cat bounce", smart money accumulating

### 6. Behavioral Bias Checklist

Common biases to avoid:
- [ ] **FOMO**: Fear of missing out - buying after big moves
- [ ] **Loss Aversion**: Holding losers too long
- [ ] **Confirmation Bias**: Only seeing data that supports position
- [ ] **Recency Bias**: Overweighting recent events
- [ ] **Overconfidence**: After winning streak
- [ ] **Anchoring**: Fixating on purchase price

## Output Format

```
## Sentiment Analysis Report
Date: [Current Date]

### Fear & Greed Index
- Current Value: [XX]/100
- Category: [Extreme Fear/Fear/Neutral/Greed/Extreme Greed]
- 7-Day Change: [+/-XX]
- 30-Day Trend: [Increasing/Decreasing/Stable]

### Contrarian Signal
**[STRONG BUY ZONE / BUY ZONE / NEUTRAL / CAUTION / STRONG CAUTION]**

### Social Sentiment
- Twitter/X: [Bullish/Bearish/Neutral] - Volume [High/Normal/Low]
- Reddit: [Bullish/Bearish/Neutral]
- Google Trends: [Rising/Falling/Stable]
- Overall Social: [X/10 bullishness]

### Market Psychology Phase
**Current Phase**: [Phase Name]
**Implications**: [What this means for positioning]

### On-Chain Sentiment
- Exchange Flows: [Net Inflow/Outflow] - [Bearish/Bullish]
- Whale Activity: [Accumulating/Distributing/Neutral]
- LTH Behavior: [Accumulating/Distributing]

### Bias Check
[Highlight any potential biases to be aware of]

### Sentiment Summary
[1-2 sentences summarizing overall sentiment and implications]

### Recommended Actions
1. [Specific action based on sentiment]
2. [Specific action based on sentiment]
```

## References
- Fear & Greed Index: [Alternative.me](https://alternative.me/crypto/fear-and-greed-index/)
- CoinMarketCap Sentiment: [CoinMarketCap F&G](https://coinmarketcap.com/charts/fear-and-greed-index/)
- Real-Time Multi-Token: [CFGI.io](https://cfgi.io/)
- Bitcoin F&G: [Bitcoin Magazine Pro](https://www.bitcoinmagazinepro.com/charts/bitcoin-fear-and-greed-index/)

$ARGUMENTS
