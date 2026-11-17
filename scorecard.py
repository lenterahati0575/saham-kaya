"""Papan Skor Sistem (2026-11-17) - bukti LIVE per sistem dari jurnal (bukan backtest), dipecah menurut kondisi IHSG saat entry.

Tujuan (user: "penyempurnaan sampai sistem bisa bermanfaat utk keuntungan"): backtest sudah banyak, yang belum ada adalah angka
nyata dari jurnal live yang bisa dibandingkan APEL-KE-APEL dgn ekspektasi backtest & diberi tanda jujur bila sampelnya masih
terlalu kecil. Modul murni (tanpa streamlit) supaya teruji.

Definisi regime di tanggal entry (memakai close IHSG SEBELUM hari entry - yg sudah diketahui saat membeli):
  BULLISH   : close > MA50
  PEMULIHAN : close <= MA50 TAPI close >= 1,08 x close terendah 20 hari  (definisi sama dgn screener.market_regime_pemulihan)
  BEARISH   : close <= MA50 dan belum rebound >= 8% dari dasar 20 hari
"""
import math

import numpy as np
import pandas as pd

MIN_TRADE_CUKUP = 30
REGIME_URUT = ["BULLISH", "PEMULIHAN", "BEARISH", "TANPA DATA"]


def label_regime_series(ihsg_close: pd.Series, ma_period: int = 50, rebound_pct: float = 8.0, low_window: int = 20) -> pd.Series:
    """Label regime per hari bursa dari seri close IHSG (index tanggal)."""
    c = ihsg_close.astype(float).dropna().sort_index()
    ma = c.rolling(ma_period).mean()
    low = c.rolling(low_window).min()
    lab = pd.Series("BEARISH", index=c.index, dtype=object)
    lab[c > ma] = "BULLISH"
    lab[(c <= ma) & (c >= (1 + rebound_pct / 100.0) * low)] = "PEMULIHAN"
    lab[ma.isna()] = "TANPA DATA"
    return lab


def regime_saat_entry(labels: pd.Series, tanggal_open) -> list:
    """Regime pada hari bursa TERAKHIR SEBELUM tanggal entry (tanpa lookahead). Tanggal tak terbaca -> 'TANPA DATA'."""
    out = []
    idx = labels.index
    for t in pd.to_datetime(pd.Series(tanggal_open), errors="coerce"):
        if pd.isna(t) or len(idx) == 0:
            out.append("TANPA DATA"); continue
        t0 = pd.Timestamp(t).normalize()
        pos = idx.searchsorted(t0, side="left") - 1          # indeks terakhir yg < tanggal entry
        out.append(labels.iloc[pos] if pos >= 0 else "TANPA DATA")
    return out


def wilson(menang: int, n: int, z: float = 1.96):
    """Interval kepercayaan 95% (Wilson) utk proporsi menang. n=0 -> (nan, nan)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = menang / n
    d = 1 + z * z / n
    pusat = (p + z * z / (2 * n)) / d
    sisi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, pusat - sisi), min(1.0, pusat + sisi))


def _kolom_pl(df: pd.DataFrame):
    pct = pd.to_numeric(df.get("P&L (%)"), errors="coerce")
    rp = pd.to_numeric(df.get("P&L (Rp)"), errors="coerce")
    return pct, rp


def tutup_saja(df: pd.DataFrame) -> pd.DataFrame:
    """Hanya posisi yg SUDAH ditutup & P&L-nya terbaca."""
    if df is None or df.empty or "Status" not in df.columns:
        return pd.DataFrame()
    pct, _ = _kolom_pl(df)
    m = (df["Status"].astype(str).str.upper().str.strip() != "OPEN") & pct.notna()
    return df[m].copy()


def ringkas(df_tutup: pd.DataFrame) -> dict:
    """Statistik satu kelompok posisi tertutup. BREAKEVEN/force-sell dihitung dari TANDA P&L (konsisten dgn tab Performance)."""
    if df_tutup is None or df_tutup.empty:
        return {"N": 0}
    pct, rp = _kolom_pl(df_tutup)
    pct = pct.dropna()
    menang = int((pct > 0).sum())
    n = int(len(pct))
    rp = rp.reindex(pct.index)
    dasar = rp if rp.notna().all() else pct
    kotor_untung = float(dasar[dasar > 0].sum()); kotor_rugi = float(abs(dasar[dasar < 0].sum()))
    pf = (kotor_untung / kotor_rugi) if kotor_rugi > 0 else (float("inf") if kotor_untung > 0 else float("nan"))
    lo, hi = wilson(menang, n)
    return {"N": n, "Menang": menang, "Win Rate %": round(menang / n * 100, 1), "WR CI Bawah %": round(lo * 100, 0),
            "WR CI Atas %": round(hi * 100, 0), "Profit Factor": pf, "Rata2 %": round(float(pct.mean()), 2),
            "Median %": round(float(pct.median()), 2), "Terburuk %": round(float(pct.min()), 2),
            "Total P&L (Rp)": float(rp.sum()) if rp.notna().any() else float("nan")}


def status_data(n: int, minimum: int = MIN_TRADE_CUKUP) -> str:
    if n == 0:
        return "Belum ada data"
    return "Cukup utk dinilai" if n >= minimum else f"Belum cukup ({n}/{minimum} trade)"


def papan_skor(sistem: dict, ihsg_close: pd.Series) -> pd.DataFrame:
    """sistem = {nama sistem: DataFrame posisi (kolom Tanggal Open, Status, P&L (%), P&L (Rp))}.
    Hasil: satu baris per (sistem x regime saat entry) + baris 'SEMUA' per sistem; urut sistem lalu regime."""
    labels = label_regime_series(ihsg_close) if ihsg_close is not None and len(ihsg_close) else pd.Series(dtype=object)
    rows = []
    for nama, df in sistem.items():
        t = tutup_saja(df)
        if t.empty:
            rows.append({"Sistem": nama, "Regime Entry": "SEMUA", "N": 0, "Status Data": status_data(0)})
            continue
        t = t.assign(_reg=regime_saat_entry(labels, t["Tanggal Open"]) if "Tanggal Open" in t.columns else "TANPA DATA")
        for reg in ["SEMUA"] + REGIME_URUT:
            sub = t if reg == "SEMUA" else t[t["_reg"] == reg]
            if reg != "SEMUA" and sub.empty:
                continue
            r = ringkas(sub)
            r.update({"Sistem": nama, "Regime Entry": reg, "Status Data": status_data(r["N"])})
            rows.append(r)
    kolom = ["Sistem", "Regime Entry", "N", "Win Rate %", "WR CI Bawah %", "WR CI Atas %", "Profit Factor", "Rata2 %", "Median %",
             "Terburuk %", "Total P&L (Rp)", "Status Data"]
    out = pd.DataFrame(rows)
    for k in kolom:
        if k not in out.columns:
            out[k] = np.nan
    return out[kolom]
