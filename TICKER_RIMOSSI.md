# 🗑️ Ticker Rimossi - Febbraio 2026

## ❌ Ticker Non Disponibili su Yahoo Finance

I seguenti ticker erano nel piano originale ma **non sono disponibili** su Yahoo Finance:

### 1. **KAP** - Kazatomprom JSC (GDR)

**Problema**: 
- Non disponibile su Yahoo Finance
- GDR (Global Depositary Receipt) non sempre tracciati

**Alternativa Adottata**:
- ✅ **UEC** (Uranium Energy Corp) - Già nel portafoglio
- ✅ **CCJ** (Cameco Corp) - Già nel portafoglio
- ✅ **LEU** (Centrus Energy) - Già nel portafoglio
- ✅ **BWXT** (BWX Technologies) - Già nel portafoglio

**Risultato**: 4 titoli uranium/nuclear energy coprono il settore ✅

---

### 2. **BOE.ASX** - Boss Energy Ltd

**Problema**: 
- Ticker `.ASX` non funziona su Yahoo Finance
- Alternative provate:
  - `BOE.AX` ❌ (non trovato)
  - `BOE.ASX` ❌ (non trovato)

**Alternativa Adottata**:
- ✅ **UEC** (Uranium Energy Corp)
- ✅ **CCJ** (Cameco Corp)

**Note**: 
- Titolo australiano, difficile accesso via Yahoo Finance US
- Esposizione uranium comunque coperta con 4 titoli USA

---

### 3. **CSG.AS** - Czechoslovak Group

**Problema**: 
- Non disponibile su Yahoo Finance
- Ticker Euronext Amsterdam potrebbe essere errato
- Società non quotata pubblicamente o simbolo sbagliato

**Alternativa Adottata**:
- ✅ **LMT** (Lockheed Martin) - Defense & Aerospace
- ✅ **RTX** (RTX Corporation) - Defense & Aerospace
- ✅ **RR.L** (Rolls-Royce) - Defense & Aerospace

**Risultato**: Settore Defense coperto con 3 titoli solidi ✅

---

## 📊 Impatto sul Portafoglio

| Settore | Ticker Rimossi | Alternative Presenti | Status |
|---------|---------------|---------------------|--------|
| **Nuclear Energy** | KAP, BOE.ASX | LEU, CCJ, BWXT, UEC (4) | ✅ Ben coperto |
| **Defense & Aerospace** | CSG.AS | RR.L, LMT, RTX (3) | ✅ Ben coperto |

**Conclusione**: Tutti i settori sono comunque **ben rappresentati** con alternative valide.

---

## 🔍 Come Verificare Ticker in Futuro

### Metodo 1: Script Automatico
```bash
python validate_tickers.py
```

### Metodo 2: Manuale
```bash
python -c "
import yfinance as yf
ticker = 'NUOVO_TICKER'
data = yf.Ticker(ticker).history(period='5d')
if not data.empty:
    print(f'✅ {ticker}: OK')
else:
    print(f'❌ {ticker}: Non disponibile')
"
```

### Metodo 3: Yahoo Finance Web
1. Vai su https://finance.yahoo.com/
2. Cerca il ticker
3. Se non trovato, cerca nome azienda
4. Verifica simbolo corretto

---

## 💡 Suggerimenti per Ticker Internazionali

### Suffissi Exchange Comuni:

| Exchange | Suffisso | Esempio |
|----------|----------|---------|
| **USA** | (nessuno) | `AAPL`, `MSFT` |
| **London** | `.L` | `RR.L`, `RIO.L` |
| **Germany (Xetra)** | `.DE` | `SAP.DE`, `BAYN.DE` |
| **Paris** | `.PA` | `DG.PA` |
| **Switzerland** | `.SW` o `.ZU` | `HOLN.SW` |
| **Australia** | `.AX` | `BHP.AX` |
| **Amsterdam** | `.AS` | `ASML.AS` (ma ASML funziona) |
| **Hong Kong** | `.HK` | `0700.HK` |
| **Tokyo** | `.T` | `7203.T` |

---

## ⚠️ Problemi Comuni

### 1. **GDR/ADR vs Stock Diretto**
- GDR (Global Depositary Receipt) non sempre su Yahoo
- Preferisci ADR (American Depositary Receipt) se disponibile

### 2. **Suffisso Exchange Sbagliato**
- `.ASX` vs `.AX` per Australia
- `.AS` non sempre necessario per Amsterdam

### 3. **Ticker Cambiati Post-Merger**
- Società cambiano ticker dopo fusioni
- Verifica sempre notizie recenti

### 4. **Ticker Delisted**
- Società non più quotate
- Fallimenti o acquisizioni

---

## 📋 Checklist Prima di Aggiungere Ticker

- [ ] Verifica disponibilità su Yahoo Finance
- [ ] Testa download dati con `yfinance`
- [ ] Verifica periodo storico (almeno 1 anno)
- [ ] Controlla che exchange sia corretto
- [ ] Aggiungi a classificazione settoriale
- [ ] Aggiungi a classificazione geografica
- [ ] Esegui `validate_tickers.py`

---

## 🔄 Storico Modifiche

| Data | Ticker | Azione | Motivo |
|------|--------|--------|--------|
| 2026-02-02 | KAP | ❌ Rimosso | Non disponibile su Yahoo |
| 2026-02-02 | BOE.ASX | ❌ Rimosso | Non disponibile su Yahoo |
| 2026-02-02 | CSG.AS | ❌ Rimosso | Non disponibile su Yahoo |
| 2026-02-02 | UEC | ✅ Aggiunto | Alternativa uranium |
| 2026-02-02 | LMT | ✅ Aggiunto | Alternativa defense |
| 2026-02-02 | MDT, ISRG, BSX, SYK, EW | ✅ Aggiunti | Healthcare |
| 2026-02-02 | PFE, JNJ | ✅ Aggiunti | Pharma |

---

**Stato Attuale**: 
- ✅ **50 ticker validati e funzionanti**
- ✅ **12 settori ben diversificati**
- ✅ **Nessun ticker commentato o non funzionante**

---

**Ultima Verifica**: 2 Febbraio 2026  
**Tool**: `validate_tickers.py`
