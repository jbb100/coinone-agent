# Trading Strategy Review Skill

Comprehensive evaluation framework for crypto trading strategies.

## Instructions

When invoked, analyze and evaluate a trading strategy based on proven criteria and best practices.

### 1. Strategy Classification

**Identify Strategy Type**:
| Type | Description | Typical Timeframe | Win Rate | R:R |
|------|-------------|-------------------|----------|-----|
| Scalping | Quick small profits | 1m-15m | 60-70% | 1:0.5-1:1 |
| Day Trading | Intraday positions | 15m-4H | 45-55% | 1:1.5-1:2 |
| Swing Trading | Multi-day holds | 4H-1D | 40-50% | 1:2-1:3 |
| Position Trading | Weeks to months | 1D-1W | 35-45% | 1:3-1:5 |
| HODLing | Long-term hold | Monthly+ | N/A | N/A |
| DCA | Regular buying | Weekly/Monthly | N/A | N/A |
| Arbitrage | Price differences | Seconds | 90%+ | 1:0.1 |
| Mean Reversion | Return to average | 1H-1D | 55-65% | 1:1-1:1.5 |
| Trend Following | Ride the trend | 4H-1W | 35-45% | 1:3+ |

### 2. Strategy Component Checklist

**Essential Components**:
- [ ] **Entry Rules**: Clear, unambiguous conditions
- [ ] **Exit Rules**: Both profit target AND stop loss
- [ ] **Position Sizing**: Risk-based, not arbitrary
- [ ] **Asset Selection**: Criteria for which assets to trade
- [ ] **Timeframe**: Consistent with strategy type
- [ ] **Market Conditions**: When to trade vs sit out

**Red Flags**:
- No stop loss ("I'll exit when it feels right")
- Vague entries ("buy when it looks oversold")
- Martingale/averaging down on losers
- No max loss per day/week
- Correlated positions without awareness

### 3. Strategy Evaluation Criteria

#### A. Edge Analysis
Does the strategy have a definable edge?
- Statistical edge (backtested win rate + R:R > breakeven)
- Information edge (faster data, better analysis)
- Execution edge (better fills, lower fees)
- No edge = gambling

**Breakeven Win Rate Formula**:
```
Breakeven Win Rate = 1 / (1 + Risk:Reward Ratio)
Example: 1:2 R:R = 1 / (1 + 2) = 33.3% needed to breakeven
```

#### B. Risk Assessment

**Per-Trade Risk**:
- Conservative: 0.5-1% of capital
- Standard: 1-2% of capital
- Aggressive: 2-5% of capital (not recommended)

**Portfolio Risk**:
- Max correlated exposure: 6-10%
- Daily max loss: 3-5%
- Weekly max loss: 10-15%

**Drawdown Tolerance**:
- Sustainable: 10-20% max drawdown
- Challenging: 20-30% max drawdown
- Dangerous: 30%+ max drawdown

#### C. Feasibility Check

**Time Requirements**:
- Screen time needed per day
- Decision frequency
- Compatible with lifestyle?

**Capital Requirements**:
- Minimum account size for the strategy
- Fee impact (high frequency needs volume discounts)
- Margin requirements if applicable

**Psychological Demands**:
- Handles losses well? (consecutive losing trades)
- Requires quick decisions?
- Overnight/weekend risk tolerance?

### 4. Strategy Improvement Framework

**Optimization Areas**:

1. **Entry Refinement**
   - Add confirmation indicator
   - Wait for retest of level
   - Filter by higher timeframe trend

2. **Exit Improvement**
   - Trailing stop implementation
   - Partial profit taking (scale out)
   - Time-based exits for stagnant trades

3. **Risk Management Enhancement**
   - Volatility-adjusted position sizing
   - Correlation monitoring
   - Drawdown circuit breakers

4. **Filter Addition**
   - Trend filter (only trade with trend)
   - Volatility filter (avoid low/extreme volatility)
   - Time filter (avoid certain hours/days)
   - Sentiment filter (avoid extreme fear/greed)

