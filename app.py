import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
from datetime import datetime

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

# ── THEME ──────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "numbers_visible" not in st.session_state:
    st.session_state.numbers_visible = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

is_dark = st.session_state.theme == "dark"
nums_on = st.session_state.numbers_visible

theme_bg      = "#000000" if is_dark else "#F5F5F7"
theme_card    = "#1C1C1E" if is_dark else "#FFFFFF"
theme_text    = "#FFFFFF" if is_dark else "#1D1D1F"
theme_subtext = "#8E8E93" if is_dark else "#6E6E73"
theme_border  = "#2C2C2E" if is_dark else "#D1D1D6"
theme_green   = "#30D158" if is_dark else "#34C759"
theme_red     = "#FF453A" if is_dark else "#FF3B30"
shadow_opacity = "0.5" if is_dark else "0.08"
seg_track  = "#3A3A3C" if is_dark else "#E5E5EA"
seg_active = "#1C1C1E" if is_dark else "#FFFFFF"
seg_text   = "#EBEBF5" if is_dark else "#1D1D1F"
seg_sub    = "#8E8E93" if is_dark else "#6E6E73"
chat_bg    = "#2C2C2E" if is_dark else "#F2F2F7"
chat_text  = "#FFFFFF" if is_dark else "#1D1D1F"

CATEGORY_COLORS = {
    "tw_stock": "#0A84FF" if is_dark else "#007AFF",
    "us_stock": "#5E5CE6" if is_dark else "#5856D6",
    "crypto":   "#FF9F0A" if is_dark else "#FF9500",
    "cash":     theme_green,
}

