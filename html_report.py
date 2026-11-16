"""
Generatore di report HTML con grafici interattivi
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict
from portfolio_config import (
    REPORT_CONFIG, CORRELATION_CONFIG, ALLOCATION_CONFIG, PORTFOLIO_TICKERS, THEME_CONFIG
)

# --- Helper di tema condivisi da tutti i grafici Plotly ("Midnight Terminal") ---

CHART_COLORWAY = THEME_CONFIG['qualitative_palette']


def _base_layout(**overrides) -> dict:
    """Layout Plotly comune: sfondi scuri, font chiaro, griglie sottili bianche."""
    layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor=THEME_CONFIG['bg_card_alt'],
        font=dict(color=THEME_CONFIG['text_primary'], family=THEME_CONFIG['font_family']),
        colorway=CHART_COLORWAY,
        title_font=dict(color=THEME_CONFIG['text_primary'], size=18),
        legend=dict(font=dict(color=THEME_CONFIG['text_primary'])),
    )
    layout.update(overrides)
    return layout


def _axis(**overrides) -> dict:
    """Stile assegnato agli assi cartesiani (griglie bianche sottili su sfondo scuro)."""
    axis = dict(
        gridcolor=THEME_CONFIG['grid'],
        zerolinecolor=THEME_CONFIG['grid'],
        linecolor=THEME_CONFIG['border'],
        color=THEME_CONFIG['text_secondary'],
    )
    axis.update(overrides)
    return axis


def _pct_class(value: float) -> str:
    """Classe CSS 'positive'/'negative' in base al segno, per colorare valori nelle tabelle."""
    if value > 0:
        return 'positive'
    if value < 0:
        return 'negative'
    return ''


def create_pie_chart(data: pd.DataFrame, values_col: str, names_col: str,
                     title: str, color_scheme: str = None) -> str:
    """Crea un grafico a torta interattivo con labels eleganti fuori"""
    fig = px.pie(
        data,
        values=values_col,
        names=names_col,
        title=title,
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4  # Donut chart
    )

    # Labels eleganti fuori dalle fette con linee
    fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        pull=[0.05 if i < 3 else 0 for i in range(len(data))],  # Pull out top 3
        hovertemplate='<b>%{label}</b><br>Percentuale: %{percent}<br>Valore: %{value:.2%}<extra></extra>',
        insidetextorientation='horizontal'
    )

    fig.update_layout(_base_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font=dict(size=10, color=THEME_CONFIG['text_primary'])
        ),
        height=550,
        font=dict(size=12, color=THEME_CONFIG['text_primary'], family=THEME_CONFIG['font_family']),
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=150, t=60, b=20)  # Più spazio a destra per labels
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id=f"chart_{title.replace(' ', '_')}", config={'responsive': True})


def create_bar_chart(data: pd.DataFrame, x_col: str, y_col: str,
                     title: str, color_col: str = None) -> str:
    """Crea un grafico a barre"""

    if color_col:
        fig = px.bar(
            data,
            x=x_col,
            y=y_col,
            color=color_col,
            title=title,
            text=y_col,
            color_discrete_sequence=CHART_COLORWAY
        )
    else:
        fig = px.bar(
            data,
            x=x_col,
            y=y_col,
            title=title,
            text=y_col,
            color=y_col,
            color_continuous_scale='Teal'
        )

    fig.update_traces(
        texttemplate='%{text:.2%}',
        textposition='outside'
    )

    fig.update_layout(_base_layout(
        showlegend=False,
        height=500,
        xaxis=_axis(tickangle=-45),
        yaxis=_axis(),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id=f"chart_{title.replace(' ', '_')}", config={'responsive': True})


def create_scatter_risk_return(metrics: pd.DataFrame) -> str:
    """Crea scatter plot rischio-rendimento"""
    
    if metrics.empty:
        return "<p>Dati insufficienti per generare il grafico rischio-rendimento</p>"
    
    # Crea il grafico usando graph_objects per più controllo
    fig = go.Figure()
    
    # Dimensione bolle basata su peso o uniforme
    if 'weight' in metrics.columns and metrics['weight'].sum() > 0:
        sizes = metrics['weight'] * 500 + 15
    else:
        sizes = [30] * len(metrics)
    
    # Aggiungi scatter plot
    fig.add_trace(go.Scatter(
        x=metrics['annual_volatility'],
        y=metrics['annual_return'],
        mode='markers+text',
        marker=dict(
            size=sizes,
            color=metrics['sharpe_ratio'],
            colorscale=[[0, THEME_CONFIG['negative']], [0.5, THEME_CONFIG['warning']], [1, THEME_CONFIG['positive']]],
            showscale=True,
            colorbar=dict(title="Sharpe Ratio", tickfont=dict(color=THEME_CONFIG['text_primary']),
                         title_font=dict(color=THEME_CONFIG['text_primary'])),
            line=dict(width=1, color=THEME_CONFIG['bg_card'])
        ),
        text=metrics['ticker'],
        textposition='top center',
        textfont=dict(size=9, color=THEME_CONFIG['text_primary']),
        hovertemplate='<b>%{text}</b><br>' +
                      'Rendimento: %{y:.2%}<br>' +
                      'Volatilità: %{x:.2%}<br>' +
                      'Sharpe: %{marker.color:.2f}<extra></extra>',
        name=''
    ))

    fig.update_layout(_base_layout(
        title='Analisi Rischio-Rendimento',
        height=600,
        xaxis_title='Volatilità Annuale (Rischio)',
        yaxis_title='Rendimento Annuale Atteso',
        xaxis=_axis(tickformat='.1%'),
        yaxis=_axis(tickformat='.1%'),
        showlegend=False
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="risk_return_scatter", config={'responsive': True})


def create_correlation_heatmap(corr_matrix: pd.DataFrame, top_n: int = 25) -> str:
    """Crea heatmap delle correlazioni"""
    
    if corr_matrix.empty or len(corr_matrix) < 2:
        return "<p>Dati insufficienti per generare la matrice di correlazione</p>"
    
    # Limita a top N ticker per leggibilità
    if len(corr_matrix) > top_n:
        # Seleziona i ticker con maggiore varianza di correlazione
        variances = corr_matrix.var().sort_values(ascending=False)
        top_tickers = variances.head(top_n).index
        corr_matrix = corr_matrix.loc[top_tickers, top_tickers]
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns.tolist(),
        y=corr_matrix.index.tolist(),
        colorscale=[[0, THEME_CONFIG['negative']], [0.5, THEME_CONFIG['bg_card_alt']], [1, THEME_CONFIG['accent']]],
        zmid=0,
        text=np.round(corr_matrix.values, 2),
        texttemplate='%{text}',
        textfont={"size": 8, "color": THEME_CONFIG['text_primary']},
        colorbar=dict(title="Correlazione", tickfont=dict(color=THEME_CONFIG['text_primary']),
                     title_font=dict(color=THEME_CONFIG['text_primary'])),
        hovertemplate='%{x} vs %{y}<br>Correlazione: %{z:.2f}<extra></extra>'
    ))

    fig.update_layout(_base_layout(
        title=f'Matrice di Correlazione (Top {len(corr_matrix)} Titoli)',
        height=700,
        xaxis=_axis(tickangle=-45),
        yaxis=_axis(tickangle=0),
        margin=dict(l=100, r=50, t=80, b=100)
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="correlation_heatmap", config={'responsive': True})


def create_top_performers_chart(metrics: pd.DataFrame, metric: str, 
                                top_n: int = 10, ascending: bool = False) -> str:
    """Crea grafico dei top performer per una metrica"""
    
    df_sorted = metrics.sort_values(metric, ascending=ascending).head(top_n)
    
    metric_labels = {
        'annual_return': 'Rendimento Annuale',
        'sharpe_ratio': 'Sharpe Ratio',
        'annual_volatility': 'Volatilità Annuale',
        'max_drawdown': 'Max Drawdown'
    }
    
    title = f'Top {top_n} - {metric_labels.get(metric, metric)}'
    
    # Colore basato su valore positivo/negativo
    colors = [THEME_CONFIG['positive'] if x > 0 else THEME_CONFIG['negative'] for x in df_sorted[metric]]

    fig = go.Figure(data=[
        go.Bar(
            x=df_sorted[metric],
            y=df_sorted['ticker'],
            orientation='h',
            marker=dict(color=colors),
            text=df_sorted[metric],
            texttemplate='%{text:.2%}' if metric != 'sharpe_ratio' else '%{text:.2f}',
            textposition='outside',
            textfont=dict(color=THEME_CONFIG['text_primary']),
        )
    ])

    fig.update_layout(_base_layout(
        title=title,
        xaxis_title=metric_labels.get(metric, metric),
        yaxis_title='Ticker',
        height=max(400, top_n * 40),
        showlegend=False,
        xaxis=_axis(),
        yaxis=_axis(),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id=f"top_{metric}", config={'responsive': True})


def create_optimal_allocation_pie(suggested_weights: Dict[str, float], top_n: int = 15) -> str:
    """Crea grafico a torta per allocazione ottimale suggerita"""
    
    if not suggested_weights:
        return "<p>Nessuna allocazione suggerita disponibile</p>"
    
    # Converti in DataFrame e ordina
    df = pd.DataFrame(list(suggested_weights.items()), columns=['Ticker', 'Peso'])
    df = df.sort_values('Peso', ascending=False)
    
    # Prendi top N e aggrega il resto in "Altri"
    if len(df) > top_n:
        top_df = df.head(top_n).copy()
        others_weight = df.iloc[top_n:]['Peso'].sum()
        if others_weight > 0:
            others_row = pd.DataFrame([['Altri', others_weight]], columns=['Ticker', 'Peso'])
            df = pd.concat([top_df, others_row], ignore_index=True)
    
    fig = px.pie(
        df,
        values='Peso',
        names='Ticker',
        title='Allocazione Ottimale Suggerita',
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4
    )

    # Labels eleganti fuori
    fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        pull=[0.08, 0.05, 0.03] + [0] * (len(df) - 3),  # Pull out top 3
        hovertemplate='<b>%{label}</b><br>Peso suggerito: %{percent}<br>Valore: %{value:.2%}<extra></extra>',
        insidetextorientation='horizontal'
    )

    fig.update_layout(_base_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font=dict(size=10, color=THEME_CONFIG['text_primary'])
        ),
        height=600,
        font=dict(size=12, color=THEME_CONFIG['text_primary'], family=THEME_CONFIG['font_family']),
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=150, t=80, b=20)
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="optimal_allocation_pie", config={'responsive': True})


def create_diversification_curve_chart(curve: list, chosen_n: int) -> str:
    """
    Grafico della curva di diversificazione reale: volatilità di un
    portafoglio equipesato al crescere del numero di titoli (ordinati per
    Sharpe decrescente), con il punto scelto evidenziato. Rende visibile il
    principio (Evans & Archer 1968 / Elton & Gruber 1977) su cui si basa il
    numero di titoli effettivamente selezionato.
    """
    if not curve:
        return "<p>Dati insufficienti per la curva di diversificazione</p>"

    ns = [p['n'] for p in curve]
    vols = [p['volatility'] for p in curve]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ns, y=vols, mode='lines+markers',
        line=dict(color=THEME_CONFIG['accent'], width=3),
        marker=dict(size=5, color=THEME_CONFIG['accent']),
        hovertemplate='N=%{x} titoli<br>Volatilità: %{y:.2%}<extra></extra>',
        name='Volatilità portafoglio equipesato'
    ))

    if chosen_n and chosen_n <= len(curve):
        chosen_vol = curve[chosen_n - 1]['volatility']
        fig.add_trace(go.Scatter(
            x=[chosen_n], y=[chosen_vol], mode='markers',
            marker=dict(size=14, color=THEME_CONFIG['positive'], symbol='star',
                       line=dict(width=2, color=THEME_CONFIG['bg_card'])),
            hovertemplate=f'N scelto = {chosen_n}<br>Volatilità: %{{y:.2%}}<extra></extra>',
            name='N scelto'
        ))

    fig.update_layout(_base_layout(
        title='Curva di Diversificazione Reale: Volatilità vs Numero di Titoli',
        xaxis_title='Numero di titoli (ordinati per Sharpe decrescente)',
        yaxis_title='Volatilità annualizzata (equipesata)',
        height=450,
        xaxis=_axis(),
        yaxis=_axis(tickformat='.0%'),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(color=THEME_CONFIG['text_primary'])),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="diversification_curve", config={'responsive': True})


def create_allocation_comparison(current_weights: Dict[str, float],
                                suggested_weights: Dict[str, float]) -> str:
    """Confronta allocazione corrente vs suggerita"""
    
    tickers = list(set(list(current_weights.keys()) + list(suggested_weights.keys())))
    
    current = [current_weights.get(t, 0) for t in tickers]
    suggested = [suggested_weights.get(t, 0) for t in tickers]
    
    # Ordina per peso suggerito
    sorted_indices = sorted(range(len(suggested)), key=lambda i: suggested[i], reverse=True)
    tickers = [tickers[i] for i in sorted_indices]
    current = [current[i] for i in sorted_indices]
    suggested = [suggested[i] for i in sorted_indices]
    
    # Mostra solo i top 20 per leggibilità
    if len(tickers) > 20:
        tickers = tickers[:20]
        current = current[:20]
        suggested = suggested[:20]
    
    fig = go.Figure(data=[
        go.Bar(name='Allocazione Corrente', x=tickers, y=current, marker_color=THEME_CONFIG['text_secondary']),
        go.Bar(name='Allocazione Suggerita', x=tickers, y=suggested, marker_color=THEME_CONFIG['accent'])
    ])

    fig.update_layout(_base_layout(
        title='Confronto Allocazione: Corrente vs Suggerita',
        xaxis_title='Ticker',
        yaxis_title='Peso nel Portafoglio',
        barmode='group',
        height=500,
        xaxis=_axis(tickangle=-45),
        yaxis=_axis(tickformat='.0%'),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="allocation_comparison", config={'responsive': True})


def create_backtest_chart(backtest_results: pd.DataFrame,
                         backtest_stats: Dict,
                         oos_start_date=None) -> str:
    """Crea grafico performance storica con confronto benchmark"""

    if backtest_results.empty:
        return "<p>Dati insufficienti per il backtest</p>"
    
    fig = go.Figure()
    
    # Definisci colori vivaci e spessori per ogni linea (Portafoglio in ciano
    # elettrico, più spesso, per farlo risaltare rispetto ai benchmark)
    colors = {
        'Portafoglio': THEME_CONFIG['accent'],
        'S&P 500': THEME_CONFIG['accent_2'],
        'NASDAQ': THEME_CONFIG['warning'],
        'MSCI World': THEME_CONFIG['positive'],
        'VT': '#ff6b9d',
        'VT (Total World)': '#ff6b9d'
    }

    widths = {
        'Portafoglio': 4,
        'S&P 500': 2,
        'NASDAQ': 2,
        'MSCI World': 2,
        'VT': 2,
        'VT (Total World)': 2
    }

    # Aggiungi ogni serie
    for col in backtest_results.columns:
        fig.add_trace(go.Scatter(
            x=backtest_results.index,
            y=backtest_results[col],
            mode='lines',
            name=col,
            line=dict(
                color=colors.get(col, THEME_CONFIG['text_secondary']),
                width=widths.get(col, 2)
            ),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Data: %{x|%d/%m/%Y}<br>' +
                         'Valore: %{y:.2f}<br>' +
                         '<extra></extra>'
        ))

    # Marca la finestra out-of-sample: a sinistra della linea i dati sono
    # in-sample (hanno influenzato scouting/selezione/pesi), a destra sono
    # il test onesto mai visto da quelle fasi.
    # Nota: passiamo le date come stringhe (non pd.Timestamp) perché add_vline/
    # add_vrect con Timestamp scatenano un'aritmetica interna di Plotly
    # incompatibile con le versioni recenti di pandas.
    if oos_start_date is not None and backtest_results.index[0] <= oos_start_date <= backtest_results.index[-1]:
        oos_start_str = oos_start_date.strftime('%Y-%m-%d')
        oos_end_str = backtest_results.index[-1].strftime('%Y-%m-%d')
        fig.add_vrect(
            x0=oos_start_str, x1=oos_end_str,
            fillcolor=THEME_CONFIG['accent_2'], opacity=0.12, line_width=0
        )
        # Nota: add_vline con i parametri di comodo annotation_text/
        # annotation_position scatena un bug interno di Plotly 6.x sugli assi
        # temporali (TypeError int+str). Aggiungiamo linea e annotazione come
        # due chiamate separate per evitarlo.
        fig.add_vline(x=oos_start_str, line_width=2, line_dash="dash", line_color=THEME_CONFIG['accent_2'])
        fig.add_annotation(
            x=oos_start_str, y=1, yref="paper", yanchor="bottom",
            text="Inizio Out-of-Sample", showarrow=False,
            font=dict(color=THEME_CONFIG['accent_2'], size=11)
        )

    fig.update_layout(_base_layout(
        title='Performance Storica: Portafoglio vs Benchmark',
        xaxis_title='Data',
        yaxis_title='Valore Investimento (Base 100)',
        height=600,
        hovermode='x unified',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor=THEME_CONFIG['bg_card'],
            bordercolor=THEME_CONFIG['border'],
            borderwidth=1,
            font=dict(color=THEME_CONFIG['text_primary'])
        ),
        xaxis=_axis(),
        yaxis=_axis(),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="backtest_chart", config={'responsive': True})


def create_oos_comparison_table(backtest_stats: Dict, backtest_stats_oos: Dict) -> str:
    """
    Tabella di confronto tra le statistiche sull'intero periodo (in-sample,
    include i dati usati per scegliere i titoli) e quelle sulla sola finestra
    out-of-sample (mai vista da scouting/selezione/ottimizzazione).

    Il numero "onesto" per giudicare la selezione è quello Out-of-Sample: è
    normale (e atteso) che sia più basso di quello sul periodo intero.
    """
    if not backtest_stats_oos:
        return ""

    rows = ""
    for name in backtest_stats.keys():
        full = backtest_stats.get(name, {})
        oos = backtest_stats_oos.get(name, {})
        if not oos:
            continue
        rows += f'''
        <tr>
            <td><strong>{name}</strong></td>
            <td class="num">{full.get('total_return', 0):.1%}</td>
            <td class="num accent-2"><strong>{oos.get('total_return', 0):.1%}</strong></td>
            <td class="num">{oos.get('sharpe_ratio', 0):.2f}</td>
            <td class="num negative">{oos.get('max_drawdown', 0):.1%}</td>
        </tr>
        '''

    if not rows:
        return ""

    return f'''
    <div class="info-box info-box--accent2">
        <h3>🔍 Periodo Intero vs Out-of-Sample: perché la differenza conta</h3>
        <p>I titoli sono stati scelti perché avevano il miglior punteggio storico <strong>nella finestra
        usata per la selezione</strong>. Il rendimento sul "Periodo Intero" include quindi gli stessi dati
        usati per sceglierli, ed è sistematicamente ottimistico. La colonna <strong>"Solo Out-of-Sample"</strong>
        misura invece la performance <strong>su dati mai visti</strong> da scouting, selezione smart e
        ottimizzazione dei pesi: è il numero più onesto per giudicare se la selezione ha un valore predittivo reale.</p>
    </div>
    <div class="table-scroll">
    <table class="data-table data-table--accent2">
    <thead>
        <tr>
            <th>Serie</th>
            <th class="num">Rend. Periodo Intero</th>
            <th class="num">Rend. Solo Out-of-Sample</th>
            <th class="num">Sharpe OOS</th>
            <th class="num">Max DD OOS</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
    </table>
    </div>
    '''


def create_validation_section(walk_forward_stats: Dict, opt_info: Dict, currency_risk_info: Dict) -> str:
    """
    Sezione di validazione statistica: metodologia di ottimizzazione
    (shrinkage + solver vero), risultati walk-forward multi-fold con
    intervalli di confidenza bootstrap confrontati con benchmark
    (equal-weight, minimum-variance naive), e disclosure del rischio di
    cambio non coperto.
    """
    html = '<div class="validation-section">'

    if opt_info:
        html += f'''
        <div class="info-box info-box--accent2">
            <h3>⚙️ Metodologia di Ottimizzazione</h3>
            <p>I pesi non sono più un punteggio euristico: sono la soluzione di un vero problema di ottimizzazione
            di Markowitz (solver SLSQP vincolato), con obiettivo <strong>{opt_info['objective']}</strong> per il
            profilo di rischio selezionato.</p>
            <ul>
                <li><strong>Shrinkage rendimenti attesi:</strong> {opt_info['return_shrinkage']:.0%} verso la media
                dell'universo (i rendimenti storici trailing sono stime rumorose; usarli grezzi premia gli outlier
                del campione osservato)</li>
                <li><strong>Shrinkage covarianza:</strong> {opt_info['cov_shrinkage']:.0%} verso il target a
                correlazione costante (stile Ledoit &amp; Wolf 2004; la matrice campionaria pura su poche
                centinaia di osservazioni è mal condizionata)</li>
            </ul>
        </div>
        '''

    if walk_forward_stats:
        rows = ""
        for name, stats in walk_forward_stats.items():
            if not stats:
                continue
            rows += f'''
            <tr>
                <td><strong>{name}</strong></td>
                <td class="num {_pct_class(stats['total_return'])}">{stats['total_return']:+.1%}</td>
                <td class="num">{stats['sharpe_ratio']:.2f}</td>
                <td class="num">[{stats['sharpe_ci_low']:.2f}, {stats['sharpe_ci_high']:.2f}]</td>
                <td class="num negative">{stats['max_drawdown']:.1%}</td>
            </tr>
            '''
        html += f'''
        <div class="info-box info-box--accent2">
            <h3>🔬 Validazione Walk-Forward (multi-fold, fuori campione)</h3>
            <p>Invece di un singolo split in-sample/out-of-sample, i pesi vengono ri-stimati più volte su finestre
            di training progressive e testati SOLO sul periodo immediatamente successivo, mai visto durante la
            stima (nessun look-ahead). Include un costo di transazione sul turnover ad ogni ribilanciamento.
            L'intervallo (Sharpe CI 90%) è ottenuto con block-bootstrap: se include lo zero, la performance non è
            statisticamente distinguibile dal rumore.</p>
        </div>
        <div class="table-scroll">
        <table class="data-table data-table--accent2">
        <thead>
            <tr>
                <th>Strategia</th>
                <th class="num">Rend. Totale OOS</th>
                <th class="num">Sharpe</th>
                <th class="num">Sharpe CI 90%</th>
                <th class="num">Max Drawdown</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
        </table>
        </div>
        '''

    if currency_risk_info and currency_risk_info.get('non_base_exposure', 0) > 0:
        exp_rows = ""
        for cur, exp in sorted(currency_risk_info['exposure_by_currency'].items(), key=lambda x: -x[1]):
            if cur == 'EUR' or exp <= 0:
                continue
            vol = currency_risk_info['fx_volatility_by_currency'].get(cur)
            vol_str = f"{vol:.1%}" if vol is not None else "n/d"
            exp_rows += f'''
            <tr>
                <td><strong>{cur}</strong></td>
                <td class="num">{exp:.1%}</td>
                <td class="num">{vol_str}</td>
            </tr>
            '''
        html += f'''
        <div class="info-box info-box--warning">
            <h3>💱 Rischio di Cambio (base EUR, non coperto)</h3>
            <p>Il resto del report calcola rendimento/rischio in valuta locale di ciascun titolo. Un investitore
            con capitale in EUR che tiene titoli in altre valute sopporta anche un rischio di cambio non
            modellato altrove: quantificato qui a parte, come approssimazione al primo ordine (non tiene conto
            delle correlazioni tra valute o tra valuta ed equity).</p>
            <div class="table-scroll">
            <table class="data-table data-table--compact">
            <thead><tr><th>Valuta</th><th class="num">% Portafoglio</th><th class="num">Volatilità FX annua</th></tr></thead>
            <tbody>{exp_rows}</tbody>
            </table>
            </div>
            <p class="muted-note" style="margin-top: 10px;">Esposizione totale non-EUR:
            <strong>{currency_risk_info['non_base_exposure']:.1%}</strong> — contributo di volatilità stimato:
            <strong>{currency_risk_info['estimated_fx_volatility_contribution']:.2%}</strong></p>
        </div>
        '''

    html += '</div>'
    return html


def create_correlation_analysis_section(correlation_matrix: pd.DataFrame,
                                       metrics: pd.DataFrame = None,
                                       threshold: float = None) -> str:
    """Crea sezione HTML con analisi dettagliata delle correlazioni"""
    
    if threshold is None:
        threshold = CORRELATION_CONFIG['high_correlation_threshold']
    
    if correlation_matrix.empty:
        return "<p>Dati insufficienti per l'analisi delle correlazioni</p>"
    
    # Trova coppie problematiche
    high_corr = []
    for i in range(len(correlation_matrix.columns)):
        for j in range(i+1, len(correlation_matrix.columns)):
            corr_value = correlation_matrix.iloc[i, j]
            if corr_value >= threshold:
                high_corr.append({
                    'ticker1': correlation_matrix.columns[i],
                    'ticker2': correlation_matrix.columns[j],
                    'correlation': corr_value
                })
    
    high_corr_df = pd.DataFrame(high_corr).sort_values('correlation', ascending=False) if high_corr else pd.DataFrame()
    
    # Calcola correlazioni medie
    avg_corr = correlation_matrix.mean().sort_values(ascending=False)
    
    # Titoli più correlati (problematici)
    most_corr = avg_corr.head(10)
    # Titoli meno correlati (buoni)
    least_corr = avg_corr.tail(10)
    
    html = '<div class="correlation-analysis">'

    # Box di riepilogo
    total_pairs = len(correlation_matrix) * (len(correlation_matrix) - 1) // 2
    high_pairs = len(high_corr_df)

    if high_pairs > 10:
        alert_icon = "⚠️"
        alert_msg = f"ATTENZIONE: {high_pairs} coppie con correlazione >{threshold:.0%}"
        alert_class = "info-box--danger"
    elif high_pairs > 0:
        alert_icon = "⚠️"
        alert_msg = f"{high_pairs} coppie con correlazione >{threshold:.0%} - Migliorabile"
        alert_class = "info-box--warning"
    else:
        alert_icon = "✅"
        alert_msg = "Ottima diversificazione! Nessuna coppia con correlazione eccessiva"
        alert_class = "info-box--success"

    html += f'''
    <div class="info-box {alert_class}">
        <h3>{alert_icon} {alert_msg}</h3>
        <p style="margin-top: 10px;">
            Su {total_pairs} coppie possibili, {high_pairs} hanno correlazione superiore al {threshold:.0%}.
            {'Una correlazione alta significa che i titoli si muovono insieme, riducendo la diversificazione reale.' if high_pairs > 0 else ''}
        </p>
    </div>
    '''

    # Tabella coppie problematiche
    if not high_corr_df.empty:
        html += '''
        <h3 class="section-subtitle negative">🔴 Coppie con Correlazione Alta</h3>
        <div class="table-scroll">
        <table class="data-table data-table--danger">
        <thead>
            <tr>
                <th>#</th>
                <th>Ticker 1</th>
                <th>Ticker 2</th>
                <th class="num">Correlazione</th>
                <th>Azione Suggerita</th>
            </tr>
        </thead>
        <tbody>
        '''

        for idx, row in high_corr_df.head(15).iterrows():
            html += f'''
            <tr>
                <td>{idx + 1}</td>
                <td><strong>{row['ticker1']}</strong></td>
                <td><strong>{row['ticker2']}</strong></td>
                <td class="num negative"><strong>{row['correlation']:.1%}</strong></td>
                <td style="font-size: 0.9em;">Considera di ridurre o eliminare uno dei due</td>
            </tr>
            '''

        html += '</tbody></table></div>'

    # Due colonne: titoli più/meno correlati
    html += '''
    <div class="two-col-grid">
        <div>
            <h3 class="section-subtitle negative">📉 Titoli PIÙ Correlati</h3>
            <p class="muted-note">Candidati da ridurre per migliorare diversificazione</p>
            <table class="data-table data-table--compact">
    '''

    for ticker, corr in most_corr.items():
        html += f'''
        <tr>
            <td><strong>{ticker}</strong></td>
            <td class="num negative">{corr:.1%}</td>
        </tr>
        '''

    html += '''
            </table>
        </div>
        <div>
            <h3 class="section-subtitle positive">📈 Titoli MENO Correlati</h3>
            <p class="muted-note">Migliori per diversificazione - considera di aumentare</p>
            <table class="data-table data-table--compact">
    '''

    for ticker, corr in least_corr.items():
        html += f'''
        <tr>
            <td><strong>{ticker}</strong></td>
            <td class="num positive">{corr:.1%}</td>
        </tr>
        '''

    html += '''
            </table>
        </div>
    </div>
    '''

    html += '</div>'
    return html


def create_allocation_table(suggested_weights: Dict[str, float], 
                           metrics: pd.DataFrame = None) -> str:
    """Crea una tabella HTML elegante per l'allocazione ottimale"""
    
    if not suggested_weights:
        return "<p>Nessuna allocazione disponibile</p>"
    
    # Converti in DataFrame
    df = pd.DataFrame(list(suggested_weights.items()), columns=['Ticker', 'Peso Suggerito'])
    df = df.sort_values('Peso Suggerito', ascending=False)
    
    # Aggiungi metriche se disponibili
    if metrics is not None and not metrics.empty:
        metrics_dict = metrics.set_index('ticker')[['annual_return', 'annual_volatility', 'sharpe_ratio']].to_dict('index')
        
        df['Rendimento'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('annual_return', 0))
        df['Volatilità'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('annual_volatility', 0))
        df['Sharpe'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('sharpe_ratio', 0))
    
    # Formatta le percentuali
    df['Peso %'] = (df['Peso Suggerito'] * 100).apply(lambda x: f'{x:.2f}%')
    
    # Crea HTML
    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>#</th>'
    html += '<th>Ticker</th>'
    html += '<th class="num">Peso Suggerito</th>'

    if metrics is not None and not metrics.empty:
        html += '<th class="num">Rendimento</th>'
        html += '<th class="num">Volatilità</th>'
        html += '<th class="num">Sharpe</th>'

    html += '</tr></thead><tbody>'

    for idx, row in df.iterrows():
        html += '<tr>'
        html += f'<td>{idx + 1}</td>'
        html += f'<td><strong>{row["Ticker"]}</strong></td>'
        html += f'<td class="num accent"><strong>{row["Peso %"]}</strong></td>'

        if metrics is not None and not metrics.empty:
            html += f'<td class="num {_pct_class(row["Rendimento"])}">{row["Rendimento"]:.2%}</td>'
            html += f'<td class="num">{row["Volatilità"]:.2%}</td>'
            html += f'<td class="num"><strong>{row["Sharpe"]:.2f}</strong></td>'

        html += '</tr>'

    html += '</tbody></table></div>'

    return html


