#!/usr/bin/env python3
"""
Main script for stock portfolio analysis

Usage:
    python main.py                          # Real portfolio analysis for a given capital
    python main.py --capital 50000          # Specify capital to invest
    python main.py --full-universe          # Analyze all available tickers (exploratory)
    python main.py --weighted               # Analysis using weights from portfolio_config.py
    python main.py --period 2y              # Change the historical period (1y, 2y, 5y, max)
    python main.py --risk aggressive        # Suggestions for an aggressive profile
    python main.py --profile example        # Use capital/risk/period/holdings from profiles/example.json
    python main.py --profile example --capital 20000   # Profile + one-off override of a single field
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
    """Classifies tickers by sector with their weights"""
    sector_weights = {}
    total_weight = sum(weights.values()) if weights else len(tickers)

    for sector, sector_tickers in SECTOR_CLASSIFICATION.items():
        weight = 0
        for ticker in sector_tickers:
            if ticker in tickers:
                weight += weights.get(ticker, 1/len(tickers))
        sector_weights[sector] = weight / total_weight if total_weight > 0 else 0

    # Add an "Other" category for unclassified tickers
    classified_tickers = set()
    for sector_tickers in SECTOR_CLASSIFICATION.values():
        classified_tickers.update(sector_tickers)

    other_weight = 0
    for ticker in tickers:
        if ticker not in classified_tickers:
            other_weight += weights.get(ticker, 1/len(tickers))

    if other_weight > 0:
        sector_weights["Other"] = other_weight / total_weight

    df = pd.DataFrame(list(sector_weights.items()), columns=['Sector', 'weight'])
    return df[df['weight'] > 0].sort_values('weight', ascending=False)


def classify_by_geography(tickers: list, weights: Dict[str, float]) -> pd.DataFrame:
    """Classifies tickers by geographic area with their weights"""
    geo_weights = {}
    total_weight = sum(weights.values()) if weights else len(tickers)

    for region, region_tickers in GEOGRAPHIC_CLASSIFICATION.items():
        weight = 0
        for ticker in region_tickers:
            if ticker in tickers:
                weight += weights.get(ticker, 1/len(tickers))
        geo_weights[region] = weight / total_weight if total_weight > 0 else 0

    # Add an "Other" category for unclassified tickers
    classified_tickers = set()
    for region_tickers in GEOGRAPHIC_CLASSIFICATION.values():
        classified_tickers.update(region_tickers)

    other_weight = 0
    for ticker in tickers:
        if ticker not in classified_tickers:
            other_weight += weights.get(ticker, 1/len(tickers))

    if other_weight > 0:
        geo_weights["Other"] = other_weight / total_weight

    df = pd.DataFrame(list(geo_weights.items()), columns=['Region', 'weight'])
    return df[df['weight'] > 0].sort_values('weight', ascending=False)


def main():
    parser = argparse.ArgumentParser(
        description='Full stock portfolio analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python main.py                                    # Real portfolio for the default capital
  python main.py --capital 50000                    # Real portfolio for 50k
  python main.py --capital 5000 --risk aggressive   # 5k, aggressive profile
  python main.py --full-universe                    # Analyze all {len(PORTFOLIO_TICKERS)} tickers (exploratory)
  python main.py --weighted                         # Use weights from EXAMPLE_HOLDINGS
  python main.py --period 2y                        # 2 years of historical data
        """
    )

    parser.add_argument(
        '--profile',
        default=None,
        help=f"Profile name from profiles/<name>.json (capital, risk, period, holdings). "
             f"Available: {', '.join(list_profiles()) or 'none'}"
    )

    # Default to None here: after parsing we resolve with precedence
    # explicit CLI > profile (--profile) > DEFAULT_CONFIG, instead of
    # immediately forcing the DEFAULT_CONFIG value (which would prevent the
    # profile from acting as an intermediate source).
    parser.add_argument(
        '--period',
        default=None,
        choices=['1y', '2y', '5y', 'max'],
        help=f'Historical period for the data (default: {DEFAULT_CONFIG["period"]})'
    )

    parser.add_argument(
        '--weighted',
        action='store_true',
        help='Use weights from EXAMPLE_HOLDINGS (or from the profile holdings, if --profile is given)'
    )

    parser.add_argument(
        '--risk',
        default=None,
        choices=list(RISK_PROFILES.keys()),
        help=f'Risk profile for allocation suggestions (default: {DEFAULT_CONFIG["risk_profile"]})'
    )

    parser.add_argument(
        '--output',
        default=None,
        help=f'Output HTML file name (default: {DEFAULT_CONFIG["output_file"]})'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=None,
        help=f'Total capital to invest in EUR (default: {DEFAULT_CONFIG["capital"]:.0f})'
    )

    parser.add_argument(
        '--full-universe',
        action='store_true',
        dest='full_universe',
        help='Analyze all available tickers (ignores capital, exploratory mode)'
    )

    args = parser.parse_args()

    # Load the profile (if requested) and resolve parameters with
    # precedence explicit CLI > profile > DEFAULT_CONFIG. This way a
    # profile provides "base" values for a person, but an explicit
    # command-line flag can still override a single field on the fly.
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

    # If the profile has real holdings, automatically use them as the
    # "current" weights for the comparison in the report (equivalent to
    # --weighted with EXAMPLE_HOLDINGS), without having to pass --weighted
    # by hand every time
    if profile_holdings and not args.weighted:
        args.weighted = True

    holdings_source = profile_holdings if profile_holdings else EXAMPLE_HOLDINGS

    # Determine the mode
    mode = "EXPLORATORY (All tickers)" if args.full_universe else f"REAL PORTFOLIO (€{args.capital:,.2f})"

    print("=" * 80)
    print("📊 STOCK PORTFOLIO ANALYSIS")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if profile:
        print(f"Profile:   {profile['name']} (profiles/{args.profile}.json)")
    print(f"Mode: {mode}")
    print(f"Risk profile: {args.risk}")
    print(f"Data period: {args.period}")
    print(f"Available tickers: {len(PORTFOLIO_TICKERS)}")
    print("=" * 80)
    print()

    all_tickers = list(PORTFOLIO_TICKERS.keys())

    # =============================================================================
    # PHASE 1: SCOUTING - Download data for all tickers for ranking
    # =============================================================================
    print("📥 PHASE 1: Initial scouting...")
    print("-" * 80)
    print("Downloading data for all tickers for evaluation and ranking...")

    try:
        prices_all = fetch_historical_data(all_tickers, period=args.period)
    except Exception as e:
        print(f"❌ Error while downloading data: {e}")
        sys.exit(1)

    successful_tickers = list(prices_all.columns)
    print(f"✅ Data downloaded for {len(successful_tickers)}/{len(all_tickers)} tickers")

    # Reserve a final "out-of-sample" window (never seen by scouting, smart
    # selection or weight optimization): used for an honest backtest in
    # PHASE 7, instead of evaluating the selection on the same data used to
    # choose it (circular and systematically over-optimistic)
    prices_in_sample, prices_oos, oos_days = split_in_sample_out_of_sample(
        prices_all,
        BACKTEST_CONFIG['out_of_sample_ratio'],
        BACKTEST_CONFIG['min_out_of_sample_days'],
        BACKTEST_CONFIG['max_out_of_sample_days']
    )

    oos_start_date = None
    if oos_days > 0:
        oos_start_date = prices_oos.index[0]
        print(f"📐 In-sample/out-of-sample split: {len(prices_in_sample)} days for selection "
              f"(up to {prices_in_sample.index[-1].strftime('%d/%m/%Y')}), "
              f"{oos_days} days of test data held back (from {oos_start_date.strftime('%d/%m/%Y')})")
    else:
        print("⚠️  History too short for an out-of-sample split: scouting, selection and "
              "backtest will all use the same data (in-sample only backtest, interpret with caution)")

    # Compute preliminary metrics for everyone, ONLY on the in-sample window
    weights_all_uniform = {t: 1.0/len(successful_tickers) for t in successful_tickers}
    metrics_all = calculate_metrics(prices_in_sample, weights_all_uniform)
    correlation_all = calculate_correlation_matrix(prices_in_sample)

    print(f"✅ Preliminary metrics computed for all {len(metrics_all)} tickers\n")

    # Current fundamental valuation data (P/E, PEG, P/B): "today's"
    # information, not derived from the price history, so it is computed
    # once and reused both for scouting and for the later analysis
    try:
        valuation_df = calculate_valuation_scores(successful_tickers)
    except Exception as e:
        print(f"⚠️  Error fetching valuation data: {str(e)[:100]}")
        valuation_df = None

    metrics_all = merge_valuation(metrics_all, valuation_df)

    # =============================================================================
    # PHASE 2: SMART SELECTION (if not full-universe)
    # =============================================================================
    if not args.full_universe:
        print(f"🎯 PHASE 2: Smart portfolio selection for €{args.capital:,.2f}...")
        print("-" * 80)

        # Number of stocks: no more hardcoded capital brackets, instead the
        # minimum of two constraints computed on real data (select_portfolio):
        #  1. statistical → the real diversification curve (Evans & Archer
        #     1968 / Elton & Gruber 1977): beyond which N risk reduction
        #     becomes negligible
        #  2. capital-based → how many positions of at least min_position_size
        #     can be afforded (using ~85% of the capital, the rest estimated as cash)
        selected_tickers, selection_info = select_portfolio(
            metrics_all,
            correlation_all,
            args.capital * (1 - 0.15),
            args.risk,
            ALLOCATION_CONFIG['min_position_size']
        )

        if not selected_tickers:
            print(f"❌ Capital (€{args.capital:,.2f}) is insufficient to build a minimum "
                  f"position of €{ALLOCATION_CONFIG['min_position_size']:,.2f}. "
                  f"Increase --capital or lower 'min_position_size' in portfolio_config.py.")
            sys.exit(1)

        n_stocks = selection_info['n_stocks']
        print(f"With capital €{args.capital:,.2f}:")
        print(f"  • Expected cash reserve: ~15%  →  Investable capital: ~€{args.capital * 0.85:,.2f}")
        print(f"  • 'Optimal' number of stocks for diversification (empirical minimum "
              f"of the real risk curve): {selection_info['statistically_optimal_n']}")
        print(f"  • Number of stocks affordable by the capital (min. position €{ALLOCATION_CONFIG['min_position_size']:,.0f}): "
              f"{selection_info['capital_affordable_n']}")
        print(f"  • Most binding constraint: {selection_info['binding_constraint']} → number of stocks chosen: {n_stocks}")
        print(f"  • Average investment: ~€{(args.capital * 0.85) / n_stocks:,.2f} per stock\n")

        print(f"✅ Selected stocks ({len(selected_tickers)}):")
        print(f"   {', '.join(selected_tickers[:10])}")
        if len(selected_tickers) > 10:
            print(f"   ... and {len(selected_tickers) - 10} more")
        print()

        # FILTER data for the selected tickers
        tickers_to_analyze = selected_tickers

        # If the profile requests a positive tilt on a sector, check that
        # there are enough stocks in that sector to accommodate the target
        # weight without hitting the "max weight per single stock" cap: a
        # 9% tilt on a sector with a single stock and a 6% cap is not
        # reachable (a single stock cannot exceed the cap). If needed, add
        # more candidates (by Sharpe) from the same sector until
        # n_sector_stocks * cap >= the sector's target weight.
        if profile and profile.get('sector_tilts'):
            max_weight_per_stock = ALLOCATION_CONFIG['max_weight_per_stock']
            for sector, delta in profile['sector_tilts'].items():
                if delta <= 0:
                    continue

                sector_tickers_in_selection = [t for t in tickers_to_analyze if get_sector(t) == sector]
                # rough estimate (uniform weights) of the sector's current
                # weight: the real optimization happens later, in PHASE 6,
                # but here we only need to know whether the requested tilt
                # is reachable
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
                        print(f"ℹ️  Added {len(added)} stocks for '{sector}' (the requested tilt "
                              f"would exceed the {max_weight_per_stock:.0%}/stock cap on a single stock): "
                              f"{', '.join(added)}")
                    if len(added) < n_to_add:
                        print(f"⚠️  Only {len(added)}/{n_to_add} extra candidates available for '{sector}': "
                              f"the tilt may remain partially limited by the per-stock cap")
            print()

    else:
        print("🌍 PHASE 2: Full universe mode...")
        print("-" * 80)
        print(f"Analyzing all {len(successful_tickers)} available tickers")
        print("(Exploratory mode - ignores practical allocation)\n")

        tickers_to_analyze = successful_tickers
        selection_info = None

    # =============================================================================
    # PHASE 3: IN-DEPTH ANALYSIS - Selected tickers only
    # =============================================================================
    print(f"📊 PHASE 3: In-depth portfolio analysis ({len(tickers_to_analyze)} tickers)...")
    print("-" * 80)

    # Filter prices for the tickers to analyze (in-sample only: the
    # portfolio's "current" metrics must stay consistent with the data that
    # informed the selection, without contamination from the out-of-sample
    # window)
    prices = prices_in_sample[tickers_to_analyze]

    # Determine the weights (from the profile if --profile with holdings, otherwise from EXAMPLE_HOLDINGS)
    if args.weighted and holdings_source:
        weights = {k: v for k, v in holdings_source.items() if k in tickers_to_analyze}
        if not weights:
            print("⚠️  No valid holdings among the selected tickers, using uniform weights")
            weights = {t: 1.0 for t in tickers_to_analyze}
    else:
        weights = {t: 1.0 for t in tickers_to_analyze}
        print("ℹ️  Using uniform weights for the portfolio")

    total = sum(weights.values())
    normalized_weights = {k: v/total for k, v in weights.items()}

    # Compute portfolio metrics
    metrics = calculate_metrics(prices, normalized_weights)
    metrics = merge_valuation(metrics, valuation_df)
    correlation_matrix = calculate_correlation_matrix(prices)
    portfolio_metrics = calculate_portfolio_metrics(prices, normalized_weights)

    # Upcoming earnings/dividend calendar: only for the tickers actually in
    # the portfolio (not the whole universe), queried here because it's a
    # separate endpoint from .info and tickers_to_analyze is now final
    calendar_df = fetch_calendar_events(tickers_to_analyze)

    earnings_cols = ['ticker', 'trailing_eps', 'forward_eps', 'earnings_growth', 'profit_margin', 'currency']
    earnings_cols = [c for c in earnings_cols if c in metrics.columns]
    earnings_df = metrics[earnings_cols].merge(
        calendar_df[['ticker', 'next_earnings_date', 'days_to_earnings', 'eps_estimate', 'revenue_estimate']],
        on='ticker', how='left'
    )
    earnings_df = earnings_df.sort_values('days_to_earnings', na_position='last')

    # Dividend yield computed by us (dividend_rate / the latest real price
    # available over the whole downloaded history, not just in-sample),
    # instead of Yahoo's 'dividendYield' field: depending on the
    # stock/API version it is expressed inconsistently (a 0-1 fraction or
    # already in percentage points), a real risk of getting the order of
    # magnitude wrong
    last_price = prices_all[tickers_to_analyze].iloc[-1]
    dividend_cols = ['ticker', 'dividend_rate', 'payout_ratio', 'currency']
    dividend_cols = [c for c in dividend_cols if c in metrics.columns]
    dividend_df = metrics[dividend_cols].merge(
        calendar_df[['ticker', 'next_ex_dividend_date', 'next_dividend_pay_date']],
        on='ticker', how='left'
    )
    dividend_df['last_price'] = dividend_df['ticker'].map(last_price)
    # dividend_rate is already in pence for 'GBp'/'GBX' stocks (corrected at
    # the source in valuation.fetch_valuation_metrics), so it is consistent
    # in scale with last_price below
    dividend_df['dividend_yield'] = dividend_df['dividend_rate'] / dividend_df['last_price']
    dividend_df.loc[dividend_df['dividend_rate'].isna() | (dividend_df['dividend_rate'] == 0),
                     'dividend_yield'] = None
    dividend_df = dividend_df.sort_values('dividend_yield', ascending=False, na_position='last')

    print(f"✅ Analysis complete for a portfolio of {len(tickers_to_analyze)} stocks")
    print(f"\nPortfolio metrics:")
    print(f"  • Annual return:     {portfolio_metrics['annual_return']:>8.2%}")
    print(f"  • Annual volatility: {portfolio_metrics['annual_volatility']:>8.2%}")
    print(f"  • Sharpe Ratio:      {portfolio_metrics['sharpe_ratio']:>8.2f}")
    print(f"  • Max Drawdown:      {portfolio_metrics['max_drawdown']:>8.2%}")
    print()

    # =============================================================================
    # PHASE 4: DIVERSIFICATION
    # =============================================================================
    print("🎯 PHASE 4: Diversification analysis...")
    print("-" * 80)

    diversification_score = get_diversification_score(correlation_matrix, normalized_weights)
    concentration_info = calculate_concentration(normalized_weights)

    print(f"Diversification score: {diversification_score:.1f}/100")
    print(f"Effective number of stocks (Effective N): {concentration_info['effective_n']:.1f} "
          f"out of {len(tickers_to_analyze)} in the portfolio")

    if diversification_score > 70:
        print("✅ Excellent diversification!")
    elif diversification_score > 50:
        print("⚠️  Moderate diversification")
    else:
        print("❌ Low diversification")
    print()

    # =============================================================================
    # PHASE 5: SECTOR AND GEOGRAPHIC BREAKDOWN
    # =============================================================================
    print("🏭 PHASE 5: Sector and geographic breakdown...")
    print("-" * 80)

    sector_breakdown = classify_by_sectors(tickers_to_analyze, normalized_weights)
    geographic_breakdown = classify_by_geography(tickers_to_analyze, normalized_weights)

    print("Top 5 sectors:")
    for _, row in sector_breakdown.head(5).iterrows():
        print(f"  • {row['Sector']:.<30} {row['weight']:>6.1%}")
    print()

    print("Geographic distribution:")
    for _, row in geographic_breakdown.iterrows():
        print(f"  • {row['Region']:.<30} {row['weight']:>6.1%}")
    print()

    # =============================================================================
    # PHASE 6: ALLOCATION OPTIMIZATION (real mean-variance, with shrinkage)
    # =============================================================================
    print("💡 PHASE 6: Mean-variance optimization (Markowitz, SLSQP)...")
    print("-" * 80)
    print(f"Risk profile: {args.risk}")

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
        print(f"Objective: {opt_info['objective']}  |  return shrinkage: "
              f"{opt_info['return_shrinkage']:.0%}  |  covariance shrinkage: {opt_info['cov_shrinkage']:.0%}")

        # Manual sector tilt from the profile (personal preference stated
        # by the investor, applied after optimization)
        if profile and profile.get('sector_tilts'):
            ticker_sector_map = {t: get_sector(t) for t in suggested_weights}
            suggested_weights = apply_sector_tilt(suggested_weights, ticker_sector_map, profile['sector_tilts'])
            print(f"\n📐 Sector tilt applied (from profile):")
            for sector, delta in profile['sector_tilts'].items():
                print(f"  • {sector:.<40} {delta:+.1%}")

        print(f"\nTop 10 optimized weights:")
        for ticker, w in sorted(suggested_weights.items(), key=lambda x: -x[1])[:10]:
            print(f"  • {ticker:.<10} {w:>6.1%}")
    else:
        suggested_weights = {}
        print("⚠️  Unable to compute an optimized allocation")

    # The 'weight' column of `metrics` was, until now, the uniform
    # placeholder (1/N) used in PHASE 3 only to compute the portfolio's
    # "current" metrics: in the detailed report table it therefore looked
    # identical for every stock, an internal artifact with no meaning for
    # the reader. We update it with the optimized allocation (after the
    # sector tilt) so it reflects the actually suggested weight.
    if suggested_weights:
        metrics['weight'] = metrics['ticker'].map(suggested_weights).fillna(0.0)

    print()

    # =============================================================================
    # PHASE 7: HISTORICAL BACKTEST - On the real portfolio
    # =============================================================================
    print(f"📈 PHASE 7: Historical backtest ({args.period})...")
    print("-" * 80)

    backtest_results = None
    backtest_stats = None
    backtest_stats_oos = None

    try:
        # Reuse the prices already downloaded in PHASE 1 (in-sample +
        # out-of-sample) instead of a second separate download: avoids a
        # redundant network call and guarantees the backtest covers exactly
        # the same period as --period, including the out-of-sample window
        prices_backtest = prices_all[tickers_to_analyze]

        if not prices_backtest.empty:
            backtest_results, backtest_stats, backtest_stats_oos = run_backtest(
                prices_backtest, suggested_weights, period=args.period, oos_days=oos_days
            )
            print("✅ Backtest complete")
            print(f"   Portfolio performance (whole period, includes in-sample data): "
                  f"{backtest_stats.get('Portfolio', {}).get('total_return', 0):+.1%}")
            if backtest_stats_oos:
                print(f"   Portfolio performance (OUT-OF-SAMPLE ONLY, honest test): "
                      f"{backtest_stats_oos.get('Portfolio', {}).get('total_return', 0):+.1%}")
        else:
            print(f"⚠️  Insufficient data for the backtest")
    except Exception as e:
        print(f"⚠️  Backtest error: {str(e)[:100]}")

    # =============================================================================
    # PHASE 7B: STATISTICAL VALIDATION (multi-fold walk-forward + bootstrap CI)
    # =============================================================================
    print("\n🔬 PHASE 7B: Walk-forward validation (multi-fold, with transaction costs)...")
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
            print(f"✅ Validation complete over {len(wf_result['folds'])} folds "
                  f"(no fold overlaps with the training data preceding it)")
            for name, stats in walk_forward_stats.items():
                if not stats:
                    continue
                print(f"   {name:.<25} Sharpe {stats['sharpe_ratio']:>5.2f} "
                      f"[CI90% {stats['sharpe_ci_low']:.2f}, {stats['sharpe_ci_high']:.2f}]  "
                      f"Total ret. {stats['total_return']:+.1%}")
        else:
            print("⚠️  Insufficient data for walk-forward validation (a longer history is needed)")
    except Exception as e:
        print(f"⚠️  Walk-forward validation error: {str(e)[:150]}")

    # =============================================================================
    # PHASE 8: CASH COMPONENT
    # =============================================================================
    print("\n💰 PHASE 8: Computing the cash component...")
    print("-" * 80)

    market_condition = infer_market_condition(backtest_results)
    print(f"Detected market condition: {market_condition}")

    cash_allocation = calculate_smart_cash_allocation(
        metrics,
        portfolio_metrics.get('annual_volatility', 0.20),
        market_condition=market_condition
    )

    print(f"Recommended cash:  {cash_allocation:.1%}")
    print(f"Equity allocation: {1-cash_allocation:.1%}")

    # =============================================================================
    # PHASE 8B: CURRENCY RISK (disclosure, capital in EUR)
    # =============================================================================
    print("\n💱 PHASE 8B: Currency risk estimate (EUR base)...")
    print("-" * 80)

    currency_risk_info = None
    try:
        ticker_currencies = dict(zip(valuation_df['ticker'], valuation_df['currency'])) if valuation_df is not None else {}
        currency_risk_info = estimate_currency_risk(suggested_weights, ticker_currencies, base_currency="EUR", period=args.period)
        non_base = currency_risk_info['non_base_exposure']
        print(f"Exposure to non-EUR currencies: {non_base:.1%}")
        for cur, exp in sorted(currency_risk_info['exposure_by_currency'].items(), key=lambda x: -x[1]):
            if cur == 'EUR':
                continue
            vol = currency_risk_info['fx_volatility_by_currency'].get(cur)
            vol_str = f"annual FX vol {vol:.1%}" if vol is not None else "FX vol n/a"
            print(f"  • {cur}: {exp:.1%} of the portfolio ({vol_str})")
        print(f"Volatility contribution from FX (rough estimate, does not cover correlations): "
              f"{currency_risk_info['estimated_fx_volatility_contribution']:.2%}")
    except Exception as e:
        print(f"⚠️  Error estimating currency risk: {str(e)[:100]}")

    # =============================================================================
    # PHASE 9: PRACTICAL ALLOCATION (only if not full-universe)
    # =============================================================================
    practical_allocation_df = None
    practical_allocation_info = None

    if not args.full_universe:
        print(f"\n💼 PHASE 9: Practical allocation for €{args.capital:,.2f}...")
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
                    # Reuse the same selection from PHASE 2: guarantees that
                    # the practical allocation covers the same stocks
                    # analyzed in the rest of the report (correlations,
                    # backtest, etc.)
                    selected_tickers=tickers_to_analyze
                )
                print(f"✅ Practical allocation computed with exact amounts")
            else:
                print("⚠️  Unable to compute a practical allocation")
        except Exception as e:
            print(f"⚠️  Error: {str(e)[:100]}")
    else:
        print(f"\nℹ️  PHASE 9: Practical allocation skipped (full-universe mode)")

    # =============================================================================
    # PHASE 10: HTML REPORT GENERATION
    # =============================================================================
    final_phase = "9" if args.full_universe else "10"
    print(f"\n🎨 PHASE {final_phase}: Generating HTML report...")
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

        print(f"✅ HTML report generated: {output_path}")
        print(f"   Open the file in your browser to view the interactive charts!")

    except Exception as e:
        print(f"❌ Error generating the report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 80)
    print("🎉 ANALYSIS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    # Final summary
    print("\n📋 SUMMARY:")
    print(f"  • Mode: {mode}")
    print(f"  • Stocks in the portfolio: {len(tickers_to_analyze)}")
    print(f"  • Portfolio return: {portfolio_metrics['annual_return']:.2%}")
    print(f"  • Sharpe Ratio: {portfolio_metrics['sharpe_ratio']:.2f}")
    print(f"  • Diversification: {diversification_score:.1f}/100")
    if not args.full_universe:
        print(f"  • Capital allocated: €{args.capital:,.2f}")
    print(f"  • Report saved to: {args.output}")
    print()


if __name__ == "__main__":
    main()
