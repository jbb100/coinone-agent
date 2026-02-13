# DCA (Dollar-Cost Averaging) Calculator Skill

Calculate and optimize Dollar-Cost Averaging strategies for crypto investment.

## Instructions

When invoked, help calculate DCA parameters, analyze historical DCA performance, or design optimal DCA strategies.

### 1. DCA Fundamentals

**What is DCA?**
Investing a fixed amount at regular intervals regardless of price, reducing the impact of volatility and emotional decision-making.

**Benefits**:
- Removes emotion from investing
- Reduces impact of volatility
- No need to time the market
- Builds discipline and consistency
- Historically effective for BTC (any 4-year hold = profit)

**Limitations**:
- May underperform lump sum in strong bull markets
- Still requires choosing WHAT to buy
- Doesn't protect against secular decline

### 2. Basic DCA Calculation

**Inputs**:
- Investment Amount per Period: $[X]
- Investment Frequency: [Daily/Weekly/Bi-weekly/Monthly]
- Investment Duration: [Months/Years]
- Asset: [BTC/ETH/etc.]

**Key Metrics**:
```
Total Invested = Amount × Number of Periods
Average Cost Basis = Total Invested / Total Units Acquired
Current Value = Total Units × Current Price
ROI = (Current Value - Total Invested) / Total Invested × 100%
```

### 3. DCA Strategy Variations

#### A. Standard DCA
- Fixed amount at fixed intervals
- Simplest to implement
- Works with auto-buy features

#### B. Value Averaging
- Adjust investment to reach target portfolio value
- Buy more when prices are low
- Buy less (or sell) when prices are high
- More complex but potentially better returns

Formula:
```
Investment = Target Value - Current Value
If Investment > 0: Buy
If Investment < 0: Optionally sell or skip
```

#### C. Smart DCA
- Base amount + adjustments based on indicators
- Example: Double buy when RSI < 30
- Example: Half buy when RSI > 70
- Requires more monitoring

#### D. Lump Sum + DCA Hybrid
- Deploy 30-50% immediately
- DCA remaining over 3-12 months
- Balances FOMO with risk management

### 4. Optimal DCA Parameters

**Frequency Analysis** (Historical for BTC):
| Frequency | Pros | Cons | Best For |
|-----------|------|------|----------|
| Daily | Max averaging | High fees, effort | Large portfolios |
| Weekly | Good balance | Moderate effort | Most investors |
| Bi-weekly | Aligns with paycheck | Slightly less averaging | Salary investors |
| Monthly | Easy to manage | Less averaging | Beginners |

**Amount Guidelines**:
- Only invest what you can afford to lose
- Emergency fund should be separate
- Consider 5-20% of investable income
- Consistency matters more than amount

### 5. DCA Exit Strategies

**When/How to Exit**:

1. **Time-Based**
   - Exit after X years (e.g., 4-year cycle)
   - Gradual exit over time (reverse DCA)

2. **Target-Based**
   - Exit at specific price targets
   - Exit at portfolio value goal

3. **Indicator-Based**
   - Exit when MVRV > 3
   - Exit when Fear & Greed > 90
   - Exit on technical signals

4. **Laddered Exit**
   - Sell 25% at Target 1
   - Sell 25% at Target 2
   - Sell 25% at Target 3
   - Keep 25% for "moon" scenario

### 6. DCA Tracking Spreadsheet

**Essential Columns**:
```
| Date | Amount ($) | Price | Units Bought | Total Units | Avg Cost | Current Value | ROI % |
|------|------------|-------|--------------|-------------|----------|---------------|-------|
```

**Calculated Fields**:
- Running Average Cost = Sum(Invested) / Sum(Units)
- Unrealized P/L = Current Value - Total Invested
- ROI % = (Current Value / Total Invested - 1) × 100

## Output Format

```
## DCA Analysis: [Asset]

### Strategy Parameters
- Investment: $[X] per [frequency]
- Start Date: [Date]
- Duration: [X] months/years
- Total Periods: [X]

### Projections
| Scenario | Final Units | Avg Cost | Total Invested |
|----------|-------------|----------|----------------|
| Current Price Constant | [X] | $[X] | $[X] |
| Price +50% | [X] | $[X] | $[X] |
| Price -50% | [X] | $[X] | $[X] |

### Historical Simulation (if applicable)
- Period: [Start] to [End]
- Total Invested: $[X]
- Units Acquired: [X]
- Average Cost: $[X]
- Final Value: $[X]
- ROI: [X]%
- vs Lump Sum: [Better/Worse by X%]

### Optimization Suggestions
1. [Suggestion based on analysis]
2. [Suggestion based on analysis]

### Recommended Schedule
| Date | Amount | Notes |
|------|--------|-------|
| [Date] | $[X] | [Any adjustments] |

### Risk Considerations
- Max historical drawdown during DCA: [X]%
- Longest underwater period: [X] months
- Break-even scenarios: [Analysis]
```

## DCA Best Practices

1. **Automate**: Set up recurring buys to remove emotion
2. **Stay Consistent**: Don't skip periods during dips
3. **Review Quarterly**: Adjust amounts if life changes
4. **Don't Check Daily**: Weekly or monthly review is enough
5. **Have an Exit Plan**: Know when you'll take profits
6. **Diversify**: Consider DCA into multiple assets

## References
- DCA Strategy: [Mudrex](https://mudrex.com/learn/top-crypto-trading-strategies-for-beginners-2025/)
- Crypto Trading Strategies: [CMC Markets](https://www.cmcmarkets.com/en/cryptocurrencies/7-crypto-trading-strategies)
- Investment Framework: [CAIA](https://caia.org/blog/2025/07/14/framework-cryptocurrency-trading)

$ARGUMENTS
