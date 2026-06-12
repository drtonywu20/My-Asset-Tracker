import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(
    page_title="Tony's Asset Dashboard",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="collapsed" # 預設將側邊欄收起
)

# Custom Styling to match the original React dark cosmic aesthetic
st.markdown("""
<style>
    .stApp { background-color: #0B0E14; color: #F1F5F9; }
    header[data-testid="stHeader"] { background-color: #0B0E14; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 700; color: #E2E9EF; }
    .highlight-title { color: #E2E9F4; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 2rem !important; }
    div[data-testid="stMetricLabel"] { color: #64748B !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.1em; }
    .css-1r6g72q, .stCollapse { border: 1px solid #1E293B !important; background-color: #0F172A !important; border-radius: 12px; padding: 1rem; }
    
    /* Custom styling for our new interactive table rows */
    .row-divider { border-bottom: 1px solid #1E293B; margin-top: 0.5rem; margin-bottom: 0.5rem; }
    .table-header { color: #94A3B8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;}
</style>
""", unsafe_allow_html=True)

# Path to local database
DB_FILE = "assets.json"

# Default fallback/initial assets
DEFAULT_ASSETS = [
    {"name": "元大台灣50正2", "symbol": "00631L.TW", "category": "tw_stock", "quantity": 131000.0},
    {"name": "00981A", "symbol": "00981A.TW", "category": "tw_stock", "quantity": 18000.0},
    {"name": "Berkshire Hathaway Inc.", "symbol": "BRK-B", "category": "us_stock", "quantity": 65.0},
    {"name": "Tesla, Inc.", "symbol": "TSLA", "category": "us_stock", "quantity": 155.4},
    {"name": "SPDR Gold MiniShares", "symbol": "GLDM", "category": "us_stock", "quantity": 189.0},
    {"name": "iShares Russell Top 200 Growth ETF", "symbol": "IWY", "category": "us_stock", "quantity": 66.0},
    {"name": "MicroStrategy Inc.", "symbol": "MSTR", "category": "us_stock", "quantity": 13.0},
    {"name": "NVIDIA Corporation", "symbol": "NVDA", "category": "us_stock", "quantity": 110.0},
    {"name": "Bitcoin", "symbol": "BTC-USD", "category": "crypto", "quantity": 0.09869},
    {"name": "Ethereum", "symbol": "ETH-USD", "category": "crypto", "quantity": 0.90},
    {"name": "Cash (TWD)", "symbol": "TWD", "category": "cash", "quantity": 1000000.0}
]

CATEGORY_LABELS = {"tw_stock": "Taiwan Stocks", "us_stock": "US Stocks", "crypto": "Cryptocurrency", "cash": "Cash & Equivalents"}
CATEGORY_COLORS = {"tw_stock": "#3B82F6", "us_stock": "#8B5CF6", "crypto": "#F59E0B", "cash": "#10B981"}

# ----------------- Helper Functions -----------------

def load_assets():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return DEFAULT_ASSETS
    else:
        save_assets(DEFAULT_ASSETS)
        return DEFAULT_ASSETS

def save_assets(assets_list):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(assets_list, f, ensure_ascii=False, indent=2)

def format_currency_twd(val): return f"NT$ {val:,.0f}"

def format_currency_foreign(val, currency):
    if currency == "TWD": return f"NT$ {val:,.2f}"
    elif currency == "USD": return f"${val:,.2f}"
    return f"{currency} {val:,.4f}"

# ----------------- Core Data Fetching -----------------

@st.cache_data(ttl=300)
def fetch_realtime_market_data(assets_list):
    """最純粹的獨立抓取法：不計算時區、不刪除行數，直接拿 yfinance 過濾好雜訊的最新日K線"""
    quote_data = {}
    exchange_rate = 32.5
    
    try:
        fx_hist = yf.Ticker("USDTWD=X").history(period="5d", interval="1d")
        if not fx_hist.empty:
            exchange_rate = float(fx_hist['Close'].dropna().iloc[-1])
    except: pass

    for asset in assets_list:
        if asset["category"] == "cash": continue
        sym = asset["symbol"]
        if sym in quote_data: continue
            
        try:
            hist = yf.Ticker(sym).history(period="5d", interval="1d")
            hist = hist.dropna(subset=['Close'])
            
            if hist.empty: continue
            
            price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else price
            
            quote_data[sym] = {"price": float(price), "prev_close": float(prev_close)}
        except Exception:
            pass
            
    portfolio_assets = []
    for asset in assets_list:
        asset_id = asset.get("id", asset["symbol"])
        if asset["category"] == "cash":
            portfolio_assets.append({
                "id": asset_id, "name": asset["name"], "symbol": asset["symbol"], "category": asset["category"],
                "quantity": asset["quantity"], "currentPrice": 1.0, "currency": "TWD",
                "totalValueTWD": asset["quantity"], "dayChangePercent": 0.0, "dayChangeTWD": 0.0
            })
            continue

        sym = asset["symbol"]
        quote = quote_data.get(sym, {"price": 1.0, "prev_close": 1.0})
        
        current_price = quote["price"]
        prev_close = quote["prev_close"]
        day_change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
            
        currency = "USD" if asset["category"] in ["us_stock", "crypto"] else "TWD"
        conversion_rate = exchange_rate if currency == "USD" else 1.0
        
        total_value_twd = current_price * asset["quantity"] * conversion_rate
        value_prior_twd = prev_close * asset["quantity"] * conversion_rate
        day_change_twd = total_value_twd - value_prior_twd
        
        portfolio_assets.append({
            "id": asset_id, "name": asset["name"], "symbol": asset["symbol"], "category": asset["category"],
            "quantity": asset["quantity"], "currentPrice": current_price, "currency": currency,
            "totalValueTWD": total_value_twd, "dayChangePercent": day_change_percent, "dayChangeTWD": day_change_twd
        })
        
    return exchange_rate, portfolio_assets


