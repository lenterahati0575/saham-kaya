"""Format tanggal seragam ("18 Dec 2026") utk tampilan tabel + ekspor Excel (.xlsx) asli.

Dibuat 2026-11-17 (user: "semua tanggal bisa diformat seperti ini [18 Dec 2026] dan download langsung excel bukan csv").
- Penyimpanan TETAP ISO (YYYY-MM-DD) - Google Sheets/Jurnal membaca ISO lewat strptime; modul ini HANYA mengubah
  TAMPILAN & isi file Excel, tidak pernah menulis balik ke sumber data.
- Nama bulan Inggris singkat ditulis manual (bukan strftime) supaya tdk bergantung locale server/Windows.
- Excel: tanggal ditulis sbg TANGGAL ASLI (bisa disortir/difilter) dgn format `[$-409]dd mmm yyyy` (kode 409 = en-US,
  memaksa "Dec" walau Excel berbahasa Indonesia). Teks "Rp1,234" / "12.5%" / "2.00x" yg sudah terformat di tabel
  tampilan dikonversi balik ke ANGKA asli + format sel (kalau SEMUA isi kolom cocok), supaya bisa dijumlah di Excel.
"""
import io
import re

import numpy as np
import pandas as pd

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_BULAN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$")
_PLACEHOLDER = {"", "-", "nan", "nat", "none"}
_RE_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_RE_RP = re.compile(r"^Rp\s?(-?\d[\d,]*(?:\.\d+)?)$")
_RE_PCT = re.compile(r"^([+-]?\d[\d,]*(?:\.\d+)?)%$")
_RE_X = re.compile(r"^(\d[\d,]*(?:\.\d+)?)x$")


def format_tanggal(ts, dengan_jam: bool = False) -> str:
    """Timestamp/datetime/date/string ISO -> "18 Dec 2026" (+ " 14:01" bila `dengan_jam`)."""
    t = pd.Timestamp(ts)
    s = f"{t.day:02d} {_BULAN[t.month - 1]} {t.year}"
    return f"{s} {t.hour:02d}:{t.minute:02d}" if dengan_jam else s


