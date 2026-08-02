"""
Indikator teknikal untuk panel di samping grafik (format ala TradingView Technical Analysis:
Moving Averages table + Technical Indicators table dengan verdict Buy/Sell/Neutral),
plus deteksi Swing High/Low (HH/LH/HL/LL).

CATATAN JUJUR: aturan Buy/Sell/Neutral di bawah pakai konvensi teknikal analisis standar
per indikator (dijelaskan di komentar tiap fungsi). Ini BUKAN hasil reverse-engineering
formula persis dari aplikasi manapun - kalau angka valuenya sama tapi verdict beda tipis
dengan app tertentu, itu wajar karena tiap penyedia punya ambang batas sendiri.
"""

import numpy as np
import pandas as pd


def _clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan baris NaN (mis. hari saham disuspend) dengan forward-fill, supaya
    rolling-window indicator (SMA, dll) tidak gagal total hanya karena satu baris bolong.
    ewm() (Exponential) sebenarnya cukup toleran terhadap NaN, tapi rolling().mean() (Simple)
    butuh SEMUA nilai dalam jendelanya non-NaN - itu sebabnya kolom Simple bisa jadi kosong
    kalau datanya tidak dibersihkan dulu."""
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    cleaned = df[cols].ffill().dropna()
    return cleaned


# ---------------- Moving Averages Panel ----------------

MA_PERIODS = [5, 10, 20, 50, 100, 200]


def moving_averages_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = _clean_ohlc(df)
    close = df["Close"]
    last_close = float(close.iloc[-1])
    rows = []
    buy_count = sell_count = 0
    for p in MA_PERIODS:
        if len(close) < p:
            continue
        sma = float(close.rolling(p).mean().iloc[-1])
        ema = float(close.ewm(span=p, adjust=False).mean().iloc[-1])
        sma_verdict = "Buy" if last_close > sma else "Sell"
        ema_verdict = "Buy" if last_close > ema else "Sell"
        buy_count += (sma_verdict == "Buy") + (ema_verdict == "Buy")
        sell_count += (sma_verdict == "Sell") + (ema_verdict == "Sell")
        rows.append({
            "MA": f"MA{p}",
            "Simple": f"{sma:.2f} · {sma_verdict}", "Simple Sinyal": sma_verdict,
            "Exponential": f"{ema:.2f} · {ema_verdict}", "Exponential Sinyal": ema_verdict,
        })
    total = buy_count + sell_count
    overall = "Buy" if buy_count > sell_count else ("Sell" if sell_count > buy_count else "Neutral")
    summary = {"buy": buy_count, "sell": sell_count, "total": total, "overall": overall}
    return pd.DataFrame(rows), summary


# ---------------- Technical Indicators Panel ----------------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Kasus tepi ditemukan lewat unit test: kalau avg_loss = 0 (tidak ada penurunan SAMA
    # SEKALI dalam window, mis. saham lagi ARA/limit-up beruntun), avg_gain/NaN di atas
    # jadi NaN, lalu fillna(50) polos akan salah menganggap itu "netral" - padahal
    # seharusnya RSI = 100 (paling overbought). Dibedakan dari kasus benar-benar flat
    # (avg_gain=0 DAN avg_loss=0) yang memang netral (RSI=50).
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi.fillna(50)


def _stochastic(df: pd.DataFrame, k_period=9, d_period=6):
    low_min = df["Low"].rolling(k_period).min()
    high_max = df["High"].rolling(k_period).max()
    k = 100 * (df["Close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k.fillna(50), d.fillna(50)


def _stoch_rsi(close: pd.Series, period=14):
    rsi = _rsi(close, period)
    low_min = rsi.rolling(period).min()
    high_max = rsi.rolling(period).max()
    srsi = 100 * (rsi - low_min) / (high_max - low_min).replace(0, np.nan)
    return srsi.fillna(50)


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line


def _adx(df: pd.DataFrame, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def _cci(df: pd.DataFrame, period=14):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    return cci.fillna(0)


def _ultimate_oscillator(df: pd.DataFrame, p1=7, p2=14, p3=28):
    close, high, low = df["Close"], df["High"], df["Low"]
    prior_close = close.shift()
    bp = close - pd.concat([low, prior_close], axis=1).min(axis=1)
    tr = pd.concat([high, prior_close], axis=1).max(axis=1) - pd.concat([low, prior_close], axis=1).min(axis=1)
    avg1 = bp.rolling(p1).sum() / tr.rolling(p1).sum().replace(0, np.nan)
    avg2 = bp.rolling(p2).sum() / tr.rolling(p2).sum().replace(0, np.nan)
    avg3 = bp.rolling(p3).sum() / tr.rolling(p3).sum().replace(0, np.nan)
    uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
    return uo.fillna(50)


def _williams_r(df: pd.DataFrame, period=14):
    high_max = df["High"].rolling(period).max()
    low_min = df["Low"].rolling(period).min()
    wr = -100 * (high_max - df["Close"]) / (high_max - low_min).replace(0, np.nan)
    return wr.fillna(-50)


def technical_indicators_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return (tabel indikator, summary count) - format meniru RSI/STOCH/STOCHRSI/MACD/ADX/CCI/UO/Williams%R."""
    df = _clean_ohlc(df)
    close = df["Close"]
    rows = []

    rsi_v = float(_rsi(close).iloc[-1])
    rsi_verdict = "Buy" if rsi_v > 55 else ("Sell" if rsi_v < 45 else "Neutral")
    rows.append(("RSI(14)", f"{rsi_v:.2f}", rsi_verdict))

    k, d = _stochastic(df)
    k_v = float(k.iloc[-1])
    stoch_verdict = "Buy" if k_v < 20 else ("Sell" if k_v > 80 else "Neutral")
    rows.append(("STOCH(9,6)", f"{k_v:.2f}", stoch_verdict))

    srsi_v = float(_stoch_rsi(close).iloc[-1])
    srsi_verdict = "Buy" if srsi_v < 20 else ("Sell" if srsi_v > 80 else "Neutral")
    rows.append(("STOCHRSI(14)", f"{srsi_v:.2f}", srsi_verdict))

    macd_line, signal_line = _macd(close)
    macd_v = float(macd_line.iloc[-1])
    macd_verdict = "Buy" if macd_line.iloc[-1] > signal_line.iloc[-1] else "Sell"
    rows.append(("MACD(12,26)", f"{macd_v:.2f}", macd_verdict))

    adx_v, plus_di, minus_di = _adx(df)
    adx_last = float(adx_v.iloc[-1])
    if adx_last > 20 and plus_di.iloc[-1] > minus_di.iloc[-1]:
        adx_verdict = "Buy"
    elif adx_last > 20 and minus_di.iloc[-1] > plus_di.iloc[-1]:
        adx_verdict = "Sell"
    else:
        adx_verdict = "Neutral"
    rows.append(("ADX(14)", f"{adx_last:.2f}", adx_verdict))

    cci_v = float(_cci(df).iloc[-1])
    cci_verdict = "Buy" if cci_v < -100 else ("Sell" if cci_v > 100 else "Neutral")
    rows.append(("CCI(14)", f"{cci_v:.2f}", cci_verdict))

    uo_v = float(_ultimate_oscillator(df).iloc[-1])
    uo_verdict = "Buy" if uo_v > 55 else ("Sell" if uo_v < 45 else "Neutral")
    rows.append(("UO", f"{uo_v:.2f}", uo_verdict))

    wr_v = float(_williams_r(df).iloc[-1])
    wr_verdict = "Buy" if wr_v < -80 else ("Sell" if wr_v > -20 else "Neutral")
    rows.append(("William's %R", f"{wr_v:.2f}", wr_verdict))

    table = pd.DataFrame(rows, columns=["Indikator", "Value", "Action"])
    buy_n = int((table["Action"] == "Buy").sum())
    sell_n = int((table["Action"] == "Sell").sum())
    neutral_n = int((table["Action"] == "Neutral").sum())
    if buy_n > sell_n and buy_n > neutral_n:
        overall = "Buy"
    elif sell_n > buy_n and sell_n > neutral_n:
        overall = "Sell"
    else:
        overall = "Neutral"
    summary = {"buy": buy_n, "neutral": neutral_n, "sell": sell_n, "overall": overall}
    return table, summary


