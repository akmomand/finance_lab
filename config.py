"""App configuration and shared constants."""

import os

from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "Finance Lab"
PAGE_CONFIG = {
    "page_title": APP_TITLE,
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

DEFAULT_TICKER = "AAPL"

# Fundamental scorecard bands (general screens — not industry-adjusted).
# higher_is_better: green if value >= green, yellow if >= yellow, else red
# lower_is_better:  green if value <= green, yellow if <= yellow, else red
SCORECARD_METRICS: dict[str, dict] = {
    "roe": {
        "label": "ROE",
        "format": "percent",
        "higher_is_better": True,
        "green": 0.15,
        "yellow": 0.08,
        "help": "Return on Equity — net income / shareholder equity",
    },
    "roic": {
        "label": "ROIC",
        "format": "percent",
        "higher_is_better": True,
        "green": 0.12,
        "yellow": 0.06,
        "help": "Return on Invested Capital — approx. NOPAT / (equity + debt − cash)",
    },
    "gross_margin": {
        "label": "Gross Margin",
        "format": "percent",
        "higher_is_better": True,
        "green": 0.40,
        "yellow": 0.20,
        "help": "Gross profit / revenue",
    },
    "debt_to_equity": {
        "label": "Debt / Equity",
        "format": "ratio",
        "higher_is_better": False,
        "green": 0.50,
        "yellow": 1.50,
        "help": "Total debt / shareholder equity (lower is safer)",
    },
    "current_ratio": {
        "label": "Current Ratio",
        "format": "ratio",
        "higher_is_better": True,
        "green": 1.50,
        "yellow": 1.00,
        "help": "Current assets / current liabilities",
    },
    "fcf_margin": {
        "label": "FCF Margin",
        "format": "percent",
        "higher_is_better": True,
        "green": 0.10,
        "yellow": 0.03,
        "help": "Free cash flow / revenue",
    },
}

# FRED series IDs
FRED_SERIES = {
    "cpi": "CPIAUCSL",           # Consumer Price Index
    "gdp": "GDP",                # Gross Domestic Product
    "pce": "PCEPI",              # PCE Price Index (inflation)
    "unemployment": "UNRATE",    # Unemployment Rate
    "manufacturing_pmi": "MANEMP",  # Mfg payrolls — free PMI-cycle proxy (ISM PMI is proprietary)
}

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
