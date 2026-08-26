"""
Riwayat Saham - log snapshot harian saham berSignal BUY/STRONG BUY ke satu sheet Google
Sheets ("RIWAYAT_SAHAM"), TERUS DITAMBAH (append), tidak pernah ditimpa - supaya performa
tiap saham dari waktu ke waktu bisa dilihat di SATU tempat, tanpa perlu download CSV
berulang kali (tiap download bikin file terpisah, tidak bisa dibandingkan lintas hari).

Latar belakang - user: "saya berfikir otomatis dalam bentuk excel. juga kelemahannya
setiap download terbentuk file baru. mungkin ada cara supaya selalu dalam satu file.
bahkan bisa diketahui performa setiap saham karena adanya dalam satu tempat. karena saya
lihat ada saham yang cepat naik, turun dll."

Keputusan (dipilihkan, user: "kamu pilih yang menurut kamu terbaik"):
1. Cakupan: HANYA saham Signal BUY/STRONG BUY (bukan semua 962 saham) - sheet tidak
   membengkak tak terkendali (962 baris/hari akan kena batas praktis Google Sheets dlm
   hitungan bulan), dan lebih relevan (saham yang benar2 dipertimbangkan utk dibeli).
2. Waktu: SEKALI sehari saja, di scan SORE (bukan pagi maupun 2x/hari) - konsisten dgn
   aturan yang sudah ada ("BUY vs SELL Beda Jadwal", README): data pagi cuma sebagian
   kecil hari itu, tidak representatif & tidak sebanding hari-ke-hari kalau dicampur dgn
   data sore yang sudah 1 hari penuh.

Beda dari gsheet_journal.py (POSISI): itu jurnal TRANSAKSI (buka/tutup posisi simulasi),
ini LOG SNAPSHOT PASAR (harga & sinyal tiap saham tiap hari, tidak ada konsep buka/tutup
posisi sama sekali) - sengaja modul terpisah, bukan ditumpuk ke gsheet_journal.py yang
sudah punya tanggung jawab sendiri.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

WIB = ZoneInfo("Asia/Jakarta")

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
SHEET_NAME = "RIWAYAT_SAHAM"

HEADERS = ["Tanggal", "Kode", "Nama", "Harga", "Perubahan %", "Signal", "Score",
           "Volume Ratio", "Value Traded (Rp)"]

# Signal minimal yang disimpan - "BUY ke atas" (BUY atau STRONG BUY), BUKAN WEAK BUY
# (itu kolom "Rekomendasi" terpisah, beda sistem - lihat README > "Smart Money").
SIGNAL_DISIMPAN = ("BUY", "STRONG BUY")


def is_configured() -> bool:
    """Cek apakah konfigurasi Google Sheets sudah lengkap - SAMA persis dgn
    gsheet_journal.is_configured(), sengaja diduplikasi (bukan import silang) supaya modul
    ini tetap bisa berdiri sendiri tanpa bergantung ke gsheet_journal.py."""
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
    """Ambil worksheet RIWAYAT_SAHAM - AUTO-CREATE kalau belum ada (beda dari
    gsheet_journal._get_worksheet() yang mengasumsikan sheet POSISI SUDAH dibuat manual
    oleh user) - sheet ini baru, user tidak perlu bikin tab baru sendiri dulu."""
    client = _get_client()
    sh = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    try:
        return sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        return ws


@st.cache_data(ttl=300, show_spinner=False)
def load_riwayat() -> pd.DataFrame:
    """Load seluruh riwayat snapshot dari sheet - dipakai tab viewer di app.py. Cache 5
    menit (bukan real-time kritis spt POSISI) - data historis, tidak berubah tiap detik."""
    try:
        ws = _get_worksheet()
        records = ws.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=HEADERS)
        for col in ["Harga", "Perubahan %", "Score", "Volume Ratio", "Value Traded (Rp)"]:
            if col in df.columns:
                cleaned = (df[col].astype(str)
                           .str.replace(".", "", regex=False)
                           .str.replace(",", ".", regex=False)
                           .str.replace("%", "", regex=False))
                df[col] = pd.to_numeric(cleaned, errors="coerce")
        return df
    except Exception as e:
        print(f"Error load riwayat saham: {e}")
        return pd.DataFrame(columns=HEADERS)


def append_daily_snapshot(table: pd.DataFrame) -> int:
    """Tambahkan snapshot HARI INI (saham Signal BUY/STRONG BUY dari `table` hasil
    build_screener_table()) ke sheet RIWAYAT_SAHAM - TIDAK PERNAH menimpa baris lama,
    cuma menambah baris baru di bawah.

    Guard 1x/hari: kalau snapshot utk tanggal hari ini SUDAH ada (dicek dari kolom
    "Tanggal" baris terakhir), SKIP total - cegah duplikat kalau auto_run.py atau tombol
    manual dipanggil berkali-kali di hari yang sama (sama semangatnya dgn cooldown
    open_positions_from_candidates() di gsheet_journal.py, tapi lebih simpel krn ini
    bukan per-saham, cukup 1x per hari kalender utk SELURUH batch).

    Returns:
        Jumlah baris yang berhasil ditambahkan (0 kalau di-skip krn sudah ada hari ini,
        atau tidak ada saham yang lolos filter Signal).
    """
    if table is None or table.empty or "Signal" not in table.columns:
        return 0

    ws = _get_worksheet()
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")

    existing_values = ws.get_all_values()
    if len(existing_values) > 1:
        last_row = existing_values[-1]
        if last_row and last_row[0] == today_str:
            print(f"ℹ️ Riwayat Saham: snapshot {today_str} sudah pernah ditambahkan, skip.")
            return 0

    lolos = table[table["Signal"].isin(SIGNAL_DISIMPAN)]
    if lolos.empty:
        return 0

    rows = []
    for _, r in lolos.iterrows():
        rows.append([
            today_str,
            str(r.get("Kode", "")),
            str(r.get("Nama", "")),
            float(r["Harga"]) if pd.notna(r.get("Harga")) else "",
            str(r.get("Perubahan %", "")),
            str(r.get("Signal", "")),
            float(r["Score"]) if pd.notna(r.get("Score")) else "",
            float(r["Volume Ratio"]) if pd.notna(r.get("Volume Ratio")) else "",
            float(r["Value Traded (Rp)"]) if pd.notna(r.get("Value Traded (Rp)")) else "",
        ])

    ws.append_rows(rows, value_input_option="USER_ENTERED")
    load_riwayat.clear()
    print(f"✅ Riwayat Saham: {len(rows)} snapshot ditambahkan utk {today_str}.")
    return len(rows)
