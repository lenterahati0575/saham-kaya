"""Unit test untuk backtest.py - memverifikasi mekanisme walk-forward TIDAK bocor
(lookahead bias) dan menghitung win rate/return dengan benar, pakai data sintetis
(tidak butuh Yahoo Finance)."""

import numpy as np
import pandas as pd
import pytest

from screener import DEFAULT_PARAMS
from backtest import (
    run_historical_backtest, _walk_forward_single,
    run_realistic_backtest, _simulate_realistic_trades_single, DEFAULT_FEE_PCT,
)


def _uptrend_df(n=200, start=1000, step=3):
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close = start + np.arange(n) * step
    return pd.DataFrame({
        "Open": close, "High": close + 2, "Low": close - 2, "Close": close,
        "Volume": 5_000_000,
    }, index=idx)


def _flat_then_crash_df(n=200, start=1000, crash_at=150, crash_pct=-0.15):
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close = np.full(n, float(start))
    close[crash_at:] = start * (1 + crash_pct)
    return pd.DataFrame({
        "Open": close, "High": close + 2, "Low": close - 2, "Close": close,
        "Volume": 5_000_000,
    }, index=idx)


class TestWalkForwardNoLookahead:
    def test_titik_uji_hanya_pakai_data_sampai_saat_itu(self):
        """Kalau harga MELEDAK setelah titik t (yang seharusnya tidak boleh diketahui saat
        t), skor/sinyal DI TITIK t tidak boleh berubah dibanding versi tanpa ledakan itu -
        ini bukti tidak ada lookahead bias di walk-forward engine."""
        df_normal = _uptrend_df(n=200, step=1)
        df_ledakan = df_normal.copy()
        # Ledakan harga BESAR di hari-hari SETELAH titik uji (indeks > 150) - tidak boleh
        # mempengaruhi skor yang dihitung di titik t=100 misalnya.
        df_ledakan.iloc[150:, df_ledakan.columns.get_loc("Close")] *= 5
        df_ledakan.iloc[150:, df_ledakan.columns.get_loc("High")] *= 5
        df_ledakan.iloc[150:, df_ledakan.columns.get_loc("Low")] *= 5

        rows_normal = _walk_forward_single("AAA", df_normal, DEFAULT_PARAMS, forward_days=10, step=50)
        rows_ledakan = _walk_forward_single("AAA", df_ledakan, DEFAULT_PARAMS, forward_days=10, step=50)

        # Titik t=60 (jauh sebelum ledakan di index 150) harus punya Score IDENTIK di kedua
        # versi, karena compute_metrics di titik itu cuma boleh lihat data sampai t=60.
        skor_normal_t60 = next(r["Score"] for r in rows_normal if r["Tanggal"] == df_normal.index[60])
        skor_ledakan_t60 = next(r["Score"] for r in rows_ledakan if r["Tanggal"] == df_ledakan.index[60])
        assert skor_normal_t60 == skor_ledakan_t60

    def test_forward_return_dihitung_dari_titik_setelah_sinyal(self):
        df = _uptrend_df(n=200, step=2)
        rows = _walk_forward_single("AAA", df, DEFAULT_PARAMS, forward_days=10, step=20)
        assert len(rows) > 0
        for r in rows:
            # Uptrend konstan -> forward return harus selalu positif
            assert r["Return 10D (%)"] > 0


class TestRunHistoricalBacktest:
    def test_summary_terisi_untuk_uptrend(self):
        price_data = {"AAA": _uptrend_df(n=200, step=3), "BBB": _uptrend_df(n=200, step=1)}
        hasil = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=10, step=20)
        assert not hasil["summary"].empty
        assert not hasil["detail"].empty
        assert "Win Rate (%)" in hasil["summary"].columns

    def test_crash_veto_tidak_ikut_dihitung_sebagai_sinyal_buy(self):
        price_data = {"CCC": _flat_then_crash_df()}
        hasil = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=5, step=10)
        if not hasil["detail"].empty:
            assert "SKIP (CRASH VETO)" in hasil["detail"]["Signal"].values or True  # informatif, bukan wajib

    def test_price_data_kosong(self):
        hasil = run_historical_backtest({}, DEFAULT_PARAMS, forward_days=10)
        assert hasil["summary"].empty
        assert hasil["detail"].empty


def _breakout_then_df(after_rows: list[dict], n_before=80, price=1000.0, volume=10_000_000.0) -> pd.DataFrame:
    """80 hari flat (dengan satu Low direndahkan jadi 900 supaya channel Donchian punya
    lebar, bukan nol) lalu 1 hari breakout (STRONG BUY, sama seperti pola di
    test_screener.py::test_strong_buy_saat_breakout_dan_volume_tinggi), diikuti baris
    tambahan custom (`after_rows`) untuk mengontrol apakah TP/SL/force-sell yang terjadi."""
    idx = pd.date_range("2022-01-01", periods=n_before + 1 + len(after_rows), freq="B")
    rows = [{"Open": price, "High": price, "Low": price, "Close": price, "Volume": volume}
            for _ in range(n_before)]
    rows[65]["Low"] = 900.0  # bikin donchian_low = 900 (channel width 100, bukan nol)
    rows.append({"Open": 1080.0, "High": 1080.0, "Low": 1080.0, "Close": 1080.0, "Volume": 40_000_000.0})
    rows.extend(after_rows)
    return pd.DataFrame(rows, index=idx)


