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


@st.cache_data(show_spinner=False)
def load_ticker_universe(path: str = "tickers_idx.csv") -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(ttl=900, show_spinner=False)  # cache 15 menit - jangan tembak Yahoo tiap klik
def fetch_price_history(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Ambil histori harga batch dari Yahoo Finance. Ticker IDX pakai akhiran .JK.
    Default 1 tahun (bukan 3 bulan) supaya cukup untuk MA200, RSI, MACD, dll di panel Technical Indicators."""
    results: dict[str, pd.DataFrame] = {}
    yf_tickers = [f"{t}.JK" for t in tickers]
    chunk_size = 80  # batch supaya tidak sekali tembak >600 ticker
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
    """Hitung metrik & skor untuk satu saham dari histori harga. None jika data tidak cukup."""
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

    # Donchian 20D - TIDAK termasuk candle hari ini (baris terakhir dibuang dulu)
    hist = df.iloc[-(lookback + 1) : -1]
    donchian_high = float(hist["High"].max())
    donchian_low = float(hist["Low"].min())
    if close > donchian_high:
        breakout_status = "BREAKOUT"
    elif close < donchian_low:
        breakout_status = "BREAKDOWN"
    else:
        breakout_status = "NETRAL"

    # Veto crash HARUS jadi hard block sungguhan - sebelumnya cuma penalti -3 poin, yang
    # artinya saham lagi crash tajam masih bisa "lolos" jadi BUY kalau breakout+volume-nya
    # cukup tinggi buat menutup penalti itu (mis. -3 breakout+3 volume+3 = tetap net positif).
    # Itu bertentangan dengan nama fiturnya sendiri ("veto") - veto artinya diskualifikasi,
    # bukan sekadar poin minus yang bisa di-offset sinyal lain. Sekarang begitu crash_veto
    # tersentuh, skor langsung di-hard-cap sebelum komponen bonus lain dihitung.
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
        m["Kode"] = kode
        m["Nama"] = name_map.get(kode, "")
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["Chart"] = out["Kode"].map(tradingview_url)
    cols = ["Kode", "Nama", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)",
            "Status Breakout", "Chart", "Layak Likuiditas", "Score", "Signal",
            "Donchian High", "Donchian Low", "Avg Volume 20D", "Volume"]
    out = out[cols].sort_values("Score", ascending=False).reset_index(drop=True)
    return out


# ---------------- Trade Candidates: Day Trading (BPJS/BSJP) & Swing (RR > 2:1) ----------------

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
    """Tentukan kondisi pasar keseluruhan (regime) dari IHSG: BULLISH kalau Close di atas
    MA(ma_period), BEARISH kalau di bawah, UNKNOWN kalau data belum cukup.

    KENAPA INI PENTING: skor & sinyal di atas semuanya dihitung per-saham, tanpa tahu
    kondisi pasar secara umum. Saat IHSG downtrend tajam, breakout individual saham jauh
    lebih sering jadi false signal / bull trap (naik sebentar lalu turun lagi bersama pasar)
    dibanding saat IHSG uptrend. Fungsi ini TIDAK otomatis mengubah skor saham manapun -
    dipakai di dashboard sebagai filter OPSIONAL (default mati) supaya Bro yang memutuskan,
    bukan logika tersembunyi yang mengubah hasil tanpa disadari."""
    if ihsg_df is None or ihsg_df.empty or len(ihsg_df) < ma_period:
        return {"status": "UNKNOWN", "close": None, "ma": None}
    close = float(ihsg_df["Close"].iloc[-1])
    ma = float(ihsg_df["Close"].rolling(ma_period).mean().iloc[-1])
    if pd.isna(ma):
        return {"status": "UNKNOWN", "close": close, "ma": None}
    status = "BULLISH" if close > ma else "BEARISH"
    return {"status": status, "close": close, "ma": ma}


@st.cache_data(ttl=3600, show_spinner=False)  # cache 1 jam
def fetch_ihsg_history(period: str = "1y") -> pd.DataFrame:
    """Ambil histori IHSG (^JKSE) dari Yahoo Finance, dipakai untuk bandingkan performa
    portofolio (equity) terhadap index pasar secara keseluruhan."""
    try:
        df = yf.download("^JKSE", period=period, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()
