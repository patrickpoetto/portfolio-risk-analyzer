#!/usr/bin/env python3
"""
Validatore di ticker - verifica disponibilità su Yahoo Finance
"""

import yfinance as yf
from portfolio_config import PORTFOLIO_TICKERS

def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    Verifica se un ticker è disponibile su Yahoo Finance
    
    Returns:
        (is_valid, message)
    """
    try:
        stock = yf.Ticker(ticker)
        # Prova a scaricare un dato recente
        hist = stock.history(period="5d")
        
        if hist.empty:
            return False, f"❌ {ticker}: Nessun dato disponibile"
        
        # Verifica che abbia un nome
        info = stock.info
        name = info.get('longName') or info.get('shortName') or 'N/A'
        
        return True, f"✅ {ticker}: {name}"
        
    except Exception as e:
        return False, f"❌ {ticker}: Errore - {str(e)[:50]}"


def validate_all_tickers(verbose=True):
    """
    Valida tutti i ticker nel portfolio
    
    Returns:
        dict: {ticker: (is_valid, message)}
    """
    results = {}
    
    print("=" * 80)
    print("🔍 VALIDAZIONE TICKER")
    print("=" * 80)
    print(f"Verifica {len(PORTFOLIO_TICKERS)} ticker...")
    print()
    
    valid_count = 0
    invalid_count = 0
    
    for ticker, name in PORTFOLIO_TICKERS.items():
        is_valid, message = validate_ticker(ticker)
        results[ticker] = (is_valid, message)
        
        if is_valid:
            valid_count += 1
            if verbose:
                print(message)
        else:
            invalid_count += 1
            print(message)
    
    print()
    print("=" * 80)
    print(f"✅ Validi: {valid_count}")
    print(f"❌ Non disponibili: {invalid_count}")
    print("=" * 80)
    
    if invalid_count > 0:
        print("\n💡 SUGGERIMENTI:")
        print("I ticker non disponibili potrebbero avere:")
        print("  • Simbolo errato per Yahoo Finance")
        print("  • Suffisso exchange sbagliato (.L, .DE, .AS, ecc.)")
        print("  • Ticker delisted o non più quotato")
        print("\nVerifica su: https://finance.yahoo.com/")
    
    return results


def suggest_alternatives():
    """
    Suggerisce alternative per ticker non disponibili
    """
    print("\n" + "=" * 80)
    print("💡 ALTERNATIVE SUGGERITE")
    print("=" * 80)
    
    suggestions = {
        "KAP": [
            "CCJ (Cameco Corp) - già presente ✅",
            "UEC (Uranium Energy) - già presente ✅",
            "URNM (Sprott Uranium ETF)",
            "URA (Global X Uranium ETF)"
        ],
        "BOE.ASX": [
            "PDN.AX (Paladin Energy - Australia)",
            "LEU (Centrus Energy) - già presente ✅",
            "BWXT (BWX Technologies) - già presente ✅"
        ],
        "CSG.AS": [
            "RTX (RTX Corporation) - già presente ✅",
            "LMT (Lockheed Martin) - già presente ✅",
            "BA (Boeing)",
            "NOC (Northrop Grumman)"
        ]
    }
    
    for ticker, alts in suggestions.items():
        print(f"\n{ticker}:")
        for alt in alts:
            print(f"  → {alt}")
    
    print()


if __name__ == "__main__":
    results = validate_all_tickers(verbose=True)
    
    # Mostra solo invalidi in riepilogo
    invalid = [t for t, (valid, _) in results.items() if not valid]
    
    if invalid:
        print(f"\n⚠️  Ticker da rimuovere o sostituire: {', '.join(invalid)}")
        suggest_alternatives()
    else:
        print("\n🎉 Tutti i ticker sono validi!")
