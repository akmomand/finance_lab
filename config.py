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

# Scorecard thresholds — filled in later steps (green / yellow / red bands)
SCORECARD_THRESHOLDS: dict[str, dict] = {
    "green": {},
    "yellow": {},
    "red": {},
}

# FRED series IDs
FRED_SERIES = {
    "cpi": "CPIAUCSL",           # Consumer Price Index
    "gdp": "GDP",                # Gross Domestic Product
    "pce": "PCEPI",              # PCE Price Index (inflation)
    "unemployment": "UNRATE",    # Unemployment Rate
    "manufacturing_pmi": "MANEMP",  # Manufacturing employment (PMI proxy on FRED)
}

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
