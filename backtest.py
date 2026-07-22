"""
Backtest HISTORIS atas rule skor di screener.py - beda dengan Jurnal Backtest (gsheet_journal.py)
yang sifatnya FORWARD-testing (mencatat sinyal mulai hari ini ke depan).

Modul ini WALK-FORWARD ke belakang: pada setiap titik waktu t di masa lalu, hitung skor &
sinyal PERSIS memakai compute_metrics() yang sama dengan yang dipakai live (bukan logika
duplikat), lalu lihat apa yang SUNGGUH TERJADI forward_days bar kemudian. Ini menjawab
pertanyaan "apakah rule skor ini benar-benar prediktif secara historis?" - yang sebelumnya
tidak bisa dijawab dashboard, karena Jurnal Backtest cuma mulai mencatat dari sekarang.

PENTING soal lookahead bias: pada setiap titik t, HANYA data sampai baris t yang dipakai
untuk menghitung skor (df.iloc[:t+1]) - baris t+1..t+forward_days SAMA SEKALI tidak boleh
"bocor" ke perhitungan skor, cuma dipakai untuk mengukur hasil sesudahnya. compute_metrics()
sendiri sudah didesain begitu (Donchian tidak menghitung candle hari ini), jadi modul ini
tinggal mengulang pemanggilannya di titik waktu yang berbeda-beda.

CARA PAKAI (butuh koneksi internet ke Yahoo Finance, jalankan lokal - bukan di dashboard,
supaya tidak membebani quota Yahoo Finance tiap kali dashboard dibuka):

    python backtest.py --tickers BBCA,TLKM,ADRO --years 3 --forward-days 10

Atau import langsung:

    from screener import load_ticker_universe, fetch_price_history, DEFAULT_PARAMS
    from backtest import run_historical_backtest
    universe = load_ticker_universe()
    price_data = fetch_price_history(universe["Kode"].tolist()[:100], period="3y")
    hasil = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=10)
    print(hasil["summary"])
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from screener import DEFAULT_PARAMS, compute_metrics


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


def _main():
    ap = argparse.ArgumentParser(description="Backtest historis rule skor screener.py")
    ap.add_argument("--tickers", type=str, default="",
                     help="Daftar kode saham dipisah koma, mis. BBCA,TLKM,ADRO. Kosongkan "
                          "untuk pakai N saham pertama dari tickers_idx.csv (lihat --n).")
    ap.add_argument("--n", type=int, default=100, help="Jumlah saham dari tickers_idx.csv kalau --tickers kosong.")
    ap.add_argument("--years", type=int, default=3, help="Panjang histori yang diambil.")
    ap.add_argument("--forward-days", type=int, default=10, help="Horizon pengukuran return sesudah sinyal.")
    ap.add_argument("--step", type=int, default=5, help="Jarak antar titik pengujian (hari bursa).")
    args = ap.parse_args()

    from screener import load_ticker_universe, fetch_price_history

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        universe = load_ticker_universe()
        tickers = universe["Kode"].tolist()[: args.n]

    print(f"Mengambil data {len(tickers)} saham, {args.years} tahun terakhir dari Yahoo Finance...")
    price_data = fetch_price_history(tickers, period=f"{args.years}y")
    print(f"Berhasil ambil {len(price_data)}/{len(tickers)} saham. Menjalankan backtest...")

    hasil = run_historical_backtest(price_data, DEFAULT_PARAMS, forward_days=args.forward_days, step=args.step)
    if hasil["summary"].empty:
        print("Tidak ada sinyal yang bisa diuji (data terlalu pendek atau semua gagal diambil).")
        sys.exit(1)

    print("\n=== Ringkasan Backtest Historis ===")
    print(hasil["summary"].to_string(index=False))
    print(f"\nTotal titik sinyal diuji: {len(hasil['detail'])}")

    out_path = f"backtest_detail_{args.forward_days}d.csv"
    hasil["detail"].to_csv(out_path, index=False)
    print(f"Detail lengkap disimpan ke {out_path}")


if __name__ == "__main__":
    _main()
