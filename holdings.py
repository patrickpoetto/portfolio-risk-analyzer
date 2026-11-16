"""
Persistent ledger of the positions actually held in the portfolio
(holdings/holdings.json) and an append-only transaction log
(holdings/transactions.json).

Unlike profiles/*.json (which describe capital and preferences to generate
a hypothetical allocation report), this module keeps the REAL state of the
portfolio: how many shares of what, at what average cost basis, updated on
every actual purchase/sale. It is the data source for live monitoring
(portfolio_monitor.py) and for the Telegram bot.

Command-line usage:
    python holdings.py show
    python holdings.py buy AAPL 5 150.00
    python holdings.py buy NEWTICKER 10 42.50 --name "New Company Inc" --exchange "NASDAQ" --currency USD
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
    Records a purchase: if the ticker is already in the portfolio,
    recomputes the average cost basis as a weighted average (existing
    average price and the new lot, weighted by number of shares) instead of
    replacing it — the same criterion (weighted average cost) you would use
    by hand on a spreadsheet. If it is a new ticker, it requires
    name/exchange/currency so it can be displayed correctly in the monitor.
    """
    data = load_holdings()
    pos = find_position(data, ticker)

    if pos is None:
        if not (name and exchange and currency):
            raise ValueError(
                f"'{ticker}' is not yet in the portfolio: --name, --exchange and --currency "
                f"are required to register it for the first time."
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
    Records a sale: reduces the shares held, computes the realized
    gain/loss relative to the average cost basis (which does NOT change for
    the remaining shares — that's how weighted average cost works) and adds
    it to realized_pl_total_eur. If the shares sold exhaust the position, it
    is removed from the portfolio.
    """
    data = load_holdings()
    pos = find_position(data, ticker)
    if pos is None:
        raise ValueError(f"'{ticker}' is not in the portfolio, nothing to sell.")
    if shares > pos["shares"] + 1e-9:
        raise ValueError(f"You're selling {shares} shares of {ticker} but you only hold {pos['shares']}.")

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

    print(f"{'Ticker':10s} {'Name':40s} {'Shares':>12s} {'Avg Price':>14s} {'Total Cost EUR':>15s}")
    print("-" * 95)
    for p in positions:
        cost = p["shares"] * p["avg_cost_eur"]
        print(f"{p['ticker']:10s} {p['name'][:40]:40s} {p['shares']:>12.4f} "
              f"{p['avg_cost_eur']:>14.2f} {cost:>15.2f}")
    print("-" * 95)
    print(f"{'TOTAL COST BASIS':63s} {total_cost:>15.2f} EUR")
    print(f"Cumulative realized gain/loss: {data.get('realized_pl_total_eur', 0.0):.2f} EUR")
    if data.get("last_updated"):
        print(f"Last updated: {data['last_updated']}")


def main():
    parser = argparse.ArgumentParser(description="Portfolio positions ledger management")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Show current positions")

    p_buy = sub.add_parser("buy", help="Record a purchase")
    p_buy.add_argument("ticker")
    p_buy.add_argument("shares", type=float)
    p_buy.add_argument("price_eur", type=float, help="Price per share in EUR")
    p_buy.add_argument("--name", help="Full name (only for a new ticker)")
    p_buy.add_argument("--exchange", help="Exchange (only for a new ticker)")
    p_buy.add_argument("--currency", help="Listing currency, e.g. USD/EUR/GBp (only for a new ticker)")
    p_buy.add_argument("--date", dest="trade_date", help="Trade date YYYY-MM-DD (defaults to today)")

    p_sell = sub.add_parser("sell", help="Record a sale")
    p_sell.add_argument("ticker")
    p_sell.add_argument("shares", type=float)
    p_sell.add_argument("price_eur", type=float, help="Price per share in EUR")
    p_sell.add_argument("--date", dest="trade_date", help="Trade date YYYY-MM-DD (defaults to today)")

    args = parser.parse_args()

    if args.command == "show":
        print_holdings()
    elif args.command == "buy":
        pos = record_buy(args.ticker, args.shares, args.price_eur, args.name,
                         args.exchange, args.currency, args.trade_date)
        print(f"✅ Purchase recorded: {args.ticker} now {pos['shares']:.4f} shares "
              f"at average price {pos['avg_cost_eur']:.2f} EUR")
    elif args.command == "sell":
        result = record_sell(args.ticker, args.shares, args.price_eur, args.trade_date)
        label = "gain" if result["realized_pl_eur"] >= 0 else "loss"
        print(f"✅ Sale recorded: realized {label} of {result['realized_pl_eur']:.2f} EUR, "
              f"{result['remaining_shares']:.4f} shares of {args.ticker} remaining")


if __name__ == "__main__":
    main()
