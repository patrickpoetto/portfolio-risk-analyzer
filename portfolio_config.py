"""
Configurazione del portafoglio con tutti i ticker selezionati
"""

# Lista completa dei ticker con nomi descrittivi
PORTFOLIO_TICKERS = {
    # Energia Nucleare / Uranio
    "LEU": "Centrus Energy Corp",
    # "KAP": "Kazatomprom JSC (GDR)",  # Non disponibile su Yahoo Finance
    "CCJ": "Cameco Corp",
    "BWXT": "BWX Technologies Inc",
    # "BOE.ASX": "Boss Energy Ltd",  # Non disponibile - prova "BOE.AX" se vuoi
    "UEC": "Uranium Energy Corp",  # Alternativa
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

    # Semiconduttori / Technology
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

    # Utility / Energia
    "NEE": "NextEra Energy Inc",
    "ETR": "Entergy Corp",
    "GE": "General Electric Co",
    "ENR.DE": "Siemens Energy AG",
    "XOM": "Exxon Mobil Corp",
    "TTE": "TotalEnergies SE",

    # Industriali / Costruzioni
    "CW": "Curtiss-Wright Corporation",
    "FLR": "Fluor Corp",
    "CAT": "Caterpillar Inc",
    "HOLN.SW": "Holcim Ltd",  # Swiss Exchange
    "DG.PA": "Vinci SA",
    "RTX": "RTX Corporation",
    "HON": "Honeywell International Inc",
    "SIE.DE": "Siemens AG",  # Xetra

    # Pharma / Farmaceutico
    "BAYN.DE": "Bayer AG",
    "PFE": "Pfizer Inc",
    "JNJ": "Johnson & Johnson",
    "LLY": "Eli Lilly and Co",
    "NVO": "Novo Nordisk A/S",

    # Biomedicale / Medical Devices
    "MDT": "Medtronic plc",
    "ISRG": "Intuitive Surgical Inc",
    "BSX": "Boston Scientific Corp",
    "SYK": "Stryker Corporation",
    "EW": "Edwards Lifesciences Corp",
    "ABT": "Abbott Laboratories",
    "ZBH": "Zimmer Biomet Holdings Inc",

    # Mining / Materiali
    "CENX": "Century Aluminum Company",
    "PPTA": "Perpetua Resources Corp",
    "RIO.L": "Rio Tinto Plc",
    "FCX": "Freeport-McMoRan Inc",
    "BHP": "BHP Group Ltd",

    # Defense / Aerospace
    # "CSG.AS": "Czechoslovak Group",  # Non disponibile su Yahoo Finance
    "RR.L": "Rolls-Royce Holdings",  # London Stock Exchange
    "LMT": "Lockheed Martin",  # Alternativa Defense
    "NOC": "Northrop Grumman Corp",
    "LDO.MI": "Leonardo SpA",  # Milano

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

    # Banking & Financial Services (Europa)
    #"HSBA.L": "HSBC Holdings plc",  # London Stock Exchange
    #"BARC.L": "Barclays plc",  # London Stock Exchange
    #"SAN.MC": "Banco Santander SA",  # Madrid
    #"BBVA.MC": "Banco Bilbao Vizcaya Argentaria SA",  # Madrid
    #"BNP.PA": "BNP Paribas SA",  # Parigi
    #"DBK.DE": "Deutsche Bank AG",  # Xetra
    #"ALV.DE": "Allianz SE",  # Xetra (assicurazioni)
    "INGA.AS": "ING Groep NV",  # Amsterdam
    "UBSG.SW": "UBS Group AG",  # Swiss Exchange
    #"ISP.MI": "Intesa Sanpaolo SpA",  # Milano
}

# Classificazione per settore (semplificata)
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

# Classificazione per area geografica (per borsa di quotazione/valuta, non
# per nazionalità della società: es. NIO/TTE/NVO sono ADR USD su borsa USA)
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

# Esempio di allocazione iniziale (in EUR o USD - usa la stessa valuta)
# Modifica questi valori con il tuo capitale effettivo per ogni posizione
EXAMPLE_HOLDINGS = {
    # Lascia vuoto o aggiungi i tuoi valori reali
    # "LEU": 1000,
    # "RGTI": 1500,
    # ... etc
}

# =============================================================================
# PARAMETRI DI CONFIGURAZIONE GENERALE
# =============================================================================

# Tasso privo di rischio annuo usato per lo Sharpe Ratio (es. rendimento
# di un BOT/T-Bill a breve termine). Centralizzato qui: prima era duplicato
# come valore fisso in 3 punti diversi del codice (risk_analysis.py e
# backtest.py), quindi andava aggiornato manualmente in più posti quando
# cambiano i tassi di mercato.
RISK_FREE_RATE = 0.035

