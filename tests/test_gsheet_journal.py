"""
Uji auto_close_positions() - khususnya fix utk bug nyata yang ditemukan dari laporan user:
posisi OPEN pada saham yang TIDAK masuk batch price_lookup (mis. di luar window alfabetis
"Jumlah saham dipindai" default) dulu di-skip via `continue` dan TIDAK PERNAH bisa dicek
TP/SL/force-sell selamanya. Fix-nya: fetch harga tambahan khusus utk saham yang OPEN tapi
tidak ada di price_lookup, sebelum loop pengecekan.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gsheet_journal as gj


def _tanggal_open_recent(hari_lalu: int = 2) -> str:
    """Tanggal open yang SELALU beberapa hari lalu relatif ke SEKARANG (bukan hardcoded
    string) - cegah test gagal begitu waktu asli berjalan lewat ambang force-sell 15 hari
    (bug nyata yang sudah pernah terjadi sebelumnya di sesi ini - lihat komentar
    TestTargetLock)."""
    return (datetime.now(gj.WIB) - timedelta(days=hari_lalu)).strftime("%Y-%m-%d %H:%M")


def _tanggal_open_hari_ini(jam: str = "09:00") -> str:
    """Tanggal open di TANGGAL KALENDER SEKARANG (hari yang sama dgn saat test jalan) -
    dipakai TestSkipCekSamaHariDenganBuka utk simulasi posisi yang BARU SAJA dibuka."""
    return datetime.now(gj.WIB).strftime(f"%Y-%m-%d {jam}")


def _tanggal_open_kemarin_sore(jam: str = "15:07") -> str:
    """Tanggal open KEMARIN sore (tanggal KALENDER beda dari sekarang, TAPI kalau dicek pagi
    ini selisih JAM-nya < 24 jam) - dipakai utk membuktikan fix pakai perbandingan TANGGAL
    KALENDER (`.date()`), BUKAN selisih jam (`timedelta.days`), yang akan SALAH treat ini
    sbg "hari yang sama" padahal sudah beda tanggal kalender & MEMANG SAH utk dicek."""
    return (datetime.now(gj.WIB) - timedelta(days=1)).strftime(f"%Y-%m-%d {jam}")


def _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0, tipe="SWING", lot=10,
                          tanggal_open="2026-07-20 10:00", sl_awal=None, tanpa_kolom_sl_awal=False):
    row = {
        "Tanggal Open": tanggal_open, "Saham": kode, "Harga Beli": harga_beli, "TP": tp,
        "SL": sl, "Tipe": tipe, "Lot": lot, "Tanggal Close": "", "Harga Jual": "",
        "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN", "Hari": "",
    }
    if not tanpa_kolom_sl_awal:
        # Default SL Awal = sl (posisi belum pernah digeser) - SAMA dgn perilaku baris
        # yang baru dibuka via open_positions_from_candidates().
        row["SL Awal"] = sl_awal if sl_awal is not None else sl
    return pd.DataFrame([row])


def _mock_worksheet():
    ws = MagicMock()
    ws.get_all_values.return_value = [
        ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Tipe", "Lot", "Tanggal Close",
         "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "Hari"],
        ["2026-07-20 10:00", "ZZZZ", "100", "110", "90", "SWING", "10", "", "", "", "", "OPEN", ""],
    ]
    return ws


class TestTimestampPakaiWIB:
    """Bug nyata dari laporan user: "Tanggal Open" tercatat jam 05:26 padahal posisi dibuka
    12:26 WIB sebenarnya - datetime.now() polos di server (UTC) tidak dikonversi ke WIB,
    sama persis kelas bug yang sudah diperbaiki di get_market_session() (app.py) tapi belum
    diterapkan di gsheet_journal.py."""

    def test_wib_adalah_asia_jakarta(self):
        from zoneinfo import ZoneInfo
        assert gj.WIB == ZoneInfo("Asia/Jakarta")

    def test_tanggal_open_ditulis_pakai_jam_wib_bukan_utc(self):
        candidates = pd.DataFrame([{"Saham": "ZZZZ", "Entry": 100.0, "Target": 110.0,
                                     "Stop Loss": 90.0, "RR": 2.0}])
        appended_rows = []
        ws = MagicMock()
        ws.append_row.side_effect = lambda row, **kw: appended_rows.append(row)

        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=pd.DataFrame(columns=gj.HEADERS)):
            gj.open_positions_from_candidates(candidates, "SWING")

        assert len(appended_rows) == 1
        tanggal_open_tertulis = datetime.strptime(appended_rows[0][0], "%Y-%m-%d %H:%M")
        # Bandingkan dgn jam WIB SAAT INI - toleransi beberapa menit (waktu eksekusi test),
        # tapi HARUS dekat dgn WIB, bukan UTC (yg beda 7 jam).
        now_wib = datetime.now(gj.WIB).replace(tzinfo=None)
        assert abs((tanggal_open_tertulis - now_wib).total_seconds()) < 120


class TestReEntryCooldown:
    """Bug nyata dari laporan user (screenshot sheet POSISI): SLIS/ESTI/PTMP masing2 dibuka
    2x DALAM SATU HARI YANG SAMA - kena SL di pagi/siang, lalu re-entry lagi sore krn masih
    lolos sbg kandidat. Guard lama di open_positions_from_candidates() cuma cek "Status ==
    OPEN sekarang", tidak cek "sudah pernah dibuka hari ini" - jadi begitu posisi lama
    ditutup (menang/rugi/breakeven), sistem bebas membeli lagi saham yang sama di hari yang
    sama. Fix: cooldown 1x buka/saham/hari, terlepas dari statusnya."""

    def test_saham_yang_sudah_dibuka_hari_ini_tidak_dibuka_ulang_walau_sudah_closed(self):
        today_wib = datetime.now(gj.WIB).strftime("%Y-%m-%d")
        existing = pd.DataFrame([{
            "Tanggal Open": f"{today_wib} 09:18", "Saham": "SLIS", "Harga Beli": 88.0,
            "TP": 113.0, "SL": 79.0, "Tipe": "SWING", "Lot": 376, "Tanggal Close": f"{today_wib} 09:30",
            "Harga Jual": 79.0, "P&L (Rp)": -351635.2, "P&L (%)": -10.63, "Status": "LOSS (SL)",
            "Hari": 0, "SL Awal": 79.0,
        }])
        candidates = pd.DataFrame([
            {"Saham": "SLIS", "Entry": 79.0, "Target": 100.0, "Stop Loss": 70.0, "RR": 2.0},
            {"Saham": "WWWW", "Entry": 100.0, "Target": 120.0, "Stop Loss": 90.0, "RR": 2.0},
        ])
        appended_rows = []
        ws = MagicMock()
        ws.append_row.side_effect = lambda row, **kw: appended_rows.append(row)

        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=existing):
            opened = gj.open_positions_from_candidates(candidates, "SWING")

        assert opened == ["WWWW"]
        assert len(appended_rows) == 1
        assert appended_rows[0][1] == "WWWW"

    def test_saham_yang_dibuka_kemarin_dan_sudah_closed_boleh_dibuka_lagi_hari_ini(self):
        existing = pd.DataFrame([{
            "Tanggal Open": "2026-07-20 09:18", "Saham": "SLIS", "Harga Beli": 88.0,
            "TP": 113.0, "SL": 79.0, "Tipe": "SWING", "Lot": 376, "Tanggal Close": "2026-07-20 09:30",
            "Harga Jual": 79.0, "P&L (Rp)": -351635.2, "P&L (%)": -10.63, "Status": "LOSS (SL)",
            "Hari": 0, "SL Awal": 79.0,
        }])
        candidates = pd.DataFrame([
            {"Saham": "SLIS", "Entry": 79.0, "Target": 100.0, "Stop Loss": 70.0, "RR": 2.0},
        ])
        appended_rows = []
        ws = MagicMock()
        ws.append_row.side_effect = lambda row, **kw: appended_rows.append(row)

        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=existing):
            opened = gj.open_positions_from_candidates(candidates, "SWING")

        assert opened == ["SLIS"]


class TestMaxPosisiBaruPerHari:
    """Bug nyata dari laporan user: 10 Agustus sistem buka SEMUA top_n=10 kandidat SEKALIGUS
    dlm 1 hari (ARKO/KIJA/HRUM/dst.), lalu IHSG terkoreksi tipis beberapa hari sesudahnya -
    SEMUA posisi kena SL BERBARENGAN krn dibuka berbarengan (risiko terkonsentrasi, bukan
    tersebar). User (modal kecil): "ideal backtest ini diperlakukan seperti saat membeli
    saham [beneran], bedanya ini dilakukan oleh sistem" - trader modal kecil beneran TIDAK
    akan beli 10 saham berbeda dlm 1 hari. Fix: max_new_per_day (default 5) - batas TOTAL
    posisi baru per hari kalender, dihitung ULANG dari sheet tiap panggilan (bukan variabel
    proses) supaya berlaku gabungan lintas cron otomatis & klik manual berkali-kali."""

    def _candidates(self, n):
        return pd.DataFrame([
            {"Saham": f"S{i:03d}", "Entry": 100.0 + i, "Target": 120.0 + i, "Stop Loss": 90.0 + i, "RR": 2.0}
            for i in range(n)
        ])

    def test_sheet_kosong_batas_5_hanya_buka_5_dari_10_kandidat(self):
        ws = MagicMock()
        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=pd.DataFrame(columns=gj.HEADERS)):
            opened = gj.open_positions_from_candidates(self._candidates(10), "SWING", max_new_per_day=5)
        assert len(opened) == 5
        assert opened == ["S000", "S001", "S002", "S003", "S004"]

    def test_sudah_3_dibuka_hari_ini_sisa_slot_cuma_2(self):
        today_wib = datetime.now(gj.WIB).strftime("%Y-%m-%d")
        existing = pd.DataFrame([
            {"Tanggal Open": f"{today_wib} 09:{10+i}", "Saham": f"OLD{i}", "Harga Beli": 100.0,
             "TP": 120.0, "SL": 90.0, "Tipe": "SWING", "Lot": 10, "Tanggal Close": "",
             "Harga Jual": "", "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN", "Hari": "",
             "SL Awal": 90.0}
            for i in range(3)
        ])
        ws = MagicMock()
        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=existing):
            opened = gj.open_positions_from_candidates(self._candidates(10), "SWING", max_new_per_day=5)
        assert len(opened) == 2  # 5 - 3 yg sudah dibuka hari ini = sisa 2 slot

    def test_sudah_penuh_hari_ini_tidak_buka_apa_pun(self):
        today_wib = datetime.now(gj.WIB).strftime("%Y-%m-%d")
        existing = pd.DataFrame([
            {"Tanggal Open": f"{today_wib} 09:{10+i}", "Saham": f"OLD{i}", "Harga Beli": 100.0,
             "TP": 120.0, "SL": 90.0, "Tipe": "SWING", "Lot": 10, "Tanggal Close": "",
             "Harga Jual": "", "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN", "Hari": "",
             "SL Awal": 90.0}
            for i in range(5)
        ])
        ws = MagicMock()
        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=existing):
            opened = gj.open_positions_from_candidates(self._candidates(10), "SWING", max_new_per_day=5)
        assert opened == []
        ws.append_row.assert_not_called()

    def test_default_max_new_per_day_adalah_5(self):
        ws = MagicMock()
        with patch.object(gj, "_get_worksheet", return_value=ws), \
             patch.object(gj, "load_positions", return_value=pd.DataFrame(columns=gj.HEADERS)):
            opened = gj.open_positions_from_candidates(self._candidates(10), "SWING")  # tanpa isi param
        assert len(opened) == 5


class TestEnrichPriceLookup:
    """enrich_price_lookup() dipakai BARENG oleh auto_close_positions() dan tampilan debug
    tabel "Posisi yang dicek" di app.py - dulu dua tempat itu pakai sumber data yang beda
    (satu dilengkapi, satu tidak), bikin debug tabel kelihatan "N/A" padahal logika
    penutupan sebenarnya sudah benar. Sekarang harus konsisten."""

    def test_saham_yang_kurang_di_fetch_dan_ditambahkan(self):
        with patch("screener.fetch_price_history", return_value={"ZZZZ": pd.DataFrame({"Close": [123.0]})}) as mock_fetch:
            result = gj.enrich_price_lookup({"AAAA": 100.0}, ["AAAA", "ZZZZ"])
        mock_fetch.assert_called_once_with(["ZZZZ"], period="5d")
        assert result == {"AAAA": 100.0, "ZZZZ": 123.0}

    def test_tidak_ada_yang_kurang_tidak_fetch(self):
        with patch("screener.fetch_price_history") as mock_fetch:
            result = gj.enrich_price_lookup({"AAAA": 100.0}, ["AAAA"])
        mock_fetch.assert_not_called()
        assert result == {"AAAA": 100.0}

    def test_tidak_mutasi_dict_asli(self):
        original = {"AAAA": 100.0}
        with patch("screener.fetch_price_history", return_value={"ZZZZ": pd.DataFrame({"Close": [123.0]})}):
            gj.enrich_price_lookup(original, ["AAAA", "ZZZZ"])
        assert original == {"AAAA": 100.0}  # dict asli caller tidak boleh berubah


class TestEnrichHlLookup:
    """enrich_hl_lookup() - sibling enrich_price_lookup() tapi utk High/Low, dipakai
    auto_close_positions() supaya TP/SL dicek dari rentang harga hari itu, bukan cuma Close."""

    def test_saham_yang_kurang_di_fetch_dan_ditambahkan(self):
        fake_df = pd.DataFrame({"High": [130.0], "Low": [90.0]})
        with patch("screener.fetch_price_history", return_value={"ZZZZ": fake_df}) as mock_fetch:
            result = gj.enrich_hl_lookup({"AAAA": (110.0, 95.0)}, ["AAAA", "ZZZZ"])
        mock_fetch.assert_called_once_with(["ZZZZ"], period="5d")
        assert result == {"AAAA": (110.0, 95.0), "ZZZZ": (130.0, 90.0)}

    def test_tidak_ada_yang_kurang_tidak_fetch(self):
        with patch("screener.fetch_price_history") as mock_fetch:
            result = gj.enrich_hl_lookup({"AAAA": (110.0, 95.0)}, ["AAAA"])
        mock_fetch.assert_not_called()
        assert result == {"AAAA": (110.0, 95.0)}


class TestAutoClosePositionsHighLow:
    """Bug/gap nyata: dulu TP/SL cuma dicek dari 1 titik harga (Close) - bisa MELEWATKAN
    TP/SL yang sebenarnya tersentuh intraday (High/Low) lalu harga balik lagi sebelum
    sempat dicek. Ini bikin live SISTEMATIS beda dari backtest yang sudah divalidasi
    (backtest selalu cek High>=Target / Low<=SL). hl_lookup menutup gap ini."""

    def test_tp_kesentuh_via_high_walau_close_di_bawah_tp(self):
        # Close=105 (di bawah TP=110), tapi High hari itu=115 (SUDAH lewat TP) - versi lama
        # (Close-only) akan bilang masih HOLD, padahal TP sebenarnya sudah tersentuh. Begitu
        # Target tersentuh, SL digeser (target-lock, lihat TestTargetLock), BUKAN ditutup
        # langsung - risk_awal=100-90=10, SL baru = 110 - 0.5*10 = 105.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (115.0, 100.0)})
        assert closed == []  # posisi TETAP OPEN
        ws.update.assert_called_once_with("E2", [[105.0]])

    def test_sl_kesentuh_via_low_walau_close_di_atas_sl(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 95.0}, {"ZZZZ": (100.0, 85.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 90.0

    def test_sl_dicek_lebih_dulu_kalau_high_low_hari_itu_kena_dua_duanya(self):
        # High=120 (>=TP 110) DAN Low=85 (<=SL 90) di HARI YANG SAMA - asumsi konservatif
        # SAMA seperti backtest.py: anggap SL kena duluan, bukan TP.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (120.0, 85.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_tanpa_hl_lookup_tetap_jalan_seperti_dulu_close_only(self):
        # Backward-compat: caller yang TIDAK kasih hl_lookup sama sekali (mis. kode lama
        # yang belum diupdate) - harus tetap berfungsi persis seperti sebelum fitur ini ada.
        # fetch_price_history di-mock kosong (bukan network call asli) - "ZZZZ" dianggap
        # "hilang" dari hl_lookup kosong, tapi fetch tambahan gagal/kosong -> fallback ke
        # Close-only (perilaku lama), BUKAN error.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history", return_value={}):
            closed = gj.auto_close_positions({"ZZZZ": 115.0})  # tidak kasih hl_lookup
        # Close-only fallback: today_high=today_low=115 -> Target(110) tersentuh -> SL
        # digeser (target-lock), bukan ditutup. risk_awal=10, SL baru=110-0.5*10=105.
        assert closed == []
        ws.update.assert_called_once_with("E2", [[105.0]])


class TestTargetLock:
    """TARGET-LOCK: begitu Target (TP) tersentuh, SL digeser ke Target-k*risk_awal (k=0,5,
    TRAIL_AT_TARGET_K) - posisi TETAP OPEN, dibiarkan jalan lebih lanjut (BUKAN ditutup
    langsung spt sebelumnya). Menggantikan trailing-ke-breakeven yang lama (TERBUKTI
    sistematis memotong untung, bukan cuma menyelamatkan rugi - lihat komentar
    TRAIL_AT_TARGET_K di gsheet_journal.py). DIUJI (614 sinyal, 350 saham/3 tahun,
    walk-forward, dipecah per regime IHSG): avg return naik ~2x lipat di bullish
    (+1,94% -> +3,36%) TANPA mengurangi win rate (tetap 32,7% - mekanisme ini cuma
    menyalakan diri pada trade yang SUDAH menang, jadi strict improvement, bukan
    trade-off). Ide dari praktik manual user: 'kalau target tercapai, geser SL dibawah
    target, supaya kalau harga balik, untung terselamatkan'. README > 'Target-Lock:
    Kunci Untung, Bukan Kunci Rugi'."""

    def test_target_tersentuh_sl_digeser_bukan_exit_langsung(self):
        # risk_awal = 100-90 = 10. TP=130 tersentuh -> SL baru = 130 - 0.5*10 = 125.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 128.0}, {"ZZZZ": (131.0, 126.0)})
        assert closed == []  # TETAP OPEN, tidak ditutup begitu Target tersentuh
        ws.update.assert_called_once_with("E2", [[125.0]])

    def test_setelah_terkunci_exit_di_level_kuncian_dilabel_win(self):
        # SL sudah digeser ke 125 (target-lock, dari test sebelumnya) - SL Awal tetap 90.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=125.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 124.0}, {"ZZZZ": (127.0, 123.0)})
        assert closed == ["ZZZZ (WIN (TARGET TERKUNCI))"]
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 125.0  # exit tepat di level kuncian (125), bukan SL Awal (90)

    def test_setelah_terkunci_tidak_dicek_tp_lagi_tetap_jalan(self):
        # Sudah target-lock (SL=125), harga masih di atas level itu - TETAP OPEN, TIDAK
        # ada pengecekan TP lagi (target sudah "lewat", bukan menunggu level tetap lagi).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=125.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 140.0}, {"ZZZZ": (145.0, 135.0)})
        assert closed == []
        ws.update.assert_not_called()

    def test_force_sell_setelah_terkunci_dilabel_win_bukan_generik(self):
        # Force-sell (15 hari SWING) TAPI sudah target-lock sebelumnya - HARUS dilabel WIN
        # (posisi ini SUDAH PASTI untung, level kuncian selalu > harga beli - lihat
        # pembuktian matematis di komentar TRAIL_AT_TARGET_K), bukan "FORCE SELL" generik.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=125.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent(hari_lalu=16))
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 135.0}, {"ZZZZ": (136.0, 130.0)})
        assert len(closed) == 1
        assert closed[0].startswith("ZZZZ (WIN (FORCE SELL target terkunci")

    def test_belum_capai_target_sl_dan_force_sell_tetap_spt_biasa(self):
        # Belum pernah target-lock (SL == SL Awal) - LOSS (SL) spt sebelumnya, tidak berubah.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 88.0}, {"ZZZZ": (95.0, 85.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_sl_dicek_lebih_dulu_kalau_sama_sekali_belum_terkunci(self):
        # High & Low hari yang sama menyentuh TP dan SL sekaligus, BELUM pernah target-lock
        # - asumsi konservatif SAMA PERSIS spt sebelumnya: SL dicek/menang duluan.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 100.0}, {"ZZZZ": (135.0, 85.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_risk_awal_tidak_valid_fallback_tutup_langsung_di_target(self):
        # SL Awal == Harga Beli (risk_awal=0, data tidak masuk akal/korup) - jangan geser
        # ke level yang tidak valid, fallback tutup langsung di Target spt perilaku lama.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0,
                                            sl_awal=100.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 115.0}, {"ZZZZ": (115.0, 105.0)})
        assert closed == ["ZZZZ (WIN (TP))"]


