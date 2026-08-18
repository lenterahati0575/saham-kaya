"""
Jurnal backtest POSISI, terhubung ke Google Sheets (sheet 'POSISI').
Auto-BUY saat Signal = BUY/STRONG BUY, auto-SELL saat harga live menyentuh TP atau SL.

STRUKTUR KOLOM (dengan Lot & SL Awal):
A: Tanggal Open | B: Saham | C: Harga Beli | D: TP | E: SL | F: Tipe |
G: Lot | H: Tanggal Close | I: Harga Jual | J: P&L (Rp) | K: P&L (%) |
L: Status | M: Hari | N: SL Awal

N (SL Awal): SL asli saat posisi dibuka - TIDAK PERNAH diubah setelahnya, beda dari
kolom E (SL) yang BISA di-trail naik ke breakeven setelah profit >=1R (lihat
auto_close_positions()). Dipakai utk menghitung ulang jarak risk (Harga Beli - SL Awal)
kapan saja tanpa peduli SL sudah ditrail atau belum. Baris LAMA (dibuka sebelum kolom
ini ada) akan kosong - auto_close_positions() fallback ke SL saat ini sbg SL Awal utk
baris itu (tidak bisa trailing, tapi tidak crash).
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

# WAJIB pakai timezone Asia/Jakarta (WIB) secara eksplisit - server (Streamlit Cloud/GitHub
# Actions) jalan di UTC, jadi datetime.now() polos akan tercatat 7 jam lebih awal dari jam
# WIB sebenarnya. Bug nyata yang ditemukan dari laporan user: posisi tercatat "Tanggal Open"
# jam 05:26 padahal dibuka jam 12:26 WIB sebenarnya - sama persis kelas bug yang sudah
# diperbaiki di get_market_session() (app.py) tapi belum pernah diterapkan di sini.
WIB = ZoneInfo("Asia/Jakarta")

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    # drive.file (BUKAN drive penuh): cukup untuk akses file yang sudah di-share ke Service
    # Account ini (sheet POSISI dkk) - kalau key ini bocor, exposure-nya cuma sheet yang
    # memang sudah di-share, bukan seluruh Drive pemiliknya.
    "https://www.googleapis.com/auth/drive.file",
]
SHEET_NAME = "POSISI"

# Fee round-trip default (0.15% beli + 0.25% jual, sama seperti default broker di
# real_journal.py) - Jurnal Backtest ini simulasi umum (bukan per-broker seperti Jurnal
# Real), tapi P&L tanpa fee sama sekali akan systematically overstate profit dibanding
# transaksi riil. Dipotong dari P&L supaya angka win rate/profit di tab Performance lebih
# dekat ke kenyataan, bukan return kotor.
FEE_PCT_ROUNDTRIP = 0.15 + 0.25

# HEADERS DENGAN KOLOM LOT (kolom G) & SL Awal (kolom N)
HEADERS = ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Tipe",
           "Lot", "Tanggal Close", "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "Hari", "SL Awal"]

# Kolom numerik (non-tanggal, non-teks) - dipakai load_positions() utk parsing manual.
NUMERIC_COLS = ["Harga Beli", "TP", "SL", "Lot", "Harga Jual", "P&L (Rp)", "P&L (%)", "Hari", "SL Awal"]

# Trailing stop: begitu profit floating (dari High hari itu) mencapai kelipatan risk awal
# (Harga Beli - SL Awal) sebesar ini, SL dinaikkan SEKALI ke breakeven (Harga Beli).
# Dibacktest (615 saham/5 tahun, walk-forward, README > "Trailing Stop ke Breakeven"):
# avg net return naik dari +0.62% (SL/TP tetap) jadi +0.78% (trailing), konsisten di 2
# periode (+0.12%/+0.20%). TIDAK trailing lebih jauh dari breakeven (cuma 1 langkah) -
# belum diuji versi trailing bertingkat.
TRAILING_TRIGGER_R = 1.0


def is_configured() -> bool:
    """Cek apakah semua konfigurasi Google Sheets sudah lengkap."""
    return (
        GSPREAD_AVAILABLE
        and "gcp_service_account" in st.secrets
        and "GOOGLE_SHEET_ID" in st.secrets
    )


@st.cache_resource(show_spinner=False)
def _get_client():
    """Inisialisasi client Google Sheets (cached untuk performa)."""
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


def _get_worksheet():
    """Ambil worksheet POSISI dari Google Sheets."""
    client = _get_client()
    sh = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    return sh.worksheet(SHEET_NAME)


@st.cache_data(ttl=30, show_spinner=False)
def load_positions() -> pd.DataFrame:
    """Load semua posisi dari Google Sheets ke DataFrame.

    BUG NYATA yang ditemukan dari laporan user (lihat screenshot tab Performance -
    P&L GDST tampil Rp1.316.832/+701%, padahal sheet aslinya Rp131.683,2/+7,01%):
    `ws.get_all_records()` bawaan gspread numericise-kan tiap sel SENDIRI, dan
    `gspread.utils.numericise()` menganggap koma = pemisah RIBUAN gaya Inggris lalu
    MENGHAPUSNYA sblm parsing (lihat docstring-nya sendiri: `numericise("2,000.1")
    -> 2000.1`). Sel locale Indonesia yang tampil "131683,2" (koma = DESIMAL) jadi
    "1316832" - inflasi 10x kalau 1 digit desimal, 100x kalau 2 digit (P&L (%)).
    Ini BUKAN salah rumus P&L (sudah diverifikasi manual thd sheet asli, rumus di
    auto_close_positions() benar) - murni salah baca oleh gspread di sisi ini.

    Fix: `numericise_ignore=['all']` mematikan numericise otomatis gspread (semua sel
    balik jadi string APA ADANYA, sesuai FORMAT TAMPILAN sheet) - lalu kolom numerik
    diparsing manual DI SINI dgn urutan yg benar utk locale Indonesia: hapus titik
    (pemisah ribuan) dulu, BARU ganti koma jadi titik (desimal)."""
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
        print(f"Error load positions: {e}")
        return pd.DataFrame(columns=HEADERS)


def _append_row(ws, row: list):
    """Append row baru ke Google Sheets."""
    ws.append_row(row, value_input_option="USER_ENTERED")


def _find_row_number(ws, saham: str, status: str = "OPEN") -> int:
    """
    Cari nomor baris di Google Sheet berdasarkan kode saham dan status.
    Return nomor baris (1-based, header = 1) atau None jika tidak ditemukan.
    """
    try:
        all_values = ws.get_all_values()
        
        for i, row_data in enumerate(all_values):
            # Kolom B (index 1) = Saham, Kolom L (index 11) = Status
            if len(row_data) >= 12:
                if row_data[1] == saham and row_data[11] == status:
                    return i + 1  # +1 karena gspread 1-based
        
        return None
    except Exception as e:
        print(f"Error find row number for {saham}: {e}")
        return None


def open_positions_from_candidates(candidates: pd.DataFrame, tipe: str) -> list[str]:
    """Buka posisi baru dari tabel kandidat (hasil screener.build_trade_candidates).
    
    Args:
        candidates: DataFrame dengan kolom Saham, Entry, Target, Stop Loss, Lot (opsional)
        tipe: 'BPJS', 'BSJP', atau 'SWING'
    
    Returns:
        List kode saham yang berhasil dibuka
    """
    if candidates is None or candidates.empty:
        return []
    
    ws = _get_worksheet()
    existing = load_positions()
    open_symbols = set()
    opened_today_symbols = set()
    if not existing.empty and "Status" in existing.columns:
        open_symbols = set(existing.loc[existing["Status"] == "OPEN", "Saham"])
    # Cooldown 1 hari/saham: cegah re-entry di HARI YANG SAMA stlh saham ini kena SL/close -
    # ditemukan lewat laporan user (screenshot sheet POSISI): SLIS/ESTI/PTMP masing2 dibuka
    # 2x dlm 1 hari (kena SL pagi/siang, lalu re-entry sore krn masih lolos sbg kandidat) -
    # bukan bug backtest, tapi celah nyata: guard lama cuma cek "OPEN sekarang", bukan
    # "sudah pernah dibuka/ditutup HARI INI". Tanpa cooldown ini, sistem bisa berulang kali
    # ngejar saham yg baru saja gagal di hari yang sama.
    if not existing.empty and "Tanggal Open" in existing.columns:
        today_str = datetime.now(WIB).strftime("%Y-%m-%d")
        tgl_open_str = existing["Tanggal Open"].astype(str).str[:10]
        opened_today_symbols = set(existing.loc[tgl_open_str == today_str, "Saham"])

    opened = []
    for _, row in candidates.iterrows():
        kode = row["Saham"]

        # Skip jika sudah ada posisi open, ATAU sudah pernah dibuka hari ini (cooldown 1x/hari)
        if kode in open_symbols or kode in opened_today_symbols:
            continue
        
        try:
            entry = float(row["Entry"])
            tp = float(row["Target"])
            sl = float(row["Stop Loss"])
            
            # Ambil lot dari kandidat, atau default 10 lot
            lot = int(row.get("Lot", 10))
            if lot <= 0:
                lot = 10
            
            # Validasi dan auto-swap TP/SL jika terbalik (untuk posisi LONG)
            if tp <= entry and sl >= entry:
                print(f"⚠️ {kode}: TP ({tp}) dan SL ({sl}) terbalik, auto-swap")
                tp, sl = sl, tp
            
            # Buat row baru sesuai struktur HEADERS
            new_row = [
                datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),  # A: Tanggal Open
                kode,                                         # B: Saham
                entry,                                        # C: Harga Beli
                tp,                                           # D: TP
                sl,                                           # E: SL
                tipe,                                         # F: Tipe
                lot,                                          # G: Lot (BARU!)
                "",                                           # H: Tanggal Close
                "",                                           # I: Harga Jual
                "",                                           # J: P&L (Rp)
                "",                                           # K: P&L (%)
                "OPEN",                                       # L: Status
                "",                                           # M: Hari
                sl,                                           # N: SL Awal (SAMA dgn SL saat buka -
                                                               # kolom E bisa ditrail nanti, ini tidak)
            ]
            
            _append_row(ws, new_row)
            opened.append(kode)
            print(f"✅ Buka posisi: {kode} @ Rp{entry:,.0f}, Lot: {lot}, TP: Rp{tp:,.0f}, SL: Rp{sl:,.0f}")
            
        except Exception as e:
            print(f"❌ Error buka posisi {kode}: {e}")
            continue
    
    # Clear cache karena data berubah
    if opened:
        load_positions.clear()
    
    return opened


def enrich_price_lookup(price_lookup: dict, tickers_needed) -> dict:
    """Lengkapi `price_lookup` dgn harga saham yang dibutuhkan tapi TIDAK ada di dalamnya
    (mis. posisi OPEN pada saham di luar window scan dashboard) - fetch harga tambahan
    khusus utk saham yang kurang saja, bukan fetch ulang semuanya.

    SENGAJA diekspos sbg fungsi terpisah (dipakai bareng oleh `auto_close_positions()` DAN
    tampilan debug tabel "Posisi yang dicek" di app.py) - dulu debug tabel itu baca
    `price_lookup` yang BELUM dilengkapi (langsung dari caller), sementara
    `auto_close_positions()` melengkapinya sendiri secara internal - user melihat debug
    tabel bilang "N/A" (kelihatan seperti bug) padahal logika penutupan di baliknya sudah
    benar. Sekarang keduanya pakai fungsi yang SAMA, supaya apa yang user LIHAT konsisten
    dengan apa yang sistem benar-benar pakai untuk memutuskan tutup/tidak."""
    price_lookup = dict(price_lookup)
    missing = [k for k in tickers_needed if k not in price_lookup]
    if missing:
        from screener import fetch_price_history
        try:
            missing_price_data = fetch_price_history(missing, period="5d")
            for kode, df_price in missing_price_data.items():
                if not df_price.empty and "Close" in df_price.columns:
                    price_lookup[kode] = float(df_price["Close"].iloc[-1])
        except Exception:
            pass  # fetch tambahan gagal (mis. rate-limit) - lanjut dgn apa yang sudah ada
    return price_lookup


def enrich_hl_lookup(hl_lookup: dict, tickers_needed) -> dict:
    """Sama seperti enrich_price_lookup(), tapi utk High/Low hari ini (bukan cuma Close) -
    dipakai auto_close_positions() supaya bisa cek TP/SL via HIGH/LOW intrabar utk saham
    yang posisinya OPEN tapi di luar batch scan dashboard. Fetch TERPISAH dari
    enrich_price_lookup() (bukan digabung) - fungsi murni ini sengaja dibuat mandiri &
    simpel, mirror pola yang sudah ada, drpd mengubah signature enrich_price_lookup() yang
    sudah dipakai & ditest di tempat lain."""
    hl_lookup = dict(hl_lookup)
    missing = [k for k in tickers_needed if k not in hl_lookup]
    if missing:
        from screener import fetch_price_history
        try:
            missing_price_data = fetch_price_history(missing, period="5d")
            for kode, df_price in missing_price_data.items():
                if not df_price.empty and "High" in df_price.columns and "Low" in df_price.columns:
                    hl_lookup[kode] = (float(df_price["High"].iloc[-1]), float(df_price["Low"].iloc[-1]))
        except Exception:
            pass  # fetch tambahan gagal - lanjut dgn apa yang sudah ada (fallback ke harga Close saja)
    return hl_lookup


def auto_close_positions(price_lookup: dict, hl_lookup: dict | None = None) -> list[str]:
    """Cek semua posisi OPEN: tutup kalau TP/SL tersentuh, ATAU force-sell sesuai aturan waktu.

    Aturan force-sell:
    - SWING  : force sell kalau sudah 15 hari dan belum kena TP/SL (dinaikkan dari 10 hari -
      divalidasi lewat backtest realistis + out-of-sample: 15 hari net lebih profitable
      daripada 10 hari di kedua periode uji, lihat README bagian "Backtest Historis").
    - BPJS   : force sell kalau sudah lewat 1 hari (mestinya keluar hari yang sama).
    - BSJP   : force sell kalau sudah lewat 2 hari (mestinya keluar besok pagi).

    Args:
        price_lookup: Dict {kode_saham: harga_sekarang (Close)} - tetap dipakai sbg exit
            price utk FORCE SELL, dan fallback kalau hl_lookup tidak tersedia utk saham itu.
        hl_lookup: Dict {kode_saham: (High_hari_ini, Low_hari_ini)}, opsional. TANPA ini,
            TP/SL dicek cuma dari 1 titik harga (Close) - bisa MELEWATKAN TP/SL yang
            sebenarnya tersentuh intraday lalu harga balik lagi sebelum sempat dicek (gap
            nyata vs backtest yang mengasumsikan tersentuh High/Low bar - lihat README).
            DENGAN hl_lookup, TP dicek dari High hari itu & SL dari Low hari itu - jauh
            lebih dekat ke metodologi backtest yang sudah divalidasi.

    Returns:
        List string format "KODE (ALASAN)" untuk posisi yang ditutup
    """
    ws = _get_worksheet()
    df = load_positions()

    if df.empty or "Status" not in df.columns:
        return []

    open_df = df[df["Status"] == "OPEN"]
    needed = open_df["Saham"].unique()

    # Lengkapi price_lookup (DAN High/Low kalau tersedia di respons yang SAMA) dgn saham
    # yg posisinya OPEN tapi TIDAK masuk batch yang baru dipindai dashboard (mis. di luar
    # window alfabetis "Jumlah saham dipindai" default) - tanpa ini, posisi itu di-skip via
    # `continue` di bawah dan TIDAK PERNAH bisa dicek TP/SL/force-sell SELAMANYA, walau
    # sudah jauh lewat batas waktunya. Bug nyata yang ditemukan dari laporan user - 9 dari
    # 14 posisi OPEN saat itu di luar window scan default (400).
    #
    # SATU fetch saja utk saham yang kurang dari price_lookup (bukan panggil
    # enrich_price_lookup() lalu enrich_hl_lookup() terpisah - itu akan memanggil
    # fetch_price_history() 2x utk ticker yang SAMA, buang kuota Yahoo Finance tanpa guna).
    # Saham yang SUDAH ada di price_lookup (dlm window scan) tapi kebetulan tidak ada di
    # hl_lookup (mis. caller lama yang belum kasih hl_lookup sama sekali) TIDAK memicu
    # fetch baru - fallback diam2 ke Close-only utk saham itu di bagian bawah (perilaku
    # lama, tetap benar walau kurang presisi drpd yang ada High/Low-nya).
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
            pass  # fetch tambahan gagal (mis. rate-limit) - lanjut dgn apa yang sudah ada

    FORCE_SELL_HARI = {"SWING": 15, "BPJS": 1, "BSJP": 2}
    closed = []
    any_trailed = False  # SL ditrail ke breakeven (posisi TETAP OPEN, bukan ditutup) -
    # cache load_positions() tetap harus di-clear kalau ini terjadi, sama seperti `closed`.

    # Ambil semua data dari sheet untuk mapping nomor baris yang akurat
    all_values = ws.get_all_values()

    for idx, row in open_df.iterrows():
        try:
            kode = row["Saham"]
            harga_live = price_lookup.get(kode)

            if harga_live is None:
                continue

            # Parse data dari row
            tp = float(row["TP"]) if pd.notna(row["TP"]) else None
            sl = float(row["SL"]) if pd.notna(row["SL"]) else None
            harga_beli = float(row["Harga Beli"])
            # SL Awal - fallback ke SL SAAT INI kalau kosong (baris lama dibuka sebelum
            # kolom ini ada) - konsekuensinya baris lama itu tidak bisa trailing (risk
            # awal tidak diketahui), tapi TIDAK crash, perilaku sama seperti sebelumnya.
            sl_awal = float(row["SL Awal"]) if pd.notna(row.get("SL Awal")) else sl
            lot = int(row["Lot"]) if pd.notna(row.get("Lot")) else 10
            tgl_open = pd.to_datetime(row["Tanggal Open"])
            # "Tanggal Open" ditulis pakai jam WIB (lihat open_positions_from_candidates) -
            # naive, jadi "now" WIB-nya juga di-strip tzinfo dulu spy angka jamnya konsisten
            # dibandingkan (bukan dibandingkan dgn UTC polos yg 7 jam lebih awal).
            hari = (datetime.now(WIB).replace(tzinfo=None) - tgl_open).days
            tipe = str(row.get("Tipe", "")).strip().upper()

            # Validasi dan auto-swap TP/SL jika terbalik (untuk posisi LONG)
            if tp is not None and sl is not None:
                if tp <= harga_beli and sl >= harga_beli:
                    print(f"⚠️ {kode}: TP/SL terbalik, auto-swap")
                    tp, sl = sl, tp

            # High/Low HARI INI kalau ada (dari hl_lookup) - fallback ke harga_live (titik
            # tunggal) kalau tidak tersedia, SAMA seperti perilaku LAMA (sebelum hl_lookup ada).
            hl = hl_lookup.get(kode)
            today_high, today_low = hl if hl is not None else (harga_live, harga_live)

            status_baru = None
            exit_price = harga_live

            # SL dicek LEBIH DULU (asumsi konservatif kalau High & Low hari yang sama
            # menyentuh TP dan SL sekaligus) - SAMA PERSIS urutannya dgn
            # backtest.py::_simulate_realistic_trades_single(), supaya hasil live tidak
            # sistematis lebih optimis drpd yang sudah dibuktikan backtest. Exit price
            # dicatat TEPAT di level TP/SL (bukan di High/Low ekstrem hari itu, dan bukan di
            # harga_live/Close) - juga sama dgn asumsi backtest, supaya P&L live sebanding
            # dgn P&L yang diklaim hasil backtest, bukan angka yang beda metodologi.
            # Sudah di breakeven kalau SL sekarang == Harga Beli (ditrail di run
            # SEBELUMNYA) - dipakai utk membedakan label "BREAKEVEN" (untung kecil/rugi
            # tipis krn fee, TAPI TERHINDAR dari rugi lebih dalam) dari "LOSS (SL)" biasa
            # (SL asli, belum pernah ditrail).
            sudah_breakeven = sl is not None and abs(sl - harga_beli) < 0.01

            if sl is not None and today_low <= sl:
                status_baru = "BREAKEVEN" if sudah_breakeven else "LOSS (SL)"
                exit_price = sl
            elif tp is not None and today_high >= tp:
                status_baru = "WIN (TP)"
                exit_price = tp
            elif hari >= FORCE_SELL_HARI.get(tipe, 15):
                status_baru = f"FORCE SELL ({hari} hari)"
                exit_price = harga_live

            if status_baru:
                # Cari nomor baris yang AKURAT di Google Sheet
                sheet_row = _find_row_number(ws, kode, "OPEN")

                if sheet_row:
                    # Hitung P&L dengan memperhitungkan Lot (1 lot = 100 lembar) DAN fee
                    # round-trip - tanpa ini, P&L simulasi selalu lebih bagus dari yang bisa
                    # dicapai transaksi riil (lihat FEE_PCT_ROUNDTRIP di atas).
                    modal_rp = harga_beli * 100 * lot
                    fee_rp = modal_rp * (FEE_PCT_ROUNDTRIP / 100)
                    pnl_rp = (exit_price - harga_beli) * 100 * lot - fee_rp
                    pnl_pct = (pnl_rp / modal_rp) * 100 if modal_rp > 0 else 0.0

                    # Update kolom H sampai M (Tanggal Close, Harga Jual, P&L Rp, P&L %, Status, Hari)
                    ws.update(f"H{sheet_row}:M{sheet_row}", [[
                        datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),  # H: Tanggal Close
                        float(exit_price),                          # I: Harga Jual
                        round(pnl_rp, 2),                           # J: P&L (Rp)
                        round(pnl_pct, 2),                          # K: P&L (%)
                        status_baru,                                # L: Status
                        int(hari),                                  # M: Hari
                    ]])

                    closed.append(f"{kode} ({status_baru})")
                    print(f"✅ Tutup posisi: {kode} @ Rp{exit_price:,.0f} - {status_baru}, P&L: Rp{pnl_rp:,.0f}")
                else:
                    print(f"❌ Tidak menemukan baris {kode} dengan status OPEN di sheet")
            elif not sudah_breakeven and sl_awal is not None and sl_awal < harga_beli:
                # TRAILING STOP: belum exit hari ini, SL belum pernah ditrail, dan risk
                # awal (Harga Beli - SL Awal) valid (positif) - cek apakah High hari ini
                # sudah mencapai profit target TRAILING_TRIGGER_R x risk awal. Kalau iya,
                # naikkan SL ke breakeven (Harga Beli) SEKALI - dibacktest (README >
                # "Trailing Stop ke Breakeven"): avg net return naik +0.62% -> +0.78%,
                # konsisten di 2 periode. TIDAK menutup posisi hari ini, cuma menaikkan SL
                # utk pengecekan berikutnya.
                risk_awal = harga_beli - sl_awal
                trigger_price = harga_beli + TRAILING_TRIGGER_R * risk_awal
                if today_high >= trigger_price:
                    sheet_row = _find_row_number(ws, kode, "OPEN")
                    if sheet_row:
                        ws.update(f"E{sheet_row}", [[harga_beli]])
                        any_trailed = True
                        print(f"📈 {kode}: SL ditrail ke breakeven Rp{harga_beli:,.0f} (profit >= {TRAILING_TRIGGER_R:.0f}R tercapai)")

        except Exception as e:
            print(f"❌ Error proses posisi {row.get('Saham', 'UNKNOWN')}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Clear cache karena data berubah - baik posisi ditutup MAUPUN cuma SL ditrail
    # (posisi tetap OPEN tapi kolom E-nya berubah di sheet).
    if closed or any_trailed:
        load_positions.clear()

    return closed


def summarize(df: pd.DataFrame) -> dict:
    """Hitung ringkasan statistik dari semua posisi."""
    if df.empty:
        return {
            "total": 0,
            "open": 0,
            "win": 0,
            "loss": 0,
            "breakeven": 0,
            "winrate": 0.0,
            "total_pnl_pct": 0.0
        }

    total = len(df)
    open_n = int((df["Status"] == "OPEN").sum()) if "Status" in df.columns else 0

    # Hitung WIN dan LOSS (handle berbagai format status)
    # Bug nyata dari laporan user: posisi yang FORCE SELL (bukan kena TP/SL) dulu TIDAK
    # dihitung sbg WIN maupun LOSS sama sekali - cuma dicek substring "WIN"/"LOSS" pd
    # Status, dan Status utk force-sell isinya "FORCE SELL (N hari)" (tidak mengandung
    # kata WIN/LOSS). Akibatnya kotak WIN/LOSS/Win Rate tetap 0 walau ada force-sell yang
    # untung besar (mis. P&L +701%). Fix: force-sell diklasifikasi WIN/LOSS dari TANDA
    # P&L (%) aktualnya (untung/rugi tetap tercatat, cuma exit reason-nya beda dari TP/SL).
    #
    # Bug nyata LANJUTAN dari laporan user (tab Performance): "Win Rate 2,1%" (1 WIN, 47
    # LOSS) - ternyata dari 48 closed, cuma 28 BENAR kena SL, 19 SISANYA "BREAKEVEN" (SL
    # berhasil ditrail ke breakeven, P&L cuma -0,4% krn fee) - versi lama menganggap
    # BREAKEVEN SAMA PERSIS dgn LOSS (P&L<=0 -> loss_mask), padahal itu trailing-stop
    # BEKERJA BENAR melindungi modal, bukan kegagalan spt SL penuh (-3% s.d -10%). Fix:
    # BREAKEVEN dipisah jadi kategori TERSENDIRI (bukan menang ATAU kalah), Win Rate dihitung
    # dari WIN vs LOSS asli saja (BREAKEVEN tidak masuk keduanya).
    win = 0
    loss = 0
    breakeven = 0
    if "Status" in df.columns:
        status_str = df["Status"].astype(str)
        is_force_sell = status_str.str.contains("FORCE SELL", case=False, na=False)
        is_breakeven = status_str.str.contains("BREAKEVEN", case=False, na=False)
        pnl_num = pd.to_numeric(df["P&L (%)"], errors="coerce") if "P&L (%)" in df.columns else pd.Series([float("nan")] * len(df), index=df.index)
        win_mask = status_str.str.contains("WIN", case=False, na=False) | (is_force_sell & (pnl_num > 0))
        loss_mask = status_str.str.contains("LOSS", case=False, na=False) | (is_force_sell & (pnl_num <= 0))
        win = int((win_mask & ~is_breakeven).sum())
        loss = int((loss_mask & ~is_breakeven).sum())
        breakeven = int(is_breakeven.sum())

    closed_n = win + loss
    winrate = (win / closed_n * 100) if closed_n > 0 else 0.0
    
    # Total P&L persen
    total_pnl_pct = 0.0
    if "P&L (%)" in df.columns:
        total_pnl_pct = pd.to_numeric(df["P&L (%)"], errors="coerce").sum()
        if pd.isna(total_pnl_pct):
            total_pnl_pct = 0.0
    
    return {
        "total": total,
        "open": open_n,
        "win": win,
        "loss": loss,
        "breakeven": breakeven,
        "winrate": winrate,
        "total_pnl_pct": total_pnl_pct
    }


def monthly_performance(df: pd.DataFrame) -> dict:
    """Hitung performa bulanan dari transaksi yang SUDAH CLOSE di sheet POSISI.
    
    Profit per bulan = jumlah P&L(%) semua transaksi yang closed di bulan itu 
    (penjumlahan sederhana ala signal-provider, BUKAN compounding return riil).
    """
    empty = {
        "monthly": pd.DataFrame(columns=["Bulan", "Profit %"]), 
        "cumulative_pct": 0.0,
        "avg_per_month": 0.0, 
        "top_trades": pd.DataFrame(), 
        "n_closed": 0
    }
    
    if df.empty or "Status" not in df.columns:
        return empty

    # Filter hanya yang sudah close (WIN, LOSS, atau FORCE SELL)
    closed = df[df["Status"].astype(str).str.match(r"^(WIN|LOSS|FORCE SELL)", case=False, na=False)].copy()
    
    if closed.empty:
        return empty

    # Parse tanggal close dan P&L
    closed["Tanggal Close_dt"] = pd.to_datetime(closed["Tanggal Close"], errors="coerce")
    closed["P&L (%)_num"] = pd.to_numeric(closed["P&L (%)"], errors="coerce")
    
    # Drop baris yang tanggal atau P&L-nya invalid
    closed = closed.dropna(subset=["Tanggal Close_dt", "P&L (%)_num"])
    
    if closed.empty:
        return empty

    # Group by bulan
    closed["Bulan"] = closed["Tanggal Close_dt"].dt.strftime("%Y-%m")
    monthly = closed.groupby("Bulan")["P&L (%)_num"].sum().reset_index()
    monthly.columns = ["Bulan", "Profit %"]
    monthly = monthly.sort_values("Bulan")

    # Hitung statistik
    cumulative_pct = float(monthly["Profit %"].sum())
    avg_per_month = float(monthly["Profit %"].mean()) if len(monthly) else 0.0

    # Top 10 trades terbaik
    top_trades = closed.sort_values("P&L (%)_num", ascending=False)[
        ["Saham", "Tipe", "Tanggal Close", "P&L (%)_num", "Status"]
    ].rename(columns={"P&L (%)_num": "Profit %"}).head(10)

    return {
        "monthly": monthly, 
        "cumulative_pct": cumulative_pct,
        "avg_per_month": avg_per_month, 
        "top_trades": top_trades, 
        "n_closed": len(closed)
    }
