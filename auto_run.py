"""
Runner OTOMATIS untuk auto-buy/auto-sell backtest - dijalankan terjadwal oleh GitHub Actions,
BUKAN lewat dashboard web. Ini menjawab kelemahan: kalau dashboard tidak dibuka, backtest
sebelumnya terlewat karena tombolnya tidak pernah diklik.

PENTING: script ini memanggil fungsi yang PERSIS SAMA dengan yang dipakai app.py
(screener.py, gsheet_journal.py) - bukan logika duplikat/tertulis ulang - supaya hasil
auto-buy/auto-sell di sini selalu konsisten dengan yang akan terjadi kalau tombol di
dashboard diklik manual.

Cara jalan: lihat .github/workflows/auto_backtest.yml (dipicu terjadwal oleh GitHub, gratis).
"""

import sys
import os
from datetime import datetime

import streamlit as st
from screener import (
    DEFAULT_PARAMS, load_ticker_universe, fetch_price_history, build_screener_table,
    build_trade_candidates, classify_daytrading_tipe,
)
import gsheet_journal as gj
from telegram_notify import send_telegram_message

# Parameter sama seperti default di sidebar dashboard - ubah di sini kalau mau beda
N_SCAN = 615                 # pindai semua saham (bukan cuma top-N seperti default dashboard)
DONCHIAN_LB_SWING = 20
DONCHIAN_LB_DAY = 10
MIN_RR = 2.0


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def main():
    if not gj.is_configured():
        log("❌ Google Sheets belum terkonfigurasi (secrets tidak ditemukan). Berhenti.")
        sys.exit(1)

    log("Memuat daftar saham...")
    universe = load_ticker_universe()
    tickers = universe["Kode"].tolist()[:N_SCAN]

    log(f"Mengambil data live Yahoo Finance untuk {len(tickers)} saham (bisa beberapa menit)...")
    price_data = fetch_price_history(tickers)
    log(f"Berhasil ambil data {len(price_data)}/{len(tickers)} saham.")

    table = build_screener_table(price_data, universe, DEFAULT_PARAMS)
    if table.empty:
        log("⚠️ Tabel screener kosong (kemungkinan gagal ambil data). Berhenti.")
        sys.exit(1)
    log(f"Screener selesai: {len(table)} saham lolos data historis minimum.")

    # ---- Auto-BUY: Day Trading ----
    day_tipe = classify_daytrading_tipe()
    cands_day = build_trade_candidates(table, price_data, DONCHIAN_LB_DAY, MIN_RR, top_n=10)
    opened_day = gj.open_positions_from_candidates(cands_day, day_tipe)
    log(f"Auto-BUY Day Trading ({day_tipe}): {opened_day if opened_day else 'tidak ada posisi baru'}")

    # ---- Auto-BUY: Swing Trading ----
    cands_swing = build_trade_candidates(table, price_data, DONCHIAN_LB_SWING, MIN_RR, top_n=10)
    opened_swing = gj.open_positions_from_candidates(cands_swing, "SWING")
    log(f"Auto-BUY Swing Trading: {opened_swing if opened_swing else 'tidak ada posisi baru'}")

    # ---- Auto-SELL: cek TP/SL/force-sell semua posisi OPEN ----
    price_lookup = dict(zip(table["Kode"], table["Harga"]))
    closed = gj.auto_close_positions(price_lookup)
    log(f"Auto-SELL: {closed if closed else 'tidak ada posisi yang perlu ditutup'}")

    # ---- Kirim ringkasan ke Telegram (supaya Bro tahu hasilnya TANPA perlu buka GitHub/web) ----
    bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        waktu = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        lines = [f"<b>🤖 Auto-Backtest Selesai</b> ({waktu})", ""]
        lines.append(f"📊 Dipindai: {len(table)} saham")
        lines.append(f"🟢 Auto-BUY Day Trading ({day_tipe}): " +
                      (", ".join(opened_day) if opened_day else "tidak ada"))
        lines.append(f"🟢 Auto-BUY Swing: " + (", ".join(opened_swing) if opened_swing else "tidak ada"))
        lines.append(f"🔴 Auto-SELL: " + (", ".join(closed) if closed else "tidak ada"))
        ok, info = send_telegram_message(bot_token, chat_id, "\n".join(lines))
        log(f"Telegram: {'terkirim' if ok else 'GAGAL - ' + info}")
    else:
        log("ℹ️ TELEGRAM_BOT_TOKEN/CHAT_ID belum diisi - lewati notifikasi Telegram.")

    log("✅ Selesai.")


if __name__ == "__main__":
    main()
