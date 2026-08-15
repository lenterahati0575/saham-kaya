"""
Jurnal Trading REAL - mencatat transaksi UANG BENERAN Bro, terpisah total dari
jurnal backtest (POSISI) supaya data simulasi tidak tercampur dengan data riil.

Konsep diadaptasi dari file referensi Bro (Jurnal_Trading_Pro_Versi_Otomatis.xlsx), dengan
beberapa perbaikan:
- Biaya beli/jual dihitung PER SEKURITAS (broker beda, fee beda) - bukan satu angka flat
  untuk semua broker seperti di file referensi.
- Cumulative P/L dihitung di Python (pandas), bukan formula Excel `=E5+D6` yang gampang
  rusak (#VALUE!) begitu ada satu baris kosong di tengah data - sudah terbukti error di
  file referensi Bro sendiri (baris ANALYSIS!E6 dst.).
- Input lewat FORM di dashboard (bukan isi manual sel spreadsheet) - biar "mudah diisi"
  sesuai permintaan Bro: pilih dari dropdown, isi angka, klik simpan.
- Sheet dibuat OTOMATIS kalau belum ada (tidak perlu Bro siapkan dulu di Google Sheets).

Menggunakan koneksi Google Sheets yang sama dengan gsheet_journal.py (satu Service Account,
satu Sheet ID) - tidak perlu setup ulang kalau jurnal backtest sudah jalan.
"""

from datetime import datetime
import pandas as pd
import streamlit as st

from gsheet_journal import is_configured, _get_client  # reuse koneksi yang sudah ada

TRADES_SHEET = "JURNAL_REAL"
BROKER_SHEET = "SEKURITAS"

TRADES_HEADERS = ["No", "Tanggal Entry", "Sekuritas", "Saham", "Setup", "Entry (Rp)",
                   "Stop Loss (Rp)", "Target (Rp)", "Lot", "Tanggal Exit", "Exit (Rp)",
                   "Biaya (Rp)", "Net P/L (Rp)", "Return %", "Status", "Catatan"]
BROKER_HEADERS = ["Sekuritas", "Biaya Beli (%)", "Biaya Jual (%)"]

SETUP_OPTIONS = ["Swing", "Momentum", "Breakout", "Mean Reversion", "Day Trading", "Lainnya"]

DEFAULT_BROKERS = [
    ["Profits Anywhere", 0.15, 0.25],
    ["Stockbit", 0.15, 0.25],
    ["Ajaib", 0.15, 0.25],
]


def _ensure_worksheet(sheet_id: str, name: str, headers: list, default_rows: list | None = None):
    client = _get_client()
    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(name)
    except Exception:
        ws = sh.add_worksheet(title=name, rows=1000, cols=len(headers) + 2)
        ws.append_row(headers, value_input_option="RAW")
        if default_rows:
            for row in default_rows:
                ws.append_row(row, value_input_option="RAW")
    return ws


def _get_trades_ws():
    return _ensure_worksheet(st.secrets["GOOGLE_SHEET_ID"], TRADES_SHEET, TRADES_HEADERS)


def _get_broker_ws():
    return _ensure_worksheet(st.secrets["GOOGLE_SHEET_ID"], BROKER_SHEET, BROKER_HEADERS, DEFAULT_BROKERS)


@st.cache_data(ttl=30, show_spinner=False)  # cache 30 detik - cegah 429 quota exceeded Google Sheets
def load_brokers() -> pd.DataFrame:
    ws = _get_broker_ws()
    records = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(DEFAULT_BROKERS, columns=BROKER_HEADERS)
    return df


