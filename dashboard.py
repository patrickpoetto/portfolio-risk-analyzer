"""
Dashboard di monitoraggio LIVE del portafoglio realmente detenuto.

A differenza di main.py/html_report.py (report di allocazione ipotetico
generato una tantum per un capitale/profilo dato), questa pagina mostra lo
stato del portafoglio reale: valore di mercato corrente, plus/minusvalenza
per posizione, andamento nel tempo, prossimi utili/dividendi. Riusa lo
stesso tema visivo ("Midnight Terminal") e gli stessi helper Plotly di
html_report.py per coerenza, invece di duplicare lo stile da zero.

Uso:
    python dashboard.py                  # aggiorna e apre portfolio_dashboard.html
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
    Rasterizza il grafico in un PNG incorporato (base64) invece che come
    Plotly interattivo: Telegram non apre gli HTML ricevuti in un browser
    vero (niente JS eseguito), quindi un grafico interattivo risultava un
    riquadro vuoto. Un'immagine statica si vede ovunque, anche
    nell'anteprima di Telegram e offline — al costo di perdere hover/zoom.
    `div_id` non serve più per il rendering ma resta per compatibilità
    con le chiamate esistenti.
    """
    png_bytes = fig.to_image(format="png", scale=2)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{div_id}" style="width:100%; height:auto; display:block; border-radius: 8px;">'


def create_value_history_chart(value_history: pd.DataFrame) -> str:
    """
    Andamento del valore di mercato totale nel tempo, con il costo di
    carico come riferimento tratteggiato. Costruito dai punti realmente
    osservati ad ogni esecuzione del monitor (holdings/value_history.json),
    non da una ricostruzione storica: con un solo punto disponibile mostra
    comunque il valore odierno, e si arricchisce di forma via via che il
    monitor viene rilanciato nei giorni successivi.
    """
    fig = go.Figure()

    if value_history.empty:
        fig.update_layout(_base_layout(height=350, title="Andamento Valore Portafoglio"))
        return _fig_to_html(fig, "chart_value_history")

    fig.add_trace(go.Scatter(
        x=value_history['date'], y=value_history['total_market_value_eur'],
        mode='lines+markers', name='Valore di mercato',
        line=dict(color=THEME_CONFIG['accent'], width=3),
        marker=dict(size=7, color=THEME_CONFIG['accent']),
        fill='tozeroy', fillcolor=THEME_CONFIG['accent_soft'],
    ))
    fig.add_trace(go.Scatter(
        x=value_history['date'], y=value_history['total_cost_basis_eur'],
        mode='lines', name='Costo di carico',
        line=dict(color=THEME_CONFIG['text_secondary'], width=2, dash='dash'),
    ))

    fig.update_layout(_base_layout(
        title="Andamento Valore Portafoglio",
        height=420,
        xaxis=_axis(title="Data"),
        yaxis=_axis(title="EUR"),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(color=THEME_CONFIG['text_primary'])),
        margin=dict(l=60, r=30, t=60, b=50),
    ))
    return _fig_to_html(fig, "chart_value_history")


def create_pl_bar_chart(snapshot: pd.DataFrame) -> str:
    """Barre orizzontali con la plus/minusvalenza % per posizione, verde/rosso in base al segno."""
    df = snapshot.dropna(subset=['unrealized_pl_pct']).sort_values('unrealized_pl_pct')
    colors = [THEME_CONFIG['positive'] if v >= 0 else THEME_CONFIG['negative'] for v in df['unrealized_pl_pct']]

    fig = go.Figure(go.Bar(
        x=df['unrealized_pl_pct'], y=df['ticker'], orientation='h',
        marker=dict(color=colors),
        text=[f"{v:+.1%}" for v in df['unrealized_pl_pct']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Plus/minus: %{x:+.2%}<extra></extra>',
    ))
    fig.update_layout(_base_layout(
        title="Plus/Minusvalenza % per Titolo",
        height=max(400, 24 * len(df)),
        xaxis=_axis(title="Plus/minusvalenza %", tickformat='+.0%'),
        yaxis=_axis(title=""),
        showlegend=False,
        margin=dict(l=90, r=60, t=60, b=40),
    ))
    return _fig_to_html(fig, "chart_pl_bar")


def create_position_pie_chart(pie_data: pd.DataFrame) -> str:
    """Torta allocazione per titolo, interattiva (vedi _fig_to_html)."""
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
        title="Allocazione per Titolo",
        showlegend=False,
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    ))
    return _fig_to_html(fig, "chart_position_pie")


