"""
Unit test untuk screener.py - TIDAK butuh koneksi internet/Yahoo Finance sama sekali.
Semua data harga di sini SINTETIS (dibuat manual dengan pandas), supaya logika skor bisa
diuji dengan angka yang presisi diketahui, dan supaya test ini bisa jalan otomatis di
GitHub Actions setiap kali ada perubahan kode (lihat .github/workflows/tests.yml).
"""

import numpy as np
import pandas as pd
import pytest

from screener import (DEFAULT_PARAMS, compute_metrics, market_regime, build_trade_candidates,
                      ihsg_seasonality, build_screener_table, build_simple_candidates,
                      compute_zigzag_pivots)


def _flat_ohlcv(n: int, price: float = 1000.0, volume: float = 2_000_000.0) -> pd.DataFrame:
    """DataFrame OHLCV datar (harga & volume konstan) sepanjang n hari - dipakai sebagai
    dasar histori sebelum baris terakhir diubah untuk menguji skenario tertentu."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": price, "High": price, "Low": price, "Close": price, "Volume": volume,
    }, index=idx)


def _uptrend_ohlcv(n: int, start_price: float = 1000.0, step: float = 2.0,
                    volume: float = 10_000_000.0) -> pd.DataFrame:
    """DataFrame OHLCV naik LINEAR sepanjang n hari - dipakai khusus utk uji "Gap Trend
    Aligned" (susunan MA20>MA50>MA200 butuh histori panjang & benar-benar uptrend,
    _flat_ohlcv tidak cukup krn harga datar bikin semua MA sama)."""
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    prices = [start_price + i * step for i in range(n)]
    return pd.DataFrame({
        "Open": prices, "High": prices, "Low": prices, "Close": prices, "Volume": volume,
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


class TestOpenLowPattern:
    """Pola "Open=Low" (Shaven Bottom) - EKSPLORATIF, ditambahkan setelah user berbagi
    sistem trading praktisi ttg candle tanpa ekor bawah. TIDAK divalidasi backtest (butuh
    konfirmasi order book yg tidak ada di data historis) - cuma info tambahan di UI."""

    def test_low_sama_open_terdeteksi_shaven_bottom(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        # Breakout + volume tinggi + Low == Open (candle tanpa ekor bawah sama sekali)
        df.iloc[-1, df.columns.get_loc("Open")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1080.0
        df.iloc[-1, df.columns.get_loc("High")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 40_000_000
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is True
        assert m["Status Breakout"] == "BREAKOUT"
        assert m["Setup A Breakout"] is True  # shaven bottom + breakout + volume tinggi

    def test_ada_ekor_bawah_tidak_terdeteksi(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        # Low JAUH di bawah Open (ekor bawah panjang) - bukan shaven bottom
        df.iloc[-1, df.columns.get_loc("Open")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1080.0
        df.iloc[-1, df.columns.get_loc("High")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 40_000_000
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is False
        assert m["Setup A Breakout"] is False

    def test_shaven_bottom_tanpa_breakout_bukan_setup_a(self):
        # Low==Open (shaven bottom) TAPI harga TIDAK breakout (masih di dalam range histori
        # flat 1000) - "Open=Low" True tapi "Setup A Breakout" False (syarat breakout gagal).
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1000.0
        df.iloc[-1, df.columns.get_loc("High")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 40_000_000
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is True
        assert m["Status Breakout"] != "BREAKOUT"
        assert m["Setup A Breakout"] is False

    def test_shaven_bottom_breakout_tapi_volume_rendah_bukan_setup_a(self):
        # Low==Open + breakout, TAPI volume TIDAK di atas ambang 1.5x rata-rata - gagal
        # syarat "volume tinggi" di Setup A.
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1080.0
        df.iloc[-1, df.columns.get_loc("High")] = 1080.0
        df.iloc[-1, df.columns.get_loc("Volume")] = 10_000_000  # SAMA dgn rata-rata, bukan 1.5x
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is True
        assert m["Status Breakout"] == "BREAKOUT"
        assert m["Setup A Breakout"] is False

    def test_open_low_trend_aligned_true_saat_susunan_ma_bullish_penuh(self):
        # SAMA persis konsep dgn "Gap Trend Aligned" (Harga>MA20>MA50>MA200, no lookahead).
        # Dibacktest (README > "Backtest Open=Low"): Setup B (tanpa breakout) + Trend
        # Aligned avg +0,30%/hari (vs -0,05% tanpa filter) - info tambahan, BUKAN filter
        # keras (magnitude masih di bawah fee 0,4%, beda dari Gap Up yg +2,82%).
        df = _uptrend_ohlcv(251, start_price=1000.0, step=2.0)
        prev_close = float(df["Close"].iloc[-2])
        df.iloc[-1, df.columns.get_loc("Open")] = prev_close
        df.iloc[-1, df.columns.get_loc("Low")] = prev_close  # Low == Open -> shaven bottom
        df.iloc[-1, df.columns.get_loc("Close")] = prev_close * 1.01
        df.iloc[-1, df.columns.get_loc("High")] = prev_close * 1.01
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is True
        assert m["Open=Low Trend Aligned"] is True

    def test_open_low_trend_aligned_false_kalau_histori_flat(self):
        df = _flat_ohlcv(251, price=1000.0, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1000.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1010.0
        df.iloc[-1, df.columns.get_loc("High")] = 1010.0
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Open=Low"] is True
        assert m["Open=Low Trend Aligned"] is False


class TestGapUpDown:
    """classify_gap() - EKSPLORATIF, proxy dari data EOD (Open vs Prev Close), belum
    dibacktest. Ditambahkan atas permintaan user setelah berbagi materi trading gap
    up/down - beda dari sistem intraday (opening range/VWAP) yg butuh data real-time
    yang tidak tersedia gratis."""

    def test_gap_up_terdeteksi_dan_dikonfirmasi(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)  # prev close = 1000
        df.iloc[-1, df.columns.get_loc("Open")] = 1040.0   # +4% dari prev close -> Gap Up
        df.iloc[-1, df.columns.get_loc("Low")] = 1030.0
        df.iloc[-1, df.columns.get_loc("High")] = 1060.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1050.0  # Close >= Open -> konfirmasi
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP UP"
        assert round(m["Gap %"], 1) == 4.0
        assert m["Gap Konfirmasi"] is True

    def test_gap_down_terdeteksi_dan_dikonfirmasi_lanjut_turun(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 960.0    # -4% -> Gap Down
        df.iloc[-1, df.columns.get_loc("Low")] = 940.0
        df.iloc[-1, df.columns.get_loc("High")] = 965.0
        df.iloc[-1, df.columns.get_loc("Close")] = 950.0   # Close <= Open -> lanjut turun
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP DOWN"
        assert round(m["Gap %"], 1) == -4.0
        assert m["Gap Konfirmasi"] is True

    def test_gap_down_tidak_dikonfirmasi_artinya_arah_tidak_jelas(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 960.0
        df.iloc[-1, df.columns.get_loc("Low")] = 940.0
        df.iloc[-1, df.columns.get_loc("High")] = 985.0
        df.iloc[-1, df.columns.get_loc("Close")] = 980.0   # Close > Open -> gap mulai "dimakan"
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP DOWN"
        assert m["Gap Konfirmasi"] is False

    def test_gap_di_bawah_ambang_tidak_dianggap_gap(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1010.0   # +1%, di bawah ambang default 3%
        df.iloc[-1, df.columns.get_loc("Low")] = 1005.0
        df.iloc[-1, df.columns.get_loc("High")] = 1020.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1015.0
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "NONE"

    def test_gap_up_dgn_breakout_dan_volume_tinggi_terdeteksi_gap_breakout(self):
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1040.0    # gap up
        df.iloc[-1, df.columns.get_loc("Low")] = 1030.0
        df.iloc[-1, df.columns.get_loc("High")] = 1080.0    # > histori flat 1000 -> BREAKOUT
        df.iloc[-1, df.columns.get_loc("Close")] = 1070.0   # >= Open -> konfirmasi
        df.iloc[-1, df.columns.get_loc("Volume")] = 40_000_000  # 4x rata-rata -> volume tinggi
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP UP"
        assert m["Status Breakout"] == "BREAKOUT"
        assert m["Gap Breakout"] is True

    def test_ambang_gap_bisa_diatur_lewat_params(self):
        # gap_min_pct dinaikkan ke 6% - gap +4% seharusnya TIDAK lolos lagi.
        df = _flat_ohlcv(25, price=1000, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1040.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1030.0
        df.iloc[-1, df.columns.get_loc("High")] = 1060.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1050.0
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000, gap_min_pct=6.0))
        assert m["Gap Type"] == "NONE"

    def test_trend_aligned_true_saat_susunan_ma_bullish_penuh(self):
        # Susunan MA20>MA50>MA200 (uptrend panjang, 250 hari) + Gap Up + Konfirmasi.
        # Dibacktest (615 saham/5 tahun): kombinasi ini avg +2,82%/hari berikutnya,
        # konsisten split-half (+2,91%/+2,74%) - jauh di atas Gap Up+Konfirmasi tanpa
        # filter tren (+1,42%). Atas permintaan user: "diatas MA20 diatas MA50 dan MA200,
        # MA50 diatas MA200... MA20>MA50>MA200".
        df = _uptrend_ohlcv(251, start_price=1000.0, step=2.0)
        prev_close = float(df["Close"].iloc[-2])
        gap_open = prev_close * 1.04
        df.iloc[-1, df.columns.get_loc("Open")] = gap_open
        df.iloc[-1, df.columns.get_loc("Low")] = gap_open * 0.995
        df.iloc[-1, df.columns.get_loc("Close")] = gap_open * 1.01   # >= Open -> konfirmasi
        df.iloc[-1, df.columns.get_loc("High")] = gap_open * 1.02
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP UP"
        assert m["Gap Konfirmasi"] is True
        assert m["Gap Trend Aligned"] is True

    def test_trend_aligned_false_kalau_histori_flat_walau_gap_up_konfirmasi(self):
        # Histori PANJANG (250 hari, cukup utk MA200) tapi FLAT (bukan uptrend) - harga
        # kemarin TIDAK di atas MA20/50/200 (semua sama), jadi trend_aligned harus False
        # walau Gap Up-nya sendiri terdeteksi & confirmed.
        df = _flat_ohlcv(251, price=1000.0, volume=10_000_000)
        df.iloc[-1, df.columns.get_loc("Open")] = 1040.0
        df.iloc[-1, df.columns.get_loc("Low")] = 1030.0
        df.iloc[-1, df.columns.get_loc("Close")] = 1050.0
        df.iloc[-1, df.columns.get_loc("High")] = 1060.0
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP UP"
        assert m["Gap Konfirmasi"] is True
        assert m["Gap Trend Aligned"] is False

    def test_trend_aligned_selalu_false_untuk_gap_down_walau_uptrend(self):
        # Versi simetris (susunan bearish penuh) utk Gap Down DIUJI TAPI TIDAK terbukti
        # (README > "Backtest Gap Up/Down") - trend_aligned SELALU False utk Gap Down,
        # brapa pun susunan MA-nya, supaya tidak jadi filter ketat yang keliru di sisi itu.
        df = _uptrend_ohlcv(251, start_price=1000.0, step=2.0)
        prev_close = float(df["Close"].iloc[-2])
        gap_open = prev_close * 0.96  # -4% gap down
        df.iloc[-1, df.columns.get_loc("Open")] = gap_open
        df.iloc[-1, df.columns.get_loc("High")] = gap_open * 1.005
        df.iloc[-1, df.columns.get_loc("Close")] = gap_open * 0.99   # <= Open -> lanjut turun
        df.iloc[-1, df.columns.get_loc("Low")] = gap_open * 0.98
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP DOWN"
        assert m["Gap Trend Aligned"] is False

    def test_trend_aligned_false_kalau_histori_kurang_dari_200_hari(self):
        # Uptrend tapi histori cuma 25 hari (kurang dari 200) - ma200_prev None ->
        # trend_aligned harus False, bukan error.
        df = _uptrend_ohlcv(26, start_price=1000.0, step=2.0)
        prev_close = float(df["Close"].iloc[-2])
        gap_open = prev_close * 1.04
        df.iloc[-1, df.columns.get_loc("Open")] = gap_open
        df.iloc[-1, df.columns.get_loc("Low")] = gap_open * 0.995
        df.iloc[-1, df.columns.get_loc("Close")] = gap_open * 1.01
        df.iloc[-1, df.columns.get_loc("High")] = gap_open * 1.02
        m = compute_metrics(df, _params(min_value_traded=3_000_000_000))
        assert m["Gap Type"] == "GAP UP"
        assert m["Gap Trend Aligned"] is False


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
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=2.0, top_n=10, require_minervini_position=False)
        assert isinstance(out, pd.DataFrame)
        # Tidak boleh ada baris dengan RR < 2.0
        if not out.empty:
            assert (out["RR"] >= 2.0).all()

    def test_regime_bearish_kosongkan_kandidat(self):
        # Entry=910 (dekat Donchian Low=900, jauh dari Donchian High=1000) -> RR tinggi
        # (risk kecil, reward besar). Entry == Donchian High selalu menghasilkan RR == 1.0
        # persis (Target = 2*High - Low, jadi Reward = High - Low = Risk kalau Entry = High) -
        # itu sebabnya entry TIDAK dibuat sama dengan harga flat 1000 seperti fixture lain.
        table = pd.DataFrame([
            {"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9},
        ])
        price_data = {
            "AAA": _flat_ohlcv(25, price=1000).assign(
                **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)}
            ),
        }
        out_bearish = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False,
                                              require_bullish_regime=True, regime_status="BEARISH")
        assert out_bearish.empty

        out_bullish = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False,
                                              require_bullish_regime=True, regime_status="BULLISH")
        assert not out_bullish.empty

        out_default = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert not out_default.empty  # require_bullish_regime default False - perilaku lama tidak berubah

    def test_tanpa_total_equity_lot_tidak_diisi(self):
        # Entry=910, Donchian Low=900, Donchian High=1000 (sama seperti fixture regime test)
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert "Lot" not in out.columns  # perilaku lama: fallback ke default 10 lot di gsheet_journal.py

    def test_dengan_total_equity_lot_dihitung_dari_risiko(self):
        # risk = entry - sl = 910 - 900 = 10 (Rupiah/lembar). Modal 10jt, risiko 1% = Rp100rb.
        # lembar = 100_000 / 10 = 10_000 -> lot = 10_000 // 100 = 100.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False,
                                      total_equity=10_000_000, risk_pct=1.0)
        assert "Lot" in out.columns
        assert out.iloc[0]["Lot"] == 100

    def test_risiko_terlalu_kecil_saham_dilewati_bukan_fallback_default(self):
        # Modal sangat kecil -> lot hasil hitung < 1 -> JANGAN fallback ke lot default (itu
        # melanggar batas risiko yang diminta), saham ini harus DIKELUARKAN dari hasil.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False,
                                      total_equity=100.0, risk_pct=1.0)
        assert out.empty


class TestBuildSimpleCandidates:
    """Screener SEDERHANA (pembanding) - user: "apakah perlu buat screener pembanding.
    mungkin lebih sederhana tapi bisa winrate lebih tinggi dan buy/sellnya tepat", lalu
    "target saya yang penting profit dengan risk rendah, tetap profesional." 3 syarat
    entry (breakout + posisi 52-minggu + volume RENDAH), SL dibatasi 5% (bukan 10% spt
    build_trade_candidates()) - DIUJI (350 saham/3 tahun, walk-forward): N=381, avg
    +9,70%/trade, win rate 59,1%, Profit Factor 6,22 - jauh lebih baik dari sistem Score-
    komposit (+2,16%/trade, PF 1,68). README > "Screener Sederhana: Breakout + Posisi
    52-Minggu + Volume Rendah"."""

    def _price_data(self, low_override_2nd_last=900.0):
        return {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], low_override_2nd_last)})}

    def _table(self, harga=1010.0, minervini_ok=True, volume_ratio=0.8, donchian_high=1000.0):
        return pd.DataFrame([{
            "Kode": "AAA", "Harga": harga, "Donchian High": donchian_high,
            "Minervini Position OK": minervini_ok, "Volume Ratio": volume_ratio,
        }])

    def test_lolos_semua_3_kriteria_muncul_di_hasil(self):
        out = build_simple_candidates(self._table(), self._price_data(), lookback=20, min_rr=1.5)
        assert list(out["Saham"]) == ["AAA"]

    def test_tanpa_breakout_dikeluarkan(self):
        # Harga (990) TIDAK di atas Donchian High (1000) - bukan breakout.
        out = build_simple_candidates(self._table(harga=990.0), self._price_data(), lookback=20, min_rr=1.5)
        assert out.empty

    def test_minervini_gagal_dikeluarkan(self):
        out = build_simple_candidates(self._table(minervini_ok=False), self._price_data(), lookback=20, min_rr=1.5)
        assert out.empty

    def test_volume_tinggi_dikeluarkan(self):
        # Volume Ratio 1.5 (>1.0) - KEBALIKAN dari yang diinginkan (volume RENDAH).
        out = build_simple_candidates(self._table(volume_ratio=1.5), self._price_data(), lookback=20, min_rr=1.5)
        assert out.empty

    def test_volume_persis_1_0_tetap_lolos(self):
        # Ambang inklusif (<=1.0), bukan eksklusif (<1.0).
        out = build_simple_candidates(self._table(volume_ratio=1.0), self._price_data(), lookback=20, min_rr=1.5)
        assert not out.empty

    def test_sl_dibatasi_5_persen_bukan_10_persen(self):
        # Breakout jauh (entry=1200, dh=1000) & Donchian Low sangat rendah (500) & MA20~1000
        # - keduanya JAUH dari entry, jadi cap 5% (1200*0.95=1140) yang MENGIKAT.
        # target_proj_mult=1.0 dipertahankan (bukan default baru 0.5) - test ini soal SL
        # cap, bukan target, biar RR (dgn range dh-dl=500) tetap jauh di atas min_rr=1.5.
        table = self._table(harga=1200.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=500.0)
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=1.5, target_proj_mult=1.0)
        assert not out.empty
        assert out.iloc[0]["Stop Loss"] == 1140.0  # 1200 * (1 - 0.05)

    def test_sl_cap_pct_bisa_dikustom(self):
        table = self._table(harga=1200.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=500.0)
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=1.5, sl_cap_pct=0.10,
                                       target_proj_mult=1.0)
        assert out.iloc[0]["Stop Loss"] == 1080.0  # 1200 * (1 - 0.10)

    def test_kolom_persen_sl_menghitung_jarak_riil_bukan_selalu_cap(self):
        # entry=1010 (breakout TIPIS di atas dh=1000) -> sl_cap 5% = 959,5, TAPI MA20 (~1000,
        # dari histori flat) LEBIH TINGGI drpd cap - MA20 yang mengikat (SL=1000), BUKAN cap -
        # jarak riilnya jauh LEBIH KETAT dari 5% & harus tercermin di kolom "% SL".
        table = self._table(harga=1010.0, donchian_high=1000.0)
        out = build_simple_candidates(table, self._price_data(), lookback=20, min_rr=1.5)
        sl = out.iloc[0]["Stop Loss"]
        assert sl == 1000.0
        expected_pct = round((1010.0 - sl) / 1010.0 * 100, 2)
        assert out.iloc[0]["% SL"] == expected_pct
        assert out.iloc[0]["% SL"] < 5.0  # SL riil lebih ketat dari cap 5%, harus tercermin

    def test_regime_bearish_kosongkan_kandidat(self):
        out_bearish = build_simple_candidates(self._table(), self._price_data(), lookback=20, min_rr=1.5,
                                               require_bullish_regime=True, regime_status="BEARISH")
        assert out_bearish.empty
        out_bullish = build_simple_candidates(self._table(), self._price_data(), lookback=20, min_rr=1.5,
                                               require_bullish_regime=True, regime_status="BULLISH")
        assert not out_bullish.empty

    def test_total_equity_menghitung_lot(self):
        table = self._table(harga=1200.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=500.0)
        # risk = 1200-1140 = 60/lembar. Modal 10jt, risiko 1% = Rp100rb -> lembar=1666 -> lot=16.
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=1.5,
                                       total_equity=10_000_000, risk_pct=1.0, target_proj_mult=1.0)
        assert "Lot" in out.columns
        assert out.iloc[0]["Lot"] == 16

    def test_tanpa_total_equity_lot_tidak_diisi(self):
        out = build_simple_candidates(self._table(), self._price_data(), lookback=20, min_rr=1.5)
        assert "Lot" not in out.columns

    def test_rr_di_bawah_minimum_dikeluarkan(self):
        # entry=1001 (breakout tipis di atas dh=1000), dl=900, ma20~1000 -> sl=max(900,1000,
        # 1001*0.95=950.95)=1000 (ma20 mengikat) -> risk=1, target=1000+100=1100,
        # reward=99 -> rr=99 (lolos), jadi utk uji GAGAL rr, pakai min_rr sangat tinggi.
        out = build_simple_candidates(self._table(harga=1001.0), self._price_data(), lookback=20, min_rr=200.0)
        assert out.empty

    def test_default_target_proj_mult_sekarang_0_5_bukan_1_0(self):
        # User: "uji juga target rr" - dulu target = dh + 1,0x(dh-dl) - diuji ulang di
        # sistem gabungan (RR tetap KALAH vs proyeksi Donchian; kelipatan proyeksi 0,25x-
        # 2,0x DIUJI, puncak jelas di 0,3-0,5x - dipilih 0,5x, PF 9,44 vs 7,17 lama, split-
        # half paling stabil). entry=1200, dh=1000, dl=500 (range=500) -> target default
        # BARU = 1000+0,5*500=1250 (BUKAN 1500 spt default lama).
        table = self._table(harga=1200.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=500.0)
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=0.1)  # target_proj_mult TIDAK diisi -> pakai default
        assert not out.empty
        assert out.iloc[0]["Target"] == 1250.0

    def test_target_proj_mult_bisa_dikustom(self):
        table = self._table(harga=1200.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=500.0)
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=0.1, target_proj_mult=1.0)
        assert out.iloc[0]["Target"] == 1500.0  # 1000 + 1.0*(1000-500)

    def test_default_min_rr_tetap_1_5_bukan_2_0(self):
        # User sempat minta RR minimum dinaikkan ke 2.0 (README > "RR Minimum Dinaikkan"),
        # TAPI setelah target proyeksi JUGA diperketat ke 0,5x (target_proj_mult), KEDUA
        # pengetatan itu MENUMPUK & bikin sinyal jadi terlalu jarang (user: "apakah
        # screener cocok...saya tidak centang volume 3M" - laporan tab sering kosong).
        # Dikembalikan ke 1.5 - lihat catatan lengkap di docstring atas & README.
        #
        # entry=1010, dh=1000, dl=944 (via low_override) -> sl=1000 (ma20 mengikat),
        # risk=10, target (proyeksi 0,5x default) = 1000+0,5*(1000-944)=1028, reward=18 ->
        # RR=1,8: LOLOS di default SEKARANG (>=1.5), akan GAGAL kalau default masih 2.0.
        table = self._table(harga=1010.0, donchian_high=1000.0)
        price_data = self._price_data(low_override_2nd_last=944.0)
        out = build_simple_candidates(table, price_data, lookback=20)  # min_rr TIDAK diisi -> pakai default
        assert not out.empty
        assert out.iloc[0]["RR"] == 1.8

    def test_min_value_traded_default_nonaktif_tidak_menyaring(self):
        # Default 0 -> gate likuiditas nonaktif SAMA SEKALI (perilaku sblm gate ini ada) -
        # kandidat tidak likuid (Value Traded kecil) tetap lolos kalau parameter tidak diisi.
        table = self._table()
        table["Value Traded (Rp)"] = 100_000_000  # Rp 100 juta - jauh di bawah gate 3 M
        out = build_simple_candidates(table, self._price_data(), lookback=20, min_rr=1.5)
        assert not out.empty

    def test_min_value_traded_aktif_menyaring_saham_tidak_likuid(self):
        table = self._table()
        table["Value Traded (Rp)"] = 100_000_000  # Rp 100 juta - di bawah gate
        out = build_simple_candidates(table, self._price_data(), lookback=20, min_rr=1.5,
                                       min_value_traded=3_000_000_000)
        assert out.empty

    def test_min_value_traded_aktif_meloloskan_saham_likuid(self):
        table = self._table()
        table["Value Traded (Rp)"] = 5_000_000_000  # Rp 5 M - di atas gate
        out = build_simple_candidates(table, self._price_data(), lookback=20, min_rr=1.5,
                                       min_value_traded=3_000_000_000)
        assert not out.empty

    def test_min_value_traded_aktif_tanpa_kolom_tidak_crash(self):
        # Kolom "Value Traded (Rp)" tidak ada sama sekali di table (mis. caller lama/test
        # lain) - gate diabaikan drpd KeyError, TIDAK memblokir semua kandidat diam-diam.
        out = build_simple_candidates(self._table(), self._price_data(), lookback=20, min_rr=1.5,
                                       min_value_traded=3_000_000_000)
        assert not out.empty