def add_broker(nama: str, biaya_beli_pct: float, biaya_jual_pct: float):
    ws = _get_broker_ws()
    existing = load_brokers()
    match = existing[existing["Sekuritas"].astype(str).str.strip() == nama.strip()]
    if not match.empty:
        # update baris yang sudah ada - pakai index dari dataframe, BUKAN ws.find() yang rapuh
        # (ws.find() bisa return None walau datanya ada, misal beda spasi/whitespace)
        sheet_row = match.index[0] + 2  # +2: header + index 0-based -> baris sheet 1-based
        ws.update(f"A{sheet_row}:C{sheet_row}", [[nama.strip(), biaya_beli_pct, biaya_jual_pct]], value_input_option="RAW")
    else:
        ws.append_row([nama.strip(), biaya_beli_pct, biaya_jual_pct], value_input_option="RAW")
    load_brokers.clear()  # data berubah - paksa baca ulang di panggilan berikutnya


def delete_broker(nama: str) -> tuple[bool, str]:
    ws = _get_broker_ws()
    existing = load_brokers()
    match = existing[existing["Sekuritas"].astype(str).str.strip() == nama.strip()]
    if match.empty:
        return False, f"Sekuritas '{nama}' tidak ditemukan."
    sheet_row = match.index[0] + 2
    ws.delete_rows(sheet_row)
    load_brokers.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Sekuritas '{nama}' dihapus."


@st.cache_data(ttl=30, show_spinner=False)  # cache 30 detik - cegah 429 quota exceeded Google Sheets
def load_trades() -> pd.DataFrame:
    ws = _get_trades_ws()
    records = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=TRADES_HEADERS)
    return df


def _calculate_trade_result(entry: float, exit_price: float, lot: float,
                             biaya_beli_pct: float, biaya_jual_pct: float) -> dict:
    """Rumus inti Biaya/Net P/L/Return%/Status - dipakai oleh close_trade() dan edit_trade(),
    dan bisa dipanggil langsung untuk verifikasi (lihat tab Kelola Sekuritas > Tes Formula)."""
    lembar = lot * 100
    biaya = (entry * lembar * biaya_beli_pct / 100) + (exit_price * lembar * biaya_jual_pct / 100)
    net_pl = (exit_price - entry) * lembar - biaya
    return_pct = (net_pl / (entry * lembar)) * 100 if entry * lembar > 0 else 0
    status = "PROFIT" if net_pl > 0 else ("LOSS" if net_pl < 0 else "BREAKEVEN")
    return {"biaya": biaya, "net_pl": net_pl, "return_pct": return_pct, "status": status}


def open_trade(tanggal_entry: str, sekuritas: str, saham: str, setup: str,
                entry: float, sl: float, target: float, lot: int, catatan: str = ""):
    ws = _get_trades_ws()
    existing = load_trades()
    # BUKAN len(existing)+1 - itu bug nyata: kalau ada trade yang pernah DIHAPUS
    # (delete_trade() betul2 delete_rows di sheet), jumlah baris berkurang, jadi No baru bisa
    # COLLIDE dgn No yang masih ada (mis. trade No 1,2,3 -> hapus No 2 -> tinggal 2 baris ->
    # trade baru dihitung No=3, padahal No 3 SUDAH ADA). Akibatnya close_trade()/edit_trade()/
    # delete_trade() yang cari baris via `trades["No"]==no` bisa match 2 baris & diam2 selalu
    # ambil yang PERTAMA (.iloc[0]) - salah trade yang ketutup/keedit tanpa ada pesan error.
    # Fix: No baru = MAX No yang pernah ada + 1, bukan jumlah baris + 1.
    if not existing.empty and "No" in existing.columns:
        no_terpakai = pd.to_numeric(existing["No"], errors="coerce")
        no = int(no_terpakai.max()) + 1 if no_terpakai.notna().any() else 1
    else:
        no = 1
    row = [no, tanggal_entry, sekuritas, saham.upper(), setup, entry, sl, target, lot,
           "", "", "", "", "", "OPEN", catatan]
    ws.append_row(row, value_input_option="RAW")
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return no


