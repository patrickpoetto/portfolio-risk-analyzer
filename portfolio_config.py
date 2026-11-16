"""
Portfolio configuration with all selected tickers
"""

# Full list of tickers with descriptive names
PORTFOLIO_TICKERS = {
    # Nuclear Energy / Uranium
    "LEU": "Centrus Energy Corp",
    # "KAP": "Kazatomprom JSC (GDR)",  # Not available on Yahoo Finance
    "CCJ": "Cameco Corp",
    "BWXT": "BWX Technologies Inc",
    # "BOE.ASX": "Boss Energy Ltd",  # Not available - try "BOE.AX" instead
    "UEC": "Uranium Energy Corp",  # Alternative
    "CEG": "Constellation Energy Corp",
    "DNN": "Denison Mines Corp",

    # Quantum Computing
    "RGTI": "Rigetti Computing Inc",
    "QBTS": "D-Wave Quantum Inc",
    "IONQ": "IONQ Inc",
    "QUBT": "Quantum Computing Inc",
    "ARQQ": "Arqit Quantum Inc",
    "QSI": "Quantum-Si Inc",

    # Battery / Energy Storage
    "ABAT": "American Battery Technology Co",

    # Semiconductors / Technology
    "MRVL": "Marvell Technology Group Ltd",
    "SKYT": "SkyWater Technology Inc",
    "SMCI": "Super Micro Computer Inc",
    "AVGO": "Broadcom Inc",
    "ASML": "ASML Holding NV",
    "TSM": "Taiwan Semiconductor Manufacturing Co",
    "MU": "Micron Technology",
    "AMD": "AMD",
    "NVDA": "Nvidia Corp",
    "QCOM": "Qualcomm Inc",

    # Utilities / Energy
    "NEE": "NextEra Energy Inc",
    "ETR": "Entergy Corp",
    "GE": "General Electric Co",
    "ENR.DE": "Siemens Energy AG",
    "XOM": "Exxon Mobil Corp",
    "TTE": "TotalEnergies SE",

    # Industrials / Construction
    "CW": "Curtiss-Wright Corporation",
    "FLR": "Fluor Corp",
    "CAT": "Caterpillar Inc",
    "HOLN.SW": "Holcim Ltd",  # Swiss Exchange
    "DG.PA": "Vinci SA",
    "RTX": "RTX Corporation",
    "HON": "Honeywell International Inc",
    "SIE.DE": "Siemens AG",  # Xetra

    # Pharma / Pharmaceuticals
    "BAYN.DE": "Bayer AG",
    "PFE": "Pfizer Inc",
    "JNJ": "Johnson & Johnson",
    "LLY": "Eli Lilly and Co",
    "NVO": "Novo Nordisk A/S",

    # Biomedical / Medical Devices
    "MDT": "Medtronic plc",
    "ISRG": "Intuitive Surgical Inc",
    "BSX": "Boston Scientific Corp",
    "SYK": "Stryker Corporation",
    "EW": "Edwards Lifesciences Corp",
    "ABT": "Abbott Laboratories",
    "ZBH": "Zimmer Biomet Holdings Inc",

    # Mining / Materials
    "CENX": "Century Aluminum Company",
    "PPTA": "Perpetua Resources Corp",
    "RIO.L": "Rio Tinto Plc",
    "FCX": "Freeport-McMoRan Inc",
    "BHP": "BHP Group Ltd",

    # Defense / Aerospace
    # "CSG.AS": "Czechoslovak Group",  # Not available on Yahoo Finance
    "RR.L": "Rolls-Royce Holdings",  # London Stock Exchange
    "LMT": "Lockheed Martin",  # Defense alternative
    "NOC": "Northrop Grumman Corp",
    "LDO.MI": "Leonardo SpA",  # Milan

    # Tech / Cloud / Software
    "SNOW": "Snowflake Inc",
    "ORCL": "Oracle Corp",
    "SAP.DE": "SAP SE",
    "ADBE": "Adobe Inc",
    "PLTR": "Palantir Technologies",
    "MSFT": "Microsoft Corp",
    "CRM": "Salesforce Inc",

    # EV / Auto
    "NIO": "NIO Inc (ADR)",
    #"TSLA": "Tesla Inc",
    "STLA": "Stellantis NV",

    # Energy / Oil
    "CVX": "Chevron Corp",

    # Data Centers / REITs
    "DLR": "Digital Realty Trust Inc",
    "EQIX": "Equinix Inc",
    "AMT": "American Tower Corp",
    "VRT": "Vertiv Holdings Co",

    # Components
    "LITE": "Lumentum Holdings Inc",

    # Banking & Financial Services (Europe)
    #"HSBA.L": "HSBC Holdings plc",  # London Stock Exchange
    #"BARC.L": "Barclays plc",  # London Stock Exchange
    #"SAN.MC": "Banco Santander SA",  # Madrid
    #"BBVA.MC": "Banco Bilbao Vizcaya Argentaria SA",  # Madrid
    #"BNP.PA": "BNP Paribas SA",  # Paris
    #"DBK.DE": "Deutsche Bank AG",  # Xetra
    #"ALV.DE": "Allianz SE",  # Xetra (insurance)
    "INGA.AS": "ING Groep NV",  # Amsterdam
    "UBSG.SW": "UBS Group AG",  # Swiss Exchange
    #"ISP.MI": "Intesa Sanpaolo SpA",  # Milan
}

