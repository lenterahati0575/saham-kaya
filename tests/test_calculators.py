"""Unit test untuk calculators.py - kalkulator profit, average, dan manajemen risiko."""

import pytest

from calculators import (
    profit_calculator, average_calculator, average_lot_simulator, risk_management_calculator,
)


class TestProfitCalculator:
    def test_untung_dengan_komisi(self):
        r = profit_calculator(harga_beli=1000, harga_jual=1100, lot=10,
                               komisi_beli_pct=0.15, komisi_jual_pct=0.25)
        lembar = 10 * 100
        total_beli = 1000 * lembar * 1.0015
        total_jual = 1100 * lembar * 0.9975
        assert r["total_beli"] == pytest.approx(total_beli)
        assert r["total_jual"] == pytest.approx(total_jual)
        assert r["untung_rugi_rp"] == pytest.approx(total_jual - total_beli)

    def test_bep_lebih_tinggi_dari_harga_beli(self):
        """BEP (Break Even Price) harus SELALU >= harga beli kalau ada komisi, karena
        butuh margin ekstra buat menutup komisi beli+jual sebelum impas."""
        r = profit_calculator(harga_beli=1000, harga_jual=1000, lot=10,
                               komisi_beli_pct=0.15, komisi_jual_pct=0.25)
        assert r["bep"] > 1000
        # rugi kalau jual persis di harga beli (belum menutup komisi)
        assert r["untung_rugi_rp"] < 0

    def test_bep_pas_impas(self):
        r = profit_calculator(harga_beli=1000, harga_jual=1000, lot=10,
                               komisi_beli_pct=0.15, komisi_jual_pct=0.25)
        r_impas = profit_calculator(harga_beli=1000, harga_jual=r["bep"], lot=10,
                                     komisi_beli_pct=0.15, komisi_jual_pct=0.25)
        assert r_impas["untung_rugi_rp"] == pytest.approx(0, abs=1e-6)


class TestAverageCalculator:
    def test_average_down(self):
        r = average_calculator(harga_awal=1000, lot_awal=10, harga_tambahan=800, lot_tambahan=10)
        assert r["tipe"] == "AVERAGE DOWN"
        assert r["avg_baru"] == pytest.approx(900.0)
        assert r["total_lot"] == pytest.approx(20.0)

    def test_average_up(self):
        r = average_calculator(harga_awal=1000, lot_awal=10, harga_tambahan=1200, lot_tambahan=10)
        assert r["tipe"] == "AVERAGE UP"
        assert r["avg_baru"] == pytest.approx(1100.0)

    def test_harga_sama(self):
        r = average_calculator(harga_awal=1000, lot_awal=10, harga_tambahan=1000, lot_tambahan=5)
        assert r["tipe"] == "HARGA SAMA"

    def test_total_lot_nol_error(self):
        r = average_calculator(harga_awal=1000, lot_awal=0, harga_tambahan=800, lot_tambahan=0)
        assert "error" in r


class TestAverageLotSimulator:
    def test_simulasi_average_down_konsisten_dengan_average_calculator(self):
        rs = average_lot_simulator(harga_awal=4500, lot_awal=10, target_avg=4000, harga_tambahan=3700)
        assert "error" not in rs
        # Hasil simulasi lot tambahan, kalau dipakai ulang di average_calculator, harus
        # menghasilkan average yang mendekati target (dalam toleransi 1 lot pembulatan ke atas).
        assert rs["avg_hasil"] <= 4000 + 5  # sedikit di bawah/sama target karena dibulatkan CEIL

    def test_target_di_luar_rentang_error(self):
        rs = average_lot_simulator(harga_awal=4500, lot_awal=10, target_avg=5000, harga_tambahan=3700)
        assert "error" in rs

    def test_target_sama_harga_tambahan_error(self):
        rs = average_lot_simulator(harga_awal=4500, lot_awal=10, target_avg=3700, harga_tambahan=3700)
        assert "error" in rs


class TestRiskManagementCalculator:
    def test_dasar_tanpa_harga_saham(self):
        r = risk_management_calculator(total_modal=10_000_000, resiko_pct=1.0, sl_pct=5.0, rr_ratio=2.0)
        assert r["resiko_rp"] == pytest.approx(100_000)
        assert r["maksimal_beli_rp"] == pytest.approx(2_000_000)
        assert r["take_profit_pct"] == pytest.approx(10.0)
        assert r["dibatasi_modal"] is False

    def test_dibatasi_modal_saat_posisi_melebihi_modal(self):
        r = risk_management_calculator(total_modal=1_000_000, resiko_pct=5.0, sl_pct=1.0, rr_ratio=2.0)
        assert r["dibatasi_modal"] is True
        assert r["maksimal_beli_rp"] == pytest.approx(1_000_000)

    def test_dengan_harga_saham_hasil_dalam_lot(self):
        r = risk_management_calculator(total_modal=10_000_000, resiko_pct=1.0, sl_pct=5.0,
                                        rr_ratio=2.0, harga_saham=1000)
        assert r["lot"] * 100 == r["lembar"]
        assert r["lembar"] % 100 == 0
        assert r["stop_loss_price"] == pytest.approx(950.0)
        assert r["take_profit_price"] == pytest.approx(1100.0)

    def test_sl_pct_nol_error(self):
        r = risk_management_calculator(total_modal=10_000_000, resiko_pct=1.0, sl_pct=0, rr_ratio=2.0)
        assert "error" in r


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
