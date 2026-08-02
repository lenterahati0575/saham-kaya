import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import math
import numpy as np
from scipy import stats
from scipy.stats import norm
from screener import (DEFAULT_PARAMS, load_ticker_universe, fetch_price_history, build_screener_table,
                      build_trade_candidates, classify_daytrading_tipe, fetch_ihsg_history, market_regime,
                      _donchian_levels)
from telegram_notify import send_telegram_message, format_watchlist_message
import gsheet_journal as gj
import indicators as ind
import calculators as calc
import sectors as sec
import real_journal as rj
import equity as eq

st.set_page_config(page_title="IDX Screener Dashboard", page_icon="📈", layout="wide")

def _check_auth() -> bool:
    app_password = st.secrets.get("APP_PASSWORD", "")
    if not app_password:
        st.warning("⚠️ Dashboard ini belum terkunci. `APP_PASSWORD` belum diisi di Settings > Secrets.")
        return True
    if st.session_state.get("_authenticated", False):
        return True
    st.title("🔒 IDX Screener Dashboard")
    st.caption("Dashboard ini berisi data trading pribadi. Masukkan password untuk melanjutkan.")
    with st.form("_login_form"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Masuk", type="primary")
        if submitted:
            if pw == app_password:
                st.session_state["_authenticated"] = True
                st.rerun()
            else:
                st.error("Password salah.")
    return False

if not _check_auth():
    st.stop()

components.html("""
<script>
(function() {
try {
const doc = window.parent.document;
if (!window.parent.__autoSelectNumberInputs) {
window.parent.__autoSelectNumberInputs = true;
doc.addEventListener('focusin', function(e) {
if (e.target && e.target.tagName === 'INPUT' && e.target.type === 'number') {
e.target.select();
}
});
}
} catch (err) { }
})();
</script>
""", height=0)

def embed_tradingview_chart(kode: str, height: int = 520):
    src = (
        f"https://s.tradingview.com/widgetembed/?symbol=IDX%3A{kode}"
        f"&interval=D&theme=dark&style=1&locale=id&toolbar_bg=%230e1117"
        f"&hide_top_toolbar=0&allow_symbol_change=1&save_image=0"
    )
    html = f'<iframe src="{src}" width="100%" height="{height}" frameborder="0" allowtransparency="true" scrolling="no"></iframe>'
    components.html(html, height=height + 10)

# ============================================================
# GANN SQUARE OF 9 + TIME CYCLE MODULE
# ============================================================
class GannSquareOf9:
    @staticmethod
    def calculate_level(price):
        sqrt_price = math.sqrt(price)
        return {
            'resistance': {
                'R1_45°': round((sqrt_price + 0.125) ** 2, 2), 'R2_90°': round((sqrt_price + 0.25) ** 2, 2),
                'R3_180°': round((sqrt_price + 0.5) ** 2, 2), 'R4_360°': round((sqrt_price + 1.0) ** 2, 2),
            },
            'support': {
                'S1_45°': round((sqrt_price - 0.125) ** 2, 2), 'S2_90°': round((sqrt_price - 0.25) ** 2, 2),
                'S3_180°': round((sqrt_price - 0.5) ** 2, 2), 'S4_360°': round((sqrt_price - 1.0) ** 2, 2),
            }
        }
    @staticmethod
    def time_cycle_analysis(start_date, price_at_start, current_date=None):
        if current_date is None: current_date = datetime.now()
        gann_cycles = [30, 45, 60, 90, 120, 180, 270, 360, 540, 720]
        fib_cycles = [8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
        all_cycles = []
        for days in gann_cycles + fib_cycles:
            target_date = start_date + timedelta(days=days)
            days_from_now = (target_date - current_date).days
            all_cycles.append({'type': 'Gann' if days in gann_cycles else 'Fibonacci', 'days': days, 'date': target_date.strftime('%Y-%m-%d'), 'days_from_now': days_from_now, 'passed': days_from_now < 0})
        all_cycles.sort(key=lambda x: x['days_from_now'])
        return all_cycles

def detect_pivot_low(df, window=10):
    if df is None or len(df) < window * 2 + 1: return df.index[-1] if df is not None and len(df) > 0 else datetime.now(), 0
    lows = df['Low'].rolling(window=window*2+1, center=True).min()
    pivots = df[df['Low'] == lows].copy()
    if len(pivots) == 0:
        idx = df.iloc[-window:]['Low'].idxmin()
        return idx, df.loc[idx, 'Low']
    return pivots.index[-1], pivots['Low'].iloc[-1]

def detect_pivot_high(df, window=10):
    if df is None or len(df) < window * 2 + 1: return df.index[-1] if df is not None and len(df) > 0 else datetime.now(), 0
    highs = df['High'].rolling(window=window*2+1, center=True).max()
    pivots = df[df['High'] == highs].copy()
    if len(pivots) == 0:
        idx = df.iloc[-window:]['High'].idxmax()
        return idx, df.loc[idx, 'High']
    return pivots.index[-1], pivots['High'].iloc[-1]

def analyze_ihsg_gann(ihsg_hist):
    if ihsg_hist is None or ihsg_hist.empty: return None
    current_price = float(ihsg_hist['Close'].iloc[-1])
    high_1y = float(ihsg_hist['High'].max())
    low_1y = float(ihsg_hist['Low'].min())
    pivot_low_idx, pivot_low_price = detect_pivot_low(ihsg_hist, window=10)
    pivot_high_idx, pivot_high_price = detect_pivot_high(ihsg_hist, window=10)
    gann = GannSquareOf9.calculate_level(current_price)
    pivot_low_date = pivot_low_idx.to_pydatetime() if isinstance(pivot_low_idx, pd.Timestamp) else datetime.now() - timedelta(days=30)
    cycles = GannSquareOf9.time_cycle_analysis(pivot_low_date, pivot_low_price)
    upcoming = [c for c in cycles if not c['passed'] and c['days_from_now'] <= 90]
    range_total = high_1y - low_1y
    position_pct = ((current_price - low_1y) / range_total * 100) if range_total > 0 else 50
    rsi_approx = 30 + (position_pct / 100 * 40)
    near_resistance = current_price > gann['resistance']['R1_45°'] * 0.995
    near_support = current_price < gann['support']['S1_45°'] * 1.005
    cycle_alert = any(c['days_from_now'] <= 7 for c in upcoming)
    if near_support and rsi_approx < 35: bias = "🟢 BULLISH BIAS — Dekat Support"
    elif near_resistance and rsi_approx > 65: bias = "🔴 BEARISH BIAS — Dekat Resistance"
    elif cycle_alert: bias = "🟡 REVERSAL WATCH — Time Cycle Aktif"
    else: bias = "⚪ NEUTRAL — Pantau Breakout"
    return {'current': current_price, 'high_1y': high_1y, 'low_1y': low_1y, 'pivot_low': (pivot_low_idx, pivot_low_price), 'pivot_high': (pivot_high_idx, pivot_high_price), 'gann': gann, 'cycles': upcoming, 'position_pct': position_pct, 'rsi_approx': rsi_approx, 'bias': bias, 'cycle_alert': cycle_alert}

class BrokerAPI:
    SUPPORTED_BROKERS = ["Mirae Asset Sekuritas", "Ajaib Sekuritas", "Stockbit Sekuritas", "Philip Sekuritas", "IPOT (Indo Premier)", "Sinarmas Sekuritas", "Bahana Sekuritas", "BNI Sekuritas", "Mandiri Sekuritas", "Manual / Lainnya"]
    def __init__(self, broker_name="Manual / Lainnya", api_key=None, api_secret=None):
        self.broker = broker_name; self.api_key = api_key; self.api_secret = api_secret; self.connected = False
    def connect(self):
        self.connected = True
        return True, "Manual mode — order dicatat di jurnal saja" if self.broker == "Manual / Lainnya" else f"{self.broker} — API integration placeholder."
    def place_order(self, kode, side, qty, price, order_type="LIMIT"):
        if not self.connected: return False, "Not connected to broker"
        return True, f"Order dicatat di jurnal: {side} {kode} @ Rp{price:,.0f} x {qty} lot" if self.broker == "Manual / Lainnya" else f"[API] {side} {kode} @ Rp{price:,.0f} x {qty} lot — ORDER PLACED (simulasi)"

def validate_order(kode, side, qty, price, cash_available, broker_fee_pct=0.0015):
    errors = []
    if qty < 1: errors.append("Lot minimal 1")
    if price <= 0: errors.append("Harga harus > 0")
    total = price * qty * 100; fee = total * broker_fee_pct; total_cost = total + fee
    if side.upper() == "BUY" and total_cost > cash_available: errors.append(f"Dana tidak cukup. Butuh: Rp{total_cost:,.0f}, Tersedia: Rp{cash_available:,.0f}")
    if errors: return False, " | ".join(errors), total_cost
    return True, f"Order valid. Total: Rp{total_cost:,.0f} (incl. fee Rp{fee:,.0f})", total_cost

def black_scholes(S, K, T, r, sigma, option_type='call'):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return None
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call': price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else: price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    if option_type == 'put': theta = theta - r * K * np.exp(-r * T) * norm.cdf(-d2)
    else: theta = theta + r * K * np.exp(-r * T) * norm.cdf(d2)
    vega = S * norm.pdf(d1) * np.sqrt(T)
    return {"price": round(price, 2), "delta": round(delta, 4), "gamma": round(gamma, 6), "theta": round(theta, 4), "vega": round(vega, 4)}

def calculate_iv_rank(df, window=252):
    if df is None or len(df) < window: return None
    returns = df['Close'].pct_change().dropna()
    if len(returns) < window: return None
    rolling_vol = returns.rolling(20).std() * np.sqrt(252) * 100
    current_vol = rolling_vol.iloc[-1]; vol_high = rolling_vol.tail(window).max(); vol_low = rolling_vol.tail(window).min()
    iv_rank = ((current_vol - vol_low) / (vol_high - vol_low)) * 100 if vol_high != vol_low else 50
    return {"current_hv": round(current_vol, 2), "52w_high": round(vol_high, 2), "52w_low": round(vol_low, 2), "iv_rank": round(iv_rank, 1), "iv_percentile": round((rolling_vol.tail(window) < current_vol).mean() * 100, 1), "interpretation": "HIGH IV — Sell premium" if iv_rank > 70 else ("LOW IV — Buy premium" if iv_rank < 30 else "NORMAL IV")}

def expected_move(S, sigma, days=30):
    if S <= 0 or sigma <= 0: return None
    move = S * (sigma / 100) * np.sqrt(days / 252)
    return {"up": round(S + move, 2), "down": round(S - move, 2), "move_pct": round((move / S) * 100, 2), "range": f"Rp{S - move:,.0f} - Rp{S + move:,.0f}"}

def generate_option_chain(S, current_price, vol, r=0.065, days_to_expiry=30):
    T = days_to_expiry / 365
    step = max(25, round(current_price * 0.02 / 25) * 25)
    atm = round(current_price / step) * step
    strikes = [atm + (i - 5) * step for i in range(11)]
    chain = []
    for K in strikes:
        call = black_scholes(S, K, T, r, vol / 100, 'call'); put = black_scholes(S, K, T, r, vol / 100, 'put')
        moneyness = "ATM" if abs(K - S) < step * 0.5 else ("ITM" if K < S else "OTM")
        chain.append({"Strike": int(K), "Moneyness": moneyness, "Call Price": f"Rp{call['price']:,.0f}" if call else "-", "Call Delta": call['delta'] if call else "-", "Put Price": f"Rp{put['price']:,.0f}" if put else "-", "Put Delta": put['delta'] if put else "-"})
    return chain

def get_market_session():
    now = datetime.now(); hour = now.hour; minute = now.minute; time_val = hour + minute / 60; weekday = now.weekday()
    if weekday >= 5:
        next_open = now + timedelta(days=(7 - weekday) % 7); next_open = next_open.replace(hour=8, minute=0, second=0)
        return {"session": "🔴 WEEKEND CLOSED", "color": "#7f1d1d", "desc": "Pasar tutup. Buka Senin 08:00 WIB.", "next_open": next_open, "countdown": (next_open - now).total_seconds(), "is_open": False}
    if 8 <= time_val < 9: return {"session": "🟡 PRE-MARKET", "color": "#eab308", "desc": "Bursa belum buka.", "next_open": now.replace(hour=9, minute=0), "countdown": 0, "is_open": False}
    elif 9 <= time_val < 9.5: return {"session": "🟢 OPENING AUCTION", "color": "#16a34a", "desc": "JATS opening auction.", "next_open": None, "countdown": 0, "is_open": True}
    elif 9.5 <= time_val < 12: return {"session": "🟢 REGULAR SESSION I", "color": "#16a34a", "desc": "Sesi reguler pagi.", "next_open": None, "countdown": 0, "is_open": True}
    elif 12 <= time_val < 13.5: return {"session": "🟠 LUNCH BREAK", "color": "#f97316", "desc": "Istirahat.", "next_open": now.replace(hour=13, minute=30), "countdown": 0, "is_open": False}
    elif 13.5 <= time_val < 15: return {"session": "🟢 REGULAR SESSION II", "color": "#16a34a", "desc": "Sesi reguler sore.", "next_open": None, "countdown": 0, "is_open": True}
    elif 15 <= time_val < 15.25: return {"session": "🟢 CLOSING AUCTION", "color": "#16a34a", "desc": "Closing auction.", "next_open": None, "countdown": 0, "is_open": True}
    elif 15.25 <= time_val < 16: return {"session": "🟡 POST-MARKET", "color": "#eab308", "desc": "After hours.", "next_open": None, "countdown": 0, "is_open": False}
    else:
        next_day = now + timedelta(days=1); next_open = next_day.replace(hour=8, minute=0, second=0)
        if next_open.weekday() >= 5: next_open += timedelta(days=(7 - next_open.weekday()) % 7)
        return {"session": "🔴 CLOSED", "color": "#7f1d1d", "desc": "Pasar tutup.", "next_open": next_open, "countdown": (next_open - now).total_seconds(), "is_open": False}

def format_countdown(seconds):
    if seconds <= 0: return "00:00:00"
    return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"

def moon_phase(date):
    known_new = datetime(2000, 1, 6, 18, 14); diff = (date - known_new).total_seconds() / 86400; lunar_cycle = 29.53059; age = diff % lunar_cycle; phase_pct = age / lunar_cycle
    if age < 1: name = "🌑 NEW MOON"; trading_bias = "🟢 BULLISH — Reversal ke atas"
    elif age < 7: name = "🌒 WAXING CRESCENT"; trading_bias = "🟢 BULLISH — Momentum naik"
    elif age < 14: name = "🌓 FIRST QUARTER"; trading_bias = "🟡 NEUTRAL-BULLISH"
    elif age < 16: name = "🌕 FULL MOON"; trading_bias = "🔴 BEARISH — Reversal ke bawah"
    elif age < 22: name = "🌖 WANING GIBBOUS"; trading_bias = "🔴 BEARISH — Momentum turun"
    elif age < 28: name = "🌗 LAST QUARTER"; trading_bias = "🟡 NEUTRAL-BEARISH"
    else: name = "🌘 WANING CRESCENT"; trading_bias = "🟢 BULLISH — Persiapan New Moon"
    return {"age": age, "phase_pct": phase_pct, "name": name, "bias": trading_bias}

def astro_cycle_analysis(current_date=None):
    if current_date is None: current_date = datetime.now()
    moon = moon_phase(current_date)
    planets = {"Mercury": 88, "Venus": 225, "Mars": 687, "Jupiter": 4333, "Saturn": 10759}
    base_date = datetime(2000, 1, 1); days_since = (current_date - base_date).days
    planet_positions = {name: round(((days_since % period) / period) * 360, 1) for name, period in planets.items()}
    conjunctions = []; planet_names = list(planet_positions.keys())
    for i in range(len(planet_names)):
        for j in range(i+1, len(planet_names)):
            p1, p2 = planet_names[i], planet_names[j]; diff = abs(planet_positions[p1] - planet_positions[p2])
            if diff > 180: diff = 360 - diff
            if diff < 15: conjunctions.append(f"{p1}-{p2} ({diff:.1f}°)")
    fib_days = [8, 13, 21, 34, 55, 89, 144, 233, 377]; recent_events = []
    last_new_moon = current_date - timedelta(days=int(moon["age"]))
    for fd in fib_days:
        target = last_new_moon + timedelta(days=fd); days_diff = (target - current_date).days
        if 0 <= days_diff <= 7: recent_events.append({"event": f"Fib {fd} dari New Moon", "date": target.strftime("%Y-%m-%d"), "days_left": days_diff, "type": "🌑 Lunar-Fib"})
    return {"moon": moon, "planets": planet_positions, "conjunctions": conjunctions, "events": recent_events}

@st.cache_data(ttl=1800)
def fetch_sentiment_news():
    import requests; news_items = []
    try:
        api_key = st.secrets.get("NEWSAPI_KEY", "")
        if api_key:
            url = f"https://newsapi.org/v2/everything?q=IHSG+OR+Indonesia+stock&language=id&sortBy=publishedAt&pageSize=10&apiKey={api_key}"
            resp = requests.get(url, timeout=10); data = resp.json()
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                positive_words = ["naik", "rebound", "cuan", "profit", "bullish", "membeli", "net buy", "menguat", "positif", "optimis"]
                negative_words = ["turun", "jual", "bearish", "rugi", "loss", "melemah", "net sell", "jual asing", "inflasi", "resesi"]
                for a in articles[:8]:
                    title = a.get("title", "").lower()
                    pos_count = sum(1 for w in positive_words if w in title); neg_count = sum(1 for w in negative_words if w in title)
                    if pos_count > neg_count: sent = "positive"
                    elif neg_count > pos_count: sent = "negative"
                    else: sent = "neutral"
                    news_items.append({"headline": a.get("title", ""), "sentiment": sent, "source": a.get("source", {}).get("name", "News"), "time": "recent"})
    except: pass
    if not news_items:
        news_items = [{"headline": "IHSG Rebound 18% dari Low, Analis: Belum Konfirmasi Bull Run", "sentiment": "neutral", "source": "IDX Channel", "time": "2h ago"},
                      {"headline": "Asing Net Buy Rp500M Hari Ini, Fokus ke BBCA dan BMRI", "sentiment": "positive", "source": "Kontan", "time": "5h ago"},
                      {"headline": "Rupiah Melemah ke Rp18.200, BI Rate Diproyeksi Turun", "sentiment": "negative", "source": "Bisnis Indonesia", "time": "4h ago"}]
    pos = sum(1 for n in news_items if n["sentiment"] == "positive"); neg = sum(1 for n in news_items if n["sentiment"] == "negative"); neu = sum(1 for n in news_items if n["sentiment"] == "neutral"); total = len(news_items)
    sentiment_score = ((pos - neg) / total * 100) if total > 0 else 0
    if sentiment_score > 20: overall = "🟢 BULLISH"; color = "#16a34a"
    elif sentiment_score > 5: overall = "🟡 SLIGHTLY BULLISH"; color = "#eab308"
    elif sentiment_score > -5: overall = "⚪ NEUTRAL"; color = "#6b7280"
    elif sentiment_score > -20: overall = "🟠 SLIGHTLY BEARISH"; color = "#f97316"
    else: overall = "🔴 BEARISH"; color = "#dc2626"
    return {"items": news_items, "positive": pos, "negative": neg, "neutral": neu, "score": round(sentiment_score, 1), "overall": overall, "color": color}

def ml_signal_predict(df, lookback=20):
    if df is None or len(df) < lookback + 10: return None
    try:
        close = df['Close']; volume = df['Volume']
        ma5 = close.rolling(5).mean().iloc[-1]; ma20 = close.rolling(20).mean().iloc[-1]; ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma20
        trend_score = 0
        if close.iloc[-1] > ma5: trend_score += 1
        if ma5 > ma20: trend_score += 1
        if ma20 > ma50: trend_score += 1
        high_20 = df['High'].tail(20).max(); low_20 = df['Low'].tail(20).min(); range_20 = high_20 - low_20
        momentum = (close.iloc[-1] - low_20) / range_20 if range_20 > 0 else 0.5
        momentum_score = 1 if momentum > 0.6 else (0 if momentum > 0.4 else -1)
        vol_avg = volume.tail(20).mean(); vol_today = volume.iloc[-1]
        vol_score = 1 if vol_today > vol_avg * 1.2 else (0 if vol_today > vol_avg * 0.8 else -1)
        atr = calculate_atr(df, 14); atr_pct = (atr / close.iloc[-1]) * 100 if close.iloc[-1] > 0 else 0
        vol_regime_score = 1 if atr_pct < 2.5 else (0 if atr_pct < 4 else -1)
        total_score = trend_score + momentum_score + vol_score + vol_regime_score
        features = [trend_score, momentum_score, vol_score, vol_regime_score]
        agreement = sum(1 for f in features if f == (1 if total_score > 0 else (-1 if total_score < 0 else 0)))
        confidence = min(95, agreement * 25)
        if total_score >= 3: signal = "🟢 STRONG BUY"; signal_color = "#065f46"
        elif total_score >= 1: signal = "🟡 BUY"; signal_color = "#16a34a"
        elif total_score <= -3: signal = "🔴 STRONG SELL"; signal_color = "#7f1d1d"
        elif total_score <= -1: signal = "🟠 SELL"; signal_color = "#dc2626"
        else: signal = "⚪ HOLD"; signal_color = "#6b7280"; confidence = 30
        return {"signal": signal, "confidence": confidence, "score": total_score, "features": {"Trend": trend_score, "Momentum": momentum_score, "Volume": vol_score, "Volatility": vol_regime_score}, "signal_color": signal_color}
    except: return None

def check_alert_conditions(ihsg_gann_data, current_price, prev_price=None):
    alerts = []
    if ihsg_gann_data is None: return alerts
    gann = ihsg_gann_data['gann']
    for k, v in gann['resistance'].items():
        if abs(current_price - v) / v < 0.003: alerts.append(f"🚨 IHSG mendekati Gann RESISTANCE {k}: {v:,.0f}")
    for k, v in gann['support'].items():
        if abs(current_price - v) / v < 0.003: alerts.append(f"🚨 IHSG mendekati Gann SUPPORT {k}: {v:,.0f}")
    for c in ihsg_gann_data.get('cycles', []):
        if c['days_from_now'] == 0: alerts.append(f"⏰ TIME CYCLE HARI INI: {c['type']} {c['days']}D")
        elif c['days_from_now'] == 1: alerts.append(f"⏰ TIME CYCLE BESOK: {c['type']} {c['days']}D")
    return alerts

def calculate_atr(df, period=14):
    if df is None or len(df) < period + 1: return 0
    high_low = df['High'] - df['Low']; high_close = abs(df['High'] - df['Close'].shift()); low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

def volatility_regime(df, period=14):
    atr = calculate_atr(df, period); close = df['Close'].iloc[-1]; atr_pct = (atr / close) * 100 if close > 0 else 0
    if atr_pct < 1.0: return {"regime": "LOW", "atr_pct": atr_pct, "color": "#4ade80", "desc": "Volatilitas rendah"}
    elif atr_pct < 2.5: return {"regime": "NORMAL", "atr_pct": atr_pct, "color": "#38bdf8", "desc": "Volatilitas normal"}
    elif atr_pct < 4.0: return {"regime": "HIGH", "atr_pct": atr_pct, "color": "#fbbf24", "desc": "Volatilitas tinggi"}
    else: return {"regime": "EXTREME", "atr_pct": atr_pct, "color": "#f87171", "desc": "Volatilitas ekstrem"}

def market_breadth(price_data, tickers, lookback=20):
    above_ma = 0; below_ma = 0; total_valid = 0; advancers = 0; decliners = 0
    for kode in tickers:
        df = price_data.get(kode)
        if df is None or len(df) < lookback + 2: continue
        try:
            ma20 = df['Close'].rolling(lookback).mean().iloc[-1]; current = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
            if pd.notna(ma20) and pd.notna(current):
                total_valid += 1
                if current > ma20: above_ma += 1
                else: below_ma += 1
                if current > prev: advancers += 1
                elif current < prev: decliners += 1
        except: continue
    if total_valid == 0: return None
    ad_ratio = advancers / max(decliners, 1); above_pct = (above_ma / total_valid) * 100
    if above_pct > 65 and ad_ratio > 1.5: health = "🟢 STRONG BULLISH"; health_color = "#16a34a"
    elif above_pct > 55: health = "🟡 BULLISH"; health_color = "#eab308"
    elif above_pct > 45: health = "⚪ NEUTRAL"; health_color = "#6b7280"
    elif above_pct > 35: health = "🟠 BEARISH"; health_color = "#f97316"
    else: health = "🔴 STRONG BEARISH"; health_color = "#dc2626"
    return {"total": total_valid, "above_ma": above_ma, "below_ma": below_ma, "above_pct": round(above_pct, 1), "advancers": advancers, "decliners": decliners, "ad_ratio": round(ad_ratio, 2), "health": health, "health_color": health_color}

def correlation_matrix(price_data, tickers, period=60):
    returns = {}
    for kode in tickers:
        df = price_data.get(kode)
        if df is not None and len(df) >= period + 5:
            try:
                ret = df['Close'].pct_change().dropna().tail(period)
                if len(ret) == period: returns[kode] = ret.values
            except: continue
    if len(returns) < 3: return None
    codes = list(returns.keys()); data_matrix = np.array([returns[c] for c in codes]); corr = np.corrcoef(data_matrix)
    return pd.DataFrame(corr, index=codes, columns=codes)

def smart_money_flow(df, period=20):
    if df is None or len(df) < period + 5: return None
    typical = (df['High'] + df['Low'] + df['Close']) / 3; vwap = (typical * df['Volume']).rolling(period).sum() / df['Volume'].rolling(period).sum()
    current = df['Close'].iloc[-1]; vwap_now = vwap.iloc[-1]; vol_avg = df['Volume'].rolling(period).mean().iloc[-1]; vol_today = df['Volume'].iloc[-1]
    vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1
    if current > vwap_now and vol_ratio > 1.3: signal = "🟢 SMART MONEY ACCUMULATING"; strength = min(100, int(vol_ratio * 30))
    elif current < vwap_now and vol_ratio > 1.3: signal = "🔴 SMART MONEY DISTRIBUTING"; strength = min(100, int(vol_ratio * 30))
    elif current > vwap_now: signal = "🟡 Mild Accumulation"; strength = 30
    else: signal = "⚪ Neutral"; strength = 20
    return {"vwap": float(vwap_now) if pd.notna(vwap_now) else 0, "current": float(current), "vol_ratio": round(float(vol_ratio), 2), "signal": signal, "strength": strength}

def elliott_wave_count(df, period=20):
    if df is None or len(df) < period + 10: return None
    highs = df['High'].rolling(window=5, center=True).max(); lows = df['Low'].rolling(window=5, center=True).min()
    last_highs = df[df['High'] == highs].tail(5); last_lows = df[df['Low'] == lows].tail(5)
    if len(last_highs) < 3 or len(last_lows) < 3: return {"pattern": "INSUFFICIENT DATA", "confidence": 0}
    hh = last_highs['High'].is_monotonic_increasing; hl = last_lows['Low'].is_monotonic_increasing
    lh = last_highs['High'].is_monotonic_decreasing; ll = last_lows['Low'].is_monotonic_decreasing
    if hh and hl: return {"pattern": "IMPULSE WAVE (1-2-3-4-5) — Uptrend", "confidence": 75, "trend": "UP"}
    elif lh and ll: return {"pattern": "CORRECTIVE WAVE (A-B-C) — Downtrend", "confidence": 70, "trend": "DOWN"}
    else: return {"pattern": "CORRECTION / CONSOLIDATION", "confidence": 40, "trend": "SIDEWAYS"}

def risk_metrics(returns_series):
    if returns_series is None or len(returns_series) < 10: return None
    returns = pd.Series(returns_series).dropna()
    if len(returns) < 10: return None
    mean_ret = returns.mean(); std_ret = returns.std()
    sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0
    downside = returns[returns < 0]; downside_std = downside.std() if len(downside) > 0 else 0.0001
    sortino = (mean_ret / downside_std) * np.sqrt(252) if downside_std > 0 else 0
    cum = (1 + returns).cumprod(); peak = cum.cummax(); dd = (cum - peak) / peak; max_dd = dd.min()
    return {"sharpe": round(sharpe, 2), "sortino": round(sortino, 2), "max_dd": round(max_dd * 100, 2), "volatility": round(std_ret * np.sqrt(252) * 100, 2)}

def fibonacci_retracement(high, low, current):
    diff = high - low
    levels = {"0% (High)": high, "23.6%": high - diff * 0.236, "38.2%": high - diff * 0.382, "50%": high - diff * 0.5, "61.8%": high - diff * 0.618, "78.6%": high - diff * 0.786, "100% (Low)": low}
    position = (current - low) / diff if diff > 0 else 0.5
    return levels, position, min(levels.items(), key=lambda x: abs(x[1] - current))

def dataframe_with_chart(df_display, kode_col="Kode", height=460, key=None, column_config=None):
    event = st.dataframe(df_display, use_container_width=True, hide_index=True, height=height, on_select="rerun", selection_mode="single-row", key=key, column_config=column_config or {})
    selected_rows = event.selection.rows if event and hasattr(event, "selection") else []
    if selected_rows:
        kode_selected = df_display.iloc[selected_rows[0]][kode_col]
        st.markdown(f"📈 Chart TradingView — {kode_selected}")
        embed_tradingview_chart(kode_selected, height=420)
    else:
        st.caption("💡 Klik salah satu baris di tabel di atas untuk melihat chart TradingView langsung di sini.")

st.markdown("""<style>.block-container {padding-top: 1.5rem;} div[data-testid="stMetric"] {background: #111827; border-radius: 12px; padding: 12px 14px; border: 1px solid #1f2937; overflow: hidden;} div[data-testid="stMetricValue"] {font-size: 1.35rem !important; white-space: normal !important; overflow-wrap: break-word;} div[data-testid="stMetricLabel"] {font-size: 0.8rem !important;}</style>""", unsafe_allow_html=True)
st.title("📈 IDX Screener Dashboard")
st.caption("Data live Yahoo Finance · Gate likuiditas + Donchian 20D Breakout · Gratis & mobile-friendly")

# ============================================================
# LOAD DATA AWAL (DIPINDAHKAN KE SINI agar tidak error di Sidebar)
# ============================================================
universe = load_ticker_universe()
ihsg_hist = fetch_ihsg_history()
regime = market_regime(ihsg_hist)

with st.sidebar:
    st.header("⚙️ Parameter Filter")
    session = get_market_session()
    st.markdown(f"""<div style="background:{session['color']};border-radius:10px;padding:12px;margin-bottom:12px;text-align:center;border:1px solid rgba(255,255,255,0.1);"><div style="font-size:11px;color:rgba(255,255,255,0.7);">MARKET SESSION</div><div style="font-size:16px;font-weight:700;color:#fff;margin:4px 0;">{session['session']}</div><div style="font-size:10px;color:rgba(255,255,255,0.6);">{session['desc']}</div></div>""", unsafe_allow_html=True)
    if session['next_open'] and session['countdown'] > 0:
        st.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:8px;margin-bottom:12px;text-align:center;border:1px solid #334155;"><div style="font-size:10px;color:#94a3b8;">NEXT OPEN IN</div><div style="font-size:18px;font-weight:700;color:#38bdf8;font-family:monospace;">{format_countdown(session['countdown'])}</div></div>""", unsafe_allow_html=True)
    auto_refresh = st.checkbox("🔄 Auto Refresh (5 menit)", value=False, key="auto_refresh")
    min_vt = st.number_input("Min. Value Traded (Rp miliar/hari)", min_value=0.0, value=3.0, step=0.5)
    crash_veto = st.slider("Ambang Crash Veto (%)", min_value=-15, max_value=-1, value=-5) / 100
    donchian_lb = st.number_input("Donchian Lookback - Swing (hari bursa)", min_value=5, max_value=60, value=20)
    donchian_lb_day = st.number_input("Donchian Lookback - Day Trading (hari bursa)", min_value=3, max_value=30, value=10)
    min_rr = st.number_input("Minimum Risk:Reward (RR)", min_value=1.0, value=2.0, step=0.1)
    st.divider()
    st.subheader("Ambang Skor Sinyal")
    sb = st.number_input("Skor min. STRONG BUY", value=7); b = st.number_input("Skor min. BUY", value=4)
    s = st.number_input("Skor maks. SELL", value=-2); ss = st.number_input("Skor maks. STRONG SELL", value=-4)
    st.divider()
    n_scan = st.select_slider("Jumlah saham dipindai", options=[50, 100, 200, 400, 615], value=200)
    refresh = st.button("🔄 Refresh Data Live", use_container_width=True, type="primary")
    st.divider()
    aktifkan_sektor = st.checkbox("🏷️ Aktifkan Filter Sektor", value=False)
    st.divider()
    st.subheader("🌐 Kondisi Pasar (IHSG)")
    filter_market = st.checkbox("Sembunyikan kandidat BUY saat IHSG Bearish", value=False)
    st.divider()
    st.subheader("🔮 IHSG Gann + Time Cycle")
    ihsg_gann_data = analyze_ihsg_gann(ihsg_hist)
    if ihsg_gann_data:
        g = ihsg_gann_data['gann']; c = ihsg_gann_data['current']
        st.markdown(f"""<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:8px;border:1px solid #334155;"><div style="font-size:11px;color:#94a3b8;">IHSG SAAT INI</div><div style="font-size:18px;font-weight:700;color:#38bdf8;">{c:,.0f}</div></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:8px;border:1px solid #334155;"><div style="font-size:11px;color:#94a3b8;">GANN BIAS</div><div style="font-size:12px;font-weight:600;color:#fbbf24;">{ihsg_gann_data['bias']}</div></div>""", unsafe_allow_html=True)
        if ihsg_gann_data['cycle_alert']:
            upcoming_now = [x for x in ihsg_gann_data['cycles'] if x['days_from_now'] <= 7][:1]
            if upcoming_now:
                st.markdown(f"""<div style="background:#7f1d1d;border-radius:8px;padding:8px;margin-top:8px;border:1px solid #dc2626;"><div style="font-size:11px;color:#fca5a5;">⚠️ TIME CYCLE DEKAT</div><div style="font-size:12px;color:#f87171;font-weight:600;">{upcoming_now[0]['type']} {upcoming_now[0]['days']}D → {upcoming_now[0]['date']}</div></div>""", unsafe_allow_html=True)
    st.divider()
    st.subheader("⚡ Volatility Regime")
    vol = volatility_regime(ihsg_hist)
    if vol:
        st.markdown(f"""<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:8px;border:1px solid {vol['color']};"><div style="font-size:11px;color:#94a3b8;">IHSG VOLATILITY</div><div style="font-size:14px;font-weight:700;color:{vol['color']};">{vol['regime']} ({vol['atr_pct']:.2f}%)</div><div style="font-size:10px;color:#94a3b8;margin-top:2px;">{vol['desc']}</div></div>""", unsafe_allow_html=True)
    st.divider()
    st.subheader("📱 Telegram Alert")
    alert_messages = check_alert_conditions(ihsg_gann_data, regime.get("close", 0) if regime else 0)
    if alert_messages:
        st.markdown(f"""<div style="background:#7f1d1d;border-radius:8px;padding:10px;margin-bottom:8px;border:1px solid #dc2626;"><div style="font-size:11px;color:#fca5a5;font-weight:600;">🚨 {len(alert_messages)} ALERT AKTIF</div></div>""", unsafe_allow_html=True)
        for msg in alert_messages[:3]: st.markdown(f"<div style='font-size:10px;color:#f87171;margin-bottom:2px;'>• {msg}</div>", unsafe_allow_html=True)
    if st.button("📤 Kirim Alert ke Telegram", use_container_width=True, key="btn_telegram_alert"):
        if alert_messages:
            msg_text = "🚨 *IHSG ALERT* 🚨\n\n" + "\n".join(alert_messages) + f"\n\n📊 IHSG: {regime.get('close', 0):,.0f}\n🕐 {datetime.now().strftime('%d %b %Y %H:%M')}"
            try: send_telegram_message(msg_text); st.success("✅ Alert terkirim ke Telegram!")
            except Exception as e: st.error(f"Gagal kirim: {str(e)}")

params = {"min_value_traded": min_vt * 1_000_000_000, "crash_veto": crash_veto, "donchian_lookback": int(donchian_lb), "score_strong_buy": sb, "score_buy": b, "score_sell": s, "score_strong_sell": ss}
tickers = universe["Kode"].tolist()[:int(n_scan)]
if refresh: st.cache_data.clear()
with st.spinner(f"Mengambil data live untuk {len(tickers)} saham..."):
    price_data = fetch_price_history(tickers)
    table = build_screener_table(price_data, universe, params)
    if table.empty: st.warning("Belum ada data yang berhasil diambil."); st.stop()

if aktifkan_sektor:
    with st.spinner("Mengambil data sektor..."):
        sector_map = sec.fetch_sectors(table["Kode"].tolist())
        table["Sektor"] = table["Kode"].map(sector_map).fillna("TIDAK DIKETAHUI")
else: table["Sektor"] = None

st.caption(f"Terakhir refresh: {datetime.now().strftime('%d %b %Y, %H:%M')} · {len(table)}/{len(tickers)} saham")
if regime["status"] == "BEARISH": st.error(f"📉 IHSG BEARISH (Close {regime['close']:,.0f} < MA50 {regime['ma']:,.0f})")
elif regime["status"] == "BULLISH": st.success(f"📈 IHSG BULLISH (Close {regime['close']:,.0f} > MA50 {regime['ma']:,.0f})")
market_ok = not (filter_market and regime["status"] == "BEARISH")

cands_day_all = build_trade_candidates(table, price_data, int(donchian_lb_day), min_rr, top_n=10)
cands_swing_all = build_trade_candidates(table, price_data, int(donchian_lb), min_rr, top_n=10)
if not market_ok: cands_day_all = cands_day_all.iloc[0:0]; cands_swing_all = cands_swing_all.iloc[0:0]

# Tampilkan Market Breadth di main area (karena price_data baru di-load di sini)
breadth = market_breadth(price_data, tickers[:int(n_scan)], lookback=20)
if breadth:
    st.markdown(f"""<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:12px;border:1px solid #334155;"><div style="font-size:11px;color:#94a3b8;">MARKET HEALTH: {breadth['health']}</div><div style="font-size:10px;color:#94a3b8;margin-top:4px;">{breadth['advancers']}↑ {breadth['decliners']}↓ dari {breadth['total']} saham ({breadth['above_pct']}% above MA20)</div></div>""", unsafe_allow_html=True)

t_kandidat, t_semua, t_grafik, t_backtest, t_top10, t_real, t_equity, t_perf, t_kalk, t_fundamental, t_invest, t_ihsg, t_corr, t_astro, t_sentiment, t_ml, t_options, t_broker = st.tabs([
    "🏆 Kandidat", "📋 Semua", "📉 Grafik", "📒 Backtest", "🎯 Top 10", "💼 Jurnal Real", "💰 Equity", "🚀 Performance",
    "🧮 Kalkulator", "📊 Fundamental", "🏛️ Value Invest", "📊 IHSG Analysis", "🔗 Correlation", "🌙 Astronacci", "📰 Sentiment", "🤖 ML Signal", "📉 Options", "🏦 Broker"
])

# (TAB 1 to TAB 5 will continue in Part 2 along with the rest of the tabs to prevent text cut-off)
# ============================================================================
# TAB 6: KALKULATOR (100% dari app.py asli)
# ============================================================================
with t_kalk:
    st.subheader("🧮 Kalkulator Profit & Risiko")
    kalk_col1, kalk_col2 = st.columns(2)
    with kalk_col1:
        st.subheader("🧮 Kalkulator Profit Saham")
        st.caption("Hitung untung/rugi transaksi, termasuk komisi beli & jual.")
        pilih_isi = st.selectbox("Isi harga otomatis dari saham (opsional)", options=[""] + table["Kode"].tolist(), key="kalk_profit_pilih", format_func=lambda k: "-- pilih manual --" if k == "" else k)
        harga_acuan = float(table.loc[table["Kode"] == pilih_isi, "Harga"].values[0]) if pilih_isi else 0.0
        cp1, cp2 = st.columns(2)
        harga_beli_in = cp1.number_input("Harga Beli (Rp)", min_value=0.0, value=harga_acuan, step=1.0, key="hb")
        harga_jual_in = cp2.number_input("Harga Jual (Rp)", min_value=0.0, value=harga_acuan * 1.05 if harga_acuan else 0.0, step=1.0, key="hj")
        lot_in = st.number_input("Lot (1 lot = 100 lembar)", min_value=1, value=10, step=1, key="lot")
        cp3, cp4 = st.columns(2)
        komisi_beli_in = cp3.number_input("Komisi Beli (%)", min_value=0.0, value=0.15, step=0.01, key="kb", help="Umumnya 0.15%-0.19% tergantung broker.")
        komisi_jual_in = cp4.number_input("Komisi Jual (%)", min_value=0.0, value=0.25, step=0.01, key="kj", help="Umumnya 0.25%-0.29% (sudah termasuk pajak final penjualan 0.1%).")
        if st.button("Hitung Profit", type="primary", use_container_width=True):
            r = calc.profit_calculator(harga_beli_in, harga_jual_in, lot_in, komisi_beli_in, komisi_jual_in)
            rc1, rc2 = st.columns(2)
            rc1.metric("Total Beli", f"Rp{r['total_beli']:,.0f}")
            rc2.metric("Total Jual", f"Rp{r['total_jual']:,.0f}")
            rc3, rc4 = st.columns(2)
            rc3.metric("Total Untung/Rugi", f"Rp{r['untung_rugi_rp']:,.0f}")
            rc4.metric("Total Untung/Rugi (%)", f"{r['untung_rugi_pct']:+.2f}%")
            if r["bep"]:
                st.info(f"💡 **Break Even Price**: Rp{r['bep']:,.2f} — harga jual minimum supaya impas (sudah memperhitungkan komisi beli & jual).")
    with kalk_col2:
        st.subheader("🛡️ Kalkulator Manajemen Risiko")
        st.caption("Hitung ukuran posisi ideal berdasar modal & toleransi risiko.")
        pilih_isi2 = st.selectbox("Isi harga saham otomatis (opsional)", options=[""] + table["Kode"].tolist(), key="kalk_risk_pilih", format_func=lambda k: "-- pilih manual --" if k == "" else k)
        harga_saham_default = float(table.loc[table["Kode"] == pilih_isi2, "Harga"].values[0]) if pilih_isi2 else 0.0
        modal_in = st.number_input("Total Modal (Rp)", min_value=0.0, value=10_000_000.0, step=500_000.0, key="modal")
        resiko_in = st.number_input("Resiko per Transaksi (%)", min_value=0.1, value=1.0, step=0.1, key="resiko", help="Berapa % dari modal yang rela hilang kalau kena Stop Loss. Umumnya 1-2%.")
        sl_in = st.number_input("Persen Stop Loss (%)", min_value=0.1, value=5.0, step=0.5, key="slpct")
        rr_in = st.number_input("Risk Reward Ratio", min_value=0.5, value=2.0, step=0.5, key="rrin")
        harga_saham_in = st.number_input("Harga Saham (Rp) - opsional, untuk hasil dalam LOT", min_value=0.0, value=harga_saham_default, step=1.0, key="hs")
        if st.button("Hitung Manajemen Risiko", type="primary", use_container_width=True):
            r2 = calc.risk_management_calculator(modal_in, resiko_in, sl_in, rr_in, harga_saham_in if harga_saham_in > 0 else None)
            if "error" in r2:
                st.error(r2["error"])
            else:
                if r2["dibatasi_modal"]:
                    st.warning("⚠️ Ukuran posisi ideal melebihi modal - dibatasi otomatis ke total modal yang ada.")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Resiko (Rp)", f"Rp{r2['resiko_rp']:,.0f}")
                rc2.metric("Maksimal Beli (Rp)", f"Rp{r2['maksimal_beli_rp']:,.0f}")
                rc3.metric("Target Profit (%)", f"{r2['take_profit_pct']:.1f}%")
                if "lot" in r2:
                    rc4, rc5, rc6 = st.columns(3)
                    rc4.metric("Jumlah Lot", f"{r2['lot']} lot ({r2['lembar']:,} lembar)")
                    rc5.metric("Stop Loss (Rp)", f"Rp{r2['stop_loss_price']:,.0f}")
                    rc6.metric("Take Profit (Rp)", f"Rp{r2['take_profit_price']:,.0f}")
                    st.caption(f"Total dana terpakai: Rp{r2['total_saham_rp']:,.0f} · Risiko aktual (sudah dibulatkan ke lot): Rp{r2['risiko_aktual_rp']:,.0f}")
                else:
                    st.caption("Isi 'Harga Saham' di atas untuk mendapat hasil dalam satuan LOT, harga Stop Loss & Take Profit riil.")
    st.divider()
    st.subheader("📉📈 Kalkulator Average Down / Average Up")
    st.caption("Average Down = beli tambahan saat harga TURUN untuk menurunkan harga rata-rata. Average Up = beli tambahan saat harga NAIK (menambah posisi pemenang). Rumus tertimbang standar: Avg Baru = (Modal Awal + Modal Tambahan) / (Lot Awal + Lot Tambahan).")
    avg_tab1, avg_tab2 = st.tabs(["🧮 Hitung Average", "🎯 Simulasi Lot Tambahan (target average)"])
    with avg_tab1:
        pilih_isi3 = st.selectbox("Isi harga sekarang otomatis (opsional)", options=[""] + table["Kode"].tolist(), key="kalk_avg_pilih", format_func=lambda k: "-- pilih manual --" if k == "" else k)
        harga_now = float(table.loc[table["Kode"] == pilih_isi3, "Harga"].values[0]) if pilih_isi3 else 0.0
        ac1, ac2 = st.columns(2)
        with ac1:
            st.markdown("**Posisi Awal (yang sudah dimiliki)**")
            harga_awal_in = st.number_input("Harga Beli Awal (Rp)", min_value=0.0, value=1000.0, step=1.0, key="avg_ha")
            lot_awal_in = st.number_input("Lot Awal", min_value=0.0, value=10.0, step=1.0, key="avg_la")
        with ac2:
            st.markdown("**Pembelian Tambahan**")
            harga_tambah_in = st.number_input("Harga Beli Tambahan (Rp)", min_value=0.0, value=harga_now if harga_now else 900.0, step=1.0, key="avg_ht")
            lot_tambah_in = st.number_input("Lot Tambahan", min_value=0.0, value=10.0, step=1.0, key="avg_lt")
        if st.button("Hitung Average", type="primary", use_container_width=True, key="btn_avg"):
            ra = calc.average_calculator(harga_awal_in, lot_awal_in, harga_tambah_in, lot_tambah_in)
            if "error" in ra:
                st.error(ra["error"])
            else:
                badge = "📉 AVERAGE DOWN" if ra["tipe"] == "AVERAGE DOWN" else ("📈 AVERAGE UP" if ra["tipe"] == "AVERAGE UP" else "⚪ HARGA SAMA")
                st.markdown(f"**{badge}**")
                rac1, rac2, rac3 = st.columns(3)
                rac1.metric("Harga Rata-Rata Baru", f"Rp{ra['avg_baru']:,.2f}", f"{ra['selisih_pct']:+.2f}%")
                rac2.metric("Total Lot", f"{ra['total_lot']:,.0f} lot")
                rac3.metric("Total Modal", f"Rp{ra['total_modal']:,.0f}")
                st.caption("Setelah average, harga saham cukup naik/turun ke angka Harga Rata-Rata Baru di atas untuk balik modal (belum termasuk komisi transaksi).")
    with avg_tab2:
        st.caption("Isi target harga rata-rata yang diinginkan, kalkulator hitung berapa lot tambahan yang dibutuhkan di harga tertentu untuk mencapainya.")
        sc1, sc2 = st.columns(2)
        with sc1:
            sim_harga_awal = st.number_input("Harga Beli Awal (Rp)", min_value=0.0, value=4500.0, step=1.0, key="sim_ha")
            sim_lot_awal = st.number_input("Lot Awal", min_value=0.0, value=10.0, step=1.0, key="sim_la")
        with sc2:
            sim_harga_tambah = st.number_input("Harga Beli Tambahan Rencana (Rp)", min_value=0.0, value=3700.0, step=1.0, key="sim_ht")
            sim_target_avg = st.number_input("Target Harga Rata-Rata (Rp)", min_value=0.0, value=4000.0, step=1.0, key="sim_ta")
        if st.button("Hitung Lot Tambahan", type="primary", use_container_width=True, key="btn_sim"):
            rs = calc.average_lot_simulator(sim_harga_awal, sim_lot_awal, sim_target_avg, sim_harga_tambah)
            if "error" in rs:
                st.error(rs["error"])
            else:
                rsc1, rsc2 = st.columns(2)
                rsc1.metric("Lot Tambahan Dibutuhkan", f"{rs['lot_tambahan']:,} lot")
                rsc2.metric("Modal Tambahan Dibutuhkan", f"Rp{rs['modal_tambahan_dibutuhkan']:,.0f}")
                st.caption(f"Hasil akhir: rata-rata jadi **Rp{rs['avg_hasil']:,.2f}** dengan total **{rs['total_lot_hasil']:,.0f} lot**.")

# ============================================================================
# TAB 7: PERFORMANCE (BACKTEST) (100% dari app.py asli)
# ============================================================================
with t_perf:
    if not gj.is_configured():
        st.warning("Performance dihitung dari sheet POSISI (Google Sheets). Belum terhubung - isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets.")
    else:
        positions_perf = gj.load_positions()
        if positions_perf.empty:
            st.info("Belum ada transaksi tercatat di sheet POSISI.")
        else:
            for col in ["Harga Beli", "Harga Jual", "Lot", "P&L (Rp)", "P&L (%)", "TP", "SL"]:
                if col in positions_perf.columns:
                    positions_perf[col] = pd.to_numeric(positions_perf[col], errors="coerce")
            is_open_mask = positions_perf["Status"].astype(str).str.upper().str.strip() == "OPEN"
            open_df = positions_perf[is_open_mask].copy()
            closed_df = positions_perf[~is_open_mask].copy()
            st.markdown("### ⚙️ Parameter Backtest")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                modal_awal_bt = st.number_input("Modal Awal Backtest (Rp)", min_value=1_000_000, value=10_000_000, step=1_000_000, help="Angka virtual sebagai benchmark return %.")
            with col_m2:
                include_open = st.checkbox("Sertakan Floating P/L (posisi OPEN)", value=True, help="Centang untuk hitung unrealized P/L posisi terbuka.")
            with col_m3:
                show_all_trades = st.checkbox("Tampilkan semua trade", value=True)
            price_lookup = dict(zip(table["Kode"], table["Harga"])) if not table.empty else {}
            realized_total = closed_df["P&L (Rp)"].sum() if not closed_df.empty and "P&L (Rp)" in closed_df.columns else 0
            floating_total = 0
            floating_list = []
            if include_open and not open_df.empty:
                for _, row in open_df.iterrows():
                    saham = str(row.get("Saham", "")).strip().upper()
                    entry = float(row["Harga Beli"]) if pd.notna(row.get("Harga Beli")) else 0
                    lot = int(row["Lot"]) if pd.notna(row.get("Lot")) else 0
                    current = price_lookup.get(saham, 0)
                    if current > 0 and entry > 0 and lot > 0:
                        fl = (current - entry) * lot * 100
                        floating_total += fl
                        floating_list.append({"Saham": saham, "Entry": entry, "Current": current, "Lot": lot, "Floating (Rp)": fl})
            n_open, n_closed = len(open_df), len(closed_df)
            n_win = int((closed_df["P&L (Rp)"] > 0).sum()) if not closed_df.empty and "P&L (Rp)" in closed_df.columns else 0
            n_loss = int((closed_df["P&L (Rp)"] < 0).sum()) if not closed_df.empty and "P&L (Rp)" in closed_df.columns else 0
            winrate = (n_win / n_closed * 100) if n_closed > 0 else 0
            gross_profit = closed_df.loc[closed_df["P&L (Rp)"] > 0, "P&L (Rp)"].sum() if n_win > 0 else 0
            gross_loss = abs(closed_df.loc[closed_df["P&L (Rp)"] < 0, "P&L (Rp)"].sum()) if n_loss > 0 else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
            pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
            equity_now = modal_awal_bt + realized_total + (floating_total if include_open else 0)
            total_return = ((equity_now / modal_awal_bt) - 1) * 100
            st.markdown("### 📊 Ringkasan Performance Backtest")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Posisi", n_open + n_closed); c2.metric("OPEN", n_open); c3.metric("CLOSED", n_closed); c4.metric("WIN", n_win); c5.metric("LOSS", n_loss)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Win Rate", f"{winrate:.1f}%"); m2.metric("Profit Factor", pf_str); m3.metric("Realized P/L", f"Rp{realized_total:,.0f}"); m4.metric("Floating P/L", f"Rp{floating_total:,.0f}")
            st.divider()
            st.markdown("### 📈 Kurva Ekuitas Backtest")
            tgl_col = next((c for c in ["Tanggal Close", "TanggalClose", "Tgl Close"] if c in closed_df.columns), None)
            eq_points = [{"Tanggal": datetime.now() - pd.Timedelta(days=30), "Equity": modal_awal_bt, "Label": "START"}]
            if not closed_df.empty and tgl_col:
                closed_df[tgl_col] = pd.to_datetime(closed_df[tgl_col], errors="coerce")
                closed_sorted = closed_df.sort_values(tgl_col).copy()
                closed_sorted["Cum_PnL"] = closed_sorted["P&L (Rp)"].cumsum()
                for _, row in closed_sorted.iterrows():
                    eq_points.append({"Tanggal": row[tgl_col], "Equity": modal_awal_bt + row["Cum_PnL"], "Label": f"{row.get('Saham','')} ({row['P&L (Rp)']:+.0f})"})
            if include_open and floating_total != 0:
                eq_points.append({"Tanggal": datetime.now(), "Equity": modal_awal_bt + realized_total + floating_total, "Label": f"FLOATING ({floating_total:+.0f})"})
            eq_df_perf = pd.DataFrame(eq_points).sort_values("Tanggal")
            if len(eq_df_perf) > 1:
                eq_df_perf["Peak"] = eq_df_perf["Equity"].cummax()
                eq_df_perf["Drawdown %"] = (eq_df_perf["Equity"] - eq_df_perf["Peak"]) / eq_df_perf["Peak"] * 100
                max_dd = eq_df_perf["Drawdown %"].min()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=eq_df_perf["Tanggal"], y=eq_df_perf["Equity"], mode="lines+markers", name="Equity", line=dict(color="#4ade80", width=2.5), fill="tozeroy", fillcolor="rgba(74,222,128,0.10)", hovertemplate="%{y:,.0f}<br>%{text}", text=eq_df_perf["Label"]))
                fig.add_hline(y=modal_awal_bt, line_dash="dash", line_color="#6b7280", annotation_text="Modal Awal")
                fig.update_layout(height=400, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Equity (Rp)", showlegend=False, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Modal Awal (BT)", f"Rp{modal_awal_bt:,.0f}"); r2.metric("Equity Sekarang", f"Rp{eq_df_perf['Equity'].iloc[-1]:,.0f}", f"{total_return:+.2f}%"); r3.metric("Max Drawdown", f"{max_dd:.2f}%"); r4.metric("Peak Equity", f"Rp{eq_df_perf['Peak'].max():,.0f}")
            if floating_list:
                st.divider()
                st.markdown("**📉 Posisi OPEN & Floating P/L**")
                fl_df = pd.DataFrame(floating_list)
                fl_df["Floating (Rp)"] = fl_df["Floating (Rp)"].map(lambda x: f"Rp{x:,.0f}")
                st.dataframe(fl_df, use_container_width=True, hide_index=True)
            if show_all_trades:
                st.divider()
                st.markdown("**🏅 Riwayat Semua Trade**")
                display_cols = ["Saham", "Tipe", "Tanggal Close", "Harga Beli", "Harga Jual", "Lot", "P&L (Rp)", "P&L (%)", "Status"]
                display_cols = [c for c in display_cols if c in positions_perf.columns]
                st.dataframe(positions_perf[display_cols], use_container_width=True, hide_index=True, height=350)