def overall_summary(ma_summary: dict, ti_summary: dict) -> str:
    """Verdict gabungan Buy/Sell/Neutral dari MA + Technical Indicators (mirip badge 'Summary' di gambar)."""
    buy = ma_summary["buy"] + ti_summary["buy"]
    sell = ma_summary["sell"] + ti_summary["sell"]
    if buy > sell:
        return "Buy"
    elif sell > buy:
        return "Sell"
    return "Neutral"


def smart_score(ma_summary: dict, ti_summary: dict) -> float:
    """Skor gabungan 0-100 dari panel MA + Technical Indicators (mirip 'Smart Score' di gambar)."""
    total_buy = ma_summary["buy"] + ti_summary["buy"]
    total_all = ma_summary["buy"] + ma_summary["sell"] + ti_summary["buy"] + ti_summary["sell"] + ti_summary["neutral"]
    if total_all == 0:
        return 50.0
    return round(100 * total_buy / total_all, 1)


# ---------------- Swing High / Swing Low (HH-LL-HL-LH) ----------------

def find_swing_points(df: pd.DataFrame, order: int = 3):
    """Deteksi swing high/low pakai fractal window (order bar kiri-kanan)."""
    df = _clean_ohlc(df)
    highs, lows = df["High"].values, df["Low"].values
    idx = df.index
    n = len(df)
    swing_highs, swing_lows = [], []
    for i in range(order, n - order):
        window_h = highs[i - order: i + order + 1]
        if highs[i] == window_h.max() and np.argmax(window_h) == order:
            swing_highs.append((idx[i], float(highs[i])))
        window_l = lows[i - order: i + order + 1]
        if lows[i] == window_l.min() and np.argmin(window_l) == order:
            swing_lows.append((idx[i], float(lows[i])))
    return swing_highs, swing_lows


def classify_swings(swing_highs, swing_lows):
    """Urutkan kronologis, beri label HH/LH untuk swing high dan HL/LL untuk swing low."""
    events = [(d, p, "H") for d, p in swing_highs] + [(d, p, "L") for d, p in swing_lows]
    events.sort(key=lambda x: x[0])
    labeled = []
    last_high = last_low = None
    for d, p, typ in events:
        if typ == "H":
            label = "HH" if (last_high is not None and p > last_high) else ("LH" if last_high is not None else "H")
            last_high = p
        else:
            label = "HL" if (last_low is not None and p > last_low) else ("LL" if last_low is not None else "L")
            last_low = p
        labeled.append({"Tanggal": d, "Harga": p, "Tipe": typ, "Label": label})
    return pd.DataFrame(labeled)