def _find_trade_row(trades: pd.DataFrame, no: int, require_open: bool = False):
    """Cari SATU baris yang cocok dgn nomor 'No'. Return (row, sheet_row, error_msg) -
    row/sheet_row None kalau error.

    Bug nyata dari laporan user: coba tutup posisi (mis. BWPT di harga 91, di bawah target)
    lewat 'Jurnal Real' - TIDAK ada pesan error, TAPI datanya tidak berubah (Status tetap
    OPEN). Root cause: close_trade()/delete_trade()/edit_trade() dulu cuma `.iloc[0]` dari
    hasil filter "No"==no TANPA cek apakah hasilnya lebih dari 1 baris. Kalau ada 2 baris
    dgn "No" yang sama (sisa dari bug lama SEBELUM open_trade() diperbaiki jadi
    `No = MAX(No)+1` - baris yang KADUNG duplikat sebelum fix itu tidak otomatis
    dibersihkan), update/hapus diam-diam mengenai baris PERTAMA yang cocok - yang bisa saja
    itu baris LAIN (mis. trade lama yang sudah closed), BUKAN posisi yang sebenarnya
    dimaksud user. Tidak ada exception/error krn dari sudut pandang kode, "berhasil update
    SATU baris" - cuma salah sasaran.

    require_open=True (dipakai close_trade - kita SPESIFIK mau tutup posisi yg masih OPEN):
    kalau di antara baris yg "No"-nya duplikat ada yang Status=="OPEN", persempit ke situ
    dulu sebelum menilai ambigu - INI kemungkinan besar memperbaiki kasus BWPT tanpa perlu
    user membersihkan data manual, SELAMA cuma satu dari yang duplikat itu masih OPEN.
    Kalau masih tersisa >1 kandidat setelah itu, baru dianggap benar2 ambigu & ditolak
    dgn pesan jelas (drpd diam2 salah sasaran)."""
    match = trades[trades["No"].astype(str) == str(no)]
    if require_open and "Status" in trades.columns:
        match_open = match[match["Status"] == "OPEN"]
        if not match_open.empty:
            match = match_open
    if match.empty:
        return None, None, "Nomor trade tidak ditemukan."
    if len(match) > 1:
        return None, None, (
            f"Ditemukan {len(match)} baris dengan nomor #{no} yang sama (kemungkinan data "
            "duplikat lama) - tidak bisa dipastikan baris mana yang dimaksud, jadi TIDAK "
            "diproses (drpd salah sasaran diam-diam). Cek manual kolom 'No' di Google Sheets "
            "(tab TRADES), pastikan tidak ada nomor yang kembar, lalu coba lagi."
        )
    return match.iloc[0], match.index[0] + 2, None


def _close_at_sheet_row(ws, r: pd.Series, sheet_row: int, tanggal_exit: str, exit_price: float,
                          brokers: pd.DataFrame) -> tuple[bool, str]:
    """Inti logika tutup posisi (hitung biaya/Net P/L/Return%/Status, tulis ke sheet) - dipakai
    close_trade() (cari baris via "No", bisa ambigu -> ditolak lewat _find_trade_row()) MAUPUN
    close_trade_at_row() (baris SUDAH PASTI dari index DataFrame, tidak perlu cari lagi)."""
    # exit_price/tanggal_exit di-cast eksplisit ke tipe Python murni - lihat komentar panjang
    # di edit_trade_at_row() soal TypeError "int64 is not JSON serializable" kalau nilai numpy
    # (dari akses Series pandas langsung) kelolos sampai ke ws.update().
    entry = float(r["Entry (Rp)"])
    lot = float(r["Lot"])
    exit_price = float(exit_price)
    tanggal_exit = str(tanggal_exit)
    sekuritas = r["Sekuritas"]
    fee_row = brokers[brokers["Sekuritas"] == sekuritas]
    biaya_beli_pct = float(fee_row["Biaya Beli (%)"].values[0]) if not fee_row.empty else 0.15
    biaya_jual_pct = float(fee_row["Biaya Jual (%)"].values[0]) if not fee_row.empty else 0.25
    r_calc = _calculate_trade_result(entry, exit_price, lot, biaya_beli_pct, biaya_jual_pct)
    ws.update(f"J{sheet_row}:O{sheet_row}", [[
        tanggal_exit, exit_price, float(round(r_calc["biaya"], 2)), float(round(r_calc["net_pl"], 2)),
        float(round(r_calc["return_pct"], 2)), str(r_calc["status"]),
    ]], value_input_option="RAW")
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Trade #{r['No']} ({r['Saham']}) ditutup: {r_calc['status']} ({r_calc['return_pct']:+.2f}%)"


