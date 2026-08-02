"""
Equity Tracking - catatan snapshot modal per sekuritas dari waktu ke waktu.
Beda dengan Jurnal Real (yang mencatat TRANSAKSI per saham): ini mencatat POSISI MODAL
keseluruhan tiap sekuritas pada tanggal tertentu (Total Equity, Cash, Invested, dan batas
manajemen risiko per sekuritas) - dipakai untuk melihat tren portofolio & bandingkan
dengan IHSG dari waktu ke waktu.

Kenapa per snapshot manual (bukan otomatis dihitung)? Karena Total Equity riil = uang di
RDN + nilai saham yang dipegang, dan itu hanya diketahui Bro sendiri dari aplikasi
sekuritas masing-masing - tidak bisa dihitung otomatis dari data Yahoo Finance saja.
"""

import pandas as pd
import streamlit as st

from gsheet_journal import is_configured, _get_client  # reuse koneksi yang sudah ada

EQUITY_SHEET = "EQUITY"
EQUITY_HEADERS = ["Tanggal", "Sekuritas", "Total Equity (Rp)", "Cash (Rp)", "Invested (Rp)",
                   "Max Risk/Trade (%)", "Max Position/Stock (%)"]


def _ensure_worksheet(sheet_id: str, name: str, headers: list):
    client = _get_client()
    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(name)
    except Exception:
        ws = sh.add_worksheet(title=name, rows=1000, cols=len(headers) + 2)
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws


def _get_equity_ws():
    return _ensure_worksheet(st.secrets["GOOGLE_SHEET_ID"], EQUITY_SHEET, EQUITY_HEADERS)


@st.cache_data(ttl=30, show_spinner=False)  # cache 30 detik - cegah 429 quota exceeded Google Sheets
def load_equity() -> pd.DataFrame:
    ws = _get_equity_ws()
    records = ws.get_all_records()
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=EQUITY_HEADERS)
    return df


def add_equity_snapshot(tanggal: str, sekuritas: str, total_equity: float, cash: float,
                         invested: float, max_risk_pct: float, max_position_pct: float) -> tuple[bool, str]:
    ws = _get_equity_ws()
    ws.append_row(
        [tanggal, sekuritas, total_equity, cash, invested, max_risk_pct, max_position_pct],
        value_input_option="USER_ENTERED",
    )
    load_equity.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Snapshot equity {sekuritas} pada {tanggal} tersimpan."


def delete_equity_row(tanggal: str, sekuritas: str) -> tuple[bool, str]:
    """Hapus snapshot spesifik (tanggal+sekuritas dipakai sebagai kunci karena tidak ada No)."""
    ws = _get_equity_ws()
    df = load_equity()
    match = df[(df["Tanggal"].astype(str) == str(tanggal)) & (df["Sekuritas"] == sekuritas)]
    if match.empty:
        return False, "Snapshot tidak ditemukan."
    sheet_row = match.index[0] + 2
    ws.delete_rows(sheet_row)
    load_equity.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, "Snapshot dihapus."


def latest_per_sekuritas(df: pd.DataFrame) -> pd.DataFrame:
    """Snapshot TERBARU untuk masing-masing sekuritas (dipakai buat pie/bar breakdown)."""
    if df.empty:
        return df
    d = df.copy()
    d["Tanggal_dt"] = pd.to_datetime(d["Tanggal"], errors="coerce")
    d = d.dropna(subset=["Tanggal_dt"])
    d = d.sort_values("Tanggal_dt")
    return d.groupby("Sekuritas").tail(1).reset_index(drop=True)


def total_equity_over_time(df: pd.DataFrame) -> pd.DataFrame:
    """Total equity gabungan SEMUA sekuritas per tanggal (jumlahkan tiap sekuritas pada
    tanggal yang sama - kalau ada sekuritas yang tidak diisi tanggal itu, dianggap sama
    dengan snapshot terakhirnya / forward-fill, supaya total tidak drop palsu)."""
    if df.empty:
        return pd.DataFrame(columns=["Tanggal", "Total Equity (Rp)"])
    d = df.copy()
    d["Tanggal_dt"] = pd.to_datetime(d["Tanggal"], errors="coerce")
    d["Total Equity (Rp)_num"] = pd.to_numeric(d["Total Equity (Rp)"], errors="coerce")
    d = d.dropna(subset=["Tanggal_dt", "Total Equity (Rp)_num"])
    if d.empty:
        return pd.DataFrame(columns=["Tanggal", "Total Equity (Rp)"])

    pivot = d.pivot_table(index="Tanggal_dt", columns="Sekuritas",
                           values="Total Equity (Rp)_num", aggfunc="last")
    pivot = pivot.sort_index().ffill()  # sekuritas yang belum diupdate hari itu, pakai nilai terakhir
    out = pivot.sum(axis=1).reset_index()
    out.columns = ["Tanggal", "Total Equity (Rp)"]
    return out


def portfolio_return_pct(equity_series: pd.DataFrame) -> pd.DataFrame:
    """% perubahan Total Equity terhadap snapshot PALING AWAL (dipakai untuk bandingkan
    dengan return IHSG di periode yang sama)."""
    if equity_series.empty:
        return equity_series
    out = equity_series.copy()
    base = out["Total Equity (Rp)"].iloc[0]
    out["Return %"] = (out["Total Equity (Rp)"] / base - 1) * 100 if base > 0 else 0
    return out
