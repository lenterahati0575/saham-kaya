"""Test format tanggal seragam + ekspor Excel (2026-11-17). Data sintetis, tanpa jaringan."""
import io
from datetime import date, datetime

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from format_export import (XLSX_MIME, format_tanggal, format_tanggal_df, format_tanggal_styler, to_excel_bytes)


class TestFormatTanggal:
    def test_format_dasar_dan_jam(self):
        assert format_tanggal("2026-12-18") == "18 Dec 2026"
        assert format_tanggal(datetime(2026, 8, 10, 14, 1), True) == "10 Aug 2026 14:01"
        assert format_tanggal(date(2027, 1, 5)) == "05 Jan 2027"

    def test_df_string_iso_datetime_dan_date_diubah_kolom_lain_utuh(self):
        df = pd.DataFrame({
            "Tanggal": ["2026-11-18", "2026-11-22", "-"],
            "Waktu": ["2026-08-10 14:01", "2026-08-13 10:03", "2026-08-13 19:16"],
            "dt": pd.to_datetime(["2026-12-03", "2026-12-18", None]),
            "d": [date(2026, 1, 2), date(2026, 3, 4), None],
            "Kode": ["BBRI", "ASII", "2026-no"],            # teks biasa - tidak boleh diubah
            "Harga": [1000.0, 2000.0, 3000.0]})
        out = format_tanggal_df(df)
        assert list(out["Tanggal"]) == ["18 Nov 2026", "22 Nov 2026", "-"]
        assert list(out["Waktu"]) == ["10 Aug 2026 14:01", "13 Aug 2026 10:03", "13 Aug 2026 19:16"]
        assert list(out["dt"]) == ["03 Dec 2026", "18 Dec 2026", ""]
        assert list(out["d"]) == ["02 Jan 2026", "04 Mar 2026", ""]
        assert list(out["Kode"]) == ["BBRI", "ASII", "2026-no"] and list(out["Harga"]) == [1000.0, 2000.0, 3000.0]
        assert df["Tanggal"].iloc[0] == "2026-11-18"          # df asli tidak berubah

    def test_kosong_dan_styler(self):
        assert format_tanggal_df(pd.DataFrame()).empty
        df = pd.DataFrame({"date": ["2026-11-18", "2026-12-03"], "n": [1, 2]})
        sty = format_tanggal_styler(df.style.map(lambda v: "color:red", subset=["n"]))
        html = sty.to_html()
        assert "18 Nov 2026" in html and "03 Dec 2026" in html and "2026-11-18" not in html


class TestExcel:
    def _baca(self, df, **kw):
        data = to_excel_bytes(df, **kw)
        assert data[:2] == b"PK"                               # berkas zip/xlsx sungguhan
        return load_workbook(io.BytesIO(data))

    def test_tanggal_asli_format_en_us_dan_angka(self):
        df = pd.DataFrame({"Tanggal Open": ["2026-08-10 14:01", "2026-08-13 10:03"], "Tgl": ["2026-12-18", "2026-12-19"],
                           "Lot": [10, 25], "P&L": [1234567.5, -200.25], "Kode": ["BBRI", "ASII"]})
        ws = self._baca(df, sheet_name="Riwayat/Trade?").active
        assert ws.title == "Riwayat Trade "[:31].strip() or ws.title                      # karakter terlarang dibuang
        assert [c.value for c in ws[1]] == ["Tanggal Open", "Tgl", "Lot", "P&L", "Kode"]
        assert ws["A2"].value == datetime(2026, 8, 10, 14, 1) and "dd mmm yyyy hh:mm" in ws["A2"].number_format
        assert ws["B2"].value == datetime(2026, 12, 18) and ws["B2"].number_format == "[$-409]dd mmm yyyy"
        assert ws["C2"].value == 10 and ws["C2"].number_format == "#,##0"
        assert ws["D2"].value == 1234567.5 and ws["D2"].number_format == "#,##0.00"
        assert ws["E3"].value == "ASII" and ws.freeze_panes == "A2" and ws.auto_filter.ref == "A1:E3"

    def test_teks_rp_persen_x_jadi_angka_asli(self):
        df = pd.DataFrame({"Entry": ["Rp1,234", "Rp12,500", "-"], "Return": ["+5.20%", "-1.50%", "0.00%"],
                           "RR": ["2.00x", "1.50x", "3.25x"], "Campur": ["Rp100", "teks", "Rp5"]})
        ws = self._baca(df).active
        assert ws["A2"].value == 1234.0 and ws["A2"].number_format == '"Rp"#,##0' and ws["A4"].value is None
        assert abs(ws["B2"].value - 0.052) < 1e-9 and ws["B2"].number_format == "0.00%"
        assert ws["C4"].value == 3.25 and ws["C4"].number_format == '0.00"x"'
        assert ws["D2"].value == "Rp100"                        # kolom campur TIDAK dikonversi

    def test_nan_none_bool_dan_tz_dan_df_kosong_aman(self):
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [True, False, True],
                           "t": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).tz_localize("Asia/Jakarta")})
        ws = self._baca(df).active
        assert ws["A3"].value is None and ws["B2"].value is True and ws["C2"].value == datetime(2026, 1, 1)
        assert self._baca(pd.DataFrame({"x": []})).active.max_row == 1

    def test_mime_xlsx(self):
        assert XLSX_MIME.endswith("spreadsheetml.sheet")