def close_trade(no: int, tanggal_exit: str, exit_price: float):
    """Tutup posisi: hitung biaya (sesuai fee sekuritas trade itu), Net P/L, Return%, Status."""
    ws = _get_trades_ws()
    trades = load_trades()
    brokers = load_brokers()
    r, sheet_row, err = _find_trade_row(trades, no, require_open=True)
    if err:
        return False, err
    return _close_at_sheet_row(ws, r, sheet_row, tanggal_exit, exit_price, brokers)


def close_trade_at_row(row_index: int, tanggal_exit: str, exit_price: float) -> tuple[bool, str]:
    """Tutup posisi lewat INDEX BARIS DataFrame yang sudah pasti unik (dari `load_trades()`
    yang baru saja dipanggil UI, dipasangkan lewat `st.selectbox` yang value-nya index baris,
    BUKAN "No") - dipakai tab 'Tutup Posisi'. Bug nyata dari laporan user: dropdown yang pakai
    "No" sbg identitas pilihan bikin baris dgn "No" duplikat (mis. BWPT & DOOH sama2 No=9)
    TIDAK BISA dibedakan/dipilih terpisah oleh Streamlit selectbox - salah satunya jadi
    "hilang" dari pilihan. Index DataFrame TIDAK PERNAH duplikat (beda dari "No"), jadi aman
    dipakai sbg identitas dropdown walau datanya sendiri masih ada "No" yang kembar."""
    ws = _get_trades_ws()
    trades = load_trades()
    if row_index not in trades.index:
        return False, "Baris trade tidak ditemukan - data mungkin baru berubah, refresh halaman lalu coba lagi."
    r = trades.loc[row_index]
    brokers = load_brokers()
    return _close_at_sheet_row(ws, r, row_index + 2, tanggal_exit, exit_price, brokers)


def delete_trade(no: int) -> tuple[bool, str]:
    """Hapus transaksi (misal salah input total, batal dicatat)."""
    ws = _get_trades_ws()
    trades = load_trades()
    _r, sheet_row, err = _find_trade_row(trades, no)
    if err:
        return False, err
    ws.delete_rows(sheet_row)
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Trade #{no} dihapus."


def delete_trade_at_row(row_index: int) -> tuple[bool, str]:
    """Hapus transaksi lewat INDEX BARIS DataFrame (lihat penjelasan lengkap di
    close_trade_at_row() - identitas dropdown "No" saja tidak cukup kalau ada duplikat)."""
    ws = _get_trades_ws()
    trades = load_trades()
    if row_index not in trades.index:
        return False, "Baris trade tidak ditemukan - data mungkin baru berubah, refresh halaman lalu coba lagi."
    r = trades.loc[row_index]
    sheet_row = row_index + 2
    ws.delete_rows(sheet_row)
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Trade #{r['No']} ({r['Saham']}) dihapus."


