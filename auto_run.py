"""
Runner OTOMATIS untuk auto-buy/auto-sell backtest - dijalankan terjadwal oleh GitHub Actions,
BUKAN lewat dashboard web. Ini menjawab kelemahan: kalau dashboard tidak dibuka, backtest
sebelumnya terlewat karena tombolnya tidak pernah diklik.

PENTING: script ini memanggil fungsi yang PERSIS SAMA dengan yang dipakai app.py
(screener.py, gsheet_journal.py) - bukan logika duplikat/tertulis ulang - supaya hasil
auto-buy/auto-sell di sini selalu konsisten dengan yang akan terjadi kalau tombol di
dashboard diklik manual.

BUY vs SELL beda jadwal (lihat main()): BUY cuma jalan SORE (>=12:00 WIB), SELL jalan
tiap kali dipanggil (pagi & sore) - lihat komentar di main() utk alasan lengkapnya.

Cara jalan: lihat .github/workflows/auto_backtest.yml (dipicu terjadwal oleh GitHub, gratis).
"""

import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from screener import (
    DEFAULT_PARAMS, load_ticker_universe, get_price_history_with_report, build_screener_table,
    build_trade_candidates, build_simple_candidates, fetch_ihsg_history, market_regime,
)
import gsheet_journal as gj
import equity as eq
import riwayat_journal as riwayat
import simple_journal
from telegram_notify import send_telegram_message

WIB = ZoneInfo("Asia/Jakarta")

# Parameter sama seperti default di sidebar dashboard - ubah di sini kalau mau beda
N_SCAN = 962                 # pindai semua saham (bukan cuma top-N seperti default dashboard) -
                              # 962 = seluruh saham tercatat IDX per tickers_idx.csv resmi BEI
DONCHIAN_LB_SWING = 20
# MIN_RR_SWING=1.5 divalidasi lewat backtest realistis + out-of-sample (README > Backtest
# Historis).
MIN_RR_SWING = 1.5
RISK_PCT_PER_TRADE = 1.0     # sama seperti default sidebar dashboard
# Batas posisi baru/hari - bug nyata dari laporan user: 10 Agustus buka SEMUA top_n=10
# kandidat SEKALIGUS dlm 1 hari, IHSG terkoreksi tipis beberapa hari sesudahnya, SEMUA
# posisi kena SL berbarengan krn dibuka berbarengan (risiko terkonsentrasi). User (modal
# kecil) diminta pilih batas realistis spt trader beneran, pilih 5 - sama dgn default
# sidebar dashboard.
MAX_POSISI_BARU_PER_HARI = 5


def log(msg: str):
    print(f"[{datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')} WIB] {msg}", flush=True)