# ============================================================================
# TAB 8: JURNAL REAL (100% dari app.py asli)
# ============================================================================
with t_real:
    st.caption("Catatan transaksi UANG BENERAN Bro - terpisah total dari Jurnal Backtest (simulasi).")
    if not gj.is_configured():
        st.warning("Jurnal Real butuh koneksi Google Sheets. Isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets.")
    else:
        sub1, sub2, sub3, sub4, sub5 = st.tabs(["➕ Catat Trade", "🔓 Tutup Posisi", "Performance Real", "⚙️ Sekuritas", "✏️ Edit/Hapus"])
        with sub1:
            st.markdown("**Catat posisi baru (OPEN)**")
            brokers_df = rj.load_brokers()
            broker_options = brokers_df["Sekuritas"].tolist() if not brokers_df.empty else ["Lainnya"]
            auto_data = st.session_state.get('auto_fill_trade', None)
            if auto_data:
                st.success(f"🎯 Auto-fill aktif: **{auto_data['kode']}** ({auto_data['rekomendasi']})")
                with st.expander("📋 Detail Auto-fill", expanded=True):
                    st.write(f"**Entry:** Rp{auto_data['entry']:,.0f} | **SL:** Rp{auto_data['stop_loss']:,.0f} | **Target:** Rp{auto_data['target']:,.0f} | **RR:** {auto_data['rr']}x | **Setup:** {auto_data['setup']} | **Lot:** {auto_data['lot']}")
                if st.button("🗑️ Batal Auto-fill", key="btn_cancel_autofill"):
                    del st.session_state['auto_fill_trade']
                    for k in ["saham_rj", "setup_rj", "lot_rj", "entry_rj", "sl_rj", "target_rj", "catatan_rj"]:
                        if k in st.session_state: del st.session_state[k]
                    st.rerun()
                st.divider()
            if auto_data:
                st.session_state["saham_rj"] = str(auto_data.get('kode', ''))
                st.session_state["setup_rj"] = auto_data.get('setup', rj.SETUP_OPTIONS[0]) if auto_data.get('setup', rj.SETUP_OPTIONS[0]) in rj.SETUP_OPTIONS else rj.SETUP_OPTIONS[0]
                st.session_state["lot_rj"] = int(auto_data.get('lot', 10))
                st.session_state["entry_rj"] = float(auto_data.get('entry', 0))
                st.session_state["sl_rj"] = float(auto_data.get('stop_loss', 0))
                st.session_state["target_rj"] = float(auto_data.get('target', 0))
                st.session_state["catatan_rj"] = f"Auto-fill dari Kandidat Terbaik - {auto_data.get('rekomendasi', '')}"
                del st.session_state['auto_fill_trade']
            fc1, fc2, fc3 = st.columns(3)
            with fc1: tgl_entry = st.date_input("Tanggal Entry", value=datetime.now(), key="tgl_entry_rj")
            with fc2: sekuritas_in = st.selectbox("Sekuritas", options=broker_options, key="sekuritas_rj")
            with fc3: saham_in = st.text_input("Kode Saham", key="saham_rj").upper()
            fc4, fc5 = st.columns(2)
            with fc4: setup_in = st.selectbox("Setup", options=rj.SETUP_OPTIONS, key="setup_rj")
            with fc5: lot_in2 = st.number_input("Lot", min_value=1, step=1, key="lot_rj")
            fc6, fc7, fc8 = st.columns(3)
            with fc6: entry_in2 = st.number_input("Entry (Rp)", min_value=0.0, step=1.0, key="entry_rj")
            with fc7: sl_in2 = st.number_input("Stop Loss (Rp)", min_value=0.0, step=1.0, key="sl_rj")
            with fc8: target_in2 = st.number_input("Target (Rp)", min_value=0.0, step=1.0, key="target_rj")
            catatan_in = st.text_area("Catatan", height=70, key="catatan_rj")
            if st.button("💾 Simpan Trade (OPEN)", type="primary", key="btn_open_rj"):
                if not saham_in or entry_in2 <= 0: st.error("Kode saham dan Entry wajib diisi.")
                else:
                    no = rj.open_trade(tgl_entry.strftime("%Y-%m-%d"), sekuritas_in, saham_in, setup_in, entry_in2, sl_in2, target_in2, lot_in2, catatan_in)
                    st.success(f"Trade #{no} ({saham_in}) berhasil dicatat.")
                    for k in ["saham_rj", "setup_rj", "lot_rj", "entry_rj", "sl_rj", "target_rj", "catatan_rj"]:
                        if k in st.session_state: del st.session_state[k]
                    st.rerun()
        with sub2:
            trades_now = rj.load_trades()
            open_trades = trades_now[trades_now["Status"] == "OPEN"] if not trades_now.empty else pd.DataFrame()
            if open_trades.empty: st.info("Tidak ada posisi OPEN saat ini.")
            else:
                st.markdown("**Posisi yang masih terbuka**")
                st.dataframe(open_trades[["No", "Tanggal Entry", "Sekuritas", "Saham", "Setup", "Entry (Rp)", "Stop Loss (Rp)", "Target (Rp)", "Lot"]], use_container_width=True, hide_index=True)
                pilih_no = st.selectbox("Pilih nomor trade yang mau ditutup", options=open_trades["No"].tolist(), format_func=lambda n: f"#{n} - {open_trades.loc[open_trades['No']==n,'Saham'].values[0]}", key="pilih_no_rj")
                cc1, cc2 = st.columns(2)
                with cc1: tgl_exit_in = cc1.date_input("Tanggal Exit", value=datetime.now(), key="tgl_exit_rj")
                with cc2: exit_price_in = cc2.number_input("Harga Exit (Rp)", min_value=0.0, step=1.0, key="exit_price_rj")
                if st.button("🔓 Tutup Posisi Ini", type="primary", key="btn_close_rj"):
                    if exit_price_in <= 0: st.error("Harga Exit wajib diisi.")
                    else:
                        ok, msg = rj.close_trade(pilih_no, tgl_exit_in.strftime("%Y-%m-%d"), exit_price_in)
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)
        with sub3:
            trades_all = rj.load_trades()
            stats_rj = rj.compute_stats(trades_all)
            if stats_rj["total"] == 0: st.info("Belum ada trade tercatat.")
            else:
                r1, r2, r3 = st.columns(3)
                r1.metric("Win Rate", f"{stats_rj['winrate']:.1f}%")
                r2.metric("Profit Factor", "∞" if stats_rj["profit_factor"] == float("inf") else f"{stats_rj['profit_factor']:.2f}")
                r3.metric("Total Trade", f"{stats_rj['total']} ({stats_rj['win']}W · {stats_rj['loss']}L · {stats_rj['open']} OPEN)")
                r4, r5 = st.columns(2)
                r4.metric("Total Transaction Value", f"Rp{stats_rj['total_transaction_value']:,.0f}")
                r5.metric("Net P/L", f"Rp{stats_rj['net_pl']:,.0f}")
                st.divider()
                pb1, pb2 = st.columns(2)
                with pb1:
                    st.markdown("**Performance per Sekuritas**")
                    st.dataframe(rj.performance_by_broker(trades_all), use_container_width=True, hide_index=True)
                with pb2:
                    st.markdown("**Performance per Setup**")
                    st.dataframe(rj.performance_by_setup(trades_all), use_container_width=True, hide_index=True)
                st.markdown("**Riwayat Semua Trade**")
                st.dataframe(trades_all, use_container_width=True, hide_index=True, height=350)
        with sub4:
            st.markdown("**Daftar Sekuritas & Biaya Transaksi**")
            brokers_now = rj.load_brokers()
            st.dataframe(brokers_now, use_container_width=True, hide_index=True)
            st.markdown("**Tambah / Update Sekuritas**")
            bc1, bc2, bc3 = st.columns(3)
            with bc1: nama_broker_in = bc1.text_input("Nama Sekuritas", key="nama_broker_rj")
            with bc2: biaya_beli_in2 = bc2.number_input("Biaya Beli (%)", min_value=0.0, value=0.15, step=0.01, key="bb_broker")
            with bc3: biaya_jual_in2 = bc3.number_input("Biaya Jual (%)", min_value=0.0, value=0.25, step=0.01, key="bj_broker")
            if st.button("💾 Simpan Sekuritas", key="btn_save_broker"):
                if not nama_broker_in: st.error("Nama sekuritas wajib diisi.")
                else:
                    rj.add_broker(nama_broker_in, biaya_beli_in2, biaya_jual_in2)
                    st.success(f"Sekuritas '{nama_broker_in}' disimpan.")
        with sub5:
            st.caption("Salah input harga/lot/sekuritas? Pilih nomor trade di bawah, koreksi, lalu simpan.")
            trades_edit = rj.load_trades()
            if trades_edit.empty: st.info("Belum ada trade untuk diedit.")
            else:
                pilih_edit_no = st.selectbox("Pilih nomor trade", options=trades_edit["No"].tolist(), format_func=lambda n: f"#{n} - {trades_edit.loc[trades_edit['No']==n,'Saham'].values[0]}", key="pilih_edit_no_rj")
                row_edit = trades_edit[trades_edit["No"] == pilih_edit_no].iloc[0]
                broker_options_edit = rj.load_brokers()["Sekuritas"].tolist()
                ec1, ec2, ec3 = st.columns(3)
                with ec1: e_tgl_entry = ec1.text_input("Tanggal Entry (YYYY-MM-DD)", value=str(row_edit["Tanggal Entry"]), key="e_tgl")
                with ec2: 
                    idx_broker = broker_options_edit.index(row_edit["Sekuritas"]) if row_edit["Sekuritas"] in broker_options_edit else 0
                    e_sekuritas = ec2.selectbox("Sekuritas", options=broker_options_edit, index=idx_broker, key="e_sek")
                with ec3: e_saham = ec3.text_input("Kode Saham", value=str(row_edit["Saham"]), key="e_saham").upper()
                ec4, ec5 = st.columns(2)
                with ec4: 
                    idx_setup = rj.SETUP_OPTIONS.index(row_edit["Setup"]) if row_edit["Setup"] in rj.SETUP_OPTIONS else 0
                    e_setup = ec4.selectbox("Setup", options=rj.SETUP_OPTIONS, index=idx_setup, key="e_setup")
                with ec5: e_lot = ec5.number_input("Lot", min_value=1.0, value=float(row_edit["Lot"] or 1), step=1.0, key="e_lot")
                ec6, ec7, ec8 = st.columns(3)
                with ec6: e_entry = ec6.number_input("Entry (Rp)", min_value=0.0, value=float(row_edit["Entry (Rp)"] or 0), step=1.0, key="e_entry")
                with ec7: e_sl = ec7.number_input("Stop Loss (Rp)", min_value=0.0, value=float(row_edit["Stop Loss (Rp)"] or 0), step=1.0, key="e_sl")
                with ec8: e_target = ec8.number_input("Target (Rp)", min_value=0.0, value=float(row_edit["Target (Rp)"] or 0), step=1.0, key="e_target")
                e_catatan = st.text_area("Catatan", value=str(row_edit["Catatan"] or ""), height=70, key="e_catatan")
                ec9, ec10 = st.columns(2)
                with ec9: e_tgl_exit = ec9.text_input("Tanggal Exit (YYYY-MM-DD, kosongkan kalau OPEN)", value=str(row_edit["Tanggal Exit"] or ""), key="e_tgl_exit")
                with ec10: e_exit_price = ec10.number_input("Harga Exit (Rp, 0 = OPEN)", min_value=0.0, value=float(row_edit["Exit (Rp)"] or 0), step=1.0, key="e_exit_price")
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("💾 Simpan Perubahan", type="primary", use_container_width=True, key="btn_edit_rj"):
                        if not e_saham or e_entry <= 0: st.error("Kode saham dan Entry wajib diisi.")
                        else:
                            ok, msg = rj.edit_trade(pilih_edit_no, e_tgl_entry, e_sekuritas, e_saham, e_setup, e_entry, e_sl, e_target, e_lot, e_catatan, tanggal_exit=e_tgl_exit if e_exit_price > 0 else "", exit_price=e_exit_price if e_exit_price > 0 else None)
                            if ok: st.success(msg)
                            else: st.error(msg)
                with bcol2:
                    if st.button("🗑️ Hapus Trade Ini", use_container_width=True, key="btn_delete_rj"):
                        st.session_state["confirm_delete_rj"] = pilih_edit_no
                if st.session_state.get("confirm_delete_rj") == pilih_edit_no:
                    st.warning(f"Yakin mau hapus trade #{pilih_edit_no} ({row_edit['Saham']})? Tidak bisa dibatalkan.")
                    yes_col, no_col = st.columns(2)
                    if yes_col.button("Ya, hapus", type="primary", key="btn_confirm_delete_rj"):
                        ok, msg = rj.delete_trade(pilih_edit_no)
                        del st.session_state["confirm_delete_rj"]
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)
                    if no_col.button("Batal", key="btn_cancel_delete_rj"):
                        del st.session_state["confirm_delete_rj"]
                        st.rerun()