def create_earnings_table(earnings_df: pd.DataFrame) -> str:
    """
    Crea tabella HTML dedicata agli utili dei titoli in portafoglio: EPS
    trailing/forward, crescita utili, margine, e prossima data di
    pubblicazione con stima di consensus (EPS/ricavi attesi).

    Ordinata per prossimità della prossima pubblicazione (i titoli con
    dato mancante, tipicamente esteri fuori copertura Yahoo, in fondo).
    """
    if earnings_df is None or earnings_df.empty:
        return "<p>Dati utili non disponibili</p>"

    df = earnings_df.copy()

    def fmt_eps(row, col):
        val = row.get(col)
        if pd.isna(val):
            return 'n/d'
        cur = row.get('currency') if pd.notna(row.get('currency')) else ''
        return f"{val:.2f} {cur}".strip()

    def fmt_pct(val):
        return f'{val:+.1%}' if pd.notna(val) else 'n/d'

    def fmt_date(row):
        d = row.get('next_earnings_date')
        if pd.isna(d) or d is None:
            return 'n/d'
        days = row.get('days_to_earnings')
        days_str = f' ({int(days)}g)' if pd.notna(days) else ''
        return f'{d}{days_str}'

    def fmt_revenue(val):
        if pd.isna(val):
            return 'n/d'
        if val >= 1e9:
            return f'{val / 1e9:.2f} Mld'
        if val >= 1e6:
            return f'{val / 1e6:.1f} Mln'
        return f'{val:,.0f}'

    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>Ticker</th>'
    html += '<th class="num">EPS (trailing)</th>'
    html += '<th class="num">EPS (forward)</th>'
    html += '<th class="num">Crescita Utili YoY</th>'
    html += '<th class="num">Margine Netto</th>'
    html += '<th>Prossima Pubblicazione</th>'
    html += '<th class="num">EPS Atteso (consensus)</th>'
    html += '<th class="num">Ricavi Attesi (consensus)</th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        growth = row.get('earnings_growth')
        growth_class = _pct_class(growth) if pd.notna(growth) else ''
        soon = pd.notna(row.get('days_to_earnings')) and row['days_to_earnings'] <= 14
        row_class = ' class="highlight-row"' if soon else ''

        html += f'<tr{row_class}>'
        html += f'<td><strong>{row["ticker"]}</strong></td>'
        html += f'<td class="num">{fmt_eps(row, "trailing_eps")}</td>'
        html += f'<td class="num">{fmt_eps(row, "forward_eps")}</td>'
        html += f'<td class="num {growth_class}">{fmt_pct(growth)}</td>'
        html += f'<td class="num">{fmt_pct(row.get("profit_margin"))}</td>'
        html += f'<td>{fmt_date(row)}</td>'
        html += f'<td class="num">{fmt_eps(row, "eps_estimate")}</td>'
        html += f'<td class="num">{fmt_revenue(row.get("revenue_estimate"))}</td>'
        html += '</tr>'

    html += '</tbody></table></div>'
    return html


