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
    initial_sidebar_state="expanded"
)

# Custom Styling to match the original React dark cosmic aesthetic
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp {
        background-color: #0B0E14;
        color: #F1F5F9;
    }
    header[data-testid="stHeader"] {
        background-color: #0B0E14;
    }
    .main-title {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #E2E9EF;
    }
    .highlight-title {
        color: #E2E9F4;
        font-weight: bold;
    }
    /* Metric Cards styling */
    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        font-size: 2rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #64748B !important;
        text-transform: uppercase;
        font-size: 0.75rem !important;
        letter-spacing: 0.1em;
    }
    /* Custom container borders */
    .css-1r6g72q, .stCollapse {
        border: 1px solid #1E293B !important;
        background-color: #0F172A !important;
        border-radius: 12px;
        padding: 1rem;
    }
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

CATEGORY_LABELS = {
    "tw_stock": "Taiwan Stocks",
    "us_stock": "US Stocks",
    "crypto": "Cryptocurrency",
    "cash": "Cash & Equivalents",
}

CATEGORY_COLORS = {
    "tw_stock": "#3B82F6", # blue
    "us_stock": "#8B5CF6", # purple
    "crypto": "#F59E0B",   # amber/yellow
    "cash": "#10B981"      # green
}

# ----------------- Helper Functions -----------------

def load_assets():
    """Loads assets list from JSON file or initializes with default values."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_ASSETS
    else:
        save_assets(DEFAULT_ASSETS)
        return DEFAULT_ASSETS

def save_assets(assets_list):
    """Saves assets list to JSON file."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(assets_list, f, ensure_ascii=False, indent=2)

def format_currency_twd(val):
    return f"NT$ {val:,.0f}"

def format_currency_foreign(val, currency):
    if currency == "TWD":
        return format_currency_twd(val)
    elif currency == "USD":
        return f"${val:,.2f}"
    return f"{currency} {val:,.4f}"

# 5-minute cache to keep API requests optimal, with key for resetting
@st.cache_data(ttl=300)
def fetch_realtime_market_data(assets_list):
    """Fetches quotes and USDTWD rate from Yahoo Finance."""
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    # We append the exchange rate ticket
    symbols_to_fetch = list(set(symbols + ["USDTWD=X"]))
    
    quote_data = {}
    exchange_rate = 32.5
    
    try:
        tickers = yf.Tickers(" ".join(symbols_to_fetch))
        for sym in symbols_to_fetch:
            try:
                # Use fast_info or info or history for robustness
                t = tickers.tickers[sym]
                # Try getting regular Market Price
                price = t.fast_info.get('last_price', None)
                prev_close = t.fast_info.get('previous_close', None)
                
                # Fetch basic info fallback
                if price is None:
                    # fetch 1d history to get last close
                    h = t.history(period="2d")
                    if not h.empty:
                        price = h['Close'].iloc[-1]
                        prev_close = h['Close'].iloc[-2] if len(h) > 1 else price
                
                if price is not None:
                    quote_data[sym] = {
                        "price": price,
                        "prev_close": prev_close or price
                    }
            except Exception as e:
                # Fallback standard
                pass
    except Exception as general_err:
        st.warning(f"Unable to load full realtime quotes. Using simulated fallback exchange rates.")
        
    # Extracted Exchange Rate
    if "USDTWD=X" in quote_data:
        exchange_rate = quote_data["USDTWD=X"]["price"]
        
    portfolio_assets = []
    
    for asset in assets_list:
        asset_id = asset.get("id", asset["symbol"]) # backward compatible
        if asset["category"] == "cash":
            portfolio_assets.append({
                "id": asset_id,
                "name": asset["name"],
                "symbol": asset["symbol"],
                "category": asset["category"],
                "quantity": asset["quantity"],
                "currentPrice": 1.0,
                "currency": "TWD",
                "totalValueTWD": asset["quantity"],
                "dayChangePercent": 0.0,
                "dayChangeTWD": 0.0
            })
            continue

        sym = asset["symbol"]
        quote = quote_data.get(sym, {"price": 1.0, "prev_close": 1.0})
        
        current_price = quote["price"]
        prev_close = quote["prev_close"]
        
        # Calculate day change %
        if prev_close > 0:
            day_change_percent = ((current_price - prev_close) / prev_close) * 100
        else:
            day_change_percent = 0.0
            
        currency = "USD"
        if asset["category"] == "tw_stock":
            currency = "TWD"
            
        conversion_rate = exchange_rate if currency == "USD" else 1.0
        
        total_value_twd = current_price * asset["quantity"] * conversion_rate
        value_prior_twd = prev_close * asset["quantity"] * conversion_rate
        day_change_twd = total_value_twd - value_prior_twd
        
        portfolio_assets.append({
            "id": asset_id,
            "name": asset["name"],
            "symbol": asset["symbol"],
            "category": asset["category"],
            "quantity": asset["quantity"],
            "currentPrice": current_price,
            "currency": currency,
            "totalValueTWD": total_value_twd,
            "dayChangePercent": day_change_percent,
            "dayChangeTWD": day_change_twd
        })
        
    return exchange_rate, portfolio_assets


