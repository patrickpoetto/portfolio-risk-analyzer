#!/usr/bin/env python3
"""
Quick script to view the suggested optimal allocation
"""

from portfolio_config import PORTFOLIO_TICKERS
from risk_analysis import (
    fetch_historical_data,
    calculate_metrics,
    suggest_optimal_allocation
)
import sys

def main():
    risk_profile = sys.argv[1] if len(sys.argv) > 1 else "moderate"

    if risk_profile not in ["conservative", "moderate", "aggressive"]:
        print("❌ Invalid profile. Use: conservative, moderate, aggressive")
        sys.exit(1)

    print(f"🔍 Computing optimal allocation ({risk_profile})...")
    print("=" * 80)

    tickers = list(PORTFOLIO_TICKERS.keys())

    # Download data
    try:
        prices = fetch_historical_data(tickers, period="1y")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Compute metrics
    successful_tickers = list(prices.columns)
    weights = {t: 1.0/len(successful_tickers) for t in successful_tickers}
    metrics = calculate_metrics(prices, weights)

    # Suggestions
    suggested = suggest_optimal_allocation(metrics, target_risk=risk_profile)

    if suggested.empty:
        print("❌ Unable to compute allocation")
        sys.exit(1)

    print(f"\n💡 SUGGESTED OPTIMAL ALLOCATION - {risk_profile.upper()} Profile")
    print("=" * 80)
    print(f"{'#':<4} {'Ticker':<10} {'Weight':<8} {'Return':<12} {'Volatility':<12} {'Sharpe':<8}")
    print("-" * 80)

    total = 0
    for idx, row in suggested.head(20).iterrows():
        weight_pct = row['suggested_weight'] * 100
        total += weight_pct
        print(f"{idx+1:<4} {row['ticker']:<10} {weight_pct:>6.2f}%  "
              f"{row['annual_return']:>10.2%}  {row['annual_volatility']:>10.2%}  "
              f"{row['sharpe_ratio']:>6.2f}")

    if len(suggested) > 20:
        remaining = len(suggested) - 20
        remaining_weight = (1 - total/100) * 100
        print(f"{'...':<4} {'Other':<10} {remaining_weight:>6.2f}%  ({remaining} stocks)")

    print("-" * 80)
    print(f"{'TOTAL':<14} {total:>6.2f}%")
    print()
    print("💾 For the full report with charts: python main.py --risk " + risk_profile)
    print()

if __name__ == "__main__":
    main()
