import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
from datetime import datetime, timedelta

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_IMPORTED = True
except ImportError:
    GEMINI_IMPORTED = False

st.set_page_config(
    page_title="Tony's Asset Dashboard",
    page_icon="🍄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

is_dark = st.session_state.theme == "dark"

theme_bg      = "#000000" if is_dark else "#F5F5F7"
theme_card    = "#1C1C1E" if is_dark else "#FFFFFF"
theme_text    = "#FFFFFF" if is_dark else "#1D1D1F"
theme_subtext = "#8E8E93" if is_dark else "#6E6E73"
theme_border  = "#2C2C2E" if is_dark else "#D1D1D6"
theme_green   = "#30D158" if is_dark else "#34C759"
theme_red     = "#FF453A" if is_dark else "#FF3B30"
shadow_opacity = "0.5" if is_dark else "0.08"

# segmented control pill colours (light mode needs a light track)
seg_track  = "#3A3A3C" if is_dark else "#E5E5EA"
seg_active = "#1C1C1E" if is_dark else "#FFFFFF"
seg_text   = "#EBEBF5" if is_dark else "#1D1D1F"
seg_sub    = "#8E8E93"

CATEGORY_COLORS = {
    "tw_stock": "#0A84FF" if is_dark else "#007AFF",
    "us_stock": "#5E5CE6" if is_dark else "#5856D6",
    "crypto":   "#FF9F0A" if is_dark else "#FF9500",
    "cash":     theme_green,
}

st.markdown(f"""
<style>
  /* ── 1. GLOBAL BACKGROUND ─────────────────────────────────── */
  html, body,
  .stApp,
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewContainer"] > div,
  section[data-testid="stMain"],
  [data-testid="stMainBlockContainer"],
  [data-testid="stAppViewBlockContainer"],
  section.main {{
      background-color: {theme_bg} !important;
      background-image: none !important;
  }}
  [data-testid="stHeader"] {{ background-color: transparent !important; }}

  /* ── 2. TYPOGRAPHY ────────────────────────────────────────── */
  html, body, .stApp {{
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Helvetica, Arial, sans-serif !important;
      color: {theme_text} !important;
  }}
  .main-title {{
      font-weight: 700; color: {theme_text};
      letter-spacing: -0.02em; font-size: 2.4rem; margin-bottom: 0.2rem;
  }}
  .highlight-title {{ color: {CATEGORY_COLORS['tw_stock']}; font-weight: bold; }}
  div[data-testid="stMetricValue"] {{
      font-weight: 700; font-size: 1.8rem !important;
      letter-spacing: -0.01em; color: {theme_text} !important;
  }}
  div[data-testid="stMetricLabel"] {{
      color: {theme_subtext} !important; text-transform: uppercase;
      font-size: 0.7rem !important; letter-spacing: 0.05em; font-weight: 600;
  }}
  p, .stMarkdown p, h3, h4, label, .stTextInput label,
  [data-testid="stWidgetLabel"] p {{
      color: {theme_text} !important;
  }}

  /* ── 3. CARD CONTAINERS ───────────────────────────────────── */
  div[data-testid="stVerticalBlock"] {{
      background-color: transparent !important;
  }}
  div[data-testid="stVerticalBlock"]:has(> div.element-container .section-card) {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 20px !important;
      padding: 1.5rem !important;
      box-shadow: 0 8px 30px rgba(0,0,0,{shadow_opacity}) !important;
  }}
  .section-card {{ display: none !important; }}
  div[data-testid="stVerticalBlock"]:has(> div.element-container .section-card) > div {{
      background-color: transparent !important;
  }}

  /* ── 4. BUTTONS ───────────────────────────────────────────── */
  /* secondary / default */
  button[kind="secondary"],
  button[data-testid="stBaseButton-secondary"],
  button[data-testid="stPopoverButton"] {{
      background-color: {theme_card} !important;
      color: {theme_text} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
      transition: border-color 0.15s ease, color 0.15s ease !important;
  }}
  button[kind="secondary"]:hover,
  button[data-testid="stBaseButton-secondary"]:hover,
  button[data-testid="stPopoverButton"]:hover {{
      border-color: {CATEGORY_COLORS['tw_stock']} !important;
      color: {CATEGORY_COLORS['tw_stock']} !important;
  }}
  /* primary (delete) */
  button[kind="primary"],
  button[data-testid="stBaseButton-primary"] {{
      background-color: {theme_red} !important;
      color: #FFFFFF !important;
      border: none !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
  }}
  /* form submit */
  button[kind="secondaryFormSubmit"],
  button[data-testid="stBaseButton-secondaryFormSubmit"] {{
      background-color: {CATEGORY_COLORS['tw_stock']} !important;
      color: #FFFFFF !important;
      border: none !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
  }}

  /* ── 5. SEGMENTED CONTROL ─────────────────────────────────── */
  [data-testid="stButtonGroup"],
  div[aria-label="button group"] {{
      background-color: {seg_track} !important;
      border-radius: 10px !important;
      padding: 2px !important;
  }}
  button[kind="segmented_control"],
  button[data-testid="stBaseButton-segmented_control"] {{
      background-color: transparent !important;
      color: {seg_sub} !important;
      border: none !important;
      border-radius: 8px !important;
      font-weight: 500 !important;
  }}
  button[kind="segmented_controlActive"],
  button[data-testid="stBaseButton-segmented_controlActive"] {{
      background-color: {seg_active} !important;
      color: {seg_text} !important;
      border: none !important;
      border-radius: 8px !important;
      font-weight: 600 !important;
      box-shadow: 0 1px 4px rgba(0,0,0,0.2) !important;
  }}

  /* ── 6. INPUTS & SELECTS ──────────────────────────────────── */
  [data-baseweb="input"] > div,
  [data-baseweb="select"] > div,
  [data-testid="stNumberInputContainer"] > div {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 10px !important;
  }}
  [data-baseweb="input"] input,
  [data-baseweb="select"] div[class*="ValueContainer"] *,
  input[data-testid="stNumberInputField"] {{
      color: {theme_text} !important;
  }}
  /* Chat input */
  [data-testid="stChatInput"] {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 14px !important;
  }}
  [data-testid="stChatInput"] textarea {{
      color: {theme_text} !important;
      background-color: transparent !important;
  }}

  /* ── 7. POPOVER ───────────────────────────────────────────── */
  [data-testid="stPopoverBody"] {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 16px !important;
      box-shadow: 0 20px 40px rgba(0,0,0,{(0.8 if is_dark else 0.12)}) !important;
  }}
  [data-testid="stPopoverBody"] > div {{ background-color: transparent !important; }}

  /* ── 8. MISC ──────────────────────────────────────────────── */
  [data-testid="stImage"] img {{ border-radius: 50% !important; object-fit: cover; }}
  .row-divider {{ border-bottom: 1px solid {theme_border}; margin: 0.75rem 0; }}
  .table-header {{
      color: {theme_subtext}; font-size: 0.78rem; text-transform: uppercase;
      font-weight: 600; letter-spacing: 0.06em;
  }}
  /* expander arrow & label colour */
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] summary svg,
  [data-testid="stExpander"] summary p {{
      color: {theme_text} !important;
      font-weight: 600 !important;
  }}
  [data-testid="stExpander"] {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 16px !important;
  }}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ──────────────────────────────────────────────────
DB_FILE = "assets.json"

DEFAULT_ASSETS = [
    {"id": "00631L_TW",   "name": "元大台灣50正2",                    "symbol": "00631L.TW", "category": "tw_stock", "quantity": 131000.0, "average_cost": 30.0,    "account": "Default"},
    {"id": "00981A_TW",   "name": "00981A",                           "symbol": "00981A.TW", "category": "tw_stock", "quantity": 18000.0,  "average_cost": 25.0,    "account": "Default"},
    {"id": "BRKB_US",     "name": "Berkshire Hathaway Inc.",          "symbol": "BRK-B",     "category": "us_stock", "quantity": 65.0,     "average_cost": 400.0,   "account": "IB"},
    {"id": "TSLA_IB",     "name": "Tesla, Inc.",                      "symbol": "TSLA",      "category": "us_stock", "quantity": 100.0,    "average_cost": 200.0,   "account": "IB"},
    {"id": "TSLA_CATHAY", "name": "Tesla, Inc.",                      "symbol": "TSLA",      "category": "us_stock", "quantity": 55.4,     "average_cost": 190.0,   "account": "Cathay"},
    {"id": "GLDM_US",     "name": "SPDR Gold MiniShares",             "symbol": "GLDM",      "category": "us_stock", "quantity": 189.0,    "average_cost": 70.0,    "account": "Cathay"},
    {"id": "IWY_US",      "name": "iShares Russell Top 200 Growth ETF","symbol": "IWY",      "category": "us_stock", "quantity": 66.0,     "average_cost": 250.0,   "account": "IB"},
    {"id": "MSTR_US",     "name": "MicroStrategy Inc.",               "symbol": "MSTR",      "category": "us_stock", "quantity": 13.0,     "average_cost": 100.0,   "account": "IB"},
    {"id": "NVDA_US",     "name": "NVIDIA Corporation",               "symbol": "NVDA",      "category": "us_stock", "quantity": 110.0,    "average_cost": 100.0,   "account": "Cathay"},
    {"id": "BTC_CRYPTO",  "name": "Bitcoin",                          "symbol": "BTC-USD",   "category": "crypto",   "quantity": 0.09869,  "average_cost": 60000.0, "account": "Default"},
    {"id": "ETH_CRYPTO",  "name": "Ethereum",                         "symbol": "ETH-USD",   "category": "crypto",   "quantity": 0.90,     "average_cost": 2500.0,  "account": "Default"},
    {"id": "TWD_CASH",    "name": "Cash (TWD)",                       "symbol": "TWD",       "category": "cash",     "quantity": 1000000.0,"average_cost": 1.0,     "account": "Default"},
]

CATEGORY_LABELS = {"tw_stock": "Taiwan Stocks", "us_stock": "US Stocks", "crypto": "Cryptocurrency", "cash": "Cash & Equivalents"}
ACCOUNT_LABELS  = {"Default": "國泰證券戶", "Cathay": "國泰複委託 (Cathay)", "IB": "IB海外券商 (IB)"}

# ── FIREBASE ───────────────────────────────────────────────────
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
        except Exception:
            return None
    return None

# ── LOAD / SAVE ────────────────────────────────────────────────
def load_assets():
    db = get_db()
    if db:
        try:
            doc = db.collection("portfolios").document("tony_portfolio").get()
            if doc.exists:
                return doc.to_dict().get("assets", DEFAULT_ASSETS)
        except Exception:
            pass
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_ASSETS
    return DEFAULT_ASSETS

def save_assets(assets_list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(assets_list, f, ensure_ascii=False, indent=2)
    db = get_db()
    if db:
        try:
            db.collection("portfolios").document("tony_portfolio").set(
                {"assets": assets_list, "last_updated": datetime.now().isoformat()}
            )
        except Exception:
            st.toast("Warning: Could not sync to cloud database.", icon="⚠️")

def format_currency_twd(val):       return f"NT$ {val:,.0f}"
def format_currency_foreign(val, c):
    if c == "TWD": return f"NT$ {val:,.2f}"
    if c == "USD": return f"${val:,.2f}"
    return f"{c} {val:,.4f}"

# ── MARKET DATA ────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_realtime_market_data(assets_list):
    quote_data = {}
    exchange_rate = 32.5
    try:
        fx_hist = yf.Ticker("USDTWD=X").history(period="1mo", interval="1d")
        if not fx_hist.empty:
            exchange_rate = float(fx_hist["Close"].dropna().iloc[-1])
    except Exception:
        pass

    for asset in assets_list:
        if asset["category"] == "cash":
            continue
        sym = asset["symbol"]
        if sym in quote_data:
            continue
        try:
            ticker = yf.Ticker(sym)
            try:
                fi = ticker.fast_info
                if fi.last_price is not None and fi.previous_close is not None:
                    quote_data[sym] = {"price": float(fi.last_price), "prev_close": float(fi.previous_close)}
                    continue
            except Exception:
                pass
            hist = ticker.history(period="1mo", interval="1d").dropna(subset=["Close"])
            if hist.empty:
                continue
            hist.index = pd.to_datetime(hist.index, utc=True).tz_convert(None).normalize()
            hist = hist[~hist.index.duplicated(keep="last")].sort_index()
            if asset["category"] != "crypto":
                hist = hist[hist.index.dayofweek < 5]
                if "Volume" in hist.columns:
                    v = hist["Volume"] > 0
                    if len(v):
                        v.iloc[-1] = True
                        hist = hist[v]
            price      = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            quote_data[sym] = {"price": price, "prev_close": prev_close}
        except Exception:
            pass

    portfolio_assets = []
    for asset in assets_list:
        asset_id = asset.get("id", asset["symbol"])
        avg_cost = asset.get("average_cost", 0.0)
        account  = asset.get("account", "Default")
        if asset["category"] == "cash":
            portfolio_assets.append({
                "id": asset_id, "name": asset["name"], "symbol": asset["symbol"],
                "category": "cash", "account": account, "quantity": asset["quantity"],
                "currentPrice": 1.0, "currency": "TWD", "average_cost": 1.0,
                "totalCostTWD": asset["quantity"], "totalValueTWD": asset["quantity"],
                "dayChangePercent": 0.0, "dayChangeTWD": 0.0,
                "unrealizedPnlTWD": 0.0, "unrealizedPnlPercent": 0.0,
            })
            continue
        sym   = asset["symbol"]
        quote = quote_data.get(sym, {"price": 1.0, "prev_close": 1.0})
        cur_price   = quote["price"]
        prev_close  = quote["prev_close"]
        day_chg_pct = ((cur_price - prev_close) / prev_close * 100) if prev_close else 0.0
        currency    = "USD" if asset["category"] in ["us_stock", "crypto"] else "TWD"
        conv        = exchange_rate if currency == "USD" else 1.0
        tot_val     = cur_price * asset["quantity"] * conv
        tot_cost    = avg_cost  * asset["quantity"] * conv
        portfolio_assets.append({
            "id": asset_id, "name": asset["name"], "symbol": sym,
            "category": asset["category"], "account": account,
            "quantity": asset["quantity"], "currentPrice": cur_price,
            "currency": currency, "average_cost": avg_cost,
            "totalCostTWD": tot_cost,
            "unrealizedPnlTWD": tot_val - tot_cost,
            "unrealizedPnlPercent": ((cur_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0,
            "totalValueTWD": tot_val,
            "dayChangePercent": day_chg_pct,
            "dayChangeTWD": tot_val - prev_close * asset["quantity"] * conv,
        })
    return exchange_rate, portfolio_assets


@st.cache_data(ttl=600)
def fetch_historical_performance(assets_list, period="1mo"):
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    if not symbols:
        return []
    syms = list(set(symbols + ["USDTWD=X"]))
    pmap = {"1w": ("7d","1d"), "1mo": ("1mo","1d"), "3mo": ("3mo","1d"), "6mo": ("6mo","1d"), "1y": ("1y","1d")}
    yf_p, yf_i = pmap.get(period, ("1mo","1d"))
    frames = []
    for sym in syms:
        try:
            h = yf.Ticker(sym).history(period=yf_p, interval=yf_i)
            if h.empty: continue
            h.index = pd.to_datetime(h.index, utc=True).tz_convert(None).normalize()
            h = h[["Close"]].rename(columns={"Close": sym})
            h = h[~h.index.duplicated(keep="last")].sort_index()
            frames.append(h)
        except Exception:
            pass
    if not frames:
        return []
    df = pd.concat(frames, axis=1).sort_index().ffill().bfill()
    cash_val = sum(a["quantity"] for a in assets_list if a["category"] == "cash")
    rows = []
    for date in df.index:
        fx = 32.5
        if "USDTWD=X" in df.columns:
            v = df.loc[date, "USDTWD=X"]
            if not pd.isna(v): fx = float(v)
        tw = us = cr = 0.0
        for asset in assets_list:
            if asset["category"] == "cash": continue
            sym = asset["symbol"]
            if sym not in df.columns: continue
            v = df.loc[date, sym]
            if pd.isna(v): continue
            val = float(v) * asset["quantity"] * (fx if asset["category"] in ["us_stock","crypto"] else 1.0)
            if asset["category"] == "tw_stock": tw += val
            elif asset["category"] == "us_stock": us += val
            elif asset["category"] == "crypto": cr += val
        rows.append({"date": date.strftime("%Y-%m-%d"),
                     "twStock": tw, "usStock": us, "crypto": cr,
                     "cash": cash_val, "total": tw+us+cr+cash_val})
    return rows

# ── SESSION STATE ──────────────────────────────────────────────
if "assets" not in st.session_state:
    st.session_state.assets = load_assets()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=300&q=80", width=150)
    st.markdown("### System Status")
    if get_db():
        st.success("🟢 Firebase Cloud Sync: Active")
        st.caption("Data is safely backed up to Google Cloud.")
    else:
        st.warning("🟡 Local Storage Mode")
        st.caption("Cloud database not connected. Data may reset if Streamlit hibernates.")

# ── FETCH DATA ─────────────────────────────────────────────────
with st.spinner("Fetching active markets …"):
    exchange_rate, portfolio = fetch_realtime_market_data(st.session_state.assets)

total_net_worth       = sum(a["totalValueTWD"] for a in portfolio)
total_day_change      = sum(a["dayChangeTWD"]   for a in portfolio)
prior_net_worth       = total_net_worth - total_day_change
percent_change        = (total_day_change / prior_net_worth * 100) if prior_net_worth else 0.0
total_unrealized_pnl  = sum(a["unrealizedPnlTWD"] for a in portfolio if a["category"] != "cash")
total_cost_basis      = sum(a["totalCostTWD"]     for a in portfolio if a["category"] != "cash")
total_unrealized_pct  = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis else 0.0
cash_total            = sum(a["totalValueTWD"] for a in portfolio if a["category"] == "cash")

# ── HEADER ─────────────────────────────────────────────────────
hdr_l, hdr_r = st.columns([1.2, 1])
with hdr_l:
    st.markdown(f"<h1 class='main-title'>Tony's <span class='highlight-title'>Asset Dashboard</span></h1>", unsafe_allow_html=True)
    st.write("Real-time multi-asset portfolio tracker — TW Stocks, US Stocks, Crypto & Cash.")
with hdr_r:
    ds    = "+" if total_day_change >= 0 else ""
    color = theme_green if total_day_change >= 0 else theme_red
    st.markdown(f"""
    <div style='text-align:right;padding-top:0.5rem;'>
      <div style='color:{theme_subtext};font-size:.85rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;'>Total Net Worth</div>
      <div style='color:{theme_text};font-size:3.2rem;font-weight:700;font-family:-apple-system,BlinkMacSystemFont,monospace;letter-spacing:-0.02em;line-height:1;'>{format_currency_twd(total_net_worth)}</div>
      <div style='color:{color};font-size:1.1rem;font-weight:600;font-family:-apple-system,BlinkMacSystemFont,monospace;margin-top:8px;'>{ds}{format_currency_twd(total_day_change)} ({ds}{percent_change:.2f}%) Today</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# ── ACTION BAR ─────────────────────────────────────────────────
ac1, ac2, ac3, _ = st.columns([1.5, 1.5, 1.5, 5.5])

with ac1:
    if st.button("🔄 Refresh Rates", use_container_width=True):
        st.cache_data.clear()
        st.toast("Refreshed!", icon="✅")
        st.rerun()

with ac2:
    with st.popover("➕ Add Asset", use_container_width=True):
        st.markdown("**Add New Asset (新增資產)**")
        search_kw   = st.text_input("🔍 1. Search", placeholder="e.g. 2330 or AAPL")
        options_dict = {}
        if search_kw:
            try:
                r = requests.get(
                    f"https://query2.finance.yahoo.com/v1/finance/search?q={search_kw}",
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                for q in r.json().get("quotes", []):
                    if "symbol" in q and q.get("quoteType") in ["EQUITY","ETF","MUTUALFUND","CRYPTOCURRENCY","CURRENCY"]:
                        sym  = q["symbol"]
                        name = q.get("shortname", q.get("longname", "Unknown"))
                        exch = q.get("exchDisp", "")
                        options_dict[sym] = f"{sym} | {name} ({exch})"
            except Exception:
                pass
        with st.form("add_asset_form", clear_on_submit=True):
            if options_dict:
                new_sym = st.selectbox("🎯 2. Select Asset", list(options_dict.keys()), format_func=lambda x: options_dict[x])
            else:
                new_sym = st.text_input("🎯 2. Symbol (manual)", value=search_kw.upper() if search_kw else "")
            new_cat  = st.selectbox("Category", options=list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS[x])
            new_acc  = st.selectbox("Broker / Account", options=list(ACCOUNT_LABELS.keys()), format_func=lambda x: ACCOUNT_LABELS[x])
            new_qty  = st.number_input("Quantity",     min_value=0.0, step=0.1, value=0.0, format="%.5f")
            new_cost = st.number_input("Average Cost", min_value=0.0, step=0.1, value=0.0, format="%.5f")
            if st.form_submit_button("Save to Portfolio", use_container_width=True):
                if not new_sym:
                    st.error("Please enter or select a symbol.")
                else:
                    clean = new_sym.strip().upper()
                    name  = clean
                    if clean in options_dict:
                        parts = options_dict[clean].split(" | ")
                        if len(parts) > 1: name = parts[1].rsplit(" (", 1)[0]
                    else:
                        try:
                            info = yf.Ticker(clean).info
                            name = info.get("shortName", info.get("longName", clean))
                        except Exception:
                            pass
                    st.session_state.assets.append({
                        "id": f"{clean}_{int(datetime.now().timestamp())}",
                        "name": name, "symbol": clean,
                        "category": new_cat, "account": new_acc,
                        "quantity": float(new_qty), "average_cost": float(new_cost),
                    })
                    save_assets(st.session_state.assets)
                    st.cache_data.clear()
                    st.rerun()

with ac3:
    label = "🌞 Light Mode" if is_dark else "🌙 Dark Mode"
    if st.button(label, use_container_width=True):
        st.session_state.theme = "light" if is_dark else "dark"
        st.rerun()

st.markdown("---")

# ── METRIC CARDS ───────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
with m1:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        us = "+" if total_unrealized_pnl >= 0 else ""
        st.metric("Total Unrealized P/L", f"{us}{format_currency_twd(total_unrealized_pnl)}", f"{us}{total_unrealized_pct:.2f}% (All-Time)", delta_color="normal")
with m2:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        st.metric("Cash Liquidity", format_currency_twd(cash_total), f"{(cash_total/total_net_worth*100) if total_net_worth else 0:.1f}% of portfolio", delta_color="off")
with m3:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        st.metric("USDTWD Rate", f"NT$ {exchange_rate:.2f}", "Live Yahoo Query")

# ── CHARTS (collapsible) ───────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    with st.expander("📈 Performance History", expanded=False):
        chart_p1, chart_p2 = st.columns([2, 3])
        with chart_p1:
            selected_period = st.segmented_control(
                "Timeframe", ["1w","1mo","3mo","6mo","1y"],
                format_func=lambda x: x.upper(), default="1mo", label_visibility="collapsed")
        with chart_p2:
            selected_class = st.segmented_control(
                "Class", ["total","twStock","usStock","crypto","cash"],
                format_func=lambda x: {"total":"Total Portfolio","twStock":"Taiwan Stocks",
                                        "usStock":"US Stocks","crypto":"Cryptocurrency","cash":"Cash Only"}[x],
                default="total", label_visibility="collapsed")
        hist_data = fetch_historical_performance(st.session_state.assets, period=selected_period)
        if hist_data:
            df_hist  = pd.DataFrame(hist_data)
            fig_area = go.Figure()
            line_color = {"total": CATEGORY_COLORS["tw_stock"], "twStock": CATEGORY_COLORS["tw_stock"],
                          "usStock": CATEGORY_COLORS["us_stock"], "crypto": CATEGORY_COLORS["crypto"],
                          "cash": CATEGORY_COLORS["cash"]}.get(selected_class, CATEGORY_COLORS["tw_stock"])
            fig_area.add_trace(go.Scatter(
                x=df_hist["date"], y=df_hist[selected_class], mode="lines",
                line=dict(color=line_color, width=3),
                hovertemplate="<b>Date</b>: %{x}<br><b>Value (TWD)</b>: NT$ %{y:,.0f}<extra></extra>"))
            fig_area.update_layout(
                margin=dict(l=20,r=20,t=10,b=10), height=280,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, tickfont=dict(color=theme_subtext, size=10)),
                yaxis=dict(showgrid=True, gridcolor=theme_border,
                           tickfont=dict(color=theme_subtext, size=10), tickprefix="NT$ "))
            st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Loading performance timeline…")

with col_right:
    with st.expander("🍩 Current Asset Allocation", expanded=False):
        alloc_view = st.segmented_control(
            "View", ["Category","Asset"],
            format_func=lambda x: "資產類別" if x == "Category" else "單一標的",
            default="Category", label_visibility="collapsed")
        if alloc_view == "Category":
            df_alloc = pd.DataFrame([
                {"Category": CATEGORY_LABELS[k], "Value": v, "Color": CATEGORY_COLORS[k]}
                for k, v in {cat: sum(a["totalValueTWD"] for a in portfolio if a["category"] == cat)
                             for cat in CATEGORY_LABELS}.items() if v > 0])
            if not df_alloc.empty:
                fig_pie = px.pie(df_alloc, values="Value", names="Category", hole=0.55,
                                 color="Category",
                                 color_discrete_map={CATEGORY_LABELS[k]: CATEGORY_COLORS[k] for k in CATEGORY_LABELS})
        else:
            at = {}
            for a in portfolio:
                s = a["symbol"].split(".")[0]
                at[s] = at.get(s, 0) + a["totalValueTWD"]
            df_alloc = pd.DataFrame([{"Asset": k, "Value": v} for k, v in at.items() if v > 0])
            if not df_alloc.empty:
                fig_pie = px.pie(df_alloc, values="Value", names="Asset", hole=0.55)
        if not df_alloc.empty:
            fig_pie.update_traces(
                textinfo="percent+label", textposition="outside",
                textfont=dict(size=13, color=theme_text),
                hovertemplate="<b>%{label}</b><br>Value: NT$ %{value:,.0f}<br>Percent: %{percent}<extra></extra>")
            fig_pie.update_layout(margin=dict(l=60,r=60,t=40,b=80), height=380,
                                  paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No asset holdings.")

# ── AI PORTFOLIO ADVISOR ───────────────────────────────────────
st.markdown("---")
st.subheader("🤖 AI Portfolio Advisor")

with st.container(border=True):
    st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)

    if not GEMINI_IMPORTED or "GEMINI_API_KEY" not in st.secrets:
        st.warning("⚠️ AI 分析模組尚未啟用")
        st.info("""
**💡 3 步驟免費啟用 Google Gemini AI 顧問：**
1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 獲取免費 API Key。
2. 在 Streamlit Secrets 中新增：`GEMINI_API_KEY = "你的金鑰"`
3. 在 `requirements.txt` 加入：`google-generativeai`
        """)
    else:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        # ── 對話記錄顯示在輸入框上方 ──
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ── 快速分析按鈕 + 輸入框 ──
        col_btn, _ = st.columns([1, 2])
        with col_btn:
            analyze_clicked = st.button("✨ 一鍵分析目前的資產配置", use_container_width=True)

        user_msg = st.chat_input("詢問 AI 關於投資組合的建議 …")

        if analyze_clicked:
            user_msg = "請以專業財務顧問的角度，分析我目前的資產配置，並根據目前的總體經濟局勢給出建議。"

        if user_msg:
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)

            context = f"以下是我的投資組合現況 (總淨值: NT$ {total_net_worth:,.0f}):\n"
            for a in portfolio:
                pct = (a["totalValueTWD"]/total_net_worth*100) if total_net_worth else 0
                context += f"- {a['name']} ({a['category']}): NT$ {a['totalValueTWD']:,.0f} ({pct:.1f}%)\n"
            full_prompt = f"{context}\n\n使用者問題: {user_msg}"

            with st.chat_message("assistant"):
                with st.spinner("AI 正在深度分析中 …"):
                    try:
                        available = [m.name for m in genai.list_models()
                                     if "generateContent" in m.supported_generation_methods]
                        safe = [m for m in available
                                if not any(x in m for x in ["preview","experimental","computer"])]
                        target = next((m for m in safe if "gemini-1.5-flash" in m),
                                      next((m for m in safe if "flash" in m),
                                           safe[0] if safe else "models/gemini-1.5-flash"))
                        model    = genai.GenerativeModel(target)
                        response = model.generate_content(full_prompt)
                        st.markdown(response.text)
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"AI 回應發生錯誤：{e}")

            st.rerun()   # ← 讓新訊息出現在上方記錄區，輸入框回到底部