class TestComputeZigzagPivots:
    """Fungsi murni, walk-forward-safe - dites dgn seri harga yg swing-nya dikontrol persis
    (naik >=5% dari titik awal -> arah 'up', turun >=5% dari peak -> pivot H, turun lagi ->
    extreme baru, naik >=5% dari situ -> pivot L) supaya index & tipe pivot bisa diverifikasi
    tepat, bukan cuma 'jalan tanpa error'."""

    def test_pivot_h_dan_l_terdeteksi_di_index_yang_benar(self):
        closes = ([1000] * 9 +
                  [1000, 1010, 1020, 1040, 1060, 1080, 1100,  # naik ke 1100 (idx 15) -> peak
                   1080, 1050, 1010, 990,                      # turun >=5% dari 1100 -> pivot H @ idx15
                   970, 950, 920, 900,                         # turun lagi, extreme baru 900 @ idx23
                   950])                                       # naik +5,56% dari 900 -> pivot L @ idx23
        s = pd.Series(closes)
        pivots = compute_zigzag_pivots(s, threshold_pct=5.0)
        assert pivots == [(15, 1100, "H"), (23, 900, "L")]

    def test_harga_flat_tidak_ada_pivot(self):
        s = pd.Series([1000] * 30)
        assert compute_zigzag_pivots(s, threshold_pct=5.0) == []

    def test_ambang_lebih_tinggi_menyaring_swing_kecil(self):
        # Swing cuma +/-6% - lolos threshold 5%, tersaring kalau threshold dinaikkan ke 10%.
        closes = [1000] * 5 + [1000, 1060, 1000, 940, 1000]
        s = pd.Series(closes)
        assert len(compute_zigzag_pivots(s, threshold_pct=5.0)) > 0
        assert compute_zigzag_pivots(s, threshold_pct=10.0) == []


