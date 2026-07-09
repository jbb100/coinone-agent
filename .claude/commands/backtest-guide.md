# Backtesting Guide Skill

Comprehensive guide for backtesting crypto trading strategies with best practices and pitfall avoidance.

## Instructions

When invoked, provide guidance on backtesting methodology, help analyze backtest results, or assist in setting up proper backtesting procedures.

### 1. Backtesting Fundamentals

**What is Backtesting?**
Testing a trading strategy using historical data to evaluate how it would have performed in the past.

**Why Backtest?**
- Validate strategy logic before risking real capital
- Understand expected drawdowns and risk metrics
- Optimize parameters within reason
- Build confidence in the strategy

### 2. Data Requirements

**Essential Data Quality Checks**:
- [ ] Reliable data source (exchange APIs, professional providers)
- [ ] Appropriate timeframe (1m, 5m, 1H, 4H, 1D)
- [ ] Price AND volume data included
- [ ] Multiple market conditions covered (bull, bear, sideways)
- [ ] At least 2-3 full market cycles for crypto
- [ ] No survivorship bias (include delisted assets if relevant)

**Recommended Data Sources**:
- Exchange APIs (Binance, Coinbase, Coinone)
- CCXT library for multi-exchange data
- TradingView for visual validation
- CryptoCompare, CoinGecko for historical data

### 3. Critical Pitfalls to Avoid

#### A. Overfitting (Most Common!)
**Problem**: Strategy works perfectly on historical data but fails live
**Signs**:
- Too many parameters (>5-7 is suspicious)
- Exceptional returns (>200% annually with low drawdown)
- Strategy only works on specific date ranges
- Complex rules that don't have logical basis

**Solutions**:
- Keep strategies simple (KISS principle)
- Use out-of-sample testing (train on 70%, test on 30%)
- Walk-forward optimization
- Validate on different assets/timeframes

#### B. Look-Ahead Bias
**Problem**: Using future information in current decisions
**Examples**:
- Using daily close before the day ends
- Calculating indicators that peek into future candles
- Knowing which trades are winners in advance

**Solutions**:
- Only use data available at decision time
- Shift indicator calculations properly
- Review entry/exit logic carefully

#### C. Survivorship Bias
**Problem**: Only testing on assets that still exist
**Example**: Testing on current top 20 coins ignores coins that crashed to zero

**Solutions**:
- Include delisted/failed assets in universe
- Test on broader universe at each point in time

#### D. Unrealistic Execution
**Problem**: Assuming perfect fills at exact prices
**Reality**:
- Slippage (0.1-0.5% typical, more in volatile periods)
- Fees (0.1-0.2% per trade)
- Latency (seconds to minutes)
- Partial fills and rejected orders

**Solutions**:
- Add realistic slippage model (0.1-0.3% conservative)
- Include ALL fees (maker, taker, funding)
- Test with limit orders vs market orders
- Assume worst-case execution on large orders

### 4. Proper Backtesting Methodology

**Step-by-Step Process**:

1. **Define Strategy Rules Clearly**
   - Entry conditions (exact rules)
   - Exit conditions (take profit, stop loss)
   - Position sizing rules
   - Asset selection criteria

2. **Split Data**
   - Training set: 60-70% of data
   - Validation set: 15-20%
   - Test set (untouched): 15-20%

3. **Run Initial Backtest**
   - Use training data only
   - Record all metrics

4. **Validate**
   - Test on validation set WITHOUT changing rules
   - If performance drops >30%, likely overfitted

5. **Final Test**
   - Run on test set ONCE
   - This is your realistic expectation

6. **Paper Trade**
   - 3-6 months of live paper trading
   - Compare to backtest results
   - Expect 20-40% performance haircut

### 5. Key Metrics to Evaluate

**Primary Metrics**:
| Metric | Good | Excellent | Concerning |
|--------|------|-----------|------------|
| Sharpe Ratio | >1.0 | >2.0 | <0.5 |
| Max Drawdown | <30% | <20% | >50% |
| Win Rate | >40% | >55% | <30% |
| Profit Factor | >1.5 | >2.0 | <1.2 |
| Avg Trade | >0.5% | >1% | <0% |

**Secondary Metrics**:
- Recovery Factor: Total Return / Max Drawdown
- Calmar Ratio: Annual Return / Max Drawdown
- Number of Trades: Enough for statistical significance (>100)
- Average Holding Period: Matches strategy intent

### 6. Dynamic Position Sizing

**CRITICAL**: Don't use fixed dollar amounts!

**Wrong**: $10,000 per trade on $100,000 account
**Right**: 10% of current account value per trade

This ensures:
- Compounding works correctly
- Drawdowns are properly modeled
- Results are scalable

### 7. Red Flags in Backtest Results

Warning signs that suggest unreliable results:
- [ ] Sharpe Ratio > 3 (too good to be true)
- [ ] Max Drawdown < 10% with high returns
- [ ] Win Rate > 80% (unless very tight stops)
- [ ] No losing months in multi-year test
- [ ] Dramatic performance drop in out-of-sample
- [ ] Only works on one specific asset
- [ ] Requires perfect timing to work

## Output Format (For Backtest Review)

```
## Backtest Analysis Review

### Strategy Summary
- Name: [Strategy Name]
- Timeframe: [1H/4H/1D]
- Test Period: [Start Date] to [End Date]
- Assets Tested: [List]

### Performance Metrics
| Metric | Value | Assessment |
|--------|-------|------------|
| Total Return | X% | [Good/Concerning] |
| Annual Return | X% | [Good/Concerning] |
| Max Drawdown | X% | [Good/Concerning] |
| Sharpe Ratio | X | [Good/Concerning] |
| Win Rate | X% | [Good/Concerning] |
| Profit Factor | X | [Good/Concerning] |
| Total Trades | X | [Sufficient/Insufficient] |

### Overfitting Check
- Parameter Count: [X] - [OK/Too Many]
- Out-of-Sample Test: [Performed/Not Performed]
- Performance Degradation: [X]%

### Realism Check
- Slippage Included: [Yes/No]
- Fees Included: [Yes/No]
- Dynamic Sizing: [Yes/No]

### Red Flags Detected
[List any concerns]

### Recommendations
1. [Specific recommendation]
2. [Specific recommendation]

### Confidence Level: [High/Medium/Low]
[Explanation of confidence assessment]
```

## References
- Backtesting Guide: [Coin Bureau](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy/)
- Best Practices: [3Commas](https://3commas.io/blog/comprehensive-2025-guide-to-backtesting-ai-trading)
- Crucial Tips: [Shrimpy Academy](https://academy.shrimpy.io/post/crypto-backtesting-5-crucial-tips)
- Strategy Testing: [CoinGecko](https://www.coingecko.com/learn/popular-crypto-trading-strategies-backtesting)

$ARGUMENTS
