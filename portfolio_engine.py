from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from database import get_connection


@dataclass(frozen=True)
class PortfolioTotals:
    total_cost: float
    total_market_value: float
    unrealized_gain: float
    total_return_pct: float


def load_transactions() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, ticker, buy_date, buy_price, quantity, currency, note, created_at
            FROM transactions
            ORDER BY buy_date DESC, id DESC
            """,
            conn,
        )


def load_latest_prices() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT p.ticker, p.date, p.close_price, p.source
            FROM prices p
            JOIN (
                SELECT ticker, MAX(date) AS max_date
                FROM prices
                GROUP BY ticker
            ) latest
              ON p.ticker = latest.ticker
             AND p.date = latest.max_date
            """,
            conn,
        )


def add_transaction(
    ticker: str,
    buy_date: date,
    buy_price: float,
    quantity: float,
    currency: str,
    note: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transactions (ticker, buy_date, buy_price, quantity, currency, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticker.strip().upper(),
                buy_date.isoformat(),
                buy_price,
                quantity,
                currency.strip().upper(),
                note.strip(),
            ),
        )


def delete_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


def upsert_price(ticker: str, price_date: date, close_price: float, source: str = "manual") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prices (ticker, date, close_price, source, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker, date) DO UPDATE SET
                close_price = excluded.close_price,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (ticker.strip().upper(), price_date.isoformat(), close_price, source),
        )


def get_held_tickers() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ticker
            FROM transactions
            ORDER BY ticker
            """
        ).fetchall()
    return [row["ticker"] for row in rows]


def calculate_holdings(as_of: date | None = None) -> pd.DataFrame:
    as_of = as_of or date.today()
    tx = load_transactions()
    if tx.empty:
        return pd.DataFrame()

    latest_prices = load_latest_prices()
    price_map = latest_prices.set_index("ticker")["close_price"].to_dict() if not latest_prices.empty else {}
    price_date_map = latest_prices.set_index("ticker")["date"].to_dict() if not latest_prices.empty else {}

    holdings = tx.groupby(["ticker", "currency"], as_index=False).agg(
        quantity=("quantity", "sum"),
        cost_basis=("buy_price", lambda s: float((s * tx.loc[s.index, "quantity"]).sum())),
        first_buy_date=("buy_date", "min"),
    )
    holdings["avg_cost"] = holdings["cost_basis"] / holdings["quantity"]
    holdings["current_price"] = holdings["ticker"].map(price_map)
    holdings["price_date"] = holdings["ticker"].map(price_date_map)
    holdings["market_value"] = holdings["current_price"] * holdings["quantity"]
    holdings["unrealized_gain"] = holdings["market_value"] - holdings["cost_basis"]
    holdings["total_return_pct"] = holdings["unrealized_gain"] / holdings["cost_basis"]

    first_buy_dates = pd.to_datetime(holdings["first_buy_date"]).dt.date
    holding_days = first_buy_dates.map(lambda d: max((as_of - d).days, 1))
    growth = holdings["market_value"] / holdings["cost_basis"]
    holdings["annualized_return_pct"] = growth.pow(365 / holding_days) - 1

    total_market_value = holdings["market_value"].sum(skipna=True)
    holdings["weight"] = holdings["market_value"] / total_market_value if total_market_value else 0

    return holdings.sort_values("market_value", ascending=False, na_position="last")


def calculate_totals(holdings: pd.DataFrame) -> PortfolioTotals:
    if holdings.empty:
        return PortfolioTotals(0, 0, 0, 0)

    total_cost = float(holdings["cost_basis"].sum())
    total_market_value = float(holdings["market_value"].sum(skipna=True))
    unrealized_gain = total_market_value - total_cost
    total_return_pct = unrealized_gain / total_cost if total_cost else 0
    return PortfolioTotals(total_cost, total_market_value, unrealized_gain, total_return_pct)


def save_snapshot(snapshot_date: date, totals: PortfolioTotals) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (date, total_cost, total_market_value, total_return_pct, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(date) DO UPDATE SET
                total_cost = excluded.total_cost,
                total_market_value = excluded.total_market_value,
                total_return_pct = excluded.total_return_pct,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                snapshot_date.isoformat(),
                totals.total_cost,
                totals.total_market_value,
                totals.total_return_pct,
            ),
        )


def load_snapshots() -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, total_cost, total_market_value, total_return_pct
            FROM portfolio_snapshots
            ORDER BY date
            """,
            conn,
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def calculate_ytd_return(snapshots: pd.DataFrame, current_value: float) -> float | None:
    if snapshots.empty:
        return None

    current_year = datetime.now().year
    ytd = snapshots[snapshots["date"].dt.year == current_year]
    if ytd.empty:
        return None

    start_value = float(ytd.iloc[0]["total_market_value"])
    if start_value == 0:
        return None
    return current_value / start_value - 1
