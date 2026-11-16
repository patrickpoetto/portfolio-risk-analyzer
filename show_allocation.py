#!/usr/bin/env python3
"""
Script veloce per visualizzare l'allocazione ottimale suggerita
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
        print("❌ Profilo non valido. Usa: conservative, moderate, aggressive")
        sys.exit(1)
    
    print(f"🔍 Calcolo allocazione ottimale ({risk_profile})...")
    print("=" * 80)
    
    tickers = list(PORTFOLIO_TICKERS.keys())
    
    # Scarica dati
    try:
        prices = fetch_historical_data(tickers, period="1y")
    except Exception as e:
        print(f"❌ Errore: {e}")
        sys.exit(1)
    
    # Calcola metriche
    successful_tickers = list(prices.columns)
    weights = {t: 1.0/len(successful_tickers) for t in successful_tickers}
    metrics = calculate_metrics(prices, weights)
    
    # Suggerimenti
    suggested = suggest_optimal_allocation(metrics, target_risk=risk_profile)
    
    if suggested.empty:
        print("❌ Impossibile calcolare allocazione")
        sys.exit(1)
    
    print(f"\n💡 ALLOCAZIONE OTTIMALE SUGGERITA - Profilo {risk_profile.upper()}")
    print("=" * 80)
    print(f"{'#':<4} {'Ticker':<10} {'Peso':<8} {'Rendimento':<12} {'Volatilità':<12} {'Sharpe':<8}")
    print("-" * 80)
    
    total = 0
    for idx, row in suggested.head(20).iterrows():
        peso_pct = row['suggested_weight'] * 100
        total += peso_pct
        print(f"{idx+1:<4} {row['ticker']:<10} {peso_pct:>6.2f}%  "
              f"{row['annual_return']:>10.2%}  {row['annual_volatility']:>10.2%}  "
              f"{row['sharpe_ratio']:>6.2f}")
    
    if len(suggested) > 20:
        remaining = len(suggested) - 20
        remaining_weight = (1 - total/100) * 100
        print(f"{'...':<4} {'Altri':<10} {remaining_weight:>6.2f}%  ({remaining} titoli)")
    
    print("-" * 80)
    print(f"{'TOTALE':<14} {total:>6.2f}%")
    print()
    print("💾 Per il report completo con grafici: python main.py --risk " + risk_profile)
    print()

if __name__ == "__main__":
    main()