def create_positions_table(snapshot: pd.DataFrame) -> str:
    rows = []
    for _, p in snapshot.iterrows():
        price_eur = f"{p['last_price_eur']:.2f}" if pd.notna(p['last_price_eur']) else "n/d"
        value_eur = f"{p['market_value_eur']:,.2f}" if pd.notna(p['market_value_eur']) else "n/d"
        pl_eur = p['unrealized_pl_eur']
        pl_pct = p['unrealized_pl_pct']
        pl_eur_str = f"{pl_eur:+,.2f}" if pd.notna(pl_eur) else "n/d"
        pl_pct_str = f"{pl_pct:+.2%}" if pd.notna(pl_pct) else "n/d"
        pl_class = _pct_class(pl_eur) if pd.notna(pl_eur) else ""
        weight_str = f"{p['weight']:.2%}" if pd.notna(p['weight']) else "n/d"

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
            <th>Ticker</th><th>Nome</th><th>Azioni</th><th>Prezzo Medio</th>
            <th>Prezzo Attuale</th><th>Valore (EUR)</th><th>P/L (EUR)</th><th>P/L (%)</th><th>Peso</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    </div>'''


def create_events_table(calendar_df: pd.DataFrame) -> str:
    """Prossimi utili e dividendi per i titoli in portafoglio, ordinati per data più vicina."""
    if calendar_df.empty:
        return "<p class='muted-note'>Nessun evento in calendario disponibile.</p>"

    df = calendar_df.copy()

    def fmt_date(d):
        return d.strftime('%d/%m/%Y') if pd.notna(d) else "n/d"

    def next_event(row):
        candidates = []
        if pd.notna(row.get('next_earnings_date')):
            candidates.append((row['next_earnings_date'], f"📢 Utili {fmt_date(row['next_earnings_date'])}"))
        if pd.notna(row.get('next_ex_dividend_date')):
            candidates.append((row['next_ex_dividend_date'], f"💶 Stacco div. {fmt_date(row['next_ex_dividend_date'])}"))
        if pd.notna(row.get('next_dividend_pay_date')):
            candidates.append((row['next_dividend_pay_date'], f"💰 Pagamento div. {fmt_date(row['next_dividend_pay_date'])}"))
        if not candidates:
            return None, "Nessun evento noto"
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
        <thead><tr><th>Ticker</th><th>Prossimo Evento</th></tr></thead>
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
    pl_pct_str = f"{totals['unrealized_pl_pct']:+.2%}" if totals['unrealized_pl_pct'] is not None else "n/d"

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
            <h3>⚠️ Prezzo non disponibile</h3>
            <p>Impossibile scaricare il prezzo corrente per: {', '.join(totals['failed_tickers'])}</p>
        </div>'''

    html_template = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="300">
        <title>Portafoglio Live - {datetime.now().strftime('%d/%m/%Y %H:%M')}</title>
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
                <h1>📡 PORTAFOGLIO LIVE</h1>
                <p>Aggiornato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')} · si aggiorna da solo ogni 5 minuti se lasciata aperta</p>
            </header>
            <div class="content">
                <div class="section">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3>Valore di Mercato</h3>
                            <div class="stat-value">{totals['total_market_value_eur']:,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Costo di Carico</h3>
                            <div class="stat-value">{totals['total_cost_basis_eur']:,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Plus/Minus Non Realizzata</h3>
                            <div class="stat-value {pl_class}">{totals['unrealized_pl_eur']:+,.2f} € ({pl_pct_str})</div>
                        </div>
                        <div class="stat-card">
                            <h3>Plus/Minus Realizzata</h3>
                            <div class="stat-value {_pct_class(totals['realized_pl_eur'])}">{totals['realized_pl_eur']:+,.2f} €</div>
                        </div>
                        <div class="stat-card">
                            <h3>Plus/Minus Totale</h3>
                            <div class="stat-value {total_pl_class}">{totals['total_pl_eur']:+,.2f} €</div>
                        </div>
                    </div>
                    {failed_html}
                </div>

                <div class="section">
                    <h2>Andamento nel Tempo</h2>
                    <div class="chart-container">{value_history_html}</div>
                    <p class="muted-note">Un punto per ogni esecuzione del monitor: rilancialo periodicamente (o lascialo fare al bot Telegram) per costruire lo storico giorno per giorno.</p>
                </div>

                <div class="two-col-grid">
                    <div class="chart-container">{pie_html}</div>
                    <div class="chart-container">{pl_bar_html}</div>
                </div>

                <div class="section">
                    <h2>Posizioni Dettagliate</h2>
                    {positions_table_html}
                </div>

                <div class="section">
                    <h2>Prossimi Eventi (Utili / Dividendi)</h2>
                    {events_table_html}
                </div>
            </div>
            <footer>Dashboard generata automaticamente — dati di mercato via Yahoo Finance, possono avere ritardo</footer>
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
    print(f"✅ Dashboard generata: {path}")
    webbrowser.open(f"file://{os.path.abspath(path)}")