def edit_trade(no: int, tanggal_entry: str, sekuritas: str, saham: str, setup: str,
                entry: float, sl: float, target: float, lot: int, catatan: str,
                tanggal_exit: str = "", exit_price: float | None = None) -> tuple[bool, str]:
    """Edit transaksi yang salah input. Kalau trade sudah closed (ada Tanggal Exit & Exit),
    Biaya/Net P/L/Return%/Status dihitung ULANG otomatis mengikuti data baru - supaya tidak
    ada data 'nyangkut' dari perhitungan lama yang sudah tidak sesuai."""
    ws = _get_trades_ws()
    trades = load_trades()
    _r, sheet_row, err = _find_trade_row(trades, no)
    if err:
        return False, err

    # Bug nyata dari laporan user: klik "Simpan Perubahan" langsung error
    # "TypeError: Object of type int64 is not JSON serializable" - root cause: `no` dikirim
    # dari app.py sbg `row_edit["No"]`, hasil akses langsung ke Series pandas (`.loc[idx]`)
    # yang TIDAK lewat `.tolist()` (beda dari kode lama yg pakai `pilih_edit_no` dari
    # `st.selectbox(options=trades_edit["No"].tolist(), ...)` - `.tolist()` otomatis
    # mengonversi numpy.int64 jadi `int` Python biasa, itulah kenapa dulu aman). gspread
    # men-JSON-kan tiap sel sebelum dikirim - numpy.int64/float64 BUKAN tipe yang bisa
    # di-JSON-kan bawaan Python, beda dari int/float murni. Fix: cast eksplisit SEMUA nilai
    # numerik ke tipe Python murni tepat sebelum ditulis ke sheet, drpd berharap semua
    # pemanggil selalu kirim tipe yang benar.
    no = int(no)
    entry = float(entry); sl = float(sl); target = float(target); lot = float(lot)

    is_closed = bool(tanggal_exit) and exit_price is not None and exit_price > 0
    if is_closed:
        exit_price = float(exit_price)
        brokers = load_brokers()
        fee_row = brokers[brokers["Sekuritas"] == sekuritas]
        biaya_beli_pct = float(fee_row["Biaya Beli (%)"].values[0]) if not fee_row.empty else 0.15
        biaya_jual_pct = float(fee_row["Biaya Jual (%)"].values[0]) if not fee_row.empty else 0.25
        r_calc = _calculate_trade_result(entry, exit_price, lot, biaya_beli_pct, biaya_jual_pct)
        exit_row = [tanggal_exit, exit_price, float(round(r_calc["biaya"], 2)), float(round(r_calc["net_pl"], 2)),
                    float(round(r_calc["return_pct"], 2)), str(r_calc["status"])]
    else:
        exit_row = ["", "", "", "", "", "OPEN"]

    full_row = [no, str(tanggal_entry), str(sekuritas), str(saham).upper(), str(setup),
                entry, sl, target, lot] + exit_row + [str(catatan)]
    ws.update(f"A{sheet_row}:P{sheet_row}", [full_row], value_input_option="RAW")
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Trade #{no} berhasil diperbarui."


