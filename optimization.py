"""
Mean-variance (Markowitz) optimization module with shrinkage.

Replaces the heuristic score (percentile rank + multiplicative penalties)
with a real optimization problem solved numerically (SLSQP), and reduces
estimation risk on covariance/expected returns with shrinkage toward
structured targets, instead of using raw sample estimates.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, Tuple


def shrink_covariance(cov_matrix: pd.DataFrame, shrinkage: float = 0.2) -> pd.DataFrame:
    """
    Shrinks the covariance matrix toward the "constant correlation" target
    (same average correlation for every pair, individual variances
    unchanged) — the Ledoit & Wolf (2004) approach. Here we use a fixed
    (configurable) intensity instead of analytically estimating the optimal
    intensity from the original paper: a declared simplification, not the
    full implementation.

    Why it's needed: the pure sample covariance matrix, estimated from a few
    hundred daily observations across dozens of stocks, is notoriously
    ill-conditioned (noisy) — used directly in an optimizer it produces
    extreme, unstable weights that change drastically with small changes in
    the data. Shrinkage makes it more stable.
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
    Shrinkage (James-Stein style / in the spirit of Black-Litterman, here
    simplified) of expected returns toward the cross-sectional mean of the
    universe, instead of using the raw trailing historical return.

    Why it's needed: the trailing historical return is a very noisy
    estimate over 1-5 year windows, and using it directly as "expected
    return" systematically rewards outliers in the observed sample
    (momentum/hindsight bias). Shrinking the estimates toward the mean
    reduces overconfidence in individual scores, a standard trade-off
    between "trust only the data" and "ignore the data".
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
    Solves the Markowitz optimization problem with a constrained numerical
    solver (SLSQP), not a heuristic score:

    - "max_sharpe": maximizes (return - risk free) / volatility
      (tangency portfolio)
    - "min_variance": minimizes portfolio variance

    Constraints: sum of weights = 1, maximum weight per stock (automatically
    relaxed to 1/N if otherwise unreachable, same logic as
    risk_analysis.cap_weights), minimum weight per stock equal to
    `min_weight_factor * (1/N)` (0 = no floor, original behavior).

    Without a floor on the minimum weight, SLSQP typically converges to
    corner solutions: with a max-Sharpe or min-variance objective the solver
    has no incentive to spread weight beyond the minimum needed to hit the
    objective, so it drives a substantial share (even half) of the stocks
    to exactly zero — even though they were selected upstream specifically
    for diversification benefit. The floor ensures every chosen stock
    receives an effective allocation.
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
    Convenience entry point: builds expected returns and covariance (with
    shrinkage) for the given tickers, picks the objective based on the risk
    profile, and solves the actual optimization.

    Profile -> (objective, return shrinkage) mapping:
    - conservative: minimizes variance, high shrinkage on returns (little
      weight on noisy historical estimates, focus on stability)
    - moderate: maximizes Sharpe, medium shrinkage
    - aggressive: maximizes Sharpe, low shrinkage (more trust in the
      observed historical return)
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
    Applies a manual adjustment (tilt) to weights at the sector level: shifts
    percentage points of weight to/from the sectors specified in `tilts`
    (e.g. {"Banking & Financial Services": -0.15, "Mining & Materials": 0.05}).

    - Negative delta (reduce a sector): proportionally rescales the
      weights already present, preserving the optimizer's relative
      preferences among the stocks in that sector.
    - Positive delta (increase a sector): distributes the target weight
      EVENLY across all stocks in the sector, instead of proportionally
      scaling what is already there. Reason: the optimizer may assign ~0
      weight to a stock just added to accommodate the tilt (if its
      risk/return profile doesn't make it attractive on its own); scaling a
      weight near zero stays near zero, effectively concentrating the
      entire increase on a single already-strong stock and immediately
      hitting the "max weight per stock" cap — defeating the purpose of
      having added more stocks to the sector in main.py.

    This is not a true sector-constrained optimization (it would be more
    correct to impose the constraints directly in the solver): it is an
    explicit manual adjustment, meant to reflect a personal preference
    stated by the investor, applied after optimization and before
    computing the exact amounts.
    """
    weights = dict(weights)

    sector_tickers: Dict[str, list] = {}
    for t in weights:
        s = ticker_sector.get(t, "Other")
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