# Sector classification (simplified)
SECTOR_CLASSIFICATION = {
    "Nuclear Energy": ["LEU", "CCJ", "BWXT", "UEC", "CEG", "DNN"],
    "Quantum Computing": ["RGTI", "QBTS", "IONQ", "QUBT", "ARQQ", "QSI"],
    "Semiconductors": ["MRVL", "SKYT", "SMCI", "AVGO", "ASML", "TSM", "MU", "AMD", "LITE", "NVDA", "QCOM"],
    "Energy & Utilities": ["NEE", "ETR", "GE", "ENR.DE", "CVX", "XOM", "TTE"],
    "Industrials & Construction": ["CW", "FLR", "CAT", "HOLN.SW", "DG.PA", "RTX", "HON", "SIE.DE"],
    "Mining & Materials": ["CENX", "PPTA", "RIO.L", "ABAT", "FCX", "BHP"],
    "Defense & Aerospace": ["RR.L", "LMT", "NOC", "LDO.MI"],
    "Cloud & Software": ["SNOW", "ORCL", "SAP.DE", "ADBE", "PLTR", "MSFT", "CRM"],
    "Automotive": ["NIO", "TSLA", "STLA"],
    "Data Centers": ["DLR", "EQIX", "AMT", "VRT"],
    "Pharmaceuticals": ["BAYN.DE", "PFE", "JNJ", "LLY", "NVO"],
    "Biomedical & Medical Devices": ["MDT", "ISRG", "BSX", "SYK", "EW", "ABT", "ZBH"],
    "Banking & Financial Services": ["HSBA.L", "BARC.L", "SAN.MC", "BBVA.MC", "BNP.PA",
                                     "DBK.DE", "ALV.DE", "INGA.AS", "UBSG.SW", "ISP.MI"],
}

# Geographic classification (by listing exchange/currency, not company
# nationality: e.g. NIO/TTE/NVO are USD ADRs listed on US exchanges)
GEOGRAPHIC_CLASSIFICATION = {
    "North America": ["LEU", "CCJ", "BWXT", "RGTI", "QBTS", "IONQ", "QUBT", "ABAT",
                     "MRVL", "SKYT", "SMCI", "AVGO", "NEE", "ETR", "GE", "CW", "FLR",
                     "CAT", "CENX", "PPTA", "SNOW", "NIO", "RTX", "CVX", "DLR",
                     "EQIX", "ORCL", "ADBE", "LITE", "MU", "AMD", "PLTR",
                     "PFE", "JNJ", "MDT", "ISRG", "BSX", "SYK", "EW", "LMT", "UEC",
                     "CEG", "DNN", "ARQQ", "QSI", "NVDA", "QCOM", "XOM", "TTE",
                     "HON", "FCX", "BHP", "NOC", "MSFT", "CRM", "TSLA", "STLA",
                     "AMT", "VRT", "LLY", "NVO", "ABT", "ZBH"],
    "Europe": ["BAYN.DE", "ENR.DE", "HOLN.SW", "DG.PA", "RIO.L",
              "SAP.DE", "RR.L", "ASML",
              "HSBA.L", "BARC.L", "SAN.MC", "BBVA.MC", "BNP.PA",
              "DBK.DE", "ALV.DE", "INGA.AS", "UBSG.SW", "ISP.MI",
              "SIE.DE", "LDO.MI"],
    "Asia-Pacific": ["TSM"],
}