def edit_trade_at_row(row_index: int, no: int, tanggal_entry: str, sekuritas: str, saham: str,
                       setup: str, entry: float, sl: float, target: float, lot: int, catatan: str,
                       tanggal_exit: str = "", exit_price: float | None = None) -> tuple[bool, str]:
    """Edit transaksi lewat INDEX BARIS DataFrame (lihat penjelasan lengkap di
    close_trade_at_row() - identitas dropdown "No" saja tidak cukup kalau ada duplikat). "No"
    tetap diminta sbg parameter terpisah krn kolom itu ditulis balik apa adanya (form edit
    tidak mengubah nomor trade)."""
    ws = _get_trades_ws()
    trades = load_trades()
    if row_index not in trades.index:
        return False, "Baris trade tidak ditemukan - data mungkin baru berubah, refresh halaman lalu coba lagi."
    sheet_row = row_index + 2

    # Bug nyata dari laporan user: klik "Simpan Perubahan" langsung error
    # "TypeError: Object of type int64 is not JSON serializable" - root cause: `no` dikirim
    # dari app.py sbg `row_edit["No"]`, hasil akses langsung ke Series pandas (`.loc[idx]`)
    # yang TIDAK lewat `.tolist()` (beda dari kode lama yg pakai `pilih_edit_no` dari
    # `st.selectbox(options=trades_edit["No"].tolist(), ...)` - `.tolist()` otomatis
    # mengonversi numpy.int64 jadi `int` Python biasa, itulah kenapa dulu aman). gspread
    # men-JSON-kan tiap sel sebelum dikirim - numpy.int64/float64 BUKAN tipe yang bisa
    # di-JSON-kan bawaan Python, beda dari int/float murni. Fix: cast eksplisit SEMUA nilai
    # numerik ke tipe Python murni tepat sebelum ditulis ke sheet, drpd berharap semua
    # pemanggil selalu kirim tipe yang benar.
    no = int(no)
    entry = float(entry); sl = float(sl); target = float(target); lot = float(lot)

    is_closed = bool(tanggal_exit) and exit_price is not None and exit_price > 0
    if is_closed:
        exit_price = float(exit_price)
        brokers = load_brokers()
        fee_row = brokers[brokers["Sekuritas"] == sekuritas]
        biaya_beli_pct = float(fee_row["Biaya Beli (%)"].values[0]) if not fee_row.empty else 0.15
        biaya_jual_pct = float(fee_row["Biaya Jual (%)"].values[0]) if not fee_row.empty else 0.25
        r_calc = _calculate_trade_result(entry, exit_price, lot, biaya_beli_pct, biaya_jual_pct)
        exit_row = [tanggal_exit, exit_price, float(round(r_calc["biaya"], 2)), float(round(r_calc["net_pl"], 2)),
                    float(round(r_calc["return_pct"], 2)), str(r_calc["status"])]
    else:
        exit_row = ["", "", "", "", "", "OPEN"]

    full_row = [no, str(tanggal_entry), str(sekuritas), str(saham).upper(), str(setup),
                entry, sl, target, lot] + exit_row + [str(catatan)]
    ws.update(f"A{sheet_row}:P{sheet_row}", [full_row], value_input_option="RAW")
    load_trades.clear()  # data berubah - paksa baca ulang di panggilan berikutnya
    return True, f"Trade #{no} berhasil diperbarui."


def open_positions_risk(trades: pd.DataFrame) -> pd.DataFrame:
    """Risiko (Rp) tiap posisi OPEN = (Entry - Stop Loss) x Lot x 100 lembar.

    KENAPA INI PENTING: Kalkulator Manajemen Risiko di tab Kalkulator cuma menghitung risiko
    SATU trade pada satu waktu. Tidak ada yang menjumlahkan risiko dari SEMUA posisi yang
    sedang OPEN bersamaan - jadi Bro bisa saja sudah membuka 5-6 posisi yang masing-masing
    "aman" secara individual (1-2% modal), tapi totalnya sudah jauh melebihi toleransi risiko
    portofolio tanpa disadari. Fungsi ini menjumlahkan semuanya. Dipakai di tab Equity >
    Risk Portofolio bersama Total Equity terbaru untuk menghitung % risiko agregat.

    CATATAN: kalau Stop Loss belum diisi (0) untuk suatu trade, risikonya TIDAK bisa dihitung
    (dianggap 0 di total, bukan diabaikan diam-diam) - baris itu ditandai di kolom
    'SL Belum Diisi' supaya kelihatan kalau agregat ini kemungkinan under-estimate."""
    cols = ["Saham", "Sekuritas", "Entry (Rp)", "Stop Loss (Rp)", "Lot", "Risiko (Rp)", "SL Belum Diisi"]
    if trades.empty or "Status" not in trades.columns:
        return pd.DataFrame(columns=cols)
    open_t = trades[trades["Status"] == "OPEN"].copy()
    if open_t.empty:
        return pd.DataFrame(columns=cols)

    entry = pd.to_numeric(open_t["Entry (Rp)"], errors="coerce").fillna(0)
    sl = pd.to_numeric(open_t["Stop Loss (Rp)"], errors="coerce").fillna(0)
    lot = pd.to_numeric(open_t["Lot"], errors="coerce").fillna(0)
    sl_kosong = sl <= 0
    risiko = ((entry - sl).clip(lower=0)) * lot * 100
    risiko = risiko.where(~sl_kosong, 0)

    open_t["Risiko (Rp)"] = risiko
    open_t["SL Belum Diisi"] = sl_kosong
    return open_t[cols]


