"""
Module for fundamental stock valuation (over/undervaluation)

Downloads current valuation multiples (P/E, PEG, P/B) via yfinance and
compares them against peers in the same sector within our universe, to get
a RELATIVE overvaluation score — not an absolute one, because comparing
the P/E of a nuclear stock with a quantum computing one makes no sense:
they are sectors with completely different growth and risk profiles.
"""

import yfinance as yf
import pandas as pd
from datetime import date
from typing import List
from portfolio_config import SECTOR_CLASSIFICATION, VALUATION_CONFIG


def fetch_valuation_metrics(tickers: List[str]) -> pd.DataFrame:
    """
    Downloads current valuation multiples for each ticker.

    Returns:
        DataFrame with columns: ticker, trailing_pe, peg_ratio, price_to_book,
        trailing_eps, earnings_growth, profit_margin
        (missing or non-meaningful values set to NaN)
    """
    print(f"📐 Downloading valuation data for {len(tickers)} tickers...")

    rows = []
    failed = 0

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info

            pe = info.get('trailingPE')
            peg = info.get('trailingPegRatio', info.get('pegRatio'))
            pb = info.get('priceToBook')
            eps = info.get('trailingEps')
            forward_eps = info.get('forwardEps')
            # Year-over-year earnings growth (latest quarter vs. the same
            # quarter a year earlier); unlike P/E, PEG and P/B, a negative
            # value here is informative (declining earnings), not a figure
            # to discard as non-comparable
            earnings_growth = info.get('earningsGrowth', info.get('earningsQuarterlyGrowth'))
            profit_margin = info.get('profitMargins')

            # Annual dividend per share, in local currency (absolute, not
            # ambiguous). We do NOT use Yahoo's 'dividendYield' field:
            # depending on the stock/API version it is expressed
            # inconsistently (sometimes a 0-1 fraction, sometimes already in
            # percentage points), a real risk of showing a yield off by an
            # order of magnitude. We compute it ourselves in main.py as
            # dividend_rate / last known price, data we already download.
            dividend_rate = info.get('dividendRate')
            payout_ratio = info.get('payoutRatio')

            # A negative P/E (loss-making company) is not meaningfully
            # comparable to positive P/Es: we treat it as missing instead of
            # forcing it into a comparison that wouldn't make sense
            if pe is not None and pe <= 0:
                pe = None
            if peg is not None and peg <= 0:
                peg = None
            if pb is not None and pb <= 0:
                pb = None

            currency = info.get('currency')

            # Stocks listed in London (currency 'GBp'/'GBX', price in
            # pence): Yahoo reports historical prices in pence but EPS and
            # dividend per share in pounds (GBP) — a 100x discrepancy,
            # verified empirically (trailingEps * trailingPE = price in
            # pence / 100). We convert at the source here to pence, so every
            # "per share" figure stays on the same scale as the price used
            # elsewhere in the pipeline.
            if currency in ('GBp', 'GBX'):
                if eps is not None:
                    eps *= 100
                if forward_eps is not None:
                    forward_eps *= 100
                if dividend_rate is not None:
                    dividend_rate *= 100
            rows.append({'ticker': ticker, 'trailing_pe': pe, 'peg_ratio': peg,
                        'price_to_book': pb, 'trailing_eps': eps, 'forward_eps': forward_eps,
                        'earnings_growth': earnings_growth, 'profit_margin': profit_margin,
                        'dividend_rate': dividend_rate, 'payout_ratio': payout_ratio,
                        'currency': currency})
        except Exception as e:
            failed += 1
            rows.append({'ticker': ticker, 'trailing_pe': None, 'peg_ratio': None,
                        'price_to_book': None, 'trailing_eps': None, 'forward_eps': None,
                        'earnings_growth': None, 'profit_margin': None,
                        'dividend_rate': None, 'payout_ratio': None, 'currency': None})
            print(f"  ⚠️  {ticker}: error fetching valuation data - {str(e)[:50]}")

    print(f"✅ Valuation data downloaded: {len(tickers) - failed}/{len(tickers)} tickers\n")

    return pd.DataFrame(rows)


def get_sector(ticker: str) -> str:
    """Finds a ticker's sector (same logic as practical_allocation.get_sector)"""
    for sector, tickers in SECTOR_CLASSIFICATION.items():
        if ticker in tickers:
            return sector
    return "Other"


def calculate_overvaluation_score(valuation_df: pd.DataFrame) -> pd.Series:
    """
    Computes an overvaluation percentile (0=cheapest in its sector, 1=most
    expensive) for each ticker, as the average of the available percentiles
    on P/E, PEG and P/B computed ONLY against peers in the same sector
    within this universe (a cross-sector comparison would not be
    meaningful). If no multiple is available for a ticker, the score stays
    neutral (0.5): missing data is interpreted neither as cheap nor as
    expensive.

    Returns:
        Series indexed by ticker with the overvaluation percentile
    """
    if valuation_df.empty:
        return pd.Series(dtype=float)

    df = valuation_df.copy()
    df['sector'] = df['ticker'].apply(get_sector)

    metric_cols = VALUATION_CONFIG['metrics']
    percentile_cols = []

    for col in metric_cols:
        if col not in df.columns:
            continue
        pct_col = f'{col}_pct'
        # rank within sector group: 1 = most expensive in the sector on that metric
        df[pct_col] = df.groupby('sector')[col].rank(pct=True, na_option='keep')
        percentile_cols.append(pct_col)

    if not percentile_cols:
        return pd.Series(0.5, index=df['ticker'])

    overvaluation = df[percentile_cols].mean(axis=1, skipna=True)
    overvaluation = overvaluation.fillna(0.5)

    return pd.Series(overvaluation.values, index=df['ticker'])


