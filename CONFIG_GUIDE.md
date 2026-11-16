# 📝 Guida alla Configurazione

Tutti i parametri configurabili del progetto sono centralizzati in `portfolio_config.py`.

## 📁 Struttura Configurazione

### 1️⃣ **DEFAULT_CONFIG** - Parametri di Default

```python
DEFAULT_CONFIG = {
    "capital": 10000.0,              # Capitale di default (EUR)
    "risk_profile": "moderate",      # Profilo di rischio
    "period": "1y",                  # Periodo storico dati
    "output_file": "portfolio_report.html",
}
```

**Usa per**: Impostare valori di default quando esegui `python main.py` senza parametri.

**Come modificare**:
```python
# Esempio: cambia capitale default a 50k
DEFAULT_CONFIG["capital"] = 50000.0
```

---

### 2️⃣ **ALLOCATION_CONFIG** - Allocazione Pratica

```python
ALLOCATION_CONFIG = {
    "min_position_size": 500.0,      # Investimento minimo per titolo
    "max_weight_per_stock": 0.12,    # Max 12% per singolo titolo
    
    "capital_thresholds": {
        "very_small": 3000,          # < 3k → 5-6 titoli
        "small": 10000,              # 3k-10k → 8-10 titoli  
        "medium": 30000,             # 10k-30k → 15-20 titoli
        "large": 100000,             # 30k-100k → 25-30 titoli
    },
}
```

**Usa per**: Controllare come vengono selezionati i titoli in base al capitale.

**Esempio Modifica**:
```python
# Più conservativo: richiedi almeno €800 per posizione
ALLOCATION_CONFIG["min_position_size"] = 800.0

# Più concentrato: permetti fino al 20% per singolo titolo
ALLOCATION_CONFIG["max_weight_per_stock"] = 0.20

# Più titoli per capitali medi: abbassa soglia
ALLOCATION_CONFIG["capital_thresholds"]["medium"] = 20000
```

---

### 3️⃣ **CORRELATION_CONFIG** - Correlazioni e Diversificazione

```python
CORRELATION_CONFIG = {
    "high_correlation_threshold": 0.7,  # Correlazione "alta" se > 70%
    "max_correlation_penalty": 0.7,     # Penalizza titoli con corr > 70%
    "correlation_weight": 0.4,          # Peso correlazione nella selezione (40%)
    "sharpe_weight": 0.4,               # Peso Sharpe Ratio (40%)
    "sector_bonus_weight": 0.2,         # Peso diversificazione settoriale (20%)
}
```

**Usa per**: Controllare quanto pesano le correlazioni nella selezione.

**Esempio Modifica**:
```python
# Più severo sulle correlazioni: abbassa soglia
CORRELATION_CONFIG["high_correlation_threshold"] = 0.6

# Dai più importanza alla diversificazione
CORRELATION_CONFIG["correlation_weight"] = 0.5
CORRELATION_CONFIG["sharpe_weight"] = 0.3
```

---

### 4️⃣ **RISK_PROFILES** - Profili di Rischio

```python
RISK_PROFILES = {
    "conservative": {
        "sharpe_weight": 0.3,
        "correlation_weight": 0.5,    # Più focus su diversificazione
        "sector_weight": 0.2,
    },
    "moderate": {
        "sharpe_weight": 0.4,
        "correlation_weight": 0.4,    # Bilanciato
        "sector_weight": 0.2,
    },
    "aggressive": {
        "sharpe_weight": 0.6,         # Più focus su performance
        "correlation_weight": 0.3,
        "sector_weight": 0.1,
    },
}
```

**Usa per**: Personalizzare i profili di rischio o aggiungerne di nuovi.

**Esempio - Crea Profilo Custom**:
```python
RISK_PROFILES["ultra_conservative"] = {
    "sharpe_weight": 0.2,
    "correlation_weight": 0.6,
    "sector_weight": 0.2,
    "description": "Massima diversificazione, minimo rischio"
}

# Poi usa con:
# python main.py --risk ultra_conservative
```

---

### 5️⃣ **BACKTEST_CONFIG** - Backtest Storico

```python
BACKTEST_CONFIG = {
    "period": "5y",
    "benchmarks": ["^GSPC", "^IXIC", "URTH", "VT"],
    "benchmark_names": {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "URTH": "MSCI World",
        "VT": "VT (Total World)"
    },
}
```

**Usa per**: Cambiare periodo backtest o aggiungere/rimuovere benchmark.

**Esempio Modifica**:
```python
# Backtest su 10 anni
BACKTEST_CONFIG["period"] = "10y"

# Aggiungi DAX tedesco
BACKTEST_CONFIG["benchmarks"].append("^GDAXI")
BACKTEST_CONFIG["benchmark_names"]["^GDAXI"] = "DAX"
```

