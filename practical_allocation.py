"""
Modulo per calcolo allocazione pratica basata su capitale reale
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
from portfolio_config import (
    SECTOR_CLASSIFICATION,
    ALLOCATION_CONFIG,
    DIVERSIFICATION_TARGET_CONFIG,
    RISK_PROFILES,
    VALUATION_CONFIG
)
from risk_analysis import cap_weights


def determine_optimal_portfolio_size(total_capital: float,
                                     min_position_size: float = None) -> int:
    """
    Tetto di titoli che il capitale disponibile può sostenere, data la
    dimensione minima di posizione configurata (ALLOCATION_CONFIG
    ['min_position_size']). Non è una scelta per fasce arbitrarie: è
    semplicemente quante posizioni da almeno quella cifra il capitale può
    permettersi. Il numero di titoli EFFETTIVO combina questo vincolo con
    quello statistico calcolato da select_portfolio() / determine_
    diversification_optimal_n().

    Args:
        total_capital: Capitale totale da investire
        min_position_size: Dimensione minima posizione (default da config)

    Returns:
        Numero massimo di titoli sostenibile dal capitale
    """
    if min_position_size is None:
        min_position_size = ALLOCATION_CONFIG['min_position_size']

    if total_capital <= 0 or min_position_size <= 0:
        return 0

    return max(1, int(total_capital / min_position_size))


def build_covariance_matrix(metrics: pd.DataFrame, correlation_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Ricostruisce la matrice di covarianza (Cov_ij = corr_ij · vol_i · vol_j)
    dalle volatilità annualizzate già calcolate in metrics e dalla matrice
    di correlazione. Serve per misurare il rischio di portafoglio reale
    (w'Σw), non solo la correlazione media.
    """
    vols = metrics.set_index('ticker')['annual_volatility']
    tickers = [t for t in correlation_matrix.index if t in vols.index]
    corr = correlation_matrix.loc[tickers, tickers]
    vol = vols.loc[tickers]
    return corr.mul(vol, axis=0).mul(vol, axis=1)


def diversification_curve(ordered_tickers: List[str], cov_matrix: pd.DataFrame) -> List[Dict]:
    """
    Calcola, per ogni N crescente (nell'ordine di merito dato da
    select_smart_portfolio), la volatilità annualizzata di un portafoglio
    equipesato dei primi N titoli usando la VERA matrice di covarianza.

    Fondamento teorico: Evans & Archer (1968) e Elton & Gruber (1977) sulla
    "diversificazione ingenua" (naive diversification) mostrano che il
    rischio specifico di un portafoglio equipesato si riduce rapidamente
    aggiungendo titoli poco correlati, convergendo verso il rischio
    sistematico residuo con benefici marginali decrescenti. Qui misuriamo
    questa curva sui dati reali del portafoglio invece di assumerla in
    forma chiusa (che richiederebbe varianza e correlazione uniformi tra
    tutti i titoli, un'ipotesi semplificativa che i nostri dati non
    rispettano).
    """
    valid = [t for t in ordered_tickers if t in cov_matrix.index]
    curve = []
    for n in range(1, len(valid) + 1):
        subset = valid[:n]
        sub_cov = cov_matrix.loc[subset, subset].values
        w = np.full(n, 1.0 / n)
        variance = float(w @ sub_cov @ w)
        curve.append({'n': n, 'variance': variance, 'volatility': variance ** 0.5})
    return curve


def determine_diversification_optimal_n(curve: List[Dict],
                                        min_n: int = None,
                                        stability_tolerance: float = None,
                                        stability_window: int = None) -> int:
    """
    Trova il numero minimo di titoli oltre il quale il rischio di portafoglio
    (varianza equipesata, misurata sui dati reali) smette di scendere in modo
    stabile. Niente soglia percentuale teorica: si cerca direttamente il
    punto in cui la curva si stabilizza vicino al suo minimo assoluto.

    Usiamo una finestra di titoli consecutivi entro `stability_tolerance` dal
    minimo (non il primo singolo punto basso) per non scambiare un
    avvallamento isolato/rumoroso della curva per la vera convergenza: se non
    si trova nessuna finestra così ampia, la si restringe gradualmente fino a
    un singolo punto, garantendo comunque una risposta.

    Il risultato non scende mai sotto `min_n` (floor pratico da config).
    """
    if min_n is None:
        min_n = DIVERSIFICATION_TARGET_CONFIG['min_stocks']
    if stability_tolerance is None:
        stability_tolerance = DIVERSIFICATION_TARGET_CONFIG['stability_tolerance']
    if stability_window is None:
        stability_window = DIVERSIFICATION_TARGET_CONFIG['stability_window']

    if not curve:
        return min_n

    variances = [p['variance'] for p in curve]
    n_total = len(variances)
    global_min = min(variances)
    threshold = global_min * (1 + stability_tolerance)

    for window in range(min(stability_window, n_total), 0, -1):
        for i in range(n_total):
            window_end = min(i + window, n_total)
            if all(v <= threshold for v in variances[i:window_end]):
                return max(curve[i]['n'], min_n)

    return max(curve[-1]['n'], min_n)


