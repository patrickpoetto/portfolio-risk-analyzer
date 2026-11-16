"""
Ledger persistente delle posizioni realmente detenute in portafoglio
(holdings/holdings.json) e log append-only delle transazioni
(holdings/transactions.json).

A differenza di profiles/*.json (che descrivono capitale e preferenze per
generare un report di allocazione ipotetico), questo modulo tiene lo stato
REALE del portafoglio: quante azioni di cosa, a che prezzo medio di carico,
aggiornato ad ogni acquisto/vendita effettivo. È la fonte dati per il
monitoraggio live (portfolio_monitor.py) e per il bot Telegram.

Uso da riga di comando:
    python holdings.py show
    python holdings.py buy AAPL 5 150.00
    python holdings.py buy NUOVOTICKER 10 42.50 --name "Nuova Azienda SpA" --exchange "NASDAQ" --currency USD
    python holdings.py sell AAPL 2 180.00
"""

import argparse
import json
import os
from datetime import date
from typing import Dict, List, Optional

HOLDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdings")
HOLDINGS_FILE = os.path.join(HOLDINGS_DIR, "holdings.json")
TRANSACTIONS_FILE = os.path.join(HOLDINGS_DIR, "transactions.json")


def load_holdings() -> Dict:
    if not os.path.isfile(HOLDINGS_FILE):
        return {"positions": [], "realized_pl_total_eur": 0.0, "last_updated": None}
    with open(HOLDINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_holdings(data: Dict) -> None:
    data["last_updated"] = date.today().isoformat()
    os.makedirs(HOLDINGS_DIR, exist_ok=True)
    with open(HOLDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_transactions() -> List[Dict]:
    if not os.path.isfile(TRANSACTIONS_FILE):
        return []
    with open(TRANSACTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def append_transaction(tx: Dict) -> None:
    transactions = load_transactions()
    transactions.append(tx)
    os.makedirs(HOLDINGS_DIR, exist_ok=True)
    with open(TRANSACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)
        f.write("\n")


def find_position(data: Dict, ticker: str) -> Optional[Dict]:
    for pos in data["positions"]:
        if pos["ticker"] == ticker:
            return pos
    return None


def record_buy(ticker: str, shares: float, price_eur: float,
              name: Optional[str] = None, exchange: Optional[str] = None,
              currency: Optional[str] = None, trade_date: Optional[str] = None) -> Dict:
    """
    Registra un acquisto: se il ticker è già in portafoglio, ricalcola il
    prezzo medio di carico come media pesata (prezzo medio esistente e nuovo
    lotto, pesati per numero di azioni) invece di sostituirlo — lo stesso
    criterio (costo medio ponderato) che useresti a mano su un foglio di
    calcolo. Se è un ticker nuovo, richiede nome/borsa/valuta per poterlo
    mostrare correttamente nel monitor.
    """
    data = load_holdings()
    pos = find_position(data, ticker)

    if pos is None:
        if not (name and exchange and currency):
            raise ValueError(
                f"'{ticker}' non è ancora in portafoglio: servono --name, --exchange e --currency "
                f"per registrarlo la prima volta."
            )
        pos = {"ticker": ticker, "name": name, "exchange": exchange, "currency": currency,
               "shares": 0.0, "avg_cost_eur": 0.0}
        data["positions"].append(pos)

    new_total_shares = pos["shares"] + shares
    pos["avg_cost_eur"] = (
        (pos["shares"] * pos["avg_cost_eur"] + shares * price_eur) / new_total_shares
        if new_total_shares > 0 else price_eur
    )
    pos["shares"] = new_total_shares

    save_holdings(data)
    append_transaction({
        "date": trade_date or date.today().isoformat(),
        "ticker": ticker, "action": "buy", "shares": shares,
        "price_eur": price_eur, "total_eur": round(shares * price_eur, 2),
        "note": "",
    })
    return pos


def record_sell(ticker: str, shares: float, price_eur: float,
                trade_date: Optional[str] = None) -> Dict:
    """
    Registra una vendita: riduce le azioni detenute, calcola la plusvalenza/
    minusvalenza realizzata rispetto al prezzo medio di carico (che NON
    cambia per le azioni rimaste — è così che funziona il costo medio
    ponderato) e la accumula in realized_pl_total_eur. Se le azioni vendute
    esauriscono la posizione, la rimuove dal portafoglio.
    """
    data = load_holdings()
    pos = find_position(data, ticker)
    if pos is None:
        raise ValueError(f"'{ticker}' non è in portafoglio, niente da vendere.")
    if shares > pos["shares"] + 1e-9:
        raise ValueError(f"Stai vendendo {shares} azioni di {ticker} ma ne possiedi solo {pos['shares']}.")

    realized_pl = shares * (price_eur - pos["avg_cost_eur"])
    pos["shares"] -= shares
    if pos["shares"] <= 1e-9:
        data["positions"] = [p for p in data["positions"] if p["ticker"] != ticker]

    data["realized_pl_total_eur"] = data.get("realized_pl_total_eur", 0.0) + realized_pl
    save_holdings(data)
    append_transaction({
        "date": trade_date or date.today().isoformat(),
        "ticker": ticker, "action": "sell", "shares": shares,
        "price_eur": price_eur, "total_eur": round(shares * price_eur, 2),
        "realized_pl_eur": round(realized_pl, 2), "note": "",
    })
    return {"realized_pl_eur": realized_pl, "remaining_shares": max(pos["shares"], 0.0)}


def print_holdings() -> None:
    data = load_holdings()
    positions = sorted(data["positions"], key=lambda p: p["shares"] * p["avg_cost_eur"], reverse=True)
    total_cost = sum(p["shares"] * p["avg_cost_eur"] for p in positions)

    print(f"{'Ticker':10s} {'Nome':40s} {'Azioni':>12s} {'Prezzo medio':>14s} {'Costo tot. EUR':>15s}")
    print("-" * 95)
    for p in positions:
        cost = p["shares"] * p["avg_cost_eur"]
        print(f"{p['ticker']:10s} {p['name'][:40]:40s} {p['shares']:>12.4f} "
              f"{p['avg_cost_eur']:>14.2f} {cost:>15.2f}")
    print("-" * 95)
    print(f"{'TOTALE COSTO CARICO':63s} {total_cost:>15.2f} EUR")
    print(f"Plusvalenza/minusvalenza realizzata cumulata: {data.get('realized_pl_total_eur', 0.0):.2f} EUR")
    if data.get("last_updated"):
        print(f"Ultimo aggiornamento: {data['last_updated']}")


def main():
    parser = argparse.ArgumentParser(description="Gestione ledger posizioni portafoglio")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Mostra le posizioni correnti")

    p_buy = sub.add_parser("buy", help="Registra un acquisto")
    p_buy.add_argument("ticker")
    p_buy.add_argument("shares", type=float)
    p_buy.add_argument("price_eur", type=float, help="Prezzo per azione in EUR")
    p_buy.add_argument("--name", help="Nome completo (solo per un ticker nuovo)")
    p_buy.add_argument("--exchange", help="Borsa (solo per un ticker nuovo)")
    p_buy.add_argument("--currency", help="Valuta di quotazione, es. USD/EUR/GBp (solo per un ticker nuovo)")
    p_buy.add_argument("--date", dest="trade_date", help="Data operazione YYYY-MM-DD (default oggi)")

    p_sell = sub.add_parser("sell", help="Registra una vendita")
    p_sell.add_argument("ticker")
    p_sell.add_argument("shares", type=float)
    p_sell.add_argument("price_eur", type=float, help="Prezzo per azione in EUR")
    p_sell.add_argument("--date", dest="trade_date", help="Data operazione YYYY-MM-DD (default oggi)")

    args = parser.parse_args()

    if args.command == "show":
        print_holdings()
    elif args.command == "buy":
        pos = record_buy(args.ticker, args.shares, args.price_eur, args.name,
                         args.exchange, args.currency, args.trade_date)
        print(f"✅ Acquisto registrato: {args.ticker} ora {pos['shares']:.4f} azioni "
              f"a prezzo medio {pos['avg_cost_eur']:.2f} EUR")
    elif args.command == "sell":
        result = record_sell(args.ticker, args.shares, args.price_eur, args.trade_date)
        segno = "guadagno" if result["realized_pl_eur"] >= 0 else "perdita"
        print(f"✅ Vendita registrata: {segno} realizzato {result['realized_pl_eur']:.2f} EUR, "
              f"restano {result['remaining_shares']:.4f} azioni di {args.ticker}")


if __name__ == "__main__":
    main()
