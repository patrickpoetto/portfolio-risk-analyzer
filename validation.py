"""
Modulo di validazione statistica: backtest walk-forward multi-fold,
intervalli di confidenza bootstrap, confronto con benchmark.

Un singolo split in-sample/out-of-sample (introdotto in una fase precedente
del progetto) è già un passo avanti rispetto a nessuno split, ma resta un
solo campione: potrebbe essere per caso favorevole o sfavorevole. Qui si
ripete la validazione su più finestre consecutive (walk-forward) e si
quantifica l'incertezza statistica della performance osservata (bootstrap),
invece di riportare un singolo numero come se fosse certo.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from risk_analysis import calculate_metrics, calculate_correlation_matrix, calculate_returns
from optimization import optimize_portfolio, mean_variance_optimize


def _portfolio_daily_returns(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    aligned = returns[weights.index]
    return (aligned * weights.values).sum(axis=1)


def walk_forward_backtest(prices: pd.DataFrame,
                         risk_free_rate: float,
                         max_weight: float,
                         target_risk: str,
                         n_folds: int = 4,
                         test_window_days: int = 63,
                         min_train_days: int = 252,
                         cost_bps: float = 10.0) -> Dict:
    """
    Backtest walk-forward multi-fold: la finestra di test scorre in avanti
    nel tempo, ciascuna preceduta da una finestra di training espandibile
    (expanding window, dall'inizio dei dati fino all'inizio del test). I pesi
    (portafoglio ottimizzato + benchmark equal-weight e minimum-variance
    "naive" senza shrinkage) sono stimati SOLO su dati di training e poi
    applicati, fissi, al periodo di test immediatamente successivo — mai
    visto durante la stima, nessun look-ahead.

    Un costo di transazione (`cost_bps` punti base sul turnover) viene
    applicato ad ogni ribilanciamento tra un fold e il successivo.

    Nota di onestà metodologica: qui si re-ottimizzano i PESI ad ogni fold,
    ma l'universo di titoli candidati resta fisso (non si ri-fa lo screening/
    selezione titoli ad ogni fold). Un walk-forward completo rifarebbe anche
    la selezione dei titoli ad ogni finestra; qui è stato scelto un
    compromesso pragmatico per i tempi di calcolo.
    """
    total_days = len(prices)
    strategy_names = ['Ottimizzato', 'Equal-Weight', 'Min-Varianza (naive)']
    fold_returns = {name: [] for name in strategy_names}
    fold_details = []
    prev_weights = {name: None for name in strategy_names}

    usable_days = total_days - min_train_days
    if usable_days < test_window_days:
        return {'returns': {name: pd.Series(dtype=float) for name in strategy_names}, 'folds': []}

    max_folds = max(1, usable_days // test_window_days)
    n_folds = min(n_folds, max_folds)

    test_start_indices = []
    end = total_days
    for _ in range(n_folds):
        start = end - test_window_days
        if start < min_train_days:
            break
        test_start_indices.append(start)
        end = start
    test_start_indices = list(reversed(test_start_indices))

    for fold_idx, test_start in enumerate(test_start_indices):
        test_end = min(test_start + test_window_days, total_days)
        train_prices = prices.iloc[:test_start]
        test_prices = prices.iloc[test_start:test_end]

        if len(train_prices) < min_train_days or len(test_prices) < 5:
            continue

        weights_uniform = {t: 1.0 / len(train_prices.columns) for t in train_prices.columns}
        train_metrics = calculate_metrics(train_prices, weights_uniform)
        train_metrics = train_metrics[train_metrics['sharpe_ratio'].notna()].copy()
        if train_metrics.empty:
            continue

        valid_tickers = train_metrics['ticker'].tolist()
        train_corr = calculate_correlation_matrix(train_prices[valid_tickers])

        # Strategia principale: shrinkage + vera ottimizzazione
        opt_weights, _ = optimize_portfolio(
            train_metrics, train_corr, valid_tickers, risk_free_rate, max_weight, target_risk
        )

        # Benchmark 1: equal-weight (diversificazione naive, nessuna stima)
        eq_weights = pd.Series(1.0 / len(valid_tickers), index=valid_tickers)

        # Benchmark 2: minimum-variance sulla covarianza CAMPIONARIA grezza
        # (senza shrinkage), per isolare quanto contribuisce lo shrinkage
        vols = train_metrics.set_index('ticker').loc[valid_tickers, 'annual_volatility']
        naive_cov = train_corr.mul(vols, axis=0).mul(vols, axis=1)
        minvar_weights = mean_variance_optimize(
            train_metrics.set_index('ticker').loc[valid_tickers, 'annual_return'],
            naive_cov, risk_free_rate, max_weight, objective="min_variance"
        )

        strategy_weights = {
            'Ottimizzato': opt_weights,
            'Equal-Weight': eq_weights,
            'Min-Varianza (naive)': minvar_weights,
        }

        test_returns = calculate_returns(test_prices[valid_tickers]).fillna(0)

        for name, w in strategy_weights.items():
            port_ret = _portfolio_daily_returns(test_returns, w)

            if prev_weights[name] is not None:
                all_idx = w.index.union(prev_weights[name].index)
                turnover = (w.reindex(all_idx, fill_value=0) -
                          prev_weights[name].reindex(all_idx, fill_value=0)).abs().sum()
            else:
                turnover = 1.0  # costruzione iniziale del portafoglio da zero

            cost = turnover * (cost_bps / 10000.0)
            if len(port_ret) > 0:
                port_ret = port_ret.copy()
                port_ret.iloc[0] = port_ret.iloc[0] - cost

            fold_returns[name].append(port_ret)
            prev_weights[name] = w

        fold_details.append({
            'fold': fold_idx + 1,
            'test_start': test_prices.index[0],
            'test_end': test_prices.index[-1],
            'n_train_days': len(train_prices),
            'n_test_days': len(test_prices),
        })

    aggregated = {
        name: (pd.concat(series_list) if series_list else pd.Series(dtype=float))
        for name, series_list in fold_returns.items()
    }

    return {'returns': aggregated, 'folds': fold_details}


def bootstrap_sharpe_ci(daily_returns: pd.Series,
                       risk_free_rate: float,
                       n_bootstrap: int = 1000,
                       ci: float = 0.90,
                       block_size: int = None,
                       seed: int = 42) -> Tuple[float, float, float]:
    """
    Intervallo di confidenza bootstrap A BLOCCHI (non i.i.d., per rispettare
    l'autocorrelazione seriale tipica dei rendimenti finanziari) sullo Sharpe
    Ratio realizzato. Una singola stima puntuale non dice se la performance
    osservata sia statisticamente distinguibile dal rumore campionario.

    Returns:
        (sharpe puntuale, limite inferiore CI, limite superiore CI)
    """
    returns = daily_returns.dropna().values
    n = len(returns)
    if n < 20:
        return 0.0, 0.0, 0.0

    if block_size is None:
        block_size = max(5, n // 20)
    block_size = min(block_size, n)

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    sharpes = np.empty(n_bootstrap)

    for b in range(n_bootstrap):
        starts = rng.integers(0, n - block_size + 1, size=n_blocks)
        sample = np.concatenate([returns[s:s + block_size] for s in starts])[:n]
        mean = sample.mean() * 252
        vol = sample.std() * np.sqrt(252)
        sharpes[b] = (mean - risk_free_rate) / vol if vol > 0 else 0.0

    point_mean = returns.mean() * 252
    point_vol = returns.std() * np.sqrt(252)
    point_sharpe = (point_mean - risk_free_rate) / point_vol if point_vol > 0 else 0.0

    lower = float(np.percentile(sharpes, (1 - ci) / 2 * 100))
    upper = float(np.percentile(sharpes, (1 + ci) / 2 * 100))

    return float(point_sharpe), lower, upper


def summarize_strategy_returns(daily_returns: pd.Series, risk_free_rate: float) -> Dict:
    """Statistiche aggregate (rendimento, volatilità, Sharpe+CI, drawdown) su una serie di rendimenti giornalieri."""
    returns = daily_returns.dropna()
    if len(returns) < 5:
        return {}

    total_return = float((1 + returns).prod() - 1)
    years = len(returns) / 252
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -0.99 else 0.0
    annual_vol = float(returns.std() * np.sqrt(252))

    sharpe, ci_low, ci_high = bootstrap_sharpe_ci(returns, risk_free_rate)

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = float(drawdown.min())

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe,
        'sharpe_ci_low': ci_low,
        'sharpe_ci_high': ci_high,
        'max_drawdown': max_drawdown,
        'n_days': len(returns),
    }
