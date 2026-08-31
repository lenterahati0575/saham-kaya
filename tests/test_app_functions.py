"""
Unit test untuk fungsi-fungsi murni (bukan UI Streamlit) di app.py.

app.py TIDAK bisa di-import biasa (`import app`) karena berisi kode level-atas yang
langsung jalan begitu file dibuka - fetch data live, baca st.secrets, render UI, dst.
Modul ini mengekstrak definisi fungsi yang dibutuhkan lewat AST (baca source, ambil
node FunctionDef yang namanya cocok, compile & exec di namespace terbatas) - supaya
bisa dites TANPA menjalankan seluruh aplikasi. Pola ini juga dipakai skrip backtest
ML Signal (lihat riwayat validasi di README).
"""
import ast
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm  # dibutuhkan black_scholes() - tidak ikut ter-extract otomatis

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

_NEEDED_FUNCS = {
    "calculate_atr", "ml_signal_predict", "black_scholes", "validate_order",
    "format_countdown", "moon_phase", "fibonacci_retracement", "expected_move",
    "to_csv_excel_id",
}
# Konstanta level-modul yang dipakai fungsi di atas (mis. ml_signal_predict butuh
# _ML_SIGNAL_BACKTEST_STATS) - kalau tidak ikut di-extract, NameError di dalam fungsi
# akan tertelan diam-diam oleh try/except-nya dan cuma kelihatan sebagai return None.
_NEEDED_CONSTANTS = {"_ML_SIGNAL_BACKTEST_STATS"}


def _extract_functions():
    with open(APP_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    ns = {"np": np, "pd": pd, "math": math, "datetime": datetime, "timedelta": timedelta, "norm": norm}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _NEEDED_FUNCS:
            mod = ast.Module(body=[node], type_ignores=[])
            exec(compile(mod, f"<app_extract:{node.name}>", "exec"), ns)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in _NEEDED_CONSTANTS:
            mod = ast.Module(body=[node], type_ignores=[])
            exec(compile(mod, f"<app_extract:{node.targets[0].id}>", "exec"), ns)
    missing = _NEEDED_FUNCS - set(ns.keys())
    assert not missing, f"Fungsi tidak ditemukan di app.py (mungkin nama berubah): {missing}"
    missing_const = _NEEDED_CONSTANTS - set(ns.keys())
    assert not missing_const, f"Konstanta tidak ditemukan di app.py (mungkin nama berubah): {missing_const}"
    return ns


_FN = _extract_functions()
calculate_atr = _FN["calculate_atr"]
ml_signal_predict = _FN["ml_signal_predict"]
black_scholes = _FN["black_scholes"]
validate_order = _FN["validate_order"]
format_countdown = _FN["format_countdown"]
moon_phase = _FN["moon_phase"]
fibonacci_retracement = _FN["fibonacci_retracement"]
expected_move = _FN["expected_move"]
to_csv_excel_id = _FN["to_csv_excel_id"]


def _flat_ohlcv(n, price=1000.0, volume=2_000_000.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": price, "High": price, "Low": price, "Close": price, "Volume": volume}, index=idx)


class TestCalculateATR:
    def test_flat_price_atr_nol(self):
        df = _flat_ohlcv(30)
        assert calculate_atr(df, period=14) == pytest.approx(0.0, abs=1e-9)

    def test_data_kurang_return_nol(self):
        df = _flat_ohlcv(5)
        assert calculate_atr(df, period=14) == 0

    def test_true_range_naik_saat_volatil(self):
        df = _flat_ohlcv(30, price=1000.0)
        df.loc[df.index[-1], ["High", "Low"]] = [1050.0, 950.0]  # range 100 di hari terakhir
        atr = calculate_atr(df, period=14)
        assert atr > 0


class TestMLSignalPredict:
    def test_data_kurang_return_none(self):
        df = _flat_ohlcv(10)
        assert ml_signal_predict(df, lookback=20) is None

    def test_uptrend_kuat_score_tinggi_dan_win_rate_terisi(self):
        idx = pd.date_range("2024-01-01", periods=80, freq="B")
        close = np.linspace(1000, 1400, 80)  # uptrend tegas
        df = pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99,
                            "Close": close, "Volume": np.full(80, 3_000_000.0)}, index=idx)
        sig = ml_signal_predict(df, lookback=20)
        assert sig is not None
        assert sig["score"] >= 1  # uptrend jelas -> trend_score & momentum_score positif
        assert 0 <= sig["hist_win_rate"] <= 100
        # confidence yang ditampilkan HARUS sama dengan win rate historis (bukan lagi
        # rumus agreement*25 yang tidak divalidasi - lihat catatan di ml_signal_predict)
        assert sig["confidence"] == round(sig["hist_win_rate"])

    def test_harga_flat_dapat_score_1_bukan_0(self):
        """Kuirk yang ditemukan lewat test ini: harga benar-benar flat TIDAK menghasilkan
        Score=0/NETRAL seperti intuisi awal - karena vol_regime_score selalu +1 kalau ATR
        rendah (volatilitas rendah dianggap "baik" di ensemble ini terlepas arah), jadi
        baseline Score untuk data flat adalah 1 ("CUKUP KUAT"), bukan 0. Dicatat di sini
        supaya kalau kelak ada yang "memperbaiki" jadi 0, ketahuan itu perubahan berarti."""
        df = _flat_ohlcv(80, price=1000.0)
        sig = ml_signal_predict(df, lookback=20)
        assert sig is not None
        assert sig["score"] == 1
        assert sig["signal"] == "🟡 CUKUP KUAT (relatif)"

    def test_hist_avg_return_selalu_dalam_rentang_backtest(self):
        # Kalibrasi empiris (README > Backtest Historis: ML Signal) di rentang -3..6,
        # avg_return_10d antara +0.32% (Score=0) dan +2.42% (Score=6) - SEMUA positif,
        # karena drift pasar umum. Pastikan tidak ada nilai di luar rentang itu.
        idx = pd.date_range("2024-01-01", periods=80, freq="B")
        for step in [-2, -0.5, 0, 0.5, 2, 5]:
            close = 1000 + np.arange(80) * step
            close = np.clip(close, 1, None)
            df = pd.DataFrame({"Open": close, "High": close * 1.02, "Low": close * 0.98,
                                "Close": close, "Volume": np.full(80, 3_000_000.0)}, index=idx)
            sig = ml_signal_predict(df, lookback=20)
            if sig:
                assert 0.30 <= sig["hist_avg_return_10d"] <= 2.45