class TestBuildSimpleCandidatesZigZag:
    """Zig Zag sbg entry TAMBAHAN (OR, bukan pengganti Breakout) - user: "mungkin perlu
    diuji juga penggunaan zig zag" setelah mengeluhkan entry Breakout terlambat ("setelah
    harga sudah tinggi baru ditangkap screener"). DIUJI GABUNGAN dgn batas realistis 5
    slot/hari (README > "Zig Zag: Entry Tambahan"): Profit Factor gabungan (4,9) lebih
    tinggi dari Breakout (11,4) *dan* ZigZag (3,2) [avg tertimbang - PF gabungan BUKAN
    rata-rata sederhana kedua PF], krn ZigZag cuma mengisi slot yg Breakout tidak menyala."""

    def _zigzag_price_data(self, harga_hari_ini=1000.0):
        # harga_hari_ini=1000 -> naik 11,11% dari extreme low 900 (idx23), CUKUP utk lolos
        # threshold default 10% (bukan cuma 5% lama) - lihat catatan tuning threshold di
        # build_simple_candidates().
        pad = [1000] * 9
        closes = (pad +
                  [1000, 1010, 1020, 1040, 1060, 1080, 1100,
                   1080, 1050, 1010, 990,
                   970, 950, 920, 900,
                   harga_hari_ini])
        idx = pd.date_range("2024-01-01", periods=len(closes), freq="B")
        return {"BBB": pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                                      "Close": closes, "Volume": 5_000_000.0}, index=idx)}

    def _table_zigzag(self, minervini_ok=True, harga=1000.0, volume_ratio=0.8):
        # Volume Ratio RENDAH (0.8, default - Zig Zag SEKARANG juga mewajibkan ini, sama
        # spt Breakout, lihat komentar di is_zigzag_row) & Harga (1000) DI BAWAH Donchian
        # High (1100) - sengaja GAGAL syarat Breakout LEWAT HARGA, supaya sinyal yang
        # lolos di sini PASTI datang dari jalur Zig Zag, bukan kebetulan lolos Breakout.
        return pd.DataFrame([{
            "Kode": "BBB", "Harga": harga, "Donchian High": 1100.0,
            "Minervini Position OK": minervini_ok, "Volume Ratio": volume_ratio,
        }])

    def test_zigzag_low_terkonfirmasi_masuk_walau_bukan_breakout(self):
        out = build_simple_candidates(self._table_zigzag(), self._zigzag_price_data(),
                                       lookback=20, min_rr=0.1)
        assert list(out["Saham"]) == ["BBB"]
        assert out.iloc[0]["Tipe Sinyal"] == "ZigZag"

    def test_zigzag_volume_tinggi_dikeluarkan(self):
        # User: "coba tes zig zag dengan volume" - diuji (1.035 sinyal ZigZag sendirian,
        # 350 saham/3 tahun): volume RENDAH menang jelas (PF 3,46->4,15, winrate
        # 62,8%->70,9%), divalidasi ULANG di sistem gabungan+slot-cap (avg
        # +7,91%->+8,34%, PF 5,03->5,24) - Zig Zag SEKARANG juga mewajibkan volume
        # rendah, SAMA spt Breakout.
        out = build_simple_candidates(self._table_zigzag(volume_ratio=1.5), self._zigzag_price_data(),
                                       lookback=20, min_rr=0.1)
        assert out.empty

    def test_zigzag_volume_persis_1_0_tetap_lolos(self):
        # Ambang inklusif (<=1.0), sama pola dgn Breakout.
        out = build_simple_candidates(self._table_zigzag(volume_ratio=1.0), self._zigzag_price_data(),
                                       lookback=20, min_rr=0.1)
        assert not out.empty

    def test_zigzag_tanpa_minervini_tetap_dikeluarkan(self):
        # Minervini tetap wajib utk KEDUA jalur, bukan cuma Breakout.
        out = build_simple_candidates(self._table_zigzag(minervini_ok=False), self._zigzag_price_data(),
                                       lookback=20, min_rr=0.1)
        assert out.empty

    def test_lolos_breakout_dan_zigzag_bersamaan_ditandai_breakout(self):
        # Harga hari ini dinaikkan sampai breakout (>1100) + volume rendah (<=1.0) - lolos
        # KEDUA jalur sekaligus. Pivot Low @ idx23 (2 hari sebelum hari terakhir) tidak
        # berubah krn cuma nilai hari TERAKHIR (idx24) yang diubah.
        table = self._table_zigzag(harga=1150.0, volume_ratio=0.5)
        price_data = self._zigzag_price_data(harga_hari_ini=1150.0)
        out = build_simple_candidates(table, price_data, lookback=20, min_rr=0.1)
        assert list(out["Saham"]) == ["BBB"]
        assert out.iloc[0]["Tipe Sinyal"] == "Breakout"

    def test_bukan_breakout_dan_bukan_zigzag_dikeluarkan(self):
        # Harga hari ini diturunkan supaya BUKAN 1 hari setelah pivot Low (geser pola-nya).
        price_data = self._zigzag_price_data(harga_hari_ini=901.0)
        # Timpa 2 bar terakhir supaya pivot Low TIDAK lagi persis di idx n-2.
        df = price_data["BBB"]
        df.iloc[-2, df.columns.get_loc("Close")] = 905.0
        out = build_simple_candidates(self._table_zigzag(harga=901.0), price_data,
                                       lookback=20, min_rr=0.1)
        assert out.empty