def main():
    if not gj.is_configured():
        log("❌ Google Sheets belum terkonfigurasi (secrets tidak ditemukan). Berhenti.")
        sys.exit(1)

    # BUY hanya dijalankan SORE/mendekati penutupan (>=12:00 WIB), BUKAN pagi. Alasan:
    # SELURUH sistem yang sudah divalidasi sepanjang sesi ini (Score/Signal, Gap Up/Down,
    # Open=Low) dibacktest dgn asumsi data 1 HARI PENUH/settled (Volume Ratio vs rata-rata
    # 20 hari, breakout, dst.). Kalau scan BUY dijalankan pagi (09:15 WIB, baru 15 menit
    # bursa buka), Volume Ratio & komponen Score lain baru mencerminkan sebagian KECIL hari
    # itu - TIDAK representatif, di luar asumsi backtest. Diskusi dgn user: "kita berfikir
    # sejenak... sekarang disepakati apakah swing membeli pagi hari atau sore hari" ->
    # disepakati SORE. Cek JUAL (SL/TP posisi yg SUDAH OPEN) aman kapan saja - cuma
    # membandingkan harga terkini vs level yg sudah ditetapkan, TIDAK butuh data 1 hari
    # penuh - jadi TETAP jalan tiap kali script ini dipanggil (pagi maupun sore).
    is_sore = datetime.now(WIB).hour >= 12
    log(f"Jam sekarang: {datetime.now(WIB).strftime('%H:%M')} WIB -> mode: {'SORE (scan BUY + cek JUAL)' if is_sore else 'PAGI (cek JUAL saja, skip scan BUY)'}")

    if not is_sore:
        # Mode PAGI: skip scan 962 saham sepenuhnya (tidak dipakai utk BUY, buang2 kuota
        # Yahoo Finance kalau tetap di-fetch) - auto_close_positions({}, {}) SENDIRI sudah
        # bisa fetch harga (Close+High+Low) khusus saham yg statusnya OPEN saja (lihat
        # "missing" di gsheet_journal.py), jauh lebih ringan & cepat.
        closed = gj.auto_close_positions({}, {})
        log(f"Auto-SELL (mode pagi): {closed if closed else 'tidak ada posisi yang perlu ditutup'}")

        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        if bot_token and chat_id:
            waktu = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
            msg = f"<b>🤖 Cek Pagi ({waktu})</b>\n\n🔴 Auto-SELL: " + (", ".join(closed) if closed else "tidak ada")
            ok, info = send_telegram_message(bot_token, chat_id, msg)
            log(f"Telegram: {'terkirim' if ok else 'GAGAL - ' + info}")
        else:
            log("ℹ️ TELEGRAM_BOT_TOKEN/CHAT_ID belum diisi - lewati notifikasi Telegram.")
        log("✅ Selesai (mode pagi).")
        return

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

    # Riwayat Saham: log snapshot harian (Signal BUY/STRONG BUY) ke sheet RIWAYAT_SAHAM,
    # TERUS DITAMBAH (append) - user mau performa tiap saham bisa dilihat dari waktu ke
    # waktu di SATU tempat, tanpa download CSV berulang yg bikin file terpisah tiap kali.
    # Sengaja di sini (run SORE, sekali sehari) - SAMA rasionalnya dgn kenapa scan
    # BUY cuma sore: data 1 hari penuh, representatif & sebanding hari-ke-hari - bukan
    # data pagi yg baru sebagian kecil hari itu. Dibungkus try/except sendiri - gagal di
    # sini TIDAK BOLEH menghentikan alur BUY/SELL utama di bawah.
    try:
        if riwayat.is_configured():
            n_snapshot = riwayat.append_daily_snapshot(table)
            log(f"Riwayat Saham: {n_snapshot} snapshot ditambahkan." if n_snapshot
                else "Riwayat Saham: tidak ada snapshot baru (sudah ada hari ini, atau tidak ada Signal BUY+).")
    except Exception as e:
        log(f"⚠️ Riwayat Saham gagal disimpan (tidak menghentikan proses BUY/SELL): {e}")

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

    # ---- Auto-BUY: Day Trading (BPJS/BSJP) DIHAPUS ----
    # Day Trading terbukti TIDAK konsisten profit (lihat README > "Day Trading: Bukan Soal
    # Parameter, Tapi Desain Sinyal") - sudah dihapus dari dashboard (app.py), TAPI script ini
    # (dijalankan terjadwal oleh GitHub Actions, terpisah dari dashboard) masih memanggilnya
    # sendiri - ketinggalan waktu penghapusan, jadi BPJS/BSJP tetap ke-auto-buy 2x/hari
    # (09:15 & 14:45 WIB) TANPA sepengetahuan siapa pun yang cuma lihat dashboard. Baru
    # ditemukan saat user melaporkan floating loss besar & audit menemukan closed trade
    # yang tercatat semuanya BPJS - bukan Swing.
    #
    # ---- Auto-BUY: Swing Trading (digate regime IHSG - divalidasi lewat backtest realistis
    # + out-of-sample: net rugi kalau dipaksa aktif di pasar bearish, lihat README). Filter
    # anti-kejar-harga (Naik dari Open % > 10%) sudah otomatis ikut di build_trade_candidates().
    # require_minervini_position TIDAK diisi eksplisit -> ikut default True (screener.py) -
    # SENGAJA independen dari checkbox dashboard ("Wajib posisi 52-minggu") yang bisa
    # dimatikan user; skrip otomatis tanpa pengawasan ini tetap pakai default paling
    # tervalidasi/aman, terlepas apa yang sedang dipilih user di dashboard interaktifnya. ----
    ihsg_hist = fetch_ihsg_history()
    regime = market_regime(ihsg_hist)
    log(f"Regime IHSG: {regime['status']}")
    cands_swing = build_trade_candidates(table, price_data, DONCHIAN_LB_SWING, MIN_RR_SWING, top_n=10,
                                          require_bullish_regime=True, regime_status=regime["status"],
                                          total_equity=total_equity_now, risk_pct=RISK_PCT_PER_TRADE)
    opened_swing = gj.open_positions_from_candidates(cands_swing, "SWING", max_new_per_day=MAX_POSISI_BARU_PER_HARI)
    if regime["status"] != "BULLISH":
        log(f"Auto-BUY Swing Trading: dilewati (IHSG {regime['status']}, filter regime aktif)")
    else:
        log(f"Auto-BUY Swing Trading: {opened_swing if opened_swing else 'tidak ada posisi baru'}")

    # ---- Auto-SELL: cek TP/SL/force-sell semua posisi OPEN ----
    # hl_lookup (High/Low hari ini) - SAMA seperti yang dipakai dashboard (app.py) supaya
    # TP/SL dicek dari rentang harga hari itu, bukan cuma 1 titik harga (Close) yang bisa
    # MELEWATKAN TP/SL yang sebenarnya tersentuh intraday. Sebelum ini auto_run.py cuma
    # kirim price_lookup (Close-only) - kurang presisi dibanding metodologi backtest.
    price_lookup = dict(zip(table["Kode"], table["Harga"]))
    hl_lookup = {kode: (float(df["High"].iloc[-1]), float(df["Low"].iloc[-1]))
                 for kode, df in price_data.items() if df is not None and not df.empty}
    closed = gj.auto_close_positions(price_lookup, hl_lookup)
    log(f"Auto-SELL: {closed if closed else 'tidak ada posisi yang perlu ditutup'}")

    # ---- Screener Sederhana (pembanding) - jurnal & sheet TERPISAH (simple_journal.py,
    # sheet POSISI_SEDERHANA) - user: "target saya yang penting profit dengan risk rendah,
    # tetap profesional... mungkin fokus ke screener dulu", lalu "ya" (setuju dibangun jadi
    # sistem live). Entry: breakout + posisi 52-minggu + volume rendah, SL 5%
    # (build_simple_candidates()); exit: 2 lapis (partial-lock 0,7R->0,5R + target-lock
    # 0,5R, simple_journal.py). SENGAJA TIDAK digate regime IHSG spt Swing di atas - data
    # uji (350 saham/3 tahun) menunjukkan regime BEARISH utk screener ini SUDAH positif
    # (+0,49% avg), beda dari sistem lama yang memang net rugi kalau dipaksa aktif saat
    # bearish - belum diuji A/B eksplisit apa gating regime akan menambah baik, jadi
    # dibiarkan aktif di semua regime dulu sampai ada bukti sebaliknya.
    try:
        if simple_journal.is_configured():
            cands_simple = build_simple_candidates(table, price_data, top_n=10,
                                                    total_equity=total_equity_now, risk_pct=RISK_PCT_PER_TRADE,
                                                    min_value_traded=DEFAULT_PARAMS["min_value_traded"])
            opened_simple = simple_journal.open_positions_from_candidates(
                cands_simple, max_new_per_day=MAX_POSISI_BARU_PER_HARI)
            log(f"Auto-BUY Screener Sederhana: {opened_simple if opened_simple else 'tidak ada posisi baru'}")
            closed_simple = simple_journal.auto_close_positions(price_lookup, hl_lookup)
            log(f"Auto-SELL Screener Sederhana: {closed_simple if closed_simple else 'tidak ada posisi yang perlu ditutup'}")
    except Exception as e:
        log(f"⚠️ Screener Sederhana gagal diproses (tidak menghentikan alur utama): {e}")

    # ---- Kirim ringkasan ke Telegram (supaya Bro tahu hasilnya TANPA perlu buka GitHub/web) ----
    bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        waktu = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
        lines = [f"<b>🤖 Auto-Backtest Selesai</b> ({waktu})", ""]
        lines.append(f"📊 Dipindai: {len(table)} saham")
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
