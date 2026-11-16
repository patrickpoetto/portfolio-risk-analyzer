"""
Module for computing practical allocation based on real capital
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
    Ceiling on the number of stocks the available capital can support, given
    the configured minimum position size (ALLOCATION_CONFIG
    ['min_position_size']). This is not an arbitrary bracket choice: it is
    simply how many positions of at least that amount the capital can
    afford. The EFFECTIVE number of stocks combines this constraint with the
    statistical one computed by select_portfolio() / determine_
    diversification_optimal_n().

    Args:
        total_capital: Total capital to invest
        min_position_size: Minimum position size (defaults from config)

    Returns:
        Maximum number of stocks the capital can sustain
    """
    if min_position_size is None:
        min_position_size = ALLOCATION_CONFIG['min_position_size']

    if total_capital <= 0 or min_position_size <= 0:
        return 0

    return max(1, int(total_capital / min_position_size))


def build_covariance_matrix(metrics: pd.DataFrame, correlation_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstructs the covariance matrix (Cov_ij = corr_ij · vol_i · vol_j)
    from the annualized volatilities already computed in metrics and the
    correlation matrix. Needed to measure real portfolio risk (w'Σw), not
    just average correlation.
    """
    vols = metrics.set_index('ticker')['annual_volatility']
    tickers = [t for t in correlation_matrix.index if t in vols.index]
    corr = correlation_matrix.loc[tickers, tickers]
    vol = vols.loc[tickers]
    return corr.mul(vol, axis=0).mul(vol, axis=1)


def diversification_curve(ordered_tickers: List[str], cov_matrix: pd.DataFrame) -> List[Dict]:
    """
    Computes, for each increasing N (in the merit order given by
    select_smart_portfolio), the annualized volatility of an equal-weighted
    portfolio of the first N stocks using the REAL covariance matrix.

    Theoretical basis: Evans & Archer (1968) and Elton & Gruber (1977) on
    "naive diversification" show that the specific risk of an
    equal-weighted portfolio falls rapidly as low-correlation stocks are
    added, converging toward the residual systematic risk with diminishing
    marginal benefits. Here we measure this curve on the portfolio's real
    data instead of assuming a closed form (which would require uniform
    variance and correlation across all stocks, a simplifying assumption
    our data does not meet).
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
    Finds the minimum number of stocks beyond which portfolio risk
    (equal-weighted variance, measured on real data) stops falling in a
    stable way. No theoretical percentage threshold: we directly look for
    the point where the curve settles near its absolute minimum.

    We use a window of consecutive stocks within `stability_tolerance` of
    the minimum (not the first single low point) so as not to mistake an
    isolated/noisy dip in the curve for true convergence: if no window that
    wide is found, it is gradually narrowed down to a single point,
    guaranteeing an answer regardless.

    The result never falls below `min_n` (a practical floor from config).
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
    Determines HOW MANY stocks to hold and WHICH ones, combining two
    independent constraints (no hardcoded number of stocks per bracket):

    1. Statistical: the point where the real diversification curve
       (`diversification_curve`) shows marginal benefits that are now
       negligible for further reducing portfolio risk.
    2. Capital: how many positions of at least `min_position_size` the
       available capital can actually sustain.

    The more restrictive of the two constraints wins.

    Returns:
        (list of selected tickers in merit order, dict with the
        computation details for transparency/summary in the report)
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

    # The "how many" and the "which ones" must be measured with two
    # different orderings, to avoid circularity: if we measured the
    # diversification benefit on the order ALREADY optimized for low
    # correlation, the curve would converge artificially fast (the first
    # stocks would already have been chosen specifically to be
    # uncorrelated with each other). So we use the "naive" descending-Sharpe
    # order to measure how many stocks are needed (faithful to the Evans &
    # Archer 1968 method on naive diversification), and the smart algorithm
    # (performance + correlation + sector) only to choose which stocks to
    # keep among those N.
    sharpe_order = valid_metrics.sort_values('sharpe_ratio', ascending=False)['ticker'].tolist()

    cov_matrix = build_covariance_matrix(metrics, correlation_matrix)
    curve = diversification_curve(sharpe_order, cov_matrix)

    statistically_optimal_n = determine_diversification_optimal_n(curve)
    capital_affordable_n = determine_optimal_portfolio_size(total_capital, min_position_size)

    n_stocks = max(1, min(statistically_optimal_n, capital_affordable_n, len(sharpe_order)))
    binding_constraint = 'capital' if capital_affordable_n < statistically_optimal_n else 'diversification'

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
    Selects the N best stocks balancing performance and diversification

    Strategy:
    1. Sort by Sharpe Ratio
    2. Select the top performer
    3. For each subsequent pick, consider:
       - High Sharpe
       - Low correlation with already-selected stocks
       - Sector diversity

    Returns:
        List of selected tickers
    """
    if metrics.empty or n_stocks <= 0:
        return []

    # Filter valid stocks
    valid_metrics = metrics[metrics['sharpe_ratio'].notna()].copy()
    n_stocks = min(n_stocks, len(valid_metrics))
    if 'overvaluation_percentile' not in valid_metrics.columns:
        valid_metrics['overvaluation_percentile'] = 0.5

    selected = []
    selected_sectors = []

    # 1. Start from the best Sharpe score adjusted for overvaluation: an
    # excellent Sharpe but very expensive relative to the sector should not
    # automatically win first place
    valuation_penalty_weight = VALUATION_CONFIG['penalty_weight']
    valid_metrics['_seed_score'] = valid_metrics['sharpe_ratio'] * (
        1 - valid_metrics['overvaluation_percentile'] * valuation_penalty_weight
    )
    best_sharpe = valid_metrics.nlargest(1, '_seed_score')['ticker'].iloc[0]
    selected.append(best_sharpe)
    selected_sectors.append(get_sector(best_sharpe))

    # 2. Build the portfolio iteratively
    remaining = valid_metrics[~valid_metrics['ticker'].isin(selected)].copy()

    while len(selected) < n_stocks and not remaining.empty:
        # Compute a score for each candidate
        scores = []

        for _, row in remaining.iterrows():
            ticker = row['ticker']

            # Component 1: Performance (normalized Sharpe)
            sharpe_score = row['sharpe_ratio'] / valid_metrics['sharpe_ratio'].max()
            sharpe_score = max(0, min(1, sharpe_score))  # Clip 0-1

            # Component 2: Diversification (average correlation with selected)
            if ticker in correlation_matrix.index:
                correlations = [abs(correlation_matrix.loc[ticker, s])
                               for s in selected
                               if s in correlation_matrix.columns]
                avg_corr = np.mean(correlations) if correlations else 0.5
                diversification_score = 1 - avg_corr  # Lower correlation = better
            else:
                diversification_score = 0.5

            # Component 3: Different sector (bonus for a new sector)
            ticker_sector = get_sector(ticker)
            sector_bonus = 0.2 if ticker_sector not in selected_sectors else 0

            # Final score (adaptive weights per risk profile, from config)
            profile = RISK_PROFILES.get(target_risk, RISK_PROFILES['moderate'])
            sharpe_w = profile['sharpe_weight']
            corr_w = profile['correlation_weight']
            sector_w = profile['sector_weight']

            final_score = (sharpe_score * sharpe_w +
                         diversification_score * corr_w +
                         sector_bonus * sector_w)

            # Penalize stocks that are expensive relative to their own
            # sector (0-1 percentile already computed in valuation.py and
            # merged into metrics)
            overvaluation = row.get('overvaluation_percentile', 0.5)
            final_score *= (1 - overvaluation * valuation_penalty_weight)

            scores.append({'ticker': ticker, 'score': final_score,
                          'sector': ticker_sector})

        # Pick the best one
        scores_df = pd.DataFrame(scores)
        best = scores_df.nlargest(1, 'score').iloc[0]

        selected.append(best['ticker'])
        selected_sectors.append(best['sector'])

        remaining = remaining[remaining['ticker'] != best['ticker']]

    return selected


def get_sector(ticker: str) -> str:
    """Finds a ticker's sector"""
    for sector, tickers in SECTOR_CLASSIFICATION.items():
        if ticker in tickers:
            return sector
    return "Other"


def calculate_practical_allocation(total_capital: float,
                                   metrics: pd.DataFrame,
                                   correlation_matrix: pd.DataFrame,
                                   suggested_weights: Dict[str, float],
                                   cash_allocation: float = 0.0,
                                   target_risk: str = "moderate",
                                   min_position_size: float = None,
                                   selected_tickers: List[str] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Computes a practical allocation with exact amounts

    Args:
        total_capital: Total available capital
        metrics: DataFrame with stock metrics
        correlation_matrix: Correlation matrix
        suggested_weights: Original optimal weights
        cash_allocation: % to keep in cash
        target_risk: Risk profile
        min_position_size: Minimum investment per stock (defaults from config)
        selected_tickers: If given, reuses this selection (the same stocks
            already analyzed in the rest of the report) instead of
            recomputing a new one with a potentially different number of
            stocks

    Returns:
        DataFrame with the practical allocation, Dict with additional info
    """

    if min_position_size is None:
        min_position_size = ALLOCATION_CONFIG['min_position_size']

    # Capital to invest (after cash)
    investable_capital = total_capital * (1 - cash_allocation)
    cash_amount = total_capital * cash_allocation

    if selected_tickers is not None:
        # Reuse the selection already made upstream, to guarantee that the
        # practical allocation is based on the same stocks analyzed in the
        # rest of the report
        n_stocks = len(selected_tickers)
    else:
        # Fallback for standalone use: same combined criterion (statistical
        # + capital) as select_portfolio(), not just the capital constraint
        selected_tickers, _selection_info = select_portfolio(
            metrics, correlation_matrix, investable_capital, target_risk, min_position_size
        )
        n_stocks = len(selected_tickers)

    print(f"\n💰 PRACTICAL ALLOCATION")
    print("="*80)
    print(f"Total capital:       €{total_capital:,.2f}")
    print(f"Cash ({cash_allocation:.1%}):          €{cash_amount:,.2f}")
    print(f"To invest:            €{investable_capital:,.2f}")
    print(f"Optimal # of stocks:  {n_stocks}")
    if n_stocks > 0:
        print(f"Average investment:   €{investable_capital/n_stocks:,.2f} per stock")

    if n_stocks <= 0:
        print("⚠️  Insufficient capital to build a minimum position")
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
        print("⚠️  No selectable stocks with the available data")
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

    print(f"\n✅ Selected stocks: {', '.join(selected_tickers[:10])}" +
          (f" +{len(selected_tickers)-10} more" if len(selected_tickers) > 10 else ""))

    # Extract weights for selected stocks
    selected_weights = {t: suggested_weights.get(t, 0) for t in selected_tickers}
    total_selected_weight = sum(selected_weights.values())

    # Renormalize weights
    if total_selected_weight > 0:
        normalized_weights = {t: w/total_selected_weight
                             for t, w in selected_weights.items()}
    else:
        # Fallback: equal weights
        normalized_weights = {t: 1/len(selected_tickers)
                             for t in selected_tickers}

    # Reapply the cap on the maximum weight per stock (with iterative
    # redistribution of the excess): the configured cap is designed for the
    # full universe, so on a narrow selection cap_weights automatically
    # raises it to the equal-weight share whenever it would otherwise be
    # unreachable
    normalized_weights = cap_weights(normalized_weights, ALLOCATION_CONFIG['max_weight_per_stock'])

    # Compute exact amounts
    allocations = []
    for ticker in selected_tickers:
        weight = normalized_weights[ticker]
        amount = investable_capital * weight

        # Find ticker info
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
            'sector': get_sector(ticker),
            'weight_pct': weight * 100,
            'amount_eur': amount,
            'sharpe_ratio': sharpe,
            'annual_return': annual_return,
            'volatility': volatility
        })

    df_allocation = pd.DataFrame(allocations)
    df_allocation = df_allocation.sort_values('amount_eur', ascending=False)

    # Compute allocation statistics
    total_allocated = df_allocation['amount_eur'].sum()

    # Average correlation of the selection
    if len(selected_tickers) > 1:
        selected_corr_matrix = correlation_matrix.loc[
            [t for t in selected_tickers if t in correlation_matrix.index],
            [t for t in selected_tickers if t in correlation_matrix.columns]
        ]

        # Average correlation (excluding the diagonal)
        mask = np.triu(np.ones_like(selected_corr_matrix, dtype=bool), k=1)
        avg_correlation = selected_corr_matrix.where(mask).stack().mean()
    else:
        avg_correlation = 0
        selected_corr_matrix = pd.DataFrame()

    # Sector diversification
    sector_dist = df_allocation.groupby('sector')['weight_pct'].sum().to_dict()

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

    # Print summary
    print(f"\n📊 SELECTION STATISTICS")
    print("="*80)
    print(f"Average correlation: {avg_correlation:.2%}")
    print(f"Distinct sectors:    {len(sector_dist)}")
    print(f"\nSector distribution:")
    for sector, pct in sorted(sector_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector:.<30} {pct:>5.1f}%")

    return df_allocation, info