class TestFilterAntiKejarHarga:
    """Bug nyata dari laporan user: klik 'Buka Posisi Swing Trading' di waktu sembarang
    (bukan pas market baru buka) bisa membeli saham yg SUDAH naik jauh dari Open hari itu,
    lalu koreksi kecil langsung kena SL (kasus nyata: SLIS beli 88, LOSS SL di 79, -10.63%).
    Dibacktest (615 saham/5 tahun): naik dari Open >10% saat entry -> avg net return NEGATIF
    konsisten di 2 periode. `max_naik_dari_open_pct` (default 10.0) memfilter ini di
    build_trade_candidates() - lihat README > 'Filter Anti-Kejar Harga'."""

    def _fixture(self, naik_dari_open_pct):
        # Entry=910, Donchian Low=900, Donchian High=1000 -> RR memenuhi min_rr=1.5 (sama
        # fixture dgn test regime/lot di atas).
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0,
                                "Value Traded (Rp)": 5e9, "Naik dari Open %": naik_dari_open_pct}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        return table, price_data

    def test_naik_dari_open_melebihi_ambang_default_dilewati(self):
        table, price_data = self._fixture(naik_dari_open_pct=15.0)  # > ambang default 10%
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert out.empty

    def test_naik_dari_open_dalam_ambang_tetap_lolos(self):
        table, price_data = self._fixture(naik_dari_open_pct=5.0)  # <= ambang default 10%
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert not out.empty

    def test_ambang_bisa_diatur_manual(self):
        table, price_data = self._fixture(naik_dari_open_pct=15.0)
        out_default = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert out_default.empty
        out_longgar = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False,
                                              max_naik_dari_open_pct=20.0)
        assert not out_longgar.empty

    def test_kolom_tidak_ada_tetap_jalan_seperti_dulu(self):
        # Tabel TANPA kolom "Naik dari Open %" sama sekali (mis. dari caller lama/test lain) -
        # tidak boleh crash, default ke 0 (tidak difilter).
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10, require_minervini_position=False)
        assert not out.empty


