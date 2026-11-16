#!/bin/bash
# Script per aprire il report HTML nel browser

if [ -f "portfolio_report.html" ]; then
    open portfolio_report.html
    echo "✅ Report aperto nel browser!"
else
    echo "❌ Report non trovato. Esegui prima: python main.py"
fi
