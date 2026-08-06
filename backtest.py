"""
Backtest HISTORIS atas rule skor di screener.py - beda dengan Jurnal Backtest (gsheet_journal.py)
yang sifatnya FORWARD-testing (mencatat sinyal mulai hari ini ke depan).

Modul ini menjawab DUA pertanyaan yang berbeda, lewat dua fungsi berbeda - jangan dicampur:

1. run_historical_backtest() - "Apakah skornya PREDIKTIF?" Walk-forward ke belakang: di
   setiap titik waktu t, hitung skor & sinyal PERSIS memakai compute_metrics() yang sama
   dengan yang dipakai live, lalu ukur return fixed-horizon (forward_days bar kemudian,
   exit di harga Close apa adanya) - dibandingkan LINTAS SEMUA jenis Signal (STRONG BUY,
   BUY, HOLD, SELL, dst.) dengan metrik yang SAMA, supaya bisa dicek apakah skor makin
   tinggi memang berkorelasi dengan return makin bagus. TIDAK memperhitungkan biaya
   transaksi dan TIDAK memakai TP/SL - exit-nya murni tanggal, bukan level harga.

2. run_realistic_backtest() - "Kalau BENERAN dieksekusi, untung bersih berapa?" Simulasi
   trade nyata HANYA untuk sinyal yang benar-benar dibeli sistem live (STRONG BUY/BUY yang
   lolos RR minimum, sama seperti build_trade_candidates()) - Entry/Target/Stop Loss dari
   Donchian, exit begitu High menyentuh Target atau Low menyentuh Stop Loss (bar mana yang
   lebih dulu), force-sell di harga Close kalau tidak kena TP/SL dalam max_hold_days -
   dikurangi fee round-trip. Inilah yang seharusnya dipakai untuk menjawab "apakah sistem
   ini beneran profitable setelah biaya", bukan fungsi #1.

PENTING soal lookahead bias (berlaku untuk KEDUA fungsi): pada setiap titik t, HANYA data
sampai baris t yang dipakai untuk menghitung skor (df.iloc[:t+1]) - baris t+1 dst SAMA
SEKALI tidak boleh "bocor" ke perhitungan skor, cuma dipakai untuk mengukur hasil sesudahnya.
compute_metrics() sendiri sudah didesain begitu (Donchian tidak menghitung candle hari ini),
jadi modul ini tinggal mengulang pemanggilannya di titik waktu yang berbeda-beda.

CARA PAKAI (butuh koneksi internet ke Yahoo Finance, jalankan lokal - bukan di dashboard,
supaya tidak membebani quota Yahoo Finance tiap kali dashboard dibuka):

    python backtest.py --tickers BBCA,TLKM,ADRO --years 3 --forward-days 10 --max-hold-days 10

Atau import langsung:

    from screener import load_ticker_universe, get_price_history_with_report, DEFAULT_PARAMS
    from backtest import run_historical_backtest, run_realistic_backtest
    universe = load_ticker_universe()
    price_data, failed_tickers = get_price_history_with_report(universe["Kode"].tolist()[:100], period="3y")
    prediktif = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=10)
    print(prediktif["summary"])
    realistis = run_realistic_backtest(price_data, DEFAULT_PARAMS)
    print(realistis["summary"])
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from screener import DEFAULT_PARAMS, compute_metrics, _donchian_levels

# Fee round-trip default: 0.15% beli + 0.25% jual, sama dengan default broker di
# real_journal.py (DEFAULT_BROKERS) - dipakai kalau tidak diisi manual. Belum termasuk
# slippage (selisih harga eksekusi riil vs harga yang tercatat di data historis).
DEFAULT_FEE_PCT = 0.15 + 0.25


def _walk_forward_single(kode: str, df: pd.DataFrame, params: dict, forward_days: int,
                          step: int = 5, min_history: int = 60) -> list[dict]:
    """Jalankan compute_metrics() di banyak titik waktu berbeda sepanjang histori satu
    saham, lalu ukur return aktual forward_days bar kemudian setelah tiap sinyal muncul.

    step=5: tidak dihitung di SETIAP hari (mahal & datanya saling tumpang tindih/tidak
    independen kalau tiap hari), cukup tiap `step` hari bursa - cara umum di backtest
    walk-forward supaya sampel tidak terlalu berkorelasi satu sama lain."""
    rows = []
    n = len(df)
    lookback = params["donchian_lookback"]
    start = max(min_history, lookback + 2)
    for t in range(start, n - forward_days, step):
        window = df.iloc[: t + 1]  # HANYA data sampai hari t - tidak ada lookahead
        m = compute_metrics(window, params)
        if m is None:
            continue
        entry_price = m["Harga"]
        exit_price = float(df.iloc[t + forward_days]["Close"])
        fwd_return_pct = (exit_price - entry_price) / entry_price * 100 if entry_price else np.nan
        rows.append({
            "Kode": kode, "Tanggal": df.index[t], "Signal": m["Signal"], "Score": m["Score"],
            "Harga Saat Sinyal": entry_price, f"Harga +{forward_days}D": exit_price,
            f"Return {forward_days}D (%)": fwd_return_pct,
        })
    return rows


def run_historical_backtest(price_data: dict[str, pd.DataFrame], params: dict | None = None,
                             forward_days: int = 10, step: int = 5) -> dict:
    """Jalankan walk-forward backtest di semua saham dalam price_data. Return dict berisi
    'detail' (tiap titik sinyal + hasil forward return) dan 'summary' (win rate & rata-rata
    return per jenis Signal - inilah jawaban statistik atas pertanyaan "skor 7 utk STRONG BUY
    itu beneran prediktif atau bukan")."""
    params = params or DEFAULT_PARAMS
    all_rows: list[dict] = []
    for kode, df in price_data.items():
        if df is None or df.empty:
            continue
        all_rows.extend(_walk_forward_single(kode, df, params, forward_days, step))

    detail = pd.DataFrame(all_rows)
    if detail.empty:
        return {"detail": detail, "summary": pd.DataFrame()}

    ret_col = f"Return {forward_days}D (%)"
    detail = detail.dropna(subset=[ret_col])

    def _agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        win = (g[ret_col] > 0).sum()
        return pd.Series({
            "Jumlah Sinyal": n,
            "Win Rate (%)": round(win / n * 100, 1) if n else 0,
            "Rata-rata Return (%)": round(g[ret_col].mean(), 2),
            "Median Return (%)": round(g[ret_col].median(), 2),
            "Return Terbaik (%)": round(g[ret_col].max(), 2),
            "Return Terburuk (%)": round(g[ret_col].min(), 2),
        })

    summary = detail.groupby("Signal").apply(_agg, include_groups=False).reset_index()
    order = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL", "SKIP (CRASH VETO)", "SKIP (ILIKUID)"]
    summary["_order"] = summary["Signal"].apply(lambda s: order.index(s) if s in order else 99)
    summary = summary.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    return {"detail": detail, "summary": summary}


def _make_regime_checker(ihsg_df: pd.DataFrame | None, ma_period: int = 50):
    """Bikin fungsi `is_bullish(tanggal) -> bool|None` dari histori IHSG, dipakai walk-forward
    (regime dihitung dari IHSG s.d. tanggal ITU SAJA - tidak ada lookahead, sama seperti
    compute_metrics()). None kalau ihsg_df tidak diisi (filter regime tidak diaktifkan) atau
    tanggal di luar rentang data IHSG yang tersedia."""
    if ihsg_df is None or ihsg_df.empty:
        return lambda _tanggal: None
    ma = ihsg_df["Close"].rolling(ma_period).mean()
    bullish = (ihsg_df["Close"] > ma)

    def is_bullish(tanggal) -> bool | None:
        d = pd.Timestamp(tanggal).normalize()
        # cari tanggal IHSG terdekat <= tanggal saham (kalender bursa saham vs IHSG bisa
        # beda 1 hari kalau salah satu libur, jadi bukan exact-match index lookup)
        idx = bullish.index.searchsorted(d, side="right") - 1
        if idx < 0 or pd.isna(ma.iloc[idx]):
            return None
        return bool(bullish.iloc[idx])

    return is_bullish


def _simulate_realistic_trades_single(kode: str, df: pd.DataFrame, params: dict, max_hold_days: int = 10,
                                       step: int = 5, min_history: int = 60, min_rr: float = 2.0,
                                       fee_pct: float = DEFAULT_FEE_PCT,
                                       signal_filter: tuple = ("STRONG BUY", "BUY"),
                                       require_bullish_regime: bool = False,
                                       ihsg_df: pd.DataFrame | None = None) -> list[dict]:
    """Simulasikan trade NYATA (Entry/Target/Stop Loss ala build_trade_candidates()) untuk
    tiap sinyal tradeable yang muncul di histori, dieksekusi hari bursa berikutnya sampai
    salah satu tersentuh:
    - Low bar <= Stop Loss -> keluar rugi di harga SL (dicek LEBIH DULU dari TP - asumsi
      konservatif kalau High & Low bar yang sama menyentuh TP dan SL sekaligus).
    - High bar >= Target -> keluar untung di harga Target.
    - Sampai max_hold_days berlalu tanpa kena TP/SL -> force-sell di Close hari terakhir
      (meniru aturan force-sell SWING 10 hari di gsheet_journal.py).
    Return dipotong fee_pct (round-trip) - inilah return BERSIH yang relevan untuk menilai
    apakah sistem ini profitable, bukan return kotor.

    require_bullish_regime + ihsg_df: kalau diisi, entry HANYA diambil saat IHSG > MA50 pada
    tanggal itu (walk-forward, bukan status regime SEKARANG) - mode default (False) TIDAK
    menggate apa pun, hasilnya jadi UNDERSTATE performa Swing yang sebenarnya (di live,
    Swing SELALU digate regime, lihat build_trade_candidates()). Tambahan ini dibuat supaya
    tool validasi resmi ini bisa reproduksi angka yang sama dgn perbandingan head-to-head di
    README ("Regresi: Fix di Atas Ternyata Pakai Formula Stop Loss yang LEBIH BURUK"), yang
    sebelum ini cuma pernah diuji lewat skrip sekali-pakai di luar repo."""
    rows = []
    n = len(df)
    lookback = params["donchian_lookback"]
    start = max(min_history, lookback + 2)
    is_bullish = _make_regime_checker(ihsg_df) if require_bullish_regime else (lambda _t: None)
    for t in range(start, n - 1, step):
        window = df.iloc[: t + 1]  # HANYA data sampai hari t - tidak ada lookahead
        m = compute_metrics(window, params)
        if m is None or m["Signal"] not in signal_filter:
            continue
        if require_bullish_regime:
            bullish = is_bullish(df.index[t])
            if bullish is None or not bullish:
                continue

        dh, dl = _donchian_levels(window, lookback)
        if dh is None or dl is None or dl <= 0:
            continue
        entry = m["Harga"]
        # Stop Loss = PALING KETAT dari (Donchian Low, MA20, 10% di bawah entry) - SAMA
        # dgn build_trade_candidates() di screener.py (lihat komentar di sana utk hasil
        # perbandingan head-to-head vs Donchian Low murni: capped menang di semua metrik).
        ma20 = float(window["Close"].rolling(20).mean().iloc[-1]) if len(window) >= 20 else dl
        sl_cap = entry * 0.90
        sl_candidates = [x for x in [dl, ma20, sl_cap] if x < entry]
        sl = max(sl_candidates) if sl_candidates else sl_cap
        if entry <= sl:
            continue
        target = dh + (dh - dl)
        risk, reward = entry - sl, target - entry
        if risk <= 0 or reward <= 0:
            continue
        rr = reward / risk
        if rr < min_rr:
            continue

        last_t = min(t + max_hold_days, n - 1)
        exit_price, exit_reason, hold_days = None, None, None
        for d in range(t + 1, last_t + 1):
            bar = df.iloc[d]
            if bar["Low"] <= sl:
                exit_price, exit_reason, hold_days = sl, "SL", d - t
                break
            if bar["High"] >= target:
                exit_price, exit_reason, hold_days = target, "TP", d - t
                break
        if exit_price is None:
            exit_price = float(df.iloc[last_t]["Close"])
            exit_reason, hold_days = "FORCE SELL", last_t - t

        gross_return_pct = (exit_price - entry) / entry * 100
        net_return_pct = gross_return_pct - fee_pct
        rows.append({
            "Kode": kode, "Tanggal": df.index[t], "Signal": m["Signal"], "Score": m["Score"],
            "Entry": entry, "Target": round(target, 2), "Stop Loss": round(sl, 2), "RR": round(rr, 2),
            "Exit": round(exit_price, 2), "Exit Reason": exit_reason, "Hold Days": hold_days,
            "Gross Return (%)": round(gross_return_pct, 2), "Net Return (%)": round(net_return_pct, 2),
        })
    return rows


def run_realistic_backtest(price_data: dict[str, pd.DataFrame], params: dict | None = None,
                            max_hold_days: int = 10, step: int = 5, min_rr: float = 2.0,
                            fee_pct: float = DEFAULT_FEE_PCT,
                            signal_filter: tuple = ("STRONG BUY", "BUY"),
                            require_bullish_regime: bool = False,
                            ihsg_df: pd.DataFrame | None = None) -> dict:
    """Jalankan simulasi trade realistis (TP/SL/force-sell + fee) di semua saham dalam
    price_data, untuk sinyal yang benar-benar tradeable saja. Return dict berisi 'detail'
    (tiap trade simulasi) dan 'summary' (win rate & return BERSIH per jenis Signal &
    Exit Reason) - inilah jawaban atas "apakah sistem ini profitable setelah biaya".

    require_bullish_regime=True (butuh ihsg_df diisi): entry cuma diambil saat IHSG>MA50
    pada tanggal itu (walk-forward) - default False TIDAK menggate apa pun, UNDERSTATE
    performa Swing yang sebenarnya krn live SELALU menggate Swing dgn regime ini. Lihat
    README > "Regresi: Fix di Atas Ternyata Pakai Formula Stop Loss yang LEBIH BURUK"."""
    params = params or DEFAULT_PARAMS
    all_rows: list[dict] = []
    for kode, df in price_data.items():
        if df is None or df.empty:
            continue
        all_rows.extend(_simulate_realistic_trades_single(
            kode, df, params, max_hold_days, step, min_rr=min_rr, fee_pct=fee_pct,
            signal_filter=signal_filter, require_bullish_regime=require_bullish_regime, ihsg_df=ihsg_df))

    detail = pd.DataFrame(all_rows)
    if detail.empty:
        return {"detail": detail, "summary": pd.DataFrame()}

    def _agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        win = (g["Net Return (%)"] > 0).sum()
        return pd.Series({
            "Jumlah Trade": n,
            "Win Rate Bersih (%)": round(win / n * 100, 1) if n else 0,
            "Rata-rata Return Kotor (%)": round(g["Gross Return (%)"].mean(), 2),
            "Rata-rata Return Bersih (%)": round(g["Net Return (%)"].mean(), 2),
            "Total Return Bersih (%)": round(g["Net Return (%)"].sum(), 2),
            "Rata-rata Hari Ditahan": round(g["Hold Days"].mean(), 1),
            "TP (n)": int((g["Exit Reason"] == "TP").sum()),
            "SL (n)": int((g["Exit Reason"] == "SL").sum()),
            "Force Sell (n)": int((g["Exit Reason"] == "FORCE SELL").sum()),
        })

    summary = detail.groupby("Signal").apply(_agg, include_groups=False).reset_index()
    order = ["STRONG BUY", "BUY"]
    summary["_order"] = summary["Signal"].apply(lambda s: order.index(s) if s in order else 99)
    summary = summary.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    return {"detail": detail, "summary": summary}


def _main():
    ap = argparse.ArgumentParser(description="Backtest historis rule skor screener.py")
    ap.add_argument("--tickers", type=str, default="",
                     help="Daftar kode saham dipisah koma, mis. BBCA,TLKM,ADRO. Kosongkan "
                          "untuk pakai N saham pertama dari tickers_idx.csv (lihat --n).")
    ap.add_argument("--n", type=int, default=100, help="Jumlah saham dari tickers_idx.csv kalau --tickers kosong.")
    ap.add_argument("--years", type=int, default=3, help="Panjang histori yang diambil.")
    ap.add_argument("--forward-days", type=int, default=10,
                     help="[Backtest #1 - prediktif] Horizon fixed pengukuran return sesudah sinyal, lintas semua Signal.")
    ap.add_argument("--max-hold-days", type=int, default=15,
                     help="[Backtest #2 - realistis] Batas hari force-sell kalau TP/SL belum tersentuh (default 15, sama seperti Swing di live).")
    ap.add_argument("--min-rr", type=float, default=1.5, help="[Backtest #2] RR minimum, sama seperti live Swing (build_trade_candidates).")
    ap.add_argument("--fee-pct", type=float, default=DEFAULT_FEE_PCT,
                     help="[Backtest #2] Fee round-trip (%%) yang dipotong dari return kotor.")
    ap.add_argument("--step", type=int, default=5, help="Jarak antar titik pengujian (hari bursa).")
    ap.add_argument("--regime-filter", action="store_true",
                     help="[Backtest #2] Gate entry ke IHSG>MA50 (walk-forward, sama seperti Swing "
                          "di live lewat build_trade_candidates) - TANPA flag ini, angka Backtest #2 "
                          "UNDERSTATE performa Swing yang sebenarnya. Lihat README > 'Regresi: Fix di "
                          "Atas Ternyata Pakai Formula Stop Loss yang LEBIH BURUK'.")
    args = ap.parse_args()

    from screener import load_ticker_universe, get_price_history_with_report

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        universe = load_ticker_universe()
        tickers = universe["Kode"].tolist()[: args.n]

    print(f"Mengambil data {len(tickers)} saham, {args.years} tahun terakhir dari Yahoo Finance...")
    price_data, failed_tickers = get_price_history_with_report(tickers, period=f"{args.years}y")
    print(f"Berhasil ambil {len(price_data)}/{len(tickers)} saham. Menjalankan backtest...")
    if failed_tickers:
        print(f"⚠️ {len(failed_tickers)} saham gagal diambil setelah retry (tidak ikut backtest): "
              f"{', '.join(failed_tickers[:20])}{' ...' if len(failed_tickers) > 20 else ''}")

    ihsg_df = None
    if args.regime_filter:
        from screener import fetch_ihsg_history
        print("Mengambil histori IHSG utk filter regime...")
        ihsg_df = fetch_ihsg_history(period="max")

    hasil = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=args.forward_days, step=args.step)
    if hasil["summary"].empty:
        print("Tidak ada sinyal yang bisa diuji (data terlalu pendek atau semua gagal diambil).")
        sys.exit(1)

    print("\n=== Backtest #1: Apakah skornya prediktif? (fixed-horizon, semua jenis Signal, TANPA fee) ===")
    print(hasil["summary"].to_string(index=False))
    print(f"Total titik sinyal diuji: {len(hasil['detail'])}")

    out_path = f"backtest_detail_{args.forward_days}d.csv"
    hasil["detail"].to_csv(out_path, index=False)
    print(f"Detail lengkap disimpan ke {out_path}")

    realistis = run_realistic_backtest(price_data, DEFAULT_PARAMS, max_hold_days=args.max_hold_days,
                                        step=args.step, min_rr=args.min_rr, fee_pct=args.fee_pct,
                                        require_bullish_regime=args.regime_filter, ihsg_df=ihsg_df)
    regime_note = " + filter regime IHSG>MA50" if args.regime_filter else " (TANPA filter regime - understate Swing, lihat --help)"
    print(f"\n=== Backtest #2: Kalau beneran dieksekusi (TP/SL/force-sell, RR>={args.min_rr}, fee {args.fee_pct}%{regime_note}) ===")
    if realistis["summary"].empty:
        print("Tidak ada trade STRONG BUY/BUY yang lolos filter RR minimum untuk disimulasikan.")
    else:
        print(realistis["summary"].to_string(index=False))
        total_net = realistis["detail"]["Net Return (%)"].sum()
        print(f"Total trade disimulasikan: {len(realistis['detail'])} | Total Return Bersih (sum, bukan compounding): {total_net:.2f}%")
        out_path2 = f"backtest_realistic_{args.max_hold_days}d.csv"
        realistis["detail"].to_csv(out_path2, index=False)
        print(f"Detail lengkap disimpan ke {out_path2}")


if __name__ == "__main__":
    _main()