@st.cache_data(ttl=600)
def fetch_historical_performance(assets_list, period="1mo"):
    """Fetches historical prices and constructs the portfolio history over time."""
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    if not symbols:
        return []
        
    symbols_to_fetch = list(set(symbols + ["USDTWD=X"]))
    
    # Map period string to yfinance periods
    period_mapping = {
        "1w": ("7d", "1d"),
        "1mo": ("1mo", "1d"),
        "3mo": ("3mo", "1d"),
        "6mo": ("6mo", "1d"),
        "1y": ("1y", "1d"),
        "all": ("max", "1wk")
    }
    yf_period, yf_interval = period_mapping.get(period, ("1mo", "1d"))
    
    try:
        # Download historical data
        hist_df = yf.download(symbols_to_fetch, period=yf_period, interval=yf_interval, group_by='ticker')
        if hist_df.empty:
            return []
            
        # Get list of index dates
        dates = hist_df.index
        
        # Create a parsed historical record
        chart_data = []
        
        cash_asset = next((a for a in assets_list if a["category"] == "cash"), None)
        cash_value = cash_asset["quantity"] if cash_asset else 0.0
        
        for date in dates:
            # Safely grab fx_rate
            fx_rate = 32.5
            try:
                if len(symbols_to_fetch) == 1 and "USDTWD=X" in symbols_to_fetch:
                    val = hist_df.loc[date, "Close"]
                else:
                    val = hist_df.loc[date, ("USDTWD=X", "Close")]
                if not pd.isna(val):
                    fx_rate = val
            except Exception:
                pass
                
            tw_value = 0.0
            us_value = 0.0
            crypto_value = 0.0
            
            for asset in assets_list:
                if asset["category"] == "cash":
                    continue
                sym = asset["symbol"]
                quantity = asset["quantity"]
                
                # Fetch closing price
                price = None
                try:
                    if len(symbols_to_fetch) == 1:
                        val = hist_df.loc[date, "Close"]
                    else:
                        val = hist_df.loc[date, (sym, "Close")]
                    if not pd.isna(val):
                        price = val
                except Exception:
                    pass
                
                if price is None:
                    continue
                    
                currency = "USD" if asset["category"] in ["us_stock", "crypto"] else "TWD"
                conv_rate = fx_rate if currency == "USD" else 1.0
                asset_val_twd = price * quantity * conv_rate
                
                if asset["category"] == "tw_stock":
                    tw_value += asset_val_twd
                elif asset["category"] == "us_stock":
                    us_value += asset_val_twd
                elif asset["category"] == "crypto":
                    crypto_value += asset_val_twd
                    
            total_value = tw_value + us_value + crypto_value + cash_value
            chart_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "twStock": tw_value,
                "usStock": us_value,
                "crypto": crypto_value,
                "cash": cash_value,
                "total": total_value
            })
            
        return chart_data
    except Exception as e:
        # Fallback empty
        return []

# ----------------- Main Controller -----------------

# Load current assets list from session / storage
if "assets" not in st.session_state:
    st.session_state.assets = load_assets()