def calculate_valuation_scores(tickers: List[str]) -> pd.DataFrame:
    """
    Convenience entry point: downloads valuation data and computes the
    overvaluation percentile for each ticker.

    Returns:
        DataFrame with: ticker, trailing_pe, peg_ratio, price_to_book,
        trailing_eps, earnings_growth, profit_margin, overvaluation_percentile
    """
    valuation_df = fetch_valuation_metrics(tickers)
    valuation_df['overvaluation_percentile'] = calculate_overvaluation_score(valuation_df).reindex(
        valuation_df['ticker']
    ).values
    return valuation_df


def merge_valuation(metrics: pd.DataFrame, valuation_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges the valuation columns (including overvaluation_percentile) into
    a metrics DataFrame, by ticker. Tickers without valuation data get a
    neutral score (0.5, neither cheap nor expensive).
    """
    if valuation_df is None or valuation_df.empty:
        result = metrics.copy()
        result['overvaluation_percentile'] = 0.5
        return result

    cols = ['ticker', 'trailing_pe', 'peg_ratio', 'price_to_book', 'trailing_eps', 'forward_eps',
            'earnings_growth', 'profit_margin', 'dividend_rate', 'payout_ratio', 'currency',
            'overvaluation_percentile']
    cols = [c for c in cols if c in valuation_df.columns]

    result = metrics.merge(valuation_df[cols], on='ticker', how='left')
    result['overvaluation_percentile'] = result['overvaluation_percentile'].fillna(0.5)
    return result


def fetch_calendar_events(tickers: List[str]) -> pd.DataFrame:
    """
    Downloads the next earnings release date (with analyst consensus
    estimates for EPS and revenue) and the next ex-dividend/payment date
    for each ticker, via `yf.Ticker(...).calendar` — an endpoint separate
    from `.info`, queried only for the stocks actually in the portfolio
    (not the whole universe) to limit network calls. Earnings and dividends
    share the same call, so they are downloaded together here instead of in
    two separate functions.

    Note: earnings estimates are consensus figures (the average of the
    brokers covering the stock), not a certain number — they can change or
    turn out to be wrong, and for some stocks (particularly those listed
    outside the US) Yahoo Finance publishes no estimate or dividend dates
    at all (non-dividend-paying stocks, e.g. growth stocks).

    Returns:
        DataFrame with: ticker, next_earnings_date (date or None),
        days_to_earnings, eps_estimate, revenue_estimate,
        next_ex_dividend_date (date or None), next_dividend_pay_date
    """
    print(f"📅 Downloading earnings/dividend calendar for {len(tickers)} tickers...")

    rows = []
    failed = 0
    today = date.today()

    for ticker in tickers:
        try:
            calendar = yf.Ticker(ticker).calendar or {}

            # Yahoo sometimes hasn't yet updated the field with the next
            # confirmed date (earnings or dividend) and returns the last one
            # that has already passed: we discard it instead of showing a
            # meaningless negative countdown
            earnings_dates = calendar.get('Earnings Date')
            future_earnings = [d for d in (earnings_dates or []) if d >= today]
            next_earnings_date = min(future_earnings) if future_earnings else None
            days_to_earnings = (next_earnings_date - today).days if next_earnings_date else None

            ex_div_date = calendar.get('Ex-Dividend Date')
            if ex_div_date is not None and ex_div_date < today:
                ex_div_date = None
            pay_date = calendar.get('Dividend Date')
            if pay_date is not None and pay_date < today:
                pay_date = None

            # The earnings consensus estimates are tied to the date
            # discarded above: if there is no known upcoming release, it
            # makes no sense to show them
            rows.append({
                'ticker': ticker,
                'next_earnings_date': next_earnings_date,
                'days_to_earnings': days_to_earnings,
                'eps_estimate': calendar.get('Earnings Average') if next_earnings_date else None,
                'revenue_estimate': calendar.get('Revenue Average') if next_earnings_date else None,
                'next_ex_dividend_date': ex_div_date,
                'next_dividend_pay_date': pay_date,
            })
        except Exception as e:
            failed += 1
            rows.append({'ticker': ticker, 'next_earnings_date': None, 'days_to_earnings': None,
                        'eps_estimate': None, 'revenue_estimate': None,
                        'next_ex_dividend_date': None, 'next_dividend_pay_date': None})
            print(f"  ⚠️  {ticker}: error fetching earnings/dividend calendar - {str(e)[:50]}")

    print(f"✅ Earnings/dividend calendar downloaded: {len(tickers) - failed}/{len(tickers)} tickers\n")

    return pd.DataFrame(rows)