# --- Parametri Default per l'Analisi ---
DEFAULT_CONFIG = {
    "capital": 400000.0,              # Capitale di default (EUR)
    "risk_profile": "moderate",      # Profilo di rischio: conservative, moderate, aggressive
    "period": "5y",                  # Periodo storico: 1y, 2y, 5y, max
    "output_file": "portfolio_report.html",  # Nome file output
}

# --- Parametri Allocazione Pratica ---
ALLOCATION_CONFIG = {
    "min_position_size": 500.0,       # Investimento minimo per titolo (EUR)
    "max_weight_per_stock": 0.06,    # Peso massimo singolo titolo (12%)
    # Peso minimo imposto nell'ottimizzatore per ogni titolo selezionato,
    # come frazione del peso equipesato (1/N). Senza un pavimento, SLSQP
    # tende a soluzioni d'angolo che azzerano metà dei titoli scelti apposta
    # per diversificazione (vedi optimization.mean_variance_optimize) — un
    # risultato tecnicamente ottimo ma che vanifica lo scopo della selezione.
    "min_weight_factor": 0.3,
}

# --- Parametri Numero Titoli Ottimale (data-driven) ---
# Il numero di titoli NON è più scelto per fasce di capitale hardcoded: viene
# calcolato dalla vera curva di diversificazione (rischio di portafoglio
# equipesato via w'Σw al crescere di N, sui dati reali) e poi vincolato dal
# capitale disponibile. Vedi practical_allocation.select_portfolio().
#
# Il criterio è il minimo EMPIRICO della curva di rischio: continua ad
# aggiungere titoli finché il rischio scende, fermati (circa) dove smette di
# migliorare in modo stabile. "Stabile" = il rischio resta entro
# stability_tolerance dal minimo assoluto per almeno stability_window titoli
# consecutivi, non un singolo punto basso isolato (altrimenti un avvallamento
# casuale della curva farebbe scattare la soglia troppo presto o troppo tardi
# a seconda del rumore nei dati).
#
# min_stocks=20 è il floor pratico, che vince comunque se il calcolo sopra
# darebbe un numero minore: 20-30 titoli è l'intervallo comunemente citato in
# pratica per una diversificazione adeguata di portafogli di dimensioni
# significative (Statman 1987, che tiene conto anche dei costi di
# transazione oltre alla sola riduzione di varianza).
DIVERSIFICATION_TARGET_CONFIG = {
    "stability_tolerance": 0.02,   # entro il 2% del rischio minimo assoluto è considerato "convergenza"
    "stability_window": 3,        # titoli consecutivi richiesti entro la tolleranza
    "min_stocks": 20,              # floor pratico (vedi nota sopra)
}

# --- Parametri Correlazione e Diversificazione ---
# (i pesi per la selezione titoli sono in RISK_PROFILES, uno per profilo di rischio)
CORRELATION_CONFIG = {
    "high_correlation_threshold": 0.7,  # Soglia per correlazione "alta" (70%)
    "max_correlation_penalty": 0.8,     # Oltre questa soglia la penalty è massima
}

# --- Parametri Score di Diversificazione ---
# Lo score combina due aspetti indipendenti: correlazione media tra i titoli
# (poco utile se i pesi sono molto concentrati) e concentrazione dei pesi via
# HHI (Herfindahl-Hirschman Index: 1/N se equipesato, 1 se tutto su un titolo)
DIVERSIFICATION_CONFIG = {
    "correlation_weight": 0.6,      # Peso della componente correlazione nello score finale
    "concentration_weight": 0.4,    # Peso della componente concentrazione (HHI) nello score finale
}

# --- Parametri Valutazione Fondamentale (sopra/sottovalutazione) ---
# Penalizza i titoli cari rispetto ai pari del proprio settore (non ha senso
# confrontare il P/E di un titolo nucleare con uno di quantum computing).
# Il punteggio è un percentile 0-1 calcolato su questi multipli disponibili.
VALUATION_CONFIG = {
    "metrics": ["trailing_pe", "peg_ratio", "price_to_book"],
    "penalty_weight": 0.3,   # quanto pesa la sopravvalutazione nello score finale (0=ignora, 1=pesa quanto le altre componenti)
}

