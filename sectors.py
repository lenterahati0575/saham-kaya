import yfinance as yf
import streamlit as st

SECTOR_MAP = {
    "BBCA": "Keuangan", "BBRI": "Keuangan", "BMRI": "Keuangan", "BBNI": "Keuangan",
    "BBTN": "Keuangan", "BJBR": "Keuangan", "BJTM": "Keuangan", "BTPN": "Keuangan",
    "TLKM": "Telekomunikasi", "EXCL": "Telekomunikasi", "ISAT": "Telekomunikasi", "FREN": "Telekomunikasi",
    "ASII": "Otomotif", "AUTO": "Otomotif", "IMAS": "Otomotif",
    "UNVR": "Konsumen", "INDF": "Konsumen", "ICBP": "Konsumen", "MYOR": "Konsumen",
    "KLBF": "Farmasi", "SIDO": "Farmasi", "KAEF": "Farmasi", "DVLA": "Farmasi",
    "PGAS": "Energi", "PTBA": "Energi", "ITMG": "Energi", "ADRO": "Energi",
    "ANTM": "Pertambangan", "INCO": "Pertambangan", "TINS": "Pertambangan",
    "SMGR": "Properti & Konstruksi", "WSKT": "Properti & Konstruksi", "WIKA": "Properti & Konstruksi",
    "CTRA": "Properti", "PWON": "Properti", "BSDE": "Properti", "SMRA": "Properti",
    "MNCN": "Media", "SCMA": "Media", "EMTK": "Media", "VIVA": "Media",
    "ACES": "Ritel", "AMRT": "Ritel", "MAPI": "Ritel", "MPPA": "Ritel",
    "TBIG": "Infrastruktur", "TOWR": "Infrastruktur", "SRIL": "Tekstil",
    "UNTR": "Alat Berat", "INTP": "Semen", "SMCB": "Semen",
    "GGRM": "Rokok", "HMSP": "Rokok", "WIIM": "Rokok",
}

def fetch_sectors(kodes):
    """Fetch sektor untuk daftar kode saham"""
    result = {}
    for kode in kodes:
        if kode in SECTOR_MAP:
            result[kode] = SECTOR_MAP[kode]
        else:
            try:
                t = yf.Ticker(f"{kode}.JK")
                info = t.info
                sector = info.get("sector", "TIDAK DIKETAHUI")
                if sector:
                    result[kode] = sector
                else:
                    result[kode] = "TIDAK DIKETAHUI"
            except Exception:
                result[kode] = "TIDAK DIKETAHUI"
    return result
