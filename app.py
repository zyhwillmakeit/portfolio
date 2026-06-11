from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from database import init_db
from portfolio_engine import (
    add_transaction,
    calculate_holdings,
    calculate_totals,
    calculate_ytd_return,
    delete_transaction,
    load_snapshots,
    load_transactions,
    save_snapshot,
)
from price_fetcher import cache_manual_price, update_held_ticker_prices


st.set_page_config(page_title="Portfolio Monitor", layout="wide")
init_db()


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2%}"


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"${value:,.2f}"


st.title("Portfolio Monitor")

with st.sidebar:
    st.header("Add Transaction")
    with st.form("add_transaction", clear_on_submit=True):
        ticker = st.text_input("Ticker", placeholder="AAPL")
        buy_date = st.date_input("Buy date", value=date.today())
        buy_price = st.number_input("Buy price", min_value=0.0, value=100.0, step=1.0)
        quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=1.0)
        currency = st.selectbox("Currency", ["USD", "HKD", "CNY", "EUR", "JPY"])
        note = st.text_area("Note", height=80)
        submitted = st.form_submit_button("Add")

    if submitted:
        if not ticker.strip():
            st.error("Ticker is required.")
        elif buy_price <= 0 or quantity <= 0:
            st.error("Buy price and quantity must be positive.")
        else:
            add_transaction(ticker, buy_date, buy_price, quantity, currency, note)
            st.success(f"Added {ticker.strip().upper()}.")
            st.rerun()

    st.divider()
    st.header("Manual Price")
    with st.form("manual_price", clear_on_submit=True):
        manual_ticker = st.text_input("Price ticker", placeholder="MSFT")
        manual_date = st.date_input("Price date", value=date.today())
        manual_price = st.number_input("Close price", min_value=0.0, value=100.0, step=1.0)
        manual_submitted = st.form_submit_button("Save Price")

    if manual_submitted:
        if not manual_ticker.strip() or manual_price <= 0:
            st.error("Ticker and a positive close price are required.")
        else:
            cache_manual_price(manual_ticker, manual_price, manual_date)
            st.success(f"Saved {manual_ticker.strip().upper()} price.")
            st.rerun()

holdings = calculate_holdings()
totals = calculate_totals(holdings)
snapshots = load_snapshots()
ytd_return = calculate_ytd_return(snapshots, totals.total_market_value)

top_cols = st.columns([1, 1, 1, 1, 1])
top_cols[0].metric("Market Value", money(totals.total_market_value))
top_cols[1].metric("Cost Basis", money(totals.total_cost))
top_cols[2].metric("Unrealized Gain", money(totals.unrealized_gain))
top_cols[3].metric("Total Return", pct(totals.total_return_pct))
top_cols[4].metric("YTD Return", pct(ytd_return))

action_cols = st.columns([1, 1, 4])
if action_cols[0].button("Update Latest Prices", use_container_width=True):
    updated, errors = update_held_ticker_prices()
    refreshed_holdings = calculate_holdings()
    refreshed_totals = calculate_totals(refreshed_holdings)
    save_snapshot(date.today(), refreshed_totals)
    if not updated.empty:
        st.success(f"Updated {len(updated)} ticker(s).")
    if errors:
        st.warning("\n".join(errors))
    st.rerun()

if action_cols[1].button("Save Snapshot", use_container_width=True):
    save_snapshot(date.today(), totals)
    st.success("Snapshot saved.")
    st.rerun()

tab_holdings, tab_transactions, tab_charts, tab_export = st.tabs(
    ["Holdings", "Transactions", "Charts", "Export"]
)

with tab_holdings:
    if holdings.empty:
        st.info("Add your first transaction from the sidebar.")
    else:
        display = holdings.copy()
        for col in ["cost_basis", "avg_cost", "current_price", "market_value", "unrealized_gain"]:
            display[col] = display[col].map(money)
        for col in ["total_return_pct", "annualized_return_pct", "weight"]:
            display[col] = display[col].map(pct)
        display = display.rename(
            columns={
                "ticker": "Ticker",
                "currency": "Currency",
                "quantity": "Quantity",
                "cost_basis": "Cost Basis",
                "avg_cost": "Avg Cost",
                "current_price": "Current Price",
                "price_date": "Price Date",
                "market_value": "Market Value",
                "unrealized_gain": "Unrealized Gain",
                "total_return_pct": "Total Return",
                "annualized_return_pct": "Annualized Return",
                "weight": "Weight",
                "first_buy_date": "First Buy Date",
            }
        )
        st.dataframe(display, use_container_width=True, hide_index=True)

with tab_transactions:
    transactions = load_transactions()
    if transactions.empty:
        st.info("No transactions yet.")
    else:
        st.dataframe(transactions, use_container_width=True, hide_index=True)
        delete_id = st.number_input(
            "Transaction ID to delete",
            min_value=0,
            value=0,
            step=1,
            help="Use the id from the transactions table.",
        )
        if st.button("Delete Transaction") and delete_id:
            delete_transaction(int(delete_id))
            st.success(f"Deleted transaction {delete_id}.")
            st.rerun()

with tab_charts:
    if holdings.empty:
        st.info("Charts appear after holdings have prices.")
    else:
        chart_data = holdings.dropna(subset=["market_value"])
        if chart_data.empty:
            st.info("Update or enter prices to show charts.")
        else:
            chart_cols = st.columns(2)
            allocation = px.pie(
                chart_data,
                names="ticker",
                values="market_value",
                hole=0.45,
                title="Allocation",
            )
            chart_cols[0].plotly_chart(allocation, use_container_width=True)

            returns = px.bar(
                chart_data,
                x="ticker",
                y="total_return_pct",
                title="Return by Holding",
                labels={"total_return_pct": "Total Return", "ticker": "Ticker"},
            )
            returns.update_yaxes(tickformat=".0%")
            chart_cols[1].plotly_chart(returns, use_container_width=True)

    snapshots = load_snapshots()
    if not snapshots.empty:
        value_curve = px.line(
            snapshots,
            x="date",
            y="total_market_value",
            title="Portfolio Value",
            labels={"date": "Date", "total_market_value": "Market Value"},
            markers=True,
        )
        st.plotly_chart(value_curve, use_container_width=True)

with tab_export:
    transactions = load_transactions()
    export_cols = st.columns(2)
    export_cols[0].download_button(
        "Download Transactions CSV",
        data=transactions.to_csv(index=False).encode("utf-8"),
        file_name="transactions.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=transactions.empty,
    )
    export_cols[1].download_button(
        "Download Holdings CSV",
        data=holdings.to_csv(index=False).encode("utf-8"),
        file_name="holdings.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=holdings.empty,
    )