def create_dividend_table(dividend_df: pd.DataFrame) -> str:
    """
    Crea tabella HTML dedicata ai dividendi dei titoli in portafoglio:
    dividendo per azione, yield (calcolato da noi, non dal campo Yahoo
    ambiguo), payout ratio, prossima data di stacco e di pagamento.

    Ordinata per yield decrescente (i titoli senza dividendo, es. growth
    stock, in fondo).
    """
    if dividend_df is None or dividend_df.empty:
        return "<p>Dati dividendi non disponibili</p>"

    df = dividend_df.copy()

    def fmt_amount(row, col):
        val = row.get(col)
        if pd.isna(val):
            return 'n/d'
        cur = row.get('currency') if pd.notna(row.get('currency')) else ''
        return f"{val:.2f} {cur}".strip()

    def fmt_pct(val):
        return f'{val:.2%}' if pd.notna(val) else 'n/d'

    def fmt_date(val):
        return str(val) if pd.notna(val) and val is not None else 'n/d'

    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>Ticker</th>'
    html += '<th class="num">Dividendo/Azione</th>'
    html += '<th class="num">Dividend Yield</th>'
    html += '<th class="num">Payout Ratio</th>'
    html += '<th>Prossimo Stacco (ex-div)</th>'
    html += '<th>Prossimo Pagamento</th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        no_dividend = pd.isna(row.get('dividend_rate')) or row.get('dividend_rate') == 0
        html += '<tr>'
        html += f'<td><strong>{row["ticker"]}</strong></td>'
        html += f'<td class="num">{"n/d (nessun dividendo)" if no_dividend else fmt_amount(row, "dividend_rate")}</td>'
        html += f'<td class="num positive">{fmt_pct(row.get("dividend_yield"))}</td>' if not no_dividend else '<td class="num">-</td>'
        html += f'<td class="num">{fmt_pct(row.get("payout_ratio"))}</td>'
        html += f'<td>{fmt_date(row.get("next_ex_dividend_date"))}</td>'
        html += f'<td>{fmt_date(row.get("next_dividend_pay_date"))}</td>'
        html += '</tr>'

    html += '</tbody></table></div>'
    return html