def select_portfolio(metrics: pd.DataFrame,
                     correlation_matrix: pd.DataFrame,
                     total_capital: float,
                     target_risk: str = "moderate",
                     min_position_size: float = None) -> Tuple[List[str], Dict]:
    """
    Determina QUANTI titoli tenere in portafoglio e QUALI, combinando due
    vincoli indipendenti (nessun numero di titoli hardcoded per fasce):

    1. Statistico: il punto in cui la curva di diversificazione reale
       (`diversification_curve`) mostra benefici marginali ormai trascurabili
       nel ridurre ulteriormente il rischio di portafoglio.
    2. Di capitale: quante posizioni da almeno `min_position_size` il
       capitale disponibile può effettivamente sostenere.

    Vince il vincolo più restrittivo tra i due.

    Returns:
        (lista ticker selezionati in ordine di merito, dict con i dettagli
        del calcolo per trasparenza/riepilogo nel report)
    """
    empty_info = {
        'statistically_optimal_n': 0,
        'capital_affordable_n': 0,
        'n_stocks': 0,
        'diversification_curve': [],
        'binding_constraint': None,
    }

    valid_metrics = metrics[metrics['sharpe_ratio'].notna()].copy() if not metrics.empty else metrics
    if valid_metrics.empty or total_capital <= 0:
        return [], empty_info

    # Il "quanti" e il "quali" vanno misurati con due ordini diversi, per non
    # essere circolari: se misurassimo il beneficio di diversificazione
    # sull'ordine GIÀ ottimizzato per bassa correlazione, la curva
    # convergerebbe artificialmente in fretta (i primi titoli sarebbero già
    # scelti apposta per essere scorrelati tra loro). Usiamo quindi l'ordine
    # "naive" per Sharpe decrescente per misurare quanti titoli servono
    # (fedele al metodo di Evans & Archer 1968 sulla diversificazione
    # ingenua), e l'algoritmo smart (performance + correlazione + settore)
    # solo per scegliere quali titoli tenere tra quei N.
    sharpe_order = valid_metrics.sort_values('sharpe_ratio', ascending=False)['ticker'].tolist()

    cov_matrix = build_covariance_matrix(metrics, correlation_matrix)
    curve = diversification_curve(sharpe_order, cov_matrix)

    statistically_optimal_n = determine_diversification_optimal_n(curve)
    capital_affordable_n = determine_optimal_portfolio_size(total_capital, min_position_size)

    n_stocks = max(1, min(statistically_optimal_n, capital_affordable_n, len(sharpe_order)))
    binding_constraint = 'capitale' if capital_affordable_n < statistically_optimal_n else 'diversificazione'

    selected_tickers = select_smart_portfolio(metrics, correlation_matrix, n_stocks, target_risk)

    info = {
        'statistically_optimal_n': statistically_optimal_n,
        'capital_affordable_n': capital_affordable_n,
        'n_stocks': n_stocks,
        'diversification_curve': curve,
        'binding_constraint': binding_constraint,
    }

    return selected_tickers, info


