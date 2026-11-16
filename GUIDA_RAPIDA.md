# 🚀 Guida Rapida - Analisi Portafoglio

## ✅ Tutti i Problemi Risolti!

### 1. ✨ Grafici a Torta Migliorati
- **Prima**: Labels illeggibili dentro le fette
- **Ora**: Labels eleganti fuori con linee, nessuna sovrapposizione

### 2. 📊 Grafici Rischio-Rendimento e Correlazioni
- **Prima**: Grafici vuoti
- **Ora**: Completamente funzionanti e interattivi

### 3. 💡 Allocazione Ottimale
- **Nuova funzionalità**: Sezione dedicata con torta e tabella dettagliata
- Include tutti i ticker con percentuali suggerite

---

## 🎯 Comandi Essenziali

### Report HTML Completo
```bash
# Attiva environment
cd /Users/pat/Desktop/python_proj/fin_analysis
source venv/bin/activate

# Genera report (profilo moderato)
python main.py

# Con profilo aggressivo
python main.py --risk aggressive

# Con profilo conservativo
python main.py --risk conservative

# Apri report nel browser
./open_report.sh
# oppure
open portfolio_report.html
```

### Visualizzazione Rapida Allocazione (Solo Terminale)
```bash
# Veloce - mostra solo allocazione ottimale
python show_allocation.py moderate
python show_allocation.py aggressive
python show_allocation.py conservative
```

### Demo Veloce (10 ticker)
```bash
python quick_start.py
```

---

## 📊 Cosa Include il Report HTML

1. **Dashboard KPI**
   - Rendimento annuale
   - Volatilità
   - Sharpe Ratio
   - Max Drawdown
   - Score diversificazione

2. **Grafico Rischio-Rendimento** ✨ FIXATO
   - Scatter plot interattivo
   - Bolle colorate per Sharpe Ratio
   - Hover con dettagli

3. **Top Performers**
   - Per rendimento
   - Per Sharpe Ratio

4. **Diversificazione** ✨ MIGLIORATO
   - Settoriale (torta elegante)
   - Geografica (torta elegante)
   - Labels fuori dalle fette

5. **Matrice di Correlazione** ✨ FIXATO
   - Heatmap interattiva
   - Top 25 titoli
   - Valori numerici chiari

6. **💡 Allocazione Ottimale Suggerita** 🆕🆕🆕
   - Grafico a torta con top 20 titoli
   - Tabella completa con:
     * Ranking
     * Percentuale per ogni titolo
     * Rendimento
     * Volatilità
     * Sharpe Ratio
   - Info box con spiegazione strategia

7. **Confronto Allocazioni**
   - Corrente vs Suggerita (se hai inserito allocazione corrente)

8. **Tabella Dettagliata**
   - Tutte le metriche per tutti i titoli

---

## 🎨 Profili di Rischio

### Conservative (Conservativo)
- Focus: Bassa volatilità
- Pesi: 40% Sharpe + 40% bassa volatilità + 20% rendimento
- Adatto per: Capitale da proteggere

### Moderate (Moderato) - DEFAULT
- Focus: Bilanciato
- Pesi: 35% rendimento + 35% Sharpe + 30% bassa volatilità
- Adatto per: Crescita moderata a lungo termine

### Aggressive (Aggressivo)
- Focus: Alto rendimento
- Pesi: 60% rendimento + 30% Sharpe + 10% bassa volatilità
- Adatto per: Massima crescita con tolleranza al rischio

---

## 💰 Come Personalizzare la Tua Allocazione

1. Apri `portfolio_config.py`

2. Modifica il dizionario `EXAMPLE_HOLDINGS`:
```python
EXAMPLE_HOLDINGS = {
    "MU": 10000,      # €10,000 in Micron
    "LITE": 8000,     # €8,000 in Lumentum
    "ENR.DE": 7000,   # €7,000 in Siemens Energy
    "CCJ": 6000,      # €6,000 in Cameco
    # ... aggiungi tutti i tuoi investimenti
}
```

3. Esegui con `--weighted`:
```bash
python main.py --weighted
```

---

## 📈 Esempio Output Allocazione Ottimale

### Nel Report HTML
- 🥧 **Grafico a torta** interattivo con top 20 titoli
- 📋 **Tabella completa** con tutti i 43 titoli:

| # | Ticker | Peso | Rendimento | Volatilità | Sharpe |
|---|--------|------|------------|------------|--------|
| 1 | MU | 3.6% | 59.3% | 36.6% | 1.57 |
| 2 | ENR.DE | 3.6% | 36.9% | 27.8% | 1.25 |
| 3 | RR.L | 3.5% | 26.5% | 20.4% | 1.20 |
| ... | ... | ... | ... | ... | ... |

---

## 🔍 Interpretazione Risultati

### Sharpe Ratio
- **> 1.5**: Eccellente
- **1.0 - 1.5**: Molto buono
- **0.5 - 1.0**: Accettabile
- **< 0.5**: Scarso

### Diversificazione Score
- **> 70**: Eccellente
- **50 - 70**: Buona
- **< 50**: Migliorabile

### Max Drawdown
- Perdita massima storica dal picco
- Più basso (meno negativo) è meglio

---

## ⚡ Tips

1. **Primo utilizzo**: Parti con `python quick_start.py` per test veloce
2. **Allocazione veloce**: Usa `python show_allocation.py moderate` per vedere solo i suggerimenti
3. **Report completo**: `python main.py` per analisi dettagliata con grafici
4. **Dati più storici**: Usa `--period 2y` o `--period 5y` per analisi più robusta
5. **Aggiorna dati**: Riesegui `python main.py` ogni settimana/mese per dati aggiornati

---

## 🆘 Troubleshooting

### "Command not found: pip"
```bash
# Assicurati di aver attivato l'environment
source venv/bin/activate
```

### "Alcuni ticker falliscono"
- Normale per mercati esteri
- Controlla i simboli in `portfolio_config.py`
- Usa suffissi corretti (.L, .DE, .PA, ecc.)

### "Report non si apre"
```bash
# Usa il path completo
open /Users/pat/Desktop/python_proj/fin_analysis/portfolio_report.html
```

---

## 📞 File di Supporto

- `README.md` - Documentazione completa
- `CHANGELOG.md` - Storia delle modifiche
- `portfolio_config.py` - Configurazione ticker
- `requirements.txt` - Dipendenze

---

**Buon investimento! 📈💰**
