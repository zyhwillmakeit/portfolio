# Portfolio Monitor

Local MVP portfolio dashboard built with Streamlit, SQLite, yfinance, pandas, and Plotly.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

## Files

```text
data/portfolio.db       SQLite database, created on first run
app.py                  Streamlit dashboard
database.py             SQLite connection and schema
portfolio_engine.py     Holdings, return, snapshot, and export logic
price_fetcher.py        yfinance/manual price cache
scheduler.py            Optional command-line price update
requirements.txt        Python dependencies
```

## Optional Scheduler

After adding transactions, you can update prices and save a snapshot from the command line:

```bash
python scheduler.py
```
