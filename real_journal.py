import pandas as pd
from datetime import datetime

# In-memory storage
_trades_store = []
_brokers_store = [
    {"Sekuritas": "Mirae Asset Sekuritas", "Biaya Beli (%)": 0.15, "Biaya Jual (%)": 0.25},
    {"Sekuritas": "Ajaib Sekuritas", "Biaya Beli (%)": 0.15, "Biaya Jual (%)": 0.25},
    {"Sekuritas": "Stockbit Sekuritas", "Biaya Beli (%)": 0.15, "Biaya Jual (%)": 0.25},
    {"Sekuritas": "IPOT (Indo Premier)", "Biaya Beli (%)": 0.18, "Biaya Jual (%)": 0.28},
    {"Sekuritas": "Lainnya", "Biaya Beli (%)": 0.18, "Biaya Jual (%)": 0.28},
]

SETUP_OPTIONS = [
    "Breakout", "Pullback", "Trend Following", "Mean Reversion",
    "Support Bounce", "Resistance Break", "Gap Up", "Gap Down",
    "Volume Spike", "News Driven", "Earnings Play", "Dividend Capture",
    "Swing Trade", "Day Trade", "Scalping", "Custom"
]

def load_brokers():
    """Load daftar sekuritas"""
    return pd.DataFrame(_brokers_store)

def load_trades():
    """Load semua trade"""
    if not _trades_store:
        return pd.DataFrame(columns=[
            "No", "Tanggal Entry", "Sekuritas", "Saham", "Setup",
            "Entry (Rp)", "Stop Loss (Rp)", "Target (Rp)", "Lot",
            "Catatan", "Tanggal Exit", "Exit (Rp)", "Status",
            "P/L (Rp)", "P/L (%)", "Net P/L"
        ])
    return pd.DataFrame(_trades_store)

def open_trade(tgl_entry, sekuritas, saham, setup, entry, sl, target, lot, catatan):
    """Buka trade baru"""
    no = len(_trades_store) + 1
    _trades_store.append({
        "No": no,
        "Tanggal Entry": tgl_entry,
        "Sekuritas": sekuritas,
        "Saham": saham,
        "Setup": setup,
        "Entry (Rp)": entry,
        "Stop Loss (Rp)": sl,
        "Target (Rp)": target,
        "Lot": lot,
        "Catatan": catatan,
        "Tanggal Exit": "",
        "Exit (Rp)": 0,
        "Status": "OPEN",
        "P/L (Rp)": 0,
        "P/L (%)": 0,
        "Net P/L": 0,
    })
    return no

def close_trade(no, tgl_exit, exit_price):
    """Tutup trade"""
    for trade in _trades_store:
        if trade["No"] == no:
            trade["Tanggal Exit"] = tgl_exit
            trade["Exit (Rp)"] = exit_price
            trade["Status"] = "CLOSE"
            entry = trade["Entry (Rp)"]
            lot = trade["Lot"]
            pl = (exit_price - entry) * lot * 100
            pl_pct = ((exit_price / entry) - 1) * 100 if entry > 0 else 0
            trade["P/L (Rp)"] = pl
            trade["P/L (%)"] = pl_pct
            trade["Net P/L"] = pl
            return True, f"Trade #{no} ditutup @ Rp{exit_price:,.0f}"
    return False, f"Trade #{no} tidak ditemukan"

def compute_stats(trades):
    """Hitung statistik trading"""
    if trades.empty:
        return {
            "total": 0, "win": 0, "loss": 0, "open": 0,
            "winrate": 0.0, "profit_factor": 0.0,
            "total_transaction_value": 0, "net_pl": 0,
        }

    total = len(trades)
    win = len(trades[trades["P/L (Rp)"] > 0])
    loss = len(trades[trades["P/L (Rp)"] < 0])
    open_count = len(trades[trades["Status"] == "OPEN"])
    winrate = (win / (total - open_count) * 100) if (total - open_count) > 0 else 0

    gross_profit = trades[trades["P/L (Rp)"] > 0]["P/L (Rp)"].sum() if win > 0 else 0
    gross_loss = abs(trades[trades["P/L (Rp)"] < 0]["P/L (Rp)"].sum()) if loss > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    net_pl = trades["P/L (Rp)"].sum()
    total_tv = (trades["Entry (Rp)"] * trades["Lot"] * 100).sum()

    return {
        "total": total, "win": win, "loss": loss, "open": open_count,
        "winrate": winrate, "profit_factor": pf,
        "total_transaction_value": total_tv, "net_pl": net_pl,
    }

def performance_by_broker(trades):
    """Performance per sekuritas"""
    if trades.empty:
        return pd.DataFrame()
    grouped = trades.groupby("Sekuritas").agg({
        "P/L (Rp)": ["sum", "count"],
        "No": "count"
    }).reset_index()
    grouped.columns = ["Sekuritas", "Total P/L", "Count", "Trades"]
    return grouped

def performance_by_setup(trades):
    """Performance per setup"""
    if trades.empty:
        return pd.DataFrame()
    grouped = trades.groupby("Setup").agg({
        "P/L (Rp)": ["sum", "count"],
    }).reset_index()
    grouped.columns = ["Setup", "Total P/L", "Count"]
    return grouped

def edit_trade(no, tgl_entry, sekuritas, saham, setup, entry, sl, target, lot, catatan, tanggal_exit="", exit_price=None):
    """Edit trade"""
    for trade in _trades_store:
        if trade["No"] == no:
            trade["Tanggal Entry"] = tgl_entry
            trade["Sekuritas"] = sekuritas
            trade["Saham"] = saham
            trade["Setup"] = setup
            trade["Entry (Rp)"] = entry
            trade["Stop Loss (Rp)"] = sl
            trade["Target (Rp)"] = target
            trade["Lot"] = lot
            trade["Catatan"] = catatan
            if tanggal_exit:
                trade["Tanggal Exit"] = tanggal_exit
            if exit_price and exit_price > 0:
                trade["Exit (Rp)"] = exit_price
                trade["Status"] = "CLOSE"
                pl = (exit_price - entry) * lot * 100
                trade["P/L (Rp)"] = pl
                trade["P/L (%)"] = ((exit_price / entry) - 1) * 100 if entry > 0 else 0
                trade["Net P/L"] = pl
            return True, f"Trade #{no} diupdate"
    return False, f"Trade #{no} tidak ditemukan"

def delete_trade(no):
    """Hapus trade"""
    global _trades_store
    original_len = len(_trades_store)
    _trades_store = [t for t in _trades_store if t["No"] != no]
    if len(_trades_store) < original_len:
        # Renumber
        for i, trade in enumerate(_trades_store):
            trade["No"] = i + 1
        return True, f"Trade #{no} dihapus"
    return False, f"Trade #{no} tidak ditemukan"

def add_broker(nama, biaya_beli, biaya_jual):
    """Tambah sekuritas"""
    _brokers_store.append({
        "Sekuritas": nama,
        "Biaya Beli (%)": biaya_beli,
        "Biaya Jual (%)": biaya_jual,
    })
