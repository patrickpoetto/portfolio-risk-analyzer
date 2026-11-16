"""
Module for historical portfolio backtesting
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from portfolio_config import BACKTEST_CONFIG, CASH_CONFIG, RISK_FREE_RATE, MARKET_CONDITION_CONFIG


def download_benchmark_data(period: str = "5y") -> pd.DataFrame:
    """Downloads data for the main benchmarks"""

    # Readable name -> ticker, read from BACKTEST_CONFIG so that editing the
    # configuration also takes effect here
    benchmarks = {
        name: ticker
        for ticker, name in BACKTEST_CONFIG['benchmark_names'].items()
    }

    print(f"📊 Downloading benchmarks ({period})...")

    data = {}
    for name, ticker in benchmarks.items():
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=period)
            if not hist.empty:
                close = hist['Close']
                # Same reason as risk_analysis.fetch_historical_data: strips
                # the timezone so dates line up with the portfolio's prices
                # (otherwise comparing a tz-aware Timestamp with a tz-naive
                # one raises a TypeError further down in run_backtest)
                close.index = close.index.tz_localize(None).normalize()
                data[name] = close
                print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ⚠️  {name}: {str(e)[:50]}")

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Data cleanup
    df = df.dropna(how='all')
    df = df.ffill()
    df = df.dropna()

    return df


def calculate_portfolio_performance(prices: pd.DataFrame,
                                    weights: Dict[str, float]) -> pd.Series:
    """
    Computes the portfolio's historical performance with periodic rebalancing

    Args:
        prices: DataFrame with historical prices
        weights: Dict with weights {ticker: weight}

    Returns:
        Time series with portfolio value normalized to 100
    """
    # Normalize weights
    total_weight = sum(weights.values())
    if total_weight == 0:
        return pd.Series()

    normalized_weights = {k: v/total_weight for k, v in weights.items()}

    # Keep only tickers that are present
    valid_weights = {k: v for k, v in normalized_weights.items() if k in prices.columns}

    if not valid_weights:
        return pd.Series()

    # Compute returns
    returns = prices.pct_change()

    # Portfolio returns
    portfolio_returns = pd.Series(0, index=returns.index)
    for ticker, weight in valid_weights.items():
        portfolio_returns += returns[ticker].fillna(0) * weight

    # Cumulative performance (normalized to 100)
    portfolio_value = (1 + portfolio_returns).cumprod() * 100

    return portfolio_value


def calculate_statistics(returns: pd.Series) -> Dict:
    """Computes performance statistics"""

    if len(returns) < 2:
        return {}

    # Drop NaNs
    returns = returns.dropna()

    if len(returns) < 2:
        return {}

    # Percentage returns
    total_return = (returns.iloc[-1] / returns.iloc[0] - 1)

    # Compute daily returns
    daily_returns = returns.pct_change().dropna()

    if len(daily_returns) < 10:
        return {}

    # Annualize correctly
    days = len(daily_returns)
    years = days / 252

    if years > 0 and total_return > -0.99:  # Avoid negative values under the root
        annual_return = (1 + total_return) ** (1/years) - 1
    else:
        annual_return = 0

    annual_vol = daily_returns.std() * np.sqrt(252)

    # Sharpe (risk-free = configured rate)
    sharpe = (annual_return - RISK_FREE_RATE) / annual_vol if annual_vol > 0 else 0

    # Max Drawdown
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'final_value': returns.iloc[-1],
        'start_value': returns.iloc[0]
    }


def run_backtest(prices: pd.DataFrame,
                weights: Dict[str, float],
                period: str = "5y",
                oos_days: int = 0) -> Tuple[pd.DataFrame, Dict, Dict]:
    """
    Runs a full backtest with benchmark comparison.

    Args:
        oos_days: if > 0, in addition to the statistics for the whole
            period, statistics are also computed for just the last
            `oos_days` days, i.e. the out-of-sample window NEVER seen by
            scouting/selection/weighting. This is the only part of the
            backtest that constitutes an honest test of the selection; the
            rest of the chart is shown for context but is in-sample (the
            same data used to choose the stocks), so it is systematically
            optimistic.

    Returns:
        DataFrame with portfolio + benchmark performance, Dict of
        statistics for the whole period, Dict of statistics for the
        out-of-sample window only (empty if oos_days=0 or insufficient)
    """

    print("\n" + "="*80)
    print("📈 HISTORICAL PORTFOLIO BACKTEST")
    print("="*80)

    # Portfolio performance
    print(f"\nComputing portfolio performance...")
    portfolio_perf = calculate_portfolio_performance(prices, weights)

    if portfolio_perf.empty:
        print("❌ Unable to compute portfolio performance")
        return pd.DataFrame(), {}, {}

    # Download benchmarks
    benchmark_data = download_benchmark_data(period)

    if benchmark_data.empty:
        print("⚠️  No benchmark available")
        results = pd.DataFrame({'Portfolio': portfolio_perf})
    else:
        # Find the common start date for all series
        common_start = max(portfolio_perf.index[0], benchmark_data.index[0])
        common_end = min(portfolio_perf.index[-1], benchmark_data.index[-1])

        # Filter all data to the same time range
        portfolio_aligned = portfolio_perf[(portfolio_perf.index >= common_start) &
                                          (portfolio_perf.index <= common_end)]
        benchmark_aligned = benchmark_data[(benchmark_data.index >= common_start) &
                                          (benchmark_data.index <= common_end)]

        # Build the results DataFrame
        results = pd.DataFrame(index=portfolio_aligned.index)

        # Normalize the portfolio to 100 on the first date
        results['Portfolio'] = (portfolio_aligned / portfolio_aligned.iloc[0]) * 100

        # Normalize all benchmarks to 100 on the same date
        for col in benchmark_aligned.columns:
            bench_series = benchmark_aligned[col].dropna()
            if len(bench_series) > 10:  # At least 10 data points
                # Reindex to align perfectly
                bench_reindexed = bench_series.reindex(results.index, method='ffill')
                results[col] = (bench_reindexed / bench_reindexed.iloc[0]) * 100

        # Drop any remaining NaNs
        results = results.dropna()

        # Debug info
        print(f"\n✅ Data aligned: {len(results)} days")
        print(f"   Period: {results.index[0].strftime('%Y-%m-%d')} → {results.index[-1].strftime('%Y-%m-%d')}")
        print(f"   Columns: {', '.join(results.columns)}")
        print(f"\n   Starting values (base 100):")
        for col in results.columns:
            print(f"     {col}: {results[col].iloc[0]:.2f}")
        print(f"   Final values:")
        for col in results.columns:
            print(f"     {col}: {results[col].iloc[-1]:.2f}")

    # Compute statistics
    print("\n" + "="*80)
    print("📊 PERFORMANCE STATISTICS")
    print("="*80)

    stats = {}
    for col in results.columns:
        stats[col] = calculate_statistics(results[col])

        print(f"\n{col}:")
        print(f"  Total return:         {stats[col]['total_return']:>8.2%}")
        print(f"  Annual return:        {stats[col]['annual_return']:>8.2%}")
        print(f"  Annual volatility:    {stats[col]['annual_volatility']:>8.2%}")
        print(f"  Sharpe Ratio:         {stats[col]['sharpe_ratio']:>8.2f}")
        print(f"  Max Drawdown:         {stats[col]['max_drawdown']:>8.2%}")

    # Statistics for the out-of-sample window only (honest, non-circular test)
    stats_oos = {}
    if 0 < oos_days < len(results):
        print("\n" + "="*80)
        print(f"📊 OUT-OF-SAMPLE STATISTICS (last {oos_days} days, never seen by the selection)")
        print("="*80)

        for col in results.columns:
            oos_stats = calculate_statistics(results[col].iloc[-oos_days:])
            if not oos_stats:
                continue
            stats_oos[col] = oos_stats

            print(f"\n{col}:")
            print(f"  Total return:         {oos_stats['total_return']:>8.2%}")
            print(f"  Annual return:        {oos_stats['annual_return']:>8.2%}")
            print(f"  Sharpe Ratio:         {oos_stats['sharpe_ratio']:>8.2f}")
            print(f"  Max Drawdown:         {oos_stats['max_drawdown']:>8.2%}")

    print("\n" + "="*80)

    return results, stats, stats_oos


def infer_market_condition(backtest_results: pd.DataFrame,
                           reference_col: str = "S&P 500") -> str:
    """
    Estimates the market condition ("bullish", "bearish", "volatile",
    "normal") from the recent trend and volatility of a benchmark in the
    backtest, instead of always assuming "normal" regardless of the real
    context.

    Simple, transparent rule (thresholds in MARKET_CONDITION_CONFIG):
    - if the recent annualized volatility exceeds volatility_threshold => "volatile"
    - otherwise, if the return over the window exceeds +/- trend_threshold => "bullish"/"bearish"
    - otherwise "normal"
    This is not a real market-regime model, but it's better than a fixed
    value: it changes based on the downloaded data instead of always being inert.
    """
    lookback = MARKET_CONDITION_CONFIG['lookback_days']

    if backtest_results is None or backtest_results.empty or len(backtest_results) < lookback:
        return "normal"

    col = reference_col if reference_col in backtest_results.columns else backtest_results.columns[0]
    recent = backtest_results[col].iloc[-lookback:]

    trend_return = recent.iloc[-1] / recent.iloc[0] - 1
    daily_returns = recent.pct_change().dropna()
    realized_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0

    if realized_vol > MARKET_CONDITION_CONFIG['volatility_threshold']:
        return "volatile"
    if trend_return > MARKET_CONDITION_CONFIG['trend_threshold']:
        return "bullish"
    if trend_return < -MARKET_CONDITION_CONFIG['trend_threshold']:
        return "bearish"
    return "normal"


def calculate_smart_cash_allocation(metrics: pd.DataFrame,
                                    portfolio_volatility: float,
                                    market_condition: str = "normal") -> float:
    """
    Computes the optimal cash percentage based on:
    - Portfolio volatility
    - Market conditions
    - Asset quality score

    Returns:
        Recommended cash percentage (bounded by CASH_CONFIG min/max)
    """

    # Base cash and volatility adjustment, from CASH_CONFIG
    base_cash = CASH_CONFIG['base_allocation']
    vol_adjustment = portfolio_volatility * CASH_CONFIG['volatility_multiplier']

    # Asset quality adjustment
    # If many assets have Sharpe < 0.5, increase cash
    if not metrics.empty and 'sharpe_ratio' in metrics.columns:
        low_quality_ratio = (metrics['sharpe_ratio'] < 0.5).sum() / len(metrics)
        quality_adjustment = low_quality_ratio * 0.10
    else:
        quality_adjustment = 0

    # Market condition adjustment
    market_adjustments = {
        "bullish": -0.05,  # Less cash in a bull market
        "normal": 0,
        "bearish": 0.10,   # More cash in a bear market
        "volatile": 0.15   # Even more cash if highly volatile
    }
    market_adjustment = market_adjustments.get(market_condition, 0)

    # Compute total cash
    total_cash = base_cash + vol_adjustment + quality_adjustment + market_adjustment

    # Bound to the configured limits
    total_cash = max(CASH_CONFIG['min_cash'], min(CASH_CONFIG['max_cash'], total_cash))

    return total_cash