def create_practical_allocation_section(allocation_df: pd.DataFrame,
                                        allocation_info: Dict,
                                        total_capital: float) -> str:
    """Crea sezione HTML per allocazione pratica operativa"""
    
    if allocation_df.empty:
        return "<p>Allocazione non disponibile</p>"
    
    # Torta allocazione
    pie_fig = px.pie(
        allocation_df,
        values='importo_€',
        names='ticker',
        title=f'Allocazione Pratica - €{total_capital:,.0f}',
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4
    )

    pie_fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        hovertemplate='<b>%{label}</b><br>Importo: €%{value:,.0f}<br>Percentuale: %{percent}<extra></extra>'
    )

    pie_fig.update_layout(_base_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05,
                   font=dict(color=THEME_CONFIG['text_primary'])),
        height=500,
    ))

    pie_html = pie_fig.to_html(include_plotlyjs='cdn', div_id="practical_allocation_pie", config={'responsive': True})
    
    # Tabella dettagliata
    table_html = '''
    <div class="table-scroll" style="margin-top: 30px;">
    <table class="data-table">
    <thead>
        <tr>
            <th>#</th>
            <th>Ticker</th>
            <th>Settore</th>
            <th class="num">Peso %</th>
            <th class="num">Importo €</th>
            <th class="num">Sharpe</th>
            <th class="num">Rend. Annuo</th>
        </tr>
    </thead>
    <tbody>
    '''

    for idx, row in allocation_df.iterrows():
        table_html += f'''
        <tr>
            <td>{idx + 1}</td>
            <td class="accent"><strong>{row['ticker']}</strong></td>
            <td style="font-size: 0.9em;">{row['settore']}</td>
            <td class="num"><strong>{row['peso_%']:.2f}%</strong></td>
            <td class="num positive"><strong>€{row['importo_€']:,.2f}</strong></td>
            <td class="num">{row['sharpe_ratio']:.2f}</td>
            <td class="num {_pct_class(row['rendimento_annuo'])}">{row['rendimento_annuo']:.1%}</td>
        </tr>
        '''

    # Riga totale
    total_invested = allocation_df['importo_€'].sum()
    table_html += f'''
        <tr class="data-table__total">
            <td colspan="4">TOTALE INVESTITO:</td>
            <td class="num positive">€{total_invested:,.2f}</td>
            <td colspan="2"></td>
        </tr>
    '''

    if allocation_info['cash_amount'] > 0:
        table_html += f'''
        <tr class="data-table__cash">
            <td colspan="4">LIQUIDITÀ:</td>
            <td class="num warning">€{allocation_info['cash_amount']:,.2f}</td>
            <td colspan="2" style="font-size: 0.9em;">({allocation_info['cash_percent']:.1f}%)</td>
        </tr>
        <tr class="data-table__grand-total">
            <td colspan="4">TOTALE PORTAFOGLIO:</td>
            <td class="num">€{total_capital:,.2f}</td>
            <td colspan="2"></td>
        </tr>
        '''

    table_html += '</tbody></table></div>'

    # Box info allocazione
    info_html = f'''
    <div class="info-box">
        <h3>💼 Informazioni Allocazione Pratica</h3>
        <div class="info-grid">
            <div>
                <strong>Capitale Totale:</strong><br>
                €{total_capital:,.2f}
            </div>
            <div>
                <strong>Titoli Selezionati:</strong><br>
                {allocation_info['n_stocks']} su {len(PORTFOLIO_TICKERS)} disponibili
            </div>
            <div>
                <strong>Correlazione Media:</strong><br>
                {allocation_info['avg_correlation']:.1%} {'✅ Ottima' if allocation_info['avg_correlation'] < 0.3 else '⚠️ Migliorabile' if allocation_info['avg_correlation'] < 0.5 else '🔴 Alta'}
            </div>
            <div>
                <strong>Settori Diversificati:</strong><br>
                {len(allocation_info['sector_distribution'])} settori
            </div>
        </div>
    </div>
    '''
    
    # Matrice correlazione della selezione
    corr_matrix_html = ""
    if not allocation_info['correlation_matrix'].empty and len(allocation_info['selected_tickers']) > 1:
        corr_fig = px.imshow(
            allocation_info['correlation_matrix'],
            labels=dict(color="Correlazione"),
            x=allocation_info['correlation_matrix'].columns,
            y=allocation_info['correlation_matrix'].index,
            color_continuous_scale=[[0, THEME_CONFIG['accent']], [0.5, THEME_CONFIG['bg_card_alt']], [1, THEME_CONFIG['negative']]],
            aspect="auto",
            title=f"Matrice Correlazione Portafoglio Selezionato ({allocation_info['n_stocks']} titoli)"
        )

        corr_fig.update_layout(_base_layout(
            height=max(400, allocation_info['n_stocks'] * 25),
            xaxis=_axis(tickangle=-45),
            yaxis=_axis(),
        ))

        corr_matrix_html = f'''
        <h3 class="section-subtitle accent">📊 Matrice di Correlazione Ottimizzata</h3>
        <div class="info-box">
            <p>Questa matrice mostra le correlazioni solo tra i titoli selezionati per il tuo capitale.
            I titoli sono stati scelti per minimizzare la correlazione media e massimizzare la diversificazione.</p>
        </div>
        <div class="chart-container">
            {corr_fig.to_html(include_plotlyjs='cdn', div_id="practical_correlation_matrix", config={'responsive': True})}
        </div>
        '''

    # HTML completo
    full_html = f'''
    {info_html}
    <div class="chart-container" style="margin-top: 30px;">
        {pie_html}
    </div>
    <h3 class="section-subtitle accent">📋 Dettaglio Allocazione con Importi Esatti</h3>
    {table_html}
    {corr_matrix_html}
    '''

    return full_html


