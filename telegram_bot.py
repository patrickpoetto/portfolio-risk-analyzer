"""
Always-on Telegram bot for portfolio monitoring.

Responds to chat commands with the live state of the portfolio (reusing
portfolio_monitor.py/dashboard.py, the same data source as the HTML
dashboard) and sends push alerts when a stock moves beyond a daily
variation threshold. Editing positions (buys/sells) is deliberately kept
out of here: that's done from the terminal with holdings.py, by explicit
choice (a terminal command instead of doing it via the bot).

Setup (see also the welcome message printed on startup):
    1. Create a .env file in the project root (never committed, see
       .gitignore) with:
           TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
           TELEGRAM_CHAT_ID=12345678
    2. python telegram_bot.py

The bot responds ONLY to the configured chat_id: anyone else writing to
the bot (even knowing its username) gets a refusal, without seeing any
portfolio data.
"""

import json
import os
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from holdings import HOLDINGS_DIR
from portfolio_monitor import get_monitor_data, fetch_live_prices
import yfinance as yf

load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ALERT_THRESHOLD_PCT = float(os.environ.get("PRICE_ALERT_THRESHOLD_PCT", "0.05"))
ALERT_INTERVAL_MINUTES = float(os.environ.get("PRICE_ALERT_INTERVAL_MINUTES", "30"))

LAST_ALERTS_FILE = os.path.join(HOLDINGS_DIR, "last_alerts.json")