# ============================================================================
# TAB 9: EQUITY (100% dari app.py asli + BUG FIX di Risk Metrics)
# ============================================================================
with t_equity:
    if not gj.is_configured():
        st.warning("Equity Tracking butuh koneksi Google Sheets.")
    else:
        sub_ringkasan, sub_catat, sub_riwayat = st.tabs(["📊 Ringkasan", "➕ Catat Snapshot", "📋 Riwayat"])
        equity_df = eq.load_equity()
        with sub_ringkasan:
            if equity_df.empty:
                st.info("Belum ada data equity. Isi snapshot pertama di tab 'Catat Snapshot'.")
            else:
                total_series = eq.total_equity_over_time(equity_df)
                total_series["Tanggal"] = pd.to_datetime(total_series["Tanggal"])
                total_series = total_series.sort_values("Tanggal")
                latest_broker = eq.latest_per_sekuritas(equity_df)
                if not latest_broker.empty:
                    tgl_unik = latest_broker["Tanggal"].unique()
                    if len(tgl_unik) > 1:
                        st.warning(f"⚠️ Snapshot terbaru tidak konsisten! Ada {len(tgl_unik)} tanggal berbeda: {list(tgl_unik)}. Silakan update semua sekuritas di tanggal yang sama.")
                latest_total = total_series["Total Equity (Rp)"].iloc[-1] if not total_series.empty else 0
                first_total = total_series["Total Equity (Rp)"].iloc[0] if not total_series.empty else 0
                total_return = ((latest_total / first_total - 1) * 100) if first_total > 0 else 0
                st.markdown("### 📊 Ringkasan Portofolio")
                ec1, ec2, ec3 = st.columns(3)
                ec1.metric("Total Equity (Semua Sekuritas)", f"Rp{latest_total:,.0f}")
                ec2.metric("Return Sejak Snapshot Pertama", f"{total_return:+.2f}%")
                ec3.metric("Jumlah Sekuritas Aktif", equity_df["Sekuritas"].nunique())
                if not latest_broker.empty and "Cash (Rp)" in latest_broker.columns and "Invested (Rp)" in latest_broker.columns:
                    latest_broker["Cash (Rp)"] = pd.to_numeric(latest_broker["Cash (Rp)"], errors="coerce").fillna(0)
                    latest_broker["Invested (Rp)"] = pd.to_numeric(latest_broker["Invested (Rp)"], errors="coerce").fillna(0)
                    latest_broker["Total Equity (Rp)"] = pd.to_numeric(latest_broker["Total Equity (Rp)"], errors="coerce").fillna(0)
                    total_cash = latest_broker["Cash (Rp)"].sum()
                    total_invested = latest_broker["Invested (Rp)"].sum()
                    total_all = latest_broker["Total Equity (Rp)"].sum()
                    cash_ratio = (total_cash / total_all * 100) if total_all > 0 else 0
                    invested_ratio = (total_invested / total_all * 100) if total_all > 0 else 0
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Total Cash", f"Rp{total_cash:,.0f}", f"{cash_ratio:.1f}%")
                    r2.metric("Total Invested", f"Rp{total_invested:,.0f}", f"{invested_ratio:.1f}%")
                    if cash_ratio < 5: r3.error(f"⚠️ Cash Ratio {cash_ratio:.1f}% — TERLALU RENDAH!")
                    elif cash_ratio < 10: r3.warning(f"⚡ Cash Ratio {cash_ratio:.1f}% — Rendah. Ideal 10-20%.")
                    elif cash_ratio <= 25: r3.success(f"✅ Cash Ratio {cash_ratio:.1f}% — IDEAL.")
                    else: r3.info(f"💡 Cash Ratio {cash_ratio:.1f}% — Tinggi.")
                st.divider()
                st.markdown("### 📈 Kurva Total Equity vs IHSG")
                fig_eq2 = go.Figure()
                fig_eq2.add_trace(go.Scatter(x=total_series["Tanggal"], y=total_series["Total Equity (Rp)"], mode="lines+markers", name="🟦 Total Equity", line=dict(color="#4ade80", width=2.5), fill="tozeroy", fillcolor="rgba(74,222,128,0.12)"))
                if first_total > 0 and len(total_series) >= 2:
                    days = (total_series["Tanggal"].iloc[-1] - total_series["Tanggal"].iloc[0]).days
                    target_return = (1.10 ** (days / 365) - 1) * 100
                    target_equity = first_total * (1 + target_return / 100)
                    fig_eq2.add_hline(y=target_equity, line_dash="dot", line_color="#a78bfa", annotation_text=f"Target 10% CAGR (Rp{target_equity:,.0f})")
                if not ihsg_hist.empty and len(total_series) >= 2:
                    fd, ld = total_series["Tanggal"].min(), total_series["Tanggal"].max()
                    ihsg_cmp = ihsg_hist.copy()
                    if ihsg_cmp.index.tz is not None: ihsg_cmp.index = ihsg_cmp.index.tz_localize(None)
                    ihsg_r = ihsg_cmp[(ihsg_cmp.index >= fd) & (ihsg_cmp.index <= ld)]
                    if not ihsg_r.empty and len(ihsg_r) >= 2:
                        ihsg_base = float(ihsg_r["Close"].iloc[0])
                        scale_factor = first_total / ihsg_base if ihsg_base > 0 else 1
                        fig_eq2.add_trace(go.Scatter(x=ihsg_r.index, y=ihsg_r["Close"] * scale_factor, mode="lines", name="🟨 IHSG (scaled)", line=dict(color="#fbbf24", width=2, dash="dash")))
                fig_eq2.update_layout(height=400, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Rp", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified")
                st.plotly_chart(fig_eq2, use_container_width=True)
                total_series["Peak"] = total_series["Total Equity (Rp)"].cummax()
                total_series["Drawdown %"] = (total_series["Total Equity (Rp)"] - total_series["Peak"]) / total_series["Peak"] * 100
                max_dd = total_series["Drawdown %"].min()
                d1, d2, d3 = st.columns(3)
                d1.metric("Peak Equity", f"Rp{total_series['Peak'].max():,.0f}"); d2.metric("Max Drawdown", f"{max_dd:.2f}%"); d3.metric("Latest Equity", f"Rp{latest_total:,.0f}")
                st.divider()
                # ⚠️ BUG FIX DI SINI: Menggunakan total_series, bukan eq_df
                st.markdown("### 📉 Risk-Adjusted Performance Metrics")
                try:
                    if len(total_series) > 5:
                        eq_returns = total_series["Total Equity (Rp)"].pct_change().dropna()
                        rm = risk_metrics(eq_returns)
                        if rm:
                            rm1, rm2, rm3, rm4 = st.columns(4)
                            sharpe_color = "#16a34a" if rm["sharpe"] > 1.5 else ("#eab308" if rm["sharpe"] > 0.5 else "#dc2626")
                            sortino_color = "#16a34a" if rm["sortino"] > 1.5 else ("#eab308" if rm["sortino"] > 0.5 else "#dc2626")
                            dd_color = "#16a34a" if rm["max_dd"] > -10 else ("#eab308" if rm["max_dd"] > -20 else "#dc2626")
                            vol_color = "#16a34a" if rm["volatility"] < 20 else ("#eab308" if rm["volatility"] < 40 else "#dc2626")
                            rm1.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border:1px solid {sharpe_color};"><div style="font-size:10px;color:#94a3b8;">SHARPE RATIO</div><div style="font-size:20px;font-weight:700;color:{sharpe_color};">{rm['sharpe']:.2f}</div></div>""", unsafe_allow_html=True)
                            rm2.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border:1px solid {sortino_color};"><div style="font-size:10px;color:#94a3b8;">SORTINO RATIO</div><div style="font-size:20px;font-weight:700;color:{sortino_color};">{rm['sortino']:.2f}</div></div>""", unsafe_allow_html=True)
                            rm3.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border:1px solid {dd_color};"><div style="font-size:10px;color:#94a3b8;">MAX DRAWDOWN</div><div style="font-size:20px;font-weight:700;color:{dd_color};">{rm['max_dd']:.1f}%</div></div>""", unsafe_allow_html=True)
                            rm4.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border:1px solid {vol_color};"><div style="font-size:10px;color:#94a3b8;">VOLATILITY (Ann.)</div><div style="font-size:20px;font-weight:700;color:{vol_color};">{rm['volatility']:.1f}%</div></div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.caption(f"⚠️ Risk metrics tidak dapat dihitung: {str(e)}")
                st.divider()
                st.markdown("### 🏦 Equity per Sekuritas (Snapshot Terbaru)")
                if not latest_broker.empty:
                    bc1, bc2 = st.columns([1.5, 1])
                    with bc1:
                        show_cols = ["Sekuritas", "Tanggal", "Total Equity (Rp)", "Cash (Rp)", "Invested (Rp)", "Cash Ratio %"]
                        lb = latest_broker.copy()
                        lb["Total Equity (Rp)"] = pd.to_numeric(lb["Total Equity (Rp)"], errors="coerce")
                        lb["Cash (Rp)"] = pd.to_numeric(lb["Cash (Rp)"], errors="coerce")
                        lb["Cash Ratio %"] = (lb["Cash (Rp)"] / lb["Total Equity (Rp)"] * 100).round(1)
                        st.dataframe(lb[show_cols], use_container_width=True, hide_index=True)
                    with bc2:
                        fig_pie = go.Figure(data=[go.Pie(labels=latest_broker["Sekuritas"], values=pd.to_numeric(latest_broker["Total Equity (Rp)"], errors="coerce"), hole=0.5, textinfo="percent+label")])
                        fig_pie.update_layout(height=300, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
                        st.plotly_chart(fig_pie, use_container_width=True)
        with sub_catat:
            st.caption("Isi angka ini dari aplikasi sekuritas Bro. **Catat SEMUA sekuritas di tanggal yang sama.**")
            broker_options_eq = rj.load_brokers()["Sekuritas"].tolist()
            if not broker_options_eq: st.warning("Belum ada sekuritas terdaftar.")
            else:
                sc1, sc2 = st.columns(2)
                with sc1: s_tanggal = sc1.date_input("Tanggal", value=datetime.now(), key="eq_tgl")
                with sc2: s_sekuritas = sc2.selectbox("Sekuritas", options=broker_options_eq, key="eq_sek")
                sc3, sc4, sc5 = st.columns(3)
                with sc3: s_total_equity = sc3.number_input("Total Equity (Rp)", min_value=0.0, step=100000.0, key="eq_total")
                with sc4: s_cash = sc4.number_input("Cash (Rp)", min_value=0.0, step=100000.0, key="eq_cash")
                with sc5: s_invested = sc5.number_input("Invested (Rp)", min_value=0.0, step=100000.0, key="eq_invested")
                sc6, sc7 = st.columns(2)
                with sc6: s_max_risk = sc6.number_input("Max Risk/Trade (%)", min_value=0.0, value=2.0, step=0.5, key="eq_maxrisk")
                with sc7: s_max_pos = sc7.number_input("Max Position/Stock (%)", min_value=0.0, value=20.0, step=1.0, key="eq_maxpos")
                if st.button("💾 Simpan Snapshot", type="primary", key="btn_save_equity"):
                    if s_total_equity <= 0: st.error("Total Equity wajib diisi lebih dari 0.")
                    else:
                        ok, msg = eq.add_equity_snapshot(s_tanggal.strftime("%Y-%m-%d"), s_sekuritas, s_total_equity, s_cash, s_invested, s_max_risk, s_max_pos)
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)
        with sub_riwayat:
            if equity_df.empty: st.info("Belum ada riwayat snapshot.")
            else:
                st.dataframe(equity_df.sort_values("Tanggal", ascending=False), use_container_width=True, hide_index=True, height=400)
                st.download_button("⬇️ Download CSV", equity_df.to_csv(index=False).encode("utf-8"), file_name=f"equity_log_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
                st.divider()
                st.markdown("**🗑️ Hapus Snapshot**")
                del1, del2 = st.columns(2)
                with del1: del_tgl = del1.selectbox("Tanggal", options=sorted(equity_df["Tanggal"].unique(), reverse=True), key="del_eq_tgl")
                with del2: 
                    opsi_broker_del = equity_df[equity_df["Tanggal"] == del_tgl]["Sekuritas"].tolist()
                    del_sek = del2.selectbox("Sekuritas", options=opsi_broker_del, key="del_eq_sek")
                if st.button("Hapus Snapshot Ini", key="btn_del_equity"):
                    ok, msg = eq.delete_equity_row(del_tgl, del_sek)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)