def portfolio_risk_summary(trades: pd.DataFrame, total_equity: float | None) -> dict:
    """Ringkasan risiko portofolio agregat: total Rp yang dipertaruhkan dari semua posisi
    OPEN, dan berapa % itu dari Total Equity terbaru (kalau ada data Equity)."""
    detail = open_positions_risk(trades)
    total_risk_rp = float(detail["Risiko (Rp)"].sum()) if not detail.empty else 0.0
    n_open = len(detail)
    n_sl_kosong = int(detail["SL Belum Diisi"].sum()) if not detail.empty else 0
    pct = (total_risk_rp / total_equity * 100) if total_equity and total_equity > 0 else None
    return {
        "detail": detail, "total_risk_rp": total_risk_rp, "n_open": n_open,
        "n_sl_kosong": n_sl_kosong, "pct_of_equity": pct,
    }


def compute_stats(trades: pd.DataFrame) -> dict:
    empty = {"total": 0, "open": 0, "win": 0, "loss": 0, "winrate": 0,
             "net_pl": 0, "profit_factor": 0, "expectancy": 0,
             "total_transaction_value": 0, "max_profit_rp": 0, "max_loss_rp": 0,
             "max_profit_pct": 0, "max_loss_pct": 0, "avg_profit_rp": 0, "avg_loss_rp": 0}
    if trades.empty:
        return empty
    closed = trades[trades["Status"].isin(["PROFIT", "LOSS", "BREAKEVEN"])].copy()
    closed["Net P/L (Rp)_num"] = pd.to_numeric(closed["Net P/L (Rp)"], errors="coerce")
    closed["Return %_num"] = pd.to_numeric(closed["Return %"], errors="coerce")
    win = int((closed["Status"] == "PROFIT").sum())
    loss = int((closed["Status"] == "LOSS").sum())
    closed_n = win + loss
    winrate = (win / closed_n * 100) if closed_n > 0 else 0
    net_pl = closed["Net P/L (Rp)_num"].sum()
    wins_df = closed[closed["Net P/L (Rp)_num"] > 0]
    losses_df = closed[closed["Net P/L (Rp)_num"] < 0]
    gross_profit = wins_df["Net P/L (Rp)_num"].sum()
    gross_loss = abs(losses_df["Net P/L (Rp)_num"].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)
    expectancy = net_pl / closed_n if closed_n > 0 else 0

    # Total Transaction Value = total modal yang dipakai buka posisi (semua trade, OPEN+closed)
    entry_num = pd.to_numeric(trades["Entry (Rp)"], errors="coerce")
    lot_num = pd.to_numeric(trades["Lot"], errors="coerce")
    total_transaction_value = (entry_num * lot_num * 100).sum()

    return {
        "total": len(trades), "open": int((trades["Status"] == "OPEN").sum()),
        "win": win, "loss": loss, "winrate": winrate, "net_pl": net_pl,
        "profit_factor": profit_factor, "expectancy": expectancy,
        "total_transaction_value": total_transaction_value,
        "max_profit_rp": wins_df["Net P/L (Rp)_num"].max() if not wins_df.empty else 0,
        "max_loss_rp": losses_df["Net P/L (Rp)_num"].min() if not losses_df.empty else 0,
        "max_profit_pct": wins_df["Return %_num"].max() if not wins_df.empty else 0,
        "max_loss_pct": losses_df["Return %_num"].min() if not losses_df.empty else 0,
        "avg_profit_rp": wins_df["Net P/L (Rp)_num"].mean() if not wins_df.empty else 0,
        "avg_loss_rp": losses_df["Net P/L (Rp)_num"].mean() if not losses_df.empty else 0,
    }