# --- Profili di Rischio ---
# Pesi per ottimizzazione allocazione per ogni profilo
RISK_PROFILES = {
    "conservative": {
        "sharpe_weight": 0.3,
        "correlation_weight": 0.5,
        "sector_weight": 0.2,
        "description": "Focus su stabilità e diversificazione",
    },
    "moderate": {
        "sharpe_weight": 0.4,
        "correlation_weight": 0.4,
        "sector_weight": 0.2,
        "description": "Bilanciamento tra performance e rischio",
    },
    "aggressive": {
        "sharpe_weight": 0.6,
        "correlation_weight": 0.3,
        "sector_weight": 0.1,
        "description": "Focus su massima performance",
    },
}

# --- Parametri Backtest ---
BACKTEST_CONFIG = {
    "benchmark_names": {              # ticker -> nome leggibile (S&P500, NASDAQ, MSCI World, Vanguard Total)
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "URTH": "MSCI World",
        "VT": "VT (Total World)"
    },
    # Split in-sample / out-of-sample: la frazione finale dei dati scaricati
    # (secondo --period) è tenuta da parte e MAI usata per scouting, selezione
    # smart o ottimizzazione dei pesi. Il backtest la usa come test onesto,
    # perché valuta la selezione su dati che non ha potuto vedere.
    "out_of_sample_ratio": 0.2,        # frazione finale riservata al test
    "min_out_of_sample_days": 60,      # holdout minimo (~3 mesi di trading)
    "max_out_of_sample_days": 252,     # holdout massimo (~1 anno di trading)
}

# --- Parametri Liquidità ---
CASH_CONFIG = {
    "base_allocation": 0.10,         # Allocazione base liquidità (10%)
    "volatility_multiplier": 0.25,   # Moltiplicatore per volatilità portfolio
    "min_cash": 0.05,                # Minimo 5% liquidità
    "max_cash": 0.25,                # Massimo 30% liquidità
}

# --- Parametri Rilevamento Condizione di Mercato ---
# Usati per stimare bullish/bearish/volatile dal trend/volatilità recenti di
# un benchmark (es. S&P 500) nel backtest, invece di assumere sempre "normal"
MARKET_CONDITION_CONFIG = {
    "lookback_days": 63,          # Finestra di osservazione (~3 mesi di trading)
    "trend_threshold": 0.08,      # Oltre +/-8% nella finestra => bullish/bearish
    "volatility_threshold": 0.30, # Volatilità annualizzata oltre il 30% => volatile
}

# --- Parametri Visualizzazione Report ---
REPORT_CONFIG = {
    "top_n_allocation_pie": 40,      # Numero titoli da mostrare nella torta
    "top_n_metrics_table": 40,       # Top N nella tabella metriche
}

# --- Tema Report HTML: "Midnight Terminal" ---
# Palette scura stile terminale finanziario. Usata sia nel CSS del report
# sia nei layout dei grafici Plotly, per un risultato coerente.
THEME_CONFIG = {
    "bg_page": "#0a0e27",              # sfondo pagina, navy quasi nero
    "bg_card": "#131a3a",              # sfondo card/pannelli
    "bg_card_alt": "#0f1530",          # sfondo alternato (righe tabella, header)
    "bg_elevated": "#1a2248",          # sfondo elementi in rilievo (hover, badge)
    "border": "rgba(255, 255, 255, 0.12)",
    "grid": "rgba(255, 255, 255, 0.10)",   # griglie bianche sottili nei grafici
    "text_primary": "#e8ecf5",
    "text_secondary": "#8b93b0",
    "accent": "#00d9ff",               # ciano elettrico
    "accent_soft": "rgba(0, 217, 255, 0.12)",
    "accent_2": "#0080ff",             # blu elettrico scuro (hue più basso, non violaceo), per gradienti/secondo accento
    "positive": "#00ff9d",
    "positive_soft": "rgba(0, 255, 157, 0.12)",
    "negative": "#ff3860",
    "negative_soft": "rgba(255, 56, 96, 0.12)",
    "warning": "#ffb84d",
    "warning_soft": "rgba(255, 184, 77, 0.12)",
    "font_family": "'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
    "font_mono": "'JetBrains Mono', 'Consolas', monospace",
    # Palette qualitativa per grafici a torta/barre categoriali (pensata per
    # sfondo scuro: colori vividi, non pastello, a dominante blu/ciano)
    "qualitative_palette": [
        "#00d9ff", "#0080ff", "#00ff9d", "#ffb84d", "#ff3860",
        "#36c9d0", "#3399ff", "#5ee6a0", "#ffd166", "#ff6b9d",
        "#4cc9f0", "#1a8cff", "#80ffdb", "#f4a261", "#ef476f",
    ],
}