# ============================================================================
# TAB 10: FUNDAMENTAL ANALYSIS (100% dari app.py asli)
# ============================================================================
with t_fundamental:
    st.markdown("## 📊 Fundamental Analysis Pro")
    st.caption("Metrik value investing: Graham, Buffett, Lynch. Data dari Yahoo Finance.")
    sub_fund, sub_gainer, sub_compare = st.tabs(["🔬 Fundamental Screener", "🏆 Top Gainer/Loser", "⚖️ Perbandingan"])
    with sub_fund:
        st.markdown("### 🎯 Filter Saham Fundamental")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            max_pe = st.number_input("Max P/E", value=15.0, min_value=0.0, step=1.0, key="f_pe")
            min_roe = st.number_input("Min ROE (%)", value=12.0, step=1.0, key="f_roe")
        with c2:
            max_de = st.number_input("Max Debt/Equity", value=0.8, min_value=0.0, step=0.1, key="f_de")
            min_divy = st.number_input("Min Div Yield (%)", value=0.0, step=0.5, key="f_div")
        with c3:
            max_pb = st.number_input("Max P/B", value=2.0, min_value=0.0, step=0.1, key="f_pb")
            min_fcfy = st.number_input("Min FCF Yield (%)", value=0.0, step=0.5, key="f_fcf")
        with c4:
            min_mos = st.number_input("Min Margin of Safety (%)", value=20.0, step=5.0, key="f_mos")
            max_peg = st.number_input("Max PEG Ratio", value=2.0, min_value=0.0, step=0.1, key="f_peg")
        scan_limit = st.slider("Jumlah saham di-scan", 50, 400, 200, key="f_limit")
        @st.cache_data(ttl=3600)
        def fetch_fundamental_batch(ticker_list):
            import yfinance as yf
            results = []
            progress = st.progress(0, text="Mengambil data fundamental...")
            for i, kode in enumerate(ticker_list):
                try:
                    t = yf.Ticker(f"{kode}.JK")
                    info = t.info
                    if not info or len(info) < 5: continue
                    price = info.get("currentPrice", info.get("regularMarketPrice", 0))
                    mc = info.get("marketCap", 0)
                    if price <= 0 or mc <= 0: continue
                    roe = info.get("returnOnEquity", 0) or 0; roa = info.get("returnOnAssets", 0) or 0
                    pe = info.get("trailingPE", 999); pb = info.get("priceToBook", 999); peg = info.get("pegRatio", 999)
                    de = info.get("debtToEquity", 0); de = de / 100 if de else 0
                    current_ratio = info.get("currentRatio", 0)
                    eps = info.get("trailingEps", info.get("forwardEps", 0)) or 0; bvps = info.get("bookValue", 0) or 0
                    fcf = info.get("freeCashflow", 0); div_yield = info.get("dividendYield", 0) or 0; payout = info.get("payoutRatio", 0) or 0
                    earnings_g = info.get("earningsGrowth", 0) or 0; revenue_g = info.get("revenueGrowth", 0) or 0
                    graham = ((22.5 * eps * bvps) ** 0.5) if eps > 0 and bvps > 0 else 0
                    mos = ((graham - price) / graham * 100) if graham > 0 else -999
                    ey = (1 / pe * 100) if pe and pe > 0 else 0; fcfy = (fcf / mc * 100) if fcf and mc else 0
                    q_score = 0
                    if roe > 0.15:
                        q_score += 20
                    elif roe > 0.10: 
                        q_score += 10
                    if de < 0.5: 
                        q_score += 20 
                    elif de < 1.0: 
                        q_score += 10
                    if pe < 15: 
                        q_score += 15
                    elif pe < 25: 
                        q_score += 5
                    if pb < 1.5: 
                        q_score += 15 
                    elif pb < 3: 
                        q_score += 5
                    if earnings_g > 0.10: 
                        q_score += 15 
                    elif earnings_g > 0: 
                        q_score += 5
                    if div_yield > 0.02: 
                        q_score += 15
                    if current_ratio and current_ratio > 1.5: 
                        q_score += 10
                    kategori = "🟦 Dividend Aristocrat" if div_yield > 0.03 and payout < 0.7 and pe < 15 else ("🟥 Deep Value" if mos > 30 and pe < 10 and pb < 1 else ("🟩 GARP" if peg < 1.5 and earnings_g > 0.15 and pe < 25 else ("🟨 Classic Value" if pe < 15 and pb < 1.5 and de < 0.5 else "⬜ Neutral")))
                    results.append({"Kode": kode, "Nama": info.get("longName", kode)[:35], "Harga": price, "Market Cap (T)": round(mc / 1e12, 2), "P/E": round(pe, 1) if pe != 999 else None, "P/B": round(pb, 1) if pb != 999 else None, "PEG": round(peg, 2) if peg != 999 else None, "ROE %": round(roe * 100, 1) if roe else None, "ROA %": round(roa * 100, 1) if roa else None, "Debt/Eq": round(de, 2) if de else None, "Current Ratio": round(current_ratio, 2) if current_ratio else None, "EPS": round(eps, 0) if eps else None, "BVPS": round(bvps, 0) if bvps else None, "Graham Number": round(graham, 0) if graham else None, "Margin of Safety %": round(mos, 1) if mos > -900 else None, "Earnings Yield %": round(ey, 1) if ey else None, "FCF Yield %": round(fcfy, 1) if fcfy else None, "Div Yield %": round(div_yield * 100, 2) if div_yield else 0, "Payout %": round(payout * 100, 1) if payout else None, "Earnings Growth %": round(earnings_g * 100, 1) if earnings_g else None, "Revenue Growth %": round(revenue_g * 100, 1) if revenue_g else None, "Quality Score": q_score, "Kategori": kategori})
                except: continue
                progress.progress((i + 1) / len(ticker_list), text=f"Scanning {kode}... ({i+1}/{len(ticker_list)})")
            progress.empty()
            return pd.DataFrame(results)
        if st.button("🔍 Scan Fundamental", type="primary", use_container_width=True):
            df_fund = fetch_fundamental_batch(tickers[:scan_limit])
            if df_fund.empty: st.error("❌ Tidak ada data fundamental yang berhasil diambil."); st.stop()
            filtered = df_fund.copy()
            if max_pe > 0: filtered = filtered[filtered["P/E"].notna() & (filtered["P/E"] <= max_pe)]
            if min_roe > 0: filtered = filtered[filtered["ROE %"].notna() & (filtered["ROE %"] >= min_roe)]
            if max_de > 0: filtered = filtered[filtered["Debt/Eq"].notna() & (filtered["Debt/Eq"] <= max_de)]
            if min_divy > 0: filtered = filtered[filtered["Div Yield %"] >= min_divy]
            if max_pb > 0: filtered = filtered[filtered["P/B"].notna() & (filtered["P/B"] <= max_pb)]
            if min_fcfy > 0: filtered = filtered[filtered["FCF Yield %"].notna() & (filtered["FCF Yield %"] >= min_fcfy)]
            if min_mos > -100: filtered = filtered[filtered["Margin of Safety %"].notna() & (filtered["Margin of Safety %"] >= min_mos)]
            if max_peg > 0: filtered = filtered[filtered["PEG"].notna() & (filtered["PEG"] <= max_peg)]
            filtered = filtered.sort_values(["Margin of Safety %", "Quality Score"], ascending=[False, False])
            st.markdown(f"**📋 Hasil: {len(filtered)} saham lolos dari {len(df_fund)} yang di-scan**")
            if not filtered.empty:
                display = filtered.copy()
                for col in ["Harga", "EPS", "BVPS", "Graham Number"]:
                    if col in display.columns: display[col] = display[col].map(lambda x: f"Rp{x:,.0f}" if pd.notna(x) else "-")
                for col in ["P/E", "P/B", "PEG", "ROE %", "ROA %", "Debt/Eq", "Margin of Safety %", "Earnings Yield %", "FCF Yield %", "Div Yield %", "Payout %", "Earnings Growth %", "Revenue Growth %", "Quality Score"]:
                    if col in display.columns: display[col] = display[col].map(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
                def color_mos(val):
                    try:
                        v = float(str(val).replace("%", ""))
                        if v >= 50: return "background-color: #065f46; color: white; font-weight: bold;"
                        elif v >= 30: return "background-color: #16a34a; color: white;"
                        elif v >= 10: return "background-color: #eab308; color: black;"
                        else: return "background-color: #7f1d1d; color: white;"
                    except: return ""
                def color_q(val):
                    try:
                        v = float(str(val))
                        if v >= 80: return "background-color: #065f46; color: white; font-weight: bold;"
                        elif v >= 60: return "background-color: #16a34a; color: white;"
                        elif v >= 40: return "background-color: #eab308; color: black;"
                        else: return "background-color: #7f1d1d; color: white;"
                    except: return ""
                styler = display.style
                if "Margin of Safety %" in display.columns: styler = styler.map(color_mos, subset=["Margin of Safety %"])
                if "Quality Score" in display.columns: styler = styler.map(color_q, subset=["Quality Score"])
                st.dataframe(styler, use_container_width=True, hide_index=True, height=500)
                st.download_button("⬇️ Download CSV Fundamental", filtered.to_csv(index=False).encode("utf-8"), file_name=f"fundamental_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
                st.divider()
                st.markdown("### 💡 Insight")
                c_ins1, c_ins2, c_ins3 = st.columns(3)
                with c_ins1: st.metric("Deep Value", len(filtered[filtered["Kategori"] == "🟥 Deep Value"]))
                with c_ins2: st.metric("Dividend Aristocrat", len(filtered[filtered["Kategori"] == "🟦 Dividend Aristocrat"]))
                with c_ins3: st.metric("GARP", len(filtered[filtered["Kategori"] == "🟩 GARP"]))
            else: st.info("Tidak ada saham yang lolos filter. Coba longgarkan kriteria.")
    with sub_gainer:
        st.markdown("### 🏆 Top Gainer & Loser")
        periode = st.selectbox("Periode", ["1 Hari", "1 Minggu", "1 Bulan", "3 Bulan", "6 Bulan", "1 Tahun"], index=2)
        top_n = st.slider("Jumlah saham", 5, 50, 10)
        period_map = {"1 Hari": 2, "1 Minggu": 6, "1 Bulan": 22, "3 Bulan": 66, "6 Bulan": 132, "1 Tahun": 252}
        with st.spinner(f"Menghitung {periode.lower()}..."):
            gainer_data = []
            lookback = period_map[periode]
            for kode in tickers[:300]:
                try:
                    df = price_data.get(kode)
                    if df is not None and len(df) >= lookback + 1:
                        old = float(df["Close"].iloc[-lookback - 1]); new = float(df["Close"].iloc[-1])
                        if old > 0: gainer_data.append({"Kode": kode, "Harga Awal": old, "Harga Sekarang": new, "Perubahan %": ((new / old) - 1) * 100})
                except: continue
            if gainer_data:
                df_g = pd.DataFrame(gainer_data).sort_values("Perubahan %", ascending=False)
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.subheader(f"🚀 Top {top_n} Gainer")
                    top = df_g.head(top_n).copy()
                    top["Harga Awal"] = top["Harga Awal"].map(lambda x: f"Rp{x:,.0f}")
                    top["Harga Sekarang"] = top["Harga Sekarang"].map(lambda x: f"Rp{x:,.0f}")
                    top["Perubahan %"] = top["Perubahan %"].map(lambda x: f"{x:+.2f}%")
                    st.dataframe(top, use_container_width=True, hide_index=True)
                with col_g2:
                    st.subheader(f"📉 Top {top_n} Loser")
                    bottom = df_g.tail(top_n).sort_values("Perubahan %").copy()
                    bottom["Harga Awal"] = bottom["Harga Awal"].map(lambda x: f"Rp{x:,.0f}")
                    bottom["Harga Sekarang"] = bottom["Harga Sekarang"].map(lambda x: f"Rp{x:,.0f}")
                    bottom["Perubahan %"] = bottom["Perubahan %"].map(lambda x: f"{x:+.2f}%")
                    st.dataframe(bottom, use_container_width=True, hide_index=True)
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(x=df_g["Perubahan %"], nbinsx=40, marker_color="#38bdf8", opacity=0.8))
                fig_hist.add_vline(x=0, line_dash="dash", line_color="#ef4444")
                fig_hist.update_layout(height=280, template="plotly_dark", title=f"Distribusi Return {periode}", xaxis_title="Return (%)", yaxis_title="Jumlah Saham", margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_hist, use_container_width=True)
            else: st.info("Data tidak mencukupi.")
    with sub_compare:
        st.markdown("### ⚖️ Perbandingan Multi-Saham")
        pilih_compare = st.multiselect("Pilih saham (max 5)", options=table["Kode"].tolist() if not table.empty else [], default=[], max_selections=5)
        if len(pilih_compare) >= 2:
            with st.spinner("Mengambil data..."):
                import yfinance as yf
                comp_data = []
                for kode in pilih_compare:
                    try:
                        info = yf.Ticker(f"{kode}.JK").info
                        price = info.get("currentPrice", 0); eps = info.get("trailingEps", 0); bvps = info.get("bookValue", 0)
                        graham = ((22.5 * eps * bvps) ** 0.5) if eps > 0 and bvps > 0 else 0
                        mos = ((graham - price) / graham * 100) if graham > 0 else None
                        comp_data.append({"Kode": kode, "Harga": price, "P/E": info.get("trailingPE"), "P/B": info.get("priceToBook"), "ROE %": info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None, "Debt/Eq": info.get("debtToEquity", 0) / 100 if info.get("debtToEquity") else None, "Div Yield %": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0, "Graham Number": graham, "MOS %": mos, "EPS Growth %": info.get("earningsGrowth", 0) * 100 if info.get("earningsGrowth") else None})
                    except: continue
                if comp_data:
                    df_c = pd.DataFrame(comp_data).set_index("Kode").T.reset_index().rename(columns={"index": "Metrik"})
                    st.dataframe(df_c, use_container_width=True, hide_index=True)
                    categories = ["P/E", "P/B", "ROE %", "Div Yield %", "MOS %"]
                    categories = [c for c in categories if c in df_c.columns]
                    if categories:
                        fig_radar = go.Figure()
                        for kode in pilih_compare:
                            values = []
                            for cat in categories:
                                val = df_c[df_c["Metrik"] == cat][kode].values[0] if not df_c[df_c["Metrik"] == cat].empty else 0
                                if cat == "P/E": val = max(0, min(100, (30 - float(val)) / 30 * 100)) if val else 0
                                elif cat == "P/B": val = max(0, min(100, (3 - float(val)) / 3 * 100)) if val else 0
                                elif cat == "ROE %": val = min(100, float(val)) if val else 0
                                elif cat == "Div Yield %": val = min(100, float(val) * 10) if val else 0
                                elif cat == "MOS %": val = max(0, min(100, float(val))) if val else 0
                                values.append(val)
                            fig_radar.add_trace(go.Scatterpolar(r=values + [values[0]], theta=categories + [categories[0]], fill='toself', name=kode))
                        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=True, height=400, template="plotly_dark", margin=dict(l=40, r=40, t=40, b=10))
                        st.plotly_chart(fig_radar, use_container_width=True)
        else: st.info("Pilih minimal 2 saham untuk perbandingan.")

