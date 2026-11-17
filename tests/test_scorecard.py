"""Mode Pemulihan (screener.market_regime_pemulihan) + Papan Skor (scorecard.py) - data sintetis, tanpa jaringan."""
import numpy as np
import pandas as pd

from scorecard import (label_regime_series, papan_skor, regime_saat_entry, ringkas, status_data, tutup_saja, wilson)
from screener import (FAKTOR_UKURAN_PEMULIHAN, MAKS_POSISI_BARU_PEMULIHAN, REBOUND_PEMULIHAN_PCT, TIPE_SWING_PEMULIHAN,
                      market_regime_pemulihan)


def _ihsg():
    naik = np.linspace(6000, 7000, 70)                      # idx 0-69  : bullish
    turun = np.linspace(6950, 5000, 20)                     # idx 70-89 : jatuh (idx 89 = 5000 = dasar)
    pulih = 5000 + 50 * np.arange(1, 11)                    # idx 90-99 : 5050 ... 5500
    close = np.concatenate([naik, turun, pulih])
    idx = pd.bdate_range("2026-01-05", periods=len(close))
    return pd.Series(close, index=idx)


class TestMarketRegimePemulihan:
    def test_konstanta_uji_coba_terkendali(self):
        assert REBOUND_PEMULIHAN_PCT == 8.0 and FAKTOR_UKURAN_PEMULIHAN == 0.5 and MAKS_POSISI_BARU_PEMULIHAN == 2
        assert TIPE_SWING_PEMULIHAN == "SWING-PEMULIHAN"

    def test_bullish_bearish_pemulihan(self):
        s = _ihsg()
        df = lambda n: pd.DataFrame({"Close": s.iloc[:n]})
        assert market_regime_pemulihan(df(60))["status"] == "BULLISH"
        b = market_regime_pemulihan(df(90))                     # tepat di dasar, rebound 0%
        assert b["status"] == "BEARISH" and b["rebound_pct"] == 0.0
        p = market_regime_pemulihan(df(100))                    # 5500 vs dasar 5000 = +10%, masih < MA50
        assert p["status"] == "PEMULIHAN" and p["rebound_pct"] == 10.0 and p["low20"] == 5000.0 and p["close"] < p["ma"]

    def test_ambang_rebound_dan_data_kurang(self):
        s = _ihsg()
        # idx 96 (5350 = +7,0%) belum cukup; idx 97 (5400 = +8,0%) persis ambang -> pemulihan
        assert market_regime_pemulihan(pd.DataFrame({"Close": s.iloc[:97]}))["status"] == "BEARISH"
        assert market_regime_pemulihan(pd.DataFrame({"Close": s.iloc[:98]}))["status"] == "PEMULIHAN"
        assert market_regime_pemulihan(pd.DataFrame({"Close": s.iloc[:20]}))["status"] == "UNKNOWN"


class TestScorecard:
    def test_label_regime_series(self):
        lab = label_regime_series(_ihsg())
        assert lab.iloc[60] == "BULLISH" and lab.iloc[89] == "BEARISH" and lab.iloc[99] == "PEMULIHAN"
        assert lab.iloc[10] == "TANPA DATA"                      # MA50 belum terhitung

    def test_regime_saat_entry_tanpa_lookahead(self):
        s = _ihsg(); lab = label_regime_series(s)
        # entri di tanggal idx 97: regime yg dipakai = label idx 96 (BEARISH), BUKAN idx 97 (PEMULIHAN)
        assert regime_saat_entry(lab, [s.index[97], s.index[98], s.index[60]]) == ["BEARISH", "PEMULIHAN", "BULLISH"]
        assert regime_saat_entry(lab, ["bukan tanggal", None]) == ["TANPA DATA", "TANPA DATA"]
        assert regime_saat_entry(lab, [s.index[-1] + pd.Timedelta(days=3)]) == ["PEMULIHAN"]   # sesudah data terakhir

    def test_wilson_dan_status(self):
        lo, hi = wilson(6, 10)
        assert 0.30 < lo < 0.33 and 0.82 < hi < 0.85           # 60% dari 10 trade: CI sangat lebar (~31% - 83%)
        assert all(np.isnan(x) for x in wilson(0, 0))
        assert status_data(0) == "Belum ada data" and status_data(12) == "Belum cukup (12/30 trade)" and status_data(30) == "Cukup utk dinilai"

    def test_ringkas_dan_tutup_saja(self):
        df = pd.DataFrame({"Status": ["WIN (TP)", "LOSS (SL)", "WIN (PARTIAL LOCK)", "FORCE SELL (15 hari)", "OPEN", "LOSS (SL)"],
                           "P&L (%)": [10.0, -5.0, 2.0, -1.0, None, "bukan angka"],
                           "P&L (Rp)": [100.0, -50.0, 20.0, -10.0, None, None]})
        t = tutup_saja(df)
        assert len(t) == 4                                      # OPEN & P&L tak terbaca dibuang
        r = ringkas(t)
        assert r["N"] == 4 and r["Menang"] == 2 and r["Win Rate %"] == 50.0
        assert abs(r["Profit Factor"] - 2.0) < 1e-9 and r["Rata2 %"] == 1.5 and r["Terburuk %"] == -5.0
        assert r["Total P&L (Rp)"] == 60.0
        assert ringkas(pd.DataFrame()) == {"N": 0}

    def test_papan_skor_per_sistem_dan_regime(self):
        s = _ihsg()
        a = pd.DataFrame({"Tanggal Open": [s.index[60], s.index[61], s.index[98]], "Status": ["WIN (TP)", "LOSS (SL)", "WIN (PARTIAL LOCK)"],
                          "P&L (%)": [8.0, -4.0, 2.5], "P&L (Rp)": [80.0, -40.0, 25.0]})
        b = pd.DataFrame(columns=["Tanggal Open", "Status", "P&L (%)", "P&L (Rp)"])
        out = papan_skor({"Kandidat": a, "Sederhana": b}, s)
        k = out[out["Sistem"] == "Kandidat"].set_index("Regime Entry")
        assert k.loc["SEMUA", "N"] == 3 and k.loc["BULLISH", "N"] == 2 and k.loc["PEMULIHAN", "N"] == 1
        assert "BEARISH" not in k.index and k.loc["SEMUA", "Status Data"] == "Belum cukup (3/30 trade)"
        sd = out[out["Sistem"] == "Sederhana"]
        assert len(sd) == 1 and sd.iloc[0]["N"] == 0 and sd.iloc[0]["Status Data"] == "Belum ada data"
