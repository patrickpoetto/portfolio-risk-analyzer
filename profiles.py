"""
Caricamento profili investitore da file JSON (cartella profiles/).

Permette di generare report per persone diverse (capitale, profilo di
rischio, periodo, holding attuali) senza scrivere nulla direttamente in
portfolio_config.py e senza modificare il codice ad ogni nuova persona:
basta aggiungere un nuovo file profiles/<nome>.json.
"""

import json
import os
from typing import Dict, List
from portfolio_config import DEFAULT_CONFIG

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


def list_profiles() -> List[str]:
    """Elenca i profili disponibili (nomi file .json in profiles/, esclusi quelli che iniziano con '_')."""
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        f[:-5] for f in os.listdir(PROFILES_DIR)
        if f.endswith('.json') and not f.startswith('_')
    )


def load_profile(name: str) -> Dict:
    """
    Carica un profilo da profiles/<name>.json. I campi non specificati nel
    JSON vengono completati con i default di DEFAULT_CONFIG (portfolio_config.py).

    Schema atteso (tutti i campi opzionali):
        {
            "name": "Nome persona",
            "capital": 50000,
            "risk_profile": "moderate",     // conservative | moderate | aggressive
            "period": "5y",                 // 1y | 2y | 5y | max
            "output_file": "report_nome.html",
            "full_universe": false,
            "holdings": {"AAPL": 5000, "MSFT": 3000},   // holding attuali (EUR/USD), opzionale
            "sector_tilts": {"Banking & Financial Services": -0.15, "Mining & Materials": 0.05}
            // preferenza personale: sposta punti percentuali di peso da un
            // settore all'altro dopo l'ottimizzazione (positivo = aumenta,
            // negativo = riduce). I nomi settore devono corrispondere a
            // quelli in SECTOR_CLASSIFICATION (portfolio_config.py)
        }

    Returns:
        Dict con i campi risolti (name, capital, risk_profile, period,
        output_file, full_universe, holdings, sector_tilts)

    Raises:
        FileNotFoundError se il profilo non esiste (con elenco di quelli disponibili)
        ValueError se il JSON è malformato
    """
    path = os.path.join(PROFILES_DIR, f"{name}.json")

    if not os.path.isfile(path):
        available = list_profiles()
        available_str = ", ".join(available) if available else "nessuno (aggiungi un file in profiles/)"
        raise FileNotFoundError(
            f"Profilo '{name}' non trovato in {PROFILES_DIR}. Profili disponibili: {available_str}"
        )

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Profilo '{name}' non è un JSON valido: {e}")

    holdings = data.get('holdings', {}) or {}
    if not isinstance(holdings, dict):
        raise ValueError(f"Profilo '{name}': 'holdings' deve essere un oggetto {{ticker: importo}}")

    sector_tilts = data.get('sector_tilts', {}) or {}
    if not isinstance(sector_tilts, dict):
        raise ValueError(f"Profilo '{name}': 'sector_tilts' deve essere un oggetto {{settore: delta}}")

    return {
        'name': data.get('name', name),
        'capital': float(data.get('capital', DEFAULT_CONFIG['capital'])),
        'risk_profile': data.get('risk_profile', DEFAULT_CONFIG['risk_profile']),
        'period': data.get('period', DEFAULT_CONFIG['period']),
        'output_file': data.get('output_file', f"report_{name}.html"),
        'full_universe': bool(data.get('full_universe', False)),
        'holdings': {k: float(v) for k, v in holdings.items()},
        'sector_tilts': {k: float(v) for k, v in sector_tilts.items()},
    }
