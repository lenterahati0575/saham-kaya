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
    TestTrailingStopBreakeven)."""
    return (datetime.now(gj.WIB) - timedelta(days=hari_lalu)).strftime("%Y-%m-%d %H:%M")


def _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0, tipe="SWING", lot=10,
                          tanggal_open="2026-07-20 10:00", sl_awal=None, tanpa_kolom_sl_awal=False):
    row = {
        "Tanggal Open": tanggal_open, "Saham": kode, "Harga Beli": harga_beli, "TP": tp,
        "SL": sl, "Tipe": tipe, "Lot": lot, "Tanggal Close": "", "Harga Jual": "",
        "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN", "Hari": "",
    }
    if not tanpa_kolom_sl_awal:
        # Default SL Awal = sl (posisi belum pernah ditrail) - SAMA dgn perilaku baris
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
        # (Close-only) akan bilang masih HOLD, padahal TP sebenarnya sudah tersentuh.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (115.0, 100.0)})
        assert closed == ["ZZZZ (WIN (TP))"]
        # Exit price dicatat TEPAT di level TP (110), bukan di Close (105) atau High (115).
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 110.0

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
        assert closed == ["ZZZZ (WIN (TP))"]


class TestTrailingStopBreakeven:
    """Trailing stop ke breakeven - dibacktest (615 saham/5 tahun, README > 'Trailing Stop
    ke Breakeven'): avg net return naik +0.62% -> +0.78%, konsisten di 2 periode. Latar
    belakang: user tanya 'apakah sistem yang kita bangun dapat memprediksi reversal
    sebelum TP tercapai... ada uang real' - jawabannya TIDAK bisa memprediksi, tapi
    trailing SL ke breakeven mengunci sebagian untung kalau memang terjadi reversal."""

    def test_trailing_menaikkan_sl_ke_breakeven_saat_profit_1r_tercapai(self):
        # risk awal = 100-90 = 10 -> trigger begitu High >= 100+10 = 110.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0, sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 108.0}, {"ZZZZ": (111.0, 105.0)})
        assert closed == []  # posisi TETAP OPEN, bukan ditutup
        ws.update.assert_called_once_with("E2", [[100.0]])

    def test_trailing_tidak_trigger_kalau_profit_belum_1r(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0, sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (108.0, 103.0)})
        assert closed == []
        ws.update.assert_not_called()

    def test_exit_setelah_ditrail_dilabel_breakeven_bukan_loss(self):
        # SL SUDAH ditrail ke 100 (breakeven) di run sebelumnya - SL Awal tetap 90 (risk asli).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=100.0, sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 99.0}, {"ZZZZ": (105.0, 98.0)})
        assert closed == ["ZZZZ (BREAKEVEN)"]
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 100.0  # exit price = breakeven (100), bukan SL asli (90)

    def test_baris_lama_tanpa_kolom_sl_awal_tidak_crash_dan_tetap_trailing(self):
        # Baris dibuka SEBELUM kolom "SL Awal" ada - fallback ke SL saat ini (yang utk
        # baris belum-pernah-ditrail SAMA dgn SL asli) - TIDAK crash, trailing tetap jalan.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=130.0, sl=90.0,
                                            tanpa_kolom_sl_awal=True, tanggal_open=_tanggal_open_recent())
        ws = _mock_worksheet()
        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws):
            closed = gj.auto_close_positions({"ZZZZ": 108.0}, {"ZZZZ": (111.0, 105.0)})
        assert closed == []
        ws.update.assert_called_once_with("E2", [[100.0]])


class TestAutoClosePositionsMissingTicker:
    """Saham OPEN yang tidak ada di price_lookup (di luar batch scan) harus tetap bisa dicek,
    bukan di-skip selamanya - itu bug nyata yang ditemukan dari laporan user (9 dari 14
    posisi OPEN saat itu di luar window scan default)."""

    def test_saham_diluar_price_lookup_tetap_dicek_via_fetch_tambahan(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()

        fake_price_df = pd.DataFrame({"Close": [115.0]})  # >= TP 110 -> harus WIN (TP)

        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history", return_value={"ZZZZ": fake_price_df}) as mock_fetch:
            closed = gj.auto_close_positions({})  # price_lookup KOSONG - ZZZZ tidak ada di sana

        mock_fetch.assert_called_once()
        called_tickers = mock_fetch.call_args[0][0]
        assert "ZZZZ" in called_tickers
        assert closed == ["ZZZZ (WIN (TP))"]
        ws.update.assert_called_once()

    def test_saham_di_price_lookup_tidak_perlu_fetch_tambahan(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0)
        ws = _mock_worksheet()

        with patch.object(gj, "load_positions", return_value=df_positions), \
             patch.object(gj, "_get_worksheet", return_value=ws), \
             patch("screener.fetch_price_history") as mock_fetch:
            closed = gj.auto_close_positions({"ZZZZ": 115.0})  # sudah ada di price_lookup

        mock_fetch.assert_not_called()
        assert closed == ["ZZZZ (WIN (TP))"]

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
