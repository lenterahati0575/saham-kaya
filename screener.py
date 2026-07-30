"""
Modul screener saham IDX.
Logika skor di sini SENGAJA dibuat identik dengan sheet SAHAM di
IDX_Screener_Bot_diperbaiki.xlsx supaya hasil web dashboard dan Excel konsisten:
- Gate likuiditas (Value Traded = Harga x Avg Volume 20D)
- Skor momentum berbasis perubahan % (skala desimal, bukan persen bulat)
- Skor volume ratio (volume hari ini / rata-rata 20 hari)
- Veto crash (penalti besar untuk penurunan tajam)
- Bonus/penalti Donchian Breakout 20 hari (TIDAK termasuk candle hari ini,
  sesuai prinsip 4-Weeks Rule Richard Donchian)

TAMBAHAN: Quality Validator dengan analisis Akumulasi/Distribusi, Trend Strength, 
Consecutive Higher Closes, dan Rekomendasi Trading Otomatis.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st

DEFAULT_PARAMS = {
    "min_value_traded": 3_000_000_000,   # Rp 3 miliar/hari - gate likuiditas
    "crash_veto": -0.05,                 # -5% - ambang veto crash
    "donchian_lookback": 20,             # 4 minggu bursa (~20 hari)
    "score_strong_buy": 7,
    "score_buy": 4,
    "score_sell": -2,
    "score_strong_sell": -4,
}


# ============================================================================
# QUALITY VALIDATOR FUNCTIONS
# ============================================================================

def _detect_accumulation_distribution(df: pd.DataFrame, period: int = 20) -> dict:
    """
    Deteksi fase Akumulasi atau Distribusi menggunakan metode profesional.
    Kombinasi: Price Action + Volume + Close Position + OBV
    """
    if len(df) < period:
        return {
            "phase": "INSUFFICIENT_DATA",
            "signal": "NEUTRAL",
            "score": 0,
            "details": {}
        }
    
    recent = df.tail(period).copy()
    
    # === 1. VOLUME-PRICE RELATIONSHIP ===
    price_changes = recent["Close"].pct_change().dropna()
    volume_changes = recent["Volume"].pct_change().dropna()
    
    common_idx = price_changes.index.intersection(volume_changes.index)
    if len(common_idx) >= 5:
        correlation = price_changes[common_idx].corr(volume_changes[common_idx])
    else:
        correlation = 0
    
    # === 2. CLOSE POSITION IN CANDLE ===
    candle_range = recent["High"] - recent["Low"]
    candle_range = candle_range.replace(0, np.nan)
    close_position = (recent["Close"] - recent["Low"]) / candle_range
    close_position = close_position.fillna(0.5)
    avg_close_position = close_position.mean()
    
    # === 3. HIGHER LOWS ===
    highs = recent["High"].values
    lows = recent["Low"].values
    
    higher_lows = 0
    for i in range(1, len(lows)):
        if lows[i] > lows[i-1]:
            higher_lows += 1
    
    hl_ratio = higher_lows / (len(lows) - 1) if len(lows) > 1 else 0.5
    
    # === 4. ON BALANCE VOLUME (OBV) TREND ===
    obv = 0
    obv_values = []
    
    for i in range(len(recent)):
        if i == 0:
            obv_values.append(0)
            continue
        
        if recent["Close"].iloc[i] > recent["Close"].iloc[i-1]:
            obv += recent["Volume"].iloc[i]
        elif recent["Close"].iloc[i] < recent["Close"].iloc[i-1]:
            obv -= recent["Volume"].iloc[i]
        
        obv_values.append(obv)
    
    if len(obv_values) >= 5:
        obv_trend = 1 if obv_values[-1] > obv_values[-5] else -1
    else:
        obv_trend = 0
    
    # === SCORING SYSTEM ===
    total_score = 0
    
    vol_price_score = ((correlation + 1) / 2) * 100
    total_score += vol_price_score * 0.30
    
    close_score = avg_close_position * 100
    total_score += close_score * 0.25
    
    hl_score = hl_ratio * 100
    total_score += hl_score * 0.25
    
    obv_score = 100 if obv_trend > 0 else 0
    total_score += obv_score * 0.20
    
    # === KLASIFIKASI ===
    if total_score >= 65:
        phase = "ACCUMULATION"
        signal = "STRONG_BUY"
    elif total_score >= 50:
        phase = "ACCUMULATION"
        signal = "BUY"
    elif total_score >= 40:
        phase = "NEUTRAL"
        signal = "HOLD"
    elif total_score >= 25:
        phase = "DISTRIBUTION"
        signal = "SELL"
    else:
        phase = "DISTRIBUTION"
        signal = "STRONG_SELL"
    
    return {
        "phase": phase,
        "signal": signal,
        "score": round(total_score, 1),
        "details": {
            "correlation": round(correlation, 3),
            "close_position": round(avg_close_position, 3),
            "higher_lows_ratio": round(hl_ratio, 3),
            "obv_trend": "RISING" if obv_trend > 0 else "FALLING",
            "vol_price_score": round(vol_price_score, 1),
            "close_score": round(close_score, 1),
            "hl_score": round(hl_score, 1),
        }
    }


def _validate_trend_strength(df: pd.DataFrame, period: int = 10) -> dict:
    """
    Validasi kekuatan trend menggunakan multi-timeframe MA analysis.
    """
    if len(df) < 50:
        return {"strength": "INSUFFICIENT", "score": 0, "stars": 0}
    
    closes = df["Close"]
    current_price = float(closes.iloc[-1])
    
    ma5 = closes.rolling(5).mean()
    ma20 = closes.rolling(20).mean()
    ma50 = closes.rolling(50).mean()
    
    ma5_current = ma5.iloc[-1]
    ma20_current = ma20.iloc[-1]
    ma50_current = ma50.iloc[-1]
    
    score = 0
    stars = 0
    
    # === 1. PRICE POSITION (0-40 points) ===
    if current_price > ma5_current:
        score += 10
    if current_price > ma20_current:
        score += 15
    if current_price > ma50_current:
        score += 15
    
    # === 2. MA ALIGNMENT (0-35 points) ===
    if ma5_current > ma20_current > ma50_current:
        score += 35
        stars = 3
    elif ma5_current > ma20_current:
        score += 20
        stars = 2
    elif ma20_current > ma50_current:
        score += 10
        stars = 1
    elif ma5_current < ma20_current < ma50_current:
        score += 0
        stars = 0
    else:
        score += 5
        stars = 1
    
    # === 3. MOMENTUM (0-25 points) ===
    distance_from_ma20 = ((current_price - ma20_current) / ma20_current) * 100
    
    if distance_from_ma20 >= 10:
        score += 25
    elif distance_from_ma20 >= 5:
        score += 20
    elif distance_from_ma20 >= 2:
        score += 12
    elif distance_from_ma20 >= 0:
        score += 5
    
    # === KLASIFIKASI ===
    if score >= 75:
        strength = "VERY_STRONG"
    elif score >= 55:
        strength = "STRONG"
    elif score >= 35:
        strength = "MODERATE"
    elif score >= 15:
        strength = "WEAK"
    else:
        strength = "NO_TREND"
    
    return {
        "strength": strength,
        "score": round(score, 1),
        "stars": stars,
        "details": {
            "distance_from_ma20_pct": round(distance_from_ma20, 2),
            "ma_alignment": "BULLISH" if ma5_current > ma20_current > ma50_current else "BEARISH" if ma5_current < ma20_current < ma50_current else "MIXED"
        }
    }


def _count_consecutive_higher_closes(df: pd.DataFrame, max_lookback: int = 10) -> dict:
    """
    Hitung jumlah hari berturut-turut dengan close lebih tinggi.
    Indikator momentum jangka pendek.
    """
    if len(df) < 2:
        return {
            "streak": 0,
            "type": "NONE",
            "strength": "NONE",
            "score": 0,
            "volume_support": False
        }
    
    closes = df["Close"].tail(max_lookback + 1).values
    volumes = df["Volume"].tail(max_lookback + 1).values
    
    current_streak = 0
    streak_type = "NONE"
    
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i-1]:
            if streak_type == "LOWER":
                break
            streak_type = "HIGHER"
            current_streak += 1
        elif closes[i] < closes[i-1]:
            if streak_type == "HIGHER":
                break
            streak_type = "LOWER"
            current_streak += 1
        else:
            continue
    
    volume_support = False
    if current_streak > 0 and len(volumes) > current_streak:
        streak_volumes = volumes[-current_streak-1:-1] if current_streak > 0 else volumes[-1:]
        pre_streak_volumes = volumes[:-current_streak-1] if len(volumes) > current_streak + 1 else volumes
        
        if len(pre_streak_volumes) > 0:
            avg_streak_vol = np.mean(streak_volumes)
            avg_pre_vol = np.mean(pre_streak_volumes)
            volume_support = avg_streak_vol > avg_pre_vol
    
    score = 0
    if streak_type == "HIGHER":
        if current_streak >= 5 and volume_support:
            score = 100
            strength = "VERY_STRONG"
        elif current_streak >= 5:
            score = 80
            strength = "STRONG"
        elif current_streak >= 3 and volume_support:
            score = 70
            strength = "STRONG"
        elif current_streak >= 3:
            score = 50
            strength = "MODERATE"
        elif current_streak >= 2:
            score = 30
            strength = "WEAK"
        else:
            score = 10
            strength = "VERY_WEAK"
    else:
        strength = "VERY_WEAK"
        score = 0
    
    return {
        "streak": current_streak,
        "type": streak_type,
        "strength": strength,
        "score": score,
        "volume_support": volume_support
    }


def get_quality_rating(df: pd.DataFrame) -> dict:
    """
    FUNGSI UTAMA - Gabungkan semua analisis menjadi satu rating kualitas.
    """
    acc_dist = _detect_accumulation_distribution(df, period=20)
    trend = _validate_trend_strength(df, period=10)
    momentum = _count_consecutive_higher_closes(df, max_lookback=10)
    
    overall_score = (
        acc_dist["score"] * 0.40 +
        trend["score"] * 0.35 +
        momentum["score"] * 0.25
    )
    
    if overall_score >= 70:
        rating = "HIGH"
        emoji = "✅"
        color = "#16a34a"
    elif overall_score >= 45:
        rating = "MODERATE"
        emoji = "⚠️"
        color = "#eab308"
    else:
        rating = "LOW"
        emoji = "❌"
        color = "#dc2626"
    
    return {
        "rating": rating,
        "emoji": emoji,
        "color": color,
        "score": round(overall_score, 1),
        "trend_stars": trend["stars"],
        "smart_money_status": acc_dist["phase"],
        "momentum_strength": momentum["strength"],
        "details": {
            "accumulation_score": acc_dist["score"],
            "trend_score": trend["score"],
            "momentum_score": momentum["score"],
            "consecutive_closes": momentum["streak"],
            "volume_support": momentum["volume_support"]
        }
    }


def get_trade_recommendation(quality: dict) -> dict:
    """
    Analisis kombinasi semua faktor untuk memberikan rekomendasi trading.
    """
    try:
        rating = quality.get("rating", "LOW")
        trend_stars = quality.get("trend_stars", 0)
        smart_money = quality.get("smart_money_status", "N/A")
        momentum = quality.get("momentum_strength", "NONE")
        score = quality.get("score", 0)
        
        recommendation = "WAIT"
        confidence = 0
        reason = ""
        color = "#6b7280"
        emoji = "⏸️"
        
        # === KONDISI 1: DAY TRADE ===
        if (momentum in ["VERY_STRONG", "STRONG"] and 
            rating == "HIGH" and 
            smart_money == "ACCUMULATION" and
            trend_stars >= 2):
            recommendation = "DAY TRADE"
            confidence = 90
            reason = "Momentum kuat + Akumulasi + Trend positif"
            color = "#16a34a"
            emoji = "⚡"
        
        # === KONDISI 2: SWING TRADE (Ideal) ===
        elif (rating in ["HIGH", "MODERATE"] and 
              smart_money == "ACCUMULATION" and
              trend_stars >= 2):
            recommendation = "SWING TRADE"
            confidence = 75
            reason = "Trend kuat + Akumulasi, momentum perlu konfirmasi"
            color = "#2563eb"
            emoji = "🌊"
        
        # === KONDISI 3: SWING TRADE (Dengan catatan) ===
        elif (rating in ["HIGH", "MODERATE"] and 
              smart_money == "NEUTRAL" and
              trend_stars >= 2 and
              momentum in ["STRONG", "MODERATE"]):
            recommendation = "SWING TRADE"
            confidence = 60
            reason = "Trend bagus + Momentum ada, belum ada akumulasi jelas"
            color = "#3b82f6"
            emoji = "🌊"
        
        # === KONDISI 4: WAIT (Konsolidasi) ===
        elif (smart_money == "ACCUMULATION" and 
              (rating == "LOW" or trend_stars < 2)):
            recommendation = "WAIT"
            confidence = 50
            reason = "Ada akumulasi tapi trend/momentum belum konfirmasi"
            color = "#eab308"
            emoji = "⏸️"
        
        # === KONDISI 5: WAIT (Momentum lemah) ===
        elif momentum in ["VERY_WEAK", "WEAK"] and rating in ["MODERATE", "LOW"]:
            recommendation = "WAIT"
            confidence = 40
            reason = "Momentum lemah, tunggu konfirmasi"
            color = "#f59e0b"
            emoji = "⏸️"
        
        # === KONDISI 6: AVOID (Distribusi) ===
        elif smart_money == "DISTRIBUTION":
            recommendation = "AVOID"
            confidence = 80
            reason = "Institusi sedang distribusi - risiko tinggi!"
            color = "#dc2626"
            emoji = "🚫"
        
        # === KONDISI 7: WAIT (Default) ===
        else:
            recommendation = "WAIT"
            confidence = 30
            reason = "Sinyal tidak cukup kuat untuk entry"
            color = "#6b7280"
            emoji = "️"
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reason": reason,
            "color": color,
            "emoji": emoji,
            "display": f"{emoji} {recommendation}"
        }
        
    except Exception as e:
        return {
            "recommendation": "ERROR",
            "confidence": 0,
            "reason": f"Error: {str(e)}",
            "color": "#dc2626",
            "emoji": "❌",
            "display": " ERROR"
        }


# ============================================================================
# ORIGINAL SCREENER FUNCTIONS
# ============================================================================

@st.cache_data(show_spinner=False)
def load_ticker_universe(path: str = "tickers_idx.csv") -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_price_history(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Ambil histori harga batch dari Yahoo Finance."""
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
    """Hitung metrik & skor untuk satu saham dari histori harga."""
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
        
        # === QUALITY VALIDATION ===
        try:
            if len(df) >= 50:
                quality = get_quality_rating(df)
            else:
                quality = {
                    "rating": "INSUFFICIENT",
                    "emoji": "",
                    "score": 0,
                    "trend_stars": 0,
                    "smart_money_status": "N/A",
                    "momentum_strength": "N/A"
                }
        except Exception as e:
            print(f"Error quality validation for {kode}: {e}")
            quality = {
                "rating": "ERROR",
                "emoji": "⚠️",
                "score": 0,
                "trend_stars": 0,
                "smart_money_status": "ERROR",
                "momentum_strength": "ERROR"
            }
        
        # === REKOMENDASI TRADING ===
        try:
            rec = get_trade_recommendation(quality)
        except Exception as e:
            print(f"Error recommendation for {kode}: {e}")
            rec = {
                "recommendation": "ERROR",
                "confidence": 0,
                "reason": "Error",
                "color": "#dc2626",
                "emoji": "❌",
                "display": "❌ ERROR"
            }
        
        m["Kode"] = kode
        m["Nama"] = name_map.get(kode, "")
        
        # Kolom quality
        m["Quality"] = f"{quality['emoji']} {quality['rating']}"
        m["Quality Score"] = quality["score"]
        m["Trend"] = "⭐" * quality["trend_stars"]
        m["Smart Money"] = quality["smart_money_status"]
        m["Momentum"] = quality["momentum_strength"]
        
        # Kolom rekomendasi
        m["Rekomendasi"] = rec["display"]
        m["Confidence"] = f"{rec['confidence']}%"
        m["Alasan"] = rec["reason"]
        
        rows.append(m)
        
    if not rows:
        return pd.DataFrame()
        
    out = pd.DataFrame(rows)
    out["Chart"] = out["Kode"].map(tradingview_url)
    
    cols = [
        "Kode", "Nama", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)",
        "Status Breakout", "Chart", "Layak Likuiditas", "Score", "Signal", 
        "Rekomendasi", "Confidence", "Alasan",
        "Quality", "Quality Score", "Trend", "Smart Money", "Momentum",
        "Donchian High", "Donchian Low", "Avg Volume 20D", "Volume"
    ]
    
    existing_cols = [c for c in cols if c in out.columns]
    out = out[existing_cols].sort_values("Score", ascending=False).reset_index(drop=True)
    return out


