# Finance Lab

Streamlit app for US macro indicators (FRED) and public-company research (yfinance).

> Educational tool only — not investment advice.

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

Open the local URL Streamlit prints (usually http://localhost:8501).

### Sidebar tips

- **Clear data cache** — wipe cached Yahoo/FRED responses after rate limits or stale data
- Company mode loads **one section at a time** (section dropdown) to reduce Yahoo request volume

## Features

### Macro

- CPI, PCE inflation, GDP, unemployment
- Manufacturing employment as a free PMI-cycle proxy (`MANEMP` on FRED)

### Company research

1. **Overview** — quote, size, 52-week range, beta, yield, business summary  
2. **Fundamental scorecard** — ROE, ROIC, margins, leverage, liquidity (green / yellow / red)  
3. **Historical trends** — last ~8 quarters of growth, margins, balance sheet, cash flow  
4. **Key ratio trends** — profitability, liquidity, solvency, valuation  
5. **Fair value** — FCF DCF, Graham number, P/E vs history  
6. **Peers** — editable peer list with suggested defaults  
7. **Earnings** — estimate vs actual and surprise trends  
8. **Analyst sentiment** — ratings (when available) and price targets  
9. **Ownership** — institutions and insider activity  
10. **Dividends** — yield, payout, growth, history, increase streak  

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| Company data fails for every ticker | Yahoo rate limit — wait ~1 minute, click **Clear data cache**, retry |
| Macro page empty | Set `FRED_API_KEY` in `.env` and restart Streamlit |
| Some peer / earnings rows blank | Coverage varies by ticker on free Yahoo data |
| Nested expander errors | Upgrade Streamlit; company sections use a selectbox (not nested expanders) |

## Project layout

```
app.py              # Streamlit entry
config.py           # constants, FRED series, scorecard bands
data/               # fetchers (macro, company, scorecard, trends, …)
ui/                 # Streamlit views
utils/              # formatting helpers
```
