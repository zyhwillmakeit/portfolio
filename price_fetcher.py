from __future__ import annotations

from datetime import date

import pandas as pd

from portfolio_engine import get_held_tickers, upsert_price


def fetch_latest_prices(tickers: list[str]) -> tuple[pd.DataFrame, list[str]]:
    if not tickers:
        return pd.DataFrame(columns=["ticker", "date", "close_price", "source"]), []

    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame(columns=["ticker", "date", "close_price", "source"]), [
            "yfinance is not installed. Run `pip install -r requirements.txt` first."
        ]

    rows = []
    errors = []
    for ticker in tickers:
        try:
            history = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
            if history.empty or "Close" not in history:
                errors.append(f"No price data returned for {ticker}.")
                continue

            last_row = history.dropna(subset=["Close"]).iloc[-1]
            price_date = last_row.name.date()
            close_price = float(last_row["Close"])
            upsert_price(ticker, price_date, close_price, "yfinance")
            rows.append(
                {
                    "ticker": ticker,
                    "date": price_date.isoformat(),
                    "close_price": close_price,
                    "source": "yfinance",
                }
            )
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")

    return pd.DataFrame(rows), errors


def update_held_ticker_prices() -> tuple[pd.DataFrame, list[str]]:
    return fetch_latest_prices(get_held_tickers())


def cache_manual_price(ticker: str, close_price: float, price_date: date | None = None) -> None:
    upsert_price(ticker, price_date or date.today(), close_price, "manual")