class TestIhsgSeasonality:
    """ihsg_seasonality() - fitur Efek Musiman, diminta user setelah nonton klaim 'Juli
    selalu hijau' di YouTube. Diuji dgn data sintetis 3 tahun yang Januari-nya SENGAJA
    selalu naik dan Februari-nya SENGAJA selalu turun, supaya avg_return & win_rate bisa
    diverifikasi persis (bukan cuma "jalan tanpa error")."""

    def _build_synthetic_monthly_df(self):
        # Titik "akhir bulan" yang nilainya dikontrol persis (dipakai resample().last())
        end_dates = [pd.Timestamp(2020, 1, 31), pd.Timestamp(2020, 2, 29)]
        end_dates += [pd.Timestamp(2020, m, 28) for m in range(3, 13)]
        end_dates += [pd.Timestamp(2021, 1, 31), pd.Timestamp(2021, 2, 28)]
        end_dates += [pd.Timestamp(2021, m, 28) for m in range(3, 13)]
        end_dates += [pd.Timestamp(2022, 1, 31), pd.Timestamp(2022, 2, 28)]
        end_dates += [pd.Timestamp(2022, m, 28) for m in range(3, 13)]
        end_closes = (
            [100, 90] + list(range(91, 101))       # 2020: Jan=100, Feb=90 (-10%), Mar..Des naik ke 100
            + [110, 99] + list(range(100, 110))    # 2021: Jan=110 (+10%), Feb=99 (-10%), Mar..Des ke 109
            + [120, 108] + list(range(109, 119))   # 2022: Jan=120 (+10.09%), Feb=108 (-10%), Mar..Des
        )
        assert len(end_dates) == len(end_closes) == 36
        # ihsg_seasonality() butuh >=60 baris MENTAH (jaga2 dari data harian yg jelas kurang) -
        # tambah baris "isian" di awal tiap bulan (SEBELUM tanggal akhir bulan di atas, jadi
        # tidak pernah jadi baris TERAKHIR yg diambil resample().last()) supaya total baris
        # cukup, tanpa mengubah nilai akhir bulan yang sudah dikontrol persis di atas.
        filler_dates = [d.replace(day=1) + pd.Timedelta(days=i) for d in end_dates for i in range(3)]
        filler_closes = [c for c in end_closes for _ in range(3)]  # nilai isian tidak relevan
        all_dates = filler_dates + end_dates
        all_closes = filler_closes + end_closes
        df = pd.DataFrame({"Close": all_closes}, index=pd.DatetimeIndex(all_dates)).sort_index()
        assert len(df) >= 60
        return df

    def test_januari_selalu_naik_win_rate_100(self):
        result = ihsg_seasonality(self._build_synthetic_monthly_df())
        jan = result[result["Bulan"] == "Jan"].iloc[0]
        assert jan["win_rate"] == 100.0
        assert jan["n_tahun"] == 2  # Jan 2020 tidak punya "return" (tidak ada Des 2019)
        assert jan["avg_return"] == pytest.approx(10.05, abs=0.1)

    def test_februari_selalu_turun_win_rate_0(self):
        result = ihsg_seasonality(self._build_synthetic_monthly_df())
        feb = result[result["Bulan"] == "Feb"].iloc[0]
        assert feb["win_rate"] == 0.0
        assert feb["n_tahun"] == 3
        assert feb["avg_return"] == pytest.approx(-10.0, abs=0.1)

    def test_urutan_bulan_jan_sampai_des(self):
        result = ihsg_seasonality(self._build_synthetic_monthly_df())
        assert result["Bulan"].tolist() == ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul",
                                             "Agu", "Sep", "Okt", "Nov", "Des"]

    def test_data_kosong_return_dataframe_kosong(self):
        assert ihsg_seasonality(pd.DataFrame()).empty
        assert ihsg_seasonality(None).empty

    def test_data_terlalu_pendek_return_kosong(self):
        short_df = pd.DataFrame({"Close": [100, 101]},
                                 index=pd.date_range("2024-01-01", periods=2))
        assert ihsg_seasonality(short_df).empty

    def test_split_half_konsisten_kalau_arah_sama_di_kedua_paruh(self):
        # Januari SENGAJA selalu naik di kedua tahun (2021 & 2022) - split-half harus konsisten.
        result = ihsg_seasonality(self._build_synthetic_monthly_df())
        jan = result[result["Bulan"] == "Jan"].iloc[0]
        assert jan["split_half_konsisten"] == True

    def test_p_value_terhitung_bukan_none_kalau_n_cukup(self):
        result = ihsg_seasonality(self._build_synthetic_monthly_df())
        feb = result[result["Bulan"] == "Feb"].iloc[0]
        assert feb["p_value"] is not None
        assert 0 <= feb["p_value"] <= 1


