#!/usr/bin/env python3
"""
Ticker validator - checks availability on Yahoo Finance
"""

import yfinance as yf
from portfolio_config import PORTFOLIO_TICKERS

def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    Checks whether a ticker is available on Yahoo Finance

    Returns:
        (is_valid, message)
    """
    try:
        stock = yf.Ticker(ticker)
        # Try to download a recent data point
        hist = stock.history(period="5d")

        if hist.empty:
            return False, f"❌ {ticker}: No data available"

        # Check that it has a name
        info = stock.info
        name = info.get('longName') or info.get('shortName') or 'N/A'

        return True, f"✅ {ticker}: {name}"

    except Exception as e:
        return False, f"❌ {ticker}: Error - {str(e)[:50]}"


def validate_all_tickers(verbose=True):
    """
    Validates all tickers in the portfolio

    Returns:
        dict: {ticker: (is_valid, message)}
    """
    results = {}

    print("=" * 80)
    print("🔍 TICKER VALIDATION")
    print("=" * 80)
    print(f"Checking {len(PORTFOLIO_TICKERS)} tickers...")
    print()

    valid_count = 0
    invalid_count = 0

    for ticker, name in PORTFOLIO_TICKERS.items():
        is_valid, message = validate_ticker(ticker)
        results[ticker] = (is_valid, message)

        if is_valid:
            valid_count += 1
            if verbose:
                print(message)
        else:
            invalid_count += 1
            print(message)

    print()
    print("=" * 80)
    print(f"✅ Valid: {valid_count}")
    print(f"❌ Unavailable: {invalid_count}")
    print("=" * 80)

    if invalid_count > 0:
        print("\n💡 SUGGESTIONS:")
        print("Unavailable tickers may have:")
        print("  • Wrong symbol for Yahoo Finance")
        print("  • Wrong exchange suffix (.L, .DE, .AS, etc.)")
        print("  • Been delisted or no longer traded")
        print("\nCheck on: https://finance.yahoo.com/")

    return results


def suggest_alternatives():
    """
    Suggests alternatives for unavailable tickers
    """
    print("\n" + "=" * 80)
    print("💡 SUGGESTED ALTERNATIVES")
    print("=" * 80)

    suggestions = {
        "KAP": [
            "CCJ (Cameco Corp) - already included ✅",
            "UEC (Uranium Energy) - already included ✅",
            "URNM (Sprott Uranium ETF)",
            "URA (Global X Uranium ETF)"
        ],
        "BOE.ASX": [
            "PDN.AX (Paladin Energy - Australia)",
            "LEU (Centrus Energy) - already included ✅",
            "BWXT (BWX Technologies) - already included ✅"
        ],
        "CSG.AS": [
            "RTX (RTX Corporation) - already included ✅",
            "LMT (Lockheed Martin) - already included ✅",
            "BA (Boeing)",
            "NOC (Northrop Grumman)"
        ]
    }

    for ticker, alts in suggestions.items():
        print(f"\n{ticker}:")
        for alt in alts:
            print(f"  → {alt}")

    print()


if __name__ == "__main__":
    results = validate_all_tickers(verbose=True)

    # Only show invalid ones in the summary
    invalid = [t for t, (valid, _) in results.items() if not valid]

    if invalid:
        print(f"\n⚠️  Tickers to remove or replace: {', '.join(invalid)}")
        suggest_alternatives()
    else:
        print("\n🎉 All tickers are valid!")
