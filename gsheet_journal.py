"""
Jurnal backtest POSISI, terhubung ke Google Sheets (sheet 'POSISI' yang sudah ada
di file IDX_Screener_Bot). Auto-BUY saat Signal = BUY/STRONG BUY, auto-SELL saat
harga live menyentuh TP atau SL.

SETUP YANG DIBUTUHKAN (lihat README bagian "Setup Google Sheets"):
1. Google Cloud Service Account + Google Sheets API & Drive API aktif
2. File credential JSON ditempel ke Streamlit secrets sebagai [gcp_service_account]
3. Google Sheet (yang berisi tab POSISI) di-share ke email service account, akses Editor
4. Isi GOOGLE_SHEET_ID di secrets (bagian dari URL sheet: .../d/<GOOGLE_SHEET_ID>/edit)
"""

from datetime import datetime, date
import pandas as pd
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SHEET_NAME = "POSISI"
HEADERS = ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Tipe",
           "Tanggal Close", "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "Hari"]


def is_configured() -> bool:
    return (
        GSPREAD_AVAILABLE
        and "gcp_service_account" in st.secrets
        and "GOOGLE_SHEET_ID" in st.secrets
    )


@st.cache_resource(show_spinner=False)
def _get_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


def _get_worksheet():
    client = _get_client()
    sh = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    return sh.worksheet(SHEET_NAME)


@st.cache_data(ttl=30, show_spinner=False)  # cache 30 detik - cegah 429 quota exceeded Google Sheets
def load_positions() -> pd.DataFrame:
    ws = _get_worksheet()
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=HEADERS)
    return df


def _append_row(ws, row: list):
    ws.append_row(row, value_input_option="USER_ENTERED")


def open_positions_from_candidates(candidates: pd.DataFrame, tipe: str) -> list[str]:
    """Buka posisi baru dari tabel kandidat (hasil screener.build_trade_candidates).
    tipe: 'BPJS', 'BSJP', atau 'SWING'."""
    if candidates is None or candidates.empty:
        return []
    ws = _get_worksheet()
    existing = load_positions()
    open_symbols = set()
    if not existing.empty and "Status" in existing.columns:
        open_symbols = set(existing.loc[existing["Status"] == "OPEN", "Saham"])

    opened = []
    for _, row in candidates.iterrows():
        kode = row["Saham"]
        if kode in open_symbols:
            continue  # sudah ada posisi terbuka, jangan buka dobel
        new_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"), kode, row["Entry"], row["Target"], row["Stop Loss"],
            tipe, "", "", "", "", "OPEN", "",
        ]
        _append_row(ws, new_row)
        opened.append(kode)
    if opened:
        load_positions.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return opened


def auto_close_positions(price_lookup: dict) -> list[str]:
    """Cek semua posisi OPEN: tutup kalau TP/SL tersentuh, ATAU force-sell sesuai aturan waktu:
    - SWING  : force sell kalau sudah 10 hari dan belum kena TP/SL.
    - BPJS   : force sell kalau sudah lewat 1 hari (mestinya keluar hari yang sama).
    - BSJP   : force sell kalau sudah lewat 2 hari (mestinya keluar besok pagi)."""
    ws = _get_worksheet()
    df = load_positions()
    if df.empty or "Status" not in df.columns:
        return []

    FORCE_SELL_HARI = {"SWING": 10, "BPJS": 1, "BSJP": 2}

    closed = []
    for idx, row in df[df["Status"] == "OPEN"].iterrows():
        kode = row["Saham"]
        harga_live = price_lookup.get(kode)
        if harga_live is None:
            continue
        tp, sl = float(row["TP"]), float(row["SL"])
        harga_beli = float(row["Harga Beli"])
        tgl_open = pd.to_datetime(row["Tanggal Open"])
        hari = (datetime.now() - tgl_open).days
        tipe = str(row.get("Tipe", "")).strip().upper()

        status_baru = None
        if harga_live >= tp:
            status_baru = "WIN (TP)"
        elif harga_live <= sl:
            status_baru = "LOSS (SL)"
        elif hari >= FORCE_SELL_HARI.get(tipe, 10):
            status_baru = "FORCE SELL (WAKTU)"

        if status_baru:
            pnl_rp = harga_live - harga_beli
            pnl_pct = pnl_rp / harga_beli
            sheet_row = idx + 2  # +2: header + index 0-based -> baris sheet 1-based
            ws.update(f"G{sheet_row}:L{sheet_row}", [[
                datetime.now().strftime("%Y-%m-%d %H:%M"), harga_live,
                round(pnl_rp, 2), round(pnl_pct * 100, 2), status_baru, hari,
            ]])
            closed.append(f"{kode} ({status_baru})")
    if closed:
        load_positions.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return closed


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "open": 0, "win": 0, "loss": 0, "winrate": 0, "total_pnl_pct": 0}
    total = len(df)
    open_n = int((df["Status"] == "OPEN").sum())
    win = int(df["Status"].astype(str).str.startswith("WIN").sum())
    loss = int(df["Status"].astype(str).str.startswith("LOSS").sum())
    closed_n = win + loss
    winrate = (win / closed_n * 100) if closed_n > 0 else 0
    total_pnl_pct = pd.to_numeric(df.get("P&L (%)", pd.Series(dtype=float)), errors="coerce").sum()
    return {"total": total, "open": open_n, "win": win, "loss": loss,
            "winrate": winrate, "total_pnl_pct": total_pnl_pct}


def monthly_performance(df: pd.DataFrame) -> dict:
    """Hitung performa bulanan dari transaksi yang SUDAH CLOSE di sheet POSISI (bukan sheet
    terpisah - supaya tidak ada risiko data performance beda sendiri dari data transaksi asli).
    Profit per bulan = jumlah P&L(%) semua transaksi yang closed di bulan itu (penjumlahan
    sederhana ala signal-provider, BUKAN compounding return riil - ditampilkan apa adanya)."""
    empty = {"monthly": pd.DataFrame(columns=["Bulan", "Profit %"]), "cumulative_pct": 0.0,
             "avg_per_month": 0.0, "top_trades": pd.DataFrame(), "n_closed": 0}
    if df.empty or "Status" not in df.columns:
        return empty

    closed = df[df["Status"].astype(str).str.match(r"^(WIN|LOSS|FORCE SELL)")].copy()
    if closed.empty:
        return empty

    closed["Tanggal Close_dt"] = pd.to_datetime(closed["Tanggal Close"], errors="coerce")
    closed["P&L (%)_num"] = pd.to_numeric(closed["P&L (%)"], errors="coerce")
    closed = closed.dropna(subset=["Tanggal Close_dt", "P&L (%)_num"])
    if closed.empty:
        return empty

    closed["Bulan"] = closed["Tanggal Close_dt"].dt.strftime("%Y-%m")
    monthly = closed.groupby("Bulan")["P&L (%)_num"].sum().reset_index()
    monthly.columns = ["Bulan", "Profit %"]
    monthly = monthly.sort_values("Bulan")

    cumulative_pct = float(monthly["Profit %"].sum())
    avg_per_month = float(monthly["Profit %"].mean()) if len(monthly) else 0.0

    top_trades = closed.sort_values("P&L (%)_num", ascending=False)[
        ["Saham", "Tipe", "Tanggal Close", "P&L (%)_num", "Status"]
    ].rename(columns={"P&L (%)_num": "Profit %"}).head(10)

    return {"monthly": monthly, "cumulative_pct": cumulative_pct,
            "avg_per_month": avg_per_month, "top_trades": top_trades, "n_closed": len(closed)}