class TestMinerviniPosition52w:
    """Referensi screener profesional (Mark Minervini - Trend Template/SEPA) - user minta
    dievaluasi "apa yang perlu disempurnakan krn win rate rendah". Dibacktest (350 saham/3
    tahun, walk-forward): kandidat yg GAGAL posisi ini (blm >=25% dari low 52w ATAU masih
    >25% di bawah high 52w) terbukti MERUGI konsisten (median -2,85%, README > "Referensi
    Screener Profesional") - beda dari filter tren/RS relatif yg cuma memperbesar untung."""

    def test_ok_true_saat_uptrend_kuat_dan_dekat_high_52w(self):
        # Uptrend linear panjang -> harga hari ini selalu dekat high52w (baru dibuat) &
        # jauh di atas low52w (harga di awal histori, jauh lebih rendah).
        df = _uptrend_ohlcv(260, start_price=1000.0, step=3.0)
        m = compute_metrics(df, _params())
        assert m["Minervini Position OK"] is True
        assert m["Pct Above Low52w"] >= 25
        assert m["Pct Below High52w"] <= 25

    def test_ok_false_saat_histori_flat_belum_pernah_naik(self):
        # Flat total -> harga hari ini SAMA dgn low52w (0% di atas low) - gagal kriteria
        # ">=25% dari low", walau breakout kecil di hari terakhir.
        df = _flat_ohlcv(260, price=1000.0)
        df.iloc[-1, df.columns.get_loc("Close")] = 1010.0  # breakout kecil hari ini saja
        df.iloc[-1, df.columns.get_loc("High")] = 1010.0
        m = compute_metrics(df, _params())
        assert m["Minervini Position OK"] is False

    def test_none_kalau_histori_kurang_dari_60_hari(self):
        # compute_metrics() sendiri cuma butuh lookback+2 (22) hari, TAPI Minervini butuh
        # minimal 60 - histori 25 hari (spt banyak fixture lama) harus dapat False, BUKAN
        # crash/None yang tidak ditangani.
        df = _uptrend_ohlcv(25, start_price=1000.0, step=3.0)
        m = compute_metrics(df, _params())
        assert m["Minervini Position OK"] is False
        assert m["Pct Above Low52w"] is None
        assert m["Pct Below High52w"] is None


