"""
Modul screener saham IDX.
Logika skor di sini SENGAJA dibuat identik dengan sheet SAHAM di
IDX_Screener_Bot_diperbaiki.xlsx supaya hasil web dashboard dan Excel konsisten.
TAMBAHAN: Quality Validator (Trend, Smart Money, Momentum) - TANPA scipy.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st

DEFAULT_PARAMS = {
    "min_value_traded": 3_000_000_000,
    "crash_veto": -0.05,
    "donchian_lookback": 20,
    "score_strong_buy": 7,
    "score_buy": 4,
    "score_sell": -2,
    "score_strong_sell": -4,
}


# ==============================================================================
# QUALITY VALIDATOR FUNCTIONS (TANPA scipy - pakai numpy polyfit)
# ==============================================================================

def _validate_trend_quality(df: pd.DataFrame, period: int = 10) -> dict:
    """Validasi kualitas trend menggunakan numpy polyfit (pengganti scipy linregress)."""
    if len(df) < period:
        return {"quality": "INSUFFICIENT", "stars": 0, "score": 0}
    
    closes = df["Close"].tail(period).values
    x = np.arange(len(closes), dtype=float)
    
    # Linear regression dengan numpy polyfit (pengganti scipy.stats.linregress)
    try:
        coeffs = np.polyfit(x, closes, 1)
        slope = coeffs[0]
        intercept = coeffs[1]
        
        # Hitung R-squared manual
        y_pred = slope * x + intercept
        ss_res = np.sum((closes - y_pred) ** 2)
        ss_tot = np.sum((closes - np.mean(closes)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    except Exception:
        return {"quality": "INSUFFICIENT", "stars": 0, "score": 0}
    
    # Hitung angle
    angle_degrees = np.degrees(np.arctan(slope / abs(intercept) if intercept != 0 else slope))
    
    # Cek posisi terhadap MA20
    ma20 = df["Close"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
    current_price = closes[-1]
    above_ma20 = current_price > ma20 if ma20 else False
    
    score = 0
    if angle_degrees >= 45: score += 40
    elif angle_degrees >= 30: score += 30
    elif angle_degrees >= 15: score += 20
    elif angle_degrees >= 5: score += 10
    
    if r_squared >= 0.8: score += 30
    elif r_squared >= 0.6: score += 20
    elif r_squared >= 0.4: score += 10
    
    if above_ma20: score += 30
    
    if score >= 80: return {"quality": "STRONG", "stars": 3, "score": score}
    elif score >= 50: return {"quality": "MODERATE", "stars": 2, "score": score}
    elif score >= 25: return {"quality": "WEAK", "stars": 1, "score": score}
    return {"quality": "NO_TREND", "stars": 0, "score": score}


def _detect_smart_money(df: pd.DataFrame, period: int = 20) -> dict:
    """Deteksi akumulasi institusi."""
    if len(df) < period:
        return {"status": "INSUFFICIENT", "score": 0}
    
    recent = df.tail(period).copy()
    price_changes = recent["Close"].pct_change().dropna()
    volume_changes = recent["Volume"].pct_change().dropna()
    
    common_idx = price_changes.index.intersection(volume_changes.index)
    if len(common_idx) >= 5:
        correlation = price_changes[common_idx].corr(volume_changes[common_idx])
        vol_price_score = max(0, correlation) * 100
    else:
        vol_price_score = 0
    
    candle_range = recent["High"] - recent["Low"]
    candle_range = candle_range.replace(0, np.nan)
    close_position = (recent["Close"] - recent["Low"]) / candle_range
    close_position = close_position.fillna(0.5)
    close_score = close_position.mean() * 100
    
    lows = recent["Low"].values
    higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
    hl_score = (higher_lows / (len(lows) - 1) if len(lows) > 1 else 0) * 100
    
    total_score = (vol_price_score * 0.40) + (close_score * 0.35) + (hl_score * 0.25)
    
    if total_score >= 70: return {"status": "ACCUMULATING", "score": total_score}
    elif total_score >= 50: return {"status": "NEUTRAL", "score": total_score}
    return {"status": "DISTRIBUTING", "score": total_score}


def _validate_momentum(df: pd.DataFrame, max_lookback: int = 5) -> dict:
    """Validasi momentum."""
    if len(df) < 2:
        return {"strength": "NONE", "days": 0}
    
    closes = df["Close"].tail(max_lookback + 1).values
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i-1]:
            streak += 1
        else:
            break
            
    if streak >= 4: return {"strength": "VERY_STRONG", "days": streak}
    elif streak >= 3: return {"strength": "STRONG", "days": streak}
    elif streak >= 2: return {"strength": "MODERATE", "days": streak}
    elif streak >= 1: return {"strength": "WEAK", "days": streak}
    return {"strength": "NONE", "days": 0}


def get_quality_rating(df: pd.DataFrame) -> dict:
    """Gabungkan semua validasi menjadi satu rating."""
    trend = _validate_trend_quality(df)
    smart_money = _detect_smart_money(df)
    momentum = _validate_momentum(df)
    
    overall_score = (trend["score"] * 0.40) + (smart_money["score"] * 0.35) + ((momentum["days"] / 5 * 100) * 0.25)
    
    if overall_score >= 75:
        return {"rating": "HIGH", "emoji": "✅", "score": round(overall_score, 1), "trend_stars": trend["stars"], "smart_money_status": smart_money["status"], "momentum_strength": momentum["strength"]}
    elif overall_score >= 50:
        return {"rating": "MODERATE", "emoji": "⚠️", "score": round(overall_score, 1), "trend_stars": trend["stars"], "smart_money_status": smart_money["status"], "momentum_strength": momentum["strength"]}
    else:
        return {"rating": "LOW", "emoji": "❌", "score": round(overall_score, 1), "trend_stars": trend["stars"], "smart_money_status": smart_money["status"], "momentum_strength": momentum["strength"]}


# ==============================================================================
# FUNGSI SCREENER ASLI (Dipertahankan 100%)
# ==============================================================================

@st.cache_data(show_spinner=False)
def load_ticker_universe(path: str = "tickers_idx.csv") -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_price_history(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    yf_tickers = [f"{t}.JK" for t in tickers]
    chunk_size = 80
    for i in range(0, len(yf_tickers), chunk_size):
        chunk = yf_tickers[i : i + chunk_size]
        try:
            data = yf.download(
                chunk, period=period, interval="1d",
                group_by="ticker", threads=True, progress=False, auto_adjust=False,
            )
        except Exception:
            continue
        for yft in chunk:
            kode = yft.replace(".JK", "")
            try:
                df = data[yft] if len(chunk) > 1 else data
                df = df.dropna(how="all")
                if not df.empty and "Close" in df.columns:
                    results[kode] = df
            except Exception:
                continue
    return results


def compute_metrics(df: pd.DataFrame, params: dict) -> dict | None:
    lookback = params["donchian_lookback"]
    if df is None or len(df) < lookback + 2:
        return None

    df = df.dropna(subset=["Close", "High", "Low", "Volume"])
    if len(df) < lookback + 2:
        return None

    last = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"]
    close = float(last["Close"])
    if prev_close == 0 or pd.isna(prev_close):
        return None

    change_pct = (close - prev_close) / prev_close
    volume = float(last["Volume"])
    avg_volume20 = float(df["Volume"].tail(20).mean())
    value_traded = close * avg_volume20
    layak_likuiditas = value_traded >= params["min_value_traded"]
    vol_ratio = (volume / avg_volume20) if avg_volume20 > 0 else 0

    hist = df.iloc[-(lookback + 1) : -1]
    donchian_high = float(hist["High"].max())
    donchian_low = float(hist["Low"].min())
    if close > donchian_high:
        breakout_status = "BREAKOUT"
    elif close < donchian_low:
        breakout_status = "BREAKDOWN"
    else:
        breakout_status = "NETRAL"

    is_crash = change_pct < params["crash_veto"]

    if not layak_likuiditas:
        score = -99
    elif is_crash:
        score = -50
    else:
        score = 0
        score += 1 if change_pct > 0 else 0
        score += 1 if change_pct > 0.02 else 0
        score += 1 if change_pct > 0.05 else 0
        score += -1 if change_pct < 0 else 0
        score += -1 if change_pct < -0.02 else 0
        score += 3 if vol_ratio > 1.5 else (2 if vol_ratio > 1 else 0)
        score += 2 if vol_ratio > 3 else 0
        score += 3 if breakout_status == "BREAKOUT" else (-2 if breakout_status == "BREAKDOWN" else 0)

    if score == -99:
        signal = "SKIP (ILIKUID)"
    elif score == -50:
        signal = "SKIP (CRASH VETO)"
    elif score >= params["score_strong_buy"]:
        signal = "STRONG BUY"
    elif score >= params["score_buy"]:
        signal = "BUY"
    elif score <= params["score_strong_sell"]:
        signal = "STRONG SELL"
    elif score <= params["score_sell"]:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "Harga": close,
        "Perubahan %": change_pct,
        "Volume": volume,
        "Avg Volume 20D": avg_volume20,
        "Value Traded (Rp)": value_traded,
        "Volume Ratio": vol_ratio,
        "Donchian High": donchian_high,
        "Donchian Low": donchian_low,
        "Status Breakout": breakout_status,
        "Layak Likuiditas": layak_likuiditas,
        "Score": score,
        "Signal": signal,
    }


def build_screener_table(price_data: dict[str, pd.DataFrame], names: pd.DataFrame, params: dict) -> pd.DataFrame:
    rows = []
    name_map = dict(zip(names["Kode"], names["Nama"]))
    
    for kode, df in price_data.items():
        m = compute_metrics(df, params)
        if m is None:
            continue
        
        # === QUALITY VALIDATION (TAMBAHAN BARU) ===
        try:
            if len(df) >= 20:
                quality = get_quality_rating(df)
            else:
                quality = {"rating": "INSUFFICIENT", "emoji": "", "score": 0, "trend_stars": 0, "smart_money_status": "N/A", "momentum_strength": "N/A"}
        except Exception:
            quality = {"rating": "INSUFFICIENT", "emoji": "", "score": 0, "trend_stars": 0, "smart_money_status": "N/A", "momentum_strength": "N/A"}
        
        m["Kode"] = kode
        m["Nama"] = name_map.get(kode, "")
        
        m["Quality"] = f"{quality['emoji']} {quality['rating']}"
        m["Quality Score"] = quality["score"]
        m["Trend"] = "⭐" * quality["trend_stars"]
        m["Smart Money"] = quality["smart_money_status"]
        m["Momentum"] = quality["momentum_strength"]
        
        rows.append(m)
        
    if not rows:
        return pd.DataFrame()
        
    out = pd.DataFrame(rows)
    out["Chart"] = out["Kode"].map(tradingview_url)
    
    cols = [
        "Kode", "Nama", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)",
        "Status Breakout", "Chart", "Layak Likuiditas", "Score", "Signal", 
        "Quality", "Quality Score", "Trend", "Smart Money", "Momentum",
        "Donchian High", "Donchian Low", "Avg Volume 20D", "Volume"
    ]
    
    existing_cols = [c for c in cols if c in out.columns]
    out = out[existing_cols].sort_values("Score", ascending=False).reset_index(drop=True)
    return out


def classify_daytrading_tipe(now=None) -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        now = now or datetime.now(ZoneInfo("Asia/Jakarta"))
    except Exception:
        now = now or datetime.now()
    return "BPJS" if now.hour < 13 else "BSJP"


def tradingview_url(kode: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol=IDX%3A{kode}"


def _donchian_levels(df: pd.DataFrame, lookback: int):
    if df is None or len(df) < lookback + 2:
        return None, None
    hist = df.iloc[-(lookback + 1) : -1]
    return float(hist["High"].max()), float(hist["Low"].min())


def build_trade_candidates(table: pd.DataFrame, price_data: dict, lookback: int, min_rr: float = 2.0,
                            top_n: int = 10, signal_filter=("STRONG BUY", "BUY")) -> pd.DataFrame:
    rows = []
    picks = table[table["Signal"].isin(signal_filter)]
    for _, r in picks.iterrows():
        kode = r["Kode"]
        df = price_data.get(kode)
        dh, dl = _donchian_levels(df, lookback)
        if dh is None or dl is None or dl <= 0:
            continue
        entry = float(r["Harga"])
        sl = dl
        if entry <= sl:
            continue
        target = dh + (dh - dl)
        risk = entry - sl
        reward = target - entry
        if risk <= 0 or reward <= 0:
            continue
        rr = reward / risk
        if rr < min_rr:
            continue
        rows.append({
            "Saham": kode, "RR": round(rr, 2), "Entry": round(entry, 0),
            "Target": round(target, 0), "Stop Loss": round(sl, 0),
            "Score": int(r["Score"]), "Nilai Transaksi": r["Value Traded (Rp)"],
            "Chart": tradingview_url(kode),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["RR", "Score"], ascending=[False, False]).head(top_n).reset_index(drop=True)


def market_regime(ihsg_df: pd.DataFrame, ma_period: int = 50) -> dict:
    if ihsg_df is None or ihsg_df.empty or len(ihsg_df) < ma_period:
        return {"status": "UNKNOWN", "close": None, "ma": None}
    close = float(ihsg_df["Close"].iloc[-1])
    ma = float(ihsg_df["Close"].rolling(ma_period).mean().iloc[-1])
    if pd.isna(ma):
        return {"status": "UNKNOWN", "close": close, "ma": None}
    status = "BULLISH" if close > ma else "BEARISH"
    return {"status": status, "close": close, "ma": ma}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ihsg_history(period: str = "1y") -> pd.DataFrame:
    try:
        df = yf.download("^JKSE", period=period, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()
