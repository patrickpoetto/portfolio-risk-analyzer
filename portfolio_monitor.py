"""
Monitoraggio live del portafoglio realmente detenuto (holdings/holdings.json).

A differenza di main.py (che genera un report di allocazione/ottimizzazione
IPOTETICO per un capitale dato), questo modulo guarda lo stato REALE delle
posizioni: prezzo corrente, valore di mercato, plus/minusvalenza non
realizzata rispetto al prezzo medio di carico, peso corrente in portafoglio.
È il motore dati condiviso da dashboard.py (report HTML) e telegram_bot.py.
"""

import json
import os
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from holdings import load_holdings, HOLDINGS_DIR
from fx_risk import fetch_latest_fx_rates, convert_to_eur
from valuation import fetch_calendar_events

VALUE_HISTORY_FILE = os.path.join(HOLDINGS_DIR, "value_history.json")


def fetch_live_prices(tickers: List[str]) -> Dict[str, Optional[float]]:
    """
    Prezzo corrente (in valuta locale di quotazione) per ogni ticker, via
    fast_info (un solo endpoint leggero, niente storico) con fallback su
    .info se fast_info non lo espone per quel titolo.
    """
    prices = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.get("lastPrice") if hasattr(t.fast_info, "get") else None
            if price is None:
                price = t.info.get("currentPrice") or t.info.get("regularMarketPrice")
            prices[ticker] = float(price) if price is not None else None
        except Exception:
            prices[ticker] = None
    return prices


def build_snapshot() -> pd.DataFrame:
    """
    Costruisce lo snapshot corrente del portafoglio: una riga per posizione
    con prezzo live, valore di mercato in EUR, plus/minusvalenza non
    realizzata (assoluta e %), peso corrente.

    Returns:
        DataFrame con: ticker, name, exchange, currency, shares,
        avg_cost_eur, cost_basis_eur, last_price_local, last_price_eur,
        market_value_eur, unrealized_pl_eur, unrealized_pl_pct, weight
    """
    data = load_holdings()
    positions = data["positions"]
    if not positions:
        return pd.DataFrame()

    tickers = [p["ticker"] for p in positions]
    currencies = [p["currency"] for p in positions]

    live_prices = fetch_live_prices(tickers)
    fx_rates = fetch_latest_fx_rates(currencies)

    rows = []
    for p in positions:
        price_local = live_prices.get(p["ticker"])
        cost_basis = p["shares"] * p["avg_cost_eur"]

        if price_local is None:
            price_eur = None
            market_value = None
            pl_eur = None
            pl_pct = None
        else:
            try:
                price_eur = convert_to_eur(price_local, p["currency"], fx_rates)
            except ValueError:
                price_eur = None

            if price_eur is None:
                market_value = None
                pl_eur = None
                pl_pct = None
            else:
                market_value = p["shares"] * price_eur
                pl_eur = market_value - cost_basis
                pl_pct = (pl_eur / cost_basis) if cost_basis > 0 else None

        rows.append({
            "ticker": p["ticker"], "name": p["name"], "exchange": p["exchange"],
            "currency": p["currency"], "shares": p["shares"], "avg_cost_eur": p["avg_cost_eur"],
            "cost_basis_eur": cost_basis, "last_price_local": price_local,
            "last_price_eur": price_eur, "market_value_eur": market_value,
            "unrealized_pl_eur": pl_eur, "unrealized_pl_pct": pl_pct,
        })

    df = pd.DataFrame(rows)
    total_value = df["market_value_eur"].sum(skipna=True)
    df["weight"] = df["market_value_eur"] / total_value if total_value > 0 else None
    return df.sort_values("market_value_eur", ascending=False, na_position="last")


