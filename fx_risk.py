"""
Modulo per la stima del rischio di cambio.

Il resto della pipeline calcola rendimenti/volatilità in valuta LOCALE di
ciascun titolo (corretto per Sharpe/volatilità/correlazione, dato che sono
scale-invariant rispetto alla valuta). Ma un investitore con capitale in EUR
che tiene titoli in USD/GBP/CHF sopporta anche un rischio di cambio che
quella parte della pipeline non vede. Questo modulo lo quantifica a parte,
come disclosure esplicita, invece di fingere che non esista.
"""

import yfinance as yf
from typing import Dict, List

FX_PAIRS_VS_EUR = {
    'USD': 'EURUSD=X',
    'GBP': 'EURGBP=X',
    'GBp': 'EURGBP=X',  # GBp = pence, stesso sottostante/rischio cambio di GBP
    'CHF': 'EURCHF=X',
}


def fetch_fx_volatility(currencies: List[str], period: str = "1y") -> Dict[str, float]:
    """
    Scarica i tassi di cambio verso EUR per le valute non-EUR presenti nel
    portafoglio e calcola la loro volatilità annualizzata storica.
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
    Scarica il tasso di cambio spot più recente verso EUR (quante unità di
    valuta locale per 1 EUR) per ogni valuta non-EUR data. A differenza di
    fetch_fx_volatility (che serve la volatilità storica per la disclosure
    di rischio cambio), qui serve il rate puntuale per convertire in EUR un
    valore di mercato corrente (holdings/portfolio_monitor.py).
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
    Converte un importo in valuta locale in EUR usando i rate da
    fetch_latest_fx_rates. Gestisce GBp (pence): prima /100 per GBP, poi
    applica il rate EUR/GBP.
    """
    if currency is None or currency == 'EUR':
        return amount_local

    if currency == 'GBp':
        amount_local = amount_local / 100.0
        currency = 'GBP'

    rate = fx_rates.get(currency)
    if not rate:
        raise ValueError(f"Nessun tasso di cambio disponibile per {currency}")
    return amount_local / rate


def estimate_currency_risk(weights: Dict[str, float],
                           ticker_currencies: Dict[str, str],
                           base_currency: str = "EUR",
                           period: str = "1y") -> Dict:
    """
    Stima il rischio di cambio non coperto del portafoglio: quanto capitale
    è esposto a ciascuna valuta diversa da quella base, e un contributo di
    volatilità stimato in modo approssimato (somma pesata delle volatilità
    FX per esposizione in valuta — un'approssimazione al primo ordine che
    ignora la correlazione tra cambio ed equity e tra le valute stesse, una
    semplificazione dichiarata, non un vero VaR multi-valuta).
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
