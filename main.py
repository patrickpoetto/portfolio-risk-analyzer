#!/usr/bin/env python3
"""
Script principale per l'analisi del portafoglio azionario

Utilizzo:
    python main.py                          # Analisi portafoglio reale per capitale
    python main.py --capital 50000          # Specifica capitale da investire
    python main.py --full-universe          # Analizza tutti i titoli disponibili (esplorativo)
    python main.py --weighted               # Analisi con pesi da portfolio_config.py
    python main.py --period 2y              # Cambia periodo storico (1y, 2y, 5y, max)
    python main.py --risk aggressive        # Suggerimenti per profilo aggressivo
    python main.py --profile giorgio        # Usa capitale/rischio/periodo/holding da profiles/giorgio.json
    python main.py --profile giorgio --capital 20000   # Profilo + override puntuale di un campo
"""

import argparse
import math
import sys
from datetime import datetime
from typing import Dict

from portfolio_config import (
    PORTFOLIO_TICKERS,
    SECTOR_CLASSIFICATION,
    GEOGRAPHIC_CLASSIFICATION,
    EXAMPLE_HOLDINGS,
    DEFAULT_CONFIG,
    ALLOCATION_CONFIG,
    RISK_PROFILES,
    BACKTEST_CONFIG,
    RISK_FREE_RATE
)
from risk_analysis import (
    fetch_historical_data,
    split_in_sample_out_of_sample,
    calculate_metrics,
    calculate_correlation_matrix,
    calculate_portfolio_metrics,
    get_diversification_score,
    calculate_concentration
)
from html_report import generate_html_report
from backtest import run_backtest, calculate_smart_cash_allocation, infer_market_condition
from practical_allocation import (
    calculate_practical_allocation,
    select_portfolio,
    get_sector
)
from valuation import calculate_valuation_scores, merge_valuation, fetch_calendar_events
from optimization import optimize_portfolio, apply_sector_tilt
from validation import walk_forward_backtest, summarize_strategy_returns
from fx_risk import estimate_currency_risk
from profiles import load_profile, list_profiles

import pandas as pd


def classify_by_sectors(tickers: list, weights: Dict[str, float]) -> pd.DataFrame:
    """Classifica i ticker per settore con i loro pesi"""
    sector_weights = {}
    total_weight = sum(weights.values()) if weights else len(tickers)
    
    for sector, sector_tickers in SECTOR_CLASSIFICATION.items():
        weight = 0
        for ticker in sector_tickers:
            if ticker in tickers:
                weight += weights.get(ticker, 1/len(tickers))
        sector_weights[sector] = weight / total_weight if total_weight > 0 else 0
    
    # Aggiungi categoria "Altri" per ticker non classificati
    classified_tickers = set()
    for sector_tickers in SECTOR_CLASSIFICATION.values():
        classified_tickers.update(sector_tickers)
    
    other_weight = 0
    for ticker in tickers:
        if ticker not in classified_tickers:
            other_weight += weights.get(ticker, 1/len(tickers))
    
    if other_weight > 0:
        sector_weights["Altri"] = other_weight / total_weight
    
    df = pd.DataFrame(list(sector_weights.items()), columns=['Settore', 'weight'])
    return df[df['weight'] > 0].sort_values('weight', ascending=False)


def classify_by_geography(tickers: list, weights: Dict[str, float]) -> pd.DataFrame:
    """Classifica i ticker per area geografica con i loro pesi"""
    geo_weights = {}
    total_weight = sum(weights.values()) if weights else len(tickers)
    
    for region, region_tickers in GEOGRAPHIC_CLASSIFICATION.items():
        weight = 0
        for ticker in region_tickers:
            if ticker in tickers:
                weight += weights.get(ticker, 1/len(tickers))
        geo_weights[region] = weight / total_weight if total_weight > 0 else 0
    
    # Aggiungi categoria "Altri" per ticker non classificati
    classified_tickers = set()
    for region_tickers in GEOGRAPHIC_CLASSIFICATION.values():
        classified_tickers.update(region_tickers)
    
    other_weight = 0
    for ticker in tickers:
        if ticker not in classified_tickers:
            other_weight += weights.get(ticker, 1/len(tickers))
    
    if other_weight > 0:
        geo_weights["Altri"] = other_weight / total_weight
    
    df = pd.DataFrame(list(geo_weights.items()), columns=['Regione', 'weight'])
    return df[df['weight'] > 0].sort_values('weight', ascending=False)


