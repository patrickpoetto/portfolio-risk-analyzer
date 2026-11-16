"""
Loads investor profiles from JSON files (profiles/ folder).

Allows generating reports for different people (capital, risk profile,
period, current holdings) without writing anything directly into
portfolio_config.py and without touching the code for each new person:
just add a new profiles/<name>.json file.
"""

import json
import os
from typing import Dict, List
from portfolio_config import DEFAULT_CONFIG

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


def list_profiles() -> List[str]:
    """Lists the available profiles (.json file names in profiles/, excluding those starting with '_')."""
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        f[:-5] for f in os.listdir(PROFILES_DIR)
        if f.endswith('.json') and not f.startswith('_')
    )


def load_profile(name: str) -> Dict:
    """
    Loads a profile from profiles/<name>.json. Fields not specified in the
    JSON are filled in with the defaults from DEFAULT_CONFIG (portfolio_config.py).

    Expected schema (all fields optional):
        {
            "name": "Person name",
            "capital": 50000,
            "risk_profile": "moderate",     // conservative | moderate | aggressive
            "period": "5y",                 // 1y | 2y | 5y | max
            "output_file": "report_name.html",
            "full_universe": false,
            "holdings": {"AAPL": 5000, "MSFT": 3000},   // current holdings (EUR/USD), optional
            "sector_tilts": {"Banking & Financial Services": -0.15, "Mining & Materials": 0.05}
            // personal preference: shifts percentage points of weight from
            // one sector to another after optimization (positive =
            // increase, negative = decrease). Sector names must match those
            // in SECTOR_CLASSIFICATION (portfolio_config.py)
        }

    Returns:
        Dict with the resolved fields (name, capital, risk_profile, period,
        output_file, full_universe, holdings, sector_tilts)

    Raises:
        FileNotFoundError if the profile doesn't exist (with a list of the available ones)
        ValueError if the JSON is malformed
    """
    path = os.path.join(PROFILES_DIR, f"{name}.json")

    if not os.path.isfile(path):
        available = list_profiles()
        available_str = ", ".join(available) if available else "none (add a file under profiles/)"
        raise FileNotFoundError(
            f"Profile '{name}' not found in {PROFILES_DIR}. Available profiles: {available_str}"
        )

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Profile '{name}' is not valid JSON: {e}")

    holdings = data.get('holdings', {}) or {}
    if not isinstance(holdings, dict):
        raise ValueError(f"Profile '{name}': 'holdings' must be an object {{ticker: amount}}")

    sector_tilts = data.get('sector_tilts', {}) or {}
    if not isinstance(sector_tilts, dict):
        raise ValueError(f"Profile '{name}': 'sector_tilts' must be an object {{sector: delta}}")

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
