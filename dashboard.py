"""
LIVE monitoring dashboard for the actually held portfolio.

Unlike main.py/html_report.py (a hypothetical allocation report generated
once for a given capital/profile), this page shows the state of the real
portfolio: current market value, gain/loss per position, value over time,
upcoming earnings/dividends. It reuses the same visual theme ("Midnight
Terminal") and the same Plotly helpers as html_report.py for consistency,
instead of duplicating the styling from scratch.

Usage:
    python dashboard.py                  # refreshes and opens portfolio_dashboard.html
"""

import base64
import os
import webbrowser
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from portfolio_config import THEME_CONFIG
from html_report import _base_layout, _axis, _pct_class, CHART_COLORWAY
from portfolio_monitor import get_monitor_data

OUTPUT_FILE = "portfolio_dashboard.html"


def _fig_to_html(fig: go.Figure, div_id: str) -> str:
    """
    Rasterizes the chart into an embedded (base64) PNG instead of an
    interactive Plotly figure: Telegram doesn't open received HTML files in
    a real browser (no JS execution), so an interactive chart showed up as
    an empty box. A static image displays everywhere, even in Telegram's
    preview and offline — at the cost of losing hover/zoom. `div_id` is no
    longer needed for rendering but is kept for compatibility with
    existing call sites.
    """
    png_bytes = fig.to_image(format="png", scale=2)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{div_id}" style="width:100%; height:auto; display:block; border-radius: 8px;">'


def create_value_history_chart(value_history: pd.DataFrame) -> str:
    """
    Total market value over time, with the cost basis as a dashed
    reference line. Built from the points actually observed on each
    monitor run (holdings/value_history.json), not from a historical
    reconstruction: with a single data point it still shows today's value,
    and it fills out in shape as the monitor is re-run on subsequent days.
    """
    fig = go.Figure()

    if value_history.empty:
        fig.update_layout(_base_layout(height=350, title="Portfolio Value Over Time"))
        return _fig_to_html(fig, "chart_value_history")

    fig.add_trace(go.Scatter(
        x=value_history['date'], y=value_history['total_market_value_eur'],
        mode='lines+markers', name='Market value',
        line=dict(color=THEME_CONFIG['accent'], width=3),
        marker=dict(size=7, color=THEME_CONFIG['accent']),
        fill='tozeroy', fillcolor=THEME_CONFIG['accent_soft'],
    ))
    fig.add_trace(go.Scatter(
        x=value_history['date'], y=value_history['total_cost_basis_eur'],
        mode='lines', name='Cost basis',
        line=dict(color=THEME_CONFIG['text_secondary'], width=2, dash='dash'),
    ))

    fig.update_layout(_base_layout(
        title="Portfolio Value Over Time",
        height=420,
        xaxis=_axis(title="Date"),
        yaxis=_axis(title="EUR"),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(color=THEME_CONFIG['text_primary'])),
        margin=dict(l=60, r=30, t=60, b=50),
    ))
    return _fig_to_html(fig, "chart_value_history")