class TestBlackScholes:
    def test_put_call_parity(self):
        """Invarian matematis Black-Scholes: C - P = S - K*exp(-r*T). Cara verifikasi
        korektnes tanpa perlu angka referensi eksternal - kalau parity ini tidak
        terpenuhi, ada bug di formula."""
        S, K, T, r, sigma = 1000.0, 950.0, 0.25, 0.06, 0.30
        call = black_scholes(S, K, T, r, sigma, option_type="call")
        put = black_scholes(S, K, T, r, sigma, option_type="put")
        rhs = S - K * math.exp(-r * T)
        assert (call["price"] - put["price"]) == pytest.approx(rhs, abs=0.5)

    def test_call_price_naik_kalau_saham_naik(self):
        base = black_scholes(1000.0, 1000.0, 0.25, 0.06, 0.30, option_type="call")
        higher = black_scholes(1100.0, 1000.0, 0.25, 0.06, 0.30, option_type="call")
        assert higher["price"] > base["price"]

    def test_invalid_input_return_none(self):
        assert black_scholes(0, 1000, 0.25, 0.06, 0.30) is None
        assert black_scholes(1000, 1000, 0, 0.06, 0.30) is None
        assert black_scholes(1000, 1000, 0.25, 0.06, 0) is None


class TestValidateOrder:
    def test_dana_cukup_valid(self):
        ok, msg, total = validate_order("BBCA", "BUY", qty=10, price=1000, cash_available=2_000_000)
        assert ok is True

    def test_dana_tidak_cukup_invalid(self):
        ok, msg, total = validate_order("BBCA", "BUY", qty=100, price=1000, cash_available=1000)
        assert ok is False
        assert "Dana tidak cukup" in msg

    def test_qty_nol_invalid(self):
        ok, msg, total = validate_order("BBCA", "BUY", qty=0, price=1000, cash_available=10_000_000)
        assert ok is False

    def test_harga_nol_invalid(self):
        ok, msg, total = validate_order("BBCA", "BUY", qty=10, price=0, cash_available=10_000_000)
        assert ok is False