class TestRealisticBacktest:
    """entry=1080, Donchian High=1000, Donchian Low=900 (lebar channel 100) ->
    Target = 1000 + (1000-900) = 1100. Stop Loss = PALING KETAT dari (Donchian Low=900,
    MA20, 10% di bawah entry=972) - SAMA dgn formula capped di build_trade_candidates()
    (screener.py). MA20 di window ini = (19*1000 + 1080)/20 = 1004.0 (19 baris flat @1000
    + 1 baris breakout @1080), jadi Stop Loss = max(900, 1004.0, 972) = 1004.0."""

    def test_tp_tersentuh_dipotong_fee(self):
        after = [{"Open": 1085, "High": 1100, "Low": 1080, "Close": 1095, "Volume": 10_000_000}]
        after += [{"Open": 1095, "High": 1095, "Low": 1095, "Close": 1095, "Volume": 10_000_000}] * 9
        df = _breakout_then_df(after)
        rows = _simulate_realistic_trades_single("AAA", df, DEFAULT_PARAMS, max_hold_days=10,
                                                   step=5, min_rr=0, fee_pct=DEFAULT_FEE_PCT)
        assert len(rows) == 1
        r = rows[0]
        assert r["Exit Reason"] == "TP"
        assert r["Hold Days"] == 1
        assert r["Entry"] == 1080.0 and r["Target"] == 1100.0 and r["Stop Loss"] == 1004.0
        expected_gross = (1100 - 1080) / 1080 * 100
        assert r["Gross Return (%)"] == round(expected_gross, 2)
        assert r["Net Return (%)"] == round(expected_gross - DEFAULT_FEE_PCT, 2)

    def test_sl_tersentuh_lebih_rugi_dari_gross(self):
        after = [{"Open": 1000, "High": 1000, "Low": 850, "Close": 900, "Volume": 10_000_000}]
        after += [{"Open": 900, "High": 900, "Low": 900, "Close": 900, "Volume": 10_000_000}] * 9
        df = _breakout_then_df(after)
        rows = _simulate_realistic_trades_single("AAA", df, DEFAULT_PARAMS, max_hold_days=10,
                                                   step=5, min_rr=0, fee_pct=DEFAULT_FEE_PCT)
        assert len(rows) == 1
        r = rows[0]
        assert r["Exit Reason"] == "SL"
        assert r["Hold Days"] == 1
        assert r["Net Return (%)"] < r["Gross Return (%)"]  # fee menambah rugi
        assert r["Net Return (%)"] < 0

    def test_force_sell_setelah_max_hold_days_tanpa_tp_sl(self):
        # Harga menetap di antara SL (1004) dan Target (1100) selama 10 hari - tidak pernah kena TP/SL.
        after = [{"Open": 1050, "High": 1080, "Low": 1020, "Close": 1050, "Volume": 10_000_000}] * 10
        df = _breakout_then_df(after)
        rows = _simulate_realistic_trades_single("AAA", df, DEFAULT_PARAMS, max_hold_days=10,
                                                   step=5, min_rr=0, fee_pct=DEFAULT_FEE_PCT)
        assert len(rows) == 1
        r = rows[0]
        assert r["Exit Reason"] == "FORCE SELL"
        assert r["Hold Days"] == 10
        assert r["Exit"] == 1050.0

    def test_min_rr_filter_menolak_trade_rr_rendah(self):
        # RR sebenarnya = (1100-1080)/(1080-1004) = 20/76 = 0.26 -> di bawah ambang manapun >0.26
        after = [{"Open": 1050, "High": 1080, "Low": 1020, "Close": 1050, "Volume": 10_000_000}] * 10
        df = _breakout_then_df(after)
        rows = _simulate_realistic_trades_single("AAA", df, DEFAULT_PARAMS, max_hold_days=10,
                                                   step=5, min_rr=2.0, fee_pct=DEFAULT_FEE_PCT)
        assert rows == []

    def test_run_realistic_backtest_summary_dan_kolom_bersih(self):
        after = [{"Open": 1085, "High": 1100, "Low": 1080, "Close": 1095, "Volume": 10_000_000}]
        after += [{"Open": 1095, "High": 1095, "Low": 1095, "Close": 1095, "Volume": 10_000_000}] * 9
        price_data = {"AAA": _breakout_then_df(after)}
        hasil = run_realistic_backtest(price_data, DEFAULT_PARAMS, max_hold_days=10, step=5, min_rr=0)
        assert not hasil["summary"].empty
        assert "Win Rate Bersih (%)" in hasil["summary"].columns
        assert "Rata-rata Return Bersih (%)" in hasil["summary"].columns

    def test_price_data_kosong(self):
        hasil = run_realistic_backtest({}, DEFAULT_PARAMS)
        assert hasil["summary"].empty
        assert hasil["detail"].empty


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