def portfolio_totals(snapshot: pd.DataFrame, realized_pl_total_eur: float = 0.0) -> Dict:
    """Aggregati sull'intero portafoglio a partire dallo snapshot per-posizione."""
    valid = snapshot.dropna(subset=["market_value_eur"])
    total_value = valid["market_value_eur"].sum()
    total_cost = snapshot["cost_basis_eur"].sum()
    unrealized_pl = valid["unrealized_pl_eur"].sum()
    failed_tickers = snapshot[snapshot["market_value_eur"].isna()]["ticker"].tolist()

    return {
        "total_market_value_eur": total_value,
        "total_cost_basis_eur": total_cost,
        "unrealized_pl_eur": unrealized_pl,
        "unrealized_pl_pct": (unrealized_pl / total_cost) if total_cost > 0 else None,
        "realized_pl_eur": realized_pl_total_eur,
        "total_pl_eur": unrealized_pl + realized_pl_total_eur,
        "failed_tickers": failed_tickers,
        "as_of": datetime.now().isoformat(timespec="seconds"),
    }


def record_daily_value(totals: Dict) -> None:
    """
    Appende il valore di mercato totale odierno a un log storico
    (value_history.json), un punto al giorno (sovrascrive se lo snapshot
    di oggi esiste già, per non sporcare il grafico con rilanci multipli
    nello stesso giorno). È la serie usata dal grafico "andamento nel
    tempo" della dashboard: a differenza di una ricostruzione a posteriori
    dai prezzi storici, riflette il valore osservato nei momenti reali in
    cui il monitor è stato eseguito.
    """
    today = date.today().isoformat()
    history = []
    if os.path.isfile(VALUE_HISTORY_FILE):
        with open(VALUE_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    history = [h for h in history if h["date"] != today]
    history.append({
        "date": today,
        "total_market_value_eur": totals["total_market_value_eur"],
        "total_cost_basis_eur": totals["total_cost_basis_eur"],
        "unrealized_pl_eur": totals["unrealized_pl_eur"],
    })
    history.sort(key=lambda h: h["date"])

    with open(VALUE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_value_history() -> pd.DataFrame:
    if not os.path.isfile(VALUE_HISTORY_FILE):
        return pd.DataFrame(columns=["date", "total_market_value_eur", "total_cost_basis_eur", "unrealized_pl_eur"])
    with open(VALUE_HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    df = pd.DataFrame(history)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_monitor_data() -> Dict:
    """
    Punto di ingresso comodo: costruisce snapshot, totali, calendario
    utili/dividendi e aggiorna lo storico valore — tutto quello che serve
    a dashboard.py e telegram_bot.py in un'unica chiamata.
    """
    data = load_holdings()
    snapshot = build_snapshot()
    totals = portfolio_totals(snapshot, data.get("realized_pl_total_eur", 0.0))
    record_daily_value(totals)

    tickers = [p["ticker"] for p in data["positions"]]
    calendar_df = fetch_calendar_events(tickers) if tickers else pd.DataFrame()

    return {
        "snapshot": snapshot,
        "totals": totals,
        "calendar": calendar_df,
        "value_history": load_value_history(),
    }


if __name__ == "__main__":
    result = get_monitor_data()
    snap = result["snapshot"]
    tot = result["totals"]

    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    print(snap[["ticker", "name", "last_price_local", "currency", "market_value_eur",
               "unrealized_pl_eur", "unrealized_pl_pct", "weight"]].to_string(index=False))
    print()
    print(f"Valore di mercato totale: {tot['total_market_value_eur']:,.2f} EUR")
    print(f"Costo di carico totale:   {tot['total_cost_basis_eur']:,.2f} EUR")
    print(f"Plus/minus non realizzata: {tot['unrealized_pl_eur']:,.2f} EUR "
          f"({tot['unrealized_pl_pct'] * 100:.2f}%)" if tot['unrealized_pl_pct'] is not None else "")
    print(f"Plus/minus realizzata cumulata: {tot['realized_pl_eur']:,.2f} EUR")
    print(f"Plus/minus totale: {tot['total_pl_eur']:,.2f} EUR")
    if tot["failed_tickers"]:
        print(f"⚠️  Prezzo non disponibile per: {', '.join(tot['failed_tickers'])}")
