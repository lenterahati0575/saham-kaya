"""
Uji simple_journal.py - jurnal SCREENER SEDERHANA (pembanding), sheet Google Sheets
TERPISAH ("POSISI_SEDERHANA") dari jurnal utama. 2 lapis exit: partial-lock (0,7R->0,5R,
SEBELUM Target) + target-lock (0,5R DI BAWAH Target, SETELAH Target tersentuh).
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import simple_journal as sj


def _tanggal_open_recent(hari_lalu: int = 2) -> str:
    return (datetime.now(sj.WIB) - timedelta(days=hari_lalu)).strftime("%Y-%m-%d %H:%M")


def _tanggal_open_hari_ini(jam: str = "09:00") -> str:
    return datetime.now(sj.WIB).strftime(f"%Y-%m-%d {jam}")


def _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0, lot=10,
                         tanggal_open="2026-07-20 10:00", sl_awal=None):
    return pd.DataFrame([{
        "Tanggal Open": tanggal_open, "Saham": kode, "Harga Beli": harga_beli, "TP": tp,
        "SL": sl, "Lot": lot, "Tanggal Close": "", "Harga Jual": "",
        "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN",
        "SL Awal": sl_awal if sl_awal is not None else sl,
    }])


def _mock_ws():
    ws = MagicMock()
    ws.get_all_values.return_value = [
        ["Tanggal Open", "Saham", "Harga Beli", "TP", "SL", "Lot", "Tanggal Close",
         "Harga Jual", "P&L (Rp)", "P&L (%)", "Status", "SL Awal"],
        ["2026-07-20 10:00", "ZZZZ", "100", "150", "90", "10", "", "", "", "", "OPEN", "90"],
    ]
    return ws


class TestOpenPositionsFromCandidates:
    def test_buka_posisi_dari_kandidat(self):
        candidates = pd.DataFrame([{"Saham": "ZZZZ", "Entry": 100.0, "Target": 150.0, "Stop Loss": 90.0, "Lot": 10}])
        ws = _mock_ws()
        with patch.object(sj, "_get_worksheet", return_value=ws), \
             patch.object(sj, "load_positions", return_value=pd.DataFrame(columns=sj.HEADERS)):
            opened = sj.open_positions_from_candidates(candidates)
        assert opened == ["ZZZZ"]
        appended = ws.append_row.call_args[0][0]
        assert appended[1] == "ZZZZ" and appended[10] == "OPEN" and appended[11] == 90.0

    def test_cooldown_1x_per_hari(self):
        today_wib = datetime.now(sj.WIB).strftime("%Y-%m-%d")
        existing = pd.DataFrame([{
            "Tanggal Open": f"{today_wib} 09:00", "Saham": "ZZZZ", "Harga Beli": 100.0,
            "TP": 150.0, "SL": 90.0, "Lot": 10, "Tanggal Close": f"{today_wib} 10:00",
            "Harga Jual": 90.0, "P&L (Rp)": -1000, "P&L (%)": -1.0, "Status": "LOSS (SL)",
            "SL Awal": 90.0,
        }])
        candidates = pd.DataFrame([{"Saham": "ZZZZ", "Entry": 100.0, "Target": 150.0, "Stop Loss": 90.0}])
        ws = _mock_ws()
        with patch.object(sj, "_get_worksheet", return_value=ws), \
             patch.object(sj, "load_positions", return_value=existing):
            opened = sj.open_positions_from_candidates(candidates)
        assert opened == []
        ws.append_row.assert_not_called()

    def test_max_new_per_day(self):
        candidates = pd.DataFrame([
            {"Saham": f"S{i:03d}", "Entry": 100.0, "Target": 150.0, "Stop Loss": 90.0}
            for i in range(10)
        ])
        ws = _mock_ws()
        with patch.object(sj, "_get_worksheet", return_value=ws), \
             patch.object(sj, "load_positions", return_value=pd.DataFrame(columns=sj.HEADERS)):
            opened = sj.open_positions_from_candidates(candidates, max_new_per_day=3)
        assert len(opened) == 3


class TestSkipCekSamaHariDenganBuka:
    """SAMA bug/fix dgn gsheet_journal.py - posisi yang dibuka HARI INI (tanggal kalender
    sama) di-skip total, exit HANYA dicek mulai hari kalender berikutnya."""

    def test_posisi_dibuka_hari_ini_tidak_dicek(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            tanggal_open=_tanggal_open_hari_ini())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 145.0}, {"ZZZZ": (150.0, 80.0)})
        assert closed == []
        ws.update.assert_not_called()


class TestPartialLockLapis1:
    """Lapis 1 - begitu profit (High) capai 0,7R, SL digeser ke 0,5R (BUKAN breakeven
    penuh) - posisi TETAP OPEN."""

    def test_trigger_0_7r_menggeser_sl_ke_0_5r(self):
        # entry=100, sl_awal=90 -> risk=10. Trigger 0.7R -> High>=107. Lock 0.5R -> SL baru=105.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 108.0}, {"ZZZZ": (108.0, 105.0)})
        assert closed == []
        ws.update.assert_called_once_with("E2", [[105.0]])

    def test_belum_trigger_kalau_profit_di_bawah_0_7r(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (106.0, 103.0)})
        assert closed == []
        ws.update.assert_not_called()

    def test_exit_setelah_partial_locked_dilabel_partial_lock(self):
        # SL sudah digeser ke 105 (partial-lock) - SL Awal tetap 90.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=105.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 104.0}, {"ZZZZ": (106.0, 103.0)})
        assert closed == ["ZZZZ (WIN (PARTIAL LOCK))"]
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 105.0  # exit di level kuncian (105), untung terselamatkan


class TestTargetLockLapis2:
    """Lapis 2 - begitu Target tersentuh, SL digeser ke Target-0,5R (posisi tetap OPEN)."""

    def test_target_tersentuh_dari_belum_locked_menggeser_ke_target_lock(self):
        # entry=100, sl_awal=90, tp=150 -> risk=10. Target-0.5*10 = 145.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 152.0}, {"ZZZZ": (155.0, 148.0)})
        assert closed == []
        ws.update.assert_called_once_with("E2", [[145.0]])

    def test_target_tersentuh_dari_partial_locked_menggeser_ke_target_lock(self):
        # SL sudah di partial-lock (105) - Target tersentuh, HARUS pindah ke target-lock (145).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=105.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 152.0}, {"ZZZZ": (155.0, 148.0)})
        assert closed == []
        ws.update.assert_called_once_with("E2", [[145.0]])

    def test_exit_setelah_target_locked_dilabel_win(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=145.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 144.0}, {"ZZZZ": (147.0, 143.0)})
        assert closed == ["ZZZZ (WIN (TARGET TERKUNCI))"]
        update_call = ws.update.call_args[0][1]
        assert update_call[0][1] == 145.0

    def test_force_sell_setelah_target_locked_dilabel_win(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=145.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent(hari_lalu=16))
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 148.0}, {"ZZZZ": (149.0, 147.0)})
        assert len(closed) == 1
        assert closed[0].startswith("ZZZZ (WIN (FORCE SELL target terkunci")


class TestBelumLocked:
    def test_sl_asli_tersentuh_dilabel_loss(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 88.0}, {"ZZZZ": (95.0, 85.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_force_sell_belum_locked_generik(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent(hari_lalu=16))
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 102.0}, {"ZZZZ": (103.0, 101.0)})
        assert len(closed) == 1
        assert closed[0].startswith("ZZZZ (FORCE SELL")
        assert "target" not in closed[0].lower()


class TestSummarize:
    def test_win_loss_dihitung_benar(self):
        df = pd.DataFrame([
            {"Saham": "AAA", "Status": "WIN (TARGET TERKUNCI)", "P&L (%)": 12.0},
            {"Saham": "BBB", "Status": "LOSS (SL)", "P&L (%)": -5.0},
            {"Saham": "CCC", "Status": "WIN (PARTIAL LOCK)", "P&L (%)": 3.0},
            {"Saham": "DDD", "Status": "OPEN", "P&L (%)": None},
        ])
        stats = sj.summarize(df)
        assert stats["win"] == 2  # TARGET TERKUNCI + PARTIAL LOCK, keduanya berlabel WIN
        assert stats["loss"] == 1
        assert stats["open"] == 1

    def test_dataframe_kosong_tidak_crash(self):
        stats = sj.summarize(pd.DataFrame())
        assert stats["total"] == 0
        assert stats["winrate"] == 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
