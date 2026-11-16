"""
Modulo per analisi di rischio e rendimento del portafoglio
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
from portfolio_config import RISK_FREE_RATE, DIVERSIFICATION_CONFIG
warnings.filterwarnings('ignore')


def cap_weights(weights: Dict[str, float], max_weight: float) -> Dict[str, float]:
    """
    Applica un tetto al peso massimo per singolo ticker e redistribuisce
    l'eccesso sugli altri pesi, iterando finché il cap è rispettato da tutti.

    Un semplice "clip poi rinormalizza in un solo passo" non basta: dividere
    per la somma dopo il clip fa risalire anche i valori già cappati sopra
    la soglia. Se il cap è matematicamente irraggiungibile (troppo pochi
    ticker per il tetto configurato), il cap effettivo diventa il peso
    equamente distribuito (1/n).
    """
    tickers = list(weights.keys())
    n = len(tickers)
    if n == 0:
        return {}

    effective_cap = max(max_weight, 1 / n)

    values = np.array([weights[t] for t in tickers], dtype=float)
    total = values.sum()
    values = values / total if total > 0 else np.full(n, 1 / n)

    capped = np.zeros(n, dtype=bool)
    for _ in range(n):
        over = (values > effective_cap + 1e-12) & ~capped
        if not over.any():
            break
        values[over] = effective_cap
        capped |= over

        free = ~capped
        remaining = 1 - values[capped].sum()
        free_sum = values[free].sum()
        if free_sum > 0:
            values[free] = values[free] / free_sum * remaining
        else:
            break

    return dict(zip(tickers, values))


def fetch_historical_data(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Scarica dati storici per i ticker specificati
    
    Args:
        tickers: Lista di ticker symbols
        period: Periodo (1y, 2y, 5y, max)
    
    Returns:
        DataFrame con prezzi di chiusura aggiustati
    """
    print(f"📊 Scaricamento dati storici per {len(tickers)} ticker...")
    
    data = {}
    failed = []
    
    for ticker in tickers:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=period)
            
            if not hist.empty and len(hist) > 20:  # Minimo 20 giorni di dati
                close = hist['Close']
                # yfinance ritorna l'indice nel fuso orario della borsa di
                # quotazione (es. America/New_York per AAPL, Europe/London
                # per RR.L, Europe/Zurich per HOLN.SW...). Se lasciato così,
                # combinare ticker di borse diverse in un unico DataFrame non
                # allinea le stesse giornate di trading: "2026-06-29 New York"
                # e "2026-06-29 Londra" sono istanti UTC diversi, quindi
                # diventano righe separate. Il risultato è un indice gonfiato
                # di righe quasi-duplicate che il forward-fill successivo
                # riempie con rendimenti giornalieri artificiali vicini a
                # zero, falsando volatilità/rendimento annualizzati di
                # qualunque metrica calcolata a valle. Normalizziamo tutti gli
                # indici a semplici date (fuso rimosso) per farli combaciare.
                close.index = close.index.tz_localize(None).normalize()
                data[ticker] = close
            else:
                failed.append(ticker)
                print(f"  ⚠️  {ticker}: dati insufficienti")
                
        except Exception as e:
            failed.append(ticker)
            print(f"  ❌ {ticker}: errore - {str(e)[:50]}")
    
    if not data:
        raise ValueError("Nessun dato disponibile per i ticker forniti")
    
    df = pd.DataFrame(data)
    
    # Rimuovi righe completamente vuote (quando nessun mercato è aperto)
    df = df.dropna(how='all')
    
    # Forward fill per gestire orari di mercato diversi
    # Questo riempie i NA con l'ultimo prezzo valido
    df = df.ffill()
    
    # Rimuovi eventuali NA all'inizio (prima osservazione)
    df = df.dropna()
    
    print(f"✅ Dati scaricati: {len(data)} ticker, {len(failed)} falliti\n")

    return df


