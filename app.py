from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from database import init_db
from portfolio_engine import (
    InsufficientFundsError,
    add_transaction,
    add_deposit,
    calculate_holdings,
    calculate_totals,
    calculate_ytd_return,
    delete_transaction,
    get_available_fund,
    get_available_funds,
    load_cash_ledger,
    load_snapshots,
    load_transactions,
    save_snapshot,
)
from price_fetcher import cache_manual_price, update_held_ticker_prices


st.set_page_config(page_title="投资组合监控", layout="wide")
init_db()

st.markdown(
    """
    <style>
    #MainMenu, footer, header [data-testid="stToolbar"], .stDeployButton {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "暂无"
    return f"{value:.2%}"


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "暂无"
    return f"${value:,.2f}"


st.title("投资组合监控")

with st.sidebar:
    st.header("存入资金")
    with st.form("add_deposit", clear_on_submit=True):
        deposit_date = st.date_input("存入日期", value=date.today())
        deposit_amount = st.number_input("存入金额", min_value=0.0, value=1000.0, step=100.0)
        deposit_currency = st.selectbox("存入币种", ["USD", "HKD", "CNY", "EUR", "JPY"])
        deposit_note = st.text_input("备注", placeholder="初始资金")
        deposit_submitted = st.form_submit_button("存入")

    if deposit_submitted:
        if deposit_amount <= 0:
            st.error("存入金额必须大于 0。")
        else:
            add_deposit(deposit_date, deposit_amount, deposit_currency, deposit_note)
            st.success(f"已存入 {money(deposit_amount)} {deposit_currency}。")
            st.rerun()

    st.divider()
    st.header("添加买入交易")
    with st.form("add_transaction", clear_on_submit=True):
        ticker = st.text_input("股票代码", placeholder="AAPL")
        buy_date = st.date_input("买入日期", value=date.today())
        buy_price = st.number_input("买入价格", min_value=0.0, value=100.0, step=1.0)
        quantity = st.number_input("数量", min_value=0.0, value=1.0, step=1.0)
        currency = st.selectbox("币种", ["USD", "HKD", "CNY", "EUR", "JPY"])
        note = st.text_area("备注", height=80)
        submitted = st.form_submit_button("添加")

    if submitted:
        if not ticker.strip():
            st.error("请输入股票代码。")
        elif buy_price <= 0 or quantity <= 0:
            st.error("买入价格和数量必须大于 0。")
        else:
            try:
                add_transaction(ticker, buy_date, buy_price, quantity, currency, note)
                st.success(f"已添加 {ticker.strip().upper()}，并扣除 {money(buy_price * quantity)}。")
                st.rerun()
            except InsufficientFundsError as exc:
                st.error(str(exc))

    st.divider()
    st.header("手动录入价格")
    with st.form("manual_price", clear_on_submit=True):
        manual_ticker = st.text_input("股票代码", placeholder="MSFT")
        manual_date = st.date_input("价格日期", value=date.today())
        manual_price = st.number_input("收盘价", min_value=0.0, value=100.0, step=1.0)
        manual_submitted = st.form_submit_button("保存价格")

    if manual_submitted:
        if not manual_ticker.strip() or manual_price <= 0:
            st.error("请输入股票代码和大于 0 的收盘价。")
        else:
            cache_manual_price(manual_ticker, manual_price, manual_date)
            st.success(f"已保存 {manual_ticker.strip().upper()} 的价格。")
            st.rerun()

holdings = calculate_holdings()
totals = calculate_totals(holdings)
snapshots = load_snapshots()
ytd_return = calculate_ytd_return(snapshots, totals.total_market_value)
available_usd = get_available_fund("USD")

top_cols = st.columns([1, 1, 1, 1, 1, 1])
top_cols[0].metric("可用资金", money(available_usd))
top_cols[1].metric("当前市值", money(totals.total_market_value))
top_cols[2].metric("持仓成本", money(totals.total_cost))
top_cols[3].metric("未实现盈亏", money(totals.unrealized_gain))
top_cols[4].metric("总收益率", pct(totals.total_return_pct))
top_cols[5].metric("年初至今收益率", pct(ytd_return))

action_cols = st.columns([1, 1, 4])
if action_cols[0].button("更新最新价格", width="stretch"):
    updated, errors = update_held_ticker_prices()
    refreshed_holdings = calculate_holdings()
    refreshed_totals = calculate_totals(refreshed_holdings)
    save_snapshot(date.today(), refreshed_totals)
    if not updated.empty:
        st.success(f"已更新 {len(updated)} 个股票价格。")
    if errors:
        st.warning("\n".join(errors))
    st.rerun()

if action_cols[1].button("保存快照", width="stretch"):
    save_snapshot(date.today(), totals)
    st.success("快照已保存。")
    st.rerun()

tab_holdings, tab_cash, tab_transactions, tab_charts, tab_export = st.tabs(
    ["持仓", "资金", "交易记录", "图表", "导出"]
)

with tab_holdings:
    if holdings.empty:
        st.info("请先在侧边栏添加第一笔交易。")
    else:
        display = holdings.copy()
        for col in ["cost_basis", "avg_cost", "current_price", "market_value", "unrealized_gain"]:
            display[col] = display[col].map(money)
        for col in ["total_return_pct", "annualized_return_pct", "weight"]:
            display[col] = display[col].map(pct)
        display = display.rename(
            columns={
                "ticker": "股票代码",
                "currency": "币种",
                "quantity": "数量",
                "cost_basis": "持仓成本",
                "avg_cost": "平均成本",
                "current_price": "当前价格",
                "price_date": "价格日期",
                "market_value": "当前市值",
                "unrealized_gain": "未实现盈亏",
                "total_return_pct": "总收益率",
                "annualized_return_pct": "年化收益率",
                "weight": "组合占比",
                "first_buy_date": "首次买入日期",
            }
        )
        st.table(display)

with tab_cash:
    balances = get_available_funds()
    ledger = load_cash_ledger()
    if balances.empty:
        st.info("买入股票前，请先在侧边栏存入资金。")
    else:
        st.subheader("各币种可用资金")
        balance_display = balances.copy()
        balance_display["available_fund"] = balance_display["available_fund"].map(lambda value: f"{value:,.2f}")
        balance_display = balance_display.rename(
            columns={"currency": "币种", "available_fund": "可用资金"}
        )
        st.table(balance_display)

    if not ledger.empty:
        st.subheader("资金流水")
        ledger_display = ledger.copy()
        ledger_display["amount"] = ledger_display["amount"].map(lambda value: f"{value:,.2f}")
        ledger_display["entry_type"] = ledger_display["entry_type"].replace(
            {"DEPOSIT": "存入", "PURCHASE": "买入扣款"}
        )
        ledger_display = ledger_display.rename(
            columns={
                "id": "ID",
                "entry_date": "日期",
                "amount": "金额",
                "currency": "币种",
                "entry_type": "类型",
                "related_transaction_id": "关联交易 ID",
                "note": "备注",
                "created_at": "创建时间",
            }
        )
        st.table(ledger_display)

with tab_transactions:
    transactions = load_transactions()
    if transactions.empty:
        st.info("暂无交易记录。")
    else:
        transaction_display = transactions.rename(
            columns={
                "id": "ID",
                "ticker": "股票代码",
                "buy_date": "买入日期",
                "buy_price": "买入价格",
                "quantity": "数量",
                "currency": "币种",
                "note": "备注",
                "created_at": "创建时间",
            }
        )
        st.table(transaction_display)
        delete_id = st.number_input(
            "要删除的交易 ID",
            min_value=0,
            value=0,
            step=1,
            help="请使用交易记录表中的 ID。",
        )
        if st.button("删除交易") and delete_id:
            delete_transaction(int(delete_id))
            st.success(f"已删除交易 {delete_id}。")
            st.rerun()

with tab_charts:
    if holdings.empty:
        st.info("持仓有价格后会显示图表。")
    else:
        chart_data = holdings.dropna(subset=["market_value"])
        if chart_data.empty:
            st.info("请更新或手动录入价格后查看图表。")
        else:
            chart_cols = st.columns(2)
            allocation = px.pie(
                chart_data,
                names="ticker",
                values="market_value",
                hole=0.45,
                title="资产配置",
            )
            chart_cols[0].plotly_chart(
                allocation,
                width="stretch",
                config={"displayModeBar": False},
            )

            returns = px.bar(
                chart_data,
                x="ticker",
                y="total_return_pct",
                title="各持仓收益率",
                labels={"total_return_pct": "总收益率", "ticker": "股票代码"},
            )
            returns.update_yaxes(tickformat=".0%")
            chart_cols[1].plotly_chart(
                returns,
                width="stretch",
                config={"displayModeBar": False},
            )

    snapshots = load_snapshots()
    if not snapshots.empty:
        value_curve = px.line(
            snapshots,
            x="date",
            y="total_market_value",
            title="组合市值走势",
            labels={"date": "日期", "total_market_value": "当前市值"},
            markers=True,
        )
        st.plotly_chart(value_curve, width="stretch", config={"displayModeBar": False})

with tab_export:
    transactions = load_transactions()
    export_cols = st.columns(2)
    export_cols[0].download_button(
        "下载交易记录 CSV",
        data=transactions.to_csv(index=False).encode("utf-8"),
        file_name="transactions.csv",
        mime="text/csv",
        width="stretch",
        disabled=transactions.empty,
    )
    export_cols[1].download_button(
        "下载持仓 CSV",
        data=holdings.to_csv(index=False).encode("utf-8"),
        file_name="holdings.csv",
        mime="text/csv",
        width="stretch",
        disabled=holdings.empty,
    )
    ledger = load_cash_ledger()
    export_cols[0].download_button(
        "下载资金流水 CSV",
        data=ledger.to_csv(index=False).encode("utf-8"),
        file_name="cash_ledger.csv",
        mime="text/csv",
        width="stretch",
        disabled=ledger.empty,
    )
