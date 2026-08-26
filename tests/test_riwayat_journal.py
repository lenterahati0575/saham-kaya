"""
Uji riwayat_journal.py - log snapshot harian saham Signal BUY/STRONG BUY ke 1 sheet Google
Sheets ("RIWAYAT_SAHAM"), TERUS DITAMBAH (append), tidak pernah ditimpa. Latar belakang:
user mau performa tiap saham bisa dilihat dari waktu ke waktu di SATU tempat, tanpa perlu
download CSV berulang kali (tiap download bikin file terpisah, tidak bisa dibandingkan).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import riwayat_journal as rj


def _table(rows):
    return pd.DataFrame(rows)


def _mock_ws(existing_values=None):
    ws = MagicMock()
    ws.get_all_values.return_value = existing_values or [rj.HEADERS]
    return ws


class TestAppendDailySnapshot:
    def test_hanya_signal_buy_ke_atas_yang_disimpan(self):
        table = _table([
            {"Kode": "AAAA", "Nama": "A Corp", "Harga": 100.0, "Perubahan %": "+1,00%",
             "Signal": "STRONG BUY", "Score": 8.0, "Volume Ratio": 1.5, "Value Traded (Rp)": 5e9},
            {"Kode": "BBBB", "Nama": "B Corp", "Harga": 200.0, "Perubahan %": "-1,00%",
             "Signal": "BUY", "Score": 6.0, "Volume Ratio": 1.2, "Value Traded (Rp)": 4e9},
            {"Kode": "CCCC", "Nama": "C Corp", "Harga": 50.0, "Perubahan %": "0,00%",
             "Signal": "HOLD", "Score": 0.0, "Volume Ratio": 1.0, "Value Traded (Rp)": 3e9},
            {"Kode": "DDDD", "Nama": "D Corp", "Harga": 75.0, "Perubahan %": "-3,00%",
             "Signal": "SELL", "Score": -3.0, "Volume Ratio": 0.8, "Value Traded (Rp)": 3e9},
        ])
        ws = _mock_ws()
        with patch.object(rj, "_get_worksheet", return_value=ws), \
             patch.object(rj, "load_riwayat"):
            n = rj.append_daily_snapshot(table)
        assert n == 2
        appended = ws.append_rows.call_args[0][0]
        kodes = [row[1] for row in appended]
        assert kodes == ["AAAA", "BBBB"]

    def test_skip_kalau_snapshot_hari_ini_sudah_ada(self):
        today_str = datetime.now(rj.WIB).strftime("%Y-%m-%d")
        existing = [rj.HEADERS, [today_str, "ZZZZ", "Z Corp", "100", "+1%", "BUY", "5", "1", "1000000000"]]
        table = _table([
            {"Kode": "AAAA", "Nama": "A Corp", "Harga": 100.0, "Perubahan %": "+1,00%",
             "Signal": "STRONG BUY", "Score": 8.0, "Volume Ratio": 1.5, "Value Traded (Rp)": 5e9},
        ])
        ws = _mock_ws(existing)
        with patch.object(rj, "_get_worksheet", return_value=ws):
            n = rj.append_daily_snapshot(table)
        assert n == 0
        ws.append_rows.assert_not_called()

    def test_tidak_skip_kalau_snapshot_terakhir_beda_tanggal(self):
        kemarin = (datetime.now(rj.WIB) - timedelta(days=1)).strftime("%Y-%m-%d")
        existing = [rj.HEADERS, [kemarin, "ZZZZ", "Z Corp", "100", "+1%", "BUY", "5", "1", "1000000000"]]
        table = _table([
            {"Kode": "AAAA", "Nama": "A Corp", "Harga": 100.0, "Perubahan %": "+1,00%",
             "Signal": "STRONG BUY", "Score": 8.0, "Volume Ratio": 1.5, "Value Traded (Rp)": 5e9},
        ])
        ws = _mock_ws(existing)
        with patch.object(rj, "_get_worksheet", return_value=ws), \
             patch.object(rj, "load_riwayat"):
            n = rj.append_daily_snapshot(table)
        assert n == 1
        ws.append_rows.assert_called_once()

    def test_tabel_kosong_tidak_crash(self):
        ws = _mock_ws()
        with patch.object(rj, "_get_worksheet", return_value=ws):
            n = rj.append_daily_snapshot(pd.DataFrame())
        assert n == 0
        ws.get_all_values.assert_not_called()  # gate awal (table kosong) sebelum sempat akses sheet

    def test_tidak_ada_yang_lolos_filter_tidak_append(self):
        table = _table([
            {"Kode": "CCCC", "Nama": "C Corp", "Harga": 50.0, "Perubahan %": "0,00%",
             "Signal": "HOLD", "Score": 0.0, "Volume Ratio": 1.0, "Value Traded (Rp)": 3e9},
        ])
        ws = _mock_ws()
        with patch.object(rj, "_get_worksheet", return_value=ws):
            n = rj.append_daily_snapshot(table)
        assert n == 0
        ws.append_rows.assert_not_called()


class TestGetWorksheetAutoCreate:
    def test_auto_create_kalau_belum_ada(self):
        import gspread
        client = MagicMock()
        sh = MagicMock()
        new_ws = MagicMock()
        sh.worksheet.side_effect = gspread.WorksheetNotFound("RIWAYAT_SAHAM")
        sh.add_worksheet.return_value = new_ws
        client.open_by_key.return_value = sh
        with patch.object(rj, "_get_client", return_value=client), \
             patch.object(rj.st, "secrets", {"GOOGLE_SHEET_ID": "fake_id"}):
            ws = rj._get_worksheet()
        sh.add_worksheet.assert_called_once()
        new_ws.append_row.assert_called_once_with(rj.HEADERS, value_input_option="USER_ENTERED")
        assert ws is new_ws

    def test_pakai_worksheet_yang_sudah_ada_tanpa_create_ulang(self):
        client = MagicMock()
        sh = MagicMock()
        existing_ws = MagicMock()
        sh.worksheet.return_value = existing_ws
        client.open_by_key.return_value = sh
        with patch.object(rj, "_get_client", return_value=client), \
             patch.object(rj.st, "secrets", {"GOOGLE_SHEET_ID": "fake_id"}):
            ws = rj._get_worksheet()
        sh.add_worksheet.assert_not_called()
        assert ws is existing_ws


class TestLoadRiwayat:
    def setup_method(self):
        # @st.cache_data persist antar test dalam 1 proses pytest - HARUS di-clear supaya
        # tiap test benar2 mengeksekusi ulang fungsinya (bukan kena hasil cache test lain,
        # krn load_riwayat() tidak punya parameter apa pun sbg cache key pembeda).
        rj.load_riwayat.clear()

    def test_sheet_kosong_return_dataframe_kosong_dgn_headers(self):
        ws = MagicMock()
        ws.get_all_records.return_value = []
        with patch.object(rj, "_get_worksheet", return_value=ws):
            df = rj.load_riwayat()
        assert df.empty
        assert list(df.columns) == rj.HEADERS

    def test_parse_angka_locale_indonesia(self):
        ws = MagicMock()
        ws.get_all_records.return_value = [
            {"Tanggal": "2026-08-20", "Kode": "AAAA", "Nama": "A Corp", "Harga": "1.234",
             "Perubahan %": "1,50%", "Signal": "BUY", "Score": "5,5", "Volume Ratio": "1,2",
             "Value Traded (Rp)": "5.000.000.000"},
        ]
        with patch.object(rj, "_get_worksheet", return_value=ws):
            df = rj.load_riwayat()
        assert df.loc[0, "Harga"] == 1234.0
        assert df.loc[0, "Score"] == 5.5

    def test_error_tidak_crash_return_dataframe_kosong(self):
        with patch.object(rj, "_get_worksheet", side_effect=Exception("network error")):
            df = rj.load_riwayat()
        assert df.empty
        assert list(df.columns) == rj.HEADERS


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
