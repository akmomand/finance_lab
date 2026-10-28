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
- **Company research** — overview and deeper sections coming in later steps
