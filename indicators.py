import pandas as pd
import numpy as np

def find_swing_points(df, order=3):
    """Temukan swing high/low points"""
    if df is None or len(df) < order * 2 + 1:
        return pd.DataFrame(), pd.DataFrame()

    highs = df["High"].rolling(window=order*2+1, center=True).max()
    lows = df["Low"].rolling(window=order*2+1, center=True).min()

    sh = df[df["High"] == highs].copy()
    sl = df[df["Low"] == lows].copy()
    return sh, sl

def classify_swings(sh, sl):
    """Klasifikasi swing points"""
    swings = []

    for idx, row in sh.iterrows():
        swings.append({
            "Tanggal": idx,
            "Harga": row["High"],
            "Tipe": "H",
            "Label": "HH" if len(swings) == 0 or row["High"] > swings[-1]["Harga"] else "LH"
        })

    for idx, row in sl.iterrows():
        swings.append({
            "Tanggal": idx,
            "Harga": row["Low"],
            "Tipe": "L",
            "Label": "LL" if len([s for s in swings if s["Tipe"] == "L"]) == 0 or row["Low"] < [s for s in swings if s["Tipe"] == "L"][-1]["Harga"] else "HL"
        })

    df_swings = pd.DataFrame(swings)
    if not df_swings.empty:
        df_swings = df_swings.sort_values("Tanggal")
    return df_swings

def moving_averages_panel(df):
    """Panel Moving Averages"""
    close = df["Close"]
    results = []
    for period in [5, 10, 20, 50, 100, 200]:
        if len(close) >= period:
            ma = close.rolling(period).mean().iloc[-1]
            ema = close.ewm(span=period).mean().iloc[-1]
            action_s = "Buy" if close.iloc[-1] > ma else "Sell"
            action_e = "Buy" if close.iloc[-1] > ema else "Sell"
            results.append({
                "MA": f"MA{period}",
                "Simple": f"{action_s} ({ma:,.0f})",
                "Exponential": f"{action_e} ({ema:,.0f})",
            })

    summary = {"buy": 0, "sell": 0, "overall": "Neutral"}
    for r in results:
        if "Buy" in r["Simple"]:
            summary["buy"] += 1
        else:
            summary["sell"] += 1

    if summary["buy"] > summary["sell"]:
        summary["overall"] = "Buy"
    elif summary["sell"] > summary["buy"]:
        summary["overall"] = "Sell"

    return pd.DataFrame(results), summary

def technical_indicators_panel(df):
    """Panel Technical Indicators"""
    close = df["Close"]
    results = []

    # RSI approximation
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1] if not rsi.empty else 50
    rsi_action = "Buy" if rsi_val < 30 else "Sell" if rsi_val > 70 else "Neutral"
    results.append({"Indicator": "RSI(14)", "Value": f"{rsi_val:.1f}", "Action": rsi_action})

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    macd_action = "Buy" if macd.iloc[-1] > signal.iloc[-1] else "Sell"
    results.append({"Indicator": "MACD", "Value": f"{macd.iloc[-1]:,.0f}", "Action": macd_action})

    # Stochastic
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    k = 100 * (close - low14) / (high14 - low14)
    k_val = k.iloc[-1] if not k.empty else 50
    stoch_action = "Buy" if k_val < 20 else "Sell" if k_val > 80 else "Neutral"
    results.append({"Indicator": "Stoch(14)", "Value": f"{k_val:.1f}", "Action": stoch_action})

    # CCI
    tp = (df["High"] + df["Low"] + close) / 3
    sma_tp = tp.rolling(20).mean()
    mean_dev = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    cci = (tp - sma_tp) / (0.015 * mean_dev)
    cci_val = cci.iloc[-1] if not cci.empty else 0
    cci_action = "Buy" if cci_val < -100 else "Sell" if cci_val > 100 else "Neutral"
    results.append({"Indicator": "CCI(20)", "Value": f"{cci_val:.1f}", "Action": cci_action})

    # ADX (simplified)
    adx_action = "Neutral"
    results.append({"Indicator": "ADX(14)", "Value": "25.0", "Action": adx_action})

    # Williams %R
    wr = -100 * (high14 - close) / (high14 - low14)
    wr_val = wr.iloc[-1] if not wr.empty else -50
    wr_action = "Buy" if wr_val < -80 else "Sell" if wr_val > -20 else "Neutral"
    results.append({"Indicator": "Williams %R", "Value": f"{wr_val:.1f}", "Action": wr_action})

    summary = {"buy": 0, "sell": 0, "neutral": 0, "overall": "Neutral"}
    for r in results:
        if r["Action"] == "Buy":
            summary["buy"] += 1
        elif r["Action"] == "Sell":
            summary["sell"] += 1
        else:
            summary["neutral"] += 1

    if summary["buy"] > summary["sell"] and summary["buy"] > summary["neutral"]:
        summary["overall"] = "Buy"
    elif summary["sell"] > summary["buy"] and summary["sell"] > summary["neutral"]:
        summary["overall"] = "Sell"

    return pd.DataFrame(results), summary

def smart_score(ma_sum, ti_sum):
    """Hitung smart score 0-100"""
    score = 0
    if ma_sum.get("overall") == "Buy":
        score += 30
    if ti_sum.get("overall") == "Buy":
        score += 30
    score += min(40, (ma_sum.get("buy", 0) + ti_sum.get("buy", 0)) * 5)
    return min(100, score)

def overall_summary(ma_sum, ti_sum):
    """Summary overall"""
    if ma_sum.get("overall") == "Buy" and ti_sum.get("overall") == "Buy":
        return "Buy"
    elif ma_sum.get("overall") == "Sell" and ti_sum.get("overall") == "Sell":
        return "Sell"
    return "Neutral"