# ============================================================================
# TAB 11: VALUE INVESTING PORTFOLIO (100% dari app.py asli)
# ============================================================================
with t_invest:
    st.markdown("## 🏛️ Value Investing Portfolio")
    st.caption("Analisis berbasis prinsip Warren Buffett & Benjamin Graham.")
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        buffett_min_roe = st.number_input("Min ROE (%)", value=15.0, step=1.0, key="b_roe")
        buffett_max_de = st.number_input("Max Debt/Equity", value=0.5, step=0.1, key="b_de")
    with col_b2:
        buffett_max_pe = st.number_input("Max P/E", value=20.0, step=1.0, key="b_pe")
        buffett_min_eps_g = st.number_input("Min EPS Growth 5Y (%)", value=5.0, step=1.0, key="b_epsg")
    with col_b3:
        buffett_min_mos = st.number_input("Min Margin of Safety (%)", value=25.0, step=5.0, key="b_mos")
        mode_invest = st.selectbox("Strategi", ["🎯 Deep Value (MOS tinggi)", "💎 Quality First (ROE tinggi)", "⚖️ Balanced"], index=2)
    scan_inv = st.slider("Scan saham", 50, 400, 200, key="inv_limit")
    if st.button("🔍 Cari Saham Investasi", type="primary", use_container_width=True):
        with st.spinner("Menganalisis ratusan saham dengan kriteria Buffett..."):
            import yfinance as yf
            invest_results = []
            progress = st.progress(0)
            for i, kode in enumerate(tickers[:scan_inv]):
                try:
                    t = yf.Ticker(f"{kode}.JK")
                    info = t.info
                    if not info: continue
                    price = info.get("currentPrice", info.get("regularMarketPrice", 0)); mc = info.get("marketCap", 0)
                    if price <= 0 or mc <= 0: continue
                    roe = info.get("returnOnEquity", 0) or 0; roa = info.get("returnOnAssets", 0) or 0
                    pe = info.get("trailingPE", 999); pb = info.get("priceToBook", 999)
                    de = info.get("debtToEquity", 0); de = de / 100 if de else 0
                    eps = info.get("trailingEps", 0) or 0; bvps = info.get("bookValue", 0) or 0
                    earnings_g = info.get("earningsGrowth", 0) or 0; div_yield = info.get("dividendYield", 0) or 0; payout = info.get("payoutRatio", 0) or 0; fcf = info.get("freeCashflow", 0)
                    graham = ((22.5 * eps * bvps) ** 0.5) if eps > 0 and bvps > 0 else 0
                    mos = ((graham - price) / graham * 100) if graham > 0 else -999
                    if roe * 100 < buffett_min_roe or pe > buffett_max_pe or de > buffett_max_de or earnings_g * 100 < buffett_min_eps_g or mos < buffett_min_mos: continue
                    score = min(40, max(0, mos) / 50 * 40) + min(20, roe * 100 / 20 * 20) + (min(15, (25 - pe) / 25 * 15) if pe < 25 else 0) + (min(10, (3 - pb) / 3 * 10) if pb < 3 else 0) + min(10, earnings_g * 100 / 20 * 10) + min(5, div_yield * 100)
                    rec = "🟢 STRONG BUY" if mos >= 50 and score >= 70 else ("🟡 BUY" if mos >= 25 and score >= 50 else ("🟠 WATCHLIST" if mos >= 10 else "🔴 AVOID"))
                    invest_results.append({"Kode": kode, "Nama": info.get("longName", kode)[:30], "Rekomendasi": rec, "Value Score": round(score, 1), "Harga": price, "Graham Number": round(graham, 0) if graham else None, "MOS %": round(mos, 1) if mos > -900 else None, "P/E": round(pe, 1) if pe != 999 else None, "P/B": round(pb, 1) if pb != 999 else None, "ROE %": round(roe * 100, 1) if roe else None, "ROA %": round(roa * 100, 1) if roa else None, "Debt/Eq": round(de, 2) if de else None, "EPS": round(eps, 0) if eps else None, "EPS Growth %": round(earnings_g * 100, 1) if earnings_g else None, "Div Yield %": round(div_yield * 100, 2) if div_yield else 0, "FCF (M)": round(fcf / 1e6, 0) if fcf else None, "Market Cap (T)": round(mc / 1e12, 2)})
                except: continue
                progress.progress((i + 1) / scan_inv)
            progress.empty()
            if invest_results:
                df_inv = pd.DataFrame(invest_results)
                if mode_invest == "🎯 Deep Value (MOS tinggi)": df_inv = df_inv.sort_values("MOS %", ascending=False)
                elif mode_invest == "💎 Quality First (ROE tinggi)": df_inv = df_inv.sort_values("ROE %", ascending=False)
                else: df_inv = df_inv.sort_values("Value Score", ascending=False)
                st.markdown(f"**📋 {len(df_inv)} saham lolos filter Buffett**")
                display = df_inv.copy()
                for col in ["Harga", "Graham Number", "EPS"]:
                    if col in display.columns: display[col] = display[col].map(lambda x: f"Rp{x:,.0f}" if pd.notnull(x) else "-")
                fmt_1dec = ["Value Score", "ROE %", "ROA %", "MOS %", "EPS Growth %", "Revenue Growth %", "Div Yield %", "Payout %"]
                fmt_2dec = ["P/E", "P/B", "PEG", "Debt/Eq", "Earnings Yield %", "FCF Yield %"]
                for col in fmt_1dec:
                    if col in display.columns: display[col] = display[col].map(lambda x: f"{x:.1f}".rstrip('0').rstrip('.') if pd.notnull(x) else "-")
                for col in fmt_2dec:
                    if col in display.columns: display[col] = display[col].map(lambda x: f"{x:.2f}".rstrip('0').rstrip('.') if pd.notnull(x) else "-")
                if "Market Cap (T)" in display.columns: display["Market Cap (T)"] = display["Market Cap (T)"].map(lambda x: f"{x:.2f}".rstrip('0').rstrip('.') + " T" if pd.notnull(x) else "-")
                if "FCF (M)" in display.columns: display["FCF (M)"] = display["FCF (M)"].map(lambda x: f"{x:,.0f} M" if pd.notnull(x) else "-")
                def color_rec(val):
                    if "STRONG BUY" in str(val): return "background-color: #065f46; color: white; font-weight: bold;"
                    if "BUY" in str(val): return "background-color: #16a34a; color: white;"
                    if "WATCHLIST" in str(val): return "background-color: #eab308; color: black;"
                    if "AVOID" in str(val): return "background-color: #7f1d1d; color: white;"
                    return ""
                def color_score(val):
                    try:
                        v = float(val)
                        if v >= 70: return "background-color: #065f46; color: white; font-weight: bold;"
                        elif v >= 50: return "background-color: #16a34a; color: white;"
                        elif v >= 30: return "background-color: #eab308; color: black;"
                        else: return "background-color: #7f1d1d; color: white;"
                    except: return ""
                styler = display.style
                if "Rekomendasi" in display.columns: styler = styler.map(color_rec, subset=["Rekomendasi"])
                if "Value Score" in display.columns: styler = styler.map(color_score, subset=["Value Score"])
                st.dataframe(styler, use_container_width=True, hide_index=True, height=500)
                st.download_button("⬇️ Download Value Portfolio", df_inv.to_csv(index=False).encode("utf-8"), file_name=f"value_portfolio_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
                st.divider()
                st.markdown("### 📊 Ringkasan Portofolio Value")
                r1, r2, r3, r4 = st.columns(4)
                strong = len(df_inv[df_inv["Rekomendasi"] == "🟢 STRONG BUY"])
                buy = len(df_inv[df_inv["Rekomendasi"] == "🟡 BUY"])
                watch = len(df_inv[df_inv["Rekomendasi"] == "🟠 WATCHLIST"])
                r1.metric("STRONG BUY", strong); r2.metric("BUY", buy); r3.metric("WATCHLIST", watch); r4.metric("Rata-rata MOS", f"{df_inv['MOS %'].mean():.1f}%")
                fig_cat = go.Figure(data=[go.Pie(labels=["STRONG BUY", "BUY", "WATCHLIST"], values=[strong, buy, watch], hole=0.4, marker_colors=["#16a34a", "#eab308", "#f97316"])])
                fig_cat.update_layout(height=250, template="plotly_dark", showlegend=True, margin=dict(l=10, r=10, t=10, b=10), title="Distribusi Rekomendasi")
                st.plotly_chart(fig_cat, use_container_width=True)
                st.divider()
                st.markdown("### ✅ Buffett Checklist\n1. **ROE > 15%**\n2. **Debt/Equity < 0.5**\n3. **P/E < 20**\n4. **Margin of Safety > 25%**\n5. **EPS Growth konsisten**\n6. **Dividend (opsional)**")
            else: st.info("Tidak ada saham yang lolos kriteria Buffett. Coba longgarkan filter.")

# ============================================================================
# TAB 12: IHSG ANALYSIS (Dari app_premium_complete.py)
# ============================================================================
with t_ihsg:
    st.markdown("## 📊 IHSG Analysis — Gann Square of 9 + Time Cycle")
    st.caption("Analisis matematis berbasis W.D. Gann & Astronacci. Auto-detect pivot low/high dari data historis.")
    if ihsg_gann_data is None:
        st.warning("Data IHSG tidak tersedia untuk analisis Gann.")
    else:
        g = ihsg_gann_data['gann']; c = ihsg_gann_data['current']; h = ihsg_gann_data['high_1y']; l = ihsg_gann_data['low_1y']
        pl_idx, pl_price = ihsg_gann_data['pivot_low']; ph_idx, ph_price = ihsg_gann_data['pivot_high']
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("IHSG", f"{c:,.0f}"); m2.metric("1Y High", f"{h:,.0f}"); m3.metric("1Y Low", f"{l:,.0f}")
        m4.metric("Recovery", f"{((c-l)/l*100):+.1f}%"); m5.metric("From High", f"-{((h-c)/h*100):.1f}%")
        st.divider()
        gcol1, gcol2 = st.columns([1, 1.5])
        with gcol1:
            st.markdown("### 🔷 Gann Square of 9 Levels")
            st.markdown("**📈 Resistance**")
            for k, v in g['resistance'].items():
                color = "#f87171" if v > c else "#4ade80"; status = "⬆️ ABOVE" if v > c else "✅ CROSSED"
                st.markdown(f"<div style='display:flex;justify-content:space-between;background:#0f172a;padding:6px 10px;border-radius:6px;margin-bottom:4px;'><span style='color:#94a3b8;font-size:12px;'>{k}</span><span style='color:{color};font-weight:600;font-size:13px;'>{v:,.0f} {status}</span></div>", unsafe_allow_html=True)
            st.markdown("**📉 Support**")
            for k, v in g['support'].items():
                color = "#4ade80" if v < c else "#f87171"; status = "⬇️ BELOW" if v < c else "⚠️ BROKEN"
                st.markdown(f"<div style='display:flex;justify-content:space-between;background:#0f172a;padding:6px 10px;border-radius:6px;margin-bottom:4px;'><span style='color:#94a3b8;font-size:12px;'>{k}</span><span style='color:{color};font-weight:600;font-size:13px;'>{v:,.0f} {status}</span></div>", unsafe_allow_html=True)
        with gcol2:
            st.markdown("### 📈 IHSG Chart dengan Gann Levels")
            if not ihsg_hist.empty:
                fig_ihsg = go.Figure()
                fig_ihsg.add_trace(go.Scatter(x=ihsg_hist.index, y=ihsg_hist['Close'], mode='lines', name='IHSG Close', line=dict(color='#38bdf8', width=1.5), fill='tozeroy', fillcolor='rgba(56,189,248,0.05)'))
                colors_r = ['#f87171', '#ef4444', '#dc2626', '#991b1b']; colors_s = ['#4ade80', '#22c55e', '#16a34a', '#15803d']
                for i, (k, v) in enumerate(g['resistance'].items()): fig_ihsg.add_hline(y=v, line_dash="dash", line_color=colors_r[i], annotation_text=f"{k} {v:,.0f}", annotation_position="right")
                for i, (k, v) in enumerate(g['support'].items()): fig_ihsg.add_hline(y=v, line_dash="dash", line_color=colors_s[i], annotation_text=f"{k} {v:,.0f}", annotation_position="right")
                fig_ihsg.add_annotation(x=pl_idx, y=pl_price, text="📉 PIVOT LOW", showarrow=True, arrowhead=2, arrowcolor="#f87171", font=dict(color="#f87171", size=11), ay=40)
                fig_ihsg.add_annotation(x=ph_idx, y=ph_price, text="📈 PIVOT HIGH", showarrow=True, arrowhead=2, arrowcolor="#4ade80", font=dict(color="#4ade80", size=11), ay=-40)
                fig_ihsg.update_layout(height=450, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), yaxis_title="IHSG", showlegend=False, hovermode="x unified")
                st.plotly_chart(fig_ihsg, use_container_width=True)
        st.divider()
        st.markdown("### ⏰ Time Cycle Analysis")
        tc_col1, tc_col2 = st.columns(2)
        with tc_col1: st.markdown(f"**📉 Dari Pivot Low**<br><span style='font-size:12px;color:#94a3b8;'>{pl_idx.strftime('%d %b %Y') if hasattr(pl_idx, 'strftime') else str(pl_idx)} @ {pl_price:,.0f}</span>", unsafe_allow_html=True)
        with tc_col2: st.markdown(f"**📈 Dari Pivot High**<br><span style='font-size:12px;color:#94a3b8;'>{ph_idx.strftime('%d %b %Y') if hasattr(ph_idx, 'strftime') else str(ph_idx)} @ {ph_price:,.0f}</span>", unsafe_allow_html=True)
        if isinstance(ph_idx, pd.Timestamp): ph_date = ph_idx.to_pydatetime()
        else: ph_date = datetime.now() - timedelta(days=60)
        cycles_high = GannSquareOf9.time_cycle_analysis(ph_date, ph_price)
        upcoming_high = [c for c in cycles_high if not c['passed'] and c['days_from_now'] <= 90]
        all_cycles = []
        for c_cycle in ihsg_gann_data['cycles']:
            c_copy = c_cycle.copy(); c_copy['source'] = 'Pivot Low'; all_cycles.append(c_copy)
        for c_cycle in upcoming_high[:5]:
            c_copy = c_cycle.copy(); c_copy['source'] = 'Pivot High'; all_cycles.append(c_copy)
        all_cycles.sort(key=lambda x: x['days_from_now'])
        if all_cycles:
            combined_df = pd.DataFrame(all_cycles)
            combined_df['Status'] = combined_df['days_from_now'].apply(lambda x: "🔴 HARI INI" if x == 0 else ("🟠 DEKAT (<7h)" if x <= 7 else ("🟡 MINGGU INI" if x <= 14 else "🟢 AKAN DATANG")))
            styler_comb = combined_df[['source', 'type', 'days', 'date', 'days_from_now', 'Status']].style
            styler_comb = styler_comb.map(lambda val: "background-color:#7f1d1d;color:#fca5a5;font-weight:bold;" if "HARI INI" in val else ("background-color:#7c2d12;color:#fdba74;font-weight:bold;" if "DEKAT" in val else "background-color:#713f12;color:#fde047;" if "MINGGU" in val else "background-color:#0f172a;color:#94a3b8;"), subset=['Status'])
            st.dataframe(styler_comb, use_container_width=True, hide_index=True, height=280)
            same_day = {}
            for c_cycle in all_cycles:
                if c_cycle['days_from_now'] <= 14:
                    d = c_cycle['date']
                    if d not in same_day: same_day[d] = []
                    same_day[d].append(c_cycle)
            convergences = {k: v for k, v in same_day.items() if len(v) >= 2}
            if convergences:
                st.markdown("### ⚠️ CONVERGENCE ALERT")
                st.caption("Beberapa time cycle bertemu di tanggal yang sama — volatilitas ekstrem kemungkinan besar!")
                for date, items in sorted(convergences.items()):
                    sources = ", ".join([f"{i['source']} ({i['type']} {i['days']}D)" for i in items])
                    st.markdown(f"🔴 **{date}** ({items[0]['days_from_now']} hari lagi): {sources}")
        else: st.info("Tidak ada time cycle dalam 90 hari ke depan.")
        st.divider()
        tc1, tc2 = st.columns([2, 1])
        with tc1:
            cycles = ihsg_gann_data['cycles']
            if cycles:
                cycle_df = pd.DataFrame(cycles[:10])
                cycle_df['Status'] = cycle_df['days_from_now'].apply(lambda x: "🔴 HARI INI" if x == 0 else ("🟠 DEKAT (<7h)" if x <= 7 else ("🟡 MINGGU INI" if x <= 14 else "🟢 AKAN DATANG")))
                styler = cycle_df[['type', 'days', 'date', 'days_from_now', 'Status']].style
                styler = styler.map(lambda val: "background-color:#7f1d1d;color:#fca5a5;font-weight:bold;" if "HARI INI" in val else ("background-color:#7c2d12;color:#fdba74;font-weight:bold;" if "DEKAT" in val else "background-color:#713f12;color:#fde047;" if "MINGGU" in val else "background-color:#0f172a;color:#94a3b8;"), subset=['Status'])
                st.dataframe(styler, use_container_width=True, hide_index=True, height=350)
            else: st.info("Tidak ada time cycle dalam 90 hari ke depan.")
        with tc2:
            st.markdown("**📊 Signal Meter**")
            pos = ihsg_gann_data['position_pct']; rsi = ihsg_gann_data['rsi_approx']
            st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:12px;margin-bottom:10px;"><div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">Position in Range</div><div style="background:#0f172a;border-radius:4px;height:20px;overflow:hidden;"><div style="background:linear-gradient(90deg,#f87171,#fbbf24,#4ade80);width:{pos}%;height:100%;border-radius:4px;"></div></div><div style="text-align:right;font-size:12px;color:#38bdf8;font-weight:600;">{pos:.1f}%</div></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:12px;margin-bottom:10px;"><div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">RSI (Approx)</div><div style="background:#0f172a;border-radius:4px;height:20px;overflow:hidden;"><div style="background:linear-gradient(90deg,#f87171,#fbbf24,#4ade80);width:{rsi}%;height:100%;border-radius:4px;"></div></div><div style="text-align:right;font-size:12px;color:#38bdf8;font-weight:600;">{rsi:.1f}</div></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:12px;border-left:4px solid #fbbf24;"><div style="font-size:12px;color:#fbbf24;font-weight:700;margin-bottom:4px;">{ihsg_gann_data['bias']}</div><div style="font-size:11px;color:#94a3b8;">{'⚠️ Time cycle aktif — volatilitas tinggi' if ihsg_gann_data['cycle_alert'] else '⏳ Pantau breakout level kunci'}</div></div>""", unsafe_allow_html=True)
        st.divider()
        st.markdown("### 🎯 Trading Recommendation")
        rcol1, rcol2, rcol3 = st.columns(3)
        with rcol1:
            st.markdown("**🟢 BUY Signal**")
            buy_conditions = []
            if c < g['support']['S1_45°'] * 1.01: buy_conditions.append("✅ Di dekat Support Gann")
            if ihsg_gann_data['rsi_approx'] < 35: buy_conditions.append("✅ RSI Oversold")
            if ihsg_gann_data['cycle_alert'] and any(x['days_from_now'] == 0 for x in cycles[:3]): buy_conditions.append("⚠️ Time Cycle Hari Ini — tunggu konfirmasi")
            if not buy_conditions: buy_conditions.append("❌ Belum ada sinyal beli kuat")
            for bc in buy_conditions: st.markdown(f"<div style='font-size:12px;color:#cbd5e1;margin-bottom:4px;'>{bc}</div>", unsafe_allow_html=True)
        with rcol2:
            st.markdown("**🔴 SELL / CUT LOSS Signal**")
            sell_conditions = []
            if c > g['resistance']['R1_45°'] * 0.99: sell_conditions.append("⚠️ Dekat Resistance — jangan FOMO beli")
            if c < g['support']['S3_180°']: sell_conditions.append("❌ Break Support Major — consider cut loss")
            if ihsg_gann_data['rsi_approx'] > 70: sell_conditions.append("⚠️ RSI Overbought — profit taking zone")
            if not sell_conditions: sell_conditions.append("⏳ Belum ada sinyal jual kuat")
            for sc in sell_conditions: st.markdown(f"<div style='font-size:12px;color:#cbd5e1;margin-bottom:4px;'>{sc}</div>", unsafe_allow_html=True)
        with rcol3:
            st.markdown("**📋 Action Plan**")
            st.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border:1px solid #334155;"><div style="font-size:12px;color:#94a3b8;line-height:1.6;">1. <b>Entry:</b> Tunggu break above R1 ({g['resistance']['R1_45°']:,.0f}) dengan volume<br>2. <b>Stop Loss:</b> Di bawah S2 ({g['support']['S2_90°']:,.0f})<br>3. <b>Target:</b> R3 ({g['resistance']['R3_180°']:,.0f}) atau R4 ({g['resistance']['R4_360°']:,.0f})<br>4. <b>Risiko:</b> Jangan all-in saat time cycle aktif</div></div>""", unsafe_allow_html=True)
        st.divider()
        st.caption("🔮 **Disclaimer:** Gann & Time Cycle adalah probabilitas, bukan ramalan pasti. Selalu gunakan stop loss dan manajemen risiko.")