def authorized_only(handler):
    """Ignores/rejects any message that doesn't come from the chat_id configured in .env."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(CHAT_ID):
            await update.message.reply_text("⛔ Not authorized.")
            return
        await handler(update, context)
    return wrapper


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📡 Portfolio monitoring bot active.\n\n"
        "Available commands:\n"
        "/status — full summary (value, P/L, top movers)\n"
        "/pl — total gain/loss only\n"
        "/detail TICKER — detail for a single stock\n"
        "/earnings — upcoming earnings releases\n"
        "/dividends — upcoming ex-dividend/payment dates\n"
        "/dashboard — generate and send the updated HTML dashboard\n\n"
        f"Automatic alert if a stock moves beyond ±{ALERT_THRESHOLD_PCT:.0%} intraday "
        f"(checked every {ALERT_INTERVAL_MINUTES:.0f} minutes)."
    )


@authorized_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Updating prices, one moment...")
    data = get_monitor_data()
    snapshot = data["snapshot"]
    totals = data["totals"]

    valid = snapshot.dropna(subset=["unrealized_pl_pct"]).sort_values("unrealized_pl_pct", ascending=False)
    top_gainers = valid.head(3)
    top_losers = valid.tail(3).sort_values("unrealized_pl_pct")

    def fmt_line(row):
        return f"{row['ticker']:10s} {row['unrealized_pl_pct']:+7.2%}  ({row['unrealized_pl_eur']:+,.0f} €)"

    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/a"

    lines = [
        "📊 <b>PORTFOLIO STATUS</b>",
        "",
        f"Market value: <b>{totals['total_market_value_eur']:,.2f} €</b>",
        f"Cost basis:    {totals['total_cost_basis_eur']:,.2f} €",
        f"Unrealized P/L: <b>{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</b>",
        f"Cumulative realized P/L: {totals['realized_pl_eur']:+,.2f} €",
        "",
        "🟢 <b>Top 3 gainers</b>",
        "<pre>" + "\n".join(fmt_line(r) for _, r in top_gainers.iterrows()) + "</pre>",
        "🔴 <b>Top 3 losers</b>",
        "<pre>" + "\n".join(fmt_line(r) for _, r in top_losers.iterrows()) + "</pre>",
    ]
    if totals["failed_tickers"]:
        lines.append(f"⚠️ Price unavailable for: {', '.join(totals['failed_tickers'])}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def pl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    totals = data["totals"]
    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/a"
    await update.message.reply_text(
        f"Unrealized P/L: <b>{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</b>\n"
        f"Cumulative realized P/L: {totals['realized_pl_eur']:+,.2f} €\n"
        f"Total P/L: <b>{totals['total_pl_eur']:+,.2f} €</b>",
        parse_mode=ParseMode.HTML,
    )


@authorized_only
async def detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /detail TICKER (e.g. /detail AMD)")
        return

    query = context.args[0].upper()
    data = get_monitor_data()
    snapshot = data["snapshot"]
    match = snapshot[snapshot["ticker"].str.upper().str.startswith(query)]
    if match.empty:
        match = snapshot[snapshot["name"].str.upper().str.contains(query)]
    if match.empty:
        await update.message.reply_text(f"No position found for '{query}'.")
        return

    r = match.iloc[0]
    price_eur = f"{r['last_price_eur']:.2f} €" if r["last_price_eur"] is not None else "n/a"
    pl_pct_str = f"{r['unrealized_pl_pct']:+.2%}" if r['unrealized_pl_pct'] is not None else "n/a"
    await update.message.reply_text(
        f"<b>{r['ticker']}</b> — {r['name']}\n"
        f"Exchange: {r['exchange']}\n"
        f"Shares: {r['shares']:.4f}\n"
        f"Average cost: {r['avg_cost_eur']:.2f} €\n"
        f"Current price: {price_eur} ({r['last_price_local']} {r['currency']})\n"
        f"Market value: {r['market_value_eur']:,.2f} €\n"
        f"P/L: {r['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})\n"
        f"Portfolio weight: {r['weight']:.2%}",
        parse_mode=ParseMode.HTML,
    )


@authorized_only
async def earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    cal = data["calendar"].dropna(subset=["next_earnings_date"]).sort_values("next_earnings_date")
    if cal.empty:
        await update.message.reply_text("No known earnings date for the stocks in the portfolio.")
        return
    lines = ["📢 <b>UPCOMING EARNINGS</b>", "<pre>"]
    for _, r in cal.iterrows():
        lines.append(f"{r['ticker']:10s} {r['next_earnings_date'].strftime('%d/%m/%Y')}  (in {int(r['days_to_earnings'])}d)")
    lines.append("</pre>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def dividends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    cal = data["calendar"].dropna(subset=["next_ex_dividend_date"]).sort_values("next_ex_dividend_date")
    if cal.empty:
        await update.message.reply_text("No known ex-dividend date for the stocks in the portfolio.")
        return
    lines = ["💶 <b>UPCOMING EX-DIVIDEND DATES</b>", "<pre>"]
    for _, r in cal.iterrows():
        lines.append(f"{r['ticker']:10s} {r['next_ex_dividend_date'].strftime('%d/%m/%Y')}")
    lines.append("</pre>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Generating the updated dashboard...")
    from dashboard import generate_dashboard_html
    data = get_monitor_data()
    path = generate_dashboard_html(data)
    with open(path, "rb") as f:
        await update.message.reply_document(f, filename="portfolio_dashboard.html",
                                            caption="📡 Updated dashboard")


def _load_last_alerts() -> dict:
    if not os.path.isfile(LAST_ALERTS_FILE):
        return {}
    with open(LAST_ALERTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_last_alerts(alerts: dict) -> None:
    with open(LAST_ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)


async def check_price_moves(context: ContextTypes.DEFAULT_TYPE):
    """
    Periodic job: compares the current price vs. the previous close for
    each stock in the portfolio, and sends a push alert if the move
    exceeds the configured threshold — at most one alert per stock per
    trading day, so it doesn't spam on every cycle if the price stays
    beyond the threshold for hours.
    """
    from holdings import load_holdings
    tickers = [p["ticker"] for p in load_holdings()["positions"]]
    today = date.today().isoformat()
    last_alerts = _load_last_alerts()

    for ticker in tickers:
        try:
            fi = yf.Ticker(ticker).fast_info
            last_price = fi.get("lastPrice")
            prev_close = fi.get("previousClose")
            if not last_price or not prev_close:
                continue
            change_pct = (last_price - prev_close) / prev_close
        except Exception:
            continue

        if abs(change_pct) < ALERT_THRESHOLD_PCT:
            continue
        if last_alerts.get(ticker) == today:
            continue

        emoji = "🚀" if change_pct > 0 else "🔻"
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"{emoji} <b>{ticker}</b> {change_pct:+.2%} today (from {prev_close:.2f} to {last_price:.2f})",
            parse_mode=ParseMode.HTML,
        )
        last_alerts[ticker] = today

    _save_last_alerts(last_alerts)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID are missing: create a .env file in the "
            "project root (see this file's docstring for how to obtain them)."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("portfolio", status))
    app.add_handler(CommandHandler("pl", pl))
    app.add_handler(CommandHandler("detail", detail))
    app.add_handler(CommandHandler("earnings", earnings))
    app.add_handler(CommandHandler("dividends", dividends))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))

    app.job_queue.run_repeating(check_price_moves, interval=ALERT_INTERVAL_MINUTES * 60, first=15)

    print("🤖 Telegram bot started, listening...")
    app.run_polling()


if __name__ == "__main__":
    main()