st.markdown(f"""
<style>
  /* ── 1. GLOBAL BACKGROUND ──────────────────────────────────── */
  html, body, .stApp,
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

  /* ── 2. TYPOGRAPHY ─────────────────────────────────────────── */
  html, body, .stApp {{
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Helvetica, Arial, sans-serif !important;
      color: {theme_text} !important;
  }}
  .main-title {{ font-weight:700; color:{theme_text}; letter-spacing:-0.02em; font-size:2.4rem; margin-bottom:0.2rem; }}
  .highlight-title {{ color:{CATEGORY_COLORS['tw_stock']}; font-weight:bold; }}
  div[data-testid="stMetricValue"] {{ font-weight:700; font-size:1.8rem !important; letter-spacing:-0.01em; color:{theme_text} !important; }}
  div[data-testid="stMetricLabel"] {{ color:{theme_subtext} !important; text-transform:uppercase; font-size:0.7rem !important; letter-spacing:.05em; font-weight:600; }}
  p, .stMarkdown p, h3, h4, label, [data-testid="stWidgetLabel"] p {{ color:{theme_text} !important; }}

  /* ── 3. CARD CONTAINERS ─────────────────────────────────────── */
  div[data-testid="stVerticalBlock"] {{ background-color:transparent !important; }}
  div[data-testid="stVerticalBlock"]:has(> div.element-container .section-card) {{
      background-color:{theme_card} !important;
      border:1px solid {theme_border} !important;
      border-radius:20px !important;
      padding:1.5rem !important;
      box-shadow:0 8px 30px rgba(0,0,0,{shadow_opacity}) !important;
  }}
  .section-card {{ display:none !important; }}
  div[data-testid="stVerticalBlock"]:has(> div.element-container .section-card) > div {{ background-color:transparent !important; }}

  /* ── 4. BUTTONS ─────────────────────────────────────────────── */
  /* Force ALL Streamlit buttons to theme colours first */
  button {{
      background-color: {theme_card} !important;
      color: {theme_text} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
  }}
  button:hover {{
      border-color: {CATEGORY_COLORS['tw_stock']} !important;
      color: {CATEGORY_COLORS['tw_stock']} !important;
      background-color: {theme_card} !important;
  }}
  /* Primary / delete buttons */
  button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
      background-color: {theme_red} !important;
      color: #FFFFFF !important;
      border: none !important;
  }}
  button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
      background-color: {theme_red} !important;
      color: #FFFFFF !important;
      border: none !important;
  }}
  /* Form submit */
  button[kind="secondaryFormSubmit"], button[data-testid="stBaseButton-secondaryFormSubmit"] {{
      background-color: {CATEGORY_COLORS['tw_stock']} !important;
      color: #FFFFFF !important;
      border: none !important;
  }}

  /* ── 5. SEGMENTED CONTROL ───────────────────────────────────── */
  div[aria-label="button group"], [data-testid="stButtonGroup"] {{
      background-color: {seg_track} !important;
      border-radius: 10px !important;
      padding: 2px !important;
  }}
  button[kind="segmented_control"], button[data-testid="stBaseButton-segmented_control"] {{
      background-color: transparent !important;
      color: {seg_sub} !important;
      border: none !important;
      border-radius: 8px !important;
  }}
  button[kind="segmented_control"]:hover, button[data-testid="stBaseButton-segmented_control"]:hover {{
      background-color: transparent !important;
      color: {seg_sub} !important;
      border: none !important;
  }}
  button[kind="segmented_controlActive"], button[data-testid="stBaseButton-segmented_controlActive"] {{
      background-color: {seg_active} !important;
      color: {seg_text} !important;
      border: none !important;
      border-radius: 8px !important;
      box-shadow: 0 1px 4px rgba(0,0,0,0.2) !important;
  }}
  button[kind="segmented_controlActive"]:hover, button[data-testid="stBaseButton-segmented_controlActive"]:hover {{
      background-color: {seg_active} !important;
      color: {seg_text} !important;
      border: none !important;
  }}

  /* ── 6. INPUTS & SELECTS ────────────────────────────────────── */
  [data-baseweb="input"] > div,
  [data-baseweb="select"] > div,
  [data-testid="stNumberInputContainer"] > div {{
      background-color: {theme_card} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 10px !important;
  }}
  [data-baseweb="input"] input, input[data-testid="stNumberInputField"] {{ color:{theme_text} !important; }}

  /* ── 7. CHAT INPUT ──────────────────────────────────────────── */
  [data-testid="stChatInput"] {{
      background-color: {chat_bg} !important;
      border: 1px solid {theme_border} !important;
      border-radius: 14px !important;
  }}
  [data-testid="stChatInput"] textarea {{ color:{chat_text} !important; background-color:transparent !important; }}
  [data-testid="stChatInputSubmitButton"] {{
      background-color: {CATEGORY_COLORS['tw_stock']} !important;
      color: #FFFFFF !important;
      border: none !important;
      border-radius: 10px !important;
  }}
  /* Chat message bubbles */
  [data-testid="stChatMessage"] {{
      background-color: {chat_bg} !important;
      border-radius: 12px !important;
      color: {chat_text} !important;
  }}
  [data-testid="stChatMessage"] p {{ color: {chat_text} !important; }}

  /* ── 8. POPOVER ─────────────────────────────────────────────── */
  [data-testid="stPopoverBody"] {{
      background-color:{theme_card} !important;
      border:1px solid {theme_border} !important;
      border-radius:16px !important;
      box-shadow:0 20px 40px rgba(0,0,0,{0.8 if is_dark else 0.12}) !important;
  }}
  [data-testid="stPopoverBody"] > div {{ background-color:transparent !important; }}

  /* ── 9. EXPANDER ────────────────────────────────────────────── */
  [data-testid="stExpander"] {{
      background-color:{theme_card} !important;
      border:1px solid {theme_border} !important;
      border-radius:16px !important;
  }}
  [data-testid="stExpander"] summary, [data-testid="stExpander"] summary p,
  [data-testid="stExpander"] summary svg {{ color:{theme_text} !important; font-weight:600 !important; }}

  /* ── 10. MISC ───────────────────────────────────────────────── */
  [data-testid="stImage"] img {{ border-radius:50% !important; object-fit:cover; }}
  .row-divider {{ border-bottom:1px solid {theme_border}; margin:.75rem 0; }}
  .table-header {{ color:{theme_subtext}; font-size:.78rem; text-transform:uppercase; font-weight:600; letter-spacing:.06em; }}
  
  /* ── 11. PRIVACY TOGGLE ─────────────────────────────────────── */
  .privacy-btn {{
      background: none; border: none; cursor: pointer;
      color: {theme_subtext}; font-size: 1.4rem; padding: 0 4px;
      vertical-align: middle; line-height: 1;
  }}
  .privacy-btn:hover {{ color: {CATEGORY_COLORS['tw_stock']}; }}
  .blurred {{ filter: blur(8px); user-select: none; display: inline-block; }}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ──────────────────────────────────────────────────
DB_FILE = "assets.json"
DEFAULT_ASSETS = [
    {"id": "00631L_TW",   "name": "元大台灣50正2",                     "symbol": "00631L.TW", "category": "tw_stock", "quantity": 131000.0, "average_cost": 30.0,    "account": "Default"},
    {"id": "00981A_TW",   "name": "00981A",                            "symbol": "00981A.TW", "category": "tw_stock", "quantity": 18000.0,  "average_cost": 25.0,    "account": "Default"},
    {"id": "BRKB_US",     "name": "Berkshire Hathaway Inc.",           "symbol": "BRK-B",     "category": "us_stock", "quantity": 65.0,     "average_cost": 400.0,   "account": "IB"},
    {"id": "TSLA_IB",     "name": "Tesla, Inc.",                       "symbol": "TSLA",      "category": "us_stock", "quantity": 100.0,    "average_cost": 200.0,   "account": "IB"},
    {"id": "TSLA_CATHAY", "name": "Tesla, Inc.",                       "symbol": "TSLA",      "category": "us_stock", "quantity": 55.4,     "average_cost": 190.0,   "account": "Cathay"},
    {"id": "GLDM_US",     "name": "SPDR Gold MiniShares",              "symbol": "GLDM",      "category": "us_stock", "quantity": 189.0,    "average_cost": 70.0,    "account": "Cathay"},
    {"id": "IWY_US",      "name": "iShares Russell Top 200 Growth ETF","symbol": "IWY",       "category": "us_stock", "quantity": 66.0,     "average_cost": 250.0,   "account": "IB"},
    {"id": "MSTR_US",     "name": "MicroStrategy Inc.",                "symbol": "MSTR",      "category": "us_stock", "quantity": 13.0,     "average_cost": 100.0,   "account": "IB"},
    {"id": "NVDA_US",     "name": "NVIDIA Corporation",                "symbol": "NVDA",      "category": "us_stock", "quantity": 110.0,    "average_cost": 100.0,   "account": "Cathay"},
    {"id": "BTC_CRYPTO",  "name": "Bitcoin",                           "symbol": "BTC-USD",   "category": "crypto",   "quantity": 0.09869,  "average_cost": 60000.0, "account": "Default"},
    {"id": "ETH_CRYPTO",  "name": "Ethereum",                          "symbol": "ETH-USD",   "category": "crypto",   "quantity": 0.90,     "average_cost": 2500.0,  "account": "Default"},
    {"id": "TWD_CASH",    "name": "Cash (TWD)",                        "symbol": "TWD",       "category": "cash",     "quantity": 1000000.0,"average_cost": 1.0,     "account": "Default"},
]
CATEGORY_LABELS = {"tw_stock":"Taiwan Stocks","us_stock":"US Stocks","crypto":"Cryptocurrency","cash":"Cash & Equivalents"}
ACCOUNT_LABELS  = {"Default":"國泰證券戶","Cathay":"國泰複委託 (Cathay)","IB":"IB海外券商 (IB)"}

# ── AI SYSTEM PROMPT ───────────────────────────────────────────
AI_SYSTEM_PROMPT = """# Role
你是一位精通全球總體經濟、個股財報基本面以及量化交易的頂級「量化投資經理人 (Quantitative Investment Manager)」。你作風嚴謹、數據導向，擅長為高資產客戶或企業資產進行跨週期的動態配置。

# Task Description
請依序執行以下四個步驟，針對使用者輸入的資產數據與當前市場狀況進行深度分析，並給出符合其核心財務目標的投資策略建議。

---
## 步驟 1：資產讀取與結構化整理
首先，請仔細閱讀使用者提供的原始資產數據。在進行任何分析之前，請先將數據轉換為以下格式的 Markdown 表格，以便使用者確認你已正確解析所有資訊：

| 持有標的 (Ticker) | 持有股份 (Shares) | 目前單價 (Current Price) | 目前總價值 (Market Value) | 目前盈虧 (P&L / P&L %) | 佔總資產比例 (%) |

*注意：請在表格下方計算並標示出「目前總資產價值」與「整體核心組合的累積盈虧」。*

---
## 步驟 2：核心投資目標與角色設定
確認資產結構後，請切換至「專業量化投資經理人」視角。
* **使用者的核心目標：**「在 4 年內將資產翻倍」（這意味著資產年複合增長率 CAGR 需達到約 18.9%）。
* **操作風格限制：** 使用者屬於中長線佈局，**一年最多僅進行 4 次（每季一次）** 的核心資產配置調整。請不要給出高頻交易、當沖或過度頻繁換股的建議，所有操作建議必須以「季度」為單位進行權重平衡（Rebalancing）。

---
## 步驟 3：外部數據調研與評估依據（多維度分析）
在給出任何具體的買賣或加減碼建議之前，你必須整合並評估以下三層現實市場的經濟數據：

1. **個股最新財報基本面 (Fundamental Analysis)：**
   分析持倉標的最新一季的營收增長、EPS、毛利率變化、自由現金流以及未來指引（Guidance）。

2. **總體經濟狀況 (Macroeconomic Environment)：**
   評估當前利率環境（如聯準會貨幣政策）、通膨數據（CPI/PCE）、經濟增長率（GDP）以及市場流動性對該資產組合的潛在衝擊。

3. **即時技術分析指標 (Technical Analysis)：**
   參考持倉標的當前的關鍵技術指標（如 50MA/200MA 均線趨勢、RSI 強弱勢、MACD 以及波動率指標 ATR），判斷目前的價格區間是屬於過熱（超買）還是具備安全邊際（超賣）。

---
## 步驟 4：季度資產配置調整建議（Actionable Advice）
綜合上述所有數據與 4 年翻倍的目標，請給出具體、可執行的操作建議：
* **配置優化提案：** 針對目前的資產佔比，給出下一季度的目標權重建議（例如：維持現狀、加碼 A 標的、減碼 B 標的）。
* **策略執行理由：** 清楚說明做出此調整的邏輯。
* **風險控管提示：** 由於目標較為激進（CAGR ~19%），請特別指出當前組合中潛在的最大回撤（Maximum Drawdown）風險，以及在低操作頻率（一年 4 次）下，如何透過資產關聯度（Correlation）來分散極端市場風險。

---
# Output Format
請保持專業、冷靜、客觀的金融分析語氣，避免使用模糊不清的詞彙。請嚴格按照「步驟 1」到「步驟 4」的標題順序輸出報告，確保內容條理分明。

## 補充條款：專屬資產配置邊界與動態抄底規則
1. **核心風險承受度：** 使用者具備極高風險承受度，可接受單季最大回撤 (MDD) 達 -30%。分析時應以「追求 4 年翻倍 (CAGR ~18.9%)」為最高導向。
2. **資產目標配置比例：** 總資產配置：50% 00631L、50% 美股資產。
3. **「00631L 回檔 28%」動態抄底演算法：** 當技術指標顯示 00631L 從波段最高點跌幅超過 28% 時，必須觸發「動態加碼建議」。資金調配優先順序：優先建議動用「流動現金」進場抄底。若現金部位枯竭，應建議減碼最具防守性的 BRK.B，並將資金轉入 00631L 進行不對稱的攻擊佈局。"""

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
            pass
    return DEFAULT_ASSETS

def save_assets(assets_list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(assets_list, f, ensure_ascii=False, indent=2)
    db = get_db()
    if db:
        try:
            db.collection("portfolios").document("tony_portfolio").set(
                {"assets": assets_list, "last_updated": datetime.now().isoformat()})
        except Exception:
            st.toast("Warning: Could not sync to cloud.", icon="⚠️")

def format_currency_twd(val):     return f"NT$ {val:,.0f}"
def format_usd(val):              return f"${val:,.2f}"
def format_currency_foreign(val, c):
    if c == "TWD": return f"NT$ {val:,.2f}"
    if c == "USD": return f"${val:,.2f}"
    return f"{c} {val:,.4f}"

def private(text, always_blur=False):
    """Return text blurred if privacy mode is on."""
    if not nums_on or always_blur:
        return f"<span class='blurred'>{text}</span>"
    return text

# ── MARKET DATA ────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_realtime_market_data(assets_list):
    quote_data = {}
    exchange_rate = 32.5
    try:
        fx = yf.Ticker("USDTWD=X").history(period="1mo", interval="1d")
        if not fx.empty:
            exchange_rate = float(fx["Close"].dropna().iloc[-1])
    except Exception:
        pass

    for asset in assets_list:
        if asset["category"] == "cash": continue
        sym = asset["symbol"]
        if sym in quote_data: continue
        try:
            t = yf.Ticker(sym)
            try:
                fi = t.fast_info
                if fi.last_price is not None and fi.previous_close is not None:
                    quote_data[sym] = {"price": float(fi.last_price), "prev_close": float(fi.previous_close)}
                    continue
            except Exception:
                pass
            hist = t.history(period="1mo", interval="1d").dropna(subset=["Close"])
            if hist.empty: continue
            hist.index = pd.to_datetime(hist.index, utc=True).tz_convert(None).normalize()
            hist = hist[~hist.index.duplicated(keep="last")].sort_index()
            if asset["category"] != "crypto":
                hist = hist[hist.index.dayofweek < 5]
                if "Volume" in hist.columns:
                    v = hist["Volume"] > 0
                    if len(v): v.iloc[-1] = True; hist = hist[v]
            price      = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            quote_data[sym] = {"price": price, "prev_close": prev_close}
        except Exception:
            pass

    portfolio_assets = []
    for asset in assets_list:
        aid  = asset.get("id", asset["symbol"])
        cost = asset.get("average_cost", 0.0)
        acc  = asset.get("account", "Default")
        if asset["category"] == "cash":
            portfolio_assets.append({
                "id": aid, "name": asset["name"], "symbol": asset["symbol"],
                "category": "cash", "account": acc, "quantity": asset["quantity"],
                "currentPrice": 1.0, "currency": "TWD", "average_cost": 1.0,
                "totalCostTWD": asset["quantity"], "totalValueTWD": asset["quantity"],
                "dayChangePercent": 0.0, "dayChangeTWD": 0.0,
                "unrealizedPnlTWD": 0.0, "unrealizedPnlPercent": 0.0,
            })
            continue
        sym  = asset["symbol"]
        q    = quote_data.get(sym, {"price": 1.0, "prev_close": 1.0})
        cur  = q["price"]; prev = q["prev_close"]
        dcp  = ((cur - prev) / prev * 100) if prev else 0.0
        curr = "USD" if asset["category"] in ["us_stock","crypto"] else "TWD"
        conv = exchange_rate if curr == "USD" else 1.0
        tv   = cur  * asset["quantity"] * conv
        tc   = cost * asset["quantity"] * conv
        portfolio_assets.append({
            "id": aid, "name": asset["name"], "symbol": sym,
            "category": asset["category"], "account": acc,
            "quantity": asset["quantity"], "currentPrice": cur,
            "currency": curr, "average_cost": cost,
            "totalCostTWD": tc, "unrealizedPnlTWD": tv - tc,
            "unrealizedPnlPercent": ((cur - cost)/cost*100) if cost else 0.0,
            "totalValueTWD": tv, "dayChangePercent": dcp,
            "dayChangeTWD": tv - prev * asset["quantity"] * conv,
        })
    return exchange_rate, portfolio_assets

@st.cache_data(ttl=600)
def fetch_historical_performance(assets_list, period="1mo"):
    symbols = [a["symbol"] for a in assets_list if a["category"] != "cash"]
    if not symbols: return []
    syms = list(set(symbols + ["USDTWD=X"]))
    pmap = {"1w":("7d","1d"),"1mo":("1mo","1d"),"3mo":("3mo","1d"),"6mo":("6mo","1d"),"1y":("1y","1d")}
    yp, yi = pmap.get(period, ("1mo","1d"))
    frames = []
    for s in syms:
        try:
            h = yf.Ticker(s).history(period=yp, interval=yi)
            if h.empty: continue
            h.index = pd.to_datetime(h.index, utc=True).tz_convert(None).normalize()
            h = h[["Close"]].rename(columns={"Close": s})
            h = h[~h.index.duplicated(keep="last")].sort_index()
            frames.append(h)
        except Exception:
            pass
    if not frames: return []
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
            s = asset["symbol"]
            if s not in df.columns: continue
            v = df.loc[date, s]
            if pd.isna(v): continue
            val = float(v) * asset["quantity"] * (fx if asset["category"] in ["us_stock","crypto"] else 1.0)
            if asset["category"] == "tw_stock": tw += val
            elif asset["category"] == "us_stock": us += val
            elif asset["category"] == "crypto": cr += val
        rows.append({"date": date.strftime("%Y-%m-%d"), "twStock": tw, "usStock": us,
                     "crypto": cr, "cash": cash_val, "total": tw+us+cr+cash_val})
    return rows

# ── SESSION INIT ───────────────────────────────────────────────
if "assets" not in st.session_state:
    st.session_state.assets = load_assets()

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=300&q=80", width=150)
    st.markdown("### System Status")
    if get_db():
        st.success("🟢 Firebase Cloud Sync: Active")
        st.caption("Data safely backed up to Google Cloud.")
    else:
        st.warning("🟡 Local Storage Mode")
        st.caption("Cloud DB not connected. Data may reset on hibernation.")

# ── FETCH ──────────────────────────────────────────────────────
with st.spinner("Fetching active markets …"):
    exchange_rate, portfolio = fetch_realtime_market_data(st.session_state.assets)

total_net_worth      = sum(a["totalValueTWD"] for a in portfolio)
total_day_change     = sum(a["dayChangeTWD"]   for a in portfolio)
prior_net_worth      = total_net_worth - total_day_change
percent_change       = (total_day_change / prior_net_worth * 100) if prior_net_worth else 0.0
total_unrealized_pnl = sum(a["unrealizedPnlTWD"] for a in portfolio if a["category"] != "cash")
total_cost_basis     = sum(a["totalCostTWD"]     for a in portfolio if a["category"] != "cash")
total_unrealized_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis else 0.0
cash_total           = sum(a["totalValueTWD"] for a in portfolio if a["category"] == "cash")

# ── HEADER ─────────────────────────────────────────────────────
hdr_l, hdr_r = st.columns([1.2, 1])
with hdr_l:
    st.markdown("<h1 class='main-title'>Tony's <span class='highlight-title'>Asset Dashboard</span></h1>", unsafe_allow_html=True)
    st.write("Real-time multi-asset portfolio tracker — TW Stocks, US Stocks, Crypto & Cash.")

with hdr_r:
    ds    = "+" if total_day_change >= 0 else ""
    color = theme_green if total_day_change >= 0 else theme_red
    eye   = "👁" if nums_on else "👁‍🗨"
    # Privacy toggle button uses a Streamlit button that toggles state
    eye_label = "🙈 Hide Numbers" if nums_on else "👁 Show Numbers"
    nw_display  = format_currency_twd(total_net_worth)  if nums_on else "••••••••"
    day_display = f"{ds}{format_currency_twd(total_day_change)} ({ds}{percent_change:.2f}%) Today" if nums_on else f"•••••••• ({ds}{percent_change:.2f}%) Today"

    st.markdown(f"""
    <div style='text-align:right;padding-top:0.5rem;'>
      <div style='color:{theme_subtext};font-size:.85rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;'>Total Net Worth</div>
      <div style='color:{theme_text};font-size:3.2rem;font-weight:700;font-family:-apple-system,monospace;letter-spacing:-0.02em;line-height:1;'>{nw_display}</div>
      <div style='color:{color};font-size:1.1rem;font-weight:600;font-family:-apple-system,monospace;margin-top:8px;'>{day_display}</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# ── ACTION BAR ─────────────────────────────────────────────────
ac1, ac2, ac3, ac4, _ = st.columns([1.4, 1.4, 1.4, 1.6, 4.2])

with ac1:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.toast("Refreshed!", icon="✅")
        st.rerun()

with ac2:
    with st.popover("➕ Add Asset", use_container_width=True):
        st.markdown("**Add New Asset (新增資產)**")
        search_kw    = st.text_input("🔍 Search", placeholder="e.g. 2330 or AAPL")
        options_dict = {}
        if search_kw:
            try:
                r = requests.get(
                    f"https://query2.finance.yahoo.com/v1/finance/search?q={search_kw}",
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                for q in r.json().get("quotes", []):
                    if "symbol" in q and q.get("quoteType") in ["EQUITY","ETF","MUTUALFUND","CRYPTOCURRENCY","CURRENCY"]:
                        s = q["symbol"]
                        n = q.get("shortname", q.get("longname", "Unknown"))
                        e = q.get("exchDisp", "")
                        options_dict[s] = f"{s} | {n} ({e})"
            except Exception:
                pass
        with st.form("add_asset_form", clear_on_submit=True):
            if options_dict:
                new_sym = st.selectbox("🎯 Select Asset", list(options_dict.keys()), format_func=lambda x: options_dict[x])
            else:
                new_sym = st.text_input("🎯 Symbol (manual)", value=search_kw.upper() if search_kw else "")
            new_cat  = st.selectbox("Category", options=list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS[x])
            new_acc  = st.selectbox("Broker", options=list(ACCOUNT_LABELS.keys()), format_func=lambda x: ACCOUNT_LABELS[x])
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
                        "name": name, "symbol": clean, "category": new_cat,
                        "account": new_acc, "quantity": float(new_qty), "average_cost": float(new_cost),
                    })
                    save_assets(st.session_state.assets)
                    st.cache_data.clear()
                    st.rerun()

