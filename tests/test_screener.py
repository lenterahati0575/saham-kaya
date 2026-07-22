"""
Unit test untuk screener.py - TIDAK butuh koneksi internet/Yahoo Finance sama sekali.
Semua data harga di sini SINTETIS (dibuat manual dengan pandas), supaya logika skor bisa
diuji dengan angka yang presisi diketahui, dan supaya test ini bisa jalan otomatis di
GitHub Actions setiap kali ada perubahan kode (lihat .github/workflows/tests.yml).
"""

import numpy as np
import pandas as pd
import pytest

from screener import DEFAULT_PARAMS, compute_metrics, market_regime, build_trade_candidates


def _flat_ohlcv(n: int, price: float = 1000.0, volume: float = 2_000_000.0) -> pd.DataFrame:
    """DataFrame OHLCV datar (harga & volume konstan) sepanjang n hari - dipakai sebagai
    dasar histori sebelum baris terakhir diubah untuk menguji skenario tertentu."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": price, "High": price, "Low": price, "Close": price, "Volume": volume,
    }, index=idx)


def _params(**overrides):
    p = dict(DEFAULT_PARAMS)
    p.update(overrides)
    return p


class TestGateLikuiditas:
    def test_saham_ilikuid_di_skip(self):
        # value traded = price * avg_volume20 harus DI BAWAH min_value_traded
        df = _flat_ohlcv(25, price=100, volume=1_000)  # value traded ~ Rp100rb/hari
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m is not None
        assert m["Score"] == -99
        assert m["Signal"] == "SKIP (ILIKUID)"
        assert m["Layak Likuiditas"] is False

    def test_saham_likuid_lolos_gate(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)  # value traded = Rp10 miliar/hari
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Layak Likuiditas"] is True
        assert m["Score"] != -99


class TestCrashVeto:
    def test_crash_veto_sekarang_hard_block_bukan_cuma_penalti(self):
        """Sebelum perbaikan: saham crash tajam TAPI breakout+volume tinggi bisa tetap lolos
        BUY karena bonus breakout(+3) dan volume(+3 atau +5) menutup penalti crash lama (-3).
        Setelah perbaikan: begitu crash_veto tersentuh, skor HARUS -50 (SKIP), titik - tidak
        peduli seberapa besar bonus breakout/volume lainnya."""
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        # Hari terakhir: harga jatuh -8% (lebih dari crash_veto -5%) TAPI volume meledak 5x
        # dan harga breakout di atas seluruh histori - kombinasi yang dulu bisa lolos BUY.
        df.iloc[-1, df.columns.get_loc("Close")] = 920.0  # -8% dari 1000
        df.iloc[-1, df.columns.get_loc("High")] = 2000.0  # breakout jauh di atas histori
        df.iloc[-1, df.columns.get_loc("Volume")] = 50_000_000  # 5x avg volume

        m = compute_metrics(df, _params(min_value_traded=3_000_000_000, crash_veto=-0.05))
        assert m["Score"] == -50, "Crash veto harus hard block, bukan cuma penalti -3 poin"
        assert m["Signal"] == "SKIP (CRASH VETO)"

    def test_penurunan_kecil_tidak_kena_veto(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Close")] = 985.0  # -1.5%, di atas ambang -5%
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000, crash_veto=-0.05))
        assert m["Score"] != -50
        assert m["Signal"] != "SKIP (CRASH VETO)"


class TestBreakoutDonchian:
    def test_donchian_tidak_menghitung_candle_hari_ini(self):
        """Donchian High/Low harus dihitung dari histori SEBELUM hari ini - kalau hari ini
        breakout, level Donchian High-nya tidak boleh ikut naik gara-gara harga hari ini."""
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Close")] = 1500.0
        df.iloc[-1, df.columns.get_loc("High")] = 1500.0
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000, donchian_lookback=20))
        assert m["Donchian High"] == 1000.0  # histori sebelum hari ini masih flat di 1000
        assert m["Status Breakout"] == "BREAKOUT"

    def test_strong_buy_saat_breakout_dan_volume_tinggi(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Close")] = 1080.0  # +8%
        df.iloc[-1, df.columns.get_loc("High")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 40_000_000  # 4x avg volume
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Signal"] == "STRONG BUY"
        assert m["Score"] >= DEFAULT_PARAMS["score_strong_buy"]

    def test_data_kurang_return_none(self):
        df = _flat_ohlcv(5)  # kurang dari lookback+2
        assert compute_metrics(df, _params()) is None


class TestMarketRegime:
    def test_bullish_saat_close_di_atas_ma(self):
        idx = pd.date_range("2024-01-01", periods=60, freq="B")
        prices = np.linspace(6000, 7200, 60)  # uptrend jelas
        df = pd.DataFrame({"Close": prices}, index=idx)
        r = market_regime(df, ma_period=50)
        assert r["status"] == "BULLISH"

    def test_bearish_saat_close_di_bawah_ma(self):
        idx = pd.date_range("2024-01-01", periods=60, freq="B")
        prices = np.linspace(7200, 6000, 60)  # downtrend jelas
        df = pd.DataFrame({"Close": prices}, index=idx)
        r = market_regime(df, ma_period=50)
        assert r["status"] == "BEARISH"

    def test_unknown_saat_data_kurang(self):
        df = pd.DataFrame({"Close": [7000, 7010, 7020]})
        r = market_regime(df, ma_period=50)
        assert r["status"] == "UNKNOWN"


class TestBuildTradeCandidates:
    def test_hanya_lolos_rr_minimum(self):
        table = pd.DataFrame([
            {"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 1000.0, "Value Traded (Rp)": 5e9},
            {"Kode": "BBB", "Signal": "BUY", "Score": 6, "Harga": 1000.0, "Value Traded (Rp)": 5e9},
        ])
        # AAA: RR tinggi (SL dekat, target jauh) -> lolos. BBB: RR rendah -> tidak lolos.
        price_data = {
            "AAA": _flat_ohlcv(25, price=1000).assign(
                **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 950)}
            ),
            "BBB": _flat_ohlcv(25, price=1000),
        }
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=2.0, top_n=10)
        assert isinstance(out, pd.DataFrame)
        # Tidak boleh ada baris dengan RR < 2.0
        if not out.empty:
            assert (out["RR"] >= 2.0).all()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
