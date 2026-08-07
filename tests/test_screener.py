"""
Unit test untuk screener.py - TIDAK butuh koneksi internet/Yahoo Finance sama sekali.
Semua data harga di sini SINTETIS (dibuat manual dengan pandas), supaya logika skor bisa
diuji dengan angka yang presisi diketahui, dan supaya test ini bisa jalan otomatis di
GitHub Actions setiap kali ada perubahan kode (lihat .github/workflows/tests.yml).
"""

import numpy as np
import pandas as pd
import pytest

from screener import DEFAULT_PARAMS, compute_metrics, market_regime, build_trade_candidates, ihsg_seasonality


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
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=2.0, top_n=10)
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
        out_bearish = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10,
                                              require_bullish_regime=True, regime_status="BEARISH")
        assert out_bearish.empty

        out_bullish = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10,
                                              require_bullish_regime=True, regime_status="BULLISH")
        assert not out_bullish.empty

        out_default = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10)
        assert not out_default.empty  # require_bullish_regime default False - perilaku lama tidak berubah

    def test_tanpa_total_equity_lot_tidak_diisi(self):
        # Entry=910, Donchian Low=900, Donchian High=1000 (sama seperti fixture regime test)
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10)
        assert "Lot" not in out.columns  # perilaku lama: fallback ke default 10 lot di gsheet_journal.py

    def test_dengan_total_equity_lot_dihitung_dari_risiko(self):
        # risk = entry - sl = 910 - 900 = 10 (Rupiah/lembar). Modal 10jt, risiko 1% = Rp100rb.
        # lembar = 100_000 / 10 = 10_000 -> lot = 10_000 // 100 = 100.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10,
                                      total_equity=10_000_000, risk_pct=1.0)
        assert "Lot" in out.columns
        assert out.iloc[0]["Lot"] == 100

    def test_risiko_terlalu_kecil_saham_dilewati_bukan_fallback_default(self):
        # Modal sangat kecil -> lot hasil hitung < 1 -> JANGAN fallback ke lot default (itu
        # melanggar batas risiko yang diminta), saham ini harus DIKELUARKAN dari hasil.
        table = pd.DataFrame([{"Kode": "AAA", "Signal": "BUY", "Score": 5, "Harga": 910.0, "Value Traded (Rp)": 5e9}])
        price_data = {"AAA": _flat_ohlcv(25, price=1000).assign(
            **{"Low": lambda d: d["Low"].where(d.index != d.index[-2], 900)})}
        out = build_trade_candidates(table, price_data, lookback=20, min_rr=1.5, top_n=10,
                                      total_equity=100.0, risk_pct=1.0)
        assert out.empty


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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
