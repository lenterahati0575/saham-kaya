import pandas as pd
from datetime import datetime

# In-memory storage
_equity_store = []

def load_equity():
    """Load data equity"""
    if not _equity_store:
        return pd.DataFrame(columns=[
            "Tanggal", "Sekuritas", "Total Equity (Rp)", "Cash (Rp)",
            "Invested (Rp)", "Max Risk/Trade (%)", "Max Position/Stock (%)"
        ])
    return pd.DataFrame(_equity_store)

def total_equity_over_time(df):
    """Agregasi total equity per tanggal"""
    if df.empty:
        return pd.DataFrame(columns=["Tanggal", "Total Equity (Rp)"])
    grouped = df.groupby("Tanggal")["Total Equity (Rp)"].sum().reset_index()
    return grouped

def latest_per_sekuritas(df):
    """Ambil snapshot terbaru per sekuritas"""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["Tanggal"] = pd.to_datetime(df["Tanggal"])
    latest = df.sort_values("Tanggal").groupby("Sekuritas").last().reset_index()
    return latest

def add_equity_snapshot(tanggal, sekuritas, total_equity, cash, invested, max_risk, max_pos):
    """Tambah snapshot equity"""
    _equity_store.append({
        "Tanggal": tanggal,
        "Sekuritas": sekuritas,
        "Total Equity (Rp)": total_equity,
        "Cash (Rp)": cash,
        "Invested (Rp)": invested,
        "Max Risk/Trade (%)": max_risk,
        "Max Position/Stock (%)": max_pos,
    })
    return True, f"Snapshot {sekuritas} @ {tanggal} tersimpan"

def delete_equity_row(tanggal, sekuritas):
    """Hapus snapshot equity"""
    global _equity_store
    original_len = len(_equity_store)
    _equity_store = [
        e for e in _equity_store
        if not (e["Tanggal"] == tanggal and e["Sekuritas"] == sekuritas)
    ]
    if len(_equity_store) < original_len:
        return True, f"Snapshot {sekuritas} @ {tanggal} dihapus"
    return False, "Data tidak ditemukan"