class TestMomentum5HariBeruntun:
    """Pola dari kursus user: "ciri saham yang mau naik - Close lebih tinggi dari hari
    sebelumnya selama minimal 5 hari, dengan volume meningkat". Dibacktest (350 saham/3
    tahun, walk-forward): TERVALIDASI KUAT - avg return +0,43%/+1,51% (1D/5D) vs baseline
    +0,10%/+0,48%, split-half KONSISTEN POSITIF di kedua paruh - lebih solid dari VCP.
    "Volume meningkat" diuji 2 definisi: LONGGAR (rata2 5 hari > rata2 20 hari sebelumnya)
    tervalidasi; KETAT (naik SETIAP hari) GAGAL split-half (N kecil) - LONGGAR yang dipakai.
    README > "Referensi Screener Profesional"."""

    def _histori_dgn_streak(self, close_5hari, volume_5hari, volume_sebelum=1_000_000.0):
        """25 hari flat (harga & volume dasar), lalu 5 hari terakhir diganti sesuai param -
        cukup utk syarat len(df)>=25 di compute_metrics()."""
        df = _flat_ohlcv(25, price=close_5hari[0] - 10, volume=volume_sebelum)
        tambahan = pd.DataFrame({
            "Open": close_5hari, "High": close_5hari, "Low": close_5hari,
            "Close": close_5hari, "Volume": volume_5hari,
        }, index=pd.bdate_range(df.index[-1] + pd.Timedelta(days=1), periods=5))
        return pd.concat([df.iloc[:-5], tambahan])  # ganti 5 hari terakhir, total tetap 25

    def test_true_saat_5_hari_naik_beruntun_dan_volume_rata2_lbh_tinggi(self):
        df = self._histori_dgn_streak(
            close_5hari=[1000, 1010, 1020, 1030, 1040],
            volume_5hari=[3_000_000] * 5,  # jauh > volume dasar 1jt
            volume_sebelum=1_000_000.0,
        )
        m = compute_metrics(df, _params())
        assert m["Momentum 5 Hari"] is True

    def test_false_kalau_hari_terakhir_turun_streak_putus(self):
        df = self._histori_dgn_streak(
            close_5hari=[1000, 1010, 1020, 1030, 1025],  # hari terakhir TURUN
            volume_5hari=[3_000_000] * 5,
            volume_sebelum=1_000_000.0,
        )
        m = compute_metrics(df, _params())
        assert m["Momentum 5 Hari"] is False

    def test_false_kalau_naik_beruntun_tapi_volume_tidak_naik(self):
        df = self._histori_dgn_streak(
            close_5hari=[1000, 1010, 1020, 1030, 1040],
            volume_5hari=[800_000] * 5,  # LEBIH RENDAH dari volume dasar 1jt
            volume_sebelum=1_000_000.0,
        )
        m = compute_metrics(df, _params())
        assert m["Momentum 5 Hari"] is False

    def test_false_kalau_histori_kurang_dari_25_hari_bukan_crash(self):
        # 24 hari: cukup utk compute_metrics() sendiri (min lookback+2=22), TAPI kurang dari
        # 25 yg dibutuhkan Momentum 5 Hari - harus False, BUKAN crash.
        df = _uptrend_ohlcv(24, start_price=1000.0, step=5.0)
        m = compute_metrics(df, _params())
        assert m is not None
        assert m["Momentum 5 Hari"] is False


class TestMinerviniFilterDiTradeCandidates:
    def _fixture_gagal_minervini(self):
        # Flat 300 hari (gagal posisi 52w - lihat test di atas), breakout kecil hari
        # terakhir spt fixture RR yg sudah ada di TestBuildTradeCandidates.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0,
                                "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(300, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        return table, price_data

    def test_default_membuang_kandidat_yang_gagal_posisi_52_minggu(self):
        table, price_data = self._fixture_gagal_minervini()
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10)
        assert out.empty  # require_minervini_position default True

    def test_matikan_filter_meloloskan_kandidat_yang_sama(self):
        table, price_data = self._fixture_gagal_minervini()
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10,
                                      require_minervini_position=False)
        assert not out.empty

    def test_kolom_tidak_ada_dianggap_gagal_bukan_crash(self):
        # table TANPA kolom "Minervini Position OK" sama sekali (mis. caller lama/test lain
        # yg bikin table manual) - default False (aman, bukan lolos diam2), BUKAN crash.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0,
                                "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10)
        assert out.empty


def _vcp_ohlcv(n_base: int = 40, prior_range_pct: float = 10.0, recent_range_pct: float = 1.0,
               price: float = 1000.0) -> pd.DataFrame:
    """OHLCV dgn range harian TERKENDALI: n_base hari flat (base), lalu 10 hari "prior"
    dgn range=prior_range_pct, lalu 10 hari "recent" dgn range=recent_range_pct, lalu 1
    baris terakhir (hari ini) breakout kecil. Dipakai uji Volatility Contraction Pattern."""
    idx = pd.date_range("2023-01-01", periods=n_base + 21, freq="B")
    rows = []
    for _ in range(n_base):
        rows.append({"Open": price, "High": price, "Low": price, "Close": price, "Volume": 10_000_000.0})
    for _ in range(10):  # prior 10 hari (SEBELUM recent)
        half = price * prior_range_pct / 100 / 2
        rows.append({"Open": price, "High": price + half, "Low": price - half, "Close": price, "Volume": 10_000_000.0})
    for _ in range(10):  # recent 10 hari (tepat SEBELUM hari ini)
        half = price * recent_range_pct / 100 / 2
        rows.append({"Open": price, "High": price + half, "Low": price - half, "Close": price, "Volume": 10_000_000.0})
    rows.append({"Open": price, "High": price * 1.03, "Low": price, "Close": price * 1.02, "Volume": 15_000_000.0})  # hari ini
    return pd.DataFrame(rows, index=idx)