# ── ASSET LEDGER ───────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 Your Asset Ledger")

cols_ratio = [2, 1.2, 1.2, 1.2, 2.2, 2.2, 1.4, 0.8]

for cat_key in ["tw_stock", "us_stock", "crypto", "cash"]:
    raw_cat = [a for a in portfolio if a["category"] == cat_key]
    if not raw_cat:
        continue

    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)

        ch1, ch2 = st.columns([3, 1])
        with ch1:
            st.markdown(f"#### <span style='color:{CATEGORY_COLORS[cat_key]};'>●</span> {CATEGORY_LABELS[cat_key]}", unsafe_allow_html=True)
            if cat_key == "us_stock":
                broker_view = st.segmented_control(
                    "Filter", ["Merged","Cathay","IB"],
                    format_func=lambda x: {"Merged":"合併顯示 (All)","Cathay":"國泰複委託","IB":"IB海外券商"}[x],
                    default="Merged", label_visibility="collapsed")
                st.write("")
                if broker_view == "Cathay":
                    raw_cat = [a for a in raw_cat if a.get("account") == "Cathay"]
                elif broker_view == "IB":
                    raw_cat = [a for a in raw_cat if a.get("account") == "IB"]

        # group by symbol
        grouped = {}
        for a in raw_cat:
            s = a["symbol"]
            if s not in grouped:
                grouped[s] = {**a, "underlying": []}
            grouped[s]["underlying"].append(a)

        cat_assets = []
        for sym, grp in grouped.items():
            tot_qty  = sum(u["quantity"]        for u in grp["underlying"])
            tot_cost = sum(u["totalCostTWD"]    for u in grp["underlying"])
            tot_val  = sum(u["totalValueTWD"]   for u in grp["underlying"])
            tot_day  = sum(u["dayChangeTWD"]    for u in grp["underlying"])
            tot_pnl  = sum(u["unrealizedPnlTWD"] for u in grp["underlying"])
            if tot_qty <= 0 and grp["category"] != "cash":
                continue
            grp["quantity"]          = tot_qty
            grp["average_cost"]      = (sum(u["average_cost"]*u["quantity"] for u in grp["underlying"]) / tot_qty) if tot_qty else (sum(u["average_cost"] for u in grp["underlying"]) / len(grp["underlying"]))
            grp["totalValueTWD"]     = tot_val
            grp["dayChangeTWD"]      = tot_day
            grp["unrealizedPnlTWD"]  = tot_pnl
            grp["unrealizedPnlPercent"] = (tot_pnl / tot_cost * 100) if tot_cost else 0.0
            cat_assets.append(grp)

        cat_assets.sort(key=lambda x: x["totalValueTWD"], reverse=True)
        if not cat_assets:
            st.info("此帳戶檢視模式下目前無持有資產。")
            continue

        cat_total_val    = sum(a["totalValueTWD"] for a in cat_assets)
        cat_total_change = sum(a["dayChangeTWD"]  for a in cat_assets)

        with ch2:
            sign  = "+" if cat_total_change >= 0 else "-"
            color = theme_green if cat_total_change >= 0 else theme_red
            abs_c = abs(cat_total_change)
            if cat_key == "us_stock":
                val_usd = cat_total_val / exchange_rate
                abs_usd = abs_c / exchange_rate
                st.markdown(f"""
                <div style='text-align:right;'>
                  <strong style='font-size:1.1rem;color:{theme_text};'>{format_currency_twd(cat_total_val)}</strong>
                  <span style='font-size:.85rem;color:{theme_subtext};margin-left:4px;'>(US$ {val_usd:,.2f})</span><br>
                  <span style='font-size:.8rem;font-family:-apple-system,monospace;color:{color};'>
                    日盈虧: {sign}{format_currency_twd(abs_c)} (US$ {abs_usd:,.2f})
                  </span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='text-align:right;'>
                  <strong style='font-size:1.1rem;color:{theme_text};'>{format_currency_twd(cat_total_val)}</strong><br>
                  <span style='font-size:.8rem;font-family:-apple-system,monospace;color:{color};'>
                    日盈虧: {sign}{format_currency_twd(abs_c)}
                  </span>
                </div>""", unsafe_allow_html=True)

        # table header
        hc = st.columns(cols_ratio)
        for col, label in zip(hc, ["Asset","Holdings","Avg Cost","Price","Day Change","Total Return","Total Value","Act"]):
            col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

        for a in cat_assets:
            is_pos = a["dayChangePercent"] >= 0
            is_rp  = a["unrealizedPnlPercent"] >= 0
            if cat_key == "cash":
                change_str = return_str = price_str = cost_str = "-"
            else:
                cd  = theme_green if is_pos else theme_red
                cr  = theme_green if is_rp  else theme_red
                change_str = f"<span style='color:{cd};font-family:-apple-system,monospace;'>{'+' if is_pos else ''}{a['dayChangePercent']:.2f}% ({'+' if is_pos else '-'}{format_currency_twd(abs(a['dayChangeTWD']))})</span>"
                return_str = f"<span style='color:{cr};font-family:-apple-system,monospace;'>{'+' if is_rp else ''}{a['unrealizedPnlPercent']:.2f}% ({'+' if is_rp else '-'}{format_currency_twd(abs(a['unrealizedPnlTWD']))})</span>"
                price_str  = format_currency_foreign(a["currentPrice"],  a["currency"])
                cost_str   = format_currency_foreign(a["average_cost"], a["currency"])

            c = st.columns(cols_ratio)
            multi = f" <span style='font-size:.65rem;background:{theme_border};color:{theme_text};padding:2px 6px;border-radius:10px;margin-left:4px;'>{len(a['underlying'])} Accs</span>" if len(a["underlying"]) > 1 else ""
            c[0].markdown(f"<b style='color:{theme_text};'>{a['symbol'].split('.')[0]}</b>{multi}<br><span style='color:{theme_subtext};font-size:.75rem;'>{a['name']}</span>", unsafe_allow_html=True)
            c[1].markdown(f"<span style='color:{theme_text};'>{a['quantity']:,.5f}</span>".rstrip("0").rstrip("."), unsafe_allow_html=True)
            c[2].markdown(f"<span style='color:{theme_text};'>{cost_str}</span>",  unsafe_allow_html=True)
            c[3].markdown(f"<span style='color:{theme_text};'>{price_str}</span>", unsafe_allow_html=True)
            c[4].markdown(change_str, unsafe_allow_html=True)
            c[5].markdown(return_str, unsafe_allow_html=True)
            c[6].markdown(f"<b style='color:{theme_text};'>{format_currency_twd(a['totalValueTWD'])}</b>", unsafe_allow_html=True)

            with c[7]:
                with st.popover("⚙️"):
                    st.markdown(f"**Adjust {a['symbol'].split('.')[0]}**")
                    for i, u in enumerate(a["underlying"]):
                        st.caption(f"Broker: {ACCOUNT_LABELS.get(u.get('account','Default'),'國泰證券戶')}")
                        new_qty  = st.number_input("Holdings",     min_value=0.0, value=float(u["quantity"]),     format="%.5f", key=f"qty_{u['id']}")
                        new_cost = st.number_input("Average Cost", min_value=0.0, value=float(u["average_cost"]), format="%.5f", key=f"cost_{u['id']}")
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("💾 Save", key=f"save_{u['id']}", use_container_width=True):
                                for idx, s in enumerate(st.session_state.assets):
                                    if s.get("id", s.get("symbol")) == u["id"]:
                                        st.session_state.assets[idx]["quantity"]     = new_qty
                                        st.session_state.assets[idx]["average_cost"] = new_cost
                                        save_assets(st.session_state.assets)
                                        st.cache_data.clear()
                                        st.rerun()
                        with b2:
                            if cat_key != "cash":
                                if st.button("🗑️ Del", key=f"del_{u['id']}", use_container_width=True, type="primary"):
                                    st.session_state.assets = [s for s in st.session_state.assets if s.get("id", s.get("symbol")) != u["id"]]
                                    save_assets(st.session_state.assets)
                                    st.cache_data.clear()
                                    st.rerun()
                        if i < len(a["underlying"]) - 1:
                            st.divider()

            st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

# ── FOOTER ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:{theme_subtext};font-size:.75rem;font-family:-apple-system,monospace;'>"
    f"Tony's Asset Dashboard · Live via Yahoo Finance & Firebase · "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
    unsafe_allow_html=True)