@st.cache_data(ttl=600)
def fetch_historical_performance(assets_list, period="1mo"):
    """使用分離合併法，徹底解決時區衝突造成的歷史圖表崩潰"""
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    if not symbols: return []
    symbols_to_fetch = list(set(symbols + ["USDTWD=X"]))
    
    period_mapping = {"1w": ("7d", "1d"), "1mo": ("1mo", "1d"), "3mo": ("3mo", "1d"), "6mo": ("6mo", "1d"), "1y": ("1y", "1d"), "all": ("max", "1wk")}
    yf_period, yf_interval = period_mapping.get(period, ("1mo", "1d"))
    
    chart_data_frames = []
    
    for sym in symbols_to_fetch:
        try:
            h = yf.Ticker(sym).history(period=yf_period, interval=yf_interval)
            if h.empty: continue
            h.index = pd.to_datetime(h.index, utc=True).tz_convert(None).normalize()
            h = h[['Close']].rename(columns={'Close': sym})
            h = h[~h.index.duplicated(keep='last')]
            chart_data_frames.append(h)
        except: pass
        
    if not chart_data_frames: return []
    
    hist_df = pd.concat(chart_data_frames, axis=1)
    hist_df = hist_df.sort_index().ffill().bfill()
    
    dates = hist_df.index
    chart_data = []
    
    cash_value = sum(a["quantity"] for a in assets_list if a["category"] == "cash")
    
    for date in dates:
        fx_rate = 32.5
        if "USDTWD=X" in hist_df.columns:
            val = hist_df.loc[date, "USDTWD=X"]
            if not pd.isna(val): fx_rate = float(val)
            
        tw_value, us_value, crypto_value = 0.0, 0.0, 0.0
        
        for asset in assets_list:
            if asset["category"] == "cash": continue
            sym = asset["symbol"]
            quantity = asset["quantity"]
            
            if sym not in hist_df.columns: continue
            val = hist_df.loc[date, sym]
            if pd.isna(val): continue
                
            price = float(val)
            currency = "USD" if asset["category"] in ["us_stock", "crypto"] else "TWD"
            conv_rate = fx_rate if currency == "USD" else 1.0
            asset_val_twd = price * quantity * conv_rate
            
            if asset["category"] == "tw_stock": tw_value += asset_val_twd
            elif asset["category"] == "us_stock": us_value += asset_val_twd
            elif asset["category"] == "crypto": crypto_value += asset_val_twd
                
        chart_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "twStock": tw_value, "usStock": us_value, "crypto": crypto_value,
            "cash": cash_value, "total": tw_value + us_value + crypto_value + cash_value
        })
        
    return chart_data

# ----------------- Main UI Controller -----------------

if "assets" not in st.session_state: st.session_state.assets = load_assets()

# ----------------- Header & Global Actions -----------------

st.markdown("<h1 class='main-title'>Tony's <span class='highlight-title'>Asset Dashboard</span></h1>", unsafe_allow_html=True)
st.write("Track and balance multi-asset portfolios in Real-time (TW Stocks, US Stocks, Cryptos, and Cash).")

# ✨ 將側邊欄功能移至主頁面頂部的 Action Bar
action_c1, action_c2, action_c3 = st.columns([1.5, 1.5, 7])

with action_c1:
    if st.button("🔄 Refresh Rates", use_container_width=True):
        st.cache_data.clear()
        st.toast("Refreshed pricing index successfully!", icon="✅")
        st.rerun()