with ac3:
    label = "🌞 Light" if is_dark else "🌙 Dark"
    if st.button(label, use_container_width=True):
        st.session_state.theme = "light" if is_dark else "dark"
        st.rerun()

with ac4:
    priv_label = "🙈 Hide Numbers" if nums_on else "👁 Show Numbers"
    if st.button(priv_label, use_container_width=True):
        st.session_state.numbers_visible = not nums_on
        st.rerun()

st.markdown("---")

# ── METRIC CARDS ───────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
with m1:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        us_sign = "+" if total_unrealized_pnl >= 0 else ""
        pnl_val = f"{us_sign}{format_currency_twd(total_unrealized_pnl)}" if nums_on else "••••••••"
        pnl_delta = f"{us_sign}{total_unrealized_pct:.2f}% (All-Time)"
        st.metric("Total Unrealized P/L", pnl_val, pnl_delta, delta_color="normal")
with m2:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        cash_val = format_currency_twd(cash_total) if nums_on else "••••••••"
        cash_pct = f"{(cash_total/total_net_worth*100) if total_net_worth else 0:.1f}% of portfolio"
        st.metric("Cash Liquidity", cash_val, cash_pct, delta_color="off")
with m3:
    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)
        st.metric("USDTWD Rate", f"NT$ {exchange_rate:.2f}", "Live Yahoo Query")

