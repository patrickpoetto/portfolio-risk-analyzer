"""
Modulo per backtest storico del portafoglio
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from portfolio_config import BACKTEST_CONFIG, CASH_CONFIG, RISK_FREE_RATE, MARKET_CONDITION_CONFIG


def download_benchmark_data(period: str = "5y") -> pd.DataFrame:
    """Scarica dati dei principali benchmark"""

    # Nome leggibile -> ticker, letti da BACKTEST_CONFIG in modo che
    # modificare la configurazione abbia effetto anche qui
    benchmarks = {
        name: ticker
        for ticker, name in BACKTEST_CONFIG['benchmark_names'].items()
    }

    print(f"📊 Scaricamento benchmark ({period})...")
    
    data = {}
    for name, ticker in benchmarks.items():
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=period)
            if not hist.empty:
                close = hist['Close']
                # Stesso motivo di risk_analysis.fetch_historical_data: rimuove
                # il fuso orario così le date combaciano con i prezzi del
                # portafoglio (altrimenti confrontare Timestamp tz-aware con
                # tz-naive solleva TypeError più avanti in run_backtest)
                close.index = close.index.tz_localize(None).normalize()
                data[name] = close
                print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ⚠️  {name}: {str(e)[:50]}")
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Pulizia dati
    df = df.dropna(how='all')
    df = df.ffill()
    df = df.dropna()
    
    return df


def calculate_portfolio_performance(prices: pd.DataFrame, 
                                    weights: Dict[str, float]) -> pd.Series:
    """
    Calcola performance storica del portafoglio con rebalancing periodico
    
    Args:
        prices: DataFrame con prezzi storici
        weights: Dizionario con pesi {ticker: peso}
    
    Returns:
        Serie temporale con valore del portafoglio normalizzato a 100
    """
    # Normalizza pesi
    total_weight = sum(weights.values())
    if total_weight == 0:
        return pd.Series()
    
    normalized_weights = {k: v/total_weight for k, v in weights.items()}
    
    # Filtra solo ticker presenti
    valid_weights = {k: v for k, v in normalized_weights.items() if k in prices.columns}
    
    if not valid_weights:
        return pd.Series()
    
    # Calcola rendimenti
    returns = prices.pct_change()
    
    # Rendimenti del portafoglio
    portfolio_returns = pd.Series(0, index=returns.index)
    for ticker, weight in valid_weights.items():
        portfolio_returns += returns[ticker].fillna(0) * weight
    
    # Performance cumulativa (normalizzata a 100)
    portfolio_value = (1 + portfolio_returns).cumprod() * 100
    
    return portfolio_value


def calculate_statistics(returns: pd.Series) -> Dict:
    """Calcola statistiche di performance"""
    
    if len(returns) < 2:
        return {}
    
    # Rimuovi NaN
    returns = returns.dropna()
    
    if len(returns) < 2:
        return {}
    
    # Rendimenti percentuali
    total_return = (returns.iloc[-1] / returns.iloc[0] - 1)
    
    # Calcola rendimenti giornalieri
    daily_returns = returns.pct_change().dropna()
    
    if len(daily_returns) < 10:
        return {}
    
    # Annualizza correttamente
    days = len(daily_returns)
    years = days / 252
    
    if years > 0 and total_return > -0.99:  # Evita valori negativi nel calcolo radice
        annual_return = (1 + total_return) ** (1/years) - 1
    else:
        annual_return = 0
    
    annual_vol = daily_returns.std() * np.sqrt(252)
    
    # Sharpe (risk-free = 2%)
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
    Esegue backtest completo con confronto benchmark.

    Args:
        oos_days: se > 0, oltre alle statistiche sull'intero periodo vengono
            calcolate anche quelle sui soli ultimi `oos_days` giorni, cioè la
            finestra out-of-sample MAI vista da scouting/selezione/pesi.
            Questa è l'unica parte del backtest che costituisce un test
            onesto della selezione; il resto del grafico è mostrato per
            contesto ma è in-sample (gli stessi dati usati per scegliere i
            titoli), quindi sistematicamente ottimistico.

    Returns:
        DataFrame con performance portfolio + benchmark, Dict statistiche sul
        periodo intero, Dict statistiche sulla sola finestra out-of-sample
        (vuoto se oos_days=0 o insufficiente)
    """

    print("\n" + "="*80)
    print("📈 BACKTEST STORICO PORTAFOGLIO")
    print("="*80)

    # Performance portafoglio
    print(f"\nCalcolo performance portafoglio...")
    portfolio_perf = calculate_portfolio_performance(prices, weights)

    if portfolio_perf.empty:
        print("❌ Impossibile calcolare performance portafoglio")
        return pd.DataFrame(), {}, {}
    
    # Download benchmark
    benchmark_data = download_benchmark_data(period)
    
    if benchmark_data.empty:
        print("⚠️  Nessun benchmark disponibile")
        results = pd.DataFrame({'Portafoglio': portfolio_perf})
    else:
        # Trova la data di inizio comune a tutti
        common_start = max(portfolio_perf.index[0], benchmark_data.index[0])
        common_end = min(portfolio_perf.index[-1], benchmark_data.index[-1])
        
        # Filtra tutti i dati allo stesso range temporale
        portfolio_aligned = portfolio_perf[(portfolio_perf.index >= common_start) & 
                                          (portfolio_perf.index <= common_end)]
        benchmark_aligned = benchmark_data[(benchmark_data.index >= common_start) & 
                                          (benchmark_data.index <= common_end)]
        
        # Crea DataFrame risultati
        results = pd.DataFrame(index=portfolio_aligned.index)
        
        # Normalizza portafoglio a 100 alla prima data
        results['Portafoglio'] = (portfolio_aligned / portfolio_aligned.iloc[0]) * 100
        
        # Normalizza tutti i benchmark a 100 alla stessa data
        for col in benchmark_aligned.columns:
            bench_series = benchmark_aligned[col].dropna()
            if len(bench_series) > 10:  # Almeno 10 punti dati
                # Reindex per allineare perfettamente
                bench_reindexed = bench_series.reindex(results.index, method='ffill')
                results[col] = (bench_reindexed / bench_reindexed.iloc[0]) * 100
        
        # Rimuovi NaN rimanenti
        results = results.dropna()
        
        # Debug info
        print(f"\n✅ Dati allineati: {len(results)} giorni")
        print(f"   Periodo: {results.index[0].strftime('%Y-%m-%d')} → {results.index[-1].strftime('%Y-%m-%d')}")
        print(f"   Colonne: {', '.join(results.columns)}")
        print(f"\n   Valori iniziali (base 100):")
        for col in results.columns:
            print(f"     {col}: {results[col].iloc[0]:.2f}")
        print(f"   Valori finali:")
        for col in results.columns:
            print(f"     {col}: {results[col].iloc[-1]:.2f}")
    
    # Calcola statistiche
    print("\n" + "="*80)
    print("📊 STATISTICHE PERFORMANCE")
    print("="*80)
    
    stats = {}
    for col in results.columns:
        stats[col] = calculate_statistics(results[col])
        
        print(f"\n{col}:")
        print(f"  Rendimento totale:    {stats[col]['total_return']:>8.2%}")
        print(f"  Rendimento annuale:   {stats[col]['annual_return']:>8.2%}")
        print(f"  Volatilità annuale:   {stats[col]['annual_volatility']:>8.2%}")
        print(f"  Sharpe Ratio:         {stats[col]['sharpe_ratio']:>8.2f}")
        print(f"  Max Drawdown:         {stats[col]['max_drawdown']:>8.2%}")

    # Statistiche sulla sola finestra out-of-sample (test onesto, non circolare)
    stats_oos = {}
    if 0 < oos_days < len(results):
        print("\n" + "="*80)
        print(f"📊 STATISTICHE OUT-OF-SAMPLE (ultimi {oos_days} giorni, mai visti dalla selezione)")
        print("="*80)

        for col in results.columns:
            oos_stats = calculate_statistics(results[col].iloc[-oos_days:])
            if not oos_stats:
                continue
            stats_oos[col] = oos_stats

            print(f"\n{col}:")
            print(f"  Rendimento totale:    {oos_stats['total_return']:>8.2%}")
            print(f"  Rendimento annuale:   {oos_stats['annual_return']:>8.2%}")
            print(f"  Sharpe Ratio:         {oos_stats['sharpe_ratio']:>8.2f}")
            print(f"  Max Drawdown:         {oos_stats['max_drawdown']:>8.2%}")

    print("\n" + "="*80)

    return results, stats, stats_oos