def performance_by_stock(trades: pd.DataFrame) -> pd.DataFrame:
    """Breakdown P&L per kode saham - dipakai untuk tabel Top Gainer (mirip tampilan
    performance broker: Code, Trades, P&L Rp, P&L %)."""
    closed = trades[trades["Status"].isin(["PROFIT", "LOSS", "BREAKEVEN"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=["Saham", "Trade", "Net P/L (Rp)", "Rata-rata Return %"])
    closed["Net P/L (Rp)_num"] = pd.to_numeric(closed["Net P/L (Rp)"], errors="coerce")
    closed["Return %_num"] = pd.to_numeric(closed["Return %"], errors="coerce")
    grp = closed.groupby("Saham").agg(
        Trade=("No", "count"),
        **{"Net P/L (Rp)": ("Net P/L (Rp)_num", "sum")},
        **{"Rata-rata Return %": ("Return %_num", "mean")},
    ).reset_index()
    return grp.sort_values("Net P/L (Rp)", ascending=False).reset_index(drop=True)


def performance_by_broker(trades: pd.DataFrame) -> pd.DataFrame:
    closed = trades[trades["Status"].isin(["PROFIT", "LOSS", "BREAKEVEN"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=["Sekuritas", "Trade", "Win", "Net P/L", "Win Rate"])
    closed["Net P/L (Rp)_num"] = pd.to_numeric(closed["Net P/L (Rp)"], errors="coerce")
    grp = closed.groupby("Sekuritas").agg(
        Trade=("No", "count"),
        Win=("Status", lambda s: (s == "PROFIT").sum()),
        **{"Net P/L": ("Net P/L (Rp)_num", "sum")},
    ).reset_index()
    grp["Win Rate"] = (grp["Win"] / grp["Trade"] * 100).round(1)
    return grp


def performance_by_setup(trades: pd.DataFrame) -> pd.DataFrame:
    closed = trades[trades["Status"].isin(["PROFIT", "LOSS", "BREAKEVEN"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=["Setup", "Trade", "Win", "Net P/L", "Win Rate"])
    closed["Net P/L (Rp)_num"] = pd.to_numeric(closed["Net P/L (Rp)"], errors="coerce")
    grp = closed.groupby("Setup").agg(
        Trade=("No", "count"),
        Win=("Status", lambda s: (s == "PROFIT").sum()),
        **{"Net P/L": ("Net P/L (Rp)_num", "sum")},
    ).reset_index()
    grp["Win Rate"] = (grp["Win"] / grp["Trade"] * 100).round(1)
    return grp


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    """Kurva ekuitas kumulatif, dihitung di pandas (bukan formula Excel) supaya tidak
    rusak kalau ada baris OPEN (belum exit) di tengah data - beda dengan file referensi Bro."""
    closed = trades[trades["Status"].isin(["PROFIT", "LOSS", "BREAKEVEN"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=["Tanggal Exit", "Net P/L (Rp)", "Kumulatif (Rp)"])
    closed["Net P/L (Rp)_num"] = pd.to_numeric(closed["Net P/L (Rp)"], errors="coerce")
    closed["Tanggal Exit_dt"] = pd.to_datetime(closed["Tanggal Exit"], errors="coerce")
    closed = closed.dropna(subset=["Tanggal Exit_dt"]).sort_values("Tanggal Exit_dt")
    closed["Kumulatif (Rp)"] = closed["Net P/L (Rp)_num"].cumsum()
    return closed[["Tanggal Exit_dt", "Net P/L (Rp)_num", "Kumulatif (Rp)"]].rename(
        columns={"Tanggal Exit_dt": "Tanggal Exit", "Net P/L (Rp)_num": "Net P/L (Rp)"}
    )