# Sample initial allocation (in EUR or USD - use the same currency)
# Edit these values with your actual capital for each position
EXAMPLE_HOLDINGS = {
    # Leave empty or add your real values
    # "LEU": 1000,
    # "RGTI": 1500,
    # ... etc
}

# =============================================================================
# GENERAL CONFIGURATION PARAMETERS
# =============================================================================

# Annual risk-free rate used for the Sharpe Ratio (e.g. short-term T-Bill
# yield). Centralized here: it used to be duplicated as a fixed value in
# 3 different places in the code (risk_analysis.py and backtest.py), so it
# had to be updated manually in multiple spots whenever market rates changed.
RISK_FREE_RATE = 0.035

# --- Default Analysis Parameters ---
DEFAULT_CONFIG = {
    "capital": 400000.0,              # Default capital (EUR)
    "risk_profile": "moderate",      # Risk profile: conservative, moderate, aggressive
    "period": "5y",                  # Historical period: 1y, 2y, 5y, max
    "output_file": "portfolio_report.html",  # Output file name
}

# --- Practical Allocation Parameters ---
ALLOCATION_CONFIG = {
    "min_position_size": 500.0,       # Minimum investment per stock (EUR)
    "max_weight_per_stock": 0.06,    # Maximum weight per single stock (6%)
    # Minimum weight enforced by the optimizer for each selected stock, as a
    # fraction of the equal-weight share (1/N). Without a floor, SLSQP tends
    # toward corner solutions that zero out half of the stocks chosen
    # specifically for diversification (see optimization.mean_variance_optimize)
    # — a technically optimal result that defeats the purpose of the selection.
    "min_weight_factor": 0.3,
}

# --- Optimal Number of Stocks Parameters (data-driven) ---
# The number of stocks is NO LONGER chosen from hardcoded capital brackets:
# it is computed from the real diversification curve (equal-weighted
# portfolio risk via w'Σw as N grows, on real data) and then constrained by
# the available capital. See practical_allocation.select_portfolio().
#
# The criterion is the EMPIRICAL minimum of the risk curve: keep adding
# stocks while risk keeps falling, stop (roughly) where it stops improving
# in a stable way. "Stable" = risk stays within stability_tolerance of the
# absolute minimum for at least stability_window consecutive stocks, not a
# single isolated low point (otherwise a random dip in the curve would
# trigger the threshold too early or too late depending on data noise).
#
# min_stocks=20 is the practical floor, which still wins if the calculation
# above would give a lower number: 20-30 stocks is the range commonly cited
# in practice for adequate diversification of portfolios of meaningful size
# (Statman 1987, which also accounts for transaction costs in addition to
# pure variance reduction).
DIVERSIFICATION_TARGET_CONFIG = {
    "stability_tolerance": 0.02,   # within 2% of the absolute minimum risk counts as "convergence"
    "stability_window": 3,        # consecutive stocks required within the tolerance
    "min_stocks": 20,              # practical floor (see note above)
}

# --- Correlation and Diversification Parameters ---
# (stock-selection weights are in RISK_PROFILES, one per risk profile)
CORRELATION_CONFIG = {
    "high_correlation_threshold": 0.7,  # Threshold for "high" correlation (70%)
    "max_correlation_penalty": 0.8,     # Beyond this threshold the penalty is at its maximum
}

# --- Diversification Score Parameters ---
# The score combines two independent aspects: average correlation between
# stocks (not very useful if weights are highly concentrated) and weight
# concentration via HHI (Herfindahl-Hirschman Index: 1/N if equal-weighted,
# 1 if everything is in a single stock)
DIVERSIFICATION_CONFIG = {
    "correlation_weight": 0.6,      # Weight of the correlation component in the final score
    "concentration_weight": 0.4,    # Weight of the concentration component (HHI) in the final score
}

# --- Fundamental Valuation Parameters (over/undervaluation) ---
# Penalizes stocks that are expensive relative to peers in their own sector
# (comparing the P/E of a nuclear stock with a quantum computing one makes
# no sense). The score is a 0-1 percentile computed over these available
# multiples.
VALUATION_CONFIG = {
    "metrics": ["trailing_pe", "peg_ratio", "price_to_book"],
    "penalty_weight": 0.3,   # how much overvaluation weighs in the final score (0=ignore, 1=weighs as much as the other components)
}