class TestVCPKontraksi:
    """VCP (Volatility Contraction Pattern) proxy: rasio range 10 hari terakhir vs 10 hari
    sebelum itu (SEBELUM hari ini, no lookahead). Dibacktest: <0.7 (kontraksi kuat) menaikkan
    win rate (45,9% vs baseline ~33%) & menurunkan SL rate (46,9% vs ~57-60%) - TAPI median
    return kelompoknya TETAP NEGATIF (-1,98%), jadi dipakai sbg INFO + boost ranking, BUKAN
    filter keras (README > "Referensi Screener Profesional")."""

    def test_kuat_true_saat_range_menyempit_jauh(self):
        df = _vcp_ohlcv(n_base=40, prior_range_pct=10.0, recent_range_pct=1.0)
        m = compute_metrics(df, _params())
        assert m["VCP Kuat"] is True
        assert m["VCP Rasio Kontraksi"] < 0.7

    def test_kuat_false_saat_range_melebar(self):
        df = _vcp_ohlcv(n_base=40, prior_range_pct=1.0, recent_range_pct=10.0)
        m = compute_metrics(df, _params())
        assert m["VCP Kuat"] is False
        assert m["VCP Rasio Kontraksi"] > 1.0

    def test_kuat_false_saat_range_mirip_tidak_kontraksi(self):
        df = _vcp_ohlcv(n_base=40, prior_range_pct=5.0, recent_range_pct=4.5)
        m = compute_metrics(df, _params())
        assert m["VCP Kuat"] is False  # rasio 0.9 - bukan kontraksi KUAT (<0.7)

    def test_none_kalau_histori_kurang_dari_20_hari(self):
        # donchian_lookback dikecilkan (5) supaya compute_metrics() sendiri tidak butuh
        # >=22 baris (spt default) - fokus murni ke syarat VCP (>=20 hari histori SEBELUM
        # hari ini), bukan ketabrak syarat minimum compute_metrics() yg lain.
        df = _uptrend_ohlcv(10, start_price=1000.0, step=3.0)
        m = compute_metrics(df, _params(donchian_lookback=5))
        assert m["VCP Rasio Kontraksi"] is None
        assert m["VCP Kuat"] is False


class TestVCPBoostRankingDiTradeCandidates:
    """VCP Kuat = boost RANKING (bukan filter) - dipakai sbg kunci sort KEDUA (setelah RR,
    sebelum Score) supaya kandidat dgn kontraksi kuat diprioritaskan di antara RR yang sama,
    TANPA membuang kandidat yang tidak VCP."""

    def test_vcp_kuat_diprioritaskan_di_atas_rr_yang_sama(self):
        # Dua saham dgn RR yang PERSIS SAMA (Donchian High/Low identik) - AAA kontraksi kuat
        # (VCP), BBB tidak. Keduanya harus tetap lolos (VCP bukan filter), tapi AAA harus
        # muncul LEBIH DULU di hasil akhir.
        df_vcp = _vcp_ohlcv(n_base=250, prior_range_pct=10.0, recent_range_pct=1.0)  # 250+21 hari, lolos Minervini jg
        df_vcp.iloc[-2, df_vcp.columns.get_loc("Low")] = df_vcp["Close"].iloc[0] * 0.9  # Donchian Low seragam
        df_non_vcp = _vcp_ohlcv(n_base=250, prior_range_pct=1.0, recent_range_pct=10.0)
        df_non_vcp.iloc[-2, df_non_vcp.columns.get_loc("Low")] = df_non_vcp["Close"].iloc[0] * 0.9

        m_vcp = compute_metrics(df_vcp, _params())
        m_non_vcp = compute_metrics(df_non_vcp, _params())
        assert m_vcp["VCP Kuat"] is True
        assert m_non_vcp["VCP Kuat"] is False

        table = pd.DataFrame([
            {"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": m_vcp["Harga"],
             "Value Traded (Rp)": 5e9, "VCP Kuat": m_vcp["VCP Kuat"]},
            {"Kode": "BBB", "Signal": "BUY", "Score": 5, "Harga": m_non_vcp["Harga"],
             "Value Traded (Rp)": 5e9, "VCP Kuat": m_non_vcp["VCP Kuat"]},
        ])
        price_data = {"AAA": df_vcp, "BBB": df_non_vcp}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=0.1, top_n=10,
                                      require_minervini_position=False)
        assert len(out) == 2  # KEDUANYA tetap lolos - VCP bukan filter
        assert out.iloc[0]["Saham"] == "AAA"  # tapi AAA (VCP kuat) diprioritaskan di urutan pertama


class TestFilterSahamTidakAktifSuspen:
    """Bug nyata dari laporan user: DOOH SUSPEN (tidak ada transaksi hari itu) tapi masih
    muncul di screener - berpotensi jadi kandidat BELI utk saham yang tidak bisa ditransaksikan
    hari itu. Dideteksi 2 pola sekaligus (lihat komentar build_screener_table()): (a) bar hari
    itu ADA tapi Volume=0 (OHLC rata, tidak ada transaksi - pola nyata terlihat di histori
    DOOH 6 Agustus: O=H=L=C=274, Volume=0), (b) bar hari itu TIDAK ADA sama sekali (saham lain
    di batch scan yang sama sudah update ke tanggal lebih baru)."""

    def _names(self, kodes):
        return pd.DataFrame({"Kode": kodes, "Nama": kodes})

    def test_saham_dgn_volume_nol_hari_ini_dikeluarkan(self):
        df_aktif = _flat_ohlcv(30, price=1000, volume=10_000_000)
        df_suspen = df_aktif.copy()
        df_suspen.iloc[-1, df_suspen.columns.get_loc("Volume")] = 0
        price_data = {"AAA": df_aktif, "BBB": df_suspen}
        out = build_screener_table(price_data, self._names(["AAA", "BBB"]), _params())
        assert "AAA" in out["Kode"].tolist()
        assert "BBB" not in out["Kode"].tolist()

    def test_saham_dgn_bar_tertinggal_dari_pasar_dikeluarkan(self):
        # BBB histori-nya 1 hari lebih pendek -> tanggal bar terakhirnya TERTINGGAL dibanding
        # AAA (yang sudah update) - simulasi "belum ada bar baru sama sekali hari ini".
        df_aktif = _flat_ohlcv(30, price=1000, volume=10_000_000)
        df_tertinggal = _flat_ohlcv(29, price=1000, volume=10_000_000)
        price_data = {"AAA": df_aktif, "BBB": df_tertinggal}
        out = build_screener_table(price_data, self._names(["AAA", "BBB"]), _params())
        assert "AAA" in out["Kode"].tolist()
        assert "BBB" not in out["Kode"].tolist()

    def test_semua_saham_tertinggal_sehari_sama_rata_tidak_ada_yg_terfilter(self):
        # Scan dijalankan SEBELUM data market ter-update semua saham - SEMUA saham di batch
        # ini sama2 "tertinggal" 1 hari dari kalender asli, tapi SALING KONSISTEN satu sama
        # lain (tanggal bar terakhirnya SAMA) - tidak boleh ada yang salah kefilter.
        df_a = _flat_ohlcv(30, price=1000, volume=10_000_000)
        df_b = _flat_ohlcv(30, price=2000, volume=5_000_000)
        price_data = {"AAA": df_a, "BBB": df_b}
        out = build_screener_table(price_data, self._names(["AAA", "BBB"]), _params())
        assert set(out["Kode"]) == {"AAA", "BBB"}

    def test_kolom_internal_tanggal_harga_raw_tidak_bocor_ke_tabel_akhir(self):
        df = _flat_ohlcv(30, price=1000, volume=10_000_000)
        out = build_screener_table({"AAA": df}, self._names(["AAA"]), _params())
        assert "_tanggal_harga_raw" not in out.columns


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
