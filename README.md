# 投资组合监控

这是一个本地运行的投资组合监控 MVP，使用 Streamlit、SQLite、yfinance、pandas 和 Plotly 构建。

## 核心流程

1. 在侧边栏存入资金。
2. 添加股票买入交易。
3. 系统会自动从可用资金中扣除买入金额。
4. 点击更新最新价格，刷新持仓、收益率、图表和快照。

页面顶部会显示 USD 可用资金。资金页会按币种展示余额和完整资金流水。

年化收益率只会在持仓超过 30 天后显示，避免同日或短期持仓产生夸张的年化结果。年初至今收益率需要当前年份内有一条早于今天的快照作为基准后才会显示。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

然后打开：

```text
http://localhost:8501
```

## 文件结构

```text
data/portfolio.db       SQLite 数据库，首次运行时自动创建
app.py                  Streamlit 仪表盘
database.py             SQLite 连接和表结构
portfolio_engine.py     持仓、收益率、快照和导出逻辑
price_fetcher.py        yfinance/手动价格缓存
scheduler.py            可选的命令行价格更新脚本
requirements.txt        Python 依赖
```

## 可选定时任务

添加交易后，也可以通过命令行更新价格并保存快照：

```bash
python scheduler.py
```
