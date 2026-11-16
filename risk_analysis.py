"""
Module for portfolio risk and return analysis
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
    Applies a cap to the maximum weight per ticker and redistributes the
    excess across the other weights, iterating until the cap is respected
    by all of them.

    A simple "clip then renormalize in one pass" is not enough: dividing by
    the sum after clipping pushes the already-capped values back above the
    threshold. If the cap is mathematically unreachable (too few tickers for
    the configured cap), the effective cap becomes the equal-weight share (1/n).
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
    Downloads historical data for the given tickers

    Args:
        tickers: List of ticker symbols
        period: Period (1y, 2y, 5y, max)

    Returns:
        DataFrame with adjusted closing prices
    """
    print(f"📊 Downloading historical data for {len(tickers)} tickers...")

    data = {}
    failed = []

    for ticker in tickers:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=period)

            if not hist.empty and len(hist) > 20:  # Minimum 20 days of data
                close = hist['Close']
                # yfinance returns the index in the timezone of the listing
                # exchange (e.g. America/New_York for AAPL, Europe/London
                # for RR.L, Europe/Zurich for HOLN.SW...). Left as-is,
                # combining tickers from different exchanges into a single
                # DataFrame does not align the same trading days: "2026-06-29
                # New York" and "2026-06-29 London" are different UTC
                # instants, so they end up as separate rows. The result is
                # an index inflated with near-duplicate rows, which the
                # subsequent forward-fill fills with artificial near-zero
                # daily returns, distorting any downstream annualized
                # volatility/return metric. We normalize all indices to
                # plain dates (timezone stripped) so they line up.
                close.index = close.index.tz_localize(None).normalize()
                data[ticker] = close
            else:
                failed.append(ticker)
                print(f"  ⚠️  {ticker}: insufficient data")

        except Exception as e:
            failed.append(ticker)
            print(f"  ❌ {ticker}: error - {str(e)[:50]}")

    if not data:
        raise ValueError("No data available for the given tickers")

    df = pd.DataFrame(data)

    # Drop fully empty rows (when no market is open)
    df = df.dropna(how='all')

    # Forward fill to handle different market hours
    # This fills NaNs with the last valid price
    df = df.ffill()

    # Drop any remaining NaNs at the start (first observation)
    df = df.dropna()

    print(f"✅ Data downloaded: {len(data)} tickers, {len(failed)} failed\n")

    return df


def split_in_sample_out_of_sample(prices: pd.DataFrame,
                                  oos_ratio: float,
                                  min_oos_days: int,
                                  max_oos_days: int) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    Splits the historical series into an "in-sample" window (used for
    scouting, smart stock selection and weight optimization) and a final
    "out-of-sample" window, never seen by any of these stages.

    Without this split, the backtest would evaluate the selection on the
    same data used to choose it (stocks are chosen because they have the
    best historical Sharpe precisely in that window): a circular and
    systematically over-optimistic result, not an honest test.

    If the available history is too short for a sensible split, it returns
    all data as in-sample with no holdout (oos_days=0): in that case the
    backtest stays entirely in-sample and should be interpreted with
    caution (this is flagged explicitly in the report).
    """
    total_days = len(prices)
    oos_days = int(total_days * oos_ratio)
    oos_days = max(min_oos_days, min(max_oos_days, oos_days))

    # There still needs to be enough room to compute meaningful metrics on
    # the in-sample part (at least double the holdout window)
    if oos_days <= 0 or total_days - oos_days < max(min_oos_days * 2, 60):
        return prices, prices.iloc[0:0], 0

    in_sample = prices.iloc[:-oos_days]
    out_of_sample = prices.iloc[-oos_days:]
    return in_sample, out_of_sample, oos_days


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Computes daily percentage returns"""
    return prices.pct_change()