# ── CHARTS (collapsible) ───────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    with st.expander("📈 Performance History", expanded=False):
        cp1, cp2 = st.columns([2, 3])
        with cp1:
            selected_period = st.segmented_control(
                "TF", ["1w","1mo","3mo","6mo","1y"],
                format_func=lambda x: x.upper(), default="1mo", label_visibility="collapsed")
        with cp2:
            selected_class = st.segmented_control(
                "CL", ["total","twStock","usStock","crypto","cash"],
                format_func=lambda x: {"total":"Total","twStock":"TW","usStock":"US","crypto":"Crypto","cash":"Cash"}[x],
                default="total", label_visibility="collapsed")
        hist_data = fetch_historical_performance(st.session_state.assets, period=selected_period)
        if hist_data:
            df_hist  = pd.DataFrame(hist_data)
            lc = {"total":CATEGORY_COLORS["tw_stock"],"twStock":CATEGORY_COLORS["tw_stock"],
                  "usStock":CATEGORY_COLORS["us_stock"],"crypto":CATEGORY_COLORS["crypto"],
                  "cash":CATEGORY_COLORS["cash"]}.get(selected_class, CATEGORY_COLORS["tw_stock"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_hist["date"], y=df_hist[selected_class], mode="lines",
                                     line=dict(color=lc, width=3),
                                     hovertemplate="<b>Date</b>: %{x}<br><b>Value</b>: NT$ %{y:,.0f}<extra></extra>"))
            fig.update_layout(margin=dict(l=20,r=20,t=10,b=10), height=260,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              xaxis=dict(showgrid=False, tickfont=dict(color=theme_subtext, size=10)),
                              yaxis=dict(showgrid=True, gridcolor=theme_border,
                                         tickfont=dict(color=theme_subtext, size=10), tickprefix="NT$ "))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Loading performance timeline…")