def select_smart_portfolio(metrics: pd.DataFrame,
                          correlation_matrix: pd.DataFrame,
                          n_stocks: int,
                          target_risk: str = "moderate") -> List[str]:
    """
    Seleziona N titoli migliori bilanciando performance e diversificazione
    
    Strategy:
    1. Ordina per Sharpe Ratio
    2. Seleziona top performer
    3. Per ogni successivo, considera:
       - Sharpe alto
       - Bassa correlazione con già selezionati
       - Diversità settoriale
    
    Returns:
        Lista di ticker selezionati
    """
    if metrics.empty or n_stocks <= 0:
        return []

    # Filtra titoli validi
    valid_metrics = metrics[metrics['sharpe_ratio'].notna()].copy()
    n_stocks = min(n_stocks, len(valid_metrics))
    if 'overvaluation_percentile' not in valid_metrics.columns:
        valid_metrics['overvaluation_percentile'] = 0.5

    selected = []
    selected_sectors = []

    # 1. Inizia dal miglior punteggio Sharpe corretto per sopravvalutazione:
    # un ottimo Sharpe ma molto caro rispetto al settore non deve
    # automaticamente vincere il primo posto
    valuation_penalty_weight = VALUATION_CONFIG['penalty_weight']
    valid_metrics['_seed_score'] = valid_metrics['sharpe_ratio'] * (
        1 - valid_metrics['overvaluation_percentile'] * valuation_penalty_weight
    )
    best_sharpe = valid_metrics.nlargest(1, '_seed_score')['ticker'].iloc[0]
    selected.append(best_sharpe)
    selected_sectors.append(get_sector(best_sharpe))
    
    # 2. Costruisci portafoglio iterativamente
    remaining = valid_metrics[~valid_metrics['ticker'].isin(selected)].copy()
    
    while len(selected) < n_stocks and not remaining.empty:
        # Calcola score per ogni candidato
        scores = []
        
        for _, row in remaining.iterrows():
            ticker = row['ticker']
            
            # Component 1: Performance (Sharpe normalized)
            sharpe_score = row['sharpe_ratio'] / valid_metrics['sharpe_ratio'].max()
            sharpe_score = max(0, min(1, sharpe_score))  # Clip 0-1
            
            # Component 2: Diversificazione (correlazione media con selezionati)
            if ticker in correlation_matrix.index:
                correlations = [abs(correlation_matrix.loc[ticker, s]) 
                               for s in selected 
                               if s in correlation_matrix.columns]
                avg_corr = np.mean(correlations) if correlations else 0.5
                diversification_score = 1 - avg_corr  # Più bassa correlazione = meglio
            else:
                diversification_score = 0.5
            
            # Component 3: Settore diverso (bonus se nuovo settore)
            ticker_sector = get_sector(ticker)
            sector_bonus = 0.2 if ticker_sector not in selected_sectors else 0

            # Score finale (pesi adattivi per profilo rischio da config)
            profile = RISK_PROFILES.get(target_risk, RISK_PROFILES['moderate'])
            sharpe_w = profile['sharpe_weight']
            corr_w = profile['correlation_weight']
            sector_w = profile['sector_weight']

            final_score = (sharpe_score * sharpe_w +
                         diversification_score * corr_w +
                         sector_bonus * sector_w)

            # Penalizza i titoli cari rispetto al proprio settore (percentile
            # 0-1 già calcolato in valuation.py e unito a metrics)
            overvaluation = row.get('overvaluation_percentile', 0.5)
            final_score *= (1 - overvaluation * valuation_penalty_weight)

            scores.append({'ticker': ticker, 'score': final_score,
                          'sector': ticker_sector})
        
        # Seleziona il migliore
        scores_df = pd.DataFrame(scores)
        best = scores_df.nlargest(1, 'score').iloc[0]
        
        selected.append(best['ticker'])
        selected_sectors.append(best['sector'])
        
        remaining = remaining[remaining['ticker'] != best['ticker']]
    
    return selected


def get_sector(ticker: str) -> str:
    """Trova settore di un ticker"""
    for sector, tickers in SECTOR_CLASSIFICATION.items():
        if ticker in tickers:
            return sector
    return "Altri"