# Sidebar Setup
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=100&q=80", width=60)
    st.markdown("<h2 style='margin-top:0;'>Tony's Control Panel</h2>", unsafe_allow_html=True)
    st.write("Manage your customized financial holdings here.")

    # Top level global actions
    st.subheader("Global Commands")
    
    col_ref, col_res = st.columns(2)
    with col_ref:
        if st.button("🔄 Refresh Rates", use_container_width=True):
            st.cache_data.clear()
            st.toast("Refreshed pricing index successfully!", icon="✅")
            st.rerun()
            
    with col_res:
        if st.button("🧼 Reset Assets", use_container_width=True, help="Reset portfolio setup to default initial values"):
            st.session_state.assets = DEFAULT_ASSETS.copy()
            save_assets(DEFAULT_ASSETS)
            st.cache_data.clear()
            st.toast("Portfolio reset complete!", icon="🧹")
            st.rerun()

    st.markdown("---")
    
    # Add Asset Section
    st.subheader("➕ Add New Asset")
    with st.form("add_asset_form", clear_on_submit=True):
        new_name = st.text_input("Asset Name", placeholder="e.g. Taiwan Semiconductor")
        new_sym = st.text_input("Symbol (Yahoo Finance Format)", placeholder="e.g. 2330.TW or AAPL")
        new_cat = st.selectbox("Category", options=list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS[x])
        new_qty = st.number_input("Holding Quantity", min_value=0.0, step=0.1, value=0.0, format="%.5f")
        
        submitted = st.form_submit_with_value("Add to Portfolio")
        if submitted:
            if not new_name or not new_sym:
                st.error("Please provide both a Display Name and Symbol.")
            else:
                # Clean symbol
                clean_sym = new_sym.strip().upper()
                # Construct new asset entry
                asset_id = f"{clean_sym}_{int(datetime.now().timestamp())}"
                new_asset_entry = {
                    "id": asset_id,
                    "name": new_name.strip(),
                    "symbol": clean_sym,
                    "category": new_cat,
                    "quantity": float(new_qty)
                }
                
                current_list = st.session_state.assets.copy()
                current_list.append(new_asset_entry)
                st.session_state.assets = current_list
                save_assets(current_list)
                st.cache_data.clear() # clear quotes cache
                st.success(f"Added {new_name} ({clean_sym})!")
                st.rerun()

# Welcome Header & Title
st.markdown("<h1 class='main-title'>Tony's <span class='highlight-title'>Asset Dashboard</span></h1>", unsafe_allow_html=True)
st.write("Track and balance multi-asset portfolios in Real-time (TW Stocks, US Stocks, Cryptos, and Cash).")

# Fetch calculated valuations
with st.spinner("Fetching active markets and calculating TWD values..."):
    exchange_rate, portfolio = fetch_realtime_market_data(st.session_state.assets)

# ----------------- Dashboard Valuations / Summary Calculations -----------------

total_net_worth = sum(a["totalValueTWD"] for a in portfolio)
total_day_change = sum(a["dayChangeTWD"] for a in portfolio)
prior_net_worth = total_net_worth - total_day_change
percent_change = (total_day_change / prior_net_worth * 100) if prior_net_worth > 0 else 0.0

cash_asset = next((a for a in portfolio if a["category"] == "cash"), None)
cash_total = cash_asset["totalValueTWD"] if cash_asset else 0.0
cash_ratio = (cash_total / total_net_worth * 100) if total_net_worth > 0 else 0.0

# Render top-level net stats
m1, m2, m3 = st.columns([2, 1, 1])

with m1:
    day_sign = "+" if total_day_change >= 0 else ""
    st.metric(
        label="Total Net Worth",
        value=format_currency_twd(total_net_worth),
        delta=f"{day_sign}{percent_change:.2f}% (Day: {day_sign}{format_currency_twd(total_day_change)})",
        delta_color="normal"
    )

with m2:
    st.metric(
        label="Cash Liquidity",
        value=format_currency_twd(cash_total),
        delta=f"{cash_ratio:.1f}% of portfolio",
        delta_color="off"
    )

with m3:
    st.metric(
        label="USDTWD Exchange Rate",
        value=f"NT$ {exchange_rate:.2f}",
        delta="Live Yahoo Query"
    )

# ----------------- Layout Main Sections -----------------

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📈 Performance History")
    
    # Performance Chart selectors
    chart_p1, chart_p2 = st.columns([2, 3])
    with chart_p1:
        selected_period = st.segmented_control(
            "Timeframe",
            options=["1w", "1mo", "3mo", "6mo", "1y", "all"],
            format_func=lambda x: x.upper(),
            default="1mo",
            label_visibility="collapsed"
        )
    with chart_p2:
        selected_class = st.segmented_control(
            "Asset Category Class",
            options=["total", "twStock", "usStock", "crypto", "cash"],
            format_func=lambda x: {
                "total": "Total Portfolio",
                "twStock": "Taiwan Stocks",
                "usStock": "US Stocks",
                "crypto": "Cryptocurrency",
                "cash": "Cash Only"
            }[x],
            default="total",
            label_visibility="collapsed"
        )
        
    hist_data = fetch_historical_performance(st.session_state.assets, period=selected_period)
    
    if hist_data:
        df_hist = pd.DataFrame(hist_data)
        
        # Plotly Area Chart
        fig_area = go.Figure()
        
        color_map = {
            "total": "#6366f1",
            "twStock": "#3B82F6",
            "usStock": "#8B5CF6",
            "crypto": "#F59E0B",
            "cash": "#10B981"
        }
        
        fig_area.add_trace(go.Scatter(
            x=df_hist["date"],
            y=df_hist[selected_class],
            mode="lines",
            fill="tozeroy",
            line_color=color_map.get(selected_class, "#6366f1"),
            fillcolor=f"{color_map.get(selected_class, '#6366f1')}1F", # semi-transparent
            name=selected_class,
            hovertemplate="<b>Date</b>: %{x}<br><b>Value (TWD)</b>: NT$ %{y:,.0f}<extra></extra>"
        ))
        
        fig_area.update_layout(
            margin=dict(l=20, r=20, t=10, b=10),
            height=280,
            paper_bgcolor="#0B0E14",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                showgrid=False,
                tickfont=dict(color="#A0AEC0", size=10),
                tickmode="auto"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#1E293B",
                tickfont=dict(color="#A0AEC0", size=10),
                tickprefix="NT$ "
            )
        )
        st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Loading performance timeline... (or Yahoo is fetching historical close prices)")

