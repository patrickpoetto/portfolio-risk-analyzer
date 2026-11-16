#!/usr/bin/env python3
"""
Quick start script - Esempio rapido di utilizzo

Esegui questo script per una demo veloce con un subset di ticker
"""

from risk_analysis import (
    fetch_historical_data,
    calculate_metrics,
    calculate_correlation_matrix,
    calculate_portfolio_metrics,
    get_diversification_score
)

# Seleziona un subset di 10 ticker per demo veloce
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

def main():
    print("🚀 QUICK START DEMO - Analisi Rapida Portfolio")
    print("=" * 80)
    print(f"Analizzando {len(DEMO_TICKERS)} ticker rappresentativi...\n")
    
    # Scarica dati (ultimo anno)
    print("📊 Scaricamento dati...")
    prices = fetch_historical_data(DEMO_TICKERS, period="1y")
    
    # Calcola metriche con pesi uniformi
    successful_tickers = list(prices.columns)
    weights = {t: 1.0/len(successful_tickers) for t in successful_tickers}
    
    print("\n📈 Calcolo metriche...")
    metrics = calculate_metrics(prices, weights)
    
    # Mostra top 5 per Sharpe Ratio
    print("\n🏆 TOP 5 PER SHARPE RATIO:")
    print("-" * 80)
    top_5 = metrics.nlargest(5, 'sharpe_ratio')[['ticker', 'annual_return', 
                                                   'annual_volatility', 'sharpe_ratio']]
    
    for _, row in top_5.iterrows():
        print(f"{row['ticker']:>6} | Rend: {row['annual_return']:>7.2%} | "
              f"Vol: {row['annual_volatility']:>6.2%} | Sharpe: {row['sharpe_ratio']:>5.2f}")
    
    # Metriche di portafoglio
    print("\n💼 METRICHE PORTAFOGLIO (pesi uniformi):")
    print("-" * 80)
    portfolio_metrics = calculate_portfolio_metrics(prices, weights)
    
    print(f"Rendimento annuale:  {portfolio_metrics['annual_return']:>7.2%}")
    print(f"Volatilità annuale:  {portfolio_metrics['annual_volatility']:>7.2%}")
    print(f"Sharpe Ratio:        {portfolio_metrics['sharpe_ratio']:>7.2f}")
    print(f"Max Drawdown:        {portfolio_metrics['max_drawdown']:>7.2%}")
    
    # Diversificazione
    print("\n🎯 DIVERSIFICAZIONE:")
    print("-" * 80)
    corr_matrix = calculate_correlation_matrix(prices)
    div_score = get_diversification_score(corr_matrix, weights)
    
    print(f"Score: {div_score:.1f}/100")
    
    if div_score > 70:
        print("✅ Eccellente diversificazione!")
    elif div_score > 50:
        print("⚠️  Diversificazione moderata")
    else:
        print("❌ Bassa diversificazione")
    
    print("\n" + "=" * 80)
    print("✨ Demo completata!")
    print("\nPer l'analisi completa con tutti i ticker e report HTML:")
    print("  python main.py")
    print("\nPer maggiori opzioni:")
    print("  python main.py --help")
    print("=" * 80)


if __name__ == "__main__":
    main()
