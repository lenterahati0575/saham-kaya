"""
Klasifikasi sektor & status syariah saham - dari data RESMI Bursa Efek Indonesia (kolom
"Sektor" & "Syariah" di tickers_idx.csv, hasil olah dokumen resmi IDX: daftar 962 saham
tercatat + 11 breakdown sektor IDX-IC + Pengumuman BEI ISSI Mei 2026), BUKAN lagi tebakan
dari taksonomi Yahoo Finance (GICS).

Versi sebelumnya fetch sektor live per-saham ke Yahoo Finance (yf.Ticker().info, dipetakan
kata kunci industri Yahoo -> label ala IDX) - lambat (opt-in, cache 7 hari) DAN cuma
pendekatan kasar (GICS ≠ IDX-IC resmi). Sekarang klasifikasinya statis dari tickers_idx.csv
(instan, official, 100% saham tercakup, tanpa fetch tambahan) - fungsi lama dihapus, bukan
disembunyikan, karena strictly digantikan data yang lebih baik.

CATATAN: klasifikasi resmi IDX-IC & keanggotaan ISSI dievaluasi ulang oleh BEI tiap 6 bulan
(Mei & November) - kalau tickers_idx.csv sudah lebih dari ~6 bulan, cek ulang ke idx.co.id.
"""

import pandas as pd

TIDAK_DIKETAHUI = "Tidak Diketahui"

# Ikon per label sektor IDX-IC resmi (11 sektor) - cuma utk tampilan kartu, tidak
# memengaruhi klasifikasi. Sektor di luar daftar ini pakai _DEFAULT_ICON.
_SECTOR_ICON = {
    "Energy": "🛢️", "Basic Materials": "⛏️", "Industrials": "🏭",
    "Consumer Non-Cyclicals": "🧺", "Consumer Cyclicals": "🛍️", "Healthcare": "💊",
    "Financials": "🏦", "Properties & Real Estate": "🏢", "Technology": "💻",
    "Infrastructures": "🏗️", "Transportation & Logistic": "✈️",
}
_DEFAULT_ICON = "📊"


def sector_icon(label: str) -> str:
    return _SECTOR_ICON.get(label, _DEFAULT_ICON)


def sector_performance(table: pd.DataFrame) -> pd.DataFrame:
    """Ringkas performa SEMUA sektor yang muncul di tabel screener (bukan cuma sebagian/
    top-N) - rata-rata "Perubahan %" antar saham per sektor + jumlah saham anggotanya.

    CATATAN JUJUR: ini rata-rata sederhana antar saham (equal-weight), BUKAN cap-weighted
    seperti indeks sektoral resmi IDX-IC - data kapitalisasi pasar (free float weight) per
    saham tidak diikutkan dalam agregasi ini.
    """
    if "Sektor" not in table.columns or table["Sektor"].isna().all():
        return pd.DataFrame()
    df = table.dropna(subset=["Sektor"])
    df = df[df["Sektor"] != TIDAK_DIKETAHUI]
    if df.empty:
        return pd.DataFrame()
    perf = (df.groupby("Sektor")
              .agg(rata_rata=("Perubahan %", "mean"), jumlah_saham=("Kode", "count"))
              .reset_index()
              .sort_values("rata_rata", ascending=False))
    return perf


def syariah_breadth(table: pd.DataFrame) -> pd.DataFrame | None:
    """Ringkas Market Breadth (rata-rata Perubahan %, jumlah naik/turun) dipisah Syariah
    (anggota ISSI resmi) vs Konvensional - supaya kelihatan apakah pergerakan IHSG hari ini
    lebih ditopang saham syariah atau konvensional, bukan cuma angka gabungan yang
    menyembunyikan perbedaan itu."""
    if "Syariah" not in table.columns or table["Syariah"].isna().all():
        return None
    df = table.dropna(subset=["Syariah", "Perubahan %"])
    if df.empty:
        return None
    grp = df.groupby("Syariah").agg(
        rata_rata=("Perubahan %", "mean"),
        naik=("Perubahan %", lambda s: (s > 0).sum()),
        turun=("Perubahan %", lambda s: (s < 0).sum()),
        jumlah_saham=("Kode", "count"),
    ).reset_index()
    grp["Kelompok"] = grp["Syariah"].map({True: "Syariah (ISSI)", False: "Konvensional"})
    return grp[["Kelompok", "rata_rata", "naik", "turun", "jumlah_saham"]]