class TestFormatCountdown:
    def test_nol_atau_negatif(self):
        assert format_countdown(0) == "00:00:00"
        assert format_countdown(-5) == "00:00:00"

    def test_format_benar(self):
        assert format_countdown(3661) == "01:01:01"  # 1 jam 1 menit 1 detik


class TestMoonPhase:
    def test_di_tanggal_new_moon_acuan_age_mendekati_nol(self):
        result = moon_phase(datetime(2000, 1, 6, 18, 14))
        assert result["age"] == pytest.approx(0.0, abs=0.01)
        assert result["name"] == "🌑 NEW MOON"

    def test_setengah_siklus_full_moon(self):
        result = moon_phase(datetime(2000, 1, 6, 18, 14) + timedelta(days=14.5))
        assert "FULL MOON" in result["name"]


class TestFibonacciRetracement:
    def test_level_50_persen_di_tengah(self):
        levels, position, nearest = fibonacci_retracement(high=1000.0, low=800.0, current=900.0)
        assert levels["50%"] == pytest.approx(900.0, abs=0.01)

    def test_high_dan_low_level_benar(self):
        levels, position, nearest = fibonacci_retracement(high=1000.0, low=800.0, current=900.0)
        assert levels["0% (High)"] == pytest.approx(1000.0, abs=0.01)
        assert levels["100% (Low)"] == pytest.approx(800.0, abs=0.01)

    def test_position_0_di_low_1_di_high(self):
        _, pos_at_low, _ = fibonacci_retracement(high=1000.0, low=800.0, current=800.0)
        _, pos_at_high, _ = fibonacci_retracement(high=1000.0, low=800.0, current=1000.0)
        assert pos_at_low == pytest.approx(0.0, abs=0.01)
        assert pos_at_high == pytest.approx(1.0, abs=0.01)


class TestExpectedMove:
    def test_expected_move_lebih_besar_jika_volatilitas_lebih_tinggi(self):
        # sigma di sini dalam PERSEN literal (mis. 20 = 20%), sesuai konvensi pemanggilan
        # expected_move() di app.py - bukan desimal (beda dgn black_scholes yang desimal).
        low_vol = expected_move(S=1000.0, sigma=20, days=30)
        high_vol = expected_move(S=1000.0, sigma=60, days=30)
        assert high_vol["move_pct"] > low_vol["move_pct"]

    def test_invalid_input_return_none(self):
        assert expected_move(S=0, sigma=20, days=30) is None
        assert expected_move(S=1000.0, sigma=0, days=30) is None


class TestToCsvExcelId:
    """User: "saya mau download csv langsung ke excel" - CSV standar (koma sbg pemisah
    kolom) TIDAK terbuka rapi kalau langsung di-double-click di Excel locale Indonesia
    (yang pakai titik-koma sbg pemisah, koma sbg desimal) - DITAMBAH banyak kolom tabel
    di app ini sudah diformat jadi teks berkoma ("Rp1,234,567") yang bikin CSV
    ber-koma makin ambigu dipecah Excel. Fix: titik-koma sbg pemisah + BOM UTF-8."""

    def test_pakai_titik_koma_bukan_koma(self):
        df = pd.DataFrame([{"Kode": "AAA", "Harga": 1000, "Nama": "Test"}])
        out = to_csv_excel_id(df)
        text = out.decode("utf-8-sig")
        assert "Kode;Harga;Nama" in text
        assert "AAA;1000;Test" in text

    def test_ada_bom_utf8(self):
        df = pd.DataFrame([{"Kode": "AAA"}])
        out = to_csv_excel_id(df)
        assert out.startswith(b"\xef\xbb\xbf")  # BOM UTF-8

    def test_isi_sel_berkoma_tidak_pecah_kolom(self):
        # Kolom yg sudah diformat teks ber-koma (mis. "Rp1,234,567") - kalau pemisah CSV
        # JUGA koma, Excel akan salah pecah ini jadi 3 kolom. Titik-koma menghindarinya.
        df = pd.DataFrame([{"Kode": "AAA", "Harga": "Rp1,234,567"}])
        out = to_csv_excel_id(df)
        text = out.decode("utf-8-sig")
        lines = text.strip().split("\r\n") if "\r\n" in text else text.strip().split("\n")
        assert len(lines[1].split(";")) == 2  # tetap 2 kolom, bukan 4


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
