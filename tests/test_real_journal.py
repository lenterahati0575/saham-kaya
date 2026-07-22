"""
Unit test untuk real_journal.py - fokus ke fungsi murni (tidak butuh koneksi Google Sheets):
_calculate_trade_result, open_positions_risk, portfolio_risk_summary.

Kasus baku di test_calculate_trade_result_kasus_baku() adalah kasus yang SAMA PERSIS dengan
yang dipakai tombol "Tes Formula" manual di dalam UI dashboard (tab Jurnal Real > Sekuritas) -
sekarang ada versi otomatisnya di sini juga supaya regresi ketahuan dari CI, bukan cuma
kalau Bro kebetulan buka tab itu dan klik expander-nya.
"""

import pandas as pd
import pytest

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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
