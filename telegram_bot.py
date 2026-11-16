"""
Bot Telegram sempre attivo per il monitoraggio del portafoglio.

Risponde a comandi in chat con lo stato live del portafoglio (riusando
portfolio_monitor.py/dashboard.py, la stessa fonte dati della dashboard
HTML) e manda alert push quando un titolo si muove oltre una soglia di
variazione giornaliera. La modifica delle posizioni (acquisti/vendite)
resta volutamente fuori da qui: si fa da terminale con holdings.py, per
scelta esplicita (comando da terminale invece che via bot).

Setup (vedi anche il messaggio di benvenuto stampato all'avvio):
    1. Crea un file .env nella root del progetto (mai committato, vedi
       .gitignore) con:
           TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
           TELEGRAM_CHAT_ID=12345678
    2. python telegram_bot.py

Il bot risponde SOLO al chat_id configurato: chiunque altro scriva al bot
(anche conoscendo il suo username) riceve un rifiuto, senza vedere nessun
dato del portafoglio.
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
    """Ignora/rifiuta ogni messaggio che non arrivi dal chat_id configurato in .env."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(CHAT_ID):
            await update.message.reply_text("⛔ Non autorizzato.")
            return
        await handler(update, context)
    return wrapper


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📡 Bot di monitoraggio portafoglio attivo.\n\n"
        "Comandi disponibili:\n"
        "/status — riepilogo completo (valore, P/L, top movimenti)\n"
        "/pl — solo plus/minusvalenza totale\n"
        "/dettaglio TICKER — dettaglio di un titolo\n"
        "/utili — prossime pubblicazioni utili\n"
        "/dividendi — prossimi stacchi/pagamenti dividendo\n"
        "/dashboard — genera e invia la dashboard HTML aggiornata\n\n"
        f"Alert automatico se un titolo si muove oltre ±{ALERT_THRESHOLD_PCT:.0%} in giornata "
        f"(controllo ogni {ALERT_INTERVAL_MINUTES:.0f} minuti)."
    )