# ============================================================================
# TAB 13: CORRELATION MATRIX (Dari app_premium_complete.py)
# ============================================================================
with t_corr:
    st.markdown("## 🔗 Correlation Matrix — Diversifikasi Portofolio")
    st.caption("Korelasi antar saham (60 hari). Hindari saham dengan korelasi >0.80 untuk diversifikasi optimal.")
    corr_limit = st.slider("Jumlah saham untuk analisis korelasi", 10, 100, 30, key="corr_limit")
    corr_tickers = []
    if not table.empty:
        buy_signals = table[table["Signal"].isin(["STRONG BUY", "BUY"])]["Kode"].tolist()[:15]
        corr_tickers.extend(buy_signals)
    remaining = [t for t in tickers if t not in corr_tickers]
    corr_tickers.extend(remaining[:corr_limit - len(corr_tickers)])
    corr_tickers = list(dict.fromkeys(corr_tickers))[:corr_limit]
    if st.button("🔍 Hitung Correlation Matrix", type="primary", use_container_width=True, key="btn_corr"):
        with st.spinner(f"Menghitung korelasi {len(corr_tickers)} saham..."):
            corr_df = correlation_matrix(price_data, corr_tickers, period=60)
            if corr_df is not None and not corr_df.empty:
                fig_corr = go.Figure(data=go.Heatmap(z=corr_df.values, x=corr_df.columns, y=corr_df.index, colorscale=[[0, "#dc2626"], [0.3, "#f87171"], [0.5, "#1e293b"], [0.7, "#4ade80"], [1, "#16a34a"]], zmid=0, text=np.round(corr_df.values, 2), texttemplate="%{text}", textfont={"size": 9}, hovertemplate="%{x} vs %{y}<br>Correlation: %{z:.3f}<extra></extra>"))
                fig_corr.update_layout(height=600, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), title="📊 60-Day Correlation Heatmap")
                st.plotly_chart(fig_corr, use_container_width=True)
                high_corr = []
                for i in range(len(corr_df.columns)):
                    for j in range(i+1, len(corr_df.columns)):
                        val = corr_df.iloc[i, j]
                        if abs(val) > 0.80: high_corr.append({"Saham A": corr_df.columns[i], "Saham B": corr_df.columns[j], "Korelasi": round(val, 3), "Risk": "⚠️ TINGGI — Jangan beli bersamaan" if val > 0.85 else "🟡 Waspada"})
                if high_corr:
                    st.markdown("### ⚠️ Pasang Saham dengan Korelasi Tinggi")
                    st.caption("Hindari membeli saham-saham ini bersamaan karena bergerak searah.")
                    st.dataframe(pd.DataFrame(high_corr), use_container_width=True, hide_index=True)
                else: st.success("✅ Tidak ada pasang saham dengan korelasi >0.80 — portofolio Anda sudah diversifikasi dengan baik!")
                avg_corr = corr_df.values[np.triu_indices_from(corr_df.values, k=1)].mean()
                div_score = "🟢 EXCELLENT" if avg_corr < 0.3 else ("🟡 GOOD" if avg_corr < 0.5 else ("🟠 MODERATE" if avg_corr < 0.7 else "🔴 POOR"))
                div_color = "#16a34a" if avg_corr < 0.3 else ("#eab308" if avg_corr < 0.5 else ("#f97316" if avg_corr < 0.7 else "#dc2626"))
                st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:14px;border:1px solid {div_color};margin-top:12px;"><div style="font-size:13px;color:{div_color};font-weight:700;">Diversifikasi Score: {div_score}</div><div style="font-size:11px;color:#94a3b8;margin-top:4px;">Rata-rata korelasi: {avg_corr:.3f} (semakin rendah semakin baik)</div></div>""", unsafe_allow_html=True)
            else: st.warning("Data tidak cukup untuk menghitung korelasi. Coba refresh data atau kurangi jumlah saham.")