### 5. Common Strategy Patterns (Validated)

**Proven Strategy Concepts**:

1. **DCA + Value Averaging**
   - Buy more when prices are lower
   - Reduce buys when prices are high
   - Works well for long-term accumulation

2. **Trend Following with MA Crossovers**
   - 50/200 MA golden/death cross
   - Requires patience, many false signals
   - Best in strong trending markets

3. **Mean Reversion with Bollinger Bands**
   - Buy lower band, sell upper band
   - Add RSI confirmation (<30/>70)
   - Works in ranging markets, fails in trends

4. **Breakout with Volume Confirmation**
   - Price breaks key level
   - Volume 2x+ average
   - Retest of breakout level as entry

5. **Multi-Timeframe Alignment**
   - Higher TF for direction
   - Lower TF for entry
   - All timeframes aligned = stronger signal

### 6. Strategy Documentation Template

```markdown
# Strategy: [Name]

## Overview
- Type: [Scalping/Day/Swing/Position]
- Timeframe: [Primary TF]
- Markets: [BTC, ETH, Alts, etc.]
- Expected Win Rate: [X]%
- Target R:R: 1:[X]

## Entry Rules
1. [Specific condition 1]
2. [Specific condition 2]
3. [Specific condition 3]
All conditions must be met.

## Exit Rules
### Take Profit
- Target 1: [X]% or [condition]
- Target 2: [X]% or [condition]
- Trailing: [Yes/No, conditions]

### Stop Loss
- Initial: [X]% or [technical level]
- Breakeven: Move stop to entry when [condition]

## Position Sizing
- Risk per trade: [X]% of capital
- Max positions: [X]
- Max correlated risk: [X]%

## Filters (When NOT to trade)
- [ ] When [condition]
- [ ] When [condition]

## Performance Expectations
- Monthly target: [X]%
- Max drawdown tolerance: [X]%
- Estimated trades per month: [X]
```

## Output Format

```
## Strategy Review: [Strategy Name]

### Classification
- Type: [Strategy Type]
- Timeframe: [TF]
- Complexity: [Simple/Moderate/Complex]

### Component Assessment
| Component | Present | Quality | Notes |
|-----------|---------|---------|-------|
| Entry Rules | [Y/N] | [1-5] | [Notes] |
| Exit Rules | [Y/N] | [1-5] | [Notes] |
| Stop Loss | [Y/N] | [1-5] | [Notes] |
| Position Sizing | [Y/N] | [1-5] | [Notes] |
| Filters | [Y/N] | [1-5] | [Notes] |

### Edge Analysis
- Theoretical Win Rate: [X]%
- Required Win Rate (breakeven): [X]%
- Edge Exists: [Yes/No/Unclear]

### Risk Profile
- Per-Trade Risk: [X]% - [Conservative/Standard/Aggressive]
- Max Drawdown Expected: [X]%
- Risk Rating: [Low/Medium/High]

### Strengths
1. [Strength 1]
2. [Strength 2]

### Weaknesses
1. [Weakness 1]
2. [Weakness 2]

### Improvement Recommendations
1. [Specific improvement]
2. [Specific improvement]
3. [Specific improvement]

### Overall Rating: [X]/10

### Verdict
[1-2 sentence summary of the strategy's viability]
```

## References
- Trading Strategies: [CMC Markets](https://www.cmcmarkets.com/en/cryptocurrencies/7-crypto-trading-strategies)
- Day Trading: [NFT Plazas](https://nftplazas.com/crypto-day-trading-strategies/)
- Strategy Guide: [LiteFinance](https://www.litefinance.org/blog/for-beginners/how-to-trade-crypto/cryptocurrency-trading-strategy/)
- Advanced Strategies: [AvaTrade](https://www.avatrade.com/education/online-trading-strategies/crypto-trading-strategies)

$ARGUMENTS
