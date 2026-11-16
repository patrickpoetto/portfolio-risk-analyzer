# Portfolio Risk Analyzer

A quantitative toolkit for analyzing, optimizing, and monitoring a long-term stock portfolio. It pulls historical price data for a diversified universe of tickers from Yahoo Finance, computes standard risk/return metrics (Sharpe ratio, max drawdown, VaR, volatility), builds a correlation matrix across holdings, suggests a capital-aware allocation, backtests the result against major indices, and renders everything into an interactive Plotly HTML report. A companion module tracks a real set of holdings over time and can push live price alerts to Telegram.

> Built as a personal project to apply portfolio theory (Markowitz-style diversification, risk-adjusted performance) to a real, capital-constrained investment decision, with production-style concerns (config separation, data validation, persistence, notifications) rather than a one-off notebook.

## What it does

- **Ticker universe** — a configurable set of ~40-50 equities spanning technology, healthcare, industrials, energy, financials, and materials, classified by sector and by geography.
- **Risk/return metrics** — for each security and for the portfolio as a whole: annualized return, annualized volatility, Sharpe ratio, maximum drawdown, Value at Risk (95%).
- **Correlation analysis** — full pairwise correlation matrix, with automatic flagging of highly correlated pairs and the most/least diversifying names.
- **Capital-aware allocation** — given an actual amount of capital, a selection algorithm picks how many tickers to hold and how much to allocate to each, balancing:
  - Sharpe ratio (40%)
  - marginal diversification benefit / low correlation with what's already selected (40%)
  - sector coverage bonus (20%)
  - plus a position-size cap and a "smart cash" buffer sized to the resulting portfolio's volatility.
- **Risk profiles** — conservative / moderate / aggressive presets that shift the weighting between stability and expected return.
- **Historical backtest** — simulated performance of the selected/weighted portfolio vs. benchmark indices (S&P 500, NASDAQ, MSCI World) over 1y/2y/5y/max windows.
- **Interactive HTML report** — a single self-contained Plotly dashboard: KPI cards, risk/return scatter, backtest chart, sector/geography breakdown, correlation heatmap, allocation pie + table.
- **Live portfolio tracking** — a separate ledger (shares, average cost, realized P&L) that is kept up to date via a small CLI, independent from the hypothetical/what-if allocation reports.
- **Telegram bot** — responds to chat commands with the live state of the tracked portfolio and pushes alerts when a position moves beyond a configurable daily threshold. Restricted to a single authorized chat id.
- **Ticker validation** — a standalone script to check, before adding a new ticker to the universe, that Yahoo Finance actually serves data for it.

## Architecture

The codebase is split by responsibility rather than being a single script:

```
main.py                   Entry point / CLI: orchestrates the full analysis pipeline
portfolio_config.py        Ticker universe, sector/geography classification, risk profiles
risk_analysis.py           Core metrics: returns, volatility, Sharpe, drawdown, VaR, correlation
optimization.py            Allocation optimization / Markowitz-style weighting
practical_allocation.py    Capital-aware selection: turns weights into concrete buy amounts
backtest.py                 Historical portfolio-vs-index backtesting
valuation.py                Per-ticker valuation helpers
validation.py / validate_tickers.py   Input + data-availability validation against Yahoo Finance
html_report.py              Plotly report generation (charts + layout)
fx_risk.py                   FX conversion for non-EUR positions
profiles.py                  Named "what-if" investor profiles (capital, risk, period)
holdings.py                  Real holdings ledger (buy/sell, realized P&L) - CLI
portfolio_monitor.py        Live valuation of real holdings vs. current market prices
dashboard.py                 Live dashboard (HTML) over the real holdings
telegram_bot.py              Telegram bot: status queries + threshold-based price alerts
show_allocation.py           Quick terminal-only view of the suggested allocation
quick_start.py                Minimal end-to-end demo on a small ticker subset
```

Two parallel data models run through the project, kept deliberately separate:
- **Hypothetical / what-if** (`profiles/*.json`, `portfolio_config.py`, `main.py`): "if I invested €X with risk profile Y, what allocation and metrics would I get?"
- **Real holdings** (`holdings/`, `holdings.py`, `portfolio_monitor.py`): the actual positions held, their current market value and unrealized P&L, used by the live dashboard and the Telegram bot.

Sample/demo data for both is excluded from this repository — see **Data & privacy** below.

## Tech stack

- **Python 3.8+**
- [`yfinance`](https://pypi.org/project/yfinance/) — market data retrieval from Yahoo Finance
- [`pandas`](https://pandas.pydata.org/) / [`numpy`](https://numpy.org/) — time series and numerical computation
- [`scipy`](https://scipy.org/) — optimization routines for allocation
- [`plotly`](https://plotly.com/python/) — interactive charting and HTML report generation
- [`python-telegram-bot`](https://python-telegram-bot.org/) — Telegram bot integration
- `python-dotenv` — environment-based configuration

## Getting started

```bash
# 1. Clone and enter the project
git clone https://github.com/patrickpoetto/portfolio-risk-analyzer.git
cd portfolio-risk-analyzer

# 2. Create a virtual environment and install dependencies
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. (Optional) configure the Telegram bot
cp .env.example .env
# edit .env with your own TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
```

### Run a what-if allocation report

```bash
# Default capital, auto-selects a diversified subset of tickers
python main.py

# Specify capital — the number of selected tickers scales with it
python main.py --capital 50000

# Explore the full ticker universe regardless of capital
python main.py --full-universe

# Pick a risk profile
python main.py --capital 20000 --risk aggressive

# Quick terminal-only view of the suggested allocation (no HTML report)
python show_allocation.py moderate
```

Each run produces a self-contained interactive HTML report (Plotly charts embedded, no server required to view it).

### Validate a new ticker before adding it

```bash
python validate_tickers.py
```

### Track a real portfolio

```bash
python holdings.py show
python holdings.py buy AAPL 5 150.00
python holdings.py sell AAPL 2 180.00
python dashboard.py            # generates the live HTML dashboard
python telegram_bot.py         # starts the Telegram bot (requires .env)
```

## Metrics computed

**Per security**
- Total return and annualized return
- Annualized volatility
- Sharpe ratio
- Maximum drawdown
- Value at Risk (95% confidence)

**Per portfolio**
- Capital-weighted annualized return and volatility
- Portfolio Sharpe ratio
- Diversification score (0-100)
- Sector and geographic breakdown
- Backtested performance vs. S&P 500 / NASDAQ / MSCI World

## Data & privacy

This is a public-facing copy of a personal project. The following are intentionally **not** included in this repository, even though the underlying scripts support them:

- Real investor profiles and real portfolio holdings/transactions (these contain actual personal financial data) — only a generic, non-identifying sample profile (`profiles/esempio.json`) and an empty template (`profiles/_template.json`) are kept, for reference.
- The `.env` file with live Telegram bot credentials — only `.env.example` (placeholder values) is included.
- Generated HTML reports and logs — these are build artifacts, regenerated locally on each run.

## Disclaimer

This tool is for informational and educational purposes only. It does not constitute financial advice.

## License

MIT — see [LICENSE](LICENSE).
