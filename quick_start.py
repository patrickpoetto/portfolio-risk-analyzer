#!/usr/bin/env python3
"""
Quick start script - fast usage example

Run this script for a quick demo on a subset of tickers.

Usage:
    python quick_start.py              # live data from Yahoo Finance (needs internet)
    python quick_start.py --offline    # synthetic sample data, works with no internet access
"""

import os
import sys

import pandas as pd

from risk_analysis import (
    fetch_historical_data,
    calculate_metrics,
    calculate_correlation_matrix,
    calculate_portfolio_metrics,
    get_diversification_score
)

# Select a subset of 10 tickers for a quick demo
DEMO_TICKERS = [
    "LEU",   # Nuclear
    "RGTI",  # Quantum
    "AVGO",  # Semiconductors
    "NEE",   # Energy
    "RTX",   # Defense
    "SNOW",  # Cloud
    "ORCL",  # Software
    "TSM",   # Semiconductors Asia
    "CVX",   # Oil
    "DLR",   # Data Centers
]

SAMPLE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data", "demo_prices.csv")


def load_offline_prices() -> pd.DataFrame:
    """
    Loads a small synthetic price history for DEMO_TICKERS from
    sample_data/demo_prices.csv, to demo the analysis pipeline with no
    internet access / no dependency on Yahoo Finance being reachable.

    This data is entirely synthetic (a random walk with a plausible
    drift/volatility per ticker) — it is NOT real market history, and is
    only meant to exercise the metrics/correlation/diversification code
    path end to end.
    """
    return pd.read_csv(SAMPLE_DATA_FILE, index_col="Date", parse_dates=True)


def main():
    offline = "--offline" in sys.argv[1:]

    print("🚀 QUICK START DEMO - Fast Portfolio Analysis")
    print("=" * 80)
    print(f"Analyzing {len(DEMO_TICKERS)} representative tickers...\n")

    if offline:
        print("📊 Loading synthetic sample data (offline mode, no network required)...")
        print("   ⚠️  This is synthetic data for demo purposes only, not real market history.")
        prices = load_offline_prices()
    else:
        # Download data (last year)
        print("📊 Downloading data...")
        prices = fetch_historical_data(DEMO_TICKERS, period="1y")

    # Compute metrics with uniform weights
    successful_tickers = list(prices.columns)
    weights = {t: 1.0/len(successful_tickers) for t in successful_tickers}

    print("\n📈 Computing metrics...")
    metrics = calculate_metrics(prices, weights)

    # Show top 5 by Sharpe Ratio
    print("\n🏆 TOP 5 BY SHARPE RATIO:")
    print("-" * 80)
    top_5 = metrics.nlargest(5, 'sharpe_ratio')[['ticker', 'annual_return',
                                                   'annual_volatility', 'sharpe_ratio']]

    for _, row in top_5.iterrows():
        print(f"{row['ticker']:>6} | Return: {row['annual_return']:>7.2%} | "
              f"Vol: {row['annual_volatility']:>6.2%} | Sharpe: {row['sharpe_ratio']:>5.2f}")

    # Portfolio metrics
    print("\n💼 PORTFOLIO METRICS (uniform weights):")
    print("-" * 80)
    portfolio_metrics = calculate_portfolio_metrics(prices, weights)

    print(f"Annual return:       {portfolio_metrics['annual_return']:>7.2%}")
    print(f"Annual volatility:   {portfolio_metrics['annual_volatility']:>7.2%}")
    print(f"Sharpe Ratio:        {portfolio_metrics['sharpe_ratio']:>7.2f}")
    print(f"Max Drawdown:        {portfolio_metrics['max_drawdown']:>7.2%}")

    # Diversification
    print("\n🎯 DIVERSIFICATION:")
    print("-" * 80)
    corr_matrix = calculate_correlation_matrix(prices)
    div_score = get_diversification_score(corr_matrix, weights)

    print(f"Score: {div_score:.1f}/100")

    if div_score > 70:
        print("✅ Excellent diversification!")
    elif div_score > 50:
        print("⚠️  Moderate diversification")
    else:
        print("❌ Low diversification")

    print("\n" + "=" * 80)
    print("✨ Demo complete!")
    print("\nFor the full analysis with all tickers and an HTML report:")
    print("  python main.py")
    print("\nFor more options:")
    print("  python main.py --help")
    print("=" * 80)


if __name__ == "__main__":
    main()
