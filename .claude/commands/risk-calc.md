# Risk Calculation Skill

Calculate optimal position sizing and risk management parameters for trades.

## Instructions

When invoked, help calculate proper risk management based on the Kelly Criterion and professional risk management principles.

### Input Parameters (Ask user if not provided)
- **Account Size**: Total trading capital
- **Win Rate**: Historical or estimated win rate (%)
- **Risk-Reward Ratio**: Average winner / Average loser
- **Entry Price**: Planned entry price
- **Stop Loss Price**: Planned stop loss level
- **Current Volatility**: ATR or recent price range (optional)

### 1. Kelly Criterion Calculation

The Kelly formula: **f* = (bp - q) / b**

Where:
- f* = Fraction of capital to bet
- b = Risk-Reward ratio (odds received on the wager)
- p = Probability of winning (win rate)
- q = Probability of losing (1 - p)

**IMPORTANT**: Due to crypto's high volatility, use fractional Kelly:
- **Half Kelly (50%)**: Recommended for most traders
- **Quarter Kelly (25%)**: Conservative, for beginners or high volatility

### 2. Position Sizing Rules

Professional guidelines:
- **1% Rule**: Never risk more than 1% of capital per trade (conservative)
- **2% Rule**: Maximum 2% risk per trade (CFA Institute standard)
- **5% Rule**: Aggressive, only for high-conviction trades

Position Size Formula:
```
Position Size = (Account Size × Risk %) / (Entry Price - Stop Loss)
```

### 3. Risk Assessment Checklist

Before sizing a position, verify:
- [ ] Stop loss is at a logical technical level (not arbitrary)
- [ ] Risk-reward ratio is at least 1:1.5 (preferably 1:2+)
- [ ] Total portfolio risk doesn't exceed 6-10% across all positions
- [ ] Correlation risk considered (multiple BTC-correlated positions)
- [ ] Liquidity sufficient for planned position size

### 4. Volatility Adjustment

Adjust position size based on current volatility:
- **Low Volatility** (ATR < 2%): Can use standard sizing
- **Normal Volatility** (ATR 2-5%): Standard sizing
- **High Volatility** (ATR 5-10%): Reduce size by 25-50%
- **Extreme Volatility** (ATR > 10%): Reduce size by 50-75% or avoid

## Output Format

```
## Risk Calculation Results

### Input Summary
- Account Size: $[X]
- Win Rate: [X]%
- Risk-Reward: 1:[X]
- Entry: $[X] | Stop Loss: $[X]

### Kelly Criterion
- Full Kelly: [X]% of capital
- Half Kelly (Recommended): [X]% of capital
- Quarter Kelly (Conservative): [X]% of capital

### Position Sizing
Using [X]% risk per trade:
- Risk Amount: $[X]
- Position Size: [X] units
- Position Value: $[X]

### Risk Metrics
- Risk per trade: [X]%
- Max portfolio risk: [X]%
- Risk-Reward validated: [Yes/No]

### Recommendation
[Specific recommendation based on calculations]

### Warning Flags (if any)
- [List any concerns]
```

## Important Limitations

1. **Kelly doesn't account for black swan events** - rare but extreme market moves
2. **Probabilities are estimates** - past performance doesn't guarantee future results
3. **Correlation risk** - multiple crypto positions often move together
4. **Slippage and fees** - actual execution may differ from planned

## References
- Kelly Criterion: [LBank Guide](https://www.lbank.com/explore/mastering-the-kelly-criterion-for-smarter-crypto-risk-management)
- Position Sizing: [Altrady](https://www.altrady.com/crypto-trading/risk-management/calculate-position-size-risk-ratio)
- Risk Management: [CAIA Framework](https://caia.org/blog/2025/07/14/framework-cryptocurrency-trading)

$ARGUMENTS
