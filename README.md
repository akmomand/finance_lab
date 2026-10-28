# Finance Lab

Streamlit app for exploring macro indicators (FRED) and company fundamentals (yfinance).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your FRED API key:

```
FRED_API_KEY=your_key_here
```

Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html

## Run

From the project root:

```bash
streamlit run app.py
```

## Features (in progress)

- **Macro dashboard** — CPI, PCE inflation, GDP, unemployment, manufacturing employment (PMI proxy) via FRED
- **Company overview** — quote, size, 52-week range, beta, yield, and business summary via yfinance
- **Fundamental scorecard** — ROE, ROIC, margins, leverage, liquidity with green / yellow / red bands
- **Historical trends** — last 8 quarters of growth, margins, balance sheet, and cash flow (Plotly)
- **Key ratio trends** — profitability, liquidity, solvency, and valuation over time
- **Fair value** — simple FCF DCF, Graham number, and P/E vs history
- **Peers** — editable peer tickers with suggested defaults; compare P/E, ROE, margins
- **Earnings** — last ~8 quarters estimate vs actual and surprise trends
- **Deeper company sections** — analyst sentiment, ownership, dividends coming next
