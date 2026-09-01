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
                         tanggal_open="2026-07-20 10:00", sl_awal=None, harga_puncak=None):
    row = {
        "Tanggal Open": tanggal_open, "Saham": kode, "Harga Beli": harga_beli, "TP": tp,
        "SL": sl, "Lot": lot, "Tanggal Close": "", "Harga Jual": "",
        "P&L (Rp)": "", "P&L (%)": "", "Status": "OPEN",
        "SL Awal": sl_awal if sl_awal is not None else sl,
    }
    # "Harga Puncak" SENGAJA diomit kalau tidak diberi (bukan diisi harga_beli) - supaya
    # test lama tanpa parameter ini tetap menguji jalur fallback (kolom belum ada di baris
    # lama/pre-migrasi) di auto_close_positions().
    if harga_puncak is not None:
        row["Harga Puncak"] = harga_puncak
    return pd.DataFrame([row])


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

    def test_tipe_sinyal_direkam_kolom_m(self):
        # "Tipe Sinyal" dari build_simple_candidates() direkam di kolom M (index 12) -
        # kolom yg tetap ada walau screener sekarang cuma 1 jalur ('Breakout'), fungsi
        # jurnal ini sengaja generik (rekam apapun nilainya) - dites pakai string bebas.
        candidates = pd.DataFrame([{"Saham": "ZZZZ", "Entry": 100.0, "Target": 150.0,
                                     "Stop Loss": 90.0, "Lot": 10, "Tipe Sinyal": "Breakout"}])
        ws = _mock_ws()
        with patch.object(sj, "_get_worksheet", return_value=ws), \
             patch.object(sj, "load_positions", return_value=pd.DataFrame(columns=sj.HEADERS)):
            sj.open_positions_from_candidates(candidates)
        appended = ws.append_row.call_args[0][0]
        assert appended[12] == "Breakout"

    def test_tipe_sinyal_default_breakout_kalau_kolom_tidak_ada(self):
        # Backward-compat: kandidat lama/test tanpa kolom "Tipe Sinyal" tidak boleh crash.
        candidates = pd.DataFrame([{"Saham": "ZZZZ", "Entry": 100.0, "Target": 150.0, "Stop Loss": 90.0}])
        ws = _mock_ws()
        with patch.object(sj, "_get_worksheet", return_value=ws), \
             patch.object(sj, "load_positions", return_value=pd.DataFrame(columns=sj.HEADERS)):
            sj.open_positions_from_candidates(candidates)
        appended = ws.append_row.call_args[0][0]
        assert appended[12] == "Breakout"

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
        # High hari ini (108) jadi puncak baru juga (dari fallback 100) - 2 ws.update: SL & Harga Puncak.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 108.0}, {"ZZZZ": (108.0, 105.0)})
        assert closed == []
        ws.update.assert_any_call("E2", [[105.0]])
        ws.update.assert_any_call("N2", [[108.0]])
        assert ws.update.call_count == 2

    def test_belum_trigger_kalau_profit_di_bawah_0_7r(self):
        # SL tidak digeser (belum 0.7R), TAPI Harga Puncak tetap direkam (High hari ini 106
        # > fallback 100) - drawdown dari puncak baru (106->105) cuma 0,94%, di bawah
        # SELL_DRAWDOWN_PCT jadi Sinyal Jual Dini juga belum menyala.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 105.0}, {"ZZZZ": (106.0, 103.0)})
        assert closed == []
        ws.update.assert_called_once_with("N2", [[106.0]])

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
        # High hari ini (155) juga jadi puncak baru drawdown-nya (155->152=1,9%, di bawah 5%)
        # jadi Sinyal Jual Dini belum menyala, tapi Harga Puncak tetap direkam.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 152.0}, {"ZZZZ": (155.0, 148.0)})
        assert closed == []
        ws.update.assert_any_call("E2", [[145.0]])
        ws.update.assert_any_call("N2", [[155.0]])
        assert ws.update.call_count == 2

    def test_target_tersentuh_dari_partial_locked_menggeser_ke_target_lock(self):
        # SL sudah di partial-lock (105) - Target tersentuh, HARUS pindah ke target-lock (145).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=105.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 152.0}, {"ZZZZ": (155.0, 148.0)})
        assert closed == []
        ws.update.assert_any_call("E2", [[145.0]])
        ws.update.assert_any_call("N2", [[155.0]])
        assert ws.update.call_count == 2

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