def split_in_sample_out_of_sample(prices: pd.DataFrame,
                                  oos_ratio: float,
                                  min_oos_days: int,
                                  max_oos_days: int) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    Divide la serie storica in una finestra "in-sample" (usata per scouting,
    selezione smart dei titoli e ottimizzazione dei pesi) e una finestra
    "out-of-sample" finale, mai vista da nessuna di queste fasi.

    Senza questo split, il backtest valuterebbe la selezione sugli stessi
    dati usati per sceglierla (i titoli vengono scelti perché hanno il
    miglior Sharpe storico proprio in quella finestra): un risultato
    circolare e sistematicamente troppo ottimistico, non un test onesto.

    Se lo storico disponibile è troppo corto per uno split sensato, ritorna
    tutti i dati come in-sample e nessun holdout (oos_days=0): il backtest,
    in quel caso, resta interamente in-sample e va interpretato con cautela
    (lo segnaliamo esplicitamente nel report).
    """
    total_days = len(prices)
    oos_days = int(total_days * oos_ratio)
    oos_days = max(min_oos_days, min(max_oos_days, oos_days))

    # Serve comunque spazio sufficiente per calcolare metriche significative
    # sulla parte in-sample (almeno il doppio della finestra di holdout)
    if oos_days <= 0 or total_days - oos_days < max(min_oos_days * 2, 60):
        return prices, prices.iloc[0:0], 0

    in_sample = prices.iloc[:-oos_days]
    out_of_sample = prices.iloc[-oos_days:]
    return in_sample, out_of_sample, oos_days


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calcola rendimenti giornalieri percentuali"""
    return prices.pct_change()


def calculate_metrics(prices: pd.DataFrame, weights: Dict[str, float] = None) -> pd.DataFrame:
    """
    Calcola metriche di rischio/rendimento per ogni ticker
    
    Args:
        prices: DataFrame con prezzi storici
        weights: Dizionario opzionale con pesi del portafoglio
    
    Returns:
        DataFrame con metriche calcolate
    """
    returns = calculate_returns(prices)
    
    metrics = []
    
    for ticker in prices.columns:
        if ticker not in returns.columns:
            continue
            
        ret = returns[ticker].dropna()
        
        # Richiede almeno 10 giorni di dati validi
        if len(ret) < 10:
            continue
        
        # Calcoli base
        volatility = ret.std()
        annual_volatility = volatility * np.sqrt(252)  # scaling per sqrt(T), valido sia in ottica aritmetica che geometrica

        # Calcolo rendimento totale nel periodo
        total_return = (prices[ticker].iloc[-1] / prices[ticker].iloc[0] - 1)

        # Annualizzazione GEOMETRICA (CAGR), coerente con quella usata in backtest.py:
        # composta correttamente nel tempo, a differenza di una semplice media
        # aritmetica giornaliera * 252 (che sovrastima il rendimento reale sui
        # titoli volatili per la disuguaglianza di Jensen)
        years = len(ret) / 252
        if years > 0 and total_return > -0.99:
            annual_return = (1 + total_return) ** (1 / years) - 1
        else:
            annual_return = 0

        # Sharpe Ratio
        sharpe = (annual_return - RISK_FREE_RATE) / annual_volatility if annual_volatility > 0 else 0

        # Max Drawdown
        cumulative = (1 + ret).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # VaR (Value at Risk) al 95%, giornaliero (NON annualizzato)
        var_95 = np.percentile(ret, 5)
        
        metrics.append({
            'ticker': ticker,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'weight': weights.get(ticker, 0) if weights else 0
        })
    
    df_metrics = pd.DataFrame(metrics)
    
    # Aggiungi rank per diverse metriche (solo se abbiamo dati)
    if not df_metrics.empty and len(df_metrics) > 0:
        df_metrics['return_rank'] = df_metrics['annual_return'].rank(ascending=False)
        df_metrics['sharpe_rank'] = df_metrics['sharpe_ratio'].rank(ascending=False)
        df_metrics['risk_rank'] = df_metrics['annual_volatility'].rank(ascending=True)  # Lower is better
    
    return df_metrics


