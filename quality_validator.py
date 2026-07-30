"""
Quality Validator - Sistem validasi kualitas sinyal untuk pemula.
Tidak mengubah score utama, hanya memberikan label kualitas.
"""

import numpy as np
import pandas as pd
from scipy import stats


def validate_trend_quality(df: pd.DataFrame, period: int = 10) -> dict:
    """
    Validasi kualitas trend - apakah trend benar-benar kuat atau hanya noise?
    
    Untuk pemula: Trend yang baik harus memiliki:
    1. Angle yang cukup curam (>30°)
    2. Konsistensi tinggi (R² > 0.7)
    3. Di atas MA20 (konfirmasi trend menengah)
    """
    if len(df) < period:
        return {"quality": "INSUFFICIENT_DATA", "stars": 0, "details": {}}
    
    closes = df["Close"].tail(period).values
    x = np.arange(len(closes))
    
    # Linear regression
    slope, intercept, r_value, _, _ = stats.linregress(x, closes)
    
    # Hitung angle
    angle_degrees = np.degrees(np.arctan(slope / abs(intercept) if intercept != 0 else slope))
    r_squared = r_value ** 2
    
    # Cek posisi terhadap MA20
    ma20 = df["Close"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
    current_price = closes[-1]
    above_ma20 = current_price > ma20 if ma20 else False
    
    # Scoring
    score = 0
    
    # Angle score (0-40 points)
    if angle_degrees >= 45:
        score += 40
    elif angle_degrees >= 30:
        score += 30
    elif angle_degrees >= 15:
        score += 20
    elif angle_degrees >= 5:
        score += 10
    
    # Consistency score (0-30 points) - R²
    if r_squared >= 0.8:
        score += 30
    elif r_squared >= 0.6:
        score += 20
    elif r_squared >= 0.4:
        score += 10
    
    # MA20 confirmation (0-30 points)
    if above_ma20:
        score += 30
    
    # Klasifikasi
    if score >= 80:
        quality = "STRONG"
        stars = 3
    elif score >= 50:
        quality = "MODERATE"
        stars = 2
    elif score >= 25:
        quality = "WEAK"
        stars = 1
    else:
        quality = "NO_TREND"
        stars = 0
    
    return {
        "quality": quality,
        "stars": stars,
        "score": score,
        "details": {
            "angle": round(angle_degrees, 1),
            "r_squared": round(r_squared, 2),
            "above_ma20": above_ma20
        }
    }


def detect_smart_money(df: pd.DataFrame, period: int = 20) -> dict:
    """
    Deteksi apakah ada akumulasi institusi (smart money).
    
    Untuk pemula: Saham yang diakumulasi institusi biasanya:
    1. Volume tinggi saat harga naik (buying pressure)
    2. Close sering di upper half candle (buyers in control)
    3. Higher lows (support kuat)
    """
    if len(df) < period:
        return {"status": "INSUFFICIENT_DATA", "score": 0}
    
    recent = df.tail(period).copy()
    
    # Signal 1: Volume-Price Correlation
    price_changes = recent["Close"].pct_change().dropna()
    volume_changes = recent["Volume"].pct_change().dropna()
    
    # Align indices
    common_idx = price_changes.index.intersection(volume_changes.index)
    if len(common_idx) < 5:
        vol_price_score = 0
    else:
        correlation = price_changes[common_idx].corr(volume_changes[common_idx])
        vol_price_score = max(0, correlation) * 100  # 0-100
    
    # Signal 2: Close Position in Candle
    candle_range = recent["High"] - recent["Low"]
    candle_range = candle_range.replace(0, np.nan)
    close_position = (recent["Close"] - recent["Low"]) / candle_range
    close_position = close_position.fillna(0.5)
    avg_close_pos = close_position.mean()
    close_score = avg_close_pos * 100  # 0-100
    
    # Signal 3: Higher Lows
    lows = recent["Low"].values
    higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
    hl_ratio = higher_lows / (len(lows) - 1) if len(lows) > 1 else 0
    hl_score = hl_ratio * 100  # 0-100
    
    # Total score (weighted)
    total_score = (
        vol_price_score * 0.40 +  # 40% - paling penting
        close_score * 0.35 +      # 35%
        hl_score * 0.25           # 25%
    )
    
    # Klasifikasi
    if total_score >= 70:
        status = "ACCUMULATING"
    elif total_score >= 50:
        status = "NEUTRAL"
    else:
        status = "DISTRIBUTING"
    
    return {
        "status": status,
        "score": round(total_score, 1),
        "details": {
            "vol_price_corr": round(vol_price_score, 1),
            "close_position": round(close_score, 1),
            "higher_lows": round(hl_score, 1)
        }
    }


def validate_momentum(df: pd.DataFrame, max_lookback: int = 5) -> dict:
    """
    Validasi momentum - apakah ada kekuatan untuk lanjut naik?
    
    Untuk pemula: Momentum kuat ditandai dengan:
    1. Consecutive higher closes (3+ hari)
    2. Volume mendukung (naik saat harga naik)
    """
    if len(df) < 2:
        return {"strength": "NONE", "days": 0}
    
    closes = df["Close"].tail(max_lookback + 1).values
    volumes = df["Volume"].tail(max_lookback + 1).values
    
    # Hitung consecutive higher closes
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i-1]:
            streak += 1
        else:
            break
    
    # Cek apakah volume mendukung
    if streak > 0 and len(volumes) > streak:
        recent_volumes = volumes[-streak-1:-1] if streak > 0 else volumes[-1:]
        avg_volume = np.mean(volumes[:-streak-1]) if len(volumes) > streak + 1 else np.mean(volumes)
        volume_support = np.mean(recent_volumes) > avg_volume
    else:
        volume_support = False
    
    # Klasifikasi
    if streak >= 4 and volume_support:
        strength = "VERY_STRONG"
    elif streak >= 3:
        strength = "STRONG"
    elif streak >= 2:
        strength = "MODERATE"
    elif streak >= 1:
        strength = "WEAK"
    else:
        strength = "NONE"
    
    return {
        "strength": strength,
        "days": streak,
        "volume_support": volume_support
    }


def get_quality_rating(df: pd.DataFrame) -> dict:
    """
    Gabungkan semua validasi menjadi satu rating kualitas.
    
    Ini yang akan ditampilkan di tabel sebagai badge.
    """
    trend = validate_trend_quality(df)
    smart_money = detect_smart_money(df)
    momentum = validate_momentum(df)
    
    # Hitung overall quality score (0-100)
    overall_score = (
        trend["score"] * 0.40 +           # 40% trend quality
        smart_money["score"] * 0.35 +     # 35% smart money
        (momentum["days"] / 5 * 100) * 0.25  # 25% momentum
    )
    
    # Rating
    if overall_score >= 75:
        rating = "HIGH"
        emoji = "✅"
        color = "#16a34a"  # Green
    elif overall_score >= 50:
        rating = "MODERATE"
        emoji = "⚠️"
        color = "#eab308"  # Yellow
    else:
        rating = "LOW"
        emoji = "❌"
        color = "#dc2626"  # Red
    
    return {
        "rating": rating,
        "emoji": emoji,
        "color": color,
        "score": round(overall_score, 1),
        "trend_stars": trend["stars"],
        "smart_money_status": smart_money["status"],
        "momentum_strength": momentum["strength"],
        "details": {
            "trend": trend["details"],
            "smart_money": smart_money["details"],
            "momentum_days": momentum["days"]
        }
    }