def main():
    parser = argparse.ArgumentParser(
        description='Analisi completa del portafoglio azionario',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Esempi:
  python main.py                                    # Portafoglio reale per capitale default
  python main.py --capital 50000                    # Portafoglio reale per 50k
  python main.py --capital 5000 --risk aggressive   # 5k profilo aggressivo
  python main.py --full-universe                    # Analizza tutti i {len(PORTFOLIO_TICKERS)} titoli (esplorativo)
  python main.py --weighted                         # Usa pesi da EXAMPLE_HOLDINGS
  python main.py --period 2y                        # Dati storici 2 anni
        """
    )
    
    parser.add_argument(
        '--profile',
        default=None,
        help=f"Nome profilo da profiles/<nome>.json (capitale, rischio, periodo, holding). "
             f"Disponibili: {', '.join(list_profiles()) or 'nessuno'}"
    )

    # Default a None qui: dopo il parsing risolviamo con precedenza
    # CLI esplicita > profilo (--profile) > DEFAULT_CONFIG, invece di
    # forzare subito il valore di DEFAULT_CONFIG (che impedirebbe al
    # profilo di fare da sorgente intermedia).
    parser.add_argument(
        '--period',
        default=None,
        choices=['1y', '2y', '5y', 'max'],
        help=f'Periodo storico per i dati (default: {DEFAULT_CONFIG["period"]})'
    )

    parser.add_argument(
        '--weighted',
        action='store_true',
        help='Usa pesi da EXAMPLE_HOLDINGS (o dagli holding del profilo, se --profile è specificato)'
    )

    parser.add_argument(
        '--risk',
        default=None,
        choices=list(RISK_PROFILES.keys()),
        help=f'Profilo di rischio per suggerimenti allocazione (default: {DEFAULT_CONFIG["risk_profile"]})'
    )

    parser.add_argument(
        '--output',
        default=None,
        help=f'Nome del file HTML di output (default: {DEFAULT_CONFIG["output_file"]})'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=None,
        help=f'Capitale totale da investire in EUR (default: {DEFAULT_CONFIG["capital"]:.0f})'
    )

    parser.add_argument(
        '--full-universe',
        action='store_true',
        dest='full_universe',
        help='Analizza tutti i titoli disponibili (ignora capitale, modalità esplorativa)'
    )
    
    args = parser.parse_args()

    # Carica il profilo (se richiesto) e risolve i parametri con precedenza
    # CLI esplicita > profilo > DEFAULT_CONFIG. Così un profilo fornisce i
    # valori "di base" per una persona, ma un flag esplicito sulla riga di
    # comando può comunque sovrascrivere un singolo campo al volo.
    profile = None
    profile_holdings = {}
    if args.profile:
        try:
            profile = load_profile(args.profile)
        except (FileNotFoundError, ValueError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        profile_holdings = profile['holdings']

    args.period = args.period or (profile['period'] if profile else DEFAULT_CONFIG['period'])
    args.risk = args.risk or (profile['risk_profile'] if profile else DEFAULT_CONFIG['risk_profile'])
    args.output = args.output or (profile['output_file'] if profile else DEFAULT_CONFIG['output_file'])
    args.capital = args.capital if args.capital is not None else (profile['capital'] if profile else DEFAULT_CONFIG['capital'])
    if profile and profile.get('full_universe') and not args.full_universe:
        args.full_universe = True

    # Se il profilo ha holding reali, usali automaticamente come pesi
    # "attuali" per il confronto nel report (equivalente a --weighted con
    # EXAMPLE_HOLDINGS), senza dover passare --weighted a mano ogni volta
    if profile_holdings and not args.weighted:
        args.weighted = True

    holdings_source = profile_holdings if profile_holdings else EXAMPLE_HOLDINGS

    # Determina modalità
    mode = "ESPLORATIVA (Tutti i titoli)" if args.full_universe else f"PORTAFOGLIO REALE (€{args.capital:,.2f})"

    print("=" * 80)
    print("📊 ANALISI PORTAFOGLIO AZIONARIO")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if profile:
        print(f"Profilo:   {profile['name']} (profiles/{args.profile}.json)")
    print(f"Modalità: {mode}")
    print(f"Profilo rischio: {args.risk}")
    print(f"Periodo dati: {args.period}")
    print(f"Titoli disponibili: {len(PORTFOLIO_TICKERS)}")
    print("=" * 80)
    print()
    
    all_tickers = list(PORTFOLIO_TICKERS.keys())
    
    # =============================================================================
    # FASE 1: SCOUTING - Scarica dati di tutti i titoli per ranking
    # =============================================================================
    print("📥 FASE 1: Scouting iniziale...")
    print("-" * 80)
    print("Scaricamento dati di tutti i titoli per valutazione e ranking...")
    
    try:
        prices_all = fetch_historical_data(all_tickers, period=args.period)
    except Exception as e:
        print(f"❌ Errore durante lo scaricamento dei dati: {e}")
        sys.exit(1)
    
    successful_tickers = list(prices_all.columns)
    print(f"✅ Dati scaricati per {len(successful_tickers)}/{len(all_tickers)} ticker")

    # Riserva una finestra finale "out-of-sample" (mai vista da scouting,
    # selezione smart e ottimizzazione dei pesi): serve per un backtest onesto
    # in FASE 7, invece di valutare la selezione sugli stessi dati con cui è
    # stata scelta (circolare e sistematicamente troppo ottimistico)
    prices_in_sample, prices_oos, oos_days = split_in_sample_out_of_sample(
        prices_all,
        BACKTEST_CONFIG['out_of_sample_ratio'],
        BACKTEST_CONFIG['min_out_of_sample_days'],
        BACKTEST_CONFIG['max_out_of_sample_days']
    )

    oos_start_date = None
    if oos_days > 0:
        oos_start_date = prices_oos.index[0]
        print(f"📐 Split in-sample/out-of-sample: {len(prices_in_sample)} giorni per la selezione "
              f"(fino al {prices_in_sample.index[-1].strftime('%d/%m/%Y')}), "
              f"{oos_days} giorni di test riservati (dal {oos_start_date.strftime('%d/%m/%Y')})")
    else:
        print("⚠️  Storico troppo corto per uno split out-of-sample: scouting, selezione e "
              "backtest useranno tutti gli stessi dati (backtest solo in-sample, interpretalo con cautela)")

    # Calcola metriche preliminari per tutti, SOLO sulla finestra in-sample
    weights_all_uniform = {t: 1.0/len(successful_tickers) for t in successful_tickers}
    metrics_all = calculate_metrics(prices_in_sample, weights_all_uniform)
    correlation_all = calculate_correlation_matrix(prices_in_sample)

    print(f"✅ Metriche preliminari calcolate per tutti i {len(metrics_all)} ticker\n")

    # Dati di valutazione fondamentale (P/E, PEG, P/B) attuali: informazione
    # "di oggi", non derivata dallo storico prezzi, quindi calcolata una sola
    # volta e riutilizzata sia per lo scouting che per l'analisi successiva
    try:
        valuation_df = calculate_valuation_scores(successful_tickers)
    except Exception as e:
        print(f"⚠️  Errore nel recupero dati di valutazione: {str(e)[:100]}")
        valuation_df = None

    metrics_all = merge_valuation(metrics_all, valuation_df)
    
    # =============================================================================
    # FASE 2: SELEZIONE SMART (se non full-universe)
    # =============================================================================
    if not args.full_universe:
        print(f"🎯 FASE 2: Selezione smart portafoglio per €{args.capital:,.2f}...")
        print("-" * 80)

        # Numero di titoli: non più fasce di capitale hardcoded, ma il minimo
        # tra due vincoli calcolati sui dati reali (select_portfolio):
        #  1. statistico  → curva di diversificazione reale (Evans & Archer 1968 /
        #     Elton & Gruber 1977): oltre quale N il rischio si riduce ormai poco
        #  2. di capitale → quante posizioni da almeno min_position_size ci si
        #     può permettere (usando ~85% del capitale, il resto stimato liquidità)
        selected_tickers, selection_info = select_portfolio(
            metrics_all,
            correlation_all,
            args.capital * (1 - 0.15),
            args.risk,
            ALLOCATION_CONFIG['min_position_size']
        )

        if not selected_tickers:
            print(f"❌ Capitale (€{args.capital:,.2f}) insufficiente per costruire una posizione "
                  f"minima di €{ALLOCATION_CONFIG['min_position_size']:,.2f}. "
                  f"Aumenta --capital oppure abbassa 'min_position_size' in portfolio_config.py.")
            sys.exit(1)

        n_stocks = selection_info['n_stocks']
        print(f"Con capitale €{args.capital:,.2f}:")
        print(f"  • Liquidità prevista: ~15%  →  Capitale investibile: ~€{args.capital * 0.85:,.2f}")
        print(f"  • N° titoli 'ottimale' per diversificazione (minimo empirico "
              f"della curva di rischio reale): {selection_info['statistically_optimal_n']}")
        print(f"  • N° titoli sostenibili dal capitale (posizione min. €{ALLOCATION_CONFIG['min_position_size']:,.0f}): "
              f"{selection_info['capital_affordable_n']}")
        print(f"  • Vincolo più stringente: {selection_info['binding_constraint']} → N° titoli scelto: {n_stocks}")
        print(f"  • Investimento medio: ~€{(args.capital * 0.85) / n_stocks:,.2f} per titolo\n")

        print(f"✅ Titoli selezionati ({len(selected_tickers)}):")
        print(f"   {', '.join(selected_tickers[:10])}")
        if len(selected_tickers) > 10:
            print(f"   ... e altri {len(selected_tickers) - 10}")
        print()

        # FILTRA dati per titoli selezionati
        tickers_to_analyze = selected_tickers

        # Se il profilo chiede un tilt positivo su un settore, verifica che ci
        # siano abbastanza titoli di quel settore da poter accogliere il peso
        # target senza scontrarsi col cap "max peso per singolo titolo": un
        # tilt al 9% su un settore con un solo titolo e cap 6% non è
        # raggiungibile (un titolo solo non può pesare più del cap). Se serve,
        # aggiungi altri candidati (per Sharpe) dello stesso settore finché
        # n_titoli_settore * cap >= peso target del settore.
        if profile and profile.get('sector_tilts'):
            max_weight_per_stock = ALLOCATION_CONFIG['max_weight_per_stock']
            for sector, delta in profile['sector_tilts'].items():
                if delta <= 0:
                    continue

                sector_tickers_in_selection = [t for t in tickers_to_analyze if get_sector(t) == sector]
                # stima grezza (pesi uniformi) del peso attuale del settore:
                # la vera ottimizzazione avviene dopo, in FASE 6, ma qui serve
                # solo per capire se il tilt richiesto è raggiungibile
                current_weight_est = len(sector_tickers_in_selection) / len(tickers_to_analyze)
                target_weight_est = current_weight_est + delta
                required_min_tickers = max(1, math.ceil(target_weight_est / max_weight_per_stock))

                if len(sector_tickers_in_selection) < required_min_tickers:
                    n_to_add = required_min_tickers - len(sector_tickers_in_selection)
                    candidates = metrics_all[
                        metrics_all['ticker'].apply(get_sector) == sector
                    ]
                    candidates = candidates[~candidates['ticker'].isin(tickers_to_analyze)]
                    candidates = candidates.sort_values('sharpe_ratio', ascending=False)

                    added = candidates['ticker'].head(n_to_add).tolist()
                    if added:
                        tickers_to_analyze.extend(added)
                        print(f"ℹ️  Aggiunti {len(added)} titoli per '{sector}' (il tilt richiesto "
                              f"supererebbe il cap {max_weight_per_stock:.0%}/titolo su un solo titolo): "
                              f"{', '.join(added)}")
                    if len(added) < n_to_add:
                        print(f"⚠️  Solo {len(added)}/{n_to_add} candidati extra disponibili per '{sector}': "
                              f"il tilt potrebbe restare parzialmente limitato dal cap per titolo")
            print()

    else:
        print("🌍 FASE 2: Modalità universo completo...")
        print("-" * 80)
        print(f"Analizzando tutti i {len(successful_tickers)} titoli disponibili")
        print("(Modalità esplorativa - ignora allocazione pratica)\n")

        tickers_to_analyze = successful_tickers
        selection_info = None
    
    # =============================================================================
    # FASE 3: ANALISI APPROFONDITA - Solo su titoli selezionati
    # =============================================================================
    print(f"📊 FASE 3: Analisi approfondita portafoglio ({len(tickers_to_analyze)} titoli)...")
    print("-" * 80)
    
    # Filtra prezzi per titoli da analizzare (solo in-sample: le metriche
    # "attuali" del portafoglio devono restare coerenti con i dati che hanno
    # informato la selezione, senza contaminazione dalla finestra out-of-sample)
    prices = prices_in_sample[tickers_to_analyze]
    
    # Determina i pesi (da profilo se --profile con holding, altrimenti da EXAMPLE_HOLDINGS)
    if args.weighted and holdings_source:
        weights = {k: v for k, v in holdings_source.items() if k in tickers_to_analyze}
        if not weights:
            print("⚠️  Nessun holding valido tra i titoli selezionati, uso pesi uniformi")
            weights = {t: 1.0 for t in tickers_to_analyze}
    else:
        weights = {t: 1.0 for t in tickers_to_analyze}
        print("ℹ️  Uso pesi uniformi per il portafoglio")
    
    total = sum(weights.values())
    normalized_weights = {k: v/total for k, v in weights.items()}
    
    # Calcola metriche del portafoglio
    metrics = calculate_metrics(prices, normalized_weights)
    metrics = merge_valuation(metrics, valuation_df)
    correlation_matrix = calculate_correlation_matrix(prices)
    portfolio_metrics = calculate_portfolio_metrics(prices, normalized_weights)

    # Calendario prossimi utili/dividendi: solo per i titoli effettivamente
    # in portafoglio (non l'intero universo), interrogato qui perché è un
    # endpoint separato da .info e tickers_to_analyze è già definitivo
    calendar_df = fetch_calendar_events(tickers_to_analyze)

    earnings_cols = ['ticker', 'trailing_eps', 'forward_eps', 'earnings_growth', 'profit_margin', 'currency']
    earnings_cols = [c for c in earnings_cols if c in metrics.columns]
    earnings_df = metrics[earnings_cols].merge(
        calendar_df[['ticker', 'next_earnings_date', 'days_to_earnings', 'eps_estimate', 'revenue_estimate']],
        on='ticker', how='left'
    )
    earnings_df = earnings_df.sort_values('days_to_earnings', na_position='last')

    # Rendimento da dividendo calcolato da noi (dividend_rate / ultimo prezzo
    # reale disponibile su tutto lo storico scaricato, non solo in-sample),
    # invece del campo 'dividendYield' di Yahoo: a seconda del titolo/versione
    # dell'API è espresso in modo incoerente (frazione 0-1 oppure già in punti
    # percentuali), un rischio concreto di sbagliare l'ordine di grandezza
    last_price = prices_all[tickers_to_analyze].iloc[-1]
    dividend_cols = ['ticker', 'dividend_rate', 'payout_ratio', 'currency']
    dividend_cols = [c for c in dividend_cols if c in metrics.columns]
    dividend_df = metrics[dividend_cols].merge(
        calendar_df[['ticker', 'next_ex_dividend_date', 'next_dividend_pay_date']],
        on='ticker', how='left'
    )
    dividend_df['last_price'] = dividend_df['ticker'].map(last_price)
    # dividend_rate è già in pence per i titoli 'GBp'/'GBX' (corretto alla
    # fonte in valuation.fetch_valuation_metrics), quindi coerente in scala
    # con last_price qui sotto
    dividend_df['dividend_yield'] = dividend_df['dividend_rate'] / dividend_df['last_price']
    dividend_df.loc[dividend_df['dividend_rate'].isna() | (dividend_df['dividend_rate'] == 0),
                     'dividend_yield'] = None
    dividend_df = dividend_df.sort_values('dividend_yield', ascending=False, na_position='last')

    print(f"✅ Analisi completata per portafoglio di {len(tickers_to_analyze)} titoli")
    print(f"\nMetriche portafoglio:")
    print(f"  • Rendimento annuale:  {portfolio_metrics['annual_return']:>8.2%}")
    print(f"  • Volatilità annuale:  {portfolio_metrics['annual_volatility']:>8.2%}")
    print(f"  • Sharpe Ratio:        {portfolio_metrics['sharpe_ratio']:>8.2f}")
    print(f"  • Max Drawdown:        {portfolio_metrics['max_drawdown']:>8.2%}")
    print()
    
    # =============================================================================
    # FASE 4: DIVERSIFICAZIONE
    # =============================================================================
    print("🎯 FASE 4: Analisi diversificazione...")
    print("-" * 80)
    
    diversification_score = get_diversification_score(correlation_matrix, normalized_weights)
    concentration_info = calculate_concentration(normalized_weights)

    print(f"Score diversificazione: {diversification_score:.1f}/100")
    print(f"Numero effettivo di titoli (Effective N): {concentration_info['effective_n']:.1f} "
          f"su {len(tickers_to_analyze)} in portafoglio")

    if diversification_score > 70:
        print("✅ Eccellente diversificazione!")
    elif diversification_score > 50:
        print("⚠️  Diversificazione moderata")
    else:
        print("❌ Bassa diversificazione")
    print()
    
    # =============================================================================
    # FASE 5: BREAKDOWN SETTORIALE E GEOGRAFICO
    # =============================================================================
    print("🏭 FASE 5: Breakdown settoriale e geografico...")
    print("-" * 80)
    
    sector_breakdown = classify_by_sectors(tickers_to_analyze, normalized_weights)
    geographic_breakdown = classify_by_geography(tickers_to_analyze, normalized_weights)
    
    print("Top 5 settori:")
    for _, row in sector_breakdown.head(5).iterrows():
        print(f"  • {row['Settore']:.<30} {row['weight']:>6.1%}")
    print()
    
    print("Distribuzione geografica:")
    for _, row in geographic_breakdown.iterrows():
        print(f"  • {row['Regione']:.<30} {row['weight']:>6.1%}")
    print()
    
    # =============================================================================
    # FASE 6: OTTIMIZZAZIONE ALLOCAZIONE (mean-variance vera, con shrinkage)
    # =============================================================================
    print("💡 FASE 6: Ottimizzazione mean-variance (Markowitz, SLSQP)...")
    print("-" * 80)
    print(f"Profilo di rischio: {args.risk}")

    opt_weights_series, opt_info = optimize_portfolio(
        metrics,
        correlation_matrix,
        tickers_to_analyze,
        risk_free_rate=RISK_FREE_RATE,
        max_weight=ALLOCATION_CONFIG['max_weight_per_stock'],
        target_risk=args.risk,
        min_weight_factor=ALLOCATION_CONFIG['min_weight_factor']
    )

    if not opt_weights_series.empty:
        suggested_weights = opt_weights_series.to_dict()
        print(f"Obiettivo: {opt_info['objective']}  |  shrinkage rendimenti: "
              f"{opt_info['return_shrinkage']:.0%}  |  shrinkage covarianza: {opt_info['cov_shrinkage']:.0%}")

        # Tilt settoriale manuale da profilo (preferenza personale dichiarata
        # dall'investitore, applicata dopo l'ottimizzazione)
        if profile and profile.get('sector_tilts'):
            ticker_sector_map = {t: get_sector(t) for t in suggested_weights}
            suggested_weights = apply_sector_tilt(suggested_weights, ticker_sector_map, profile['sector_tilts'])
            print(f"\n📐 Tilt settoriale applicato (da profilo):")
            for sector, delta in profile['sector_tilts'].items():
                print(f"  • {sector:.<40} {delta:+.1%}")

        print(f"\nTop 10 pesi ottimizzati:")
        for ticker, w in sorted(suggested_weights.items(), key=lambda x: -x[1])[:10]:
            print(f"  • {ticker:.<10} {w:>6.1%}")
    else:
        suggested_weights = {}
        print("⚠️  Impossibile calcolare allocazione ottimizzata")

    # La colonna 'weight' di `metrics` era finora il placeholder uniforme
    # (1/N) usato in FASE 3 solo per calcolare le metriche "attuali" del
    # portafoglio: nella tabella dettaglio del report risultava quindi
    # identica per ogni titolo, un artefatto interno privo di significato
    # per chi legge. La aggiorniamo con l'allocazione ottimizzata (post
    # tilt settoriale) così riflette il peso realmente suggerito.
    if suggested_weights:
        metrics['weight'] = metrics['ticker'].map(suggested_weights).fillna(0.0)

    print()
    
    # =============================================================================
    # FASE 7: BACKTEST STORICO - Su portafoglio reale
    # =============================================================================
    print(f"📈 FASE 7: Backtest storico ({args.period})...")
    print("-" * 80)

    backtest_results = None
    backtest_stats = None
    backtest_stats_oos = None

    try:
        # Riusa i prezzi già scaricati in FASE 1 (in-sample + out-of-sample)
        # invece di un secondo download separato: elimina una chiamata di
        # rete ridondante e garantisce che il backtest copra esattamente lo
        # stesso periodo di --period, includendo la finestra out-of-sample
        prices_backtest = prices_all[tickers_to_analyze]

        if not prices_backtest.empty:
            backtest_results, backtest_stats, backtest_stats_oos = run_backtest(
                prices_backtest, suggested_weights, period=args.period, oos_days=oos_days
            )
            print("✅ Backtest completato")
            print(f"   Performance portafoglio (periodo intero, include dati in-sample): "
                  f"{backtest_stats.get('Portafoglio', {}).get('total_return', 0):+.1%}")
            if backtest_stats_oos:
                print(f"   Performance portafoglio (SOLO out-of-sample, test onesto): "
                      f"{backtest_stats_oos.get('Portafoglio', {}).get('total_return', 0):+.1%}")
        else:
            print(f"⚠️  Dati insufficienti per il backtest")
    except Exception as e:
        print(f"⚠️  Errore backtest: {str(e)[:100]}")

    # =============================================================================
    # FASE 7B: VALIDAZIONE STATISTICA (walk-forward multi-fold + bootstrap CI)
    # =============================================================================
    print("\n🔬 FASE 7B: Validazione walk-forward (multi-fold, con costi di transazione)...")
    print("-" * 80)

    walk_forward_stats = None
    try:
        wf_result = walk_forward_backtest(
            prices_all[tickers_to_analyze],
            risk_free_rate=RISK_FREE_RATE,
            max_weight=ALLOCATION_CONFIG['max_weight_per_stock'],
            target_risk=args.risk,
            n_folds=16,
            test_window_days=63,
            min_train_days=252,
            cost_bps=10.0
        )
        if wf_result['folds']:
            walk_forward_stats = {
                name: summarize_strategy_returns(ret, RISK_FREE_RATE)
                for name, ret in wf_result['returns'].items()
            }
            print(f"✅ Validazione completata su {len(wf_result['folds'])} fold "
                  f"(nessun fold si sovrappone al training che lo precede)")
            for name, stats in walk_forward_stats.items():
                if not stats:
                    continue
                print(f"   {name:.<25} Sharpe {stats['sharpe_ratio']:>5.2f} "
                      f"[CI90% {stats['sharpe_ci_low']:.2f}, {stats['sharpe_ci_high']:.2f}]  "
                      f"Rend.tot {stats['total_return']:+.1%}")
        else:
            print("⚠️  Dati insufficienti per la validazione walk-forward (serve uno storico più lungo)")
    except Exception as e:
        print(f"⚠️  Errore validazione walk-forward: {str(e)[:150]}")

    # =============================================================================
    # FASE 8: COMPONENTE LIQUIDITÀ
    # =============================================================================
    print("\n💰 FASE 8: Calcolo componente liquidità...")
    print("-" * 80)

    market_condition = infer_market_condition(backtest_results)
    print(f"Condizione di mercato rilevata: {market_condition}")

    cash_allocation = calculate_smart_cash_allocation(
        metrics,
        portfolio_metrics.get('annual_volatility', 0.20),
        market_condition=market_condition
    )

    print(f"Liquidità consigliata: {cash_allocation:.1%}")
    print(f"Allocazione azioni:    {1-cash_allocation:.1%}")

    # =============================================================================
    # FASE 8B: RISCHIO DI CAMBIO (disclosure, capitale in EUR)
    # =============================================================================
    print("\n💱 FASE 8B: Stima rischio di cambio (base EUR)...")
    print("-" * 80)

    currency_risk_info = None
    try:
        ticker_currencies = dict(zip(valuation_df['ticker'], valuation_df['currency'])) if valuation_df is not None else {}
        currency_risk_info = estimate_currency_risk(suggested_weights, ticker_currencies, base_currency="EUR", period=args.period)
        non_base = currency_risk_info['non_base_exposure']
        print(f"Esposizione a valute diverse da EUR: {non_base:.1%}")
        for cur, exp in sorted(currency_risk_info['exposure_by_currency'].items(), key=lambda x: -x[1]):
            if cur == 'EUR':
                continue
            vol = currency_risk_info['fx_volatility_by_currency'].get(cur)
            vol_str = f"vol FX annua {vol:.1%}" if vol is not None else "vol FX n/d"
            print(f"  • {cur}: {exp:.1%} del portafoglio ({vol_str})")
        print(f"Contributo di volatilità da cambio (stima approssimata, non copre correlazioni): "
              f"{currency_risk_info['estimated_fx_volatility_contribution']:.2%}")
    except Exception as e:
        print(f"⚠️  Errore stima rischio di cambio: {str(e)[:100]}")

    # =============================================================================
    # FASE 9: ALLOCAZIONE PRATICA (solo se non full-universe)
    # =============================================================================
    practical_allocation_df = None
    practical_allocation_info = None
    
    if not args.full_universe:
        print(f"\n💼 FASE 9: Allocazione pratica per €{args.capital:,.2f}...")
        print("-" * 80)
        
        try:
            if suggested_weights and not metrics.empty:
                practical_allocation_df, practical_allocation_info = calculate_practical_allocation(
                    total_capital=args.capital,
                    metrics=metrics,
                    correlation_matrix=correlation_matrix,
                    suggested_weights=suggested_weights,
                    cash_allocation=cash_allocation,
                    target_risk=args.risk,
                    min_position_size=ALLOCATION_CONFIG['min_position_size'],
                    # Riusa la stessa selezione della FASE 2: garantisce che
                    # l'allocazione pratica sia sugli stessi titoli analizzati
                    # nel resto del report (correlazioni, backtest, ecc.)
                    selected_tickers=tickers_to_analyze
                )
                print(f"✅ Allocazione pratica calcolata con cifre esatte")
            else:
                print("⚠️  Impossibile calcolare allocazione pratica")
        except Exception as e:
            print(f"⚠️  Errore: {str(e)[:100]}")
    else:
        print(f"\nℹ️  FASE 9: Allocazione pratica saltata (modalità full-universe)")
    
    # =============================================================================
    # FASE 10: GENERAZIONE REPORT HTML
    # =============================================================================
    final_phase = "9" if args.full_universe else "10"
    print(f"\n🎨 FASE {final_phase}: Generazione report HTML...")
    print("-" * 80)
    
    try:
        output_path = generate_html_report(
            metrics=metrics,
            correlation_matrix=correlation_matrix,
            sector_breakdown=sector_breakdown,
            geographic_breakdown=geographic_breakdown,
            portfolio_metrics=portfolio_metrics,
            diversification_score=diversification_score,
            concentration_info=concentration_info,
            selection_info=selection_info,
            current_weights=normalized_weights,
            suggested_weights=suggested_weights,
            backtest_results=backtest_results,
            backtest_stats=backtest_stats,
            backtest_stats_oos=backtest_stats_oos,
            oos_start_date=oos_start_date,
            walk_forward_stats=walk_forward_stats,
            currency_risk_info=currency_risk_info,
            opt_info=opt_info,
            cash_allocation=cash_allocation,
            practical_allocation_df=practical_allocation_df,
            practical_allocation_info=practical_allocation_info,
            earnings_df=earnings_df,
            dividend_df=dividend_df,
            total_capital=args.capital if not args.full_universe else None,
            output_file=args.output
        )
        
        print(f"✅ Report HTML generato: {output_path}")
        print(f"   Apri il file nel browser per visualizzare i grafici interattivi!")
        
    except Exception as e:
        print(f"❌ Errore nella generazione del report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("🎉 ANALISI COMPLETATA CON SUCCESSO!")
    print("=" * 80)
    
    # Riepilogo finale
    print("\n📋 RIEPILOGO:")
    print(f"  • Modalità: {mode}")
    print(f"  • Titoli nel portafoglio: {len(tickers_to_analyze)}")
    print(f"  • Rendimento portafoglio: {portfolio_metrics['annual_return']:.2%}")
    print(f"  • Sharpe Ratio: {portfolio_metrics['sharpe_ratio']:.2f}")
    print(f"  • Diversificazione: {diversification_score:.1f}/100")
    if not args.full_universe:
        print(f"  • Capitale allocato: €{args.capital:,.2f}")
    print(f"  • Report salvato in: {args.output}")
    print()


if __name__ == "__main__":
    main()