# --- Risk Profiles ---
# Allocation-optimization weights for each profile
RISK_PROFILES = {
    "conservative": {
        "sharpe_weight": 0.3,
        "correlation_weight": 0.5,
        "sector_weight": 0.2,
        "description": "Focus on stability and diversification",
    },
    "moderate": {
        "sharpe_weight": 0.4,
        "correlation_weight": 0.4,
        "sector_weight": 0.2,
        "description": "Balance between performance and risk",
    },
    "aggressive": {
        "sharpe_weight": 0.6,
        "correlation_weight": 0.3,
        "sector_weight": 0.1,
        "description": "Focus on maximum performance",
    },
}

# --- Backtest Parameters ---
BACKTEST_CONFIG = {
    "benchmark_names": {              # ticker -> readable name (S&P500, NASDAQ, MSCI World, Vanguard Total)
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "URTH": "MSCI World",
        "VT": "VT (Total World)"
    },
    # In-sample / out-of-sample split: the final fraction of the downloaded
    # data (per --period) is held back and NEVER used for scouting, smart
    # selection or weight optimization. The backtest uses it as an honest
    # test, because it evaluates the selection on data it never saw.
    "out_of_sample_ratio": 0.2,        # final fraction reserved for testing
    "min_out_of_sample_days": 60,      # minimum holdout (~3 trading months)
    "max_out_of_sample_days": 252,     # maximum holdout (~1 trading year)
}

# --- Cash Parameters ---
CASH_CONFIG = {
    "base_allocation": 0.10,         # Base cash allocation (10%)
    "volatility_multiplier": 0.25,   # Multiplier for portfolio volatility
    "min_cash": 0.05,                # Minimum 5% cash
    "max_cash": 0.25,                # Maximum 25% cash
}

# --- Market Condition Detection Parameters ---
# Used to estimate bullish/bearish/volatile from the recent trend/volatility
# of a benchmark (e.g. S&P 500) in the backtest, instead of always assuming "normal"
MARKET_CONDITION_CONFIG = {
    "lookback_days": 63,          # Observation window (~3 trading months)
    "trend_threshold": 0.08,      # Beyond +/-8% over the window => bullish/bearish
    "volatility_threshold": 0.30, # Annualized volatility above 30% => volatile
}

# --- Report Display Parameters ---
REPORT_CONFIG = {
    "top_n_allocation_pie": 40,      # Number of stocks to show in the pie chart
    "top_n_metrics_table": 40,       # Top N in the metrics table
}

# --- HTML Report Theme: "Midnight Terminal" ---
# Dark palette styled like a financial terminal. Used both in the report's
# CSS and in the Plotly chart layouts, for a consistent result.
THEME_CONFIG = {
    "bg_page": "#0a0e27",              # page background, near-black navy
    "bg_card": "#131a3a",              # card/panel background
    "bg_card_alt": "#0f1530",          # alternate background (table rows, headers)
    "bg_elevated": "#1a2248",          # raised element background (hover, badges)
    "border": "rgba(255, 255, 255, 0.12)",
    "grid": "rgba(255, 255, 255, 0.10)",   # thin white gridlines in charts
    "text_primary": "#e8ecf5",
    "text_secondary": "#8b93b0",
    "accent": "#00d9ff",               # electric cyan
    "accent_soft": "rgba(0, 217, 255, 0.12)",
    "accent_2": "#0080ff",             # deep electric blue (lower hue, not violet-leaning), for gradients/secondary accent
    "positive": "#00ff9d",
    "positive_soft": "rgba(0, 255, 157, 0.12)",
    "negative": "#ff3860",
    "negative_soft": "rgba(255, 56, 96, 0.12)",
    "warning": "#ffb84d",
    "warning_soft": "rgba(255, 184, 77, 0.12)",
    "font_family": "'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
    "font_mono": "'JetBrains Mono', 'Consolas', monospace",
    # Qualitative palette for pie/bar categorical charts (designed for a dark
    # background: vivid, non-pastel colors, with a blue/cyan bias)
    "qualitative_palette": [
        "#00d9ff", "#0080ff", "#00ff9d", "#ffb84d", "#ff3860",
        "#36c9d0", "#3399ff", "#5ee6a0", "#ffd166", "#ff6b9d",
        "#4cc9f0", "#1a8cff", "#80ffdb", "#f4a261", "#ef476f",
    ],
}