class TestSkipCekSamaHariDenganBuka:
    """Bug nyata dari laporan user (screenshot sheet POSISI): FAST/CTTH/KETR/DOOH/APLN dkk
    dibuka DAN ditutup di TANGGAL KALENDER YANG SAMA (kadang cuma beda beberapa menit) -
    contoh paling jelas APLN: "kemarin hijau, hari ini naik kencang, tapi tercatat loss".
    Akar masalah: auto_run.py membeli pakai Close ~15:07 WIB (hampir tutup bursa) LALU
    LANGSUNG di eksekusi yang SAMA mengecek SL/TP pakai High/Low HARI ITU JUGA - yang
    SEBAGIAN BESAR sudah terjadi SEBELUM jam beli (dari jam buka 09:00), SECARA KAUSAL
    mustahil di dunia nyata. MENYIMPANG dari backtest.py yang tervalidasi (exit dicek MULAI
    HARI BERIKUTNYA, `range(t + 1, ...)`, tidak pernah hari yang sama dgn entry). Fix: skip
    total pengecekan TP/SL/trailing kalau tanggal KALENDER Tanggal Open == tanggal KALENDER
    sekarang."""

    def test_posisi_dibuka_hari_ini_tidak_dicek_walau_low_tembus_sl(self):
        df_positions = _make_open_position(kode="APLN", harga_beli=137.0, tp=173.0, sl=128.0,
                                            sl_awal=128.0, tanggal_open=_tanggal_open_hari_ini())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            # Low hari ini (120) SUDAH di bawah SL (128) - TANPA fix ini akan langsung
            # "LOSS (SL)", padahal posisi baru saja dibuka hari yang sama.
            closed = gj.auto_close_positions({"APLN": 145.0}, {"APLN": (150.0, 120.0)})
        assert closed == []
        ws.update.assert_not_called()

    def test_posisi_dibuka_hari_ini_tidak_dicek_walau_high_tembus_tp(self):
        # Konsisten juga utk arah UNTUNG - metodologi backtest sama sekali TIDAK mengecek
        # exit di hari entry, terlepas arahnya untung atau rugi.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_hari_ini())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 108.0}, {"ZZZZ": (115.0, 95.0)})
        assert closed == []
        ws.update.assert_not_called()

    def test_posisi_dibuka_kemarin_sore_tetap_dicek_pagi_ini_walau_kurang_24_jam(self):
        # Beda TANGGAL KALENDER (kemarin vs sekarang) walau selisih JAM < 24 jam - HARUS
        # tetap dicek normal (bukan skip) - buktikan fix pakai `.date()`, bukan `.days`.
        # Kode "ZZZZ" (bukan "PWON") - _mock_worksheet() cuma punya baris hardcode "ZZZZ"
        # utk _find_row_number(), sama seperti test lain di file ini.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=260.0, tp=308.0, sl=252.0,
                                            sl_awal=252.0, tanggal_open=_tanggal_open_kemarin_sore())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 245.0}, {"ZZZZ": (265.0, 245.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_posisi_dibuka_beberapa_hari_lalu_tetap_dicek_normal(self):
        # Regresi sanity check - posisi lama (bukan hari ini) TIDAK terpengaruh fix ini
        # (tetap diproses normal - target-lock jalan spt biasa, bukan di-skip).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent(hari_lalu=3))
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 115.0}, {"ZZZZ": (116.0, 105.0)})
        assert closed == []  # Target tersentuh -> SL digeser (target-lock), bukan ditutup
        ws.update.assert_called_once_with("E2", [[105.0]])