def calculate_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Calcola matrice di correlazione dei rendimenti"""
    returns = calculate_returns(prices)
    return returns.corr()


def calculate_portfolio_metrics(prices: pd.DataFrame, weights: Dict[str, float]) -> Dict:
    """
    Calcola metriche a livello di portafoglio
    
    Args:
        prices: DataFrame con prezzi storici
        weights: Dizionario con pesi {ticker: peso}
    
    Returns:
        Dizionario con metriche del portafoglio
    """
    returns = calculate_returns(prices)

    empty_result = {
        'annual_return': 0,
        'annual_volatility': 0,
        'sharpe_ratio': 0,
        'max_drawdown': 0,
        'total_return': 0,
        'var_95': 0,
        'cvar_95': 0
    }

    # Normalizza i pesi
    total_weight = sum(weights.values())
    if total_weight == 0:
        return empty_result

    normalized_weights = {k: v/total_weight for k, v in weights.items()}

    # Filtra solo i ticker presenti nei dati
    valid_weights = {k: v for k, v in normalized_weights.items() if k in returns.columns}

    if not valid_weights:
        return empty_result

    # Crea serie di rendimenti del portafoglio
    portfolio_returns = pd.Series(0, index=returns.index)

    for ticker, weight in valid_weights.items():
        portfolio_returns += returns[ticker] * weight

    portfolio_returns_clean = portfolio_returns.dropna()

    # Volatilità
    volatility = portfolio_returns.std()
    annual_volatility = volatility * np.sqrt(252)

    # Max Drawdown del portafoglio
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    # Calcola total return solo se abbiamo dati
    total_return = cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0

    # Annualizzazione GEOMETRICA (CAGR), coerente con calculate_metrics e backtest.py
    years = len(portfolio_returns_clean) / 252
    if years > 0 and total_return > -0.99:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = 0

    sharpe = (annual_return - RISK_FREE_RATE) / annual_volatility if annual_volatility > 0 else 0

    # VaR e CVaR (Expected Shortfall) al 95%, giornalieri (NON annualizzati):
    # il VaR è la perdita "di soglia" nel 5% dei giorni peggiori, il CVaR è la
    # perdita media condizionata a essere oltre quella soglia (più informativo
    # sul rischio di coda, perché il VaR da solo ignora quanto si perde oltre la soglia)
    if len(portfolio_returns_clean) >= 10:
        var_95 = np.percentile(portfolio_returns_clean, 5)
        tail_losses = portfolio_returns_clean[portfolio_returns_clean <= var_95]
        cvar_95 = tail_losses.mean() if not tail_losses.empty else var_95
    else:
        var_95 = 0
        cvar_95 = 0

    return {
        'annual_return': annual_return,
        'annual_volatility': annual_volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'total_return': total_return,
        'var_95': var_95,
        'cvar_95': cvar_95
    }


def calculate_concentration(weights: Dict[str, float]) -> Dict[str, float]:
    """
    Misura quanto i pesi del portafoglio sono concentrati, tramite l'indice
    di Herfindahl-Hirschman (HHI = somma dei pesi al quadrato).

    HHI = 1/N per un portafoglio equipesato su N titoli, HHI = 1 se tutto il
    capitale è su un solo titolo. effective_n = 1/HHI è il "numero equivalente"
    di titoli equipesati che darebbe la stessa concentrazione: due portafogli
    con lo stesso N possono avere una concentrazione reale molto diversa a
    seconda di come sono distribuiti i pesi (utile perché la sola correlazione
    media non se ne accorge).
    """
    total_weight = sum(weights.values())
    if not weights or total_weight == 0:
        return {'hhi': 0, 'effective_n': 0, 'concentration_score': 0}

    normalized = np.array([w / total_weight for w in weights.values()])
    hhi = float(np.sum(normalized ** 2))
    effective_n = 1 / hhi if hhi > 0 else 0

    # Score 0-100: 100 = pesi perfettamente distribuiti, tende a 0 quando
    # il portafoglio si concentra su pochi titoli
    concentration_score = max(0, min(100, (1 - hhi) * 100))

    return {'hhi': hhi, 'effective_n': effective_n, 'concentration_score': concentration_score}


def get_diversification_score(correlation_matrix: pd.DataFrame, weights: Dict[str, float]) -> float:
    """
    Calcola un punteggio di diversificazione (0-100) combinando due aspetti
    indipendenti (pesi da DIVERSIFICATION_CONFIG):
    - correlazione media ponderata tra i titoli (bassa correlazione = meglio)
    - concentrazione dei pesi via HHI (pesi ben distribuiti = meglio)

    Una bassa correlazione media da sola può ingannare: un portafoglio con
    2 titoli scorrelati avrebbe lo stesso punteggio "di correlazione" di uno
    con 50, pur essendo molto più concentrato e quindi più rischioso.
    """
    if not weights:
        return 0

    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0

    normalized_weights = {k: v/total_weight for k, v in weights.items()}
    concentration_score = calculate_concentration(normalized_weights)['concentration_score']

    valid_tickers = [t for t in normalized_weights.keys() if t in correlation_matrix.index] \
        if not correlation_matrix.empty else []

    if len(valid_tickers) < 2:
        # Senza una matrice di correlazione utilizzabile, lo score si basa
        # solo sulla concentrazione dei pesi
        return concentration_score

    # Calcola correlazione media ponderata (escludendo diagonale)
    weighted_corr_sum = 0
    weight_sum = 0

    for i, ticker1 in enumerate(valid_tickers):
        for ticker2 in valid_tickers[i+1:]:
            corr = correlation_matrix.loc[ticker1, ticker2]
            w = normalized_weights[ticker1] * normalized_weights[ticker2]
            weighted_corr_sum += corr * w
            weight_sum += w

    avg_correlation = weighted_corr_sum / weight_sum if weight_sum > 0 else 0

    # Converti in score: correlazione bassa = diversificazione alta
    # Score 100 = correlazione 0 o negativa, Score 0 = correlazione 1
    correlation_score = max(0, min(100, (1 - avg_correlation) * 100))

    corr_w = DIVERSIFICATION_CONFIG['correlation_weight']
    conc_w = DIVERSIFICATION_CONFIG['concentration_weight']

    return correlation_score * corr_w + concentration_score * conc_w


def optimize_allocation_with_correlation(metrics: pd.DataFrame, 
                                        correlation_matrix: pd.DataFrame,
                                        target_risk: str = "moderate",
                                        max_correlation: float = 0.7) -> pd.DataFrame:
    """
    Ottimizza allocazione riducendo correlazioni alte
    
    Args:
        metrics: DataFrame con metriche dei ticker
        correlation_matrix: Matrice di correlazione
        target_risk: Profilo di rischio
        max_correlation: Soglia massima correlazione accettabile
    
    Returns:
        DataFrame con pesi ottimizzati considerando correlazioni
    """
    df = metrics.copy()
    df = df[df['sharpe_ratio'].notna()].copy()
    
    if df.empty:
        return df
    
    # Calcola score base (come prima)
    if target_risk == "conservative":
        df['base_score'] = (
            df['sharpe_ratio'].rank(pct=True) * 0.4 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.4 +
            df['annual_return'].rank(pct=True) * 0.2
        )
    elif target_risk == "aggressive":
        df['base_score'] = (
            df['annual_return'].rank(pct=True) * 0.6 +
            df['sharpe_ratio'].rank(pct=True) * 0.3 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.1
        )
    else:
        df['base_score'] = (
            df['annual_return'].rank(pct=True) * 0.35 +
            df['sharpe_ratio'].rank(pct=True) * 0.35 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.3
        )
    
    # Penalizza titoli con alta correlazione media
    avg_correlations = {}
    for ticker in df['ticker']:
        if ticker in correlation_matrix.index:
            # Correlazione media con altri titoli (escluso se stesso)
            corr_values = correlation_matrix[ticker].drop(ticker, errors='ignore')
            avg_corr = corr_values.mean()
            avg_correlations[ticker] = avg_corr
        else:
            avg_correlations[ticker] = 0
    
    df['avg_correlation'] = df['ticker'].map(avg_correlations)
    
    # Penalty per alta correlazione: più alta è la correlazione, più basso il peso.
    # La penalty parte da 0.3 di correlazione media e arriva al massimo (1.0)
    # in corrispondenza di max_correlation (soglia configurabile).
    penalty_span = max(max_correlation - 0.3, 0.01)
    df['correlation_penalty'] = df['avg_correlation'].apply(
        lambda x: min(1, max(0, (x - 0.3) / penalty_span)) if x > 0.3 else 0
    )

    # Penalty per sopravvalutazione: percentile 0-1 (0=economico, 1=caro
    # rispetto al proprio settore) calcolato in valuation.calculate_valuation_scores
    # e già unito a metrics a monte. Se assente (colonna non presente), nessuna
    # penalty (0.5 = neutro non penalizzerebbe comunque, ma qui usiamo 0 per
    # retrocompatibilità con chiamate che non passano dati di valutazione)
    from portfolio_config import VALUATION_CONFIG
    overvaluation = df['overvaluation_percentile'] if 'overvaluation_percentile' in df.columns else 0

    # Score finale = base_score ridotto dalle penalty (correlazione + sopravvalutazione)
    df['final_score'] = (
        df['base_score']
        * (1 - df['correlation_penalty'] * 0.5)
        * (1 - overvaluation * VALUATION_CONFIG['penalty_weight'])
    )

    # Normalizza per ottenere pesi
    df['suggested_weight'] = df['final_score'] / df['final_score'].sum()

    # Importa configurazione
    from portfolio_config import ALLOCATION_CONFIG

    # Limita peso massimo (con redistribuzione iterativa dell'eccesso)
    max_weight = ALLOCATION_CONFIG['max_weight_per_stock']
    capped = cap_weights(dict(zip(df['ticker'], df['suggested_weight'])), max_weight)
    df['suggested_weight'] = df['ticker'].map(capped)

    return df.sort_values('suggested_weight', ascending=False)


def suggest_optimal_allocation(metrics: pd.DataFrame, 
                              target_risk: str = "moderate") -> pd.DataFrame:
    """
    Suggerisce un'allocazione ottimale basata su risk/return
    
    Args:
        metrics: DataFrame con metriche dei ticker
        target_risk: 'conservative', 'moderate', 'aggressive'
    
    Returns:
        DataFrame con pesi suggeriti
    """
    df = metrics.copy()
    
    # Rimuovi ticker con dati insufficienti
    df = df[df['sharpe_ratio'].notna()].copy()
    
    if df.empty:
        return df
    
    # Strategia basata sul profilo di rischio
    if target_risk == "conservative":
        # Favorisci bassa volatilità e Sharpe alto
        df['score'] = (
            df['sharpe_ratio'].rank(pct=True) * 0.4 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.4 +
            df['annual_return'].rank(pct=True) * 0.2
        )
    elif target_risk == "aggressive":
        # Favorisci alto rendimento
        df['score'] = (
            df['annual_return'].rank(pct=True) * 0.6 +
            df['sharpe_ratio'].rank(pct=True) * 0.3 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.1
        )
    else:  # moderate
        # Bilanciato
        df['score'] = (
            df['annual_return'].rank(pct=True) * 0.35 +
            df['sharpe_ratio'].rank(pct=True) * 0.35 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.3
        )
    
    # Normalizza gli score per ottenere pesi
    df['suggested_weight'] = df['score'] / df['score'].sum()
    
    # Limita peso massimo per singolo titolo (max 15% per diversificazione)
    max_weight = 0.15
    df['suggested_weight'] = df['suggested_weight'].clip(upper=max_weight)
    
    # Rinormalizza
    df['suggested_weight'] = df['suggested_weight'] / df['suggested_weight'].sum()
    
    return df.sort_values('suggested_weight', ascending=False)
