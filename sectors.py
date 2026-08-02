"""
Fetch sektor saham dari Yahoo Finance (yf.Ticker().info), lalu diterjemahkan/dipetakan
ke istilah yang lazim dipakai di IDX (mis. "Perbankan", bukan "Financial Services").

CATATAN JUJUR:
- Yahoo Finance pakai taksonomi GICS (bahasa Inggris, kategori global), BUKAN IDX-IC resmi
  (klasifikasi industri resmi Bursa Efek Indonesia). Pemetaan di bawah ini pendekatan praktis
  berdasar kata kunci sektor & industri dari Yahoo, bukan data resmi IDX-IC.
- Fetch sektor per-saham lumayan lambat (beda dengan fetch harga yang bisa di-batch), makanya
  fitur ini dibuat OPT-IN (ada checkbox di sidebar) dan di-cache lama (7 hari) supaya tidak
  perlu fetch ulang tiap buka dashboard.
"""

import concurrent.futures
import pandas as pd
import streamlit as st
import yfinance as yf

# Kata kunci industri Yahoo -> label sektor ala IDX. Dicek berurutan dari atas (lebih spesifik dulu).
_INDUSTRY_KEYWORDS = [
    (("bank",), "Perbankan"),
    (("insurance",), "Asuransi"),
    (("capital markets", "asset management", "financial data"), "Perusahaan Sekuritas & Investasi"),
    (("reit", "real estate",), "Properti & Real Estat"),
    (("coal",), "Batu Bara"),
    (("oil & gas", "oil and gas", "petroleum"), "Minyak & Gas"),
    (("gold", "silver", "copper", "steel", "aluminum", "mining"), "Pertambangan & Logam"),
    (("agricultural", "farm", "plantation", "palm"), "Perkebunan & Agrikultur"),
    (("telecom",), "Telekomunikasi"),
    (("software", "information technology services", "internet"), "Teknologi"),
    (("semiconductor", "electronic"), "Teknologi"),
    (("auto", "vehicle"), "Otomotif"),
    (("airline", "marine", "railroad", "trucking", "logistics"), "Transportasi & Logistik"),
    (("utilit", "electric", "power"), "Utilitas & Energi"),
    (("construction", "engineering", "building materials", "cement"), "Konstruksi & Bahan Bangunan"),
    (("retail", "department store", "specialty retail"), "Ritel"),
    (("food", "beverage", "grocery", "packaged foods"), "Makanan & Minuman"),
    (("tobacco",), "Rokok"),
    (("pharmaceutical", "healthcare", "medical", "drug", "biotechnology", "hospital"), "Kesehatan & Farmasi"),
    (("hotel", "restaurant", "leisure", "travel"), "Pariwisata, Hotel & Restoran"),
    (("media", "entertainment", "publishing"), "Media & Hiburan"),
    (("textile", "apparel", "furnishings"), "Tekstil & Garmen"),
    (("paper", "packaging", "chemicals", "specialty chemicals"), "Kimia & Bahan Dasar"),
    (("conglomerates", "industrial", "machinery"), "Perindustrian"),
]

_SECTOR_FALLBACK = {
    "Financial Services": "Keuangan (Lainnya)",
    "Basic Materials": "Material Dasar",
    "Energy": "Energi",
    "Consumer Cyclical": "Konsumer Siklikal",
    "Consumer Defensive": "Konsumer Non-Siklikal",
    "Healthcare": "Kesehatan & Farmasi",
    "Industrials": "Perindustrian",
    "Real Estate": "Properti & Real Estat",
    "Technology": "Teknologi",
    "Communication Services": "Telekomunikasi & Media",
    "Utilities": "Utilitas & Energi",
}

TIDAK_DIKETAHUI = "Tidak Diketahui"


def _classify(sector: str, industry: str) -> str:
    industry_l = (industry or "").lower()
    for keywords, label in _INDUSTRY_KEYWORDS:
        if any(k in industry_l for k in keywords):
            return label
    return _SECTOR_FALLBACK.get(sector, sector or TIDAK_DIKETAHUI)


def _fetch_one(kode: str) -> tuple[str, str]:
    try:
        info = yf.Ticker(f"{kode}.JK").info
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        return kode, _classify(sector, industry)
    except Exception:
        return kode, TIDAK_DIKETAHUI


@st.cache_data(ttl=604800, show_spinner=False)  # cache 7 hari - sektor jarang berubah
def fetch_sectors(tickers: list[str], max_workers: int = 20) -> dict[str, str]:
    """Fetch sektor untuk daftar ticker secara paralel (thread pool, karena yf.Ticker().info
    lambat kalau dipanggil satu-satu berurutan). Hasil di-cache 7 hari."""
    results: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in concurrent.futures.as_completed(futures):
            kode, sektor = future.result()
            results[kode] = sektor
    return results