---

### 6️⃣ **CASH_CONFIG** - Gestione Liquidità

```python
CASH_CONFIG = {
    "base_allocation": 0.10,         # Base 10% liquidità
    "volatility_multiplier": 0.25,   # Aumenta con volatilità
    "min_cash": 0.05,                # Minimo 5%
    "max_cash": 0.30,                # Massimo 30%
}
```

**Usa per**: Controllare la componente cash suggerita.

**Esempio Modifica**:
```python
# Più aggressivo: meno liquidità
CASH_CONFIG["base_allocation"] = 0.05
CASH_CONFIG["min_cash"] = 0.02

# Più conservativo: più liquidità
CASH_CONFIG["base_allocation"] = 0.20
CASH_CONFIG["max_cash"] = 0.40
```

---

### 7️⃣ **REPORT_CONFIG** - Aspetto Report HTML

```python
REPORT_CONFIG = {
    "top_n_allocation_pie": 20,      # Titoli da mostrare nella torta
    "top_n_metrics_table": 20,       # Top N nella tabella
    "chart_height": 500,             # Altezza grafici (px)
    "colors": {
        "primary": "#667eea",
        "secondary": "#764ba2",
        "success": "#28a745",
        "warning": "#ffc107",
        "danger": "#dc3545",
    },
}
```

**Usa per**: Personalizzare l'aspetto del report.

**Esempio Modifica**:
```python
# Mostra più titoli
REPORT_CONFIG["top_n_allocation_pie"] = 30

# Cambia colore primario
REPORT_CONFIG["colors"]["primary"] = "#3498db"

# Grafici più grandi
REPORT_CONFIG["chart_height"] = 700
```

---

## 🎯 Esempi di Uso Comune

### Caso 1: Investitore Conservativo con Capitale Alto

```python
# In portfolio_config.py:

DEFAULT_CONFIG["capital"] = 100000
DEFAULT_CONFIG["risk_profile"] = "conservative"

ALLOCATION_CONFIG["min_position_size"] = 1000  # Posizioni più grandi
ALLOCATION_CONFIG["max_weight_per_stock"] = 0.08  # Max 8% per titolo

CORRELATION_CONFIG["high_correlation_threshold"] = 0.6  # Più severo
```

### Caso 2: Investitore Aggressivo con Capitale Limitato

```python
DEFAULT_CONFIG["capital"] = 5000
DEFAULT_CONFIG["risk_profile"] = "aggressive"

ALLOCATION_CONFIG["min_position_size"] = 400  # Posizioni più piccole OK
ALLOCATION_CONFIG["max_weight_per_stock"] = 0.20  # Concentrazione OK

RISK_PROFILES["aggressive"]["sharpe_weight"] = 0.7  # Ancora più focus su performance
```

### Caso 3: Massima Diversificazione

```python
CORRELATION_CONFIG["correlation_weight"] = 0.6
CORRELATION_CONFIG["sharpe_weight"] = 0.2
CORRELATION_CONFIG["sector_bonus_weight"] = 0.2

ALLOCATION_CONFIG["max_weight_per_stock"] = 0.05  # Max 5% per titolo
```

---

## 🔄 Come Applicare le Modifiche

1. **Modifica `portfolio_config.py`**
   ```bash
   nano portfolio_config.py
   # oppure apri in Cursor/VSCode
   ```

2. **Le modifiche sono immediate**
   ```bash
   # Nessun restart necessario, basta rieseguire
   python main.py --capital 20000
   ```

3. **Testa con parametri CLI** (override temporaneo):
   ```bash
   # Questi sovrascrivono i valori in config
   python main.py --capital 50000 --risk aggressive --period 5y
   ```

---

## ⚠️ Note Importanti

1. **Backup prima di modificare**:
   ```bash
   cp portfolio_config.py portfolio_config.py.backup
   ```

2. **Valida i parametri**:
   - `max_weight_per_stock`: deve essere tra 0.01 e 1.0
   - `min_position_size`: deve essere > 0
   - Pesi nei profili devono sommare a 1.0

3. **Test dopo modifiche**:
   ```bash
   python -c "from portfolio_config import *; print('✅ Config OK')"
   ```

---

## 🆘 Ripristino Configurazione Default

Se qualcosa va storto:

```bash
# Ripristina da backup
cp portfolio_config.py.backup portfolio_config.py

# Oppure scarica originale da GitHub
git checkout portfolio_config.py
```

---

**💡 Suggerimento**: Crea diverse configurazioni salvando copie con nomi diversi:
```bash
cp portfolio_config.py portfolio_config_conservative.py
cp portfolio_config.py portfolio_config_aggressive.py
```

Poi switcha tra di esse quando serve!
