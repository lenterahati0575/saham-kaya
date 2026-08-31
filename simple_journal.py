"""
Jurnal SCREENER SEDERHANA (pembanding) - sheet Google Sheets TERPISAH ("POSISI_SEDERHANA")
dari jurnal utama (gsheet_journal.py, sheet "POSISI") - supaya performanya bisa dibandingkan
apel-ke-apel scr LIVE, bukan cuma backtest sekali jalan. Latar belakang: user - "apakah
perlu buat screener pembanding. mungkin lebih sederhana tapi bisa winrate lebih tinggi dan
buy/sellnya tepat", lalu diminta bikin "Sistem screener terpisah yang jalan live" (bukan
cuma uji backtest), dan "target saya yang penting profit dengan risk rendah, tetap
profesional".

Kandidatnya dari `screener.py::build_simple_candidates()` (breakout + posisi 52-minggu +
volume rendah, SL dibatasi 5%). Exit-nya 2 LAPIS (DIUJI, README > "Target-Lock" & lapis
partial): begitu profit capai 0,7x risiko awal, SL digeser naik SEBAGIAN (kunci 0,5x
risiko, BUKAN breakeven penuh) - lapis pertama, melindungi untung yang SUDAH terbentuk
kalau harga balik SEBELUM Target tercapai (user: "dalam banyak kasus saya terlambat
menjual karena target belum tercapai sudah balik arah"). Begitu Target akhirnya
tersentuh, SL digeser lagi ke Target-0,5xRisiko (lapis kedua, SAMA dgn gsheet_journal.py)
- posisi TETAP OPEN, dibiarkan jalan lebih jauh kalau tren lanjut.

Struktur kolom SENGAJA lebih ringkas dari POSISI (gsheet_journal.py) - user: "mungkin
versi baru tidak perlu banyak header, kecuali sudah sukses bisa migrasi yang lama" - baru
ditambah kolom/kerumitan kalau screener sederhana ini benar2 terbukti bagus di live &
dipertimbangkan utk migrasi sistem utama.

STRUKTUR KOLOM:
A: Tanggal Open | B: Saham | C: Harga Beli | D: TP | E: SL | F: Lot |
G: Tanggal Close | H: Harga Jual | I: P&L (Rp) | J: P&L (%) | K: Status | L: SL Awal |
M: Tipe Sinyal | N: Harga Puncak

M ("Tipe Sinyal": 'Breakout'/'ZigZag') ditambahkan setelah user - "mungkin perlu diuji
juga penggunaan zig zag" - divalidasi (README > "Zig Zag: Entry Tambahan") sbg entry
TAMBAHAN (OR, bukan pengganti) di `screener.py::build_simple_candidates()`. Kolom ini
CUMA label asal sinyal (utk breakdown performa live per tipe nanti) - TIDAK dipakai di
logika exit sama sekali.

N ("Harga Puncak") ditambahkan setelah user cerita masalah nyata: "hari ini muncul
sinyal buy, lalu besok... harga turun, tapi masih profit... saya tahan tidak jual
karena target belum tercapai... ternyata trader profesional... sempat jual dalam
kondisi profit, sedangkan saya tahan dan akhirnya rugi/nyangkut... apakah memungkinkan
saham yang sudah pernah masuk screener buy tetap dikawal jika muncul sinyal sell...
saya belum sampai dilevel prediksi seperti itu." Dipakai utk SINYAL JUAL DINI (lihat
SELL_DRAWDOWN_PCT di bawah) - TIDAK butuh prediksi arah, cuma deteksi harga SUDAH
turun sekian % dari titik tertingginya sejak dibeli, SAMBIL masih profit.

Sheet yang sudah live SEBELUM kolom M/N ada otomatis dilengkapi header-nya oleh
`_get_worksheet()` - user TIDAK perlu tambah kolom manual.
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
SHEET_NAME = "POSISI_SEDERHANA"

HEADERS = ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Lot",
           "Tanggal Close", "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "SL Awal",
           "Tipe Sinyal", "Harga Puncak"]
NUMERIC_COLS = ["Harga Beli", "TP", "SL", "Lot", "Harga Jual", "P&L (Rp)", "P&L (%)", "SL Awal",
                "Harga Puncak"]

FEE_PCT_ROUNDTRIP = 0.15 + 0.25
FORCE_SELL_HARI = 15

# Lapis 1 (partial-lock, SEBELUM Target): begitu profit (dari High) capai trigger_R x
# risiko awal, SL digeser ke lock_R x risiko awal (MASIH di atas breakeven=0, TIDAK
# penuh spt trailing-ke-breakeven lama yang terbukti buruk - lihat gsheet_journal.py).
# Lapis 2 (target-lock, SETELAH Target): SAMA dgn gsheet_journal.py, k=0.5R DI BAWAH
# Target. DIUJI (350 saham/3 tahun, walk-forward, README > "Lapis Pengaman Sebelum
# Target"): avg return cuma turun sedikit (+2,23% -> +2,16% utk sistem lama; dampak
# serupa diharapkan di screener sederhana ini) TAPI win rate NAIK HAMPIR 2X (32,7% ->
# 54,2%) & performa regime bearish berubah dari rugi jadi untung.
PARTIAL_TRIGGER_R = 0.7
PARTIAL_LOCK_R = 0.5
TARGET_LOCK_K = 0.5

# SINYAL JUAL DINI (2026-08-31, user: lihat catatan kolom "Harga Puncak" di atas) - dicek
# LEBIH DULU drpd lapis 1/2 di atas: begitu harga TUTUP hari ini turun >=SELL_DRAWDOWN_PCT%
# dari titik TERTINGGI sejak posisi dibuka, SAMBIL masih profit (harga_live > harga beli),
# jual SEKARANG - TIDAK menunggu SL/Target/lapis manapun. Ini BUKAN prediksi arah (Anda
# tidak perlu level analisis Astronacci) - cuma deteksi pelemahan yg SUDAH kejadian.
#
# DIUJI (350 saham/3 tahun, walk-forward, sbg tambahan di ATAS 2-lapis yang sudah ada):
# threshold 3%/5%/8%/10% SEMUANYA memperbaiki hasil (avg +7,34%->+7,90-8,05%, PF
# 4,73->5,16-5,27) - dipilih 5% (avg +8,05%, winrate 59,3%->60,9%, PF 5,27), DIVALIDASI
# split-half stabil (+8,84%/+7,26%) & KEDUA regime naik (Bullish PF 5,66->5,93, Bearish
# 3,42->4,33). Trade yang keluar via jalur ini winrate-nya ~100% by construction (syarat
# "masih profit" sudah di kode) & avg return jauh lebih tinggi (+23,4%) drpd trade yg
# keluar via SL/Target/ForceSell (+1,4%) - artinya rule ini menyelamatkan untung BESAR yg
# dulu dibiarkan jalan sampai balik ke level lock lama yg jauh dari puncak.
SELL_DRAWDOWN_PCT = 5.0


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
    """Auto-create kalau sheet POSISI_SEDERHANA belum ada - user tidak perlu bikin tab
    manual dulu, sama seperti riwayat_journal.py.

    Kalau sheet-nya SUDAH ada (live dari sebelum kolom baru ditambahkan ke HEADERS, mis.
    "Tipe Sinyal") - header row dilengkapi otomatis di sini juga, supaya kolom baru TIDAK
    perlu ditambah manual oleh user tiap kali HEADERS bertambah."""
    client = _get_client()
    sh = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    try:
        ws = sh.worksheet(SHEET_NAME)
        current_headers = ws.row_values(1)
        if len(current_headers) < len(HEADERS):
            from gspread.utils import rowcol_to_a1
            missing = HEADERS[len(current_headers):]
            start_cell = rowcol_to_a1(1, len(current_headers) + 1)
            end_cell = rowcol_to_a1(1, len(HEADERS))
            ws.update(f"{start_cell}:{end_cell}", [missing], value_input_option="USER_ENTERED")
        return ws
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        return ws


def _find_row_number(ws, saham: str, status: str = "OPEN") -> int | None:
    try:
        all_values = ws.get_all_values()
        for i, row_data in enumerate(all_values):
            # Kolom B (index 1) = Saham, Kolom K (index 10) = Status
            if len(row_data) >= 11 and row_data[1] == saham and row_data[10] == status:
                return i + 1
        return None
    except Exception as e:
        print(f"Error find row number for {saham}: {e}")
        return None


def _append_row(ws, row: list):
    ws.append_row(row, value_input_option="USER_ENTERED")


@st.cache_data(ttl=30, show_spinner=False)
def load_positions() -> pd.DataFrame:
    try:
        ws = _get_worksheet()
        records = ws.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=HEADERS)
        else:
            for col in NUMERIC_COLS:
                if col in df.columns:
                    cleaned = (df[col].astype(str)
                               .str.replace(".", "", regex=False)
                               .str.replace(",", ".", regex=False))
                    df[col] = pd.to_numeric(cleaned, errors="coerce")
        return df
    except Exception as e:
        print(f"Error load positions (simple journal): {e}")
        return pd.DataFrame(columns=HEADERS)


def open_positions_from_candidates(candidates: pd.DataFrame, max_new_per_day: int = 5) -> list[str]:
    """SAMA pola dgn gsheet_journal.py::open_positions_from_candidates() (cooldown 1x/hari
    per saham, batas total posisi baru/hari dihitung ULANG dari sheet tiap panggilan) -
    TIDAK ada parameter `tipe` (screener sederhana ini SATU tipe saja, tidak ada
    SWING/BPJS/BSJP)."""
    if candidates is None or candidates.empty:
        return []

    ws = _get_worksheet()
    existing = load_positions()
    open_symbols = set()
    opened_today_symbols = set()
    n_opened_today = 0
    if not existing.empty and "Status" in existing.columns:
        open_symbols = set(existing.loc[existing["Status"] == "OPEN", "Saham"])
    if not existing.empty and "Tanggal Open" in existing.columns:
        today_str = datetime.now(WIB).strftime("%Y-%m-%d")
        tgl_open_str = existing["Tanggal Open"].astype(str).str[:10]
        opened_today_symbols = set(existing.loc[tgl_open_str == today_str, "Saham"])
        n_opened_today = int((tgl_open_str == today_str).sum())

    slot_tersisa = max(0, max_new_per_day - n_opened_today)

    opened = []
    for _, row in candidates.iterrows():
        if len(opened) >= slot_tersisa:
            break
        kode = row["Saham"]
        if kode in open_symbols or kode in opened_today_symbols:
            continue
        try:
            entry = float(row["Entry"])
            tp = float(row["Target"])
            sl = float(row["Stop Loss"])
            lot = int(row.get("Lot", 10))
            if lot <= 0:
                lot = 10
            if tp <= entry and sl >= entry:
                tp, sl = sl, tp
            tipe_sinyal = row.get("Tipe Sinyal", "Breakout")  # fallback utk caller lama/test

            new_row = [
                datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),  # A: Tanggal Open
                kode,                                          # B: Saham
                entry,                                         # C: Harga Beli
                tp,                                            # D: TP
                sl,                                            # E: SL
                lot,                                           # F: Lot
                "",                                            # G: Tanggal Close
                "",                                            # H: Harga Jual
                "",                                            # I: P&L (Rp)
                "",                                            # J: P&L (%)
                "OPEN",                                        # K: Status
                sl,                                            # L: SL Awal
                tipe_sinyal,                                   # M: Tipe Sinyal
                entry,                                         # N: Harga Puncak (mulai dari harga beli)
            ]
            _append_row(ws, new_row)
            opened.append(kode)
            print(f"✅ [Sederhana] Buka posisi: {kode} @ Rp{entry:,.0f}, Lot: {lot}, TP: Rp{tp:,.0f}, SL: Rp{sl:,.0f}")
        except Exception as e:
            print(f"❌ [Sederhana] Error buka posisi {kode}: {e}")
            continue

    if opened:
        load_positions.clear()
    return opened


def preview_sinyal_jual_dini(price_lookup: dict, hl_lookup: dict | None = None) -> pd.DataFrame:
    """Preview READ-ONLY (TIDAK menutup posisi apa pun, TIDAK menulis ke sheet sama sekali)
    - SAMA fungsi dgn gsheet_journal.py::preview_sinyal_jual_dini(), direplikasi di sini
    supaya tab "🔬 Screener Sederhana" juga bisa menampilkan kotak "Sinyal Jual" seperti
    tab Kandidat. User: "lakukan juga discreener sederhana."""
    df = load_positions()
    if df.empty or "Status" not in df.columns:
        return pd.DataFrame()

    open_df = df[df["Status"] == "OPEN"]
    rows = []
    for _, row in open_df.iterrows():
        try:
            kode = row["Saham"]
            harga_live = price_lookup.get(kode)
            if harga_live is None:
                continue
            sl = float(row["SL"]) if pd.notna(row["SL"]) else None
            harga_beli = float(row["Harga Beli"])
            tgl_open = pd.to_datetime(row["Tanggal Open"])
            now_wib = datetime.now(WIB).replace(tzinfo=None)
            if tgl_open.date() == now_wib.date():
                continue  # SAMA guard sama-hari dgn auto_close_positions()

            hl = hl_lookup.get(kode) if hl_lookup else None
            today_high, today_low = hl if hl is not None else (harga_live, harga_live)

            peak_lama = float(row["Harga Puncak"]) if pd.notna(row.get("Harga Puncak")) and row.get("Harga Puncak") != "" else harga_beli
            peak_baru = max(peak_lama, today_high)

            sl_kena_hari_ini = sl is not None and today_low <= sl
            drawdown = (peak_baru - harga_live) / peak_baru * 100 if peak_baru > 0 else 0.0
            if sl_kena_hari_ini or harga_live <= harga_beli or drawdown < SELL_DRAWDOWN_PCT:
                continue

            pnl_pct = (harga_live - harga_beli) / harga_beli * 100
            rows.append({
                "Kode": kode,
                "Harga Beli": harga_beli,
                "Harga Sekarang": harga_live,
                "Puncak Sejak Beli": peak_baru,
                "Turun dari Puncak (%)": round(drawdown, 2),
                "P&L Saat Ini (%)": round(pnl_pct, 2),
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


def auto_close_positions(price_lookup: dict, hl_lookup: dict | None = None) -> list[str]:
    """2 lapis perlindungan (lihat komentar PARTIAL_TRIGGER_R/PARTIAL_LOCK_R/TARGET_LOCK_K
    di atas) + guard SAMA-HARI (SAMA persis bug & fix di gsheet_journal.py: posisi yang
    dibuka HARI INI di-skip total, exit HANYA dicek mulai hari kalender berikutnya - lihat
    README > "Bug Serius: Posisi Dijual di HARI YANG SAMA Dibeli")."""
    ws = _get_worksheet()
    df = load_positions()
    if df.empty or "Status" not in df.columns:
        return []

    open_df = df[df["Status"] == "OPEN"]
    needed = open_df["Saham"].unique()

    price_lookup = dict(price_lookup)
    hl_lookup = dict(hl_lookup or {})
    missing = [k for k in needed if k not in price_lookup]
    if missing:
        from screener import fetch_price_history
        try:
            fetched = fetch_price_history(missing, period="5d")
            for kode, df_price in fetched.items():
                if df_price.empty:
                    continue
                if "Close" in df_price.columns:
                    price_lookup[kode] = float(df_price["Close"].iloc[-1])
                if "High" in df_price.columns and "Low" in df_price.columns and kode not in hl_lookup:
                    hl_lookup[kode] = (float(df_price["High"].iloc[-1]), float(df_price["Low"].iloc[-1]))
        except Exception:
            pass

    closed = []
    any_trailed = False
    now_wib = datetime.now(WIB).replace(tzinfo=None)

    for idx, row in open_df.iterrows():
        try:
            kode = row["Saham"]
            harga_live = price_lookup.get(kode)
            if harga_live is None:
                continue

            tp = float(row["TP"]) if pd.notna(row["TP"]) else None
            sl = float(row["SL"]) if pd.notna(row["SL"]) else None
            harga_beli = float(row["Harga Beli"])
            sl_awal = float(row["SL Awal"]) if pd.notna(row.get("SL Awal")) else sl
            lot = int(row["Lot"]) if pd.notna(row.get("Lot")) else 10
            tgl_open = pd.to_datetime(row["Tanggal Open"])

            # Guard sama-hari (README > "Bug Serius: Posisi Dijual di HARI YANG SAMA Dibeli")
            if tgl_open.date() == now_wib.date():
                continue
            hari = (now_wib - tgl_open).days

            if tp is not None and sl is not None and tp <= harga_beli and sl >= harga_beli:
                tp, sl = sl, tp

            hl = hl_lookup.get(kode)
            today_high, today_low = hl if hl is not None else (harga_live, harga_live)

            status_baru = None
            exit_price = harga_live

            # Update "Harga Puncak" (kolom N) - fallback ke Harga Beli utk posisi lama yg
            # dibuka SEBELUM kolom ini ada (migrasi header otomatis, tapi nilai lama tetap
            # kosong sampai baris ini pernah diproses sekali).
            peak_lama = float(row["Harga Puncak"]) if pd.notna(row.get("Harga Puncak")) and row.get("Harga Puncak") != "" else harga_beli
            peak_baru = max(peak_lama, today_high)

            # SINYAL JUAL DINI (lihat catatan SELL_DRAWDOWN_PCT) - dicek sebelum lapis
            # partial/target, TAPI SETELAH cek SL hari ini (lihat guard `sl_kena_hari_ini`
            # di bawah) - user: "apakah memungkinkan saham yang sudah pernah masuk screener
            # buy tetap dikawal jika muncul sinyal sell akan muncul di screener walau tidak
            # mencapai target."
            #
            # BUG YANG DIPERBAIKI (2026-08-31, ditemukan saat mereplikasi ide ini ke
            # gsheet_journal.py): versi awal cek drawdown dari CLOSE tanpa peduli apakah SL
            # SAAT INI juga tersentuh hari yang SAMA (via Low) - kalau Low hari itu turun
            # sampai menembus sl_cur TAPI Close balik naik lagi sampai net masih profit
            # dgn drawdown>=threshold dari puncak, versi lama SALAH melabeli ini "WIN
            # (SINYAL JUAL DINI)" padahal SEHARUSNYA "LOSS (SL)"/lapis manapun yang aktif -
            # menyimpang dari konvensi "SL dicek LEBIH DULU" yang sudah dipakai di seluruh
            # sistem (lihat komentar sama persis di gsheet_journal.py::auto_close_positions
            # & backtest.py). Fix: Sinyal Jual Dini SEKARANG dijaga TIDAK aktif kalau Low
            # hari ini sudah <= SL yang sedang berlaku (`sl`, apa pun lapisnya) - re-validasi
            # backtest dgn urutan benar: PF sedikit lebih kecil dari yg dilaporkan sebelumnya
            # (5,27->5,03) TAPI tetap perbaikan nyata dari baseline (4,73), README > "Sinyal
            # Jual Dini" sudah diupdate ke angka yang benar.
            sl_kena_hari_ini = sl is not None and today_low <= sl
            drawdown_dari_peak = (peak_baru - harga_live) / peak_baru * 100 if peak_baru > 0 else 0.0
            if not sl_kena_hari_ini and harga_live > harga_beli and drawdown_dari_peak >= SELL_DRAWDOWN_PCT:
                status_baru = "WIN (SINYAL JUAL DINI)"
                exit_price = harga_live

            risk_awal = (harga_beli - sl_awal) if sl_awal is not None else None
            # Lapis mana yang sudah aktif, dideteksi dari SL SAAT INI vs SL Awal vs harga
            # beli - TIDAK perlu kolom status terpisah:
            #   - target_terkunci: SL > TP - TARGET_LOCK_K*risk_awal - k*sedikit (praktis:
            #     SL sudah "dekat/di atas" area kuncian target) ATAU lebih simpel & robust:
            #     SL >= harga_beli + PARTIAL_LOCK_R*risk_awal DAN Target sudah pernah
            #     tersentuh sebelumnya - tapi kita TIDAK menyimpan "target pernah tersentuh"
            #     sbg flag terpisah. Solusi robust: bandingkan SL SAAT INI relatif ke DUA
            #     level yang mungkin (partial-lock vs target-lock) - kalau SL >= level
            #     target-lock (yang PASTI lebih tinggi dari level partial-lock kalau
            #     TARGET_LOCK_K position konsisten), anggap sudah di lapis TARGET.
            partial_lock_level = (harga_beli + PARTIAL_LOCK_R * risk_awal) if risk_awal and risk_awal > 0 else None
            target_lock_level = (tp - TARGET_LOCK_K * risk_awal) if (risk_awal and risk_awal > 0 and tp is not None) else None
            sudah_partial = partial_lock_level is not None and sl is not None and sl >= partial_lock_level - 0.01
            sudah_target = target_lock_level is not None and sl is not None and sl >= target_lock_level - 0.01

            if status_baru is not None:
                pass  # Sinyal Jual Dini sudah memutuskan di atas - lewati lapis 1/2 di bawah.
            elif sudah_target:
                if today_low <= sl:
                    status_baru = "WIN (TARGET TERKUNCI)"
                    exit_price = sl
                elif hari >= FORCE_SELL_HARI:
                    status_baru = f"WIN (FORCE SELL target terkunci, {hari} hari)"
                    exit_price = harga_live
            elif sudah_partial:
                if today_low <= sl:
                    # Selalu untung kalau sampai tersentuh (exit = harga_beli +
                    # PARTIAL_LOCK_R*risk_awal, PARTIAL_LOCK_R>0 & risk_awal>0 selalu) -
                    # dilabel WIN, bukan status neutral, biar summarize() (cek substring
                    # "WIN") menghitungnya benar sbg kemenangan, bukan diam2 terlewat.
                    status_baru = "WIN (PARTIAL LOCK)"
                    exit_price = sl
                elif tp is not None and today_high >= tp:
                    if risk_awal and risk_awal > 0:
                        sl_baru = tp - TARGET_LOCK_K * risk_awal
                        sheet_row = _find_row_number(ws, kode, "OPEN")
                        if sheet_row:
                            ws.update(f"E{sheet_row}", [[float(sl_baru)]])
                            any_trailed = True
                            print(f"🔒 [Sederhana] {kode}: Target tercapai, untung dikunci penuh - SL -> Rp{sl_baru:,.0f}")
                    else:
                        status_baru = "WIN (TP)"
                        exit_price = tp
                elif hari >= FORCE_SELL_HARI:
                    status_baru = "WIN (FORCE SELL, partial locked)"
                    exit_price = harga_live
            else:
                if sl is not None and today_low <= sl:
                    status_baru = "LOSS (SL)"
                    exit_price = sl
                elif tp is not None and today_high >= tp:
                    if risk_awal and risk_awal > 0:
                        sl_baru = tp - TARGET_LOCK_K * risk_awal
                        sheet_row = _find_row_number(ws, kode, "OPEN")
                        if sheet_row:
                            ws.update(f"E{sheet_row}", [[float(sl_baru)]])
                            any_trailed = True
                            print(f"🔒 [Sederhana] {kode}: Target tercapai, untung dikunci - SL -> Rp{sl_baru:,.0f}")
                    else:
                        status_baru = "WIN (TP)"
                        exit_price = tp
                elif risk_awal and risk_awal > 0 and today_high >= harga_beli + PARTIAL_TRIGGER_R * risk_awal:
                    sl_baru = harga_beli + PARTIAL_LOCK_R * risk_awal
                    sheet_row = _find_row_number(ws, kode, "OPEN")
                    if sheet_row:
                        ws.update(f"E{sheet_row}", [[float(sl_baru)]])
                        any_trailed = True
                        print(f"🛡️ [Sederhana] {kode}: Profit {PARTIAL_TRIGGER_R}R tercapai, kunci sebagian - SL -> Rp{sl_baru:,.0f}")
                elif hari >= FORCE_SELL_HARI:
                    status_baru = f"FORCE SELL ({hari} hari)"
                    exit_price = harga_live

            # Simpan "Harga Puncak" terbaru (kolom N) kalau posisi TETAP OPEN & puncaknya
            # naik - biar deteksi Sinyal Jual Dini besok jalan dari titik tertinggi yg
            # BENAR, bukan cuma harga beli. Kalau posisi mau ditutup di bawah (status_baru
            # sudah terisi), tidak perlu ditulis - sudah tidak relevan.
            if status_baru is None and peak_baru > peak_lama:
                sheet_row = _find_row_number(ws, kode, "OPEN")
                if sheet_row:
                    ws.update(f"N{sheet_row}", [[float(peak_baru)]])
                    any_trailed = True

            if status_baru:
                sheet_row = _find_row_number(ws, kode, "OPEN")
                if sheet_row:
                    modal_rp = harga_beli * 100 * lot
                    fee_rp = modal_rp * (FEE_PCT_ROUNDTRIP / 100)
                    pnl_rp = (exit_price - harga_beli) * 100 * lot - fee_rp
                    pnl_pct = (pnl_rp / modal_rp) * 100 if modal_rp > 0 else 0.0
                    ws.update(f"G{sheet_row}:K{sheet_row}", [[
                        datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),
                        float(exit_price),
                        round(pnl_rp, 2),
                        round(pnl_pct, 2),
                        status_baru,
                    ]])
                    closed.append(f"{kode} ({status_baru})")
                    print(f"✅ [Sederhana] Tutup posisi: {kode} @ Rp{exit_price:,.0f} - {status_baru}, P&L: Rp{pnl_rp:,.0f}")
                else:
                    print(f"❌ [Sederhana] Tidak menemukan baris {kode} dengan status OPEN")
        except Exception as e:
            print(f"❌ [Sederhana] Error proses posisi {row.get('Saham', 'UNKNOWN')}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if closed or any_trailed:
        load_positions.clear()
    return closed


def summarize(df: pd.DataFrame) -> dict:
    """SAMA logika dgn gsheet_journal.py::summarize() - klasifikasi WIN/LOSS dari substring
    Status + tanda P&L utk FORCE SELL, tanpa kategori BREAKEVEN (screener ini tidak pernah
    menghasilkan breakeven murni - lapis partial-lock & target-lock SELALU mengunci DI ATAS
    harga beli, lihat pembuktian matematis di gsheet_journal.py)."""
    if df.empty:
        return {"total": 0, "open": 0, "win": 0, "loss": 0, "winrate": 0.0, "total_pnl_pct": 0.0}

    total = len(df)
    open_n = int((df["Status"] == "OPEN").sum()) if "Status" in df.columns else 0
    win = loss = 0
    if "Status" in df.columns:
        status_str = df["Status"].astype(str)
        is_force_sell = status_str.str.contains("FORCE SELL", case=False, na=False)
        pnl_num = pd.to_numeric(df["P&L (%)"], errors="coerce") if "P&L (%)" in df.columns else pd.Series([float("nan")] * len(df), index=df.index)
        win_mask = status_str.str.contains("WIN", case=False, na=False) | (is_force_sell & (pnl_num > 0))
        loss_mask = status_str.str.contains("LOSS", case=False, na=False) | (is_force_sell & (pnl_num <= 0))
        win = int(win_mask.sum())
        loss = int(loss_mask.sum())

    closed_n = win + loss
    winrate = (win / closed_n * 100) if closed_n > 0 else 0.0
    total_pnl_pct = 0.0
    if "P&L (%)" in df.columns:
        total_pnl_pct = pd.to_numeric(df["P&L (%)"], errors="coerce").sum()
        if pd.isna(total_pnl_pct):
            total_pnl_pct = 0.0

    return {
        "total": total, "open": open_n, "win": win, "loss": loss,
        "winrate": winrate, "total_pnl_pct": total_pnl_pct,
    }
