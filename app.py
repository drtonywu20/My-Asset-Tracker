import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests # ✨ 新增 requests 套件以支援即時搜尋
from datetime import datetime, timedelta

# ✨ 嘗試匯入 Firebase (防呆：若伺服器還沒安裝也不會崩潰)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Set page configuration
st.set_page_config(
    page_title="Tony's Asset Dashboard",
    page_icon="🍄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling to match the original React dark cosmic aesthetic
st.markdown("""
<style>
    /* 1. 整體網頁背景：極致純黑，產生最強烈的對比 */
    .stApp { background-color: #000000 !important; }
    header[data-testid="stHeader"] { background-color: #000000 !important; }
    
    /* 2. 標題與指標字體 */
    .main-title { font-family: 'Inter', sans-serif; font-weight: 700; color: #E2E9EF; }
    .highlight-title { color: #E2E9F4; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 2rem !important; }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.1em; }
    
    /* 3. ✨ 核心修正：統一的深藍色卡片設計 (確保顏色明顯跳出) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #121F33 !important; /* 明顯的高質感深海藍 */
        border: 1px solid #2A3B57 !important; /* 柔和的藍色邊框 */
        border-radius: 16px !important;
        padding: 1.5rem !important;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6) !important; /* 強烈的卡片浮出感 */
    }
    
    /* ✨ 強制清除容器內部所有的背景覆蓋，確保深藍色 100% 顯色 */
    div[data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"] > div > div {
        background-color: transparent !important;
    }
    
    /* 其他次要元素背景 (如彈出選單) */
    .css-1r6g72q, .stCollapse { 
        border: 1px solid #2A3B57 !important; 
        background-color: #121F33 !important; 
        border-radius: 12px; 
        padding: 1rem; 
    }
    
    /* 4. 表格內的線條與表頭 */
    .row-divider { border-bottom: 1px solid #2A3B57; margin-top: 0.5rem; margin-bottom: 0.5rem; }
    .table-header { color: #8BA1C0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;}
</style>
""", unsafe_allow_html=True)

# Path to local database
DB_FILE = "assets.json"

DEFAULT_ASSETS = [
    {"id": "00631L_TW", "name": "元大台灣50正2", "symbol": "00631L.TW", "category": "tw_stock", "quantity": 131000.0, "average_cost": 30.0, "account": "Default"},
    {"id": "00981A_TW", "name": "00981A", "symbol": "00981A.TW", "category": "tw_stock", "quantity": 18000.0, "average_cost": 25.0, "account": "Default"},
    {"id": "BRKB_US", "name": "Berkshire Hathaway Inc.", "symbol": "BRK-B", "category": "us_stock", "quantity": 65.0, "average_cost": 400.0, "account": "IB"},
    {"id": "TSLA_IB", "name": "Tesla, Inc.", "symbol": "TSLA", "category": "us_stock", "quantity": 100.0, "average_cost": 200.0, "account": "IB"},
    {"id": "TSLA_CATHAY", "name": "Tesla, Inc.", "symbol": "TSLA", "category": "us_stock", "quantity": 55.4, "average_cost": 190.0, "account": "Cathay"},
    {"id": "GLDM_US", "name": "SPDR Gold MiniShares", "symbol": "GLDM", "category": "us_stock", "quantity": 189.0, "average_cost": 70.0, "account": "Cathay"},
    {"id": "IWY_US", "name": "iShares Russell Top 200 Growth ETF", "symbol": "IWY", "category": "us_stock", "quantity": 66.0, "average_cost": 250.0, "account": "IB"},
    {"id": "MSTR_US", "name": "MicroStrategy Inc.", "symbol": "MSTR", "category": "us_stock", "quantity": 13.0, "average_cost": 100.0, "account": "IB"},
    {"id": "NVDA_US", "name": "NVIDIA Corporation", "symbol": "NVDA", "category": "us_stock", "quantity": 110.0, "average_cost": 100.0, "account": "Cathay"},
    {"id": "BTC_CRYPTO", "name": "Bitcoin", "symbol": "BTC-USD", "category": "crypto", "quantity": 0.09869, "average_cost": 60000.0, "account": "Default"},
    {"id": "ETH_CRYPTO", "name": "Ethereum", "symbol": "ETH-USD", "category": "crypto", "quantity": 0.90, "average_cost": 2500.0, "account": "Default"},
    {"id": "TWD_CASH", "name": "Cash (TWD)", "symbol": "TWD", "category": "cash", "quantity": 1000000.0, "average_cost": 1.0, "account": "Default"}
]

CATEGORY_LABELS = {"tw_stock": "Taiwan Stocks", "us_stock": "US Stocks", "crypto": "Cryptocurrency", "cash": "Cash & Equivalents"}
CATEGORY_COLORS = {"tw_stock": "#3B82F6", "us_stock": "#8B5CF6", "crypto": "#F59E0B", "cash": "#10B981"}

ACCOUNT_LABELS = {
    "Default": "國泰證券戶",
    "Cathay": "國泰複委託 (Cathay)",
    "IB": "IB海外券商 (IB)"
}

# ----------------- Firebase Initialization -----------------

@st.cache_resource
def get_db():
    if FIREBASE_AVAILABLE and "firebase" in st.secrets:
        try:
            if not firebase_admin._apps:
                cred_dict = dict(st.secrets["firebase"])
                if "private_key" in cred_dict:
                    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception as e:
            return None
    return None

# ----------------- Helper Functions (Load / Save) -----------------

def load_assets():
    db = get_db()
    if db is not None:
        try:
            doc = db.collection("portfolios").document("tony_portfolio").get()
            if doc.exists:
                return doc.to_dict().get("assets", DEFAULT_ASSETS)
        except Exception:
            pass 
            
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return DEFAULT_ASSETS
    else:
        return DEFAULT_ASSETS

def save_assets(assets_list):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(assets_list, f, ensure_ascii=False, indent=2)
    db = get_db()
    if db is not None:
        try:
            db.collection("portfolios").document("tony_portfolio").set({"assets": assets_list, "last_updated": datetime.now().isoformat()})
        except Exception as e:
            st.toast("Warning: Could not sync to cloud database.", icon="⚠️")

def format_currency_twd(val): return f"NT$ {val:,.0f}"

def format_currency_foreign(val, currency):
    if currency == "TWD": return f"NT$ {val:,.2f}"
    elif currency == "USD": return f"${val:,.2f}"
    return f"{currency} {val:,.4f}"

# ----------------- Core Data Fetching -----------------

@st.cache_data(ttl=300)
def fetch_realtime_market_data(assets_list):
    quote_data = {}
    exchange_rate = 32.5
    
    try:
        # 延長抓取天數為 1mo，徹底解決 yfinance 的時區截斷 bug
        fx_hist = yf.Ticker("USDTWD=X").history(period="1mo", interval="1d")
        if not fx_hist.empty:
            exchange_rate = float(fx_hist['Close'].dropna().iloc[-1])
    except: pass

    for asset in assets_list:
        if asset["category"] == "cash": continue
        sym = asset["symbol"]
        if sym in quote_data: continue
            
        try:
            ticker = yf.Ticker(sym)
            
            # ✨ 核心修正 1：優先使用 fast_info 獲取最即時且不受 K 線假數據干擾的報價
            try:
                fi = ticker.fast_info
                # 確保數值存在
                if fi.last_price is not None and fi.previous_close is not None:
                    # 針對假日的防呆，last_price 在休市或收盤後就是準確的最後收盤價
                    quote_data[sym] = {
                        "price": float(fi.last_price), 
                        "prev_close": float(fi.previous_close)
                    }
                    continue # 成功抓到就跳過歷史 K 線的運算
            except Exception:
                pass
            
            # ✨ 核心修正 2：如果 fast_info 失敗，退回使用強化版的 K 線清洗演算法
            hist = ticker.history(period="1mo", interval="1d")
            hist = hist.dropna(subset=['Close'])
            if hist.empty: continue
            
            hist.index = pd.to_datetime(hist.index, utc=True).tz_convert(None).normalize()
            hist = hist[~hist.index.duplicated(keep='last')].sort_index()
            
            if asset["category"] != "crypto":
                # 剔除六日的假數據 (針對臺股與美股週末沒開盤的情境)
                hist = hist[hist.index.dayofweek < 5]
                if 'Volume' in hist.columns:
                    valid_vols = hist['Volume'] > 0
                    if len(valid_vols) > 0:
                        valid_vols.iloc[-1] = True # 保留最後一天防剛開盤無交易量
                        hist = hist[valid_vols]
                    
            price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
            quote_data[sym] = {"price": price, "prev_close": prev_close}
        except Exception:
            pass
            
    portfolio_assets = []
    for asset in assets_list:
        asset_id = asset.get("id", asset["symbol"])
        avg_cost = asset.get("average_cost", 0.0) 
        account = asset.get("account", "Default")
        
        if asset["category"] == "cash":
            portfolio_assets.append({
                "id": asset_id, "name": asset["name"], "symbol": asset["symbol"], "category": asset["category"],
                "account": account, "quantity": asset["quantity"], "currentPrice": 1.0, "currency": "TWD",
                "average_cost": 1.0, "totalCostTWD": asset["quantity"],
                "totalValueTWD": asset["quantity"], "dayChangePercent": 0.0, "dayChangeTWD": 0.0,
                "unrealizedPnlTWD": 0.0, "unrealizedPnlPercent": 0.0
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
        
        total_cost_twd = avg_cost * asset["quantity"] * conversion_rate
        unrealized_pnl_twd = total_value_twd - total_cost_twd
        unrealized_pnl_percent = ((current_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0.0
        
        portfolio_assets.append({
            "id": asset_id, "name": asset["name"], "symbol": asset["symbol"], "category": asset["category"],
            "account": account, "quantity": asset["quantity"], "currentPrice": current_price, "currency": currency,
            "average_cost": avg_cost, "totalCostTWD": total_cost_twd, 
            "unrealizedPnlTWD": unrealized_pnl_twd, "unrealizedPnlPercent": unrealized_pnl_percent,
            "totalValueTWD": total_value_twd, "dayChangePercent": day_change_percent, "dayChangeTWD": day_change_twd
        })
        
    return exchange_rate, portfolio_assets


@st.cache_data(ttl=600)
def fetch_historical_performance(assets_list, period="1mo"):
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    if not symbols: return []
    symbols_to_fetch = list(set(symbols + ["USDTWD=X"]))
    
    period_mapping = {"1w": ("7d", "1d"), "1mo": ("1mo", "1d"), "3mo": ("3mo", "1d"), "6mo": ("6mo", "1d"), "1y": ("1y", "1d")}
    yf_period, yf_interval = period_mapping.get(period, ("1mo", "1d"))
    
    chart_data_frames = []
    for sym in symbols_to_fetch:
        try:
            h = yf.Ticker(sym).history(period=yf_period, interval=yf_interval)
            if h.empty: continue
            h.index = pd.to_datetime(h.index, utc=True).tz_convert(None).normalize()
            h = h[['Close']].rename(columns={'Close': sym})
            h = h[~h.index.duplicated(keep='last')].sort_index()
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

# --- Sidebar Connection Status ---
with st.sidebar:
    st.markdown("### System Status")
    if get_db():
        st.success("🟢 Firebase Cloud Sync: Active")
        st.caption("Your data is safely backed up to Google Cloud. Hibernation will not erase your settings.")
    else:
        st.warning("🟡 Local Storage Mode")
        st.caption("Cloud database not connected yet. Data will reset if Streamlit hibernates.")

# ----------------- Header & Global Actions -----------------

st.markdown("<h1 class='main-title'>Tony's <span class='highlight-title'>Asset Dashboard</span></h1>", unsafe_allow_html=True)
st.write("Track and balance multi-asset portfolios in Real-time (TW Stocks, US Stocks, Cryptos, and Cash).")

action_c1, action_c2, action_c3 = st.columns([1.5, 1.5, 7])

with action_c1:
    if st.button("🔄 Refresh Rates", use_container_width=True):
        st.cache_data.clear()
        st.toast("Refreshed pricing index successfully!", icon="✅")
        st.rerun()

with action_c2:
    with st.popover("➕ Add Asset", use_container_width=True):
        st.markdown("**Add New Asset (新增資產)**")
        
        search_kw = st.text_input("🔍 1. Search (輸入代碼或關鍵字後按 Enter)", placeholder="e.g. 2330 或 AAPL")
        
        options_dict = {}
        if search_kw:
            try:
                url = f"https://query2.finance.yahoo.com/v1/finance/search?q={search_kw}"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                r = requests.get(url, headers=headers, timeout=5)
                data = r.json()
                for q in data.get('quotes', []):
                    if 'symbol' in q and q.get('quoteType') in ['EQUITY', 'ETF', 'MUTUALFUND', 'CRYPTOCURRENCY', 'CURRENCY']:
                        sym = q['symbol']
                        name = q.get('shortname', q.get('longname', 'Unknown'))
                        exch = q.get('exchDisp', '')
                        options_dict[sym] = f"{sym} | {name} ({exch})"
            except Exception:
                pass
        
        with st.form("add_asset_form", clear_on_submit=True):
            if options_dict:
                new_sym = st.selectbox("🎯 2. Select Asset (選擇精確標的)", list(options_dict.keys()), format_func=lambda x: options_dict[x])
            else:
                new_sym = st.text_input("🎯 2. Symbol (找不到搜尋結果時可手動輸入)", value=search_kw.upper() if search_kw else "")

            new_cat = st.selectbox("Category (資產分類)", options=list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS[x])
            new_acc = st.selectbox("Broker / Account (券商帳戶)", options=list(ACCOUNT_LABELS.keys()), format_func=lambda x: ACCOUNT_LABELS[x])
            new_qty = st.number_input("Holding Quantity (持有數量)", min_value=0.0, step=0.1, value=0.0, format="%.5f")
            new_cost = st.number_input("Average Cost (平均成本)", min_value=0.0, step=0.1, value=0.0, format="%.5f")
            
            if st.form_submit_button("Save to Portfolio", use_container_width=True):
                if not new_sym: 
                    st.error("請輸入或選擇股票代號 (Symbol)")
                else:
                    clean_sym = new_sym.strip().upper()
                    
                    fetched_name = clean_sym
                    if clean_sym in options_dict:
                        parts = options_dict[clean_sym].split(' | ')
                        if len(parts) > 1:
                            fetched_name = parts[1].rsplit(' (', 1)[0]
                    else:
                        try:
                            info = yf.Ticker(clean_sym).info
                            fetched_name = info.get('shortName', info.get('longName', clean_sym))
                        except Exception:
                            pass 
                            
                    st.session_state.assets.append({
                        "id": f"{clean_sym}_{int(datetime.now().timestamp())}",
                        "name": fetched_name, 
                        "symbol": clean_sym, 
                        "category": new_cat, 
                        "account": new_acc, 
                        "quantity": float(new_qty), 
                        "average_cost": float(new_cost)
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

total_unrealized_pnl = sum(a["unrealizedPnlTWD"] for a in portfolio if a["category"] != "cash")
total_cost_basis = sum(a["totalCostTWD"] for a in portfolio if a["category"] != "cash")
total_unrealized_percent = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

cash_total = sum(a["totalValueTWD"] for a in portfolio if a["category"] == "cash")

m1, m2, m3, m4 = st.columns([1.5, 1.5, 1, 1])
with m1:
    ds = "+" if total_day_change >= 0 else ""
    st.metric("Total Net Worth", format_currency_twd(total_net_worth), f"{ds}{percent_change:.2f}% (Day: {ds}{format_currency_twd(total_day_change)})")
with m2:
    us = "+" if total_unrealized_pnl >= 0 else ""
    st.metric("Total Unrealized P/L", f"{us}{format_currency_twd(total_unrealized_pnl)}", f"{us}{total_unrealized_percent:.2f}% (All-Time)", delta_color="normal")
with m3: 
    st.metric("Cash Liquidity", format_currency_twd(cash_total), f"{(cash_total/total_net_worth*100) if total_net_worth>0 else 0:.1f}% of portfolio", delta_color="off")
with m4: 
    st.metric("USDTWD Rate", f"NT$ {exchange_rate:.2f}", "Live Yahoo Query")

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📈 Performance History")
    chart_p1, chart_p2 = st.columns([2, 3])
    with chart_p1: selected_period = st.segmented_control("Timeframe", ["1w", "1mo", "3mo", "6mo", "1y"], format_func=lambda x: x.upper(), default="1mo", label_visibility="collapsed")
    with chart_p2: selected_class = st.segmented_control("Class", ["total", "twStock", "usStock", "crypto", "cash"], format_func=lambda x: {"total": "Total Portfolio", "twStock": "Taiwan Stocks", "usStock": "US Stocks", "crypto": "Cryptocurrency", "cash": "Cash Only"}[x], default="total", label_visibility="collapsed")
        
    hist_data = fetch_historical_performance(st.session_state.assets, period=selected_period)
    if hist_data:
        df_hist = pd.DataFrame(hist_data)
        fig_area = go.Figure()
        
        fig_area.add_trace(go.Scatter(
            x=df_hist["date"], 
            y=df_hist[selected_class], 
            mode="lines", 
            line=dict(color={"total": "#6366f1", "twStock": "#3B82F6", "usStock": "#8B5CF6", "crypto": "#F59E0B", "cash": "#10B981"}.get(selected_class, "#6366f1"), width=3), 
            name=selected_class, 
            hovertemplate="<b>Date</b>: %{x}<br><b>Value (TWD)</b>: NT$ %{y:,.0f}<extra></extra>"
        ))
        
        fig_area.update_layout(
            margin=dict(l=20, r=20, t=10, b=10), 
            height=280, 
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)", 
            xaxis=dict(showgrid=False, tickfont=dict(color="#A0AEC0", size=10)), 
            yaxis=dict(showgrid=True, gridcolor="#2A3B57", tickfont=dict(color="#A0AEC0", size=10), tickprefix="NT$ ")
        )
        st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
    else: st.info("Loading performance timeline...")

with col_right:
    st.subheader("🍩 Current Asset Allocation")
    df_alloc = pd.DataFrame([{"Category": CATEGORY_LABELS[k], "Value": v, "Color": CATEGORY_COLORS[k]} for k, v in {cat: sum(a["totalValueTWD"] for a in portfolio if a["category"] == cat) for cat in CATEGORY_LABELS.keys()}.items() if v > 0])
    if not df_alloc.empty:
        fig_pie = px.pie(df_alloc, values="Value", names="Category", hole=0.55, color="Category", color_discrete_map={CATEGORY_LABELS[k]: CATEGORY_COLORS[k] for k in CATEGORY_LABELS.keys()})
        fig_pie.update_traces(textinfo="percent+label", textposition="outside", hovertemplate="<b>%{label}</b><br>Value: NT$ %{value:,.0f}<br>Percent: %{percent}<extra></extra>")
        
        fig_pie.update_layout(margin=dict(l=60, r=60, t=10, b=10), height=240, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
    else: st.info("No asset holdings.")

# ----------------- Grouped Asset Interactive Table -----------------
st.markdown("---")
st.subheader("📋 Your Asset Ledger")

cols_ratio = [2, 1.2, 1.2, 1.2, 2.2, 2.2, 1.4, 0.8]

for cat_key in ["tw_stock", "us_stock", "crypto", "cash"]:
    raw_cat_assets = [a for a in portfolio if a["category"] == cat_key]
    if not raw_cat_assets: continue
    
    with st.container(border=True):
        
        ch_1, ch_2 = st.columns([3, 1])
        with ch_1: 
            st.markdown(f"#### <span style='color:{CATEGORY_COLORS[cat_key]};'>●</span> {CATEGORY_LABELS[cat_key]}", unsafe_allow_html=True)
            if cat_key == "us_stock":
                us_broker_view = st.segmented_control(
                    "🇺🇸 US Stocks Filter", 
                    ["Merged", "Cathay", "IB"], 
                    format_func=lambda x: {"Merged": "合併顯示 (All)", "Cathay": "國泰複委託", "IB": "IB海外券商"}[x],
                    default="Merged",
                    label_visibility="collapsed"
                )
                st.write("") 
                
                if us_broker_view == "Cathay":
                    raw_cat_assets = [a for a in raw_cat_assets if a.get("account") == "Cathay"]
                elif us_broker_view == "IB":
                    raw_cat_assets = [a for a in raw_cat_assets if a.get("account") == "IB"]
        
        grouped_assets = {}
        for a in raw_cat_assets:
            sym = a["symbol"]
            if sym not in grouped_assets:
                grouped_assets[sym] = {"symbol": sym, "name": a["name"], "category": a["category"], "currency": a["currency"], "currentPrice": a["currentPrice"], "dayChangePercent": a["dayChangePercent"], "underlying": []}
            grouped_assets[sym]["underlying"].append(a)
            
        cat_assets = []
        for sym, grp in grouped_assets.items():
            tot_qty = sum(u["quantity"] for u in grp["underlying"])
            if tot_qty <= 0 and grp["category"] != "cash": continue 
                
            tot_cost_twd = sum(u["totalCostTWD"] for u in grp["underlying"])
            tot_val_twd = sum(u["totalValueTWD"] for u in grp["underlying"])
            tot_day_chg_twd = sum(u["dayChangeTWD"] for u in grp["underlying"])
            tot_unrealized_twd = sum(u["unrealizedPnlTWD"] for u in grp["underlying"])
            
            grp["quantity"] = tot_qty
            if tot_qty > 0:
                tot_cost_usd = sum(u["average_cost"] * u["quantity"] for u in grp["underlying"])
                grp["average_cost"] = tot_cost_usd / tot_qty
            else:
                grp["average_cost"] = sum(u["average_cost"] for u in grp["underlying"]) / len(grp["underlying"])
                
            grp["totalValueTWD"] = tot_val_twd
            grp["dayChangeTWD"] = tot_day_chg_twd
            grp["unrealizedPnlTWD"] = tot_unrealized_twd
            grp["unrealizedPnlPercent"] = (tot_unrealized_twd / tot_cost_twd * 100) if tot_cost_twd > 0 else 0.0
            
            cat_assets.append(grp)
            
        cat_assets = sorted(cat_assets, key=lambda x: x["totalValueTWD"], reverse=True)
        
        if not cat_assets:
            st.info("此帳戶檢視模式下目前無持有資產。")
            continue
            
        cat_total_val = sum(a["totalValueTWD"] for a in cat_assets)
        cat_total_change = sum(a["dayChangeTWD"] for a in cat_assets)

        with ch_2: 
            abs_change = abs(cat_total_change)
            sign = "+" if cat_total_change >= 0 else "-"
            color = "#34D399" if cat_total_change >= 0 else "#F87171"
            
            if cat_key == "us_stock":
                val_usd = cat_total_val / exchange_rate
                abs_change_usd = abs(cat_total_change / exchange_rate)
                st.markdown(f"""
                <div style='text-align:right;'>
                    <strong style='font-size:1.1rem;'>{format_currency_twd(cat_total_val)}</strong>
                    <span style='font-size:0.85rem; color:#94A3B8; margin-left:4px;'>(US$ {val_usd:,.2f})</span><br>
                    <span style='font-size:0.8rem; font-family: monospace; color:{color}'>
                        日盈虧: {sign}{format_currency_twd(abs_change)} 
                        <span style='margin-left:2px;'>(US$ {abs_change_usd:,.2f})</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='text-align:right;'>
                    <strong style='font-size:1.1rem;'>{format_currency_twd(cat_total_val)}</strong><br>
                    <span style='font-size:0.8rem; font-family: monospace; color:{color}'>
                        日盈虧: {sign}{format_currency_twd(abs_change)}
                    </span>
                </div>
                """, unsafe_allow_html=True)
        
        hc1, hc2, hc3, hc4, hc5, hc6, hc7, hc8 = st.columns(cols_ratio)
        hc1.markdown("<div class='table-header'>Asset</div>", unsafe_allow_html=True)
        hc2.markdown("<div class='table-header'>Holdings</div>", unsafe_allow_html=True)
        hc3.markdown("<div class='table-header'>Avg Cost</div>", unsafe_allow_html=True)
        hc4.markdown("<div class='table-header'>Price</div>", unsafe_allow_html=True)
        hc5.markdown("<div class='table-header'>Day Change</div>", unsafe_allow_html=True)
        hc6.markdown("<div class='table-header'>Total Return</div>", unsafe_allow_html=True)
        hc7.markdown("<div class='table-header'>Total Value</div>", unsafe_allow_html=True)
        hc8.markdown("<div class='table-header'>Act</div>", unsafe_allow_html=True)
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
        
        for a in cat_assets:
            is_pos = a["dayChangePercent"] >= 0
            is_return_pos = a["unrealizedPnlPercent"] >= 0
            
            if cat_key == "cash": 
                change_str, price_str, cost_str, return_str = "-", "-", "-", "-"
            else:
                color_day = "#34D399" if is_pos else "#F87171"
                color_return = "#34D399" if is_return_pos else "#F87171"
                
                change_str = f"<span style='color:{color_day}; font-family:monospace;'>{'+' if is_pos else ''}{a['dayChangePercent']:.2f}% ({'+' if is_pos else '-'}{format_currency_twd(abs(a['dayChangeTWD']))})</span>"
                return_str = f"<span style='color:{color_return}; font-family:monospace;'>{'+' if is_return_pos else ''}{a['unrealizedPnlPercent']:.2f}% ({'+' if is_return_pos else '-'}{format_currency_twd(abs(a['unrealizedPnlTWD']))})</span>"
                price_str = format_currency_foreign(a["currentPrice"], a["currency"])
                cost_str = format_currency_foreign(a["average_cost"], a["currency"])
                
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(cols_ratio)
            
            multi_tag = f" <span style='font-size:0.65rem; background:#1E293B; padding:2px 4px; border-radius:4px;'>{len(a['underlying'])} Accs</span>" if len(a['underlying']) > 1 else ""
            c1.markdown(f"<b>{a['symbol'].split('.')[0]}</b>{multi_tag}<br><span style='color:#8BA1C0;font-size:0.75rem;'>{a['name']}</span>", unsafe_allow_html=True)
            c2.markdown(f"{a['quantity']:,.5f}".rstrip('0').rstrip('.'))
            c3.markdown(cost_str)
            c4.markdown(price_str)
            c5.markdown(change_str, unsafe_allow_html=True)
            c6.markdown(return_str, unsafe_allow_html=True)
            c7.markdown(f"<b>{format_currency_twd(a['totalValueTWD'])}</b>", unsafe_allow_html=True)
            
            with c8:
                with st.popover("⚙️"):
                    st.markdown(f"**Adjust {a['symbol'].split('.')[0]}**")
                    for i, u in enumerate(a["underlying"]):
                        acc_label = ACCOUNT_LABELS.get(u.get("account", "Default"), "國泰證券戶")
                        st.caption(f"Broker: {acc_label}")
                        new_qty = st.number_input(f"Holdings", min_value=0.0, value=float(u['quantity']), format="%.5f", key=f"qty_{u['id']}")
                        new_cost = st.number_input(f"Average Cost", min_value=0.0, value=float(u['average_cost']), format="%.5f", key=f"cost_{u['id']}")
                        
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("💾 Save", key=f"save_{u['id']}", use_container_width=True):
                                for idx, s_asset in enumerate(st.session_state.assets):
                                    if s_asset.get("id", s_asset.get("symbol")) == u["id"]:
                                        st.session_state.assets[idx]["quantity"] = new_qty
                                        st.session_state.assets[idx]["average_cost"] = new_cost
                                        save_assets(st.session_state.assets)
                                        st.cache_data.clear()
                                        st.rerun()
                        with btn_col2:
                            if cat_key != "cash": 
                                if st.button("🗑️ Del", key=f"del_{u['id']}", use_container_width=True, type="primary"):
                                    st.session_state.assets = [s_asset for s_asset in st.session_state.assets if s_asset.get("id", s_asset.get("symbol")) != u["id"]]
                                    save_assets(st.session_state.assets)
                                    st.cache_data.clear()
                                    st.rerun()
                        if i < len(a["underlying"]) - 1:
                            st.divider()
                                
            st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

# ----------------- Footer -----------------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748B; font-size: 0.75rem; font-family: monospace;'>"
    f"Tony's Asset Dashboard • Live Sync via Yahoo Finance & Firebase • Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    "</div>", 
    unsafe_allow_html=True
)