with col_right:
    with st.expander("🍩 Current Asset Allocation", expanded=False):
        alloc_view = st.segmented_control(
            "AV", ["Category","Asset"],
            format_func=lambda x: "資產類別" if x=="Category" else "單一標的",
            default="Category", label_visibility="collapsed")
        df_alloc = pd.DataFrame()
        if alloc_view == "Category":
            df_alloc = pd.DataFrame([
                {"Category": CATEGORY_LABELS[k], "Value": v}
                for k, v in {c: sum(a["totalValueTWD"] for a in portfolio if a["category"]==c)
                             for c in CATEGORY_LABELS}.items() if v > 0])
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
                textfont=dict(size=12, color=theme_text),
                hovertemplate="<b>%{label}</b><br>Value: NT$ %{value:,.0f}<br>%{percent}<extra></extra>")
            fig_pie.update_layout(margin=dict(l=50,r=50,t=30,b=70), height=360,
                                  paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No asset holdings.")

# ── ASSET LEDGER ───────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 Your Asset Ledger")

cols_ratio = [2, 1.2, 1.2, 1.2, 2.2, 2.2, 1.4, 0.8]

for cat_key in ["tw_stock", "us_stock", "crypto", "cash"]:
    raw_cat = [a for a in portfolio if a["category"] == cat_key]
    if not raw_cat: continue

    with st.container(border=True):
        st.markdown("<div class='section-card'></div>", unsafe_allow_html=True)

        ch1, ch2 = st.columns([3, 1])
        with ch1:
            st.markdown(f"#### <span style='color:{CATEGORY_COLORS[cat_key]};'>●</span> {CATEGORY_LABELS[cat_key]}", unsafe_allow_html=True)
            if cat_key == "us_stock":
                bv = st.segmented_control("BF", ["Merged","Cathay","IB"],
                    format_func=lambda x: {"Merged":"合併顯示 (All)","Cathay":"國泰複委託","IB":"IB海外券商"}[x],
                    default="Merged", label_visibility="collapsed")
                st.write("")
                if bv == "Cathay": raw_cat = [a for a in raw_cat if a.get("account")=="Cathay"]
                elif bv == "IB":   raw_cat = [a for a in raw_cat if a.get("account")=="IB"]

        grouped = {}
        for a in raw_cat:
            s = a["symbol"]
            if s not in grouped: grouped[s] = {**a, "underlying": []}
            grouped[s]["underlying"].append(a)

        cat_assets = []
        for sym, grp in grouped.items():
            tq   = sum(u["quantity"]         for u in grp["underlying"])
            tc   = sum(u["totalCostTWD"]     for u in grp["underlying"])
            tv   = sum(u["totalValueTWD"]    for u in grp["underlying"])
            td   = sum(u["dayChangeTWD"]     for u in grp["underlying"])
            tp   = sum(u["unrealizedPnlTWD"] for u in grp["underlying"])
            if tq <= 0 and grp["category"] != "cash": continue
            grp["quantity"]             = tq
            grp["average_cost"]         = (sum(u["average_cost"]*u["quantity"] for u in grp["underlying"])/tq) if tq else 0
            grp["totalValueTWD"]        = tv
            grp["dayChangeTWD"]         = td
            grp["unrealizedPnlTWD"]     = tp
            grp["unrealizedPnlPercent"] = (tp/tc*100) if tc else 0.0
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
            ac    = abs(cat_total_change)
            tv_disp  = format_currency_twd(cat_total_val)    if nums_on else "••••••••"
            day_disp = f"{sign}{format_currency_twd(ac)}"    if nums_on else "••••••••"
            if cat_key == "us_stock":
                usd_disp = f"(US$ {cat_total_val/exchange_rate:,.2f})"       if nums_on else ""
                usd_d    = f" (US$ {ac/exchange_rate:,.2f})"                  if nums_on else ""
                st.markdown(f"""<div style='text-align:right;'>
                  <strong style='font-size:1.1rem;color:{theme_text};'>{tv_disp}</strong>
                  <span style='font-size:.85rem;color:{theme_subtext};margin-left:4px;'>{usd_disp}</span><br>
                  <span style='font-size:.8rem;font-family:-apple-system,monospace;color:{color};'>日盈虧: {day_disp}{usd_d}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div style='text-align:right;'>
                  <strong style='font-size:1.1rem;color:{theme_text};'>{tv_disp}</strong><br>
                  <span style='font-size:.8rem;font-family:-apple-system,monospace;color:{color};'>日盈虧: {day_disp}</span>
                </div>""", unsafe_allow_html=True)

        hc = st.columns(cols_ratio)
        for col, lbl in zip(hc, ["Asset","Holdings","Avg Cost","Price","Day Change","Total Return","Total Value","Act"]):
            col.markdown(f"<div class='table-header'>{lbl}</div>", unsafe_allow_html=True)
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

        for a in cat_assets:
            ip = a["dayChangePercent"] >= 0
            ir = a["unrealizedPnlPercent"] >= 0
            if cat_key == "cash":
                chg_s = ret_s = pr_s = co_s = "-"
            else:
                cd = theme_green if ip else theme_red
                cr = theme_green if ir else theme_red
                
                chg_pct_str = f"{'+' if ip else ''}{a['dayChangePercent']:.2f}%"
                chg_amt_str = f"({'+' if ip else '-'}{format_currency_twd(abs(a['dayChangeTWD']))})" if nums_on else "(••••)"
                chg_s = f"<span style='color:{cd};font-family:-apple-system,monospace;'>{chg_pct_str} {chg_amt_str}</span>"
                
                ret_pct_str = f"{'+' if ir else ''}{a['unrealizedPnlPercent']:.2f}%"
                ret_amt_str = f"({'+' if ir else '-'}{format_currency_twd(abs(a['unrealizedPnlTWD']))})" if nums_on else "(••••)"
                ret_s = f"<span style='color:{cr};font-family:-apple-system,monospace;'>{ret_pct_str} {ret_amt_str}</span>"
                
                pr_s  = format_currency_foreign(a["currentPrice"],  a["currency"])
                co_s  = format_currency_foreign(a["average_cost"],  a["currency"])

            c = st.columns(cols_ratio)
            multi = f" <span style='font-size:.65rem;background:{theme_border};color:{theme_text};padding:2px 6px;border-radius:10px;'>{len(a['underlying'])} Accs</span>" if len(a["underlying"]) > 1 else ""
            tv_cell = format_currency_twd(a["totalValueTWD"]) if nums_on else "••••••••"
            ht_cell = f"{a['quantity']:,.5f}".rstrip("0").rstrip(".") if nums_on else "••••"
            c[0].markdown(f"<b style='color:{theme_text};'>{a['symbol'].split('.')[0]}</b>{multi}<br><span style='color:{theme_subtext};font-size:.75rem;'>{a['name']}</span>", unsafe_allow_html=True)
            c[1].markdown(f"<span style='color:{theme_text};'>{ht_cell}</span>", unsafe_allow_html=True)
            c[2].markdown(f"<span style='color:{theme_text};'>{co_s}</span>",    unsafe_allow_html=True)
            c[3].markdown(f"<span style='color:{theme_text};'>{pr_s}</span>",    unsafe_allow_html=True)
            c[4].markdown(chg_s, unsafe_allow_html=True)
            c[5].markdown(ret_s, unsafe_allow_html=True)
            c[6].markdown(f"<b style='color:{theme_text};'>{tv_cell}</b>",       unsafe_allow_html=True)

            with c[7]:
                with st.popover("⚙️"):
                    st.markdown(f"**Adjust {a['symbol'].split('.')[0]}**")
                    for i, u in enumerate(a["underlying"]):
                        st.caption(f"Broker: {ACCOUNT_LABELS.get(u.get('account','Default'))}")
                        nq = st.number_input("Holdings",     min_value=0.0, value=float(u["quantity"]),     format="%.5f", key=f"qty_{u['id']}")
                        nc = st.number_input("Average Cost", min_value=0.0, value=float(u["average_cost"]), format="%.5f", key=f"cost_{u['id']}")
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("💾 Save", key=f"save_{u['id']}", use_container_width=True):
                                for idx, s in enumerate(st.session_state.assets):
                                    if s.get("id", s.get("symbol")) == u["id"]:
                                        st.session_state.assets[idx]["quantity"]     = nq
                                        st.session_state.assets[idx]["average_cost"] = nc
                                        save_assets(st.session_state.assets)
                                        st.cache_data.clear()
                                        st.rerun()
                        with b2:
                            if cat_key != "cash":
                                if st.button("🗑️ Del", key=f"del_{u['id']}", use_container_width=True, type="primary"):
                                    st.session_state.assets = [s for s in st.session_state.assets if s.get("id",s.get("symbol")) != u["id"]]
                                    save_assets(st.session_state.assets)
                                    st.cache_data.clear()
                                    st.rerun()
                        if i < len(a["underlying"]) - 1:
                            st.divider()

            st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

# ── AI PORTFOLIO ADVISOR (最底部) ──────────────────────────────
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

        # ── 對話紀錄顯示在輸入框上方 ──
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ── 一鍵分析按鈕 ──
        col_btn, _ = st.columns([1, 2])
        with col_btn:
            analyze_clicked = st.button("✨ 一鍵深度分析資產配置", use_container_width=True, key="ai_analyze_btn")

        if analyze_clicked:
            st.session_state.trigger_ai_analysis = True

        # ── 輸入框 ──
        user_msg = st.chat_input("詢問 AI 量化投資建議，或點上方按鈕一鍵分析 …")

        if st.session_state.get("trigger_ai_analysis"):
            user_msg = "請執行完整的四步驟深度分析。"
            st.session_state.trigger_ai_analysis = False

        if user_msg:
            # 組裝完整 prompt
            portfolio_data = f"【投資組合現況】總淨值: NT$ {total_net_worth:,.0f}\n\n"
            portfolio_data += "| 標的 | 類別 | 持倉數量 | 目前單價 | 市場總值(TWD) | 未實現盈虧(TWD) | 未實現盈虧% | 佔比% |\n"
            portfolio_data += "|---|---|---|---|---|---|---|---|\n"
            for a in portfolio:
                pct  = (a["totalValueTWD"]/total_net_worth*100) if total_net_worth else 0
                pr   = format_currency_foreign(a["currentPrice"], a["currency"]) if a["category"] != "cash" else "-"
                pnl  = format_currency_twd(a["unrealizedPnlTWD"]) if a["category"] != "cash" else "-"
                pnlp = f"{a['unrealizedPnlPercent']:.2f}%" if a["category"] != "cash" else "-"
                portfolio_data += f"| {a['symbol']} | {a['category']} | {a['quantity']:,.4f} | {pr} | {format_currency_twd(a['totalValueTWD'])} | {pnl} | {pnlp} | {pct:.1f}% |\n"

            full_prompt = f"{AI_SYSTEM_PROMPT}\n\n---\n\n{portfolio_data}\n\n使用者指令: {user_msg}"

            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)

            with st.chat_message("assistant"):
                with st.spinner("量化分析引擎運行中 …"):
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

            st.rerun()

# ── FOOTER ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:{theme_subtext};font-size:.75rem;font-family:-apple-system,monospace;'>"
    f"Tony's Asset Dashboard · Yahoo Finance & Firebase · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    "</div>", unsafe_allow_html=True)