def create_pl_bar_chart(snapshot: pd.DataFrame) -> str:
    """Horizontal bars with the %gain/loss per position, green/red by sign."""
    df = snapshot.dropna(subset=['unrealized_pl_pct']).sort_values('unrealized_pl_pct')
    colors = [THEME_CONFIG['positive'] if v >= 0 else THEME_CONFIG['negative'] for v in df['unrealized_pl_pct']]

    fig = go.Figure(go.Bar(
        x=df['unrealized_pl_pct'], y=df['ticker'], orientation='h',
        marker=dict(color=colors),
        text=[f"{v:+.1%}" for v in df['unrealized_pl_pct']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Gain/loss: %{x:+.2%}<extra></extra>',
    ))
    fig.update_layout(_base_layout(
        title="Gain/Loss % per Stock",
        height=max(400, 24 * len(df)),
        xaxis=_axis(title="Gain/loss %", tickformat='+.0%'),
        yaxis=_axis(title=""),
        showlegend=False,
        margin=dict(l=90, r=60, t=60, b=40),
    ))
    return _fig_to_html(fig, "chart_pl_bar")


def create_position_pie_chart(pie_data: pd.DataFrame) -> str:
    """Per-stock allocation pie chart, interactive (see _fig_to_html)."""
    fig = px.pie(
        pie_data, values='weight', names='ticker', hole=0.4,
        color_discrete_sequence=CHART_COLORWAY,
    )
    fig.update_traces(
        textposition='outside', textinfo='label+percent', textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
    )
    fig.update_layout(_base_layout(
        title="Allocation by Stock",
        showlegend=False,
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    ))
    return _fig_to_html(fig, "chart_position_pie")


def create_positions_table(snapshot: pd.DataFrame) -> str:
    rows = []
    for _, p in snapshot.iterrows():
        price_eur = f"{p['last_price_eur']:.2f}" if pd.notna(p['last_price_eur']) else "n/a"
        value_eur = f"{p['market_value_eur']:,.2f}" if pd.notna(p['market_value_eur']) else "n/a"
        pl_eur = p['unrealized_pl_eur']
        pl_pct = p['unrealized_pl_pct']
        pl_eur_str = f"{pl_eur:+,.2f}" if pd.notna(pl_eur) else "n/a"
        pl_pct_str = f"{pl_pct:+.2%}" if pd.notna(pl_pct) else "n/a"
        pl_class = _pct_class(pl_eur) if pd.notna(pl_eur) else ""
        weight_str = f"{p['weight']:.2%}" if pd.notna(p['weight']) else "n/a"

        rows.append(f'''
        <tr>
            <td><strong>{p['ticker']}</strong></td>
            <td>{p['name']}</td>
            <td class="num">{p['shares']:.4f}</td>
            <td class="num">{p['avg_cost_eur']:.2f}</td>
            <td class="num">{price_eur}</td>
            <td class="num">{value_eur}</td>
            <td class="num {pl_class}">{pl_eur_str}</td>
            <td class="num {pl_class}">{pl_pct_str}</td>
            <td class="num">{weight_str}</td>
        </tr>''')

    return f'''
    <div class="table-scroll">
    <table class="data-table">
        <thead><tr>
            <th>Ticker</th><th>Name</th><th>Shares</th><th>Avg Price</th>
            <th>Current Price</th><th>Value (EUR)</th><th>P/L (EUR)</th><th>P/L (%)</th><th>Weight</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    </div>'''


def create_events_table(calendar_df: pd.DataFrame) -> str:
    """Upcoming earnings and dividends for the stocks in the portfolio, ordered by nearest date."""
    if calendar_df.empty:
        return "<p class='muted-note'>No calendar event available.</p>"

    df = calendar_df.copy()

    def fmt_date(d):
        return d.strftime('%d/%m/%Y') if pd.notna(d) else "n/a"

    def next_event(row):
        candidates = []
        if pd.notna(row.get('next_earnings_date')):
            candidates.append((row['next_earnings_date'], f"📢 Earnings {fmt_date(row['next_earnings_date'])}"))
        if pd.notna(row.get('next_ex_dividend_date')):
            candidates.append((row['next_ex_dividend_date'], f"💶 Ex-div {fmt_date(row['next_ex_dividend_date'])}"))
        if pd.notna(row.get('next_dividend_pay_date')):
            candidates.append((row['next_dividend_pay_date'], f"💰 Dividend payment {fmt_date(row['next_dividend_pay_date'])}"))
        if not candidates:
            return None, "No known event"
        candidates.sort(key=lambda c: c[0])
        return candidates[0][0], " · ".join(c[1] for c in candidates)

    df['_sort_date'], df['_event_str'] = zip(*df.apply(next_event, axis=1)) if not df.empty else ([], [])
    df = df.sort_values('_sort_date', na_position='last')

    rows = []
    for _, r in df.iterrows():
        highlight = ' class="highlight-row"' if pd.notna(r.get('days_to_earnings')) and r['days_to_earnings'] <= 14 else ''
        rows.append(f"<tr{highlight}><td><strong>{r['ticker']}</strong></td><td>{r['_event_str']}</td></tr>")

    return f'''
    <div class="table-scroll">
    <table class="data-table">
        <thead><tr><th>Ticker</th><th>Next Event</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    </div>'''


def generate_dashboard_html(monitor_data: dict, output_file: str = OUTPUT_FILE) -> str:
    snapshot = monitor_data['snapshot']
    totals = monitor_data['totals']
    calendar_df = monitor_data['calendar']
    value_history = monitor_data['value_history']

    T = THEME_CONFIG

    pl_class = _pct_class(totals['unrealized_pl_eur'])
    total_pl_class = _pct_class(totals['total_pl_eur'])
    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/a"

    pie_data = snapshot.dropna(subset=['weight'])[['ticker', 'weight']]
    pie_html = create_position_pie_chart(pie_data) if not pie_data.empty else ""
    pl_bar_html = create_pl_bar_chart(snapshot)
    value_history_html = create_value_history_chart(value_history)
    positions_table_html = create_positions_table(snapshot)
    events_table_html = create_events_table(calendar_df)

    failed_html = ""
    if totals['failed_tickers']:
        failed_html = f'''
        <div class="info-box info-box--warning">
            <h3>⚠️ Price unavailable</h3>
            <p>Could not download the current price for: {', '.join(totals['failed_tickers'])}</p>
        </div>'''

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="300">
        <title>Live Portfolio - {datetime.now().strftime('%d/%m/%Y %H:%M')}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: {T['font_family']};
                background:
                    radial-gradient(circle at 15% 0%, rgba(0, 217, 255, 0.08), transparent 40%),
                    radial-gradient(circle at 85% 100%, rgba(123, 97, 255, 0.08), transparent 40%),
                    {T['bg_page']};
                min-height: 100vh; padding: 24px; color: {T['text_primary']}; line-height: 1.6;
            }}
            .container {{
                max-width: 1400px; margin: 0 auto; background: {T['bg_card']};
                border: 1px solid {T['border']}; border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5); overflow: hidden;
            }}
            header {{
                background: linear-gradient(135deg, {T['bg_card_alt']} 0%, {T['bg_elevated']} 100%);
                border-bottom: 1px solid {T['border']}; padding: 44px 40px; text-align: center;
            }}
            header h1 {{
                font-size: 2.4em; margin-bottom: 10px; font-weight: 800;
                background: linear-gradient(90deg, {T['accent']}, {T['accent_2']});
                -webkit-background-clip: text; background-clip: text; color: transparent;
            }}
            header p {{ font-size: 1.05em; color: {T['text_secondary']}; font-family: {T['font_mono']}; }}
            .content {{ padding: 40px; }}
            .section {{ margin-bottom: 48px; }}
            .section h2 {{
                font-size: 1.7em; font-weight: 700; margin-bottom: 20px; padding-bottom: 12px;
                border-bottom: 2px solid {T['border']};
            }}
            .section h2::before {{ content: "▸"; color: {T['accent']}; margin-right: 10px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }}
            .stat-card {{ background: {T['bg_card_alt']}; border: 1px solid {T['border']}; padding: 24px; border-radius: 12px; }}
            .stat-card h3 {{ font-size: 0.78em; color: {T['text_secondary']}; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 10px; }}
            .stat-value {{ font-size: 2.0em; font-weight: 700; font-family: {T['font_mono']}; color: {T['text_primary']}; }}
            .stat-value.positive {{ color: {T['positive']}; }}
            .stat-value.negative {{ color: {T['negative']}; }}
            .chart-container {{ background: {T['bg_card_alt']}; border: 1px solid {T['border']}; padding: 20px; border-radius: 12px; margin-bottom: 30px; }}
            .two-col-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 48px; }}
            .table-scroll {{ overflow-x: auto; border-radius: 10px; }}
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: {T['bg_card_alt']}; border-radius: 10px; overflow: hidden; font-size: 0.95em; }}
            .data-table th {{ background: linear-gradient(135deg, {T['accent']} 0%, {T['accent_2']} 100%); color: {T['bg_page']}; padding: 13px 15px; text-align: left; font-weight: 700; text-transform: uppercase; font-size: 0.78em; letter-spacing: 0.5px; }}
            .data-table td {{ padding: 11px 15px; border-bottom: 1px solid {T['border']}; font-family: {T['font_mono']}; }}
            .data-table td:first-child, .data-table th:first-child {{ font-family: {T['font_family']}; }}
            .data-table tbody tr:nth-child(even) {{ background: rgba(255, 255, 255, 0.02); }}
            .data-table tbody tr:hover {{ background: {T['bg_elevated']}; }}
            .data-table .num {{ text-align: right; }}
            .data-table tbody tr.highlight-row {{ background: {T['warning_soft']}; border-left: 3px solid {T['warning']}; }}
            .positive {{ color: {T['positive']}; }}
            .negative {{ color: {T['negative']}; }}
            .info-box {{ background: {T['accent_soft']}; border-left: 4px solid {T['accent']}; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .info-box h3 {{ color: {T['accent']}; margin-bottom: 10px; }}
            .info-box--warning {{ background: {T['warning_soft']}; border-left-color: {T['warning']}; }}
            .info-box--warning h3 {{ color: {T['warning']}; }}
            .muted-note {{ font-size: 0.9em; color: {T['text_secondary']}; margin-bottom: 10px; }}
            footer {{ background: {T['bg_card_alt']}; border-top: 1px solid {T['border']}; padding: 24px; text-align: center; color: {T['text_secondary']}; font-size: 0.9em; }}
            @media (max-width: 768px) {{
                body {{ padding: 8px; }}
                .stats-grid {{ grid-template-columns: 1fr; gap: 10px; }}
                .stat-card {{ padding: 16px; }}
                .stat-value {{ font-size: 1.5em; }}
                .two-col-grid {{ grid-template-columns: 1fr; gap: 16px; margin-bottom: 30px; }}
                header {{ padding: 24px 16px; }}
                header h1 {{ font-size: 1.4em; }}
                header p {{ font-size: 0.85em; }}
                .content {{ padding: 14px; }}
                .section h2 {{ font-size: 1.3em; }}
                .chart-container {{ padding: 8px; }}
                .data-table th, .data-table td {{ padding: 8px 10px; font-size: 0.82em; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📡 LIVE PORTFOLIO</h1>
                <p>Updated on {datetime.now().strftime('%d/%m/%Y at %H:%M')} · refreshes itself every 5 minutes if left open</p>
            </header>
            <div class="content">
                <div class="section">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3>Market Value</h3>
                            <div class="stat-value">{totals['total_market_value_eur']:,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Cost Basis</h3>
                            <div class="stat-value">{totals['total_cost_basis_eur']:,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Unrealized Gain/Loss</h3>
                            <div class="stat-value {pl_class}">{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</div>
                        </div>
                        <div class="stat-card">
                            <h3>Realized Gain/Loss</h3>
                            <div class="stat-value {_pct_class(totals['realized_pl_eur'])}">{totals['realized_pl_eur']:+,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Total Gain/Loss</h3>
                            <div class="stat-value {total_pl_class}">{totals['total_pl_eur']:+,.2f} €</div>
                        </div>
                    </div>
                    {failed_html}
                </div>

                <div class="section">
                    <h2>Value Over Time</h2>
                    <div class="chart-container">{value_history_html}</div>
                    <p class="muted-note">One point per monitor run: re-run it periodically (or let the Telegram bot do it) to build up the day-by-day history.</p>
                </div>

                <div class="two-col-grid">
                    <div class="chart-container">{pie_html}</div>
                    <div class="chart-container">{pl_bar_html}</div>
                </div>

                <div class="section">
                    <h2>Position Detail</h2>
                    {positions_table_html}
                </div>

                <div class="section">
                    <h2>Upcoming Events (Earnings / Dividends)</h2>
                    {events_table_html}
                </div>
            </div>
            <footer>Dashboard generated automatically — market data via Yahoo Finance, may be delayed</footer>
        </div>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_template)

    return output_file


if __name__ == "__main__":
    data = get_monitor_data()
    path = generate_dashboard_html(data)
    print(f"✅ Dashboard generated: {path}")
    webbrowser.open(f"file://{os.path.abspath(path)}")