class TestAutoClosePositionsMissingTicker:
    """Saham OPEN yang tidak ada di price_lookup (di luar batch scan) harus tetap bisa dicek,
    bukan di-skip selamanya - itu bug nyata yang ditemukan dari laporan user (9 dari 14
    posisi OPEN saat itu di luar window scan default)."""

    def test_saham_diluar_price_lookup_tetap_dicek_via_fetch_tambahan(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()

        # Close=115 >= TP 110 -> Target tersentuh -> SL digeser (target-lock), TETAP OPEN.
        fake_price_df = pd.DataFrame({"Close": [115.0]})

        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history", return_value={"ZZZZ": fake_price_df}) as mock_fetch:
            closed = gj.auto_close_positions({})  # price_lookup KOSONG - ZZZZ tidak ada di sana

        mock_fetch.assert_called_once()
        called_tickers = mock_fetch.call_args[0][0]
        assert "ZZZZ" in called_tickers
        assert closed == []
        ws.update.assert_called_once_with("E2", [[105.0]])  # 110 - 0.5*(100-90) = 105

    def test_saham_di_price_lookup_tidak_perlu_fetch_tambahan(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()

        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history") as mock_fetch:
            closed = gj.auto_close_positions({"ZZZZ": 115.0})  # sudah ada di price_lookup

        mock_fetch.assert_not_called()
        assert closed == []
        ws.update.assert_called_once_with("E2", [[105.0]])

    def test_fetch_tambahan_gagal_tidak_crash_lanjut_dgn_yang_ada(self):
        df_positions = _make_open_position(kode="ZZZZ")
        ws = _mock_worksheet()

        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history", side_effect=Exception("rate-limit")):
            closed = gj.auto_close_positions({})  # fetch tambahan gagal - tidak boleh crash

        assert closed == []  # ZZZZ tetap tidak bisa dicek (harga tidak tersedia), tapi TIDAK crash


def _make_closed_row(status, pnl_pct):
    return {"Saham": "ZZZZ", "Status": status, "P&L (%)": pnl_pct, "P&L (Rp)": pnl_pct * 1000}


class TestSummarizeForceSell:
    """Bug nyata dari laporan user (screenshot kotak ringkasan di tab Kandidat): 3 posisi
    FORCE SELL (2 untung besar - GDST +701%, ANTM +156%, 1 rugi kecil - APLN -4%), tapi
    kotak WIN/LOSS/Win Rate tetap 0/0/0.0% - summarize() dulu cuma cek substring "WIN"/
    "LOSS" pd kolom Status, dan Status force-sell isinya "FORCE SELL (N hari)" (tidak
    mengandung kata WIN/LOSS sama sekali), jadi tidak pernah terhitung ke mana pun."""

    def test_force_sell_untung_dihitung_win(self):
        df = pd.DataFrame([_make_closed_row("FORCE SELL (1 hari)", 701.0)])
        stats = gj.summarize(df)
        assert stats["win"] == 1
        assert stats["loss"] == 0

    def test_force_sell_rugi_dihitung_loss(self):
        df = pd.DataFrame([_make_closed_row("FORCE SELL (1 hari)", -4.0)])
        stats = gj.summarize(df)
        assert stats["win"] == 0
        assert stats["loss"] == 1

    def test_campuran_tp_sl_force_sell_dihitung_benar(self):
        # Reproduksi persis kasus screenshot user: 3 FORCE SELL (2 untung, 1 rugi) + 10 OPEN.
        df = pd.DataFrame([
            _make_closed_row("FORCE SELL (1 hari)", -4.0),    # APLN - rugi -> LOSS
            _make_closed_row("FORCE SELL (1 hari)", 701.0),   # GDST - untung -> WIN
            _make_closed_row("FORCE SELL (1 hari)", 156.0),   # ANTM - untung -> WIN
        ] + [{"Saham": f"OPEN{i}", "Status": "OPEN", "P&L (%)": "", "P&L (Rp)": ""} for i in range(10)])
        stats = gj.summarize(df)
        assert stats["total"] == 13
        assert stats["open"] == 10
        assert stats["win"] == 2
        assert stats["loss"] == 1
        assert round(stats["winrate"], 1) == round(2 / 3 * 100, 1)

    def test_tp_sl_tetap_dihitung_seperti_biasa(self):
        # Status "WIN (TP)"/"LOSS (SL)" harus tetap terhitung walau P&L sign-nya tidak dicek
        # ulang (sudah pasti benar dari cara auto_close_positions menuliskannya).
        df = pd.DataFrame([_make_closed_row("WIN (TP)", 12.0), _make_closed_row("LOSS (SL)", -8.0)])
        stats = gj.summarize(df)
        assert stats["win"] == 1
        assert stats["loss"] == 1

    def test_breakeven_tidak_dihitung_sbg_loss(self):
        # Bug nyata dari laporan user: sheet POSISI asli (48 closed: 1 WIN, 28 LOSS (SL)
        # sungguhan, 19 BREAKEVEN) - Win Rate lama menghitung 1/48=2,1% krn BREAKEVEN
        # (P&L selalu sedikit negatif krn fee) dianggap SAMA dgn LOSS. Reproduksi persis
        # skala kasus itu (disederhanakan: 1 WIN, 2 LOSS asli, 2 BREAKEVEN).
        df = pd.DataFrame([
            _make_closed_row("WIN (TP)", 23.55),
            _make_closed_row("LOSS (SL)", -10.72),
            _make_closed_row("LOSS (SL)", -6.97),
            _make_closed_row("BREAKEVEN", -0.4),
            _make_closed_row("BREAKEVEN", -0.4),
        ])
        stats = gj.summarize(df)
        assert stats["win"] == 1
        assert stats["loss"] == 2  # BUKAN 4 (2 LOSS asli + 2 BREAKEVEN yg salah dihitung)
        assert stats["breakeven"] == 2
        assert round(stats["winrate"], 1) == round(1 / 3 * 100, 1)  # 1/(1+2), BUKAN 1/5


class TestLoadPositionsLocaleParsing:
    """Bug nyata dari laporan user (screenshot tab Performance): P&L GDST tampil
    Rp1.316.832/+701%, padahal sheet aslinya Rp131.683,2/+7,01%. Akar masalah:
    gspread.utils.numericise() (dipakai default oleh ws.get_all_records()) menganggap
    koma = pemisah ribuan gaya Inggris & MENGHAPUSNYA sblm parsing - "131683,2" (locale
    Indonesia, koma=desimal) jadi "1316832". Fix: numericise_ignore=['all'] + parsing
    manual (hapus titik ribuan, ganti koma jadi titik desimal) di load_positions()."""

    def _mock_ws_locale(self, rows: list[dict]):
        headers = gj.HEADERS
        ws = MagicMock()
        ws.get_all_records.return_value = [{h: r.get(h, "") for h in headers} for r in rows]
        return ws

    def test_pnl_koma_desimal_diparsing_benar_bukan_dikali_10(self):
        # Persis kasus GDST di screenshot user.
        ws = self._mock_ws_locale([{
            "Tanggal Open": "2026-08-05 12:30", "Saham": "GDST", "Harga Beli": "108",
            "TP": "149", "SL": "89", "Tipe": "BPJS", "Lot": "174",
            "Tanggal Close": "2026-08-06 12:40", "Harga Jual": "116",
            "P&L (Rp)": "131683,2", "P&L (%)": "7,01", "Status": "FORCE SELL (1 hari)", "Hari": "1",
        }])
        gj.load_positions.clear()
        with patch.object(gj, "_get_worksheet", return_value=ws):
            df = gj.load_positions()
        gj.load_positions.clear()
        assert df.iloc[0]["P&L (Rp)"] == 131683.2
        assert df.iloc[0]["P&L (%)"] == 7.01
        # Regresi eksplisit: bukan 10x/100x lipat gara2 koma dihapus mentah2.
        assert df.iloc[0]["P&L (Rp)"] != 1316832
        assert df.iloc[0]["P&L (%)"] != 701

    def test_pnl_rugi_koma_desimal_tetap_negatif_benar(self):
        # Kasus APLN di screenshot: "-10846,8" / "-0,4" - tanda negatif harus tetap terjaga.
        ws = self._mock_ws_locale([{
            "Tanggal Open": "2026-08-05 12:30", "Saham": "APLN", "Harga Beli": "131",
            "TP": "167", "SL": "115", "Tipe": "BPJS", "Lot": "207",
            "Tanggal Close": "2026-08-06 12:40", "Harga Jual": "131",
            "P&L (Rp)": "-10846,8", "P&L (%)": "-0,4", "Status": "FORCE SELL (1 hari)", "Hari": "1",
        }])
        gj.load_positions.clear()
        with patch.object(gj, "_get_worksheet", return_value=ws):
            df = gj.load_positions()
        gj.load_positions.clear()
        assert df.iloc[0]["P&L (Rp)"] == -10846.8
        assert df.iloc[0]["P&L (%)"] == -0.4

    def test_angka_bulat_tanpa_koma_tidak_terpengaruh(self):
        # Kasus ANTM/PADI: P&L (Rp) kebetulan bulat (tanpa desimal) - harus tetap sama.
        ws = self._mock_ws_locale([{
            "Tanggal Open": "2026-08-05 12:30", "Saham": "ANTM", "Harga Beli": "3060",
            "TP": "3580", "SL": "2800", "Tipe": "BPJS", "Lot": "12",
            "Tanggal Close": "2026-08-06 12:40", "Harga Jual": "3120",
            "P&L (Rp)": "57312", "P&L (%)": "1,56", "Status": "FORCE SELL (1 hari)", "Hari": "1",
        }])
        gj.load_positions.clear()
        with patch.object(gj, "_get_worksheet", return_value=ws):
            df = gj.load_positions()
        gj.load_positions.clear()
        assert df.iloc[0]["P&L (Rp)"] == 57312
        assert df.iloc[0]["P&L (%)"] == 1.56

    def test_baris_open_dgn_kolom_kosong_tidak_crash(self):
        ws = self._mock_ws_locale([{
            "Tanggal Open": "2026-08-05 12:30", "Saham": "KOTA", "Harga Beli": "163",
            "TP": "281", "SL": "89", "Tipe": "SWING", "Lot": "44",
            "Tanggal Close": "", "Harga Jual": "", "P&L (Rp)": "", "P&L (%)": "",
            "Status": "OPEN", "Hari": "",
        }])
        gj.load_positions.clear()
        with patch.object(gj, "_get_worksheet", return_value=ws):
            df = gj.load_positions()
        gj.load_positions.clear()
        assert pd.isna(df.iloc[0]["P&L (Rp)"])
        assert df.iloc[0]["Harga Beli"] == 163