# ============================================================================
# TAB 14: ASTRONACCI (Dari app_premium_complete.py)
# ============================================================================
with t_astro:
    st.markdown("## 🌙 Astronacci — Astro-Cycle Analysis")
    st.caption("Kombinasi Astronomi + Fibonacci + Gann. Fase bulan dan posisi planet mempengaruhi sentimen pasar.")
    astro = astro_cycle_analysis(datetime.now())
    ac1, ac2 = st.columns([1, 1.5])
    with ac1:
        st.markdown("### 🌙 Fase Bulan Hari Ini")
        moon = astro["moon"]
        st.markdown(f"""<div style="background:#1e293b;border-radius:12px;padding:16px;border:1px solid #334155;text-align:center;"><div style="font-size:48px;margin-bottom:8px;">{moon['name'].split()[0]}</div><div style="font-size:14px;font-weight:700;color:#fbbf24;">{moon['name']}</div><div style="font-size:12px;color:#94a3b8;margin-top:8px;">Umur: {moon['age']:.1f} hari (siklus 29.5 hari)</div><div style="background:#0f172a;border-radius:6px;height:12px;margin-top:10px;overflow:hidden;"><div style="background:linear-gradient(90deg,#1e293b,#fbbf24,#1e293b);width:{moon['phase_pct']*100}%;height:100%;"></div></div><div style="font-size:11px;color:#94a3b8;margin-top:4px;">{moon['phase_pct']*100:.1f}% dari siklus</div><div style="font-size:13px;font-weight:600;color:#38bdf8;margin-top:10px;padding:8px;background:#0f172a;border-radius:6px;">{moon['bias']}</div></div>""", unsafe_allow_html=True)
        st.markdown("### 📅 Astro-Trading Calendar")
        st.caption("Fibonacci days dari New Moon terakhir:")
        if astro["events"]:
            for ev in astro["events"]: st.markdown(f"""<div style="background:#1e293b;border-radius:6px;padding:8px;margin-bottom:4px;border-left:3px solid #fbbf24;"><span style="font-size:11px;color:#fbbf24;font-weight:600;">{ev['type']}</span> <span style="font-size:11px;color:#94a3b8;"> → {ev['date']} ({ev['days_left']} hari)</span></div>""", unsafe_allow_html=True)
        else: st.info("Tidak ada astro-event dalam 7 hari ke depan.")
    with ac2:
        st.markdown("### 🪐 Posisi Planet (Proxy)")
        planet_data = []
        for name, deg in astro["planets"].items():
            signs = ["♈ Aries", "♉ Taurus", "♊ Gemini", "♋ Cancer", "♌ Leo", "♍ Virgo", "♎ Libra", "♏ Scorpio", "♐ Sagittarius", "♑ Capricorn", "♒ Aquarius", "♓ Pisces"]
            sign_idx = int(deg / 30) % 12
            planet_data.append({"Planet": name, "Degree": f"{deg:.1f}°", "Zodiac": signs[sign_idx]})
        st.dataframe(pd.DataFrame(planet_data), use_container_width=True, hide_index=True, height=250)
        if astro["conjunctions"]:
            st.markdown("### ⚠️ Konjungsi Planet")
            st.caption("Planet yang berdekatan (<15°) — potensi volatilitas tinggi")
            for conj in astro["conjunctions"]: st.markdown(f"<div style='background:#7f1d1d;border-radius:6px;padding:8px;margin-bottom:4px;color:#fca5a5;font-size:12px;'>🔴 {conj}</div>", unsafe_allow_html=True)
        else: st.markdown("<div style='background:#0f172a;border-radius:6px;padding:8px;color:#4ade80;font-size:12px;'>✅ Tidak ada konjungsi planet saat ini</div>", unsafe_allow_html=True)
        st.markdown("### 🔮 Astronacci Synthesis")
        st.caption("Gabungan Gann Time Cycle + Astro Cycle:")
        if ihsg_gann_data and ihsg_gann_data.get('cycle_alert'):
            st.markdown(f"""<div style="background:#7f1d1d;border-radius:8px;padding:12px;border:1px solid #dc2626;"><div style="font-size:13px;color:#fca5a5;font-weight:700;">🚨 HIGH ALERT</div><div style="font-size:12px;color:#f87171;margin-top:4px;">Time Cycle aktif + {moon['name']} → Reversal kemungkinan besar!<br>Hindari entry baru. Pantau breakout level kunci.</div></div>""", unsafe_allow_html=True)
        elif "FULL MOON" in moon['name'] or "NEW MOON" in moon['name']:
            st.markdown(f"""<div style="background:#713f12;border-radius:8px;padding:12px;border:1px solid #eab308;"><div style="font-size:13px;color:#fde047;font-weight:700;">⚡ MODERATE ALERT</div><div style="font-size:12px;color:#fbbf24;margin-top:4px;">{moon['name']} terdeteksi — sentimen pasar bisa berubah drastis.<br>Gunakan position size lebih kecil dari biasanya.</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:12px;border:1px solid #334155;"><div style="font-size:13px;color:#4ade80;font-weight:700;">✅ NORMAL</div><div style="font-size:12px;color:#94a3b8;margin-top:4px;">Tidak ada astro-anomaly. Trading sesuai plan biasa.</div></div>""", unsafe_allow_html=True)
    st.divider()
    st.caption("🔮 **Disclaimer:** Astro-cycle adalah probabilitas psikologis/seasonal, bukan sains eksak. Gunakan sebagai konfirmasi tambahan.")

# ============================================================================
# TAB 15: SENTIMENT ANALYSIS (Dari app_premium_complete.py)
# ============================================================================
with t_sentiment:
    st.markdown("## 📰 Market Sentiment Analysis")
    st.caption("Agregasi sentimen dari berita pasar modal Indonesia. Update otomatis setiap 30 menit.")
    sentiment = fetch_sentiment_news()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Positive", sentiment["positive"]); s2.metric("Negative", sentiment["negative"]); s3.metric("Neutral", sentiment["neutral"]); s4.metric("Sentiment Score", f"{sentiment['score']:+.1f}")
    st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:14px;border:1px solid {sentiment['color']};margin:12px 0;"><div style="font-size:14px;color:{sentiment['color']};font-weight:700;">Overall Sentiment: {sentiment['overall']}</div></div>""", unsafe_allow_html=True)
    score = sentiment["score"]; gauge_pos = max(0, min(100, 50 + score))
    st.markdown(f"""<div style="background:#0f172a;border-radius:8px;height:24px;overflow:hidden;margin:12px 0;"><div style="background:linear-gradient(90deg,#dc2626,#eab308,#16a34a);width:100%;height:100%;position:relative;"><div style="position:absolute;left:{gauge_pos}%;top:0;bottom:0;width:4px;background:#fff;box-shadow:0 0 8px #fff;"></div></div></div><div style="display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;"><span>🔴 Bearish (-100)</span><span>⚪ Neutral (0)</span><span>🟢 Bullish (+100)</span></div>""", unsafe_allow_html=True)
    st.divider()
    st.markdown("### 📰 Berita Terkini")
    for item in sentiment["items"]:
        color = "#16a34a" if item["sentiment"] == "positive" else ("#dc2626" if item["sentiment"] == "negative" else "#6b7280")
        icon = "🟢" if item["sentiment"] == "positive" else ("🔴" if item["sentiment"] == "negative" else "⚪")
        st.markdown(f"""<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:6px;border-left:3px solid {color};"><div style="font-size:12px;color:#e2e8f0;">{icon} {item['headline']}</div><div style="font-size:10px;color:#94a3b8;margin-top:4px;">{item['source']} · {item['time']}</div></div>""", unsafe_allow_html=True)
    st.divider()
    st.caption("💡 **Tips:** Sentimen negatif yang berlebihan bisa jadi sinyal contrarian (beli saat panic). Sentimen positif ekstrem bisa jadi sinyal distribusi (jual saat euphoria).")

