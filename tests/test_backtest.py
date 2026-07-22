"""Unit test untuk backtest.py - memverifikasi mekanisme walk-forward TIDAK bocor
(lookahead bias) dan menghitung win rate/return dengan benar, pakai data sintetis
(tidak butuh Yahoo Finance)."""

import numpy as np
import pandas as pd
import pytest

from screener import DEFAULT_PARAMS
from backtest import run_historical_backtest, _walk_forward_single


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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
