#!/bin/bash
# Script to open the HTML report in the browser

if [ -f "portfolio_report.html" ]; then
    open portfolio_report.html
    echo "✅ Report opened in the browser!"
else
    echo "❌ Report not found. Run this first: python main.py"
fi