with action_c2:
    with st.popover("➕ Add Asset", use_container_width=True):
        st.markdown("**Add New Asset**")
        with st.form("add_asset_form", clear_on_submit=True):
            new_name = st.text_input("Asset Name", placeholder="e.g. Taiwan Semiconductor")
            new_sym = st.text_input("Symbol", placeholder="e.g. 2330.TW or AAPL")
            new_cat = st.selectbox("Category", options=list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS[x])
            new_qty = st.number_input("Holding Quantity", min_value=0.0, step=0.1, value=0.0, format="%.5f")
            
            if st.form_submit_button("Save to Portfolio", use_container_width=True):
                if not new_name or not new_sym: 
                    st.error("Please provide both a Display Name and Symbol.")
                else:
                    clean_sym = new_sym.strip().upper()
                    st.session_state.assets.append({
                        "id": f"{clean_sym}_{int(datetime.now().timestamp())}",
                        "name": new_name.strip(), "symbol": clean_sym, "category": new_cat, "quantity": float(new_qty)
                    })
                    save_assets(st.session_state.assets)
                    st.cache_data.clear()
                    st.rerun()

st.markdown("---")

with st.spinner("Fetching active markets and calculating TWD values..."):
    exchange_rate, portfolio = fetch_realtime_market_data(st.session_state.assets)

# ----------------- Dashboard Layout -----------------

total_net_worth = sum(a["totalValueTWD"] for a in portfolio)
total_day_change = sum(a["dayChangeTWD"] for a in portfolio)
prior_net_worth = total_net_worth - total_day_change
percent_change = (total_day_change / prior_net_worth * 100) if prior_net_worth > 0 else 0.0

cash_total = sum(a["totalValueTWD"] for a in portfolio if a["category"] == "cash")

m1, m2, m3 = st.columns([2, 1, 1])
with m1:
    ds = "+" if total_day_change >= 0 else ""
    st.metric("Total Net Worth", format_currency_twd(total_net_worth), f"{ds}{percent_change:.2f}% (Day: {ds}{format_currency_twd(total_day_change)})")
with m2: st.metric("Cash Liquidity", format_currency_twd(cash_total), f"{(cash_total/total_net_worth*100) if total_net_worth>0 else 0:.1f}% of portfolio", delta_color="off")
with m3: st.metric("USDTWD Exchange Rate", f"NT$ {exchange_rate:.2f}", "Live Yahoo Query")

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📈 Performance History")
    chart_p1, chart_p2 = st.columns([2, 3])
    with chart_p1: selected_period = st.segmented_control("Timeframe", ["1w", "1mo", "3mo", "6mo", "1y", "all"], format_func=lambda x: x.upper(), default="1mo", label_visibility="collapsed")
    with chart_p2: selected_class = st.segmented_control("Class", ["total", "twStock", "usStock", "crypto", "cash"], format_func=lambda x: {"total": "Total Portfolio", "twStock": "Taiwan Stocks", "usStock": "US Stocks", "crypto": "Cryptocurrency", "cash": "Cash Only"}[x], default="total", label_visibility="collapsed")
        
    hist_data = fetch_historical_performance(st.session_state.assets, period=selected_period)
    if hist_data:
        df_hist = pd.DataFrame(hist_data)
        fig_area = go.Figure()
        fig_area.add_trace(go.Scatter(x=df_hist["date"], y=df_hist[selected_class], mode="lines", fill="tozeroy", line_color={"total": "#6366f1", "twStock": "#3B82F6", "usStock": "#8B5CF6", "crypto": "#F59E0B", "cash": "#10B981"}.get(selected_class, "#6366f1"), name=selected_class, hovertemplate="<b>Date</b>: %{x}<br><b>Value (TWD)</b>: NT$ %{y:,.0f}<extra></extra>"))
        fig_area.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=280, paper_bgcolor="#0B0E14", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(showgrid=False, tickfont=dict(color="#A0AEC0", size=10)), yaxis=dict(showgrid=True, gridcolor="#1E293B", tickfont=dict(color="#A0AEC0", size=10), tickprefix="NT$ "))
        st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
    else: st.info("Loading performance timeline...")

with col_right:
    st.subheader("🍩 Current Asset Allocation")
    df_alloc = pd.DataFrame([{"Category": CATEGORY_LABELS[k], "Value": v, "Color": CATEGORY_COLORS[k]} for k, v in {cat: sum(a["totalValueTWD"] for a in portfolio if a["category"] == cat) for cat in CATEGORY_LABELS.keys()}.items() if v > 0])
    if not df_alloc.empty:
        fig_pie = px.pie(df_alloc, values="Value", names="Category", hole=0.55, color="Category", color_discrete_map={CATEGORY_LABELS[k]: CATEGORY_COLORS[k] for k in CATEGORY_LABELS.keys()})
        fig_pie.update_traces(textinfo="percent+label", textposition="outside", hovertemplate="<b>%{label}</b><br>Value: NT$ %{value:,.0f}<br>Percent: %{percent}<extra></extra>")
        fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=280, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
    else: st.info("No asset holdings.")