def calculate_metrics(prices: pd.DataFrame, weights: Dict[str, float] = None) -> pd.DataFrame:
    """
    Computes risk/return metrics for each ticker

    Args:
        prices: DataFrame with historical prices
        weights: Optional dict with portfolio weights

    Returns:
        DataFrame with computed metrics
    """
    returns = calculate_returns(prices)

    metrics = []

    for ticker in prices.columns:
        if ticker not in returns.columns:
            continue

        ret = returns[ticker].dropna()

        # Requires at least 10 days of valid data
        if len(ret) < 10:
            continue

        # Base calculations
        volatility = ret.std()
        annual_volatility = volatility * np.sqrt(252)  # sqrt(T) scaling, valid in both an arithmetic and geometric sense

        # Total return over the period
        total_return = (prices[ticker].iloc[-1] / prices[ticker].iloc[0] - 1)

        # GEOMETRIC annualization (CAGR), consistent with the one used in
        # backtest.py: compounded correctly over time, unlike a simple daily
        # arithmetic mean * 252 (which overstates the real return on
        # volatile stocks due to Jensen's inequality)
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

        # VaR (Value at Risk) at 95%, daily (NOT annualized)
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

    # Add ranks for different metrics (only if we have data)
    if not df_metrics.empty and len(df_metrics) > 0:
        df_metrics['return_rank'] = df_metrics['annual_return'].rank(ascending=False)
        df_metrics['sharpe_rank'] = df_metrics['sharpe_ratio'].rank(ascending=False)
        df_metrics['risk_rank'] = df_metrics['annual_volatility'].rank(ascending=True)  # Lower is better

    return df_metrics


