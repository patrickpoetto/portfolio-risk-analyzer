"""
Modulo per la valutazione fondamentale dei titoli (sopra/sottovalutazione)

Scarica multipli di valutazione correnti (P/E, PEG, P/B) via yfinance e li
confronta con i pari dello stesso settore nel nostro universo, per ottenere
un punteggio di sopravvalutazione relativo — non assoluto, perché confrontare
il P/E di un titolo nucleare con uno di quantum computing non ha senso: sono
settori con profili di crescita e rischio completamente diversi.
"""

import yfinance as yf
import pandas as pd
from datetime import date
from typing import List
from portfolio_config import SECTOR_CLASSIFICATION, VALUATION_CONFIG


def fetch_valuation_metrics(tickers: List[str]) -> pd.DataFrame:
    """
    Scarica i multipli di valutazione correnti per ogni ticker.

    Returns:
        DataFrame con colonne: ticker, trailing_pe, peg_ratio, price_to_book,
        trailing_eps, earnings_growth, profit_margin
        (valori mancanti o non significativi impostati a NaN)
    """
    print(f"📐 Scaricamento dati di valutazione per {len(tickers)} ticker...")

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
            # Crescita utili anno su anno (ultimo trimestre vs stesso
            # trimestre l'anno prima); a differenza di P/E, PEG e P/B, un
            # valore negativo qui è informativo (utili in calo), non un
            # dato da scartare come non comparabile
            earnings_growth = info.get('earningsGrowth', info.get('earningsQuarterlyGrowth'))
            profit_margin = info.get('profitMargins')

            # Dividendo annuo per azione, in valuta locale (assoluto, non
            # ambiguo). NON usiamo il campo 'dividendYield' di Yahoo: a
            # seconda del titolo/versione API è espresso in modo incoerente
            # (a volte frazione 0-1, a volte già in punti percentuali), un
            # rischio concreto di mostrare un rendimento sbagliato di un
            # ordine di grandezza. Lo calcoliamo noi in main.py come
            # dividend_rate / ultimo prezzo noto, dati che già scarichiamo.
            dividend_rate = info.get('dividendRate')
            payout_ratio = info.get('payoutRatio')

            # P/E negativo (azienda in perdita) non è confrontabile in modo
            # significativo con P/E positivi: lo trattiamo come mancante
            # invece di forzarlo in un confronto senza senso
            if pe is not None and pe <= 0:
                pe = None
            if peg is not None and peg <= 0:
                peg = None
            if pb is not None and pb <= 0:
                pb = None

            currency = info.get('currency')

            # Titoli quotati a Londra (valuta 'GBp'/'GBX', prezzo in pence):
            # Yahoo riporta gli storici prezzi in pence ma EPS e dividendo
            # per azione in sterline (GBP) — fattore 100x di discrepanza,
            # verificato empiricamente (trailingEps * trailingPE = prezzo
            # in pence / 100). Convertiamo qui alla fonte in pence, così
            # ogni figura "per azione" resta nella stessa scala del prezzo
            # usato altrove nella pipeline.
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
            print(f"  ⚠️  {ticker}: errore dati valutazione - {str(e)[:50]}")

    print(f"✅ Dati di valutazione scaricati: {len(tickers) - failed}/{len(tickers)} ticker\n")

    return pd.DataFrame(rows)


def get_sector(ticker: str) -> str:
    """Trova il settore di un ticker (stessa logica di practical_allocation.get_sector)"""
    for sector, tickers in SECTOR_CLASSIFICATION.items():
        if ticker in tickers:
            return sector
    return "Altri"


def calculate_overvaluation_score(valuation_df: pd.DataFrame) -> pd.Series:
    """
    Calcola un percentile di sopravvalutazione (0=più economico del suo
    settore, 1=più caro) per ogni ticker, come media dei percentili
    disponibili su P/E, PEG e P/B calcolati SOLO rispetto ai pari dello
    stesso settore in questo universo (un confronto cross-settore non
    sarebbe significativo). Se per un ticker non è disponibile nessun
    multiplo, il punteggio resta neutro (0.5): dati mancanti non vengono
    interpretati né come economici né come cari.

    Returns:
        Series indicizzata per ticker con il percentile di sopravvalutazione
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
        # rank per gruppo settoriale: 1 = il più caro del settore su quella metrica
        df[pct_col] = df.groupby('sector')[col].rank(pct=True, na_option='keep')
        percentile_cols.append(pct_col)

    if not percentile_cols:
        return pd.Series(0.5, index=df['ticker'])

    overvaluation = df[percentile_cols].mean(axis=1, skipna=True)
    overvaluation = overvaluation.fillna(0.5)

    return pd.Series(overvaluation.values, index=df['ticker'])


def calculate_valuation_scores(tickers: List[str]) -> pd.DataFrame:
    """
    Punto di ingresso comodo: scarica i dati di valutazione e calcola il
    percentile di sopravvalutazione per ogni ticker.

    Returns:
        DataFrame con: ticker, trailing_pe, peg_ratio, price_to_book,
        trailing_eps, earnings_growth, profit_margin, overvaluation_percentile
    """
    valuation_df = fetch_valuation_metrics(tickers)
    valuation_df['overvaluation_percentile'] = calculate_overvaluation_score(valuation_df).reindex(
        valuation_df['ticker']
    ).values
    return valuation_df


def merge_valuation(metrics: pd.DataFrame, valuation_df: pd.DataFrame) -> pd.DataFrame:
    """
    Unisce le colonne di valutazione (incluso overvaluation_percentile) a un
    DataFrame di metriche, per ticker. Ticker senza dati di valutazione
    ricevono un punteggio neutro (0.5, né economico né caro).
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
    Scarica la prossima data di pubblicazione utili (con stima di consensus
    degli analisti su EPS e ricavi) e la prossima data di stacco/pagamento
    dividendo per ogni ticker, via `yf.Ticker(...).calendar` — un endpoint
    separato da `.info`, interrogato solo per i titoli effettivamente in
    portafoglio (non l'intero universo) per limitare le chiamate di rete.
    Utili e dividendi condividono la stessa chiamata, quindi vengono
    scaricati insieme qui invece che in due funzioni separate.

    Nota: le stime utili sono consensus (media dei broker che coprono il
    titolo), non un dato certo — possono cambiare o rivelarsi sbagliate, e
    per alcuni titoli (in particolare quelli quotati fuori dagli USA) Yahoo
    Finance non pubblica alcuna stima né date dividendo (titoli che non
    distribuiscono dividendi, ad es. growth stock).

    Returns:
        DataFrame con: ticker, next_earnings_date (date o None),
        days_to_earnings, eps_estimate, revenue_estimate,
        next_ex_dividend_date (date o None), next_dividend_pay_date
    """
    print(f"📅 Scaricamento calendario utili/dividendi per {len(tickers)} ticker...")

    rows = []
    failed = 0
    today = date.today()

    for ticker in tickers:
        try:
            calendar = yf.Ticker(ticker).calendar or {}

            # Yahoo a volte non ha ancora aggiornato il campo con la prossima
            # data confermata (utili o dividendo) e restituisce l'ultima già
            # passata: la scartiamo invece di mostrare un countdown negativo
            # privo di senso
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

            # Le stime di consensus utili sono legate alla data scartata
            # sopra: se non c'è una prossima pubblicazione nota, non ha
            # senso mostrarle
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
            print(f"  ⚠️  {ticker}: errore calendario utili/dividendi - {str(e)[:50]}")

    print(f"✅ Calendario utili/dividendi scaricato: {len(tickers) - failed}/{len(tickers)} ticker\n")

    return pd.DataFrame(rows)