with col_right:
    st.subheader("🍩 Current Asset Allocation")
    
    # Calculate categories allocations
    alloc_totals = {}
    for a in portfolio:
        cat = a["category"]
        alloc_totals[cat] = alloc_totals.get(cat, 0.0) + a["totalValueTWD"]
        
    df_alloc = pd.DataFrame([
        {"Category": CATEGORY_LABELS[k], "Value": v, "Color": CATEGORY_COLORS[k]}
        for k, v in alloc_totals.items() if v > 0
    ])
    
    if not df_alloc.empty:
        # Donut Chart with matching theme colors
        fig_pie = px.pie(
            df_alloc, 
            values="Value", 
            names="Category", 
            hole=0.55,
            color="Category",
            color_discrete_map={CATEGORY_LABELS[k]: CATEGORY_COLORS[k] for k in CATEGORY_LABELS.keys()}
        )
        fig_pie.update_traces(
            textinfo="percent+label", 
            textposition="outside",
            hovertemplate="<b>%{label}</b><br>Value: NT$ %{value:,.0f}<br>Percent: %{percent}<extra></extra>"
        )
        fig_pie.update_layout(
            margin=dict(l=0, r=0, t=10, b=10),
            height=280,
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No asset holdings to calculate allocations.")

# ----------------- Grouped Asset Table & Adjustments -----------------
st.markdown("---")
st.subheader("📋 Your Asset Ledger")

# Group assets by Category to show custom tables
for cat_key in ["tw_stock", "us_stock", "crypto", "cash"]:
    cat_assets = [a for a in portfolio if a["category"] == cat_key]
    if not cat_assets:
        continue
        
    # Sort descending based on total TWD value
    cat_assets = sorted(cat_assets, key=lambda x: x["totalValueTWD"], reverse=True)
    
    cat_total_val = sum(a["totalValueTWD"] for a in cat_assets)
    cat_total_change = sum(a["dayChangeTWD"] for a in cat_assets)
    
    # Category Header Metrics
    ch_1, ch_2 = st.columns([3, 1])
    with ch_1:
         st.markdown(f"#### 🏷️ {CATEGORY_LABELS[cat_key]}")
    with ch_2:
         sign = "+" if cat_total_change >= 0 else ""
         st.markdown(
             f"<div style='text-align:right;'><strong style='font-size:1.1rem;'>{format_currency_twd(cat_total_val)}</strong><br>"
             f"<span style='font-size:0.8rem; font-family: monospace; color:{'#34D399' if cat_total_change >=0 else '#F87171'}'>"
             f"{sign}{format_currency_twd(cat_total_change)}</span></div>", 
             unsafe_allow_html=True
         )
         
    # Build data list for render
    tbl_data = []
    for asset in cat_assets:
        is_pos = asset["dayChangePercent"] >= 0
        symbol_only = asset["symbol"].split(".")[0]
        
        # Gain string matching requirement: Percent change accompanied by TWD value
        if cat_key == "cash":
            change_str = "-"
            price_str = "-"
        else:
            pct_sign = "+" if is_pos else ""
            twd_sign = "+" if is_pos else "-"
            abs_twd_val = format_currency_twd(abs(asset["dayChangeTWD"]))
            
            # The user request #4: 在百分比的後方 用同樣的字體跟顏色 顯示 該資產漲跌的金額
            # Same font color handled by placing it in the same output block
            color_hex = "#34D399" if is_pos else "#F87171"
            change_str = f"<span style='color:{color_hex}; font-family:monospace;'>{pct_sign}{asset['dayChangePercent']:.2f}% ({twd_sign}{abs_twd_val})</span>"
            price_str = format_currency_foreign(asset["currentPrice"], asset["currency"])
            
        tbl_data.append({
            "ID": asset["id"],
            "Asset": f"**{symbol_only}**<br><span style='color:#64748B;font-size:0.75rem;'>{asset['name']}</span>",
            "Holdings": f"{asset['quantity']:,.5f}".rstrip('0').rstrip('.'),
            "Price": price_str,
            "Day Change": change_str,
            "Total Value": f"**{format_currency_twd(asset['totalValueTWD'])}**",
            "obj": asset
        })
        
    df_render = pd.DataFrame(tbl_data)
    
    # Display elegant HTML tables
    st.write(
        df_render[["Asset", "Holdings", "Price", "Day Change", "Total Value"]].to_html(
            escape=False, index=False, justify="left", classes="stTable"
        ), 
        unsafe_allow_html=True
    )
    st.write("") # spacing

# ----------------- Manage Holdings (Edit Quantity & Buy/Sell Adjust) -----------------
st.markdown("---")
st.subheader("⚙️ Manage & Adjust Asset Quantity (買賣與數量修改)")

# Select which asset to modify
asset_options = {a["id"]: f"{CATEGORY_LABELS[a['category']]} - {a['symbol']} ({a['name']})" for a in portfolio}
selected_id = st.selectbox("Select Asset to Adjust", options=list(asset_options.keys()), format_func=lambda x: asset_options[x])

if selected_id:
    # Retrieve current active asset
    tgt = next((a for a in portfolio if a["id"] == selected_id), None)
    
    if tgt:
        manage_col_1, manage_col_2, manage_col_3 = st.columns([1, 1, 1])
        
        with manage_col_1:
            st.markdown(f"**Current Holdings**: `{tgt['quantity']:,.5f}`")
            # Quick actions
            trade_type = st.radio("Action Type", ["No quick adjustments (直接修改數量)", "Buy (買入資產)", "Sell (賣出資產)"])
            
        with manage_col_2:
            st.markdown("**Transaction Size**" if "No" not in trade_type else "**Holding Settings**")
            current_qty = tgt["quantity"]
            
            if "No" not in trade_type:
                trade_volume = st.number_input("Transaction Quantity", min_value=0.0, step=1.0, value=0.0, format="%.5f")
                
                # Dynamic calculations
                if "Buy" in trade_type:
                    projected_quantity = current_qty + trade_volume
                else:
                    projected_quantity = max(0.0, current_qty - trade_volume)
                    
                st.write(f"Projected holdings: `{current_qty:,.5f}` ➔ **`{projected_quantity:,.5f}`**")
            else:
                edit_qty = st.number_input("Modify Total Holdings Directly", min_value=0.0, value=current_qty, format="%.5f")
                projected_quantity = edit_qty
                
        with manage_col_3:
            st.markdown("**Metadata Settings**")
            edit_name = st.text_input("Asset Name", value=tgt["name"])
            
            # Action Buttons
            act_col1, act_col2 = st.columns(2)
            with act_col1:
                if st.button("💾 Save Action", use_container_width=True):
                    # Update local asset
                    all_assets = load_assets()
                    for idx, a in enumerate(all_assets):
                        # match by id or symbol
                        if (a.get("id") == tgt["id"]) or (a["symbol"] == tgt["symbol"] and a.get("id") is None):
                            all_assets[idx]["quantity"] = float(projected_quantity)
                            all_assets[idx]["name"] = edit_name
                            break
                            
                    st.session_state.assets = all_assets
                    save_assets(all_assets)
                    st.cache_data.clear() # invalidate prices
                    st.toast("Holding quantities successfully updated!", icon="💾")
                    st.rerun()
                    
            with act_col2:
                if tgt["category"] == "cash":
                    st.write("(Cash cannot be removed)")
                elif st.button("🗑️ Remove Asset", use_container_width=True, type="primary"):
                    all_assets = load_assets()
                    # filter out the deleted asset
                    filtered = [a for a in all_assets if not (a.get("id") == tgt["id"] or (a["symbol"] == tgt["symbol"] and a.get("id") is None))]
                    st.session_state.assets = filtered
                    save_assets(filtered)
                    st.cache_data.clear()
                    st.toast(f"Removed {tgt['name']} from asset list", icon="🗑️")
                    st.rerun()

# Footer StatusBar
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748B; font-size: 0.75rem; font-family: monospace;'>"
    f"Tony's Asset Dashboard • Live Sync via Yahoo Finance • Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    "</div>", 
    unsafe_allow_html=True
)