def calculate_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Computes the correlation matrix of returns"""
    returns = calculate_returns(prices)
    return returns.corr()


def calculate_portfolio_metrics(prices: pd.DataFrame, weights: Dict[str, float]) -> Dict:
    """
    Computes portfolio-level metrics

    Args:
        prices: DataFrame with historical prices
        weights: Dict with weights {ticker: weight}

    Returns:
        Dict with portfolio metrics
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

    # Normalize weights
    total_weight = sum(weights.values())
    if total_weight == 0:
        return empty_result

    normalized_weights = {k: v/total_weight for k, v in weights.items()}

    # Keep only tickers present in the data
    valid_weights = {k: v for k, v in normalized_weights.items() if k in returns.columns}

    if not valid_weights:
        return empty_result

    # Build the portfolio return series
    portfolio_returns = pd.Series(0, index=returns.index)

    for ticker, weight in valid_weights.items():
        portfolio_returns += returns[ticker] * weight

    portfolio_returns_clean = portfolio_returns.dropna()

    # Volatility
    volatility = portfolio_returns.std()
    annual_volatility = volatility * np.sqrt(252)

    # Portfolio Max Drawdown
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    # Compute total return only if we have data
    total_return = cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0

    # GEOMETRIC annualization (CAGR), consistent with calculate_metrics and backtest.py
    years = len(portfolio_returns_clean) / 252
    if years > 0 and total_return > -0.99:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = 0

    sharpe = (annual_return - RISK_FREE_RATE) / annual_volatility if annual_volatility > 0 else 0

    # VaR and CVaR (Expected Shortfall) at 95%, daily (NOT annualized): the
    # VaR is the "threshold" loss on the worst 5% of days, the CVaR is the
    # average loss conditional on being beyond that threshold (more
    # informative about tail risk, since the VaR alone ignores how much is
    # lost beyond the threshold)
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
    Measures how concentrated the portfolio weights are, via the
    Herfindahl-Hirschman Index (HHI = sum of squared weights).

    HHI = 1/N for a portfolio equal-weighted over N stocks, HHI = 1 if all
    capital is in a single stock. effective_n = 1/HHI is the "equivalent
    number" of equal-weighted stocks that would give the same
    concentration: two portfolios with the same N can have very different
    real concentration depending on how the weights are distributed (useful
    because average correlation alone doesn't catch this).
    """
    total_weight = sum(weights.values())
    if not weights or total_weight == 0:
        return {'hhi': 0, 'effective_n': 0, 'concentration_score': 0}

    normalized = np.array([w / total_weight for w in weights.values()])
    hhi = float(np.sum(normalized ** 2))
    effective_n = 1 / hhi if hhi > 0 else 0

    # Score 0-100: 100 = perfectly distributed weights, tends to 0 as the
    # portfolio concentrates into a few stocks
    concentration_score = max(0, min(100, (1 - hhi) * 100))

    return {'hhi': hhi, 'effective_n': effective_n, 'concentration_score': concentration_score}


def get_diversification_score(correlation_matrix: pd.DataFrame, weights: Dict[str, float]) -> float:
    """
    Computes a diversification score (0-100) combining two independent
    aspects (weighted per DIVERSIFICATION_CONFIG):
    - weighted average correlation between stocks (lower correlation = better)
    - weight concentration via HHI (well-distributed weights = better)

    A low average correlation alone can be misleading: a portfolio with 2
    uncorrelated stocks would get the same "correlation score" as one with
    50, despite being far more concentrated and therefore riskier.
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
        # Without a usable correlation matrix, the score is based only on
        # weight concentration
        return concentration_score

    # Compute the weighted average correlation (excluding the diagonal)
    weighted_corr_sum = 0
    weight_sum = 0

    for i, ticker1 in enumerate(valid_tickers):
        for ticker2 in valid_tickers[i+1:]:
            corr = correlation_matrix.loc[ticker1, ticker2]
            w = normalized_weights[ticker1] * normalized_weights[ticker2]
            weighted_corr_sum += corr * w
            weight_sum += w

    avg_correlation = weighted_corr_sum / weight_sum if weight_sum > 0 else 0

    # Convert to a score: low correlation = high diversification
    # Score 100 = correlation 0 or negative, Score 0 = correlation 1
    correlation_score = max(0, min(100, (1 - avg_correlation) * 100))

    corr_w = DIVERSIFICATION_CONFIG['correlation_weight']
    conc_w = DIVERSIFICATION_CONFIG['concentration_weight']

    return correlation_score * corr_w + concentration_score * conc_w


def suggest_optimal_allocation(metrics: pd.DataFrame,
                              target_risk: str = "moderate") -> pd.DataFrame:
    """
    Suggests an optimal allocation based on risk/return

    Args:
        metrics: DataFrame with stock metrics
        target_risk: 'conservative', 'moderate', 'aggressive'

    Returns:
        DataFrame with suggested weights
    """
    df = metrics.copy()

    # Remove tickers with insufficient data
    df = df[df['sharpe_ratio'].notna()].copy()

    if df.empty:
        return df

    # Strategy based on risk profile
    if target_risk == "conservative":
        # Favor low volatility and high Sharpe
        df['score'] = (
            df['sharpe_ratio'].rank(pct=True) * 0.4 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.4 +
            df['annual_return'].rank(pct=True) * 0.2
        )
    elif target_risk == "aggressive":
        # Favor high return
        df['score'] = (
            df['annual_return'].rank(pct=True) * 0.6 +
            df['sharpe_ratio'].rank(pct=True) * 0.3 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.1
        )
    else:  # moderate
        # Balanced
        df['score'] = (
            df['annual_return'].rank(pct=True) * 0.35 +
            df['sharpe_ratio'].rank(pct=True) * 0.35 +
            (1 - df['annual_volatility'].rank(pct=True)) * 0.3
        )

    # Normalize the scores to get weights
    df['suggested_weight'] = df['score'] / df['score'].sum()

    # Cap the maximum weight per single stock (max 15% for diversification)
    max_weight = 0.15
    df['suggested_weight'] = df['suggested_weight'].clip(upper=max_weight)

    # Renormalize
    df['suggested_weight'] = df['suggested_weight'] / df['suggested_weight'].sum()

    return df.sort_values('suggested_weight', ascending=False)