def classify_daytrading_tipe(now=None) -> str:
    """BPJS (Beli Pagi Jual Sore) kalau sekarang pagi WIB, BSJP (Beli Sore Jual Pagi) kalau sore/malam."""
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
    """Donchian High/Low dari `lookback` hari SEBELUM hari ini (hari ini tidak dihitung)."""
    if df is None or len(df) < lookback + 2:
        return None, None
    hist = df.iloc[-(lookback + 1) : -1]
    return float(hist["High"].max()), float(hist["Low"].min())


def build_trade_candidates(table: pd.DataFrame, price_data: dict, lookback: int, min_rr: float = 2.0,
                            top_n: int = 10, signal_filter=("STRONG BUY", "BUY")) -> pd.DataFrame:
    """
    Entry = harga sekarang. Stop Loss = Donchian Low (lookback) - stop struktural, bukan persen tetap.
    Target = Donchian High + (Donchian High - Donchian Low) - proyeksi measured-move dari lebar channel.
    RR = (Target-Entry)/(Entry-SL), difilter RR >= min_rr supaya rasio untung:rugi benar-benar >2:1.
    """
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
    """Tentukan kondisi pasar keseluruhan (regime) dari IHSG."""
    if ihsg_df is None or ihsg_df.empty or len(ihsg_df) < ma_period:
        return {"status": "UNKNOWN", "close": None, "ma": None}
    close = float(ihsg_df["Close"].iloc[-1])
    ma = float(ihsg_df["Close"].rolling(ma_period).mean().iloc[-1])
    if pd.isna(ma):
        return {"status": "UNKNOWN", "close": close, "ma": None}
    status = "BULLISH" if close > ma else "BEARISH"
    return {"status": status, "close": close, "ma": ma}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ihsg_history(period: str = "3mo") -> pd.DataFrame:
    """Ambil histori IHSG (^JKSE) dari Yahoo Finance."""
    try:
        df = yf.download("^JKSE", period=period, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()