class TestSinyalJualDini:
    """User: "hari ini muncul sinyal buy, lalu besok...harga turun, tapi masih profit...
    saya tahan tidak jual karena target belum tercapai...akhirnya rugi/nyangkut...apakah
    memungkinkan saham yang sudah pernah masuk screener buy tetap dikawal jika muncul
    sinyal sell...saya belum sampai dilevel prediksi seperti itu." DIUJI (350 saham/3
    tahun, README > "Sinyal Jual Dini"): threshold 5% memperbaiki PF 4,73->5,27, avg
    +7,34%->+8,05%, divalidasi split-half & regime."""

    def test_trigger_kalau_turun_5_persen_dari_puncak_sambil_masih_profit(self):
        # entry=100, puncak sudah 120 (dari hari2 sebelumnya) - harga_live 114 = turun
        # 5% tepat dari 120, & masih > 100 (profit) -> Sinyal Jual Dini.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 114.0}, {"ZZZZ": (116.0, 113.0)})
        assert closed == ["ZZZZ (WIN (SINYAL JUAL DINI))"]
        update_call = [c for c in ws.update.call_args_list if c[0][0].startswith("G")][0]
        assert update_call[0][1][0][1] == 114.0  # exit di harga_live, bukan SL/TP

    def test_belum_trigger_kalau_drawdown_di_bawah_threshold(self):
        # Turun cuma 3% dari puncak 120 (116.4) - di bawah SELL_DRAWDOWN_PCT (5%).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 116.4}, {"ZZZZ": (117.0, 115.0)})
        assert closed == []

    def test_tidak_trigger_kalau_sudah_tidak_profit(self):
        # Turun >=5% dari puncak (120->113), TAPI harga_live (99) sudah DI BAWAH harga
        # beli (100) - bukan lagi "masih profit", jadi Sinyal Jual Dini TIDAK berlaku
        # (biar SL asli yang menentukan, bukan rule ini).
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 99.0}, {"ZZZZ": (101.0, 98.0)})
        assert closed == []

    def test_prioritas_di_atas_partial_lock_dan_target_lock(self):
        # SL sudah di target-lock (145), TAPI drawdown dari puncak (200->188 = 6%) sambil
        # masih profit -> Sinyal Jual Dini tetap menang & exit di harga_live (188), BUKAN
        # menunggu turun lagi ke level target-lock (145) yang jauh lebih rendah.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=145.0,
                                            sl_awal=90.0, harga_puncak=200.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 188.0}, {"ZZZZ": (190.0, 186.0)})
        assert closed == ["ZZZZ (WIN (SINYAL JUAL DINI))"]
        update_call = [c for c in ws.update.call_args_list if c[0][0].startswith("G")][0]
        assert update_call[0][1][0][1] == 188.0

    def test_sl_kena_hari_yang_sama_menang_bukan_jual_dini(self):
        # Low hari ini (89) SUDAH tembus SL (90) - walau Close (114) masih net profit &
        # drawdown dari puncak (120->114=5%) capai threshold, SL yang HARUS menang (konvensi
        # "SL dicek lebih dulu" yang sama dgn seluruh sistem) - BUKAN Sinyal Jual Dini.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 114.0}, {"ZZZZ": (116.0, 89.0)})
        assert closed == ["ZZZZ (LOSS (SL))"]

    def test_puncak_lama_tidak_ada_fallback_ke_harga_beli(self):
        # Posisi lama sebelum kolom "Harga Puncak" ada (kolom tidak diisi sama sekali) -
        # fallback ke Harga Beli (100), BUKAN crash. High hari ini 130 jadi puncak baru,
        # exit 120 = turun 7,7% dari 130, masih > 100 -> Sinyal Jual Dini tetap jalan.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 120.0}, {"ZZZZ": (130.0, 119.0)})
        assert closed == ["ZZZZ (WIN (SINYAL JUAL DINI))"]

    def test_puncak_naik_direkam_ke_kolom_n_saat_posisi_tetap_open(self):
        # High hari ini (106) SENGAJA di bawah trigger partial-lock (107 = 0,7R) supaya
        # HANYA Harga Puncak yang berubah - SL/lapis lain tidak ikut ke-trigger.
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=105.0,
                                            tanggal_open=_tanggal_open_recent())
        ws = _mock_ws()
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet", return_value=ws):
            closed = sj.auto_close_positions({"ZZZZ": 104.0}, {"ZZZZ": (106.0, 103.0)})
        assert closed == []  # drawdown dari puncak baru (106->104=1,9%) di bawah threshold
        ws.update.assert_called_once_with("N2", [[106.0]])


