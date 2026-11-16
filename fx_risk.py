"""
Module for estimating currency (FX) risk.

The rest of the pipeline computes returns/volatility in each stock's LOCAL
currency (correct for Sharpe/volatility/correlation, since these are
scale-invariant with respect to currency). But an investor with capital in
EUR holding USD/GBP/CHF stocks also bears a currency risk that part of the
pipeline doesn't see. This module quantifies it separately, as an explicit
disclosure, instead of pretending it doesn't exist.
"""

import yfinance as yf
from typing import Dict, List

FX_PAIRS_VS_EUR = {
    'USD': 'EURUSD=X',
    'GBP': 'EURGBP=X',
    'GBp': 'EURGBP=X',  # GBp = pence, same underlying/currency risk as GBP
    'CHF': 'EURCHF=X',
}


def fetch_fx_volatility(currencies: List[str], period: str = "1y") -> Dict[str, float]:
    """
    Downloads exchange rates against EUR for the non-EUR currencies present
    in the portfolio and computes their historical annualized volatility.
    """
    result = {}
    unique_currencies = set(c for c in currencies if c and c != 'EUR')

    for cur in unique_currencies:
        pair = FX_PAIRS_VS_EUR.get(cur)
        if not pair:
            continue
        try:
            hist = yf.Ticker(pair).history(period=period)
            if hist.empty or len(hist) < 20:
                continue
            returns = hist['Close'].pct_change().dropna()
            vol = float(returns.std() * (252 ** 0.5))
            result[cur] = vol
        except Exception:
            continue

    return result


def fetch_latest_fx_rates(currencies: List[str]) -> Dict[str, float]:
    """
    Downloads the latest spot exchange rate against EUR (how many units of
    local currency per 1 EUR) for each given non-EUR currency. Unlike
    fetch_fx_volatility (which serves the historical volatility for the
    risk disclosure), this one is used for the point-in-time rate needed to
    convert a current market value to EUR (holdings/portfolio_monitor.py).
    """
    rates = {}
    unique_currencies = set(c for c in currencies if c and c != 'EUR')

    for cur in unique_currencies:
        lookup = 'GBP' if cur == 'GBp' else cur
        pair = FX_PAIRS_VS_EUR.get(lookup)
        if not pair:
            continue
        try:
            hist = yf.Ticker(pair).history(period="5d")
            if hist.empty:
                continue
            rate = float(hist['Close'].iloc[-1])
            rates[lookup] = rate
        except Exception:
            continue

    return rates


def convert_to_eur(amount_local: float, currency: str, fx_rates: Dict[str, float]) -> float:
    """
    Converts an amount in local currency to EUR using the rates from
    fetch_latest_fx_rates. Handles GBp (pence): first /100 to get GBP, then
    applies the EUR/GBP rate.
    """
    if currency is None or currency == 'EUR':
        return amount_local

    if currency == 'GBp':
        amount_local = amount_local / 100.0
        currency = 'GBP'

    rate = fx_rates.get(currency)
    if not rate:
        raise ValueError(f"No exchange rate available for {currency}")
    return amount_local / rate


def estimate_currency_risk(weights: Dict[str, float],
                           ticker_currencies: Dict[str, str],
                           base_currency: str = "EUR",
                           period: str = "1y") -> Dict:
    """
    Estimates the portfolio's unhedged currency risk: how much capital is
    exposed to each currency other than the base one, and an approximate
    volatility contribution (weighted sum of FX volatilities by currency
    exposure — a first-order approximation that ignores the correlation
    between FX and equity and between currencies themselves, a declared
    simplification, not a real multi-currency VaR).
    """
    exposure_by_currency = {}
    for ticker, w in weights.items():
        cur = ticker_currencies.get(ticker) or base_currency
        if cur == 'GBp':
            cur = 'GBP'
        exposure_by_currency[cur] = exposure_by_currency.get(cur, 0) + w

    non_base_exposure = sum(v for k, v in exposure_by_currency.items() if k != base_currency)

    fx_volatility = fetch_fx_volatility(list(exposure_by_currency.keys()), period)

    weighted_fx_vol = sum(
        exposure_by_currency.get(cur, 0) * vol
        for cur, vol in fx_volatility.items()
    )

    return {
        'exposure_by_currency': exposure_by_currency,
        'non_base_exposure': non_base_exposure,
        'fx_volatility_by_currency': fx_volatility,
        'estimated_fx_volatility_contribution': weighted_fx_vol,
    }