# ----------------- Grouped Asset Interactive Table -----------------
st.markdown("---")
st.subheader("📋 Your Asset Ledger")

for cat_key in ["tw_stock", "us_stock", "crypto", "cash"]:
    cat_assets = sorted([a for a in portfolio if a["category"] == cat_key], key=lambda x: x["totalValueTWD"], reverse=True)
    if not cat_assets: continue
    
    cat_total_val, cat_total_change = sum(a["totalValueTWD"] for a in cat_assets), sum(a["dayChangeTWD"] for a in cat_assets)
    
    ch_1, ch_2 = st.columns([3, 1])
    with ch_1: 
        st.markdown(f"#### 🏷️ {CATEGORY_LABELS[cat_key]}")
    with ch_2: 
        st.markdown(f"<div style='text-align:right;'><strong style='font-size:1.1rem;'>{format_currency_twd(cat_total_val)}</strong><br><span style='font-size:0.8rem; font-family: monospace; color:{'#34D399' if cat_total_change >=0 else '#F87171'}'>{'+' if cat_total_change >=0 else ''}{format_currency_twd(cat_total_change)}</span></div>", unsafe_allow_html=True)
    
    hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2.5, 1.5, 2, 2.5, 2, 1])
    hc1.markdown("<div class='table-header'>Asset</div>", unsafe_allow_html=True)
    hc2.markdown("<div class='table-header'>Holdings</div>", unsafe_allow_html=True)
    hc3.markdown("<div class='table-header'>Price</div>", unsafe_allow_html=True)
    hc4.markdown("<div class='table-header'>Day Change</div>", unsafe_allow_html=True)
    hc5.markdown("<div class='table-header'>Total Value</div>", unsafe_allow_html=True)
    hc6.markdown("<div class='table-header'>Action</div>", unsafe_allow_html=True)
    st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
    
    for a in cat_assets:
        is_pos = a["dayChangePercent"] >= 0
        if cat_key == "cash": change_str, price_str = "-", "-"
        else:
            color = "#34D399" if is_pos else "#F87171"
            change_str = f"<span style='color:{color}; font-family:monospace;'>{'+' if is_pos else ''}{a['dayChangePercent']:.2f}% ({'+' if is_pos else '-'}{format_currency_twd(abs(a['dayChangeTWD']))})</span>"
            price_str = format_currency_foreign(a["currentPrice"], a["currency"])
            
        c1, c2, c3, c4, c5, c6 = st.columns([2.5, 1.5, 2, 2.5, 2, 1])
        c1.markdown(f"<b>{a['symbol'].split('.')[0]}</b><br><span style='color:#64748B;font-size:0.75rem;'>{a['name']}</span>", unsafe_allow_html=True)
        c2.markdown(f"{a['quantity']:,.5f}".rstrip('0').rstrip('.'))
        c3.markdown(price_str)
        c4.markdown(change_str, unsafe_allow_html=True)
        c5.markdown(f"<b>{format_currency_twd(a['totalValueTWD'])}</b>", unsafe_allow_html=True)
        
        with c6:
            with st.popover("⚙️"):
                st.markdown(f"**Adjust {a['symbol'].split('.')[0]}**")
                new_qty = st.number_input("Holdings", min_value=0.0, value=float(a['quantity']), format="%.5f", key=f"qty_{a['id']}")
                
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("💾 Save", key=f"save_{a['id']}", use_container_width=True):
                        for idx, s_asset in enumerate(st.session_state.assets):
                            if s_asset.get("id", s_asset.get("symbol")) == a.get("id", a.get("symbol")):
                                st.session_state.assets[idx]["quantity"] = new_qty
                                save_assets(st.session_state.assets)
                                st.cache_data.clear()
                                st.rerun()
                with btn_col2:
                    if cat_key != "cash": 
                        if st.button("🗑️ Del", key=f"del_{a['id']}", use_container_width=True, type="primary"):
                            st.session_state.assets = [s_asset for s_asset in st.session_state.assets if s_asset.get("id", s_asset.get("symbol")) != a.get("id", a.get("symbol"))]
                            save_assets(st.session_state.assets)
                            st.cache_data.clear()
                            st.rerun()
                            
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
        
    st.write("") 

# ----------------- Footer -----------------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748B; font-size: 0.75rem; font-family: monospace;'>"
    f"Tony's Asset Dashboard • Live Sync via Yahoo Finance • Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    "</div>", 
    unsafe_allow_html=True
)
