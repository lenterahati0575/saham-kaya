"""
Uji auto_close_positions() - khususnya fix utk bug nyata yang ditemukan dari laporan user:
posisi OPEN pada saham yang TIDAK masuk batch price_lookup (mis. di luar window alfabetis
"Jumlah saham dipindai" default) dulu di-skip via `continue` dan TIDAK PERNAH bisa dicek
TP/SL/force-sell selamanya. Fix-nya: fetch harga tambahan khusus utk saham yang OPEN tapi
tidak ada di price_lookup, sebelum loop pengecekan.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gsheet_journal as gj


def _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=110.0, sl=90.0, tipe="SWING", lot=10,
                          tanggal_open="2026-07-20 10:00"):
    return pd.DataFrame([{
        "Tanggal Open": tanggal_open, "Saham": kode, "Harga Beli": harga_beli, "TP": tp,
        "SL": sl, "Tipe": tipe, "Lot": lot, "Tanggal Close": "", "Harga Jual": "",
        "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN", "Hari": "",
    }])


def _mock_worksheet():
    ws = MagicMock()
    ws.get_all_values.return_value = [
        ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Tipe", "Lot", "Tanggal Close",
         "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "Hari"],
        ["2026-07-20 10:00", "ZZZZ", "100", "110", "90", "SWING", "10", "", "", "", "", "OPEN", ""],
    ]
    return ws


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