def _teks_atau_objek(s: pd.Series) -> bool:
    """dtype object (pandas 2) ATAU string (pandas 3 memakai dtype 'str' utk kolom teks)."""
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _is_placeholder(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or (isinstance(v, str) and v.strip().lower() in _PLACEHOLDER)


def _parse_tanggal(s: pd.Series):
    """Series -> Series datetime (NaT utk kosong/placeholder) bila SEMUA isi non-kosong berupa tanggal (datetime64,
    objek datetime/date, atau string ISO); selain itu None. Kolom angka/teks biasa TIDAK disentuh."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    if not _teks_atau_objek(s):
        return None
    nonnull = [v for v in s if not _is_placeholder(v)]
    if not nonnull:
        return None
    for v in nonnull:
        if isinstance(v, str):
            if not _RE_ISO.match(v.strip()):
                return None
        elif not isinstance(v, (pd.Timestamp, np.datetime64)) and not hasattr(v, "year"):
            return None
    parsed = pd.Series([pd.NaT if _is_placeholder(v) else pd.Timestamp(v.strip() if isinstance(v, str) else v) for v in s],
                       index=s.index)
    return pd.to_datetime(parsed, errors="coerce")


def _ada_jam(parsed: pd.Series) -> bool:
    p = parsed.dropna()
    if p.empty:
        return False
    return bool((p != p.dt.normalize()).any())


def format_tanggal_df(df: pd.DataFrame) -> pd.DataFrame:
    """Salinan `df` dgn SEMUA kolom tanggal (datetime atau string ISO) diubah jadi teks "18 Dec 2026". Kolom lain utuh."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for i in range(out.shape[1]):
        s = out.iloc[:, i]
        parsed = _parse_tanggal(s)
        if parsed is None:
            continue
        jam = _ada_jam(parsed)
        vals = [format_tanggal(t, jam) if pd.notna(t) else ("-" if isinstance(o, str) else "") for t, o in zip(parsed, s)]
        out.isetitem(i, vals)
    return out


def format_tanggal_styler(styler):
    """Sama utk pandas Styler: format TAMPILAN kolom tanggal lewat Styler.format (data & gaya warna tidak diubah)."""
    df = styler.data
    if df is None or df.empty or df.columns.has_duplicates:
        return styler
    for i, col in enumerate(df.columns):
        parsed = _parse_tanggal(df.iloc[:, i])
        if parsed is None:
            continue
        jam = _ada_jam(parsed)

        def _f(v, jam=jam):
            if _is_placeholder(v):
                return "-" if isinstance(v, str) else ""
            try:
                return format_tanggal(v.strip() if isinstance(v, str) else v, jam)
            except Exception:
                return str(v)
        styler = styler.format(_f, subset=pd.IndexSlice[:, [col]])
    return styler


def _coba_angka(s: pd.Series):
    """Kolom teks terformat ("Rp1,234", "+5.20%", "2.00x") -> (list nilai angka/None, number_format) kalau SEMUA isi
    non-placeholder cocok SATU pola yg sama; selain itu None."""
    if not _teks_atau_objek(s):
        return None
    nonnull = [v.strip() for v in s if isinstance(v, str) and not _is_placeholder(v)]
    if not nonnull or len([v for v in s if not _is_placeholder(v)]) != len(nonnull):
        return None
    for rx, fmt, bagi in ((_RE_RP, '"Rp"#,##0', 1.0), (_RE_PCT, "0.00%", 100.0), (_RE_X, '0.00"x"', 1.0)):
        if all(rx.match(v) for v in nonnull):
            hasil = []
            for v in s:
                if _is_placeholder(v):
                    hasil.append(None)
                else:
                    angka = float(rx.match(v.strip()).group(1).replace(",", "")) / bagi
                    hasil.append(angka)
            return hasil, fmt
    return None


def _nama_sheet(nama: str) -> str:
    bersih = re.sub(r"[\\/*?:\[\]]", " ", str(nama)).strip() or "Data"
    return bersih[:31]


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """DataFrame -> berkas .xlsx (bytes) utk st.download_button: header tebal+beku, filter otomatis, lebar kolom
    menyesuaikan, tanggal = tanggal asli berformat 18 Dec 2026, angka asli (ribuan dipisah), teks terformat Rp/%/x
    dikembalikan jadi angka. Pengganti to_csv_excel_id()."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = _nama_sheet(sheet_name)
    df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
    n_kol = df.shape[1]
    ws.append([_RE_ILLEGAL.sub("", str(c)) for c in df.columns])
    for c in range(1, n_kol + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    lebar = [len(str(c)) + 2 for c in df.columns]
    for i in range(n_kol):
        s = df.iloc[:, i]
        parsed = _parse_tanggal(s)
        if parsed is not None and getattr(parsed.dt, "tz", None) is not None:
            parsed = parsed.dt.tz_localize(None)      # Excel tidak mendukung zona waktu
        angka = None if parsed is not None else _coba_angka(s)
        if parsed is not None:
            fmt = "[$-409]dd mmm yyyy hh:mm" if _ada_jam(parsed) else "[$-409]dd mmm yyyy"
            nilai = [(None if pd.isna(t) else t.to_pydatetime()) for t in parsed]
            lebar[i] = max(lebar[i], 18 if "hh" in fmt else 13)
        elif angka is not None:
            nilai, fmt = angka
            lebar[i] = max(lebar[i], 14)
        else:
            fmt = None
            nilai = []
            semua_int = pd.api.types.is_integer_dtype(s)
            for v in s:
                if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
                    nilai.append(None)
                elif isinstance(v, (bool, np.bool_)):
                    nilai.append(bool(v))
                elif isinstance(v, (int, np.integer)):
                    nilai.append(int(v))
                elif isinstance(v, (float, np.floating)):
                    nilai.append(float(v))
                else:
                    t = _RE_ILLEGAL.sub("", str(v))[:32000]
                    nilai.append(t)
                    lebar[i] = max(lebar[i], min(len(t) + 2, 50))
            if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                fl = [v for v in nilai if isinstance(v, float)]
                fmt = "#,##0" if (semua_int or (fl and all(float(x).is_integer() for x in fl))) else "#,##0.00"
                lebar[i] = max(lebar[i], 12)
        for r, v in enumerate(nilai, start=2):
            cell = ws.cell(row=r, column=i + 1, value=v)
            if fmt and v is not None:
                cell.number_format = fmt
    for i, w in enumerate(lebar, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(w, 50)
    ws.freeze_panes = "A2"
    if n_kol and len(df):
        ws.auto_filter.ref = f"A1:{get_column_letter(n_kol)}{len(df) + 1}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
