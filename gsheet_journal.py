import streamlit as st
import pandas as pd
from datetime import datetime

# In-memory storage untuk demo (tanpa Google Sheets)
_positions_store = []

def is_configured():
    """Cek apakah Google Sheets sudah dikonfigurasi"""
    try:
        return bool(st.secrets.get("GOOGLE_SHEET_ID", ""))
    except Exception:
        return False

def load_positions():
    """Load posisi dari storage"""
    if _positions_store:
        return pd.DataFrame(_positions_store)
    return pd.DataFrame(columns=[
        "No", "Saham", "Harga Beli", "Harga Jual", "Lot", "P&L (Rp)", "P&L (%)",
        "TP", "SL", "Tipe", "Tanggal Open", "Tanggal Close", "Status"
    ])

def open_positions_from_candidates(cands, tipe):
    """Buka posisi dari kandidat"""
    opened = []
    for _, row in cands.iterrows():
        no = len(_positions_store) + 1
        _positions_store.append({
            "No": no,
            "Saham": row["Saham"],
            "Harga Beli": row["Entry"],
            "Harga Jual": 0,
            "Lot": 10,
            "P&L (Rp)": 0,
            "P&L (%)": 0,
            "TP": row["Target"],
            "SL": row["Stop Loss"],
            "Tipe": tipe,
            "Tanggal Open": datetime.now().strftime("%Y-%m-%d"),
            "Tanggal Close": "",
            "Status": "OPEN",
        })
        opened.append(row["Saham"])
    return opened

def auto_close_positions(price_lookup):
    """Auto-close posisi yang kena TP/SL"""
    closed = []
    for pos in _positions_store:
        if pos["Status"] != "OPEN":
            continue
        saham = pos["Saham"]
        current = price_lookup.get(saham, 0)
        if current <= 0:
            continue
        if current >= pos["TP"]:
            pos["Status"] = "CLOSE"
            pos["Harga Jual"] = current
            pos["P&L (Rp)"] = (current - pos["Harga Beli"]) * pos["Lot"] * 100
            pos["P&L (%)"] = ((current / pos["Harga Beli"]) - 1) * 100
            pos["Tanggal Close"] = datetime.now().strftime("%Y-%m-%d")
            closed.append(f"{saham} (TP)")
        elif current <= pos["SL"]:
            pos["Status"] = "CLOSE"
            pos["Harga Jual"] = current
            pos["P&L (Rp)"] = (current - pos["Harga Beli"]) * pos["Lot"] * 100
            pos["P&L (%)"] = ((current / pos["Harga Beli"]) - 1) * 100
            pos["Tanggal Close"] = datetime.now().strftime("%Y-%m-%d")
            closed.append(f"{saham} (SL)")
    return closed

def summarize(positions):
    """Ringkasan statistik posisi"""
    if positions.empty:
        return {"total": 0, "open": 0, "win": 0, "loss": 0, "winrate": 0.0}
    total = len(positions)
    open_count = len(positions[positions["Status"] == "OPEN"])
    win = len(positions[positions["P&L (Rp)"] > 0])
    loss = len(positions[positions["P&L (Rp)"] < 0])
    closed = total - open_count
    winrate = (win / closed * 100) if closed > 0 else 0
    return {"total": total, "open": open_count, "win": win, "loss": loss, "winrate": winrate}

def delete_equity_row(tgl, sek):
    return True, "Deleted"
