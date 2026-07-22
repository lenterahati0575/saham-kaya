"""Unit test untuk indicators.py - RSI/MA/Swing point pakai data sintetis."""

import numpy as np
import pandas as pd
import pytest

from indicators import moving_averages_panel, technical_indicators_panel, _rsi, find_swing_points


def _trending_ohlc(n=250, start=1000, step=2):
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    close = start + np.arange(n) * step
    df = pd.DataFrame({
        "Open": close, "High": close + 5, "Low": close - 5, "Close": close,
        "Volume": 1_000_000,
    }, index=idx)
    return df


class TestRSI:
    def test_rsi_uptrend_kuat_di_atas_50(self):
        close = pd.Series(np.arange(1000, 1000 + 30 * 5, 5))  # naik terus
        rsi = _rsi(close)
        assert rsi.iloc[-1] > 70

    def test_rsi_downtrend_kuat_di_bawah_50(self):
        close = pd.Series(np.arange(1000, 1000 - 30 * 5, -5))
        rsi = _rsi(close)
        assert rsi.iloc[-1] < 30


class TestMovingAveragesPanel:
    def test_uptrend_mayoritas_buy(self):
        df = _trending_ohlc(n=250, step=3)
        table, summary = moving_averages_panel(df)
        assert summary["overall"] == "Buy"
        assert summary["buy"] > summary["sell"]

    def test_downtrend_mayoritas_sell(self):
        df = _trending_ohlc(n=250, step=-3)
        table, summary = moving_averages_panel(df)
        assert summary["overall"] == "Sell"


class TestTechnicalIndicatorsPanel:
    def test_return_shape(self):
        df = _trending_ohlc(n=100, step=2)
        table, summary = technical_indicators_panel(df)
        assert len(table) == 8  # RSI, STOCH, STOCHRSI, MACD, ADX, CCI, UO, Williams%R
        assert summary["overall"] in ("Buy", "Sell", "Neutral")


class TestSwingPoints:
    def test_deteksi_swing_pada_pola_zigzag(self):
        # Bentuk pola naik-turun jelas supaya swing high/low mudah terdeteksi
        vals = [100, 105, 110, 105, 100, 95, 90, 95, 100, 105, 110, 108, 105]
        idx = pd.date_range("2024-01-01", periods=len(vals), freq="B")
        df = pd.DataFrame({"Open": vals, "High": vals, "Low": vals, "Close": vals,
                            "Volume": 1_000_000}, index=idx)
        highs, lows = find_swing_points(df, order=2)
        assert len(highs) >= 1
        assert len(lows) >= 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
