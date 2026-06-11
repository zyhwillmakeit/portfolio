from __future__ import annotations

from datetime import date

from database import init_db
from portfolio_engine import calculate_holdings, calculate_totals, save_snapshot
from price_fetcher import update_held_ticker_prices


def main() -> None:
    init_db()
    updated, errors = update_held_ticker_prices()
    holdings = calculate_holdings()
    totals = calculate_totals(holdings)
    save_snapshot(date.today(), totals)

    print(f"Updated {len(updated)} ticker price(s).")
    print(f"Portfolio market value: {totals.total_market_value:,.2f}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