@authorized_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Aggiorno i prezzi, un attimo...")
    data = get_monitor_data()
    snapshot = data["snapshot"]
    totals = data["totals"]

    valid = snapshot.dropna(subset=["unrealized_pl_pct"]).sort_values("unrealized_pl_pct", ascending=False)
    top_gainers = valid.head(3)
    top_losers = valid.tail(3).sort_values("unrealized_pl_pct")

    def fmt_line(row):
        return f"{row['ticker']:10s} {row['unrealized_pl_pct']:+7.2%}  ({row['unrealized_pl_eur']:+,.0f} €)"

    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/d"

    lines = [
        "📊 <b>STATO PORTAFOGLIO</b>",
        "",
        f"Valore di mercato: <b>{totals['total_market_value_eur']:,.2f} €</b>",
        f"Costo di carico:   {totals['total_cost_basis_eur']:,.2f} €",
        f"P/L non realizzata: <b>{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</b>",
        f"P/L realizzata cumulata: {totals['realized_pl_eur']:+,.2f} €",
        "",
        "🟢 <b>Top 3 in guadagno</b>",
        "<pre>" + "\n".join(fmt_line(r) for _, r in top_gainers.iterrows()) + "</pre>",
        "🔴 <b>Top 3 in perdita</b>",
        "<pre>" + "\n".join(fmt_line(r) for _, r in top_losers.iterrows()) + "</pre>",
    ]
    if totals["failed_tickers"]:
        lines.append(f"⚠️ Prezzo non disponibile per: {', '.join(totals['failed_tickers'])}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def pl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    totals = data["totals"]
    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/d"
    await update.message.reply_text(
        f"P/L non realizzata: <b>{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</b>\n"
        f"P/L realizzata cumulata: {totals['realized_pl_eur']:+,.2f} €\n"
        f"P/L totale: <b>{totals['total_pl_eur']:+,.2f} €</b>",
        parse_mode=ParseMode.HTML,
    )


@authorized_only
async def dettaglio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /dettaglio TICKER (es. /dettaglio AMD)")
        return

    query = context.args[0].upper()
    data = get_monitor_data()
    snapshot = data["snapshot"]
    match = snapshot[snapshot["ticker"].str.upper().str.startswith(query)]
    if match.empty:
        match = snapshot[snapshot["name"].str.upper().str.contains(query)]
    if match.empty:
        await update.message.reply_text(f"Nessuna posizione trovata per '{query}'.")
        return

    r = match.iloc[0]
    price_eur = f"{r['last_price_eur']:.2f} €" if r["last_price_eur"] is not None else "n/d"
    pl_pct_str = f"{r['unrealized_pl_pct']:+.2%}" if r['unrealized_pl_pct'] is not None else "n/d"
    await update.message.reply_text(
        f"<b>{r['ticker']}</b> — {r['name']}\n"
        f"Borsa: {r['exchange']}\n"
        f"Azioni: {r['shares']:.4f}\n"
        f"Prezzo medio carico: {r['avg_cost_eur']:.2f} €\n"
        f"Prezzo attuale: {price_eur} ({r['last_price_local']} {r['currency']})\n"
        f"Valore di mercato: {r['market_value_eur']:,.2f} €\n"
        f"P/L: {r['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})\n"
        f"Peso in portafoglio: {r['weight']:.2%}",
        parse_mode=ParseMode.HTML,
    )


@authorized_only
async def utili(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    cal = data["calendar"].dropna(subset=["next_earnings_date"]).sort_values("next_earnings_date")
    if cal.empty:
        await update.message.reply_text("Nessuna data utili nota per i titoli in portafoglio.")
        return
    lines = ["📢 <b>PROSSIMI UTILI</b>", "<pre>"]
    for _, r in cal.iterrows():
        lines.append(f"{r['ticker']:10s} {r['next_earnings_date'].strftime('%d/%m/%Y')}  (tra {int(r['days_to_earnings'])}g)")
    lines.append("</pre>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def dividendi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_monitor_data()
    cal = data["calendar"].dropna(subset=["next_ex_dividend_date"]).sort_values("next_ex_dividend_date")
    if cal.empty:
        await update.message.reply_text("Nessuna data di stacco dividendo nota per i titoli in portafoglio.")
        return
    lines = ["💶 <b>PROSSIMI STACCHI DIVIDENDO</b>", "<pre>"]
    for _, r in cal.iterrows():
        lines.append(f"{r['ticker']:10s} {r['next_ex_dividend_date'].strftime('%d/%m/%Y')}")
    lines.append("</pre>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@authorized_only
async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Genero la dashboard aggiornata...")
    from dashboard import generate_dashboard_html
    data = get_monitor_data()
    path = generate_dashboard_html(data)
    with open(path, "rb") as f:
        await update.message.reply_document(f, filename="portfolio_dashboard.html",
                                            caption="📡 Dashboard aggiornata")


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
    Job periodico: confronta prezzo corrente vs chiusura precedente per
    ogni titolo in portafoglio, e manda un alert push se il movimento
    supera la soglia configurata — al massimo un alert per titolo per
    giorno di borsa, per non spammare ad ogni ciclo se il prezzo resta
    sopra soglia per ore.
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
            text=f"{emoji} <b>{ticker}</b> {change_pct:+.2%} oggi (da {prev_close:.2f} a {last_price:.2f})",
            parse_mode=ParseMode.HTML,
        )
        last_alerts[ticker] = today

    _save_last_alerts(last_alerts)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit(
            "Mancano TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID: crea un file .env nella root "
            "del progetto (vedi il docstring di questo file per come ottenerli)."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("portafoglio", status))
    app.add_handler(CommandHandler("pl", pl))
    app.add_handler(CommandHandler("dettaglio", dettaglio))
    app.add_handler(CommandHandler("utili", utili))
    app.add_handler(CommandHandler("dividendi", dividendi))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))

    app.job_queue.run_repeating(check_price_moves, interval=ALERT_INTERVAL_MINUTES * 60, first=15)

    print("🤖 Bot Telegram avviato, in ascolto...")
    app.run_polling()


if __name__ == "__main__":
    main()