def infer_market_condition(backtest_results: pd.DataFrame,
                           reference_col: str = "S&P 500") -> str:
    """
    Stima la condizione di mercato ("bullish", "bearish", "volatile", "normal")
    dal trend e dalla volatilità recenti di un benchmark nel backtest, invece
    di assumerla sempre "normal" a prescindere dal contesto reale.

    Regola semplice e trasparente (soglie in MARKET_CONDITION_CONFIG):
    - se la volatilità annualizzata recente supera volatility_threshold => "volatile"
    - altrimenti, se il rendimento sulla finestra supera +/- trend_threshold => "bullish"/"bearish"
    - altrimenti "normal"
    Non è un vero modello di regime di mercato, ma è meglio di un valore
    fisso: cambia in base ai dati scaricati invece di essere sempre inerte.
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
    Calcola percentuale ottimale di liquidità basata su:
    - Volatilità del portafoglio
    - Condizioni di mercato
    - Score di qualità degli asset
    
    Returns:
        Percentuale di cash consigliata (limitata da CASH_CONFIG min/max)
    """

    # Base cash e aggiustamento per volatilità, da CASH_CONFIG
    base_cash = CASH_CONFIG['base_allocation']
    vol_adjustment = portfolio_volatility * CASH_CONFIG['volatility_multiplier']

    # Aggiustamento per qualità asset
    # Se molti asset hanno Sharpe < 0.5, aumenta cash
    if not metrics.empty and 'sharpe_ratio' in metrics.columns:
        low_quality_ratio = (metrics['sharpe_ratio'] < 0.5).sum() / len(metrics)
        quality_adjustment = low_quality_ratio * 0.10
    else:
        quality_adjustment = 0

    # Aggiustamento per condizioni mercato
    market_adjustments = {
        "bullish": -0.05,  # Meno cash in bull market
        "normal": 0,
        "bearish": 0.10,   # Più cash in bear market
        "volatile": 0.15   # Ancora più cash se molto volatile
    }
    market_adjustment = market_adjustments.get(market_condition, 0)

    # Calcola cash totale
    total_cash = base_cash + vol_adjustment + quality_adjustment + market_adjustment

    # Limita ai bound configurati
    total_cash = max(CASH_CONFIG['min_cash'], min(CASH_CONFIG['max_cash'], total_cash))

    return total_cash