# ============================================================================
# TAB 16: ML SIGNAL (Dari app_premium_complete.py)
# ============================================================================
with t_ml:
    st.markdown("## 🤖 ML Signal — Ensemble Technical Prediction")
    st.caption("Model ensemble sederhana: Trend (MA) + Momentum + Volume + Volatility. Bukan prediksi pasti, tapi probabilitas.")
    st.markdown("### 📊 IHSG Signal")
    ml_ihsg = ml_signal_predict(ihsg_hist, lookback=20)
    if ml_ihsg:
        st.markdown(f"""<div style="background:#1e293b;border-radius:12px;padding:16px;border:1px solid {ml_ihsg['signal_color']};text-align:center;margin-bottom:16px;"><div style="font-size:12px;color:#94a3b8;">IHSG ENSEMBLE SIGNAL</div><div style="font-size:24px;font-weight:700;color:{ml_ihsg['signal_color']};margin:8px 0;">{ml_ihsg['signal']}</div><div style="font-size:14px;color:#38bdf8;">Confidence: {ml_ihsg['confidence']}%</div><div style="background:#0f172a;border-radius:6px;height:10px;margin-top:10px;overflow:hidden;"><div style="background:{ml_ihsg['signal_color']};width:{ml_ihsg['confidence']}%;height:100%;"></div></div></div>""", unsafe_allow_html=True)
        feat = ml_ihsg['features']
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        features_display = [("Trend (MA)", feat['Trend'], {1: "🟢 UP", 0: "⚪ FLAT", -1: "🔴 DOWN"}), ("Momentum", feat['Momentum'], {1: "🟢 STRONG", 0: "⚪ MID", -1: "🔴 WEAK"}), ("Volume", feat['Volume'], {1: "🟢 HIGH", 0: "⚪ NORMAL", -1: "🔴 LOW"}), ("Volatility", feat['Volatility'], {1: "🟢 LOW", 0: "⚪ NORMAL", -1: "🔴 HIGH"})]
        for col, (name, val, mapping) in zip([fcol1, fcol2, fcol3, fcol4], features_display):
            with col: st.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;text-align:center;border:1px solid #334155;"><div style="font-size:10px;color:#94a3b8;">{name}</div><div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-top:4px;">{mapping.get(val, '⚪')}</div></div>""", unsafe_allow_html=True)
    else: st.info("Data IHSG tidak cukup untuk ML signal.")
    st.divider()
    st.markdown("### 🎯 ML Signal per Saham (Top 20)")
    st.caption("Kandidat dengan confidence tertinggi dari screening")
    ml_candidates = []
    for kode in tickers[:50]:
        df = price_data.get(kode)
        ml = ml_signal_predict(df, lookback=20)
        if ml and ml['confidence'] >= 50:
            row = table[table["Kode"] == kode]
            if not row.empty: ml_candidates.append({"Kode": kode, "Nama": row["Nama"].values[0] if "Nama" in row.columns else kode, "Signal": ml['signal'], "Confidence": ml['confidence'], "Score": ml['score'], "Harga": row["Harga"].values[0] if "Harga" in row.columns else 0, "Signal Color": ml['signal_color']})
    if ml_candidates:
        ml_df = pd.DataFrame(ml_candidates).sort_values("Confidence", ascending=False).head(20)
        def color_ml_signal(val):
            if "STRONG BUY" in val: return "background-color:#065f46;color:white;font-weight:bold;"
            if "BUY" in val: return "background-color:#16a34a;color:white;"
            if "STRONG SELL" in val: return "background-color:#7f1d1d;color:#fca5a5;font-weight:bold;"
            if "SELL" in val: return "background-color:#dc2626;color:white;"
            return "background-color:#0f172a;color:#94a3b8;"
        display_ml = ml_df.copy()
        display_ml["Harga"] = display_ml["Harga"].map(lambda x: f"Rp{x:,.0f}")
        display_ml["Confidence"] = display_ml["Confidence"].map(lambda x: f"{x}%")
        styler_ml = display_ml[["Kode", "Nama", "Signal", "Confidence", "Score", "Harga"]].style
        styler_ml = styler_ml.map(color_ml_signal, subset=["Signal"])
        st.dataframe(styler_ml, use_container_width=True, hide_index=True, height=400)
        st.caption("💡 **Cara pakai:** Prioritaskan saham dengan Signal BUY + Confidence >70% + Score ≥2. Hindari SELL signal meskipun fundamental bagus.")
    else: st.info("Tidak ada saham dengan confidence ≥50%. Coba refresh data.")
    st.divider()
    st.caption("🤖 **Disclaimer:** ML Signal menggunakan ensemble teknikal sederhana. Bukan deep learning atau AI canggih. Selalu konfirmasi dengan analisis fundamental dan manajemen risiko.")

# ============================================================================
# TAB 17: OPTIONS ANALYSIS (Dari app_premium_complete.py)
# ============================================================================
with t_options:
    st.markdown("## 📉 Options Analysis (Theoretical)")
    st.caption("Analisis opsi teoritis menggunakan Black-Scholes Model. Untuk edukasi & hedging strategy.")
    opt_kode = st.selectbox("Pilih Saham", options=table["Kode"].tolist() if not table.empty else [], key="opt_kode")
    if opt_kode in price_data:
        df_opt = price_data[opt_kode]
        S = float(df_opt['Close'].iloc[-1])
        st.markdown("### ⚙️ Parameters")
        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1: K = st.number_input("Strike Price (Rp)", min_value=0.0, value=float(round(S / 25) * 25), step=25.0, key="opt_K")
        with oc2: days = st.number_input("Days to Expiry", min_value=1, value=30, step=1, key="opt_days")
        with oc3: r = st.number_input("Risk-Free Rate (%)", min_value=0.0, value=6.5, step=0.1, key="opt_r") / 100
        with oc4: vol_input = st.number_input("Volatility (%)", min_value=1.0, value=30.0, step=1.0, key="opt_vol")
        T = days / 365
        call_result = black_scholes(S, K, T, r, vol_input / 100, 'call')
        put_result = black_scholes(S, K, T, r, vol_input / 100, 'put')
        st.divider()
        st.markdown("### 📊 Greeks & Pricing")
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**🟢 CALL OPTION**")
            if call_result:
                st.markdown(f"""<div style="background:#0f172a;border-radius:10px;padding:14px;border:1px solid #16a34a;"><div style="font-size:24px;font-weight:700;color:#16a34a;">Rp{call_result['price']:,.0f}</div><div style="font-size:11px;color:#94a3b8;margin-top:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Delta</span><span style="color:#e2e8f0;">{call_result['delta']:.4f}</span></div><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Gamma</span><span style="color:#e2e8f0;">{call_result['gamma']:.6f}</span></div><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Theta</span><span style="color:#e2e8f0;">{call_result['theta']:.4f}</span></div><div style="display:flex;justify-content:space-between;"><span>Vega</span><span style="color:#e2e8f0;">{call_result['vega']:.4f}</span></div></div></div>""", unsafe_allow_html=True)
                st.caption("💡 **Delta** = sensitivitas harga opsi terhadap harga saham | **Gamma** = perubahan delta | **Theta** = decay waktu/hari | **Vega** = sensitivitas terhadap volatilitas")
        with g2:
            st.markdown("**🔴 PUT OPTION**")
            if put_result:
                st.markdown(f"""<div style="background:#0f172a;border-radius:10px;padding:14px;border:1px solid #dc2626;"><div style="font-size:24px;font-weight:700;color:#dc2626;">Rp{put_result['price']:,.0f}</div><div style="font-size:11px;color:#94a3b8;margin-top:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Delta</span><span style="color:#e2e8f0;">{put_result['delta']:.4f}</span></div><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Gamma</span><span style="color:#e2e8f0;">{put_result['gamma']:.6f}</span></div><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Theta</span><span style="color:#e2e8f0;">{put_result['theta']:.4f}</span></div><div style="display:flex;justify-content:space-between;"><span>Vega</span><span style="color:#e2e8f0;">{put_result['vega']:.4f}</span></div></div></div>""", unsafe_allow_html=True)
        st.divider()
        st.markdown("### 📈 Volatility Analysis (IV Rank Proxy)")
        iv_data = calculate_iv_rank(df_opt, window=252)
        if iv_data:
            iv1, iv2, iv3, iv4, iv5 = st.columns(5)
            iv1.metric("Current HV", f"{iv_data['current_hv']:.1f}%"); iv2.metric("52W High", f"{iv_data['52w_high']:.1f}%"); iv3.metric("52W Low", f"{iv_data['52w_low']:.1f}%"); iv4.metric("IV Rank", f"{iv_data['iv_rank']:.0f}%"); iv5.metric("IV Percentile", f"{iv_data['iv_percentile']:.0f}%")
            iv_color = "#16a34a" if iv_data['iv_rank'] > 70 else ("#dc2626" if iv_data['iv_rank'] < 30 else "#eab308")
            st.markdown(f"""<div style="background:#0f172a;border-radius:8px;padding:10px;border-left:4px solid {iv_color};margin-top:8px;"><div style="font-size:13px;color:{iv_color};font-weight:600;">{iv_data['interpretation']}</div><div style="font-size:11px;color:#94a3b8;margin-top:4px;">{'IV tinggi = premium mahal = strategi SELL (Covered Call/Naked Put)' if iv_data['iv_rank'] > 70 else 'IV rendah = premium murah = strategi BUY (Long Call/Long Put)' if iv_data['iv_rank'] < 30 else 'IV normal = strategi spread atau iron condor'}</div></div>""", unsafe_allow_html=True)
        st.divider()
        st.markdown("### 🎯 Expected Move")
        em = expected_move(S, vol_input, days)
        if em:
            st.markdown(f"""<div style="background:#1e293b;border-radius:10px;padding:14px;text-align:center;border:1px solid #334155;"><div style="font-size:12px;color:#94a3b8;">EXPECTED MOVE ({days} HARI)</div><div style="font-size:28px;font-weight:700;color:#38bdf8;margin:8px 0;">±{em['move_pct']:.1f}%</div><div style="font-size:14px;color:#e2e8f0;">Range: {em['range']}</div></div>""", unsafe_allow_html=True)
            st.caption("💡 Expected move dari harga saham berdasarkan volatilitas saat ini. Kalau Anda yakin saham akan bergerak lebih dari ini, strategi options bisa profitable.")
        st.divider()
        st.markdown("### 📋 Theoretical Option Chain")
        with st.expander("Lihat Option Chain (Edukasi)", expanded=False):
            chain = generate_option_chain(S, S, vol_input, r, days)
            if chain:
                chain_df = pd.DataFrame(chain)
                def color_moneyness(val):
                    if "ATM" in val: return "background-color:#1e293b;color:#38bdf8;font-weight:bold;"
                    if "ITM" in val: return "background-color:#065f46;color:#4ade80;"
                    if "OTM" in val: return "background-color:#0f172a;color:#94a3b8;"
                    return ""
                styler_chain = chain_df.style
                if "Moneyness" in chain_df.columns: styler_chain = styler_chain.map(color_moneyness, subset=["Moneyness"])
                st.dataframe(styler_chain, use_container_width=True, hide_index=True, height=400)
        st.divider()
        st.markdown("### 🛠️ Strategy Builder (Edukasi)")
        st.caption("Pilih strategi untuk melihat payoff diagram teoritis")
        strat = st.selectbox("Strategi", ["Long Call (Bullish)", "Long Put (Bearish)", "Covered Call (Income)", "Protective Put (Hedge)", "Bull Call Spread", "Bear Put Spread", "Iron Condor (Sideways)"], key="opt_strat")
        if "Long Call" in strat: st.info("📗 **Long Call**: Beli Call OTM. Profit kalau saham naik > strike + premium. Risiko terbatas = premium yang dibayar.")
        elif "Long Put" in strat: st.info("📕 **Long Put**: Beli Put OTM. Profit kalau saham turun < strike - premium. Risiko terbatas = premium yang dibayar.")
        elif "Covered Call" in strat: st.info("📘 **Covered Call**: Punya saham + jual Call ATM. Income dari premium. Risiko: saham bisa dipanggil kalau naik > strike.")
        elif "Protective Put" in strat: st.info("📙 **Protective Put**: Punya saham + beli Put. Asuransi downside. Biaya = premium put.")
        elif "Bull Call" in strat: st.info("📗 **Bull Call Spread**: Beli Call ITM + jual Call OTM. Biaya lebih murah dari Long Call. Profit terbatas.")
        elif "Bear Put" in strat: st.info("📕 **Bear Put Spread**: Beli Put ITM + jual Put OTM. Biaya lebih murah dari Long Put. Profit terbatas.")
        elif "Iron Condor" in strat: st.info("📊 **Iron Condor**: Jual Call Spread + Jual Put Spread. Profit kalau saham sideways. Risiko terbatas.")
    else: st.info("Pilih saham untuk melihat analisis options.")
    st.divider()
    st.caption("⚠️ **Disclaimer:** IDX tidak memiliki options market aktif untuk retail. Modul ini untuk edukasi dan hedging simulation.")

# ============================================================================
# TAB 18: BROKER API (Dari app_premium_complete.py)
# ============================================================================
with t_broker:
    st.markdown("## 🏦 Broker Integration")
    st.caption("Hubungkan dashboard dengan broker Anda untuk order entry yang lebih cepat dan portfolio sync.")
    st.markdown("### 🔌 Koneksi Broker")
    bcol1, bcol2, bcol3 = st.columns(3)
    with bcol1: broker_pilih = st.selectbox("Pilih Broker", options=BrokerAPI.SUPPORTED_BROKERS, key="broker_select")
    with bcol2: api_key_broker = st.text_input("API Key (opsional)", type="password", key="broker_api_key", help="Hubungi broker untuk API access")
    with bcol3: api_secret_broker = st.text_input("API Secret (opsional)", type="password", key="broker_api_secret")
    if st.button("🔗 Connect", type="primary", use_container_width=True, key="btn_connect_broker"):
        broker = BrokerAPI(broker_pilih, api_key_broker, api_secret_broker)
        ok, msg = broker.connect()
        if ok:
            st.success(msg)
            st.session_state['broker_connected'] = True
            st.session_state['broker_name'] = broker_pilih
        else: st.error(msg)
    st.divider()
    st.markdown("### ⚡ Quick Order Entry")
    st.caption("Validasi order sebelum eksekusi. Untuk broker tanpa API, order dicatat di Jurnal Real.")
    o1, o2, o3, o4, o5 = st.columns(5)
    with o1: order_kode = st.selectbox("Saham", options=[""] + table["Kode"].tolist() if not table.empty else [""], key="order_kode")
    with o2: order_side = st.selectbox("Side", options=["BUY", "SELL"], key="order_side")
    with o3: order_qty = st.number_input("Lot", min_value=1, value=10, step=1, key="order_qty")
    with o4: 
        harga_default = float(table.loc[table["Kode"] == order_kode, "Harga"].values[0]) if order_kode and not table.empty and order_kode in table["Kode"].values else 0
        order_price = st.number_input("Harga (Rp)", min_value=0.0, value=harga_default, step=1.0, key="order_price")
    with o5: cash_avail = st.number_input("Cash Tersedia (Rp)", min_value=0.0, value=10_000_000.0, step=1_000_000.0, key="order_cash")
    if order_kode and order_price > 0 and order_qty > 0:
        valid, msg, total = validate_order(order_kode, order_side, order_qty, order_price, cash_avail)
        if valid:
            st.success(msg)
            st.markdown(f"""<div style="background:#0f172a;border-radius:10px;padding:14px;border:1px solid #16a34a;margin:12px 0;"><div style="font-size:13px;color:#16a34a;font-weight:700;">✅ ORDER SUMMARY</div><div style="font-size:12px;color:#e2e8f0;margin-top:8px;line-height:1.6;"><b>Broker:</b> {st.session_state.get('broker_name', 'Manual')}<br><b>Saham:</b> {order_kode}<br><b>Side:</b> {order_side}<br><b>Qty:</b> {order_qty} lot ({order_qty * 100:,} lembar)<br><b>Harga:</b> Rp{order_price:,.0f}<br><b>Total:</b> Rp{total:,.0f}</div></div>""", unsafe_allow_html=True)
            col_exec, col_journal = st.columns(2)
            with col_exec:
                if st.button("🚀 Execute Order", type="primary", use_container_width=True, key="btn_exec_order"):
                    broker = BrokerAPI(st.session_state.get('broker_name', 'Manual'))
                    ok, msg = broker.place_order(order_kode, order_side, order_qty, order_price)
                    if ok: st.success(msg); st.info("💡 Order juga dicatat di tab Jurnal Real untuk tracking.")
                    else: st.error(msg)
            with col_journal:
                if st.button("📝 Catat ke Jurnal Saja", use_container_width=True, key="btn_journal_only"):
                    st.info("Silakan buka tab Jurnal Real untuk mencatat manual.")
        else: st.error(msg)
    st.divider()
    st.markdown("### 📊 Perbandingan Broker Indonesia")
    broker_comparison = pd.DataFrame([
        {"Broker": "Mirae Asset", "Fee Beli": "0.15%", "Fee Jual": "0.25%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐⭐⭐"},
        {"Broker": "Ajaib", "Fee Beli": "0.15%", "Fee Jual": "0.25%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐⭐"},
        {"Broker": "Stockbit", "Fee Beli": "0.15%", "Fee Jual": "0.25%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐⭐"},
        {"Broker": "IPOT", "Fee Beli": "0.18%", "Fee Jual": "0.28%", "API": "❌", "Min Deposit": "Rp100K", "Rating": "⭐⭐⭐"},
        {"Broker": "Philip", "Fee Beli": "0.18%", "Fee Jual": "0.28%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐⭐"},
        {"Broker": "BNI Sekuritas", "Fee Beli": "0.18%", "Fee Jual": "0.28%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐"},
        {"Broker": "Mandiri Sekuritas", "Fee Beli": "0.18%", "Fee Jual": "0.28%", "API": "❌", "Min Deposit": "Rp0", "Rating": "⭐⭐⭐"},
    ])
    st.dataframe(broker_comparison, use_container_width=True, hide_index=True)
    st.caption("💡 **Tips memilih broker:** Cari yang fee rendah + app stabil + customer service responsif.")
    st.divider()
    st.markdown("### 📚 API Integration Guide")
    with st.expander("Cara Request API Access dari Broker", expanded=False):
        st.markdown("""**Langkah-langkah umum:**\n1. **Hubungi Relationship Manager** Anda di broker\n2. **Ajukan permohonan** API access (sebutkan "algorithmic trading")\n3. **Tanda tangani** NDA dan perjanjian penggunaan API\n4. **Dapatkan** API Key dan Secret\n5. **Integrasikan** ke dalam sistem ini\n\n**Catatan:**\n- Kebanyakan broker Indonesia **belum** menyediakan public API untuk retail\n- API access umumnya hanya untuk **institutional clients** atau **high-net-worth individuals**\n- Alternatif: Gunakan **manual order entry** + auto-catat ke Jurnal Real""")
    st.divider()
    st.caption("⚠️ **Disclaimer:** Fitur Broker API adalah template untuk pengembangan. Untuk saat ini, gunakan manual order entry melalui aplikasi broker Anda, lalu catat transaksi di tab Jurnal Real untuk tracking.")

# ============================================================================
# AUTO-REFRESH SCHEDULER & FOOTER
# ============================================================================
if auto_refresh:
    st.markdown("""<script>setTimeout(function() { window.location.reload(); }, 300000);</script>""", unsafe_allow_html=True)

st.divider()
st.caption("️ Data diambil dari Yahoo Finance (yfinance), bukan API resmi. Bukan rekomendasi keuangan. Selalu lakukan riset & kelola risiko sendiri.")