def generate_html_report(
    metrics: pd.DataFrame,
    correlation_matrix: pd.DataFrame,
    sector_breakdown: pd.DataFrame,
    geographic_breakdown: pd.DataFrame,
    portfolio_metrics: Dict,
    diversification_score: float,
    concentration_info: Dict = None,
    selection_info: Dict = None,
    current_weights: Dict[str, float] = None,
    suggested_weights: Dict[str, float] = None,
    backtest_results: pd.DataFrame = None,
    backtest_stats: Dict = None,
    backtest_stats_oos: Dict = None,
    oos_start_date=None,
    walk_forward_stats: Dict = None,
    currency_risk_info: Dict = None,
    opt_info: Dict = None,
    cash_allocation: float = 0.0,
    practical_allocation_df: pd.DataFrame = None,
    practical_allocation_info: Dict = None,
    earnings_df: pd.DataFrame = None,
    dividend_df: pd.DataFrame = None,
    total_capital: float = None,
    output_file: str = "portfolio_report.html"
) -> str:
    """
    Genera il report HTML completo
    """
    
    # Sezione "perché N titoli": curva di diversificazione reale, se disponibile
    selection_section_html = ""
    if selection_info and selection_info.get('diversification_curve'):
        curve_chart = create_diversification_curve_chart(
            selection_info['diversification_curve'], selection_info.get('n_stocks')
        )
        binding = selection_info.get('binding_constraint')
        binding_label = "il capitale disponibile" if binding == 'capitale' else "la diversificazione statistica"
        selection_section_html = f'''
        <div class="section" id="numero-titoli">
            <h2>Perché {selection_info['n_stocks']} Titoli</h2>
            <div class="info-box">
                <h3>📐 Numero titoli scelto dai dati, non da fasce fisse</h3>
                <p>Il numero di titoli non è più deciso per fasce di capitale arbitrarie: viene calcolato dal
                minimo empirico della vera curva di rischio del portafoglio (principio della "diversificazione
                ingenua" di <em>Evans &amp; Archer, 1968</em> e <em>Elton &amp; Gruber, 1977</em>) e vincolato dal
                capitale disponibile. Si continua ad aggiungere titoli finché il rischio scende, ci si ferma dove
                smette di migliorare in modo stabile (non al primo singolo punto basso, per non scambiare un
                avvallamento casuale della curva per la vera convergenza).</p>
                <div class="info-grid" style="margin-top: 15px;">
                    <div><strong>Ottimale per diversificazione:</strong><br>{selection_info['statistically_optimal_n']} titoli
                    (minimo empirico della curva di rischio)</div>
                    <div><strong>Sostenibile dal capitale:</strong><br>{selection_info['capital_affordable_n']} titoli</div>
                    <div><strong>Vincolo più stringente:</strong><br>{binding_label}</div>
                    <div><strong>Titoli scelti:</strong><br>{selection_info['n_stocks']}</div>
                </div>
            </div>
            <div class="chart-container">
                {curve_chart}
            </div>
            <p class="muted-note">Il grafico mostra la volatilità di un portafoglio equipesato aggiungendo via via
            titoli in ordine di Sharpe decrescente: oltre il punto evidenziato, il rischio smette di scendere in modo
            stabile (può anche risalire leggermente, se i titoli successivi in classifica sono più volatili).</p>
        </div>
        '''

    # Prepara i grafici
    charts = []

    # 1. Scatter Rischio-Rendimento
    charts.append(create_scatter_risk_return(metrics))
    
    # 2. Diversificazione settoriale e geografica  
    sector_chart_idx = None
    geo_chart_idx = None
    
    if not sector_breakdown.empty:
        sector_chart_idx = len(charts)
        charts.append(create_pie_chart(
            sector_breakdown, 
            'weight', 
            sector_breakdown.columns[0],
            'Diversificazione per Settore'
        ))
    
    if not geographic_breakdown.empty:
        geo_chart_idx = len(charts)
        charts.append(create_pie_chart(
            geographic_breakdown,
            'weight',
            geographic_breakdown.columns[0],
            'Diversificazione Geografica'
        ))
    
    # 3. Correlazioni
    corr_chart_idx = None
    if not correlation_matrix.empty:
        corr_chart_idx = len(charts)
        charts.append(create_correlation_heatmap(correlation_matrix))
        # Crea analisi dettagliata correlazioni (threshold da config)
        correlation_analysis_html = create_correlation_analysis_section(correlation_matrix, metrics)
    else:
        correlation_analysis_html = "<p>Dati insufficienti per analisi correlazioni</p>"
    
    # 4. Allocazione ottimale (torta e tabella)
    alloc_chart_idx = None
    if suggested_weights:
        alloc_chart_idx = len(charts)
        charts.append(create_optimal_allocation_pie(suggested_weights, top_n=REPORT_CONFIG['top_n_allocation_pie']))
        allocation_table = create_allocation_table(suggested_weights, metrics)
    else:
        allocation_table = "<p>Nessuna allocazione suggerita disponibile</p>"
    
    # 5. Confronto allocazioni (se disponibile corrente)
    comparison_chart_idx = None
    if current_weights and suggested_weights:
        comparison_chart_idx = len(charts)
        charts.append(create_allocation_comparison(current_weights, suggested_weights))
    
    # 6. Backtest storico
    backtest_chart_html = ""
    oos_comparison_html = ""
    if backtest_results is not None and not backtest_results.empty:
        backtest_chart_html = create_backtest_chart(backtest_results, backtest_stats or {}, oos_start_date)
        oos_comparison_html = create_oos_comparison_table(backtest_stats or {}, backtest_stats_oos or {})

    # 6B. Validazione statistica: metodologia ottimizzazione + walk-forward + rischio di cambio
    validation_section_html = ""
    if walk_forward_stats or opt_info:
        validation_section_html = create_validation_section(walk_forward_stats, opt_info, currency_risk_info)

    # Aggiungi info liquidità se presente
    cash_info_html = ""
    if cash_allocation > 0:
        equity_allocation = 1 - cash_allocation
        cash_info_html = f'''
        <div class="info-box info-box--success">
            <h3>💰 Componente Liquidità</h3>
            <p><strong>Allocazione suggerita:</strong></p>
            <ul>
                <li><strong>{equity_allocation:.1%}</strong> in azioni (portafoglio ottimizzato)</li>
                <li><strong>{cash_allocation:.1%}</strong> in liquidità/cash</li>
            </ul>
            <p style="margin-top: 10px; font-size: 0.95em;">
                La componente liquidità è calcolata in base alla volatilità del portafoglio e alle condizioni di mercato.
                Serve come cuscinetto di sicurezza e opportunità per ribilanciamenti futuri.
            </p>
        </div>
        '''

    # Statistiche portfolio
    portfolio_stats_html = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Rendimento Annuale</h3>
            <p class="stat-value {_pct_class(portfolio_metrics.get('annual_return', 0))}">
                {portfolio_metrics.get('annual_return', 0):.2%}
            </p>
        </div>
        <div class="stat-card">
            <h3>Volatilità Annuale</h3>
            <p class="stat-value">{portfolio_metrics.get('annual_volatility', 0):.2%}</p>
        </div>
        <div class="stat-card">
            <h3>Sharpe Ratio</h3>
            <p class="stat-value {'positive' if portfolio_metrics.get('sharpe_ratio', 0) > 1 else ''}">
                {portfolio_metrics.get('sharpe_ratio', 0):.2f}
            </p>
        </div>
        <div class="stat-card">
            <h3>Max Drawdown</h3>
            <p class="stat-value negative">{portfolio_metrics.get('max_drawdown', 0):.2%}</p>
        </div>
        <div class="stat-card">
            <h3>Score Diversificazione</h3>
            <p class="stat-value {'positive' if diversification_score > 70 else 'warning' if diversification_score > 50 else 'negative'}">
                {diversification_score:.1f}/100
            </p>
        </div>
        <div class="stat-card">
            <h3>N° Titoli</h3>
            <p class="stat-value">{len(metrics)}</p>
        </div>
        <div class="stat-card">
            <h3>Titoli Effettivi (Effective N)</h3>
            <p class="stat-value">{(concentration_info or {}).get('effective_n', 0):.1f}</p>
        </div>
        <div class="stat-card">
            <h3>VaR 95% (giornaliero)</h3>
            <p class="stat-value negative">{portfolio_metrics.get('var_95', 0):.2%}</p>
        </div>
        <div class="stat-card">
            <h3>CVaR 95% (giornaliero)</h3>
            <p class="stat-value negative">{portfolio_metrics.get('cvar_95', 0):.2%}</p>
        </div>
    </div>
    """
    
    # Tabella metriche dettagliate
    top_n_metrics = REPORT_CONFIG['top_n_metrics_table']
    top_metrics_df = metrics.sort_values('sharpe_ratio', ascending=False).head(top_n_metrics).copy()

    # Il P/E e lo Sharpe vanno formattati a parte, non come percentuale: il
    # float_format unico di to_html si applica a tutte le colonne float allo
    # stesso modo, quindi pre-formattiamo qui le colonne che non lo sono
    # (un P/E basso o un rendimento superiore al 1000% altrimenti verrebbero
    # scambiati per l'altro formato in base alla sola magnitudine)
    has_pe = 'trailing_pe' in top_metrics_df.columns
    if has_pe:
        top_metrics_df['trailing_pe'] = top_metrics_df['trailing_pe'].apply(
            lambda x: f'{x:.1f}x' if pd.notna(x) else 'n/d'
        )
    top_metrics_df['sharpe_ratio'] = top_metrics_df['sharpe_ratio'].apply(lambda x: f'{x:.2f}')

    metrics_columns = ['ticker', 'annual_return', 'annual_volatility', 'sharpe_ratio', 'max_drawdown', 'var_95']
    has_overvaluation = 'overvaluation_percentile' in top_metrics_df.columns
    if has_pe:
        metrics_columns.append('trailing_pe')
    if has_overvaluation:
        metrics_columns.append('overvaluation_percentile')
    if 'weight' in top_metrics_df.columns:
        metrics_columns.append('weight')

    metrics_table = top_metrics_df.to_html(
        classes='metrics-table data-table',
        float_format=lambda x: f'{x:.2%}',
        index=False,
        columns=metrics_columns
    )

    # Indice di navigazione: solo le voci per sezioni realmente presenti nel report
    nav_items = [('#metriche', '📈 Metriche')]
    if selection_section_html:
        nav_items.append(('#numero-titoli', '📐 N° Titoli'))
    nav_items.append(('#rischio-rendimento', '🎯 Rischio/Rendimento'))
    if backtest_chart_html:
        nav_items.append(('#backtest', '📈 Backtest'))
    if validation_section_html:
        nav_items.append(('#validazione', '🔬 Validazione'))
    if sector_chart_idx is not None:
        nav_items.append(('#settoriale', '🏭 Settori'))
    if geo_chart_idx is not None:
        nav_items.append(('#geografica', '🌍 Geografia'))
    if corr_chart_idx is not None:
        nav_items.append(('#correlazione', '🔗 Correlazione'))
    if alloc_chart_idx is not None:
        nav_items.append(('#allocazione-ottimale', '💡 Allocazione Ottimale'))
    if comparison_chart_idx is not None:
        nav_items.append(('#confronto', '💼 Confronto'))
    if practical_allocation_df is not None and not practical_allocation_df.empty:
        nav_items.append(('#allocazione-pratica', '💰 Allocazione Pratica'))
    has_earnings = earnings_df is not None and not earnings_df.empty
    if has_earnings:
        nav_items.append(('#utili', '💵 Utili'))
    has_dividends = dividend_df is not None and not dividend_df.empty
    if has_dividends:
        nav_items.append(('#dividendi', '💶 Dividendi'))
    nav_items.append(('#dettaglio-metriche', '📋 Dettaglio Titoli'))

    nav_html = ''.join(f'<a href="{href}">{label}</a>' for href, label in nav_items)

    earnings_table_html = create_earnings_table(earnings_df) if has_earnings else ''
    dividend_table_html = create_dividend_table(dividend_df) if has_dividends else ''

    T = THEME_CONFIG

    # Template HTML
    html_template = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Analisi Portafoglio - {datetime.now().strftime('%d/%m/%Y')}</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            ::selection {{
                background: {T['accent']};
                color: {T['bg_page']};
            }}

            ::-webkit-scrollbar {{
                width: 10px;
                height: 10px;
            }}
            ::-webkit-scrollbar-track {{
                background: {T['bg_page']};
            }}
            ::-webkit-scrollbar-thumb {{
                background: {T['bg_elevated']};
                border-radius: 5px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background: {T['accent']};
            }}

            body {{
                font-family: {T['font_family']};
                background:
                    radial-gradient(circle at 15% 0%, rgba(0, 217, 255, 0.08), transparent 40%),
                    radial-gradient(circle at 85% 100%, rgba(123, 97, 255, 0.08), transparent 40%),
                    {T['bg_page']};
                min-height: 100vh;
                padding: 24px;
                color: {T['text_primary']};
                line-height: 1.6;
            }}

            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: {T['bg_card']};
                border: 1px solid {T['border']};
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(0, 217, 255, 0.05);
                overflow: hidden;
            }}

            header {{
                background: linear-gradient(135deg, {T['bg_card_alt']} 0%, {T['bg_elevated']} 100%);
                border-bottom: 1px solid {T['border']};
                padding: 44px 40px;
                text-align: center;
                position: relative;
            }}

            header::after {{
                content: "";
                position: absolute;
                bottom: 0; left: 0; right: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, {T['accent']}, {T['accent_2']}, transparent);
            }}

            header h1 {{
                font-size: 2.4em;
                margin-bottom: 10px;
                font-weight: 800;
                letter-spacing: 0.5px;
                background: linear-gradient(90deg, {T['accent']}, {T['accent_2']});
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
            }}

            header p {{
                font-size: 1.05em;
                color: {T['text_secondary']};
                font-family: {T['font_mono']};
            }}

            nav.section-nav {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                padding: 14px 40px;
                background: {T['bg_card_alt']};
                border-bottom: 1px solid {T['border']};
                position: sticky;
                top: 0;
                z-index: 10;
                overflow-x: auto;
            }}

            nav.section-nav a {{
                color: {T['text_secondary']};
                text-decoration: none;
                font-size: 0.85em;
                font-weight: 600;
                white-space: nowrap;
                padding: 7px 14px;
                border-radius: 20px;
                border: 1px solid {T['border']};
                background: {T['bg_card']};
                transition: all 0.2s ease;
            }}

            nav.section-nav a:hover {{
                color: {T['bg_page']};
                background: {T['accent']};
                border-color: {T['accent']};
            }}

            .content {{
                padding: 40px;
            }}

            .section {{
                margin-bottom: 56px;
                scroll-margin-top: 70px;
            }}

            .section h2 {{
                color: {T['text_primary']};
                font-size: 1.7em;
                font-weight: 700;
                margin-bottom: 20px;
                padding-bottom: 12px;
                border-bottom: 2px solid {T['border']};
                position: relative;
            }}

            .section h2::before {{
                content: "▸";
                color: {T['accent']};
                margin-right: 10px;
            }}

            .section-subtitle {{
                margin-top: 40px;
                margin-bottom: 12px;
                font-size: 1.15em;
            }}
            .section-subtitle.accent {{ color: {T['accent']}; }}
            .section-subtitle.positive {{ color: {T['positive']}; }}
            .section-subtitle.negative {{ color: {T['negative']}; }}

            .muted-note {{
                font-size: 0.9em;
                color: {T['text_secondary']};
                margin-bottom: 10px;
            }}

            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
                gap: 16px;
                margin-bottom: 32px;
            }}

            .stat-card {{
                background: {T['bg_card_alt']};
                border: 1px solid {T['border']};
                padding: 24px;
                border-radius: 12px;
                transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            }}

            .stat-card:hover {{
                transform: translateY(-3px);
                border-color: {T['accent']};
                box-shadow: 0 8px 24px rgba(0, 217, 255, 0.15);
            }}

            .stat-card h3 {{
                font-size: 0.78em;
                color: {T['text_secondary']};
                text-transform: uppercase;
                letter-spacing: 1px;
                font-weight: 600;
                margin-bottom: 10px;
            }}

            .stat-value {{
                font-size: 2.2em;
                font-weight: 700;
                font-family: {T['font_mono']};
                color: {T['text_primary']};
            }}

            .stat-value.positive {{ color: {T['positive']}; }}
            .stat-value.negative {{ color: {T['negative']}; }}
            .stat-value.warning {{ color: {T['warning']}; }}

            .chart-container {{
                background: {T['bg_card_alt']};
                border: 1px solid {T['border']};
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 30px;
            }}

            .table-scroll {{
                overflow-x: auto;
                border-radius: 10px;
            }}

            .data-table, .metrics-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background: {T['bg_card_alt']};
                border-radius: 10px;
                overflow: hidden;
                font-size: 0.95em;
            }}

            .data-table th, .metrics-table th {{
                background: linear-gradient(135deg, {T['accent']} 0%, {T['accent_2']} 100%);
                color: {T['bg_page']};
                padding: 13px 15px;
                text-align: left;
                font-weight: 700;
                text-transform: uppercase;
                font-size: 0.78em;
                letter-spacing: 0.5px;
            }}

            .data-table td, .metrics-table td {{
                padding: 11px 15px;
                border-bottom: 1px solid {T['border']};
                font-family: {T['font_mono']};
            }}

            .data-table td:first-child, .metrics-table td:first-child,
            .data-table th:first-child, .metrics-table th:first-child {{
                font-family: {T['font_family']};
            }}

            .data-table tbody tr:nth-child(even), .metrics-table tbody tr:nth-child(even) {{
                background: rgba(255, 255, 255, 0.02);
            }}

            .data-table tbody tr:hover, .metrics-table tbody tr:hover {{
                background: {T['bg_elevated']};
            }}

            .data-table tr:last-child td, .metrics-table tr:last-child td {{
                border-bottom: none;
            }}

            .data-table .num, .metrics-table th:not(:first-child), .metrics-table td:not(:first-child) {{
                text-align: right;
            }}

            .data-table tbody tr.highlight-row {{
                background: {T['warning_soft']};
                border-left: 3px solid {T['warning']};
            }}

            .data-table tbody tr.highlight-row:hover {{
                background: {T['warning_soft']};
            }}

            .data-table--compact td, .data-table--compact th {{
                padding: 8px 12px;
                font-size: 0.9em;
            }}

            .data-table--danger th {{
                background: linear-gradient(135deg, {T['negative']} 0%, #c81f45 100%);
                color: #fff;
            }}

            .data-table--accent2 th {{
                background: linear-gradient(135deg, {T['accent_2']} 0%, #5238b8 100%);
                color: #fff;
            }}

            .data-table__total td {{
                background: {T['positive_soft']};
                font-weight: 700;
                font-size: 1.05em;
                border-bottom: none;
            }}
            .data-table__cash td {{
                background: {T['warning_soft']};
                font-weight: 700;
                border-bottom: none;
            }}
            .data-table__grand-total td {{
                background: linear-gradient(135deg, {T['accent']} 0%, {T['accent_2']} 100%);
                color: {T['bg_page']};
                font-weight: 800;
                font-size: 1.15em;
                border-bottom: none;
            }}

            .two-col-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
                margin-top: 30px;
            }}

            .info-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}

            .positive {{ color: {T['positive']}; }}
            .negative {{ color: {T['negative']}; }}
            .warning {{ color: {T['warning']}; }}
            .accent {{ color: {T['accent']}; }}
            .accent-2 {{ color: {T['accent_2']}; }}

            .info-box {{
                background: {T['accent_soft']};
                border-left: 4px solid {T['accent']};
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}

            .info-box h3 {{
                color: {T['accent']};
                margin-bottom: 10px;
            }}

            .info-box ul {{
                list-style-position: inside;
                color: {T['text_primary']};
                line-height: 1.8;
            }}

            .info-box--success {{ background: {T['positive_soft']}; border-left-color: {T['positive']}; }}
            .info-box--success h3 {{ color: {T['positive']}; }}

            .info-box--warning {{ background: {T['warning_soft']}; border-left-color: {T['warning']}; }}
            .info-box--warning h3 {{ color: {T['warning']}; }}

            .info-box--danger {{ background: {T['negative_soft']}; border-left-color: {T['negative']}; }}
            .info-box--danger h3 {{ color: {T['negative']}; }}

            .info-box--accent2 {{ background: rgba(41, 98, 255, 0.10); border-left-color: {T['accent_2']}; }}
            .info-box--accent2 h3 {{ color: {T['accent_2']}; }}

            .section--highlight {{
                background: linear-gradient(135deg, rgba(0, 255, 157, 0.06) 0%, rgba(0, 217, 255, 0.06) 100%);
                padding: 30px;
                border-radius: 15px;
                border: 1px solid {T['accent']};
            }}

            footer {{
                background: {T['bg_card_alt']};
                border-top: 1px solid {T['border']};
                padding: 24px;
                text-align: center;
                color: {T['text_secondary']};
                font-size: 0.9em;
            }}

            @media (max-width: 768px) {{
                .stats-grid, .two-col-grid {{
                    grid-template-columns: 1fr;
                }}

                header h1 {{
                    font-size: 1.6em;
                }}

                .content {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📊 ANALISI PORTAFOGLIO AZIONARIO</h1>
                <p>Report generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}</p>
            </header>

            <nav class="section-nav">{nav_html}</nav>

            <div class="content">
                <div class="section" id="metriche">
                    <h2>Metriche di Portafoglio</h2>
                    {portfolio_stats_html}

                    <div class="info-box">
                        <h3>💡 Interpretazione</h3>
                        <ul>
                            <li><strong>Sharpe Ratio &gt; 1:</strong> Ottimo rapporto rischio/rendimento</li>
                            <li><strong>Score Diversificazione &gt; 70:</strong> Portafoglio ben diversificato (combina correlazione media e concentrazione dei pesi)</li>
                            <li><strong>Max Drawdown:</strong> Peggiore perdita dal picco (più basso è meglio)</li>
                            <li><strong>Titoli Effettivi (Effective N):</strong> quanti titoli equipesati equivalgono alla concentrazione reale del portafoglio (es. 15 titoli con un 50% su uno solo pesano come ~3-4 titoli equipesati)</li>
                            <li><strong>VaR 95% giornaliero:</strong> nel 5% dei giorni peggiori, la perdita è stata pari o superiore a questo valore</li>
                            <li><strong>CVaR 95% giornaliero:</strong> perdita media nei giorni oltre la soglia del VaR — più informativo del VaR sulla reale gravità delle code negative</li>
                        </ul>
                    </div>
                </div>

                {selection_section_html}

                <div class="section" id="rischio-rendimento">
                    <h2>Analisi Rischio-Rendimento</h2>
                    <div class="chart-container">
                        {charts[0]}
                    </div>
                </div>

                {f'''
                <div class="section" id="backtest">
                    <h2>Backtest Storico</h2>
                    <div class="info-box info-box--warning">
                        <h3>ℹ️ Come Interpretare il Backtest</h3>
                        <p>Questo grafico mostra come il portafoglio ottimizzato avrebbe performato nel periodo analizzato,
                        confrontato con i principali indici di mercato. <strong>Nota:</strong> Le performance passate non garantiscono risultati futuri.</p>
                        <p style="margin-top: 10px;">La zona ombreggiata (a destra della linea tratteggiata "Inizio Out-of-Sample")
                        è la finestra di dati <strong>mai vista</strong> da scouting, selezione smart e ottimizzazione dei pesi:
                        è l'unica parte del grafico che costituisce un test onesto, non circolare, della selezione.</p>
                    </div>
                    <div class="chart-container">
                        {backtest_chart_html}
                    </div>
                    {oos_comparison_html}
                </div>
                ''' if backtest_chart_html else ''}

                {f'''
                <div class="section" id="validazione">
                    <h2>Validazione Statistica e Metodologia</h2>
                    {validation_section_html}
                </div>
                ''' if validation_section_html else ''}

                {f'''
                <div class="section" id="settoriale">
                    <h2>Diversificazione Settoriale</h2>
                    <div class="chart-container">
                        {charts[sector_chart_idx]}
                    </div>
                </div>
                ''' if sector_chart_idx is not None else ''}

                {f'''
                <div class="section" id="geografica">
                    <h2>Diversificazione Geografica</h2>
                    <div class="chart-container">
                        {charts[geo_chart_idx]}
                    </div>
                </div>
                ''' if geo_chart_idx is not None else ''}

                {f'''
                <div class="section" id="correlazione">
                    <h2>Matrice di Correlazione</h2>
                    <div class="chart-container">
                        {charts[corr_chart_idx]}
                    </div>

                    <h3 class="section-subtitle accent">📊 Analisi Dettagliata Correlazioni</h3>
                    {correlation_analysis_html}
                </div>
                ''' if corr_chart_idx is not None else ''}

                {f'''
                <div class="section" id="allocazione-ottimale">
                    <h2>Allocazione Ottimale Suggerita</h2>
                    <div class="info-box">
                        <h3>📊 Strategia di Allocazione con Riduzione Correlazioni</h3>
                        <p>Questa allocazione è ottimizzata considerando:</p>
                        <ul>
                            <li><strong>Profilo di rischio</strong> selezionato (rapporto rischio/rendimento)</li>
                            <li><strong>Riduzione correlazioni alte</strong> - I titoli con correlazione media >50% ricevono peso ridotto</li>
                            <li><strong>Diversificazione</strong> - Peso massimo {ALLOCATION_CONFIG['max_weight_per_stock']:.0%} per singolo titolo</li>
                        </ul>
                        <p style="margin-top: 10px;"><em>Confronta con la sezione "Analisi Correlazioni" per vedere quali titoli sono stati penalizzati.</em></p>
                    </div>
                    {cash_info_html}
                    <div class="chart-container">
                        {charts[alloc_chart_idx]}
                    </div>

                    <h3 class="section-subtitle accent">📋 Dettaglio Allocazione per Titolo</h3>
                    {allocation_table}
                </div>
                ''' if alloc_chart_idx is not None else ''}

                {f'''
                <div class="section" id="confronto">
                    <h2>Confronto: Allocazione Corrente vs Suggerita</h2>
                    <div class="chart-container">
                        {charts[comparison_chart_idx]}
                    </div>
                </div>
                ''' if comparison_chart_idx is not None else ''}

                {f'''
                <div class="section section--highlight" id="allocazione-pratica">
                    <h2>💰 ALLOCAZIONE PRATICA OPERATIVA</h2>
                    <div class="info-box info-box--warning">
                        <h3>🎯 Come Investire Concretamente</h3>
                        <p>Questa sezione traduce la teoria in pratica. In base al tuo capitale di <strong>€{total_capital:,.2f}</strong>,
                        abbiamo selezionato <strong>{practical_allocation_info['n_stocks']} titoli</strong> ottimali che bilanciano:</p>
                        <ul>
                            <li><strong>Diversificazione</strong> - Correlazione media {practical_allocation_info['avg_correlation']:.1%}</li>
                            <li><strong>Performance</strong> - Titoli con migliori Sharpe Ratio</li>
                            <li><strong>Praticità</strong> - Importi gestibili per titolo (min €500)</li>
                            <li><strong>Settori</strong> - {len(practical_allocation_info['sector_distribution'])} settori diversi</li>
                        </ul>
                        <p style="margin-top: 10px;"><em>💡 Con meno capitale, concentrarsi su pochi titoli ben selezionati è più efficace che frammentare troppo.</em></p>
                    </div>
                    {create_practical_allocation_section(practical_allocation_df, practical_allocation_info, total_capital)}
                </div>
                ''' if practical_allocation_df is not None and not practical_allocation_df.empty else ''}

                {f'''
                <div class="section" id="utili">
                    <h2>💵 Utili dei Titoli in Portafoglio</h2>
                    <p class="muted-note">
                        <strong>EPS (trailing)</strong>/<strong>(forward)</strong>: utile per azione degli ultimi 12 mesi / atteso nei
                        prossimi 12 mesi, nella valuta locale del titolo. <strong>Crescita Utili YoY</strong>: variazione degli utili
                        rispetto allo stesso trimestre dell'anno precedente (negativo = utili in calo). <strong>Margine Netto</strong>:
                        utile netto sui ricavi. <strong>Prossima Pubblicazione</strong>/<strong>EPS Atteso</strong>/<strong>Ricavi Attesi</strong>:
                        data e stime di consensus degli analisti per la prossima trimestrale — sono previsioni, non dati certi, e per
                        alcuni titoli esteri Yahoo Finance non ne pubblica. Le righe evidenziate indicano una pubblicazione entro 14 giorni.
                    </p>
                    {earnings_table_html}
                </div>
                ''' if has_earnings else ''}

                {f'''
                <div class="section" id="dividendi">
                    <h2>💶 Dividendi dei Titoli in Portafoglio</h2>
                    <p class="muted-note">
                        <strong>Dividendo/Azione</strong>: dividendo annuo dichiarato, nella valuta locale del titolo.
                        <strong>Dividend Yield</strong>: calcolato da noi come dividendo/azione diviso l'ultimo prezzo reale
                        disponibile (non usiamo il campo di Yahoo, espresso in modo incoerente a seconda del titolo).
                        <strong>Payout Ratio</strong>: quota dell'utile netto distribuita come dividendo (oltre il 100% indica
                        un dividendo non coperto dagli utili correnti, un segnale di attenzione). <strong>Prossimo Stacco</strong>
                        (ex-dividend date, la data da cui comprare il titolo non dà più diritto al prossimo dividendo) e
                        <strong>Prossimo Pagamento</strong> sono le date note a Yahoo Finance; molti titoli (in particolare
                        growth stock come PLTR, IONQ, NVDA) non distribuiscono dividendi.
                    </p>
                    {dividend_table_html}
                </div>
                ''' if has_dividends else ''}

                <div class="section" id="dettaglio-metriche">
                    <h2>Dettaglio Metriche Tutti i Titoli (Top {top_n_metrics})</h2>
                    <p class="muted-note">
                        Nota: <strong>var_95</strong> è il Value at Risk giornaliero (non annualizzato).
                        <strong>trailing_pe</strong> è il P/E corrente (n/d se l'azienda non è profittevole o il dato non è disponibile).
                        <strong>overvaluation_percentile</strong> è quanto un titolo è caro rispetto ai soli pari del proprio settore
                        (media dei percentili su P/E, PEG e P/B; 0% = il più economico del settore, 100% = il più caro) — penalizza
                        l'ingresso in portafoglio dei titoli più cari, non li esclude.
                    </p>
                    {metrics_table}
                </div>
            </div>

            <footer>
                <p>Generato con Python, yfinance e Plotly | Dati di mercato forniti da Yahoo Finance</p>
                <p style="margin-top: 10px; font-size: 0.85em;">
                    ⚠️ Disclaimer: Questo report è solo a scopo informativo e non costituisce consulenza finanziaria.
                </p>
            </footer>
        </div>
    </body>
    </html>
    """

    # Salva il file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_template)

    return output_file
