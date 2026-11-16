"""
Modulo di ottimizzazione mean-variance (Markowitz) con shrinkage.

Sostituisce lo score euristico (rank percentile + penalty moltiplicative) con
un vero problema di ottimizzazione risolto numericamente (SLSQP), e riduce il
rischio di stima su covarianza/rendimenti attesi con shrinkage verso target
strutturati, invece di usare le stime campionarie grezze.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, Tuple


def shrink_covariance(cov_matrix: pd.DataFrame, shrinkage: float = 0.2) -> pd.DataFrame:
    """
    Shrinkage della matrice di covarianza verso il target "correlazione
    costante" (stessa correlazione media per tutte le coppie, varianze
    individuali invariate) — approccio di Ledoit & Wolf (2004). Qui usiamo
    un'intensità fissa (configurabile) invece di stimare analiticamente
    l'intensità ottimale del paper originale: una semplificazione dichiarata,
    non l'implementazione completa.

    Perché serve: la matrice di covarianza campionaria pura, stimata da
    poche centinaia di osservazioni giornaliere su decine di titoli, è
    notoriamente mal condizionata (rumorosa) — usata direttamente in un
    ottimizzatore produce pesi estremi e instabili che cambiano radicalmente
    con piccole variazioni nei dati. Lo shrinkage la rende più stabile.
    """
    tickers = cov_matrix.index
    values = cov_matrix.values
    std = np.sqrt(np.diag(values))
    std_safe = np.where(std > 0, std, 1e-12)
    corr = values / np.outer(std_safe, std_safe)

    n = len(tickers)
    if n < 2:
        return cov_matrix.copy()

    off_diag_sum = corr.sum() - np.trace(corr)
    avg_corr = off_diag_sum / (n * (n - 1))

    target_corr = np.full((n, n), avg_corr)
    np.fill_diagonal(target_corr, 1.0)
    target_cov = target_corr * np.outer(std, std)

    shrunk = shrinkage * target_cov + (1 - shrinkage) * values
    return pd.DataFrame(shrunk, index=tickers, columns=tickers)


def shrink_returns(expected_returns: pd.Series, shrinkage: float = 0.3) -> pd.Series:
    """
    Shrinkage (stile James-Stein / nello spirito di Black-Litterman, qui
    semplificato) dei rendimenti attesi verso la media cross-sectional
    dell'universo, invece di usare grezzo il rendimento storico trailing.

    Perché serve: il rendimento storico trailing è una stima molto rumorosa
    su finestre di 1-5 anni, e usarlo direttamente come "rendimento atteso"
    premia sistematicamente gli outlier del campione osservato (bias da
    momentum/hindsight). Restringere le stime verso la media riduce
    l'overconfidence nei singoli punteggi, un compromesso standard tra
    "fidati solo dei dati" e "ignora i dati".
    """
    grand_mean = expected_returns.mean()
    return expected_returns * (1 - shrinkage) + grand_mean * shrinkage


def mean_variance_optimize(expected_returns: pd.Series,
                           cov_matrix: pd.DataFrame,
                           risk_free_rate: float,
                           max_weight: float = 1.0,
                           objective: str = "max_sharpe",
                           min_weight_factor: float = 0.0) -> pd.Series:
    """
    Risolve il problema di ottimizzazione di Markowitz con un solver
    numerico vincolato (SLSQP), non un punteggio euristico:

    - "max_sharpe": massimizza (rendimento - risk free) / volatilità
      (tangency portfolio)
    - "min_variance": minimizza la varianza di portafoglio

    Vincoli: somma dei pesi = 1, peso massimo per titolo (rilassato
    automaticamente a 1/N se altrimenti irraggiungibile, stessa logica di
    risk_analysis.cap_weights), peso minimo per titolo pari a
    `min_weight_factor * (1/N)` (0 = nessun pavimento, comportamento
    originale).

    Senza un pavimento sul peso minimo, SLSQP converge tipicamente a
    soluzioni d'angolo: con un obiettivo max-Sharpe o min-varianza il
    solver non ha alcun incentivo a distribuire peso oltre il minimo che
    serve per centrare l'obiettivo, quindi porta a zero esatto una parte
    consistente (anche metà) dei titoli — pur essendo stati selezionati
    a monte apposta per beneficio di diversificazione. Il pavimento
    garantisce che ogni titolo scelto riceva un'allocazione effettiva.
    """
    tickers = list(expected_returns.index)
    n = len(tickers)

    if n == 0:
        return pd.Series(dtype=float)
    if n == 1:
        return pd.Series([1.0], index=tickers)

    mu = expected_returns.values
    cov = cov_matrix.loc[tickers, tickers].values

    effective_max_weight = max(max_weight, 1.0 / n)
    min_weight = min(min_weight_factor * (1.0 / n), effective_max_weight)

    def portfolio_return(w):
        return w @ mu

    def portfolio_vol(w):
        return np.sqrt(max(w @ cov @ w, 1e-16))

    if objective == "min_variance":
        def obj_fn(w):
            return w @ cov @ w
    else:
        def obj_fn(w):
            return -(portfolio_return(w) - risk_free_rate) / portfolio_vol(w)

    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(min_weight, effective_max_weight) for _ in range(n)]
    w0 = np.full(n, 1.0 / n)

    result = minimize(
        obj_fn, w0, method='SLSQP', bounds=bounds, constraints=constraints,
        options={'maxiter': 1000, 'ftol': 1e-12}
    )

    weights = np.clip(result.x, 0, None)
    total = weights.sum()
    weights = weights / total if total > 0 else w0

    return pd.Series(weights, index=tickers)


def optimize_portfolio(metrics: pd.DataFrame,
                      correlation_matrix: pd.DataFrame,
                      tickers: list,
                      risk_free_rate: float,
                      max_weight: float,
                      target_risk: str = "moderate",
                      cov_shrinkage: float = 0.2,
                      min_weight_factor: float = 0.0) -> Tuple[pd.Series, dict]:
    """
    Punto di ingresso comodo: costruisce rendimenti attesi e covarianza
    (con shrinkage) per i ticker dati, sceglie l'obiettivo in base al
    profilo di rischio, e risolve l'ottimizzazione vera.

    Mappatura profilo -> (obiettivo, shrinkage rendimenti):
    - conservative: minimizza la varianza, alto shrinkage sui rendimenti
      (poco peso alle stime storiche rumorose, focus sulla stabilità)
    - moderate: massimizza lo Sharpe, shrinkage medio
    - aggressive: massimizza lo Sharpe, basso shrinkage (più fiducia nel
      rendimento storico osservato)
    """
    profile_map = {
        "conservative": {"objective": "min_variance", "return_shrinkage": 0.5},
        "moderate": {"objective": "max_sharpe", "return_shrinkage": 0.3},
        "aggressive": {"objective": "max_sharpe", "return_shrinkage": 0.1},
    }
    profile = profile_map.get(target_risk, profile_map["moderate"])

    valid_tickers = [t for t in tickers if t in correlation_matrix.index]
    sub_metrics = metrics[metrics['ticker'].isin(valid_tickers)].set_index('ticker')
    raw_returns = sub_metrics.loc[valid_tickers, 'annual_return']

    vols = sub_metrics.loc[valid_tickers, 'annual_volatility']
    corr = correlation_matrix.loc[valid_tickers, valid_tickers]
    raw_cov = corr.mul(vols, axis=0).mul(vols, axis=1)

    shrunk_returns = shrink_returns(raw_returns, profile['return_shrinkage'])
    shrunk_cov = shrink_covariance(raw_cov, cov_shrinkage)

    weights = mean_variance_optimize(
        shrunk_returns, shrunk_cov, risk_free_rate, max_weight, profile['objective'],
        min_weight_factor
    )

    info = {
        'objective': profile['objective'],
        'return_shrinkage': profile['return_shrinkage'],
        'cov_shrinkage': cov_shrinkage,
        'raw_returns': raw_returns,
        'shrunk_returns': shrunk_returns,
    }

    return weights, info


def apply_sector_tilt(weights: Dict[str, float],
                      ticker_sector: Dict[str, str],
                      tilts: Dict[str, float]) -> Dict[str, float]:
    """
    Applica un aggiustamento manuale (tilt) ai pesi a livello di settore:
    sposta punti percentuali di peso da/verso i settori indicati in `tilts`
    (es. {"Banking & Financial Services": -0.15, "Mining & Materials": 0.05}).

    - Delta negativo (riduci un settore): riscala proporzionalmente i pesi
      già presenti, preservando le preferenze relative dell'ottimizzatore
      tra i titoli di quel settore.
    - Delta positivo (aumenta un settore): distribuisce il peso target IN
      MODO EQUO tra tutti i titoli del settore, invece di scalare
      proporzionalmente quello che c'è già. Motivo: l'ottimizzatore può
      assegnare peso ~0 a un titolo appena aggiunto per accogliere il tilt
      (se il suo profilo rischio/rendimento non lo rende attraente da solo);
      scalare un peso vicino a zero resta vicino a zero, concentrando di
      fatto tutto l'aumento su un unico titolo già forte e riscontrando
      subito il cap "max peso per titolo" — vanificando lo scopo di aver
      aggiunto più titoli al settore in main.py.

    Non è una vera ottimizzazione vincolata per settore (sarebbe più corretto
    imporre i vincoli direttamente nel solver): è un aggiustamento manuale
    esplicito, pensato per riflettere una preferenza personale dichiarata
    dall'investitore, applicato dopo l'ottimizzazione e prima di calcolare
    gli importi esatti.
    """
    weights = dict(weights)

    sector_tickers: Dict[str, list] = {}
    for t in weights:
        s = ticker_sector.get(t, "Altri")
        sector_tickers.setdefault(s, []).append(t)

    for sector, delta in tilts.items():
        tickers_in_sector = sector_tickers.get(sector, [])
        if not tickers_in_sector:
            continue

        current_sector_weight = sum(weights[t] for t in tickers_in_sector)
        target_sector_weight = max(0.0, current_sector_weight + delta)

        if delta < 0 and current_sector_weight > 0:
            scale = target_sector_weight / current_sector_weight
            for t in tickers_in_sector:
                weights[t] *= scale
        else:
            even_share = target_sector_weight / len(tickers_in_sector)
            for t in tickers_in_sector:
                weights[t] = even_share

    total = sum(weights.values())
    if total > 0:
        weights = {t: w / total for t, w in weights.items()}

    return weights
