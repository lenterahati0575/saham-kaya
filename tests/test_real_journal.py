"""
Unit test untuk real_journal.py - fokus ke fungsi murni (tidak butuh koneksi Google Sheets):
_calculate_trade_result, open_positions_risk, portfolio_risk_summary.

Kasus baku di test_calculate_trade_result_kasus_baku() adalah kasus yang SAMA PERSIS dengan
yang dipakai tombol "Tes Formula" manual di dalam UI dashboard (tab Jurnal Real > Sekuritas) -
sekarang ada versi otomatisnya di sini juga supaya regresi ketahuan dari CI, bukan cuma
kalau Bro kebetulan buka tab itu dan klik expander-nya.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import real_journal as rj
from real_journal import _calculate_trade_result, open_positions_risk, portfolio_risk_summary


class TestCalculateTradeResult:
    def test_kasus_baku_profit(self):
        """Entry 458, Exit 494, Lot 10, fee 0.15%/0.25% -> harus PROFIT +Rp34.078 (+7.44%)."""
        r = _calculate_trade_result(458, 494, 10, 0.15, 0.25)
        assert r["biaya"] == pytest.approx(1922, abs=1)
        assert r["net_pl"] == pytest.approx(34078, abs=1)
        assert r["return_pct"] == pytest.approx(7.44, abs=0.01)
        assert r["status"] == "PROFIT"

    def test_loss(self):
        r = _calculate_trade_result(1000, 900, 10, 0.15, 0.25)
        assert r["status"] == "LOSS"
        assert r["net_pl"] < 0

    def test_breakeven_persis(self):
        # entry = exit, tapi tetap kena biaya beli+jual -> hasil sebenarnya LOSS tipis, bukan
        # BREAKEVEN - ini menegaskan biaya transaksi tidak boleh diabaikan.
        r = _calculate_trade_result(1000, 1000, 10, 0.15, 0.25)
        assert r["net_pl"] < 0
        assert r["status"] == "LOSS"


class TestPortfolioRisk:
    def _trades(self):
        return pd.DataFrame([
            {"No": 1, "Saham": "AAA", "Sekuritas": "Broker1", "Entry (Rp)": 1000,
             "Stop Loss (Rp)": 950, "Lot": 10, "Status": "OPEN"},
            {"No": 2, "Saham": "BBB", "Sekuritas": "Broker1", "Entry (Rp)": 2000,
             "Stop Loss (Rp)": 1900, "Lot": 5, "Status": "OPEN"},
            {"No": 3, "Saham": "CCC", "Sekuritas": "Broker1", "Entry (Rp)": 500,
             "Stop Loss (Rp)": 0, "Lot": 20, "Status": "OPEN"},  # SL belum diisi
            {"No": 4, "Saham": "DDD", "Sekuritas": "Broker1", "Entry (Rp)": 1000,
             "Stop Loss (Rp)": 900, "Lot": 10, "Status": "PROFIT"},  # sudah closed
        ])

    def test_open_positions_risk_hanya_hitung_yang_open(self):
        detail = open_positions_risk(self._trades())
        assert set(detail["Saham"]) == {"AAA", "BBB", "CCC"}  # DDD (closed) tidak ikut

    def test_risiko_dihitung_benar(self):
        detail = open_positions_risk(self._trades())
        risiko_aaa = detail.loc[detail["Saham"] == "AAA", "Risiko (Rp)"].iloc[0]
        # (1000-950) * 10 lot * 100 lembar = 50 * 1000 = 50.000
        assert risiko_aaa == pytest.approx(50_000)

    def test_sl_kosong_ditandai_bukan_dianggap_nol_risiko_diam_diam(self):
        detail = open_positions_risk(self._trades())
        row_ccc = detail[detail["Saham"] == "CCC"].iloc[0]
        assert row_ccc["SL Belum Diisi"] is True or row_ccc["SL Belum Diisi"] == True  # noqa: E712
        assert row_ccc["Risiko (Rp)"] == 0

    def test_portfolio_risk_summary_persen_dari_equity(self):
        summary = portfolio_risk_summary(self._trades(), total_equity=1_000_000)
        # AAA 50.000 + BBB (2000-1900)*5*100=50.000 + CCC 0 (SL kosong) = 100.000
        assert summary["total_risk_rp"] == pytest.approx(100_000)
        assert summary["pct_of_equity"] == pytest.approx(10.0)
        assert summary["n_sl_kosong"] == 1
        assert summary["n_open"] == 3

    def test_tanpa_total_equity_pct_none(self):
        summary = portfolio_risk_summary(self._trades(), total_equity=None)
        assert summary["pct_of_equity"] is None

    def test_trades_kosong(self):
        empty = pd.DataFrame(columns=["No", "Saham", "Sekuritas", "Entry (Rp)",
                                       "Stop Loss (Rp)", "Lot", "Status"])
        summary = portfolio_risk_summary(empty, total_equity=1_000_000)
        assert summary["total_risk_rp"] == 0
        assert summary["n_open"] == 0


class TestOpenTradeNumbering:
    """Bug nyata: open_trade() dulu pakai No=len(existing)+1 (jumlah baris, bukan No
    tertinggi). Kalau ada trade yang pernah DIHAPUS (delete_trade() betul2 delete_rows di
    sheet), No baru bisa COLLIDE dgn No yang masih ada -> close_trade()/edit_trade() yang
    cari baris via `trades["No"]==no` match 2 baris & diam2 selalu ambil yang pertama -
    salah trade yang ke-edit/ketutup tanpa pesan error apa pun."""

    def _existing(self, rows):
        return pd.DataFrame(rows, columns=rj.TRADES_HEADERS)

    def test_sheet_kosong_no_mulai_dari_1(self):
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=self._existing([])):
            no = rj.open_trade("2026-08-06", "Broker1", "AAAA", "Swing", 100, 90, 120, 10)
        assert no == 1

    def test_normal_tanpa_penghapusan_no_lanjut_dari_jumlah_baris(self):
        existing = self._existing([
            [1, "2026-08-01", "Broker1", "AAAA", "Swing", 100, 90, 120, 10,
             "", "", "", "", "", "OPEN", ""],
            [2, "2026-08-02", "Broker1", "BBBB", "Swing", 200, 180, 240, 10,
             "", "", "", "", "", "OPEN", ""],
        ])
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            no = rj.open_trade("2026-08-06", "Broker1", "CCCC", "Swing", 300, 270, 360, 10)
        assert no == 3

    def test_setelah_hapus_trade_tengah_no_baru_tidak_collide(self):
        # No 1 dan 3 masih ada (No 2 sudah dihapus via delete_trade()) - cuma 2 baris tersisa.
        # No baru HARUS 4 (max+1), BUKAN 3 (len+1) - kalau 3, akan collide dgn No 3 yang ada.
        existing = self._existing([
            [1, "2026-08-01", "Broker1", "AAAA", "Swing", 100, 90, 120, 10,
             "", "", "", "", "", "OPEN", ""],
            [3, "2026-08-03", "Broker1", "CCCC", "Swing", 300, 270, 360, 10,
             "", "", "", "", "", "OPEN", ""],
        ])
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            no = rj.open_trade("2026-08-06", "Broker1", "DDDD", "Swing", 400, 360, 480, 10)
        assert no == 4
        assert no != len(existing) + 1  # jaminan eksplisit: BUKAN lagi len+1


class TestFindTradeRowDuplicateNo:
    """Bug nyata dari laporan user: coba tutup posisi BWPT (target 96) di harga 91 lewat
    'Jurnal Real' - TIDAK ada error, TAPI datanya tidak berubah (Status tetap OPEN). Root
    cause: close_trade()/delete_trade()/edit_trade() dulu cuma `.iloc[0]` dari hasil filter
    "No"==no TANPA cek duplikat - kalau ada 2 baris dgn "No" sama (sisa dari bug lama
    SEBELUM open_trade() diperbaiki ke `No = MAX(No)+1`, lihat TestOpenTradeNumbering di
    atas - baris yg KADUNG duplikat sebelum fix itu tidak otomatis dibersihkan), update
    diam2 kena baris PERTAMA yang cocok, bukan yang dimaksud. Fix: _find_trade_row() sekarang
    menolak tegas kalau ambigu (>1 match), dan utk close_trade() secara khusus mencoba
    disambiguasi dulu lewat Status=="OPEN" (krn menutup posisi ITU SENDIRI menyiratkan
    "yang masih OPEN")."""

    def _row(self, no, saham, status, entry=100, sekuritas="Broker1"):
        return [no, "2026-08-01", sekuritas, saham, "Swing", entry, 90, 120, 10,
                "" if status == "OPEN" else "2026-08-05",
                "" if status == "OPEN" else 105,
                "" if status == "OPEN" else 5, "" if status == "OPEN" else 500,
                "" if status == "OPEN" else 5.0, status, ""]

    def _existing(self, rows):
        return pd.DataFrame(rows, columns=rj.TRADES_HEADERS)

    def test_close_trade_duplikat_no_disambiguasi_lewat_status_open_berhasil(self):
        # No=5 dobel: satu sudah CLOSED lama (AAAA), satu masih OPEN (BWPT) - close_trade()
        # harus kena baris BWPT (baris ke-3, sheet_row=4), BUKAN baris AAAA (sheet_row=2).
        existing = self._existing([
            self._row(5, "AAAA", "PROFIT"),
            self._row(1, "ZZZZ", "OPEN"),
            self._row(5, "BWPT", "OPEN", entry=88),
        ])
        ws = MagicMock()
        updated = {}
        ws.update.side_effect = lambda rng, vals, **kw: updated.update({"range": rng, "vals": vals})
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing), \
             patch.object(rj, "load_brokers", return_value=pd.DataFrame(
                 [["Broker1", 0.15, 0.25]], columns=rj.BROKER_HEADERS)):
            ok, msg = rj.close_trade(5, "2026-08-10", 91)
        assert ok is True, msg
        assert updated["range"] == "J4:O4"  # baris ke-3 (index 2) + 2 = BWPT, bukan AAAA (J2:O2)

    def test_close_trade_duplikat_no_sama_sama_open_ditolak_bukan_salah_sasaran(self):
        # Kalau KEDUANYA masih OPEN, tidak bisa disambiguasi lewat status - HARUS ditolak
        # tegas (drpd diam2 pilih salah satu).
        existing = self._existing([
            self._row(5, "AAAA", "OPEN"),
            self._row(5, "BWPT", "OPEN", entry=88),
        ])
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing), \
             patch.object(rj, "load_brokers", return_value=pd.DataFrame(
                 [["Broker1", 0.15, 0.25]], columns=rj.BROKER_HEADERS)):
            ok, msg = rj.close_trade(5, "2026-08-10", 91)
        assert ok is False
        assert "duplikat" in msg.lower() or "ditemukan" in msg.lower()
        ws.update.assert_not_called()

    def test_delete_trade_duplikat_no_ditolak(self):
        existing = self._existing([
            self._row(5, "AAAA", "PROFIT"),
            self._row(5, "BWPT", "OPEN", entry=88),
        ])
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.delete_trade(5)
        assert ok is False
        ws.delete_rows.assert_not_called()

    def test_edit_trade_duplikat_no_ditolak(self):
        existing = self._existing([
            self._row(5, "AAAA", "PROFIT"),
            self._row(5, "BWPT", "OPEN", entry=88),
        ])
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.edit_trade(5, "2026-08-01", "Broker1", "BWPT", "Swing", 88, 80, 96, 10, "")
        assert ok is False
        ws.update.assert_not_called()

    def test_close_trade_tanpa_duplikat_tetap_normal(self):
        existing = self._existing([
            self._row(1, "ZZZZ", "OPEN"),
            self._row(2, "BWPT", "OPEN", entry=88),
        ])
        ws = MagicMock()
        updated = {}
        ws.update.side_effect = lambda rng, vals, **kw: updated.update({"range": rng, "vals": vals})
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing), \
             patch.object(rj, "load_brokers", return_value=pd.DataFrame(
                 [["Broker1", 0.15, 0.25]], columns=rj.BROKER_HEADERS)):
            ok, msg = rj.close_trade(2, "2026-08-10", 91)
        assert ok is True, msg
        assert updated["range"] == "J3:O3"  # baris ke-2 (index 1) + 2 = BWPT
        assert updated["vals"][0][1] == 91  # Exit (Rp) tercatat 91, bukan diblokir


class TestCloseEditDeleteAtRow:
    """Bug nyata lanjutan dari laporan user: setelah _find_trade_row() menolak "No" duplikat
    dgn error yang jelas, user lapor "BWPT tidak muncul" di dropdown 'Pilih nomor trade' (tab
    Edit/Hapus & Tutup Posisi, app.py). Root cause: dropdown itu pakai KOLOM "No" sbg VALUE
    selectbox - kalau "No" kembar (BWPT & DOOH sama2 No=9), Streamlit tidak bisa membedakan
    2 pilihan dgn value identik, jadi salah satu (BWPT) efektif "hilang"/tidak bisa dipilih
    terpisah dari yang lain. Fix: dropdown diganti pakai INDEX BARIS DataFrame (dijamin unik,
    beda dari "No") sbg value, dipasangkan dgn fungsi baru close_trade_at_row()/
    delete_trade_at_row()/edit_trade_at_row() yang menargetkan baris LANGSUNG lewat index -
    tidak perlu cari-cari ulang lewat "No" sama sekali, jadi aman walau "No" masih kembar."""

    def _existing_dup(self):
        rows = [
            [9, "2026-07-30", "Broker1", "DOOH", "Day Trading", 226, 210, 236, 24,
             "2026-08-11", 91, 1359.6, -325359.6, -59.99, "LOSS", ""],
            [9, "2026-07-31", "Broker1", "BWPT", "Day Trading", 83, 78, 96, 101,
             "", "", "", "", "", "OPEN", ""],
        ]
        return pd.DataFrame(rows, columns=rj.TRADES_HEADERS)

    def test_close_trade_at_row_kena_baris_bwpt_bukan_dooh(self):
        existing = self._existing_dup()
        bwpt_row_index = existing[existing["Saham"] == "BWPT"].index[0]
        ws = MagicMock()
        updated = {}
        ws.update.side_effect = lambda rng, vals, **kw: updated.update({"range": rng, "vals": vals})
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing), \
             patch.object(rj, "load_brokers", return_value=pd.DataFrame(
                 [["Broker1", 0.15, 0.25]], columns=rj.BROKER_HEADERS)):
            ok, msg = rj.close_trade_at_row(bwpt_row_index, "2026-08-14", 91)
        assert ok is True, msg
        assert "BWPT" in msg
        assert updated["range"] == f"J{bwpt_row_index + 2}:O{bwpt_row_index + 2}"
        assert updated["vals"][0][1] == 91

    def test_delete_trade_at_row_kena_baris_bwpt_bukan_dooh(self):
        existing = self._existing_dup()
        bwpt_row_index = existing[existing["Saham"] == "BWPT"].index[0]
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.delete_trade_at_row(bwpt_row_index)
        assert ok is True, msg
        assert "BWPT" in msg
        ws.delete_rows.assert_called_once_with(bwpt_row_index + 2)

    def test_edit_trade_at_row_kena_baris_bwpt_bukan_dooh(self):
        existing = self._existing_dup()
        bwpt_row_index = existing[existing["Saham"] == "BWPT"].index[0]
        ws = MagicMock()
        updated = {}
        ws.update.side_effect = lambda rng, vals, **kw: updated.update({"range": rng, "vals": vals})
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.edit_trade_at_row(bwpt_row_index, 9, "2026-07-31", "Broker1", "BWPT",
                                            "Day Trading", 83, 78, 96, 101, "")
        assert ok is True, msg
        assert updated["range"] == f"A{bwpt_row_index + 2}:P{bwpt_row_index + 2}"
        assert updated["vals"][0][3] == "BWPT"

    def test_row_index_tidak_ada_ditolak_bukan_crash(self):
        existing = self._existing_dup()
        ws = MagicMock()
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.close_trade_at_row(999, "2026-08-14", 91)
        assert ok is False
        ws.update.assert_not_called()


class TestNoNumpyLeakKeSheet:
    """Bug nyata dari laporan user (live app): klik 'Simpan Perubahan' langsung error
    'TypeError: Object of type int64 is not JSON serializable'. Root cause: app.py mengirim
    `row_edit["No"]` (hasil akses langsung ke Series pandas via `.loc[idx]`) sbg parameter
    `no` - itu numpy.int64, BUKAN `int` Python biasa (beda dari kode lama yg pakai
    `.tolist()`, otomatis convert). gspread men-JSON-kan tiap sel sebelum dikirim ke Google
    Sheets API - numpy.int64/float64 tidak bisa di-JSON-kan langsung. Fix: cast eksplisit di
    edit_trade_at_row()/_close_at_sheet_row() SEBELUM ws.update() dipanggil - test ini pakai
    `json.dumps` langsung ke payload yang dikirim utk memverifikasi tidak ada lagi tipe numpy
    yang lolos, bukan cuma cek nilainya benar."""

    def _assert_json_serializable(self, payload):
        import json
        json.dumps(payload)  # akan raise TypeError kalau ada numpy.int64/float64 di dalamnya

    def test_edit_trade_at_row_dgn_no_numpy_int64_tidak_crash(self):
        existing = pd.DataFrame([
            [9, "2026-07-31", "Broker1", "BWPT", "Day Trading", 83, 78, 96, 101,
             "", "", "", "", "", "OPEN", ""],
        ], columns=rj.TRADES_HEADERS)
        no_numpy = existing.loc[0, "No"]  # numpy.int64, PERSIS spt row_edit["No"] di app.py
        assert type(no_numpy).__name__ in ("int64", "int32", "int")  # sanity: memang numpy kalau di lingkungan ini
        ws = MagicMock()
        captured = {}
        ws.update.side_effect = lambda rng, vals, **kw: (self._assert_json_serializable(vals), captured.update({"vals": vals}))
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing):
            ok, msg = rj.edit_trade_at_row(0, no_numpy, "2026-07-31", "Broker1", "BWPT",
                                            "Day Trading", 83, 78, 96, 101, "")
        assert ok is True, msg
        assert captured["vals"][0][0] == 9
        assert isinstance(captured["vals"][0][0], int) and not isinstance(captured["vals"][0][0], bool)

    def test_close_trade_at_row_dgn_lot_numpy_tidak_crash(self):
        existing = pd.DataFrame([
            [9, "2026-07-31", "Broker1", "BWPT", "Day Trading", 83, 78, 96, 101,
             "", "", "", "", "", "OPEN", ""],
        ], columns=rj.TRADES_HEADERS)
        ws = MagicMock()
        captured = {}
        ws.update.side_effect = lambda rng, vals, **kw: (self._assert_json_serializable(vals), captured.update({"vals": vals}))
        with patch.object(rj, "_get_trades_ws", return_value=ws), \
             patch.object(rj, "load_trades", return_value=existing), \
             patch.object(rj, "load_brokers", return_value=pd.DataFrame(
                 [["Broker1", 0.15, 0.25]], columns=rj.BROKER_HEADERS)):
            ok, msg = rj.close_trade_at_row(0, "2026-08-14", 91)
        assert ok is True, msg
        self._assert_json_serializable(captured["vals"])


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