class TestPreviewSinyalJualDini:
    """Preview READ-ONLY - direplikasi dari gsheet_journal.py utk tab '🔬 Screener
    Sederhana' (user: "lakukan juga discreener sederhana")."""

    def test_muncul_kalau_kriteria_terpenuhi(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        with patch.object(sj, "load_positions", return_value=df_positions):
            preview = sj.preview_sinyal_jual_dini({"ZZZZ": 114.0}, {"ZZZZ": (116.0, 113.0)})
        assert list(preview["Kode"]) == ["ZZZZ"]
        assert preview.iloc[0]["Turun dari Puncak (%)"] == 5.0

    def test_kosong_kalau_drawdown_di_bawah_threshold(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        with patch.object(sj, "load_positions", return_value=df_positions):
            preview = sj.preview_sinyal_jual_dini({"ZZZZ": 116.4}, {"ZZZZ": (117.0, 115.0)})
        assert preview.empty

    def test_kosong_kalau_sl_kena_hari_yang_sama(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        with patch.object(sj, "load_positions", return_value=df_positions):
            preview = sj.preview_sinyal_jual_dini({"ZZZZ": 114.0}, {"ZZZZ": (116.0, 89.0)})
        assert preview.empty

    def test_tidak_menulis_apa_pun_ke_sheet(self):
        df_positions = _make_open_position(kode="ZZZZ", harga_beli=100.0, tp=150.0, sl=90.0,
                                            sl_awal=90.0, harga_puncak=120.0,
                                            tanggal_open=_tanggal_open_recent())
        with patch.object(sj, "load_positions", return_value=df_positions), \
             patch.object(sj, "_get_worksheet") as mock_ws_getter:
            sj.preview_sinyal_jual_dini({"ZZZZ": 114.0}, {"ZZZZ": (116.0, 113.0)})
        mock_ws_getter.assert_not_called()


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


class TestGetWorksheetMigrasiHeader:
    """Sheet POSISI_SEDERHANA yang sudah live SEBELUM kolom "Tipe Sinyal" ditambahkan ke
    HEADERS - header row harus dilengkapi otomatis, TANPA user perlu tambah kolom manual
    (SAMA filosofi auto-create yang sudah ada)."""

    def test_header_lama_12_kolom_dilengkapi_otomatis(self):
        from gspread.utils import rowcol_to_a1
        client = MagicMock()
        sh = MagicMock()
        existing_ws = MagicMock()
        # Sheet lama, belum ada "Tipe Sinyal" MAUPUN "Harga Puncak" - keduanya harus
        # dilengkapi sekaligus dlm 1 kali update.
        existing_ws.row_values.return_value = sj.HEADERS[:12]
        sh.worksheet.return_value = existing_ws
        client.open_by_key.return_value = sh
        with patch.object(sj, "_get_client", return_value=client), \
             patch.object(sj.st, "secrets", {"GOOGLE_SHEET_ID": "fake_id"}):
            ws = sj._get_worksheet()
        start_cell = rowcol_to_a1(1, 13)
        end_cell = rowcol_to_a1(1, 14)
        existing_ws.update.assert_called_once_with(
            f"{start_cell}:{end_cell}", [["Tipe Sinyal", "Harga Puncak"]],
            value_input_option="USER_ENTERED")
        assert ws is existing_ws

    def test_header_lama_13_kolom_dilengkapi_harga_puncak_saja(self):
        from gspread.utils import rowcol_to_a1
        client = MagicMock()
        sh = MagicMock()
        existing_ws = MagicMock()
        existing_ws.row_values.return_value = sj.HEADERS[:13]  # sudah ada "Tipe Sinyal", belum "Harga Puncak"
        sh.worksheet.return_value = existing_ws
        client.open_by_key.return_value = sh
        with patch.object(sj, "_get_client", return_value=client), \
             patch.object(sj.st, "secrets", {"GOOGLE_SHEET_ID": "fake_id"}):
            sj._get_worksheet()
        start_cell = rowcol_to_a1(1, 14)
        existing_ws.update.assert_called_once_with(
            f"{start_cell}:{start_cell}", [["Harga Puncak"]], value_input_option="USER_ENTERED")

    def test_header_sudah_lengkap_tidak_diubah(self):
        client = MagicMock()
        sh = MagicMock()
        existing_ws = MagicMock()
        existing_ws.row_values.return_value = list(sj.HEADERS)  # sudah lengkap 13 kolom
        sh.worksheet.return_value = existing_ws
        client.open_by_key.return_value = sh
        with patch.object(sj, "_get_client", return_value=client), \
             patch.object(sj.st, "secrets", {"GOOGLE_SHEET_ID": "fake_id"}):
            sj._get_worksheet()
        existing_ws.update.assert_not_called()


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
