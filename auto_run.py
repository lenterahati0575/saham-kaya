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
from zoneinfo import ZoneInfo

import streamlit as st
from screener import (
    DEFAULT_PARAMS, load_ticker_universe, get_price_history_with_report, build_screener_table,
    build_trade_candidates, classify_daytrading_tipe, fetch_ihsg_history, market_regime,
)
import gsheet_journal as gj
import equity as eq
from telegram_notify import send_telegram_message

WIB = ZoneInfo("Asia/Jakarta")

# Parameter sama seperti default di sidebar dashboard - ubah di sini kalau mau beda
N_SCAN = 615                 # pindai semua saham (bukan cuma top-N seperti default dashboard)
DONCHIAN_LB_SWING = 20
DONCHIAN_LB_DAY = 10
# MIN_RR_SWING=1.5 divalidasi lewat backtest realistis + out-of-sample (README > Backtest
# Historis). MIN_RR_DAY dipertahankan di nilai lama - belum divalidasi serupa.
MIN_RR_SWING = 1.5
MIN_RR_DAY = 2.0
RISK_PCT_PER_TRADE = 1.0     # sama seperti default sidebar dashboard


def log(msg: str):
    print(f"[{datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')} WIB] {msg}", flush=True)


def main():
    if not gj.is_configured():
        log("❌ Google Sheets belum terkonfigurasi (secrets tidak ditemukan). Berhenti.")
        sys.exit(1)

    log("Memuat daftar saham...")
    universe = load_ticker_universe()
    tickers = universe["Kode"].tolist()[:N_SCAN]

    log(f"Mengambil data live Yahoo Finance untuk {len(tickers)} saham (bisa beberapa menit)...")
    price_data, failed_tickers = get_price_history_with_report(tickers)
    log(f"Berhasil ambil data {len(price_data)}/{len(tickers)} saham.")
    if failed_tickers:
        log(f"⚠️ {len(failed_tickers)} saham gagal diambil setelah retry: {', '.join(failed_tickers[:20])}"
            f"{' ...' if len(failed_tickers) > 20 else ''}")

    table = build_screener_table(price_data, universe, DEFAULT_PARAMS)
    if table.empty:
        log("⚠️ Tabel screener kosong (kemungkinan gagal ambil data). Berhenti.")
        sys.exit(1)
    log(f"Screener selesai: {len(table)} saham lolos data historis minimum.")

    # Total Equity terbaru (kalau ada snapshot) - dipakai utk hitung Lot berbasis risiko,
    # bukan angka tetap 10 lot utk semua saham tanpa peduli harga/modal (lihat README).
    total_equity_now = None
    try:
        eq_df_now = eq.load_equity()
        if not eq_df_now.empty:
            ts_now = eq.total_equity_over_time(eq_df_now)
            if not ts_now.empty:
                total_equity_now = float(ts_now["Total Equity (Rp)"].iloc[-1])
    except Exception:
        total_equity_now = None
    log(f"Total Equity utk position sizing: {'Rp{:,.0f}'.format(total_equity_now) if total_equity_now else 'belum ada snapshot - Lot fallback ke default'}")

    # ---- Auto-BUY: Day Trading (tidak digate regime IHSG - belum divalidasi seperti Swing) ----
    day_tipe = classify_daytrading_tipe()
    cands_day = build_trade_candidates(table, price_data, DONCHIAN_LB_DAY, MIN_RR_DAY, top_n=10,
                                        total_equity=total_equity_now, risk_pct=RISK_PCT_PER_TRADE)
    opened_day = gj.open_positions_from_candidates(cands_day, day_tipe)
    log(f"Auto-BUY Day Trading ({day_tipe}): {opened_day if opened_day else 'tidak ada posisi baru'}")

    # ---- Auto-BUY: Swing Trading (digate regime IHSG - divalidasi lewat backtest realistis
    # + out-of-sample: net rugi kalau dipaksa aktif di pasar bearish, lihat README) ----
    ihsg_hist = fetch_ihsg_history()
    regime = market_regime(ihsg_hist)
    log(f"Regime IHSG: {regime['status']}")
    cands_swing = build_trade_candidates(table, price_data, DONCHIAN_LB_SWING, MIN_RR_SWING, top_n=10,
                                          require_bullish_regime=True, regime_status=regime["status"],
                                          total_equity=total_equity_now, risk_pct=RISK_PCT_PER_TRADE)
    opened_swing = gj.open_positions_from_candidates(cands_swing, "SWING")
    if regime["status"] != "BULLISH":
        log(f"Auto-BUY Swing Trading: dilewati (IHSG {regime['status']}, filter regime aktif)")
    else:
        log(f"Auto-BUY Swing Trading: {opened_swing if opened_swing else 'tidak ada posisi baru'}")

    # ---- Auto-SELL: cek TP/SL/force-sell semua posisi OPEN ----
    price_lookup = dict(zip(table["Kode"], table["Harga"]))
    closed = gj.auto_close_positions(price_lookup)
    log(f"Auto-SELL: {closed if closed else 'tidak ada posisi yang perlu ditutup'}")

    # ---- Kirim ringkasan ke Telegram (supaya Bro tahu hasilnya TANPA perlu buka GitHub/web) ----
    bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        waktu = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
        lines = [f"<b>🤖 Auto-Backtest Selesai</b> ({waktu})", ""]
        lines.append(f"📊 Dipindai: {len(table)} saham")
        lines.append(f"🟢 Auto-BUY Day Trading ({day_tipe}): " +
                      (", ".join(opened_day) if opened_day else "tidak ada"))
        swing_line = (f"dilewati (IHSG {regime['status']})" if regime["status"] != "BULLISH"
                      else (", ".join(opened_swing) if opened_swing else "tidak ada"))
        lines.append(f"🟢 Auto-BUY Swing (IHSG {regime['status']}): {swing_line}")
        lines.append(f"🔴 Auto-SELL: " + (", ".join(closed) if closed else "tidak ada"))
        ok, info = send_telegram_message(bot_token, chat_id, "\n".join(lines))
        log(f"Telegram: {'terkirim' if ok else 'GAGAL - ' + info}")
    else:
        log("ℹ️ TELEGRAM_BOT_TOKEN/CHAT_ID belum diisi - lewati notifikasi Telegram.")

    log("✅ Selesai.")


if __name__ == "__main__":
    main()