def calculate_practical_allocation(total_capital: float,
                                   metrics: pd.DataFrame,
                                   correlation_matrix: pd.DataFrame,
                                   suggested_weights: Dict[str, float],
                                   cash_allocation: float = 0.0,
                                   target_risk: str = "moderate",
                                   min_position_size: float = None,
                                   selected_tickers: List[str] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Calcola allocazione pratica con cifre esatte

    Args:
        total_capital: Capitale totale disponibile
        metrics: DataFrame con metriche titoli
        correlation_matrix: Matrice correlazioni
        suggested_weights: Pesi ottimali originali
        cash_allocation: % da tenere in cash
        target_risk: Profilo di rischio
        min_position_size: Investimento minimo per titolo (default da config)
        selected_tickers: Se forniti, riusa questa selezione (stessi titoli già
            analizzati nel resto del report) invece di ricalcolarne una nuova
            con un numero di titoli potenzialmente diverso

    Returns:
        DataFrame con allocazione pratica, Dict con info aggiuntive
    """

    if min_position_size is None:
        min_position_size = ALLOCATION_CONFIG['min_position_size']

    # Capitale da investire (dopo cash)
    investable_capital = total_capital * (1 - cash_allocation)
    cash_amount = total_capital * cash_allocation

    if selected_tickers is not None:
        # Riusa la selezione già fatta a monte, per garantire che l'allocazione
        # pratica sia basata sugli stessi titoli analizzati nel resto del report
        n_stocks = len(selected_tickers)
    else:
        # Fallback per uso standalone: stesso criterio combinato (statistico +
        # capitale) di select_portfolio(), non solo il vincolo di capitale
        selected_tickers, _selection_info = select_portfolio(
            metrics, correlation_matrix, investable_capital, target_risk, min_position_size
        )
        n_stocks = len(selected_tickers)

    print(f"\n💰 ALLOCAZIONE PRATICA")
    print("="*80)
    print(f"Capitale totale:     €{total_capital:,.2f}")
    print(f"Liquidità ({cash_allocation:.1%}): €{cash_amount:,.2f}")
    print(f"Da investire:        €{investable_capital:,.2f}")
    print(f"N° titoli ottimale:  {n_stocks}")
    if n_stocks > 0:
        print(f"Investimento medio:  €{investable_capital/n_stocks:,.2f} per titolo")

    if n_stocks <= 0:
        print("⚠️  Capitale insufficiente per costruire una posizione minima")
        return pd.DataFrame(), {
            'n_stocks': 0,
            'total_invested': 0,
            'cash_amount': cash_amount,
            'cash_percent': cash_allocation * 100,
            'avg_correlation': 0,
            'sector_distribution': {},
            'correlation_matrix': pd.DataFrame(),
            'selected_tickers': []
        }

    if not selected_tickers:
        print("⚠️  Nessun titolo selezionabile con i dati disponibili")
        return pd.DataFrame(), {
            'n_stocks': 0,
            'total_invested': 0,
            'cash_amount': cash_amount,
            'cash_percent': cash_allocation * 100,
            'avg_correlation': 0,
            'sector_distribution': {},
            'correlation_matrix': pd.DataFrame(),
            'selected_tickers': []
        }

    print(f"\n✅ Titoli selezionati: {', '.join(selected_tickers[:10])}" +
          (f" +{len(selected_tickers)-10} altri" if len(selected_tickers) > 10 else ""))

    # Estrai pesi per titoli selezionati
    selected_weights = {t: suggested_weights.get(t, 0) for t in selected_tickers}
    total_selected_weight = sum(selected_weights.values())

    # Rinormalizza pesi
    if total_selected_weight > 0:
        normalized_weights = {t: w/total_selected_weight
                             for t, w in selected_weights.items()}
    else:
        # Fallback: pesi uniformi
        normalized_weights = {t: 1/len(selected_tickers)
                             for t in selected_tickers}

    # Riapplica il cap sul peso massimo per titolo (con redistribuzione
    # iterativa dell'eccesso): il cap configurato è pensato sull'universo
    # completo, su una selezione ristretta cap_weights lo alza automaticamente
    # al peso equamente distribuito quando altrimenti sarebbe irraggiungibile
    normalized_weights = cap_weights(normalized_weights, ALLOCATION_CONFIG['max_weight_per_stock'])

    # Calcola cifre esatte
    allocations = []
    for ticker in selected_tickers:
        weight = normalized_weights[ticker]
        amount = investable_capital * weight
        
        # Trova info ticker
        ticker_metrics = metrics[metrics['ticker'] == ticker]
        if not ticker_metrics.empty:
            sharpe = ticker_metrics['sharpe_ratio'].iloc[0]
            annual_return = ticker_metrics['annual_return'].iloc[0]
            volatility = ticker_metrics['annual_volatility'].iloc[0]
        else:
            sharpe = 0
            annual_return = 0
            volatility = 0
        
        allocations.append({
            'ticker': ticker,
            'settore': get_sector(ticker),
            'peso_%': weight * 100,
            'importo_€': amount,
            'sharpe_ratio': sharpe,
            'rendimento_annuo': annual_return,
            'volatilita': volatility
        })
    
    df_allocation = pd.DataFrame(allocations)
    df_allocation = df_allocation.sort_values('importo_€', ascending=False)
    
    # Calcola statistiche allocazione
    total_allocated = df_allocation['importo_€'].sum()
    
    # Correlazione media della selezione
    if len(selected_tickers) > 1:
        selected_corr_matrix = correlation_matrix.loc[
            [t for t in selected_tickers if t in correlation_matrix.index],
            [t for t in selected_tickers if t in correlation_matrix.columns]
        ]
        
        # Correlazione media (escludendo diagonale)
        mask = np.triu(np.ones_like(selected_corr_matrix, dtype=bool), k=1)
        avg_correlation = selected_corr_matrix.where(mask).stack().mean()
    else:
        avg_correlation = 0
        selected_corr_matrix = pd.DataFrame()
    
    # Diversificazione settoriale
    sector_dist = df_allocation.groupby('settore')['peso_%'].sum().to_dict()
    
    info = {
        'n_stocks': len(selected_tickers),
        'total_invested': total_allocated,
        'cash_amount': cash_amount,
        'cash_percent': cash_allocation * 100,
        'avg_correlation': avg_correlation,
        'sector_distribution': sector_dist,
        'correlation_matrix': selected_corr_matrix,
        'selected_tickers': selected_tickers
    }
    
    # Stampa riepilogo
    print(f"\n📊 STATISTICHE SELEZIONE")
    print("="*80)
    print(f"Correlazione media:  {avg_correlation:.2%}")
    print(f"Settori diversi:     {len(sector_dist)}")
    print(f"\nDistribuzione settoriale:")
    for sector, pct in sorted(sector_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector:.<30} {pct:>5.1f}%")
    
    return df_allocation, info
