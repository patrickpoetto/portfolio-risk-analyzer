"""
HTML report generator with interactive charts
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

# --- Theme helpers shared by all Plotly charts ("Midnight Terminal") ---

CHART_COLORWAY = THEME_CONFIG['qualitative_palette']


def _base_layout(**overrides) -> dict:
    """Common Plotly layout: dark backgrounds, light font, thin white gridlines."""
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
    """Style applied to cartesian axes (thin white gridlines on a dark background)."""
    axis = dict(
        gridcolor=THEME_CONFIG['grid'],
        zerolinecolor=THEME_CONFIG['grid'],
        linecolor=THEME_CONFIG['border'],
        color=THEME_CONFIG['text_secondary'],
    )
    axis.update(overrides)
    return axis


def _pct_class(value: float) -> str:
    """CSS class 'positive'/'negative' based on sign, used to color values in tables."""
    if value > 0:
        return 'positive'
    if value < 0:
        return 'negative'
    return ''


def create_pie_chart(data: pd.DataFrame, values_col: str, names_col: str,
                     title: str, color_scheme: str = None) -> str:
    """Creates an interactive pie chart with elegant outside labels"""
    fig = px.pie(
        data,
        values=values_col,
        names=names_col,
        title=title,
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4  # Donut chart
    )

    # Elegant labels outside the slices with connecting lines
    fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        pull=[0.05 if i < 3 else 0 for i in range(len(data))],  # Pull out top 3
        hovertemplate='<b>%{label}</b><br>Share: %{percent}<br>Value: %{value:.2%}<extra></extra>',
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
        margin=dict(l=20, r=150, t=60, b=20)  # More room on the right for labels
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id=f"chart_{title.replace(' ', '_')}", config={'responsive': True})


def create_bar_chart(data: pd.DataFrame, x_col: str, y_col: str,
                     title: str, color_col: str = None) -> str:
    """Creates a bar chart"""

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
    """Creates a risk-return scatter plot"""

    if metrics.empty:
        return "<p>Insufficient data to generate the risk-return chart</p>"

    # Build the chart using graph_objects for finer control
    fig = go.Figure()

    # Bubble size based on weight, or uniform
    if 'weight' in metrics.columns and metrics['weight'].sum() > 0:
        sizes = metrics['weight'] * 500 + 15
    else:
        sizes = [30] * len(metrics)

    # Add the scatter plot
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
                      'Return: %{y:.2%}<br>' +
                      'Volatility: %{x:.2%}<br>' +
                      'Sharpe: %{marker.color:.2f}<extra></extra>',
        name=''
    ))

    fig.update_layout(_base_layout(
        title='Risk-Return Analysis',
        height=600,
        xaxis_title='Annual Volatility (Risk)',
        yaxis_title='Expected Annual Return',
        xaxis=_axis(tickformat='.1%'),
        yaxis=_axis(tickformat='.1%'),
        showlegend=False
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="risk_return_scatter", config={'responsive': True})


def create_correlation_heatmap(corr_matrix: pd.DataFrame, top_n: int = 25) -> str:
    """Creates a correlation heatmap"""

    if corr_matrix.empty or len(corr_matrix) < 2:
        return "<p>Insufficient data to generate the correlation matrix</p>"

    # Limit to the top N tickers for readability
    if len(corr_matrix) > top_n:
        # Select the tickers with the highest correlation variance
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
        colorbar=dict(title="Correlation", tickfont=dict(color=THEME_CONFIG['text_primary']),
                     title_font=dict(color=THEME_CONFIG['text_primary'])),
        hovertemplate='%{x} vs %{y}<br>Correlation: %{z:.2f}<extra></extra>'
    ))

    fig.update_layout(_base_layout(
        title=f'Correlation Matrix (Top {len(corr_matrix)} Stocks)',
        height=700,
        xaxis=_axis(tickangle=-45),
        yaxis=_axis(tickangle=0),
        margin=dict(l=100, r=50, t=80, b=100)
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="correlation_heatmap", config={'responsive': True})


def create_top_performers_chart(metrics: pd.DataFrame, metric: str,
                                top_n: int = 10, ascending: bool = False) -> str:
    """Creates a chart of the top performers for a given metric"""

    df_sorted = metrics.sort_values(metric, ascending=ascending).head(top_n)

    metric_labels = {
        'annual_return': 'Annual Return',
        'sharpe_ratio': 'Sharpe Ratio',
        'annual_volatility': 'Annual Volatility',
        'max_drawdown': 'Max Drawdown'
    }

    title = f'Top {top_n} - {metric_labels.get(metric, metric)}'

    # Color based on positive/negative value
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
    """Creates a pie chart for the suggested optimal allocation"""

    if not suggested_weights:
        return "<p>No suggested allocation available</p>"

    # Convert to a DataFrame and sort
    df = pd.DataFrame(list(suggested_weights.items()), columns=['Ticker', 'Weight'])
    df = df.sort_values('Weight', ascending=False)

    # Take the top N and aggregate the rest into "Other"
    if len(df) > top_n:
        top_df = df.head(top_n).copy()
        others_weight = df.iloc[top_n:]['Weight'].sum()
        if others_weight > 0:
            others_row = pd.DataFrame([['Other', others_weight]], columns=['Ticker', 'Weight'])
            df = pd.concat([top_df, others_row], ignore_index=True)

    fig = px.pie(
        df,
        values='Weight',
        names='Ticker',
        title='Suggested Optimal Allocation',
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4
    )

    # Elegant outside labels
    fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        pull=[0.08, 0.05, 0.03] + [0] * (len(df) - 3),  # Pull out top 3
        hovertemplate='<b>%{label}</b><br>Suggested weight: %{percent}<br>Value: %{value:.2%}<extra></extra>',
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
    Chart of the real diversification curve: volatility of an
    equal-weighted portfolio as the number of stocks grows (sorted by
    descending Sharpe), with the chosen point highlighted. Makes visible
    the principle (Evans & Archer 1968 / Elton & Gruber 1977) on which the
    actually selected number of stocks is based.
    """
    if not curve:
        return "<p>Insufficient data for the diversification curve</p>"

    ns = [p['n'] for p in curve]
    vols = [p['volatility'] for p in curve]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ns, y=vols, mode='lines+markers',
        line=dict(color=THEME_CONFIG['accent'], width=3),
        marker=dict(size=5, color=THEME_CONFIG['accent']),
        hovertemplate='N=%{x} stocks<br>Volatility: %{y:.2%}<extra></extra>',
        name='Equal-weighted portfolio volatility'
    ))

    if chosen_n and chosen_n <= len(curve):
        chosen_vol = curve[chosen_n - 1]['volatility']
        fig.add_trace(go.Scatter(
            x=[chosen_n], y=[chosen_vol], mode='markers',
            marker=dict(size=14, color=THEME_CONFIG['positive'], symbol='star',
                       line=dict(width=2, color=THEME_CONFIG['bg_card'])),
            hovertemplate=f'Chosen N = {chosen_n}<br>Volatility: %{{y:.2%}}<extra></extra>',
            name='Chosen N'
        ))

    fig.update_layout(_base_layout(
        title='Real Diversification Curve: Volatility vs Number of Stocks',
        xaxis_title='Number of stocks (sorted by descending Sharpe)',
        yaxis_title='Annualized volatility (equal-weighted)',
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
    """Compares the current allocation vs the suggested one"""

    tickers = list(set(list(current_weights.keys()) + list(suggested_weights.keys())))

    current = [current_weights.get(t, 0) for t in tickers]
    suggested = [suggested_weights.get(t, 0) for t in tickers]

    # Sort by suggested weight
    sorted_indices = sorted(range(len(suggested)), key=lambda i: suggested[i], reverse=True)
    tickers = [tickers[i] for i in sorted_indices]
    current = [current[i] for i in sorted_indices]
    suggested = [suggested[i] for i in sorted_indices]

    # Show only the top 20 for readability
    if len(tickers) > 20:
        tickers = tickers[:20]
        current = current[:20]
        suggested = suggested[:20]

    fig = go.Figure(data=[
        go.Bar(name='Current Allocation', x=tickers, y=current, marker_color=THEME_CONFIG['text_secondary']),
        go.Bar(name='Suggested Allocation', x=tickers, y=suggested, marker_color=THEME_CONFIG['accent'])
    ])

    fig.update_layout(_base_layout(
        title='Allocation Comparison: Current vs Suggested',
        xaxis_title='Ticker',
        yaxis_title='Portfolio Weight',
        barmode='group',
        height=500,
        xaxis=_axis(tickangle=-45),
        yaxis=_axis(tickformat='.0%'),
    ))

    return fig.to_html(include_plotlyjs='cdn', div_id="allocation_comparison", config={'responsive': True})


def create_backtest_chart(backtest_results: pd.DataFrame,
                         backtest_stats: Dict,
                         oos_start_date=None) -> str:
    """Creates the historical performance chart with benchmark comparison"""

    if backtest_results.empty:
        return "<p>Insufficient data for the backtest</p>"

    fig = go.Figure()

    # Define vivid colors and line widths for each series (Portfolio in
    # electric cyan, thicker, to stand out against the benchmarks)
    colors = {
        'Portfolio': THEME_CONFIG['accent'],
        'S&P 500': THEME_CONFIG['accent_2'],
        'NASDAQ': THEME_CONFIG['warning'],
        'MSCI World': THEME_CONFIG['positive'],
        'VT': '#ff6b9d',
        'VT (Total World)': '#ff6b9d'
    }

    widths = {
        'Portfolio': 4,
        'S&P 500': 2,
        'NASDAQ': 2,
        'MSCI World': 2,
        'VT': 2,
        'VT (Total World)': 2
    }

    # Add each series
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
                         'Date: %{x|%d/%m/%Y}<br>' +
                         'Value: %{y:.2f}<br>' +
                         '<extra></extra>'
        ))

    # Mark the out-of-sample window: to the left of the line the data is
    # in-sample (it influenced scouting/selection/weights), to the right it
    # is the honest test never seen by those stages.
    # Note: we pass the dates as strings (not pd.Timestamp) because
    # add_vline/add_vrect with a Timestamp trigger internal Plotly
    # arithmetic that is incompatible with recent pandas versions.
    if oos_start_date is not None and backtest_results.index[0] <= oos_start_date <= backtest_results.index[-1]:
        oos_start_str = oos_start_date.strftime('%Y-%m-%d')
        oos_end_str = backtest_results.index[-1].strftime('%Y-%m-%d')
        fig.add_vrect(
            x0=oos_start_str, x1=oos_end_str,
            fillcolor=THEME_CONFIG['accent_2'], opacity=0.12, line_width=0
        )
        # Note: add_vline with the convenience annotation_text/
        # annotation_position parameters triggers an internal Plotly 6.x
        # bug on time axes (TypeError int+str). We add the line and the
        # annotation as two separate calls to avoid it.
        fig.add_vline(x=oos_start_str, line_width=2, line_dash="dash", line_color=THEME_CONFIG['accent_2'])
        fig.add_annotation(
            x=oos_start_str, y=1, yref="paper", yanchor="bottom",
            text="Out-of-Sample Start", showarrow=False,
            font=dict(color=THEME_CONFIG['accent_2'], size=11)
        )

    fig.update_layout(_base_layout(
        title='Historical Performance: Portfolio vs Benchmarks',
        xaxis_title='Date',
        yaxis_title='Investment Value (Base 100)',
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
    Comparison table between the whole-period statistics (in-sample,
    includes the data used to choose the stocks) and the out-of-sample
    window only (never seen by scouting/selection/optimization).

    The "honest" number for judging the selection is the Out-of-Sample
    one: it is normal (and expected) for it to be lower than the
    whole-period one.
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
        <h3>🔍 Whole Period vs Out-of-Sample: why the difference matters</h3>
        <p>The stocks were chosen because they had the best historical score <strong>within
        the window used for selection</strong>. The "Whole Period" return therefore includes the
        same data used to choose them, and is systematically optimistic. The <strong>"Out-of-Sample
        Only"</strong> column instead measures performance <strong>on data never seen</strong> by
        scouting, smart selection and weight optimization: it is the most honest number for judging
        whether the selection has real predictive value.</p>
    </div>
    <div class="table-scroll">
    <table class="data-table data-table--accent2">
    <thead>
        <tr>
            <th>Series</th>
            <th class="num">Whole-Period Return</th>
            <th class="num">Out-of-Sample-Only Return</th>
            <th class="num">OOS Sharpe</th>
            <th class="num">OOS Max DD</th>
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
    Statistical validation section: optimization methodology (shrinkage +
    real solver), multi-fold walk-forward results with bootstrap confidence
    intervals compared against benchmarks (equal-weight, naive
    minimum-variance), and disclosure of unhedged currency risk.
    """
    html = '<div class="validation-section">'

    if opt_info:
        html += f'''
        <div class="info-box info-box--accent2">
            <h3>⚙️ Optimization Methodology</h3>
            <p>The weights are no longer a heuristic score: they are the solution of a real Markowitz
            optimization problem (constrained SLSQP solver), with objective <strong>{opt_info['objective']}</strong>
            for the selected risk profile.</p>
            <ul>
                <li><strong>Expected return shrinkage:</strong> {opt_info['return_shrinkage']:.0%} toward the
                universe average (trailing historical returns are noisy estimates; using them raw rewards
                outliers in the observed sample)</li>
                <li><strong>Covariance shrinkage:</strong> {opt_info['cov_shrinkage']:.0%} toward the
                constant-correlation target (Ledoit &amp; Wolf 2004 style; the pure sample matrix over a few
                hundred observations is ill-conditioned)</li>
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
            <h3>🔬 Walk-Forward Validation (multi-fold, out-of-sample)</h3>
            <p>Instead of a single in-sample/out-of-sample split, the weights are re-estimated multiple times
            over progressive training windows and tested ONLY on the immediately following period, never seen
            during estimation (no look-ahead). Includes a transaction cost on turnover at every rebalancing.
            The interval (Sharpe CI 90%) is obtained via block-bootstrap: if it includes zero, the performance
            is not statistically distinguishable from noise.</p>
        </div>
        <div class="table-scroll">
        <table class="data-table data-table--accent2">
        <thead>
            <tr>
                <th>Strategy</th>
                <th class="num">OOS Total Return</th>
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
            vol_str = f"{vol:.1%}" if vol is not None else "n/a"
            exp_rows += f'''
            <tr>
                <td><strong>{cur}</strong></td>
                <td class="num">{exp:.1%}</td>
                <td class="num">{vol_str}</td>
            </tr>
            '''
        html += f'''
        <div class="info-box info-box--warning">
            <h3>💱 Currency Risk (EUR base, unhedged)</h3>
            <p>The rest of the report computes return/risk in each stock's local currency. An investor
            with capital in EUR holding stocks in other currencies also bears a currency risk not
            modeled elsewhere: quantified here separately, as a first-order approximation (it does not
            account for correlations between currencies or between currency and equity).</p>
            <div class="table-scroll">
            <table class="data-table data-table--compact">
            <thead><tr><th>Currency</th><th class="num">% of Portfolio</th><th class="num">Annual FX Volatility</th></tr></thead>
            <tbody>{exp_rows}</tbody>
            </table>
            </div>
            <p class="muted-note" style="margin-top: 10px;">Total non-EUR exposure:
            <strong>{currency_risk_info['non_base_exposure']:.1%}</strong> — estimated volatility contribution:
            <strong>{currency_risk_info['estimated_fx_volatility_contribution']:.2%}</strong></p>
        </div>
        '''

    html += '</div>'
    return html


def create_correlation_analysis_section(correlation_matrix: pd.DataFrame,
                                       metrics: pd.DataFrame = None,
                                       threshold: float = None) -> str:
    """Creates an HTML section with a detailed correlation analysis"""

    if threshold is None:
        threshold = CORRELATION_CONFIG['high_correlation_threshold']

    if correlation_matrix.empty:
        return "<p>Insufficient data for correlation analysis</p>"

    # Find problematic pairs
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

    # Compute average correlations
    avg_corr = correlation_matrix.mean().sort_values(ascending=False)

    # Most correlated stocks (problematic)
    most_corr = avg_corr.head(10)
    # Least correlated stocks (good)
    least_corr = avg_corr.tail(10)

    html = '<div class="correlation-analysis">'

    # Summary box
    total_pairs = len(correlation_matrix) * (len(correlation_matrix) - 1) // 2
    high_pairs = len(high_corr_df)

    if high_pairs > 10:
        alert_icon = "⚠️"
        alert_msg = f"WARNING: {high_pairs} pairs with correlation >{threshold:.0%}"
        alert_class = "info-box--danger"
    elif high_pairs > 0:
        alert_icon = "⚠️"
        alert_msg = f"{high_pairs} pairs with correlation >{threshold:.0%} - Room for improvement"
        alert_class = "info-box--warning"
    else:
        alert_icon = "✅"
        alert_msg = "Excellent diversification! No pair with excessive correlation"
        alert_class = "info-box--success"

    html += f'''
    <div class="info-box {alert_class}">
        <h3>{alert_icon} {alert_msg}</h3>
        <p style="margin-top: 10px;">
            Out of {total_pairs} possible pairs, {high_pairs} have a correlation above {threshold:.0%}.
            {'A high correlation means the stocks move together, reducing real diversification.' if high_pairs > 0 else ''}
        </p>
    </div>
    '''

    # Problematic pairs table
    if not high_corr_df.empty:
        html += '''
        <h3 class="section-subtitle negative">🔴 Highly Correlated Pairs</h3>
        <div class="table-scroll">
        <table class="data-table data-table--danger">
        <thead>
            <tr>
                <th>#</th>
                <th>Ticker 1</th>
                <th>Ticker 2</th>
                <th class="num">Correlation</th>
                <th>Suggested Action</th>
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
                <td style="font-size: 0.9em;">Consider reducing or dropping one of the two</td>
            </tr>
            '''

        html += '</tbody></table></div>'

    # Two columns: most/least correlated stocks
    html += '''
    <div class="two-col-grid">
        <div>
            <h3 class="section-subtitle negative">📉 MOST Correlated Stocks</h3>
            <p class="muted-note">Candidates to reduce to improve diversification</p>
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
            <h3 class="section-subtitle positive">📈 LEAST Correlated Stocks</h3>
            <p class="muted-note">Best for diversification - consider increasing</p>
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
    """Creates an elegant HTML table for the optimal allocation"""

    if not suggested_weights:
        return "<p>No allocation available</p>"

    # Convert to a DataFrame
    df = pd.DataFrame(list(suggested_weights.items()), columns=['Ticker', 'Suggested Weight'])
    df = df.sort_values('Suggested Weight', ascending=False)

    # Add metrics if available
    if metrics is not None and not metrics.empty:
        metrics_dict = metrics.set_index('ticker')[['annual_return', 'annual_volatility', 'sharpe_ratio']].to_dict('index')

        df['Return'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('annual_return', 0))
        df['Volatility'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('annual_volatility', 0))
        df['Sharpe'] = df['Ticker'].map(lambda x: metrics_dict.get(x, {}).get('sharpe_ratio', 0))

    # Format the percentages
    df['Weight %'] = (df['Suggested Weight'] * 100).apply(lambda x: f'{x:.2f}%')

    # Build the HTML
    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>#</th>'
    html += '<th>Ticker</th>'
    html += '<th class="num">Suggested Weight</th>'

    if metrics is not None and not metrics.empty:
        html += '<th class="num">Return</th>'
        html += '<th class="num">Volatility</th>'
        html += '<th class="num">Sharpe</th>'

    html += '</tr></thead><tbody>'

    for idx, row in df.iterrows():
        html += '<tr>'
        html += f'<td>{idx + 1}</td>'
        html += f'<td><strong>{row["Ticker"]}</strong></td>'
        html += f'<td class="num accent"><strong>{row["Weight %"]}</strong></td>'

        if metrics is not None and not metrics.empty:
            html += f'<td class="num {_pct_class(row["Return"])}">{row["Return"]:.2%}</td>'
            html += f'<td class="num">{row["Volatility"]:.2%}</td>'
            html += f'<td class="num"><strong>{row["Sharpe"]:.2f}</strong></td>'

        html += '</tr>'

    html += '</tbody></table></div>'

    return html


def create_earnings_table(earnings_df: pd.DataFrame) -> str:
    """
    Creates an HTML table dedicated to the earnings of the stocks in the
    portfolio: trailing/forward EPS, earnings growth, margin, and the next
    release date with consensus estimates (expected EPS/revenue).

    Sorted by proximity of the next release (stocks with missing data,
    typically foreign ones outside Yahoo's coverage, at the bottom).
    """
    if earnings_df is None or earnings_df.empty:
        return "<p>Earnings data not available</p>"

    df = earnings_df.copy()

    def fmt_eps(row, col):
        val = row.get(col)
        if pd.isna(val):
            return 'n/a'
        cur = row.get('currency') if pd.notna(row.get('currency')) else ''
        return f"{val:.2f} {cur}".strip()

    def fmt_pct(val):
        return f'{val:+.1%}' if pd.notna(val) else 'n/a'

    def fmt_date(row):
        d = row.get('next_earnings_date')
        if pd.isna(d) or d is None:
            return 'n/a'
        days = row.get('days_to_earnings')
        days_str = f' ({int(days)}d)' if pd.notna(days) else ''
        return f'{d}{days_str}'

    def fmt_revenue(val):
        if pd.isna(val):
            return 'n/a'
        if val >= 1e9:
            return f'{val / 1e9:.2f} B'
        if val >= 1e6:
            return f'{val / 1e6:.1f} M'
        return f'{val:,.0f}'

    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>Ticker</th>'
    html += '<th class="num">EPS (trailing)</th>'
    html += '<th class="num">EPS (forward)</th>'
    html += '<th class="num">YoY Earnings Growth</th>'
    html += '<th class="num">Net Margin</th>'
    html += '<th>Next Release</th>'
    html += '<th class="num">Expected EPS (consensus)</th>'
    html += '<th class="num">Expected Revenue (consensus)</th>'
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
    Creates an HTML table dedicated to the dividends of the stocks in the
    portfolio: dividend per share, yield (computed by us, not from Yahoo's
    ambiguous field), payout ratio, next ex-dividend and payment date.

    Sorted by descending yield (non-dividend-paying stocks, e.g. growth
    stocks, at the bottom).
    """
    if dividend_df is None or dividend_df.empty:
        return "<p>Dividend data not available</p>"

    df = dividend_df.copy()

    def fmt_amount(row, col):
        val = row.get(col)
        if pd.isna(val):
            return 'n/a'
        cur = row.get('currency') if pd.notna(row.get('currency')) else ''
        return f"{val:.2f} {cur}".strip()

    def fmt_pct(val):
        return f'{val:.2%}' if pd.notna(val) else 'n/a'

    def fmt_date(val):
        return str(val) if pd.notna(val) and val is not None else 'n/a'

    html = '<div class="table-scroll">'
    html += '<table class="data-table">'
    html += '<thead><tr>'
    html += '<th>Ticker</th>'
    html += '<th class="num">Dividend/Share</th>'
    html += '<th class="num">Dividend Yield</th>'
    html += '<th class="num">Payout Ratio</th>'
    html += '<th>Next Ex-Dividend Date</th>'
    html += '<th>Next Payment Date</th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        no_dividend = pd.isna(row.get('dividend_rate')) or row.get('dividend_rate') == 0
        html += '<tr>'
        html += f'<td><strong>{row["ticker"]}</strong></td>'
        html += f'<td class="num">{"n/a (no dividend)" if no_dividend else fmt_amount(row, "dividend_rate")}</td>'
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
    """Creates the HTML section for the practical operational allocation"""

    if allocation_df.empty:
        return "<p>Allocation not available</p>"

    # Allocation pie chart
    pie_fig = px.pie(
        allocation_df,
        values='amount_eur',
        names='ticker',
        title=f'Practical Allocation - €{total_capital:,.0f}',
        color_discrete_sequence=CHART_COLORWAY,
        hole=0.4
    )

    pie_fig.update_traces(
        textposition='outside',
        textinfo='label+percent',
        textfont_size=11,
        textfont_color=THEME_CONFIG['text_primary'],
        marker=dict(line=dict(color=THEME_CONFIG['bg_card'], width=2)),
        hovertemplate='<b>%{label}</b><br>Amount: €%{value:,.0f}<br>Share: %{percent}<extra></extra>'
    )

    pie_fig.update_layout(_base_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05,
                   font=dict(color=THEME_CONFIG['text_primary'])),
        height=500,
    ))

    pie_html = pie_fig.to_html(include_plotlyjs='cdn', div_id="practical_allocation_pie", config={'responsive': True})

    # Detailed table
    table_html = '''
    <div class="table-scroll" style="margin-top: 30px;">
    <table class="data-table">
    <thead>
        <tr>
            <th>#</th>
            <th>Ticker</th>
            <th>Sector</th>
            <th class="num">Weight %</th>
            <th class="num">Amount €</th>
            <th class="num">Sharpe</th>
            <th class="num">Annual Return</th>
        </tr>
    </thead>
    <tbody>
    '''

    for idx, row in allocation_df.iterrows():
        table_html += f'''
        <tr>
            <td>{idx + 1}</td>
            <td class="accent"><strong>{row['ticker']}</strong></td>
            <td style="font-size: 0.9em;">{row['sector']}</td>
            <td class="num"><strong>{row['weight_pct']:.2f}%</strong></td>
            <td class="num positive"><strong>€{row['amount_eur']:,.2f}</strong></td>
            <td class="num">{row['sharpe_ratio']:.2f}</td>
            <td class="num {_pct_class(row['annual_return'])}">{row['annual_return']:.1%}</td>
        </tr>
        '''

    # Total row
    total_invested = allocation_df['amount_eur'].sum()
    table_html += f'''
        <tr class="data-table__total">
            <td colspan="4">TOTAL INVESTED:</td>
            <td class="num positive">€{total_invested:,.2f}</td>
            <td colspan="2"></td>
        </tr>
    '''

    if allocation_info['cash_amount'] > 0:
        table_html += f'''
        <tr class="data-table__cash">
            <td colspan="4">CASH:</td>
            <td class="num warning">€{allocation_info['cash_amount']:,.2f}</td>
            <td colspan="2" style="font-size: 0.9em;">({allocation_info['cash_percent']:.1f}%)</td>
        </tr>
        <tr class="data-table__grand-total">
            <td colspan="4">TOTAL PORTFOLIO:</td>
            <td class="num">€{total_capital:,.2f}</td>
            <td colspan="2"></td>
        </tr>
        '''

    table_html += '</tbody></table></div>'

    # Allocation info box
    info_html = f'''
    <div class="info-box">
        <h3>💼 Practical Allocation Information</h3>
        <div class="info-grid">
            <div>
                <strong>Total Capital:</strong><br>
                €{total_capital:,.2f}
            </div>
            <div>
                <strong>Selected Stocks:</strong><br>
                {allocation_info['n_stocks']} out of {len(PORTFOLIO_TICKERS)} available
            </div>
            <div>
                <strong>Average Correlation:</strong><br>
                {allocation_info['avg_correlation']:.1%} {'✅ Excellent' if allocation_info['avg_correlation'] < 0.3 else '⚠️ Room for improvement' if allocation_info['avg_correlation'] < 0.5 else '🔴 High'}
            </div>
            <div>
                <strong>Diversified Sectors:</strong><br>
                {len(allocation_info['sector_distribution'])} sectors
            </div>
        </div>
    </div>
    '''

    # Correlation matrix of the selection
    corr_matrix_html = ""
    if not allocation_info['correlation_matrix'].empty and len(allocation_info['selected_tickers']) > 1:
        corr_fig = px.imshow(
            allocation_info['correlation_matrix'],
            labels=dict(color="Correlation"),
            x=allocation_info['correlation_matrix'].columns,
            y=allocation_info['correlation_matrix'].index,
            color_continuous_scale=[[0, THEME_CONFIG['accent']], [0.5, THEME_CONFIG['bg_card_alt']], [1, THEME_CONFIG['negative']]],
            aspect="auto",
            title=f"Correlation Matrix of the Selected Portfolio ({allocation_info['n_stocks']} stocks)"
        )

        corr_fig.update_layout(_base_layout(
            height=max(400, allocation_info['n_stocks'] * 25),
            xaxis=_axis(tickangle=-45),
            yaxis=_axis(),
        ))

        corr_matrix_html = f'''
        <h3 class="section-subtitle accent">📊 Optimized Correlation Matrix</h3>
        <div class="info-box">
            <p>This matrix shows correlations only among the stocks selected for your capital.
            The stocks were chosen to minimize average correlation and maximize diversification.</p>
        </div>
        <div class="chart-container">
            {corr_fig.to_html(include_plotlyjs='cdn', div_id="practical_correlation_matrix", config={'responsive': True})}
        </div>
        '''

    # Full HTML
    full_html = f'''
    {info_html}
    <div class="chart-container" style="margin-top: 30px;">
        {pie_html}
    </div>
    <h3 class="section-subtitle accent">📋 Allocation Detail with Exact Amounts</h3>
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
    Generates the full HTML report
    """

    # "Why N stocks" section: real diversification curve, if available
    selection_section_html = ""
    if selection_info and selection_info.get('diversification_curve'):
        curve_chart = create_diversification_curve_chart(
            selection_info['diversification_curve'], selection_info.get('n_stocks')
        )
        binding = selection_info.get('binding_constraint')
        binding_label = "the available capital" if binding == 'capital' else "statistical diversification"
        selection_section_html = f'''
        <div class="section" id="number-of-stocks">
            <h2>Why {selection_info['n_stocks']} Stocks</h2>
            <div class="info-box">
                <h3>📐 Number of stocks chosen from the data, not fixed brackets</h3>
                <p>The number of stocks is no longer decided from arbitrary capital brackets: it is
                computed from the empirical minimum of the portfolio's real risk curve (the "naive
                diversification" principle of <em>Evans &amp; Archer, 1968</em> and <em>Elton &amp; Gruber,
                1977</em>) and constrained by the available capital. Stocks keep being added while risk
                keeps falling, stopping where it stops improving in a stable way (not at the first single
                low point, so as not to mistake a random dip in the curve for true convergence).</p>
                <div class="info-grid" style="margin-top: 15px;">
                    <div><strong>Optimal for diversification:</strong><br>{selection_info['statistically_optimal_n']} stocks
                    (empirical minimum of the risk curve)</div>
                    <div><strong>Affordable by the capital:</strong><br>{selection_info['capital_affordable_n']} stocks</div>
                    <div><strong>Most binding constraint:</strong><br>{binding_label}</div>
                    <div><strong>Stocks chosen:</strong><br>{selection_info['n_stocks']}</div>
                </div>
            </div>
            <div class="chart-container">
                {curve_chart}
            </div>
            <p class="muted-note">The chart shows the volatility of an equal-weighted portfolio as stocks
            are added in order of descending Sharpe: beyond the highlighted point, risk stops falling in a
            stable way (it may even rise slightly, if the next-ranked stocks are more volatile).</p>
        </div>
        '''

    # Prepare the charts
    charts = []

    # 1. Risk-Return Scatter
    charts.append(create_scatter_risk_return(metrics))

    # 2. Sector and geographic diversification
    sector_chart_idx = None
    geo_chart_idx = None

    if not sector_breakdown.empty:
        sector_chart_idx = len(charts)
        charts.append(create_pie_chart(
            sector_breakdown,
            'weight',
            sector_breakdown.columns[0],
            'Diversification by Sector'
        ))

    if not geographic_breakdown.empty:
        geo_chart_idx = len(charts)
        charts.append(create_pie_chart(
            geographic_breakdown,
            'weight',
            geographic_breakdown.columns[0],
            'Geographic Diversification'
        ))

    # 3. Correlations
    corr_chart_idx = None
    if not correlation_matrix.empty:
        corr_chart_idx = len(charts)
        charts.append(create_correlation_heatmap(correlation_matrix))
        # Build the detailed correlation analysis (threshold from config)
        correlation_analysis_html = create_correlation_analysis_section(correlation_matrix, metrics)
    else:
        correlation_analysis_html = "<p>Insufficient data for correlation analysis</p>"

    # 4. Optimal allocation (pie chart and table)
    alloc_chart_idx = None
    if suggested_weights:
        alloc_chart_idx = len(charts)
        charts.append(create_optimal_allocation_pie(suggested_weights, top_n=REPORT_CONFIG['top_n_allocation_pie']))
        allocation_table = create_allocation_table(suggested_weights, metrics)
    else:
        allocation_table = "<p>No suggested allocation available</p>"

    # 5. Allocation comparison (if a current one is available)
    comparison_chart_idx = None
    if current_weights and suggested_weights:
        comparison_chart_idx = len(charts)
        charts.append(create_allocation_comparison(current_weights, suggested_weights))

    # 6. Historical backtest
    backtest_chart_html = ""
    oos_comparison_html = ""
    if backtest_results is not None and not backtest_results.empty:
        backtest_chart_html = create_backtest_chart(backtest_results, backtest_stats or {}, oos_start_date)
        oos_comparison_html = create_oos_comparison_table(backtest_stats or {}, backtest_stats_oos or {})

    # 6B. Statistical validation: optimization methodology + walk-forward + currency risk
    validation_section_html = ""
    if walk_forward_stats or opt_info:
        validation_section_html = create_validation_section(walk_forward_stats, opt_info, currency_risk_info)

    # Add cash info if present
    cash_info_html = ""
    if cash_allocation > 0:
        equity_allocation = 1 - cash_allocation
        cash_info_html = f'''
        <div class="info-box info-box--success">
            <h3>💰 Cash Component</h3>
            <p><strong>Suggested allocation:</strong></p>
            <ul>
                <li><strong>{equity_allocation:.1%}</strong> in equities (optimized portfolio)</li>
                <li><strong>{cash_allocation:.1%}</strong> in cash</li>
            </ul>
            <p style="margin-top: 10px; font-size: 0.95em;">
                The cash component is computed based on portfolio volatility and market conditions.
                It acts as a safety buffer and an opportunity reserve for future rebalancing.
            </p>
        </div>
        '''

    # Portfolio statistics
    portfolio_stats_html = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Annual Return</h3>
            <p class="stat-value {_pct_class(portfolio_metrics.get('annual_return', 0))}">
                {portfolio_metrics.get('annual_return', 0):.2%}
            </p>
        </div>
        <div class="stat-card">
            <h3>Annual Volatility</h3>
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
            <h3>Diversification Score</h3>
            <p class="stat-value {'positive' if diversification_score > 70 else 'warning' if diversification_score > 50 else 'negative'}">
                {diversification_score:.1f}/100
            </p>
        </div>
        <div class="stat-card">
            <h3>Number of Stocks</h3>
            <p class="stat-value">{len(metrics)}</p>
        </div>
        <div class="stat-card">
            <h3>Effective Stocks (Effective N)</h3>
            <p class="stat-value">{(concentration_info or {}).get('effective_n', 0):.1f}</p>
        </div>
        <div class="stat-card">
            <h3>VaR 95% (daily)</h3>
            <p class="stat-value negative">{portfolio_metrics.get('var_95', 0):.2%}</p>
        </div>
        <div class="stat-card">
            <h3>CVaR 95% (daily)</h3>
            <p class="stat-value negative">{portfolio_metrics.get('cvar_95', 0):.2%}</p>
        </div>
    </div>
    """

    # Detailed metrics table
    top_n_metrics = REPORT_CONFIG['top_n_metrics_table']
    top_metrics_df = metrics.sort_values('sharpe_ratio', ascending=False).head(top_n_metrics).copy()

    # The P/E and the Sharpe need to be formatted separately, not as a
    # percentage: to_html's single float_format applies to all float
    # columns the same way, so the non-percentage columns are
    # pre-formatted here (otherwise a low P/E or a return above 1000%
    # could be mistaken for the other format based on magnitude alone)
    has_pe = 'trailing_pe' in top_metrics_df.columns
    if has_pe:
        top_metrics_df['trailing_pe'] = top_metrics_df['trailing_pe'].apply(
            lambda x: f'{x:.1f}x' if pd.notna(x) else 'n/a'
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

    # Navigation index: only the entries for sections actually present in the report
    nav_items = [('#metrics', '📈 Metrics')]
    if selection_section_html:
        nav_items.append(('#number-of-stocks', '📐 # of Stocks'))
    nav_items.append(('#risk-return', '🎯 Risk/Return'))
    if backtest_chart_html:
        nav_items.append(('#backtest', '📈 Backtest'))
    if validation_section_html:
        nav_items.append(('#validation', '🔬 Validation'))
    if sector_chart_idx is not None:
        nav_items.append(('#sectors', '🏭 Sectors'))
    if geo_chart_idx is not None:
        nav_items.append(('#geography', '🌍 Geography'))
    if corr_chart_idx is not None:
        nav_items.append(('#correlation', '🔗 Correlation'))
    if alloc_chart_idx is not None:
        nav_items.append(('#optimal-allocation', '💡 Optimal Allocation'))
    if comparison_chart_idx is not None:
        nav_items.append(('#comparison', '💼 Comparison'))
    if practical_allocation_df is not None and not practical_allocation_df.empty:
        nav_items.append(('#practical-allocation', '💰 Practical Allocation'))
    has_earnings = earnings_df is not None and not earnings_df.empty
    if has_earnings:
        nav_items.append(('#earnings', '💵 Earnings'))
    has_dividends = dividend_df is not None and not dividend_df.empty
    if has_dividends:
        nav_items.append(('#dividends', '💶 Dividends'))
    nav_items.append(('#stock-detail', '📋 Stock Detail'))

    nav_html = ''.join(f'<a href="{href}">{label}</a>' for href, label in nav_items)

    earnings_table_html = create_earnings_table(earnings_df) if has_earnings else ''
    dividend_table_html = create_dividend_table(dividend_df) if has_dividends else ''

    T = THEME_CONFIG

    # HTML template
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Analysis - {datetime.now().strftime('%d/%m/%Y')}</title>
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
                <h1>📊 STOCK PORTFOLIO ANALYSIS</h1>
                <p>Report generated on {datetime.now().strftime('%d/%m/%Y at %H:%M')}</p>
            </header>

            <nav class="section-nav">{nav_html}</nav>

            <div class="content">
                <div class="section" id="metrics">
                    <h2>Portfolio Metrics</h2>
                    {portfolio_stats_html}

                    <div class="info-box">
                        <h3>💡 Interpretation</h3>
                        <ul>
                            <li><strong>Sharpe Ratio &gt; 1:</strong> Excellent risk/return ratio</li>
                            <li><strong>Diversification Score &gt; 70:</strong> Well-diversified portfolio (combines average correlation and weight concentration)</li>
                            <li><strong>Max Drawdown:</strong> Worst loss from a peak (lower is better)</li>
                            <li><strong>Effective Stocks (Effective N):</strong> how many equal-weighted stocks match the portfolio's real concentration (e.g. 15 stocks with 50% in one of them weigh like ~3-4 equal-weighted stocks)</li>
                            <li><strong>Daily VaR 95%:</strong> on the worst 5% of days, the loss was at or beyond this value</li>
                            <li><strong>Daily CVaR 95%:</strong> average loss on days beyond the VaR threshold — more informative than the VaR about the real severity of the negative tail</li>
                        </ul>
                    </div>
                </div>

                {selection_section_html}

                <div class="section" id="risk-return">
                    <h2>Risk-Return Analysis</h2>
                    <div class="chart-container">
                        {charts[0]}
                    </div>
                </div>

                {f'''
                <div class="section" id="backtest">
                    <h2>Historical Backtest</h2>
                    <div class="info-box info-box--warning">
                        <h3>ℹ️ How to Read the Backtest</h3>
                        <p>This chart shows how the optimized portfolio would have performed over the analyzed period,
                        compared with the main market indices. <strong>Note:</strong> past performance does not guarantee future results.</p>
                        <p style="margin-top: 10px;">The shaded area (to the right of the "Out-of-Sample Start" dashed line)
                        is the data window <strong>never seen</strong> by scouting, smart selection and weight optimization:
                        it is the only part of the chart that constitutes an honest, non-circular test of the selection.</p>
                    </div>
                    <div class="chart-container">
                        {backtest_chart_html}
                    </div>
                    {oos_comparison_html}
                </div>
                ''' if backtest_chart_html else ''}

                {f'''
                <div class="section" id="validation">
                    <h2>Statistical Validation and Methodology</h2>
                    {validation_section_html}
                </div>
                ''' if validation_section_html else ''}

                {f'''
                <div class="section" id="sectors">
                    <h2>Sector Diversification</h2>
                    <div class="chart-container">
                        {charts[sector_chart_idx]}
                    </div>
                </div>
                ''' if sector_chart_idx is not None else ''}

                {f'''
                <div class="section" id="geography">
                    <h2>Geographic Diversification</h2>
                    <div class="chart-container">
                        {charts[geo_chart_idx]}
                    </div>
                </div>
                ''' if geo_chart_idx is not None else ''}

                {f'''
                <div class="section" id="correlation">
                    <h2>Correlation Matrix</h2>
                    <div class="chart-container">
                        {charts[corr_chart_idx]}
                    </div>

                    <h3 class="section-subtitle accent">📊 Detailed Correlation Analysis</h3>
                    {correlation_analysis_html}
                </div>
                ''' if corr_chart_idx is not None else ''}

                {f'''
                <div class="section" id="optimal-allocation">
                    <h2>Suggested Optimal Allocation</h2>
                    <div class="info-box">
                        <h3>📊 Allocation Strategy with Correlation Reduction</h3>
                        <p>This allocation is optimized taking into account:</p>
                        <ul>
                            <li><strong>Selected risk profile</strong> (risk/return trade-off)</li>
                            <li><strong>High correlation reduction</strong> - Stocks with average correlation >50% receive a reduced weight</li>
                            <li><strong>Diversification</strong> - Maximum weight {ALLOCATION_CONFIG['max_weight_per_stock']:.0%} per single stock</li>
                        </ul>
                        <p style="margin-top: 10px;"><em>Compare with the "Correlation Analysis" section to see which stocks were penalized.</em></p>
                    </div>
                    {cash_info_html}
                    <div class="chart-container">
                        {charts[alloc_chart_idx]}
                    </div>

                    <h3 class="section-subtitle accent">📋 Allocation Detail per Stock</h3>
                    {allocation_table}
                </div>
                ''' if alloc_chart_idx is not None else ''}

                {f'''
                <div class="section" id="comparison">
                    <h2>Comparison: Current vs Suggested Allocation</h2>
                    <div class="chart-container">
                        {charts[comparison_chart_idx]}
                    </div>
                </div>
                ''' if comparison_chart_idx is not None else ''}

                {f'''
                <div class="section section--highlight" id="practical-allocation">
                    <h2>💰 PRACTICAL OPERATIONAL ALLOCATION</h2>
                    <div class="info-box info-box--warning">
                        <h3>🎯 How to Invest Concretely</h3>
                        <p>This section translates theory into practice. Based on your capital of <strong>€{total_capital:,.2f}</strong>,
                        we selected <strong>{practical_allocation_info['n_stocks']} optimal stocks</strong> that balance:</p>
                        <ul>
                            <li><strong>Diversification</strong> - Average correlation {practical_allocation_info['avg_correlation']:.1%}</li>
                            <li><strong>Performance</strong> - Stocks with the best Sharpe Ratios</li>
                            <li><strong>Practicality</strong> - Manageable amounts per stock (min €500)</li>
                            <li><strong>Sectors</strong> - {len(practical_allocation_info['sector_distribution'])} different sectors</li>
                        </ul>
                        <p style="margin-top: 10px;"><em>💡 With less capital, focusing on a few well-chosen stocks is more effective than spreading too thin.</em></p>
                    </div>
                    {create_practical_allocation_section(practical_allocation_df, practical_allocation_info, total_capital)}
                </div>
                ''' if practical_allocation_df is not None and not practical_allocation_df.empty else ''}

                {f'''
                <div class="section" id="earnings">
                    <h2>💵 Earnings of the Stocks in the Portfolio</h2>
                    <p class="muted-note">
                        <strong>EPS (trailing)</strong>/<strong>(forward)</strong>: earnings per share over the last 12 months / expected over the
                        next 12 months, in the stock's local currency. <strong>YoY Earnings Growth</strong>: change in earnings
                        versus the same quarter a year earlier (negative = declining earnings). <strong>Net Margin</strong>:
                        net income over revenue. <strong>Next Release</strong>/<strong>Expected EPS</strong>/<strong>Expected Revenue</strong>:
                        date and analyst consensus estimates for the next quarterly report — these are forecasts, not certain figures, and for
                        some foreign stocks Yahoo Finance publishes none. Highlighted rows indicate a release within 14 days.
                    </p>
                    {earnings_table_html}
                </div>
                ''' if has_earnings else ''}

                {f'''
                <div class="section" id="dividends">
                    <h2>💶 Dividends of the Stocks in the Portfolio</h2>
                    <p class="muted-note">
                        <strong>Dividend/Share</strong>: declared annual dividend, in the stock's local currency.
                        <strong>Dividend Yield</strong>: computed by us as dividend/share divided by the latest real price
                        available (we do not use Yahoo's field, which is expressed inconsistently depending on the stock).
                        <strong>Payout Ratio</strong>: share of net income distributed as dividends (above 100% indicates
                        a dividend not covered by current earnings, a warning sign). <strong>Next Ex-Dividend Date</strong>
                        (the date from which buying the stock no longer entitles you to the next dividend) and
                        <strong>Next Payment Date</strong> are the dates known to Yahoo Finance; many stocks (particularly
                        growth stocks like PLTR, IONQ, NVDA) do not pay dividends.
                    </p>
                    {dividend_table_html}
                </div>
                ''' if has_dividends else ''}

                <div class="section" id="stock-detail">
                    <h2>Detailed Metrics for All Stocks (Top {top_n_metrics})</h2>
                    <p class="muted-note">
                        Note: <strong>var_95</strong> is the daily Value at Risk (not annualized).
                        <strong>trailing_pe</strong> is the current P/E (n/a if the company is not profitable or the data is unavailable).
                        <strong>overvaluation_percentile</strong> is how expensive a stock is relative only to peers in its own sector
                        (average of the P/E, PEG and P/B percentiles; 0% = the cheapest in the sector, 100% = the most expensive) — it penalizes
                        the inclusion of pricier stocks in the portfolio, it does not exclude them.
                    </p>
                    {metrics_table}
                </div>
            </div>

            <footer>
                <p>Generated with Python, yfinance and Plotly | Market data provided by Yahoo Finance</p>
                <p style="margin-top: 10px; font-size: 0.85em;">
                    ⚠️ Disclaimer: This report is for informational purposes only and does not constitute financial advice.
                </p>
            </footer>
        </div>
    </body>
    </html>
    """

    # Save the file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_template)

    return output_file
