# IDX Screener Dashboard

Dashboard web gratis untuk screening saham IDX — data live dari Yahoo Finance,
logika skor identik dengan `IDX_Screener_Bot_diperbaiki.xlsx` (gate likuiditas,
veto crash, Donchian 20D Breakout).

## Isi Folder

| File | Fungsi |
|---|---|
| `app.py` | Dashboard utama (tampilan, filter, grafik) |
| `screener.py` | Ambil data Yahoo Finance + hitung skor |
| `indicators.py` | RSI/MACD/MA/Swing High-Low, dsb |
| `sectors.py` | Klasifikasi sektor saham |
| `calculators.py` | Kalkulator profit & manajemen risiko |
| `gsheet_journal.py` | Jurnal Backtest (simulasi) ke Google Sheets |
| `real_journal.py` | Jurnal Trading Real (transaksi uang beneran, multi-sekuritas) |
| `equity.py` | Tracking modal/equity per sekuritas + perbandingan IHSG |
| `auto_run.py` | Runner auto-backtest terjadwal (dipanggil GitHub Actions, bukan dashboard) |
| `.github/workflows/auto_backtest.yml` | Jadwal otomatis (GitHub Actions, gratis) |
| `.github/workflows/tests.yml` | Menjalankan `tests/` otomatis tiap push/PR (GitHub Actions, gratis) |
| `backtest.py` | Backtest HISTORIS rule skor (walk-forward, terpisah dari Jurnal Backtest yang forward-testing) |
| `tests/` | Unit test (pytest) untuk screener, kalkulator, indikator, jurnal real, dan backtest engine |
| `telegram_notify.py` | Kirim watchlist/ringkasan ke Telegram |
| `tickers_idx.csv` | Daftar 615 kode saham (dari file Excel Bro) |
| `requirements.txt` | Daftar library yang dibutuhkan |

## Cara Deploy Gratis (Streamlit Community Cloud)

1. **Buat akun GitHub** (kalau belum ada) di https://github.com
2. **Buat repository baru** (boleh Public atau Private), lalu upload SEMUA file di folder ini
   (bisa drag-drop lewat browser GitHub, tidak perlu command line)
3. **Buat akun Streamlit Cloud** di https://share.streamlit.io (login pakai akun GitHub, gratis)
4. Klik **"New app"** → pilih repository yang tadi dibuat → Main file path: `app.py` → **Deploy**
5. Tunggu 1-3 menit, dashboard akan dapat URL publik seperti
   `https://nama-app-anda.streamlit.app` — bisa dibuka di HP maupun laptop, browser apa saja.

## 🔒 Kunci Dashboard (WAJIB kalau dashboard sudah dipakai untuk uang riil)

**PENTING**: link Streamlit Community Cloud bersifat PUBLIK. Siapa saja yang punya link ini
bisa melihat Jurnal Real (transaksi uang beneran Bro) dan menekan tombol buka/tutup posisi
di Jurnal Backtest, kalau dashboard tidak dikunci. Untuk mengunci:

1. Di Streamlit Cloud: buka app → **Settings > Secrets**, tambahkan:
   ```toml
   APP_PASSWORD = "ganti-dengan-password-rahasia-anda"
   ```
2. Simpan, app otomatis restart. Sekarang dashboard akan minta password sebelum bisa dipakai.
3. Kalau `APP_PASSWORD` belum diisi, dashboard tetap bisa diakses (supaya tidak mengunci diri
   sendiri secara tidak sengaja saat masih tahap coba-coba) - tapi akan tampil warning jelas
   di halaman utama sampai Bro mengisinya.

Catatan: ini proteksi dasar (satu password dibagi bersama, dicek di sisi aplikasi), BUKAN
sistem login multi-user. Cukup untuk mencegah orang lain yang kebetulan menemukan link,
tapi jangan bagikan password ke siapapun yang tidak Bro percaya penuh.

## Aktifkan Notifikasi Telegram (Opsional)

1. Buat bot Telegram lewat **@BotFather** di Telegram → dapat `BOT_TOKEN`
2. Kirim 1 pesan apa saja ke bot itu, lalu buka
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` di browser untuk menemukan `chat_id` Bro
3. Di Streamlit Cloud: buka app → **Settings > Secrets**, isi:
   ```toml
   TELEGRAM_BOT_TOKEN = "isi-token-dari-botfather"
   TELEGRAM_CHAT_ID = "isi-chat-id-anda"
   ```
4. Simpan, app otomatis restart. Tombol "Kirim Watchlist Sekarang" di tab **Kandidat Terbaik** akan aktif.

## Setup Google Sheets untuk Jurnal Backtest (Auto Buy/Sell)

Sheet ID Bro (dari link yang dikirim): `15HuHfHf1owbFowwXx-Z_vJRLJoDqcob6f9ZwbSAw9qs`
Pastikan sheet ini punya tab bernama persis **`POSISI`** dengan header di baris 1:
`Tanggal Open | Saham | Harga Beli | TP | SL | Tipe | Tanggal Close | Harga Jual | P&L (Rp) | P&L (%) | Status | Hari`

1. Buka **console.cloud.google.com** → buat project baru (gratis, tidak perlu kartu kredit untuk ini)
2. Di project itu, aktifkan **Google Sheets API** dan **Google Drive API** (cari lewat search bar di dalam Console)
3. Buka **APIs & Services > Credentials** → **Create Credentials > Service Account** → beri nama bebas → Create
4. Buka service account yang baru dibuat → tab **Keys** → **Add Key > Create New Key > JSON** → file JSON otomatis terunduh
5. Buka file JSON itu dengan text editor, isinya seperti ini:
   ```json
   {
     "type": "service_account",
     "project_id": "...",
     "private_key_id": "...",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     "client_email": "nama-acak@project-id.iam.gserviceaccount.com",
     ...
   }
   ```
6. **Salin email di `client_email`** → buka Google Sheet Bro (yang berisi tab POSISI) → klik **Share** →
   tempel email itu → beri akses **Editor** → Send
7. Di Streamlit Cloud: buka app → **Settings > Secrets** → tempel:
   ```toml
   GOOGLE_SHEET_ID = "15HuHfHf1owbFowwXx-Z_vJRLJoDqcob6f9ZwbSAw9qs"

   [gcp_service_account]
   type = "service_account"
   project_id = "isi-dari-json"
   private_key_id = "isi-dari-json"
   private_key = "isi-dari-json (biarkan \\n apa adanya, jangan diubah)"
   client_email = "isi-dari-json"
   client_id = "isi-dari-json"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "isi-dari-json"
   ```
8. Simpan, app otomatis restart. Bagian **"🤖 Buka Posisi Otomatis"** di tab **Kandidat** akan aktif dan bisa baca/tulis ke sheet POSISI.

### Tombol TradingView (kolom "TV")
Setiap tabel saham punya kolom "TV" berisi tombol yang membuka chart TradingView saham itu
langsung di TAB YANG SAMA (bukan tab baru), memakai format `IDX:KODE`.

### Tab Performance
Menghitung performa transaksi RIIL dari sheet POSISI (bukan sheet terpisah yang harus
disinkronkan manual) - begitu ada posisi yang ditutup (WIN/LOSS/FORCE SELL) lewat tombol
"Cek TP/SL & Force-Sell" di tab Kandidat, tab Performance otomatis menampilkan: akumulasi profit,
profit per bulan (kartu hijau/merah), kurva ekuitas kumulatif, win rate, dan 10 transaksi
terbaik. Profit per bulan dihitung sebagai penjumlahan sederhana P&L(%) semua transaksi yang
closed di bulan itu (bukan compounding riil) - ditampilkan apa adanya, bukan diklaim sebagai
return portofolio sesungguhnya.

## Tab Jurnal Real (Transaksi Uang Beneran, Multi-Sekuritas)

Terpisah TOTAL dari Jurnal Backtest - supaya data simulasi tidak tercampur dengan transaksi asli.
Menggunakan koneksi Google Sheets yang SAMA (secrets yang sama, tidak perlu setup ulang), tapi
menulis ke 2 sheet baru yang **dibuat otomatis** kalau belum ada:
- **JURNAL_REAL** - log transaksi (Tanggal, Sekuritas, Saham, Setup, Entry, SL, Target, Lot, Exit, dst.)
- **SEKURITAS** - daftar broker Bro beserta biaya beli/jual masing-masing (tiap broker beda fee)

Cara pakai: tab **Catat Trade** untuk input posisi baru (form, tidak perlu edit spreadsheet manual),
tab **Tutup Posisi** untuk mencatat exit (otomatis hitung biaya sesuai fee broker itu, Net P/L, Return%),
tab **Performance Real** untuk lihat win rate/profit factor/total transaction value/max profit-loss/
top gainer per saham/kurva ekuitas, tab **Sekuritas** untuk kelola daftar broker & fee-nya, dan tab
**Edit/Hapus** kalau ada salah input (form edit isi ulang semua field, hitung ulang otomatis kalau
trade sudah closed) atau mau membatalkan pencatatan sepenuhnya (hapus permanen, ada konfirmasi dulu).

⚠️ **Jangan hapus baris di sheet JURNAL_REAL langsung dari Google Sheets** (nomor trade dipakai untuk
mencocokkan saat menutup posisi) - gunakan tombol Hapus di tab Edit/Hapus, bukan edit manual di sheet.

## Tab Equity (Tracking Modal per Sekuritas + Perbandingan IHSG)

Beda dengan Jurnal Real (yang mencatat TRANSAKSI per saham), tab ini mencatat **snapshot modal
keseluruhan** tiap sekuritas dari waktu ke waktu - kolom: Tanggal, Sekuritas, Total Equity (Rp),
Cash (Rp), Invested (Rp), Max Risk/Trade (%), Max Position/Stock (%).

Kenapa harus diisi manual (bukan otomatis)? Karena Total Equity riil = uang di RDN + nilai saham
yang dipegang, dan itu hanya diketahui Bro dari aplikasi sekuritas masing-masing - Yahoo Finance
tidak tahu isi rekening Bro. Rekomendasi: isi snapshot tiap akhir pekan atau akhir bulan per sekuritas.

Kalau punya beberapa sekuritas, isi snapshot masing-masing dengan nama Sekuritas yang sama persis
dengan yang dipakai di tab Jurnal Real (biar konsisten) - dashboard otomatis menjumlahkan semua
sekuritas jadi Total Equity gabungan (pakai forward-fill kalau salah satu broker belum diupdate
di tanggal tertentu, supaya total tidak drop palsu).

Grafik **Portofolio vs IHSG** membandingkan % return Total Equity gabungan Bro terhadap % return
IHSG (^JKSE) di periode yang sama, dimulai dari tanggal snapshot equity pertama Bro - supaya
perbandingannya adil (apple-to-apple, bukan dari titik awal yang beda).

## Chart TradingView (Klik Baris Tabel, Tanpa Tab Baru)

Semua tabel saham (Kandidat Terbaik, Semua Saham, Top 10 Day/Swing) sekarang bisa **diklik barisnya**
untuk memunculkan chart TradingView LIVE langsung di bawah tabel, di halaman yang sama - bukan link
yang membuka tab baru. Ini dipakai karena `column_config.LinkColumn` dengan `target="_self"` ternyata
tidak konsisten didukung semua environment Streamlit Cloud (pernah menyebabkan error) - solusi embed
langsung ini lebih pasti bekerja karena memang tidak ada navigasi/link sama sekali.

## Kalkulator Average Down / Average Up

Di tab Kalkulator, ada 2 mode:
- **Hitung Average** - masukkan posisi awal (harga & lot) + pembelian tambahan (harga & lot),
  langsung dapat harga rata-rata baru. Rumus tertimbang standar:
  `Avg Baru = (Modal Awal + Modal Tambahan) / (Lot Awal + Lot Tambahan)`
- **Simulasi Lot Tambahan** - kebalikannya: tentukan target harga rata-rata yang diinginkan, kalkulator
  hitung berapa lot yang perlu dibeli di harga tertentu untuk mencapainya.

⚠️ **Catatan risiko** (dari hasil riset best-practice): average down cuma masuk akal kalau fundamental
perusahaan masih baik dan penurunan harga bersifat sementara - bukan solusi otomatis untuk semua saham
yang turun. Sebagian besar praktisi menyarankan maksimal 2-3 kali averaging per saham, supaya satu
saham tidak mendominasi portofolio secara tidak proporsional.

## Auto-Backtest TANPA Buka Dashboard (GitHub Actions, Gratis)

**Masalah yang diselesaikan:** kalau dashboard web tidak dibuka, tombol Auto-BUY/Auto-SELL di tab
Jurnal Backtest tidak pernah tertekan otomatis, jadi sinyal bisa terlewat. Solusinya: jadwalkan
`auto_run.py` jalan sendiri lewat GitHub Actions - gratis, tidak perlu dashboard dibuka sama sekali.

**Jadwal default** (bisa diubah di `.github/workflows/auto_backtest.yml`):
- **09:15 WIB** - cek sinyal pagi (BPJS), buka posisi Swing baru
- **14:45 WIB** - cek sinyal sore (BSJP), cek TP/SL/force-sell semua posisi OPEN

Script ini memanggil fungsi **PERSIS SAMA** dengan tombol di dashboard (`screener.py`,
`gsheet_journal.py`) - bukan logika terpisah - supaya hasilnya selalu konsisten.

### Setup (5 menit)

1. Buka repo GitHub Bro → **Settings** → **Secrets and variables** → **Actions**
2. Klik **New repository secret**, beri nama `STREAMLIT_SECRETS_TOML`
3. Isi value-nya dengan **PERSIS SAMA** konten yang sudah Bro isi di Streamlit Cloud
   (Settings > Secrets) - tinggal copy-paste seluruh isinya (GOOGLE_SHEET_ID,
   `[gcp_service_account]`, TELEGRAM_BOT_TOKEN, dst.)
4. Klik **Add secret**
5. Buka tab **Actions** di repo → kalau ada banner "Workflows aren't being run", klik **"I understand
   my workflows, go ahead and enable them"**
6. Selesai. Workflow otomatis jalan sesuai jadwal - Bro akan dapat notifikasi Telegram setiap kali
   selesai jalan (kalau TELEGRAM_BOT_TOKEN/CHAT_ID sudah diisi).

### Uji Coba Manual (tanpa menunggu jadwal)

Buka tab **Actions** → pilih workflow **"Auto Backtest IDX Screener"** di sidebar kiri → klik
**"Run workflow"** → **"Run workflow"** (tombol hijau). Bisa dilihat prosesnya real-time, dan hasil
log lengkap tersimpan meski Bro tutup halamannya.

### Catatan

- GitHub Actions gratis untuk repo publik (unlimited), dan repo privat dapat 2.000 menit/bulan gratis -
  jadwal 2x/hari, 5 hari seminggu jauh di bawah batas itu (~sekitar 150-250 menit/bulan).
- Kalau workflow gagal (misal Yahoo Finance sedang bermasalah), GitHub otomatis kirim email
  pemberitahuan ke akun Bro - jadi tetap tahu kalau ada yang error.
- Jadwal di atas pakai UTC (`15 2 * * 1-5` = 09:15 WIB). Kalau mau ubah jam, edit file
  `.github/workflows/auto_backtest.yml`, ingat WIB = UTC+7.

## Backtest Historis (Validasi Rule Skor)

Beda dengan Jurnal Backtest di atas (yang forward-testing - mulai mencatat sinyal dari
sekarang ke depan), `backtest.py` menguji rule skor `screener.py` terhadap data HISTORIS
(mundur ke belakang). Ada DUA pertanyaan berbeda yang dijawab, jangan dicampur:

1. **Apakah skornya prediktif?** (`run_historical_backtest`) - return fixed-horizon N hari
   sesudah sinyal, dibandingkan LINTAS SEMUA jenis Signal (STRONG BUY, BUY, HOLD, SELL, dst.)
   dengan metrik yang sama. TANPA fee, TANPA TP/SL - exit-nya murni tanggal.
2. **Kalau beneran dieksekusi, untung bersih berapa?** (`run_realistic_backtest`) - simulasi
   trade nyata HANYA untuk sinyal yang benar-benar dibeli sistem live (STRONG BUY/BUY yang
   lolos RR minimum), pakai Entry/Target/Stop Loss Donchian yang sama seperti
   `build_trade_candidates()`, exit begitu TP/SL tersentuh atau force-sell kalau tidak,
   DIPOTONG fee round-trip (default 0.40%, sama seperti default broker di Jurnal Real).
   **Inilah yang harus dilihat untuk menjawab "apakah sistem ini profitable" - bukan #1.**

Jalankan lokal (butuh koneksi internet ke Yahoo Finance, JANGAN dijalankan otomatis di
dashboard supaya tidak boros quota):

```bash
pip install -r requirements.txt
python backtest.py --tickers BBCA,TLKM,ADRO,ASII,BMRI --years 3 --forward-days 10 --max-hold-days 10
```

Atau uji ke lebih banyak saham sekaligus (`--n` = jumlah saham pertama dari `tickers_idx.csv`):

```bash
python backtest.py --n 200 --years 3 --forward-days 10 --max-hold-days 10 --min-rr 2.0 --fee-pct 0.4
```

Output berupa DUA tabel ringkasan (satu untuk tiap pertanyaan di atas) plus dua file CSV
detail (`backtest_detail_*.csv` dan `backtest_realistic_*.csv`). Mekanisme walk-forward-nya
sudah diuji lewat unit test (`tests/test_backtest.py`) untuk memastikan tidak ada lookahead
bias - skor di titik waktu manapun HANYA dihitung dari data sampai titik itu.

**Catatan jujur soal keterbatasan backtest ini** (belum diperbaiki, harus disadari sebelum
percaya angkanya):
- **Survivorship bias**: `tickers_idx.csv` cuma berisi 615 saham yang aktif SEKARANG. Saham
  yang delisting/suspend dalam periode backtest tidak ikut diuji, jadi hasil historis bisa
  bias ke atas (lebih bagus dari kenyataan).
- **Tidak ada slippage**: fee sudah dipotong, tapi eksekusi riil di harga pasti TIDAK selalu
  bisa tepat di level Target/Stop Loss (gap, ARA/ARB, antrian order) - realisasi riil biasanya
  sedikit lebih buruk dari simulasi.
- Kalau sampel sinyal terlalu sedikit (saham ilikuid, periode pendek), Win Rate bisa terlihat
  ekstrem (0% atau 100%) padahal cuma kebetulan statistik - jangan percaya angka dari <30 trade.

### Hasil Validasi Parameter Default Saat Ini (Swing)

Parameter default LAMA (`score_buy=4`, `min_rr=2.0`, force-sell 10 hari, TANPA filter regime
IHSG) diuji lewat `run_realistic_backtest` di 615 saham/5 tahun **DAN** divalidasi
out-of-sample (split waktu 60% awal cari parameter, 40% akhir uji buta). Hasilnya: net RUGI
di periode out-of-sample (-152.9% dari 574 trade) meski kelihatan untung di periode yang
dipakai cari parameter (+401.1%) - overfitting klasik.

Parameter default SEKARANG (`score_buy=5`, `min_rr` Swing `=1.5`, force-sell Swing 15 hari,
DENGAN filter "hanya trading saat IHSG di atas MA50") net PROFIT di IS (+461.7%/415 trade)
*dan* OOS (+329.6%/308 trade), termasuk dengan pembatasan realistis "10 kandidat RR
tertinggi per hari" (+472.8% IS, +285.3% OOS).

**Stress-test lanjutan (multi-fold walk-forward + simulasi sequential no-overlap-per-saham)**
menunjukkan filter regime MA50 memperbaiki hasil di SEMUA 5 fold kronologis dibanding tanpa
filter sama sekali (baseline tanpa filter: net -667.9% sequential; dengan filter MA50: net
+673.4%) - bukti filter regime BENERAN bekerja, bukan kebetulan. Tapi robustness cek terhadap
MA100/MA200 menunjukkan hasil SENSITIF terhadap pilihan lookback: MA50 (selaras dengan
holding period 15 hari & Donchian lookback 20 hari) net positif dengan Sharpe-like 0.053;
MA200 (terlalu lambat bereaksi utk sistem short-holding ini) net NEGATIF di SEMUA fold
(-723.1%). **Kesimpulan jujur: ini edge yang nyata dan tervalidasi, tapi SEDANG (bukan
garansi profit)** - 2 dari 5 fold tetap rugi, keuntungan terkonsentrasi di beberapa fold,
dan "Max Drawdown" -369% adalah SUM return per-trade yang belum di-size (bukan drawdown
portofolio riil - kalau tiap trade cuma 5% modal, translate ke ±-18% drawdown riil).

**Filter regime IHSG ini HANYA divalidasi untuk Swing** (lookback Donchian 20 hari) - BELUM
diuji untuk Day Trading (lookback 10 hari, holding 1-2 hari), makanya Day Trading TIDAK
digate oleh kondisi IHSG dan tetap pakai `min_rr=2.0` yang lama. Kalau Bro mengubah parameter
manapun lewat sidebar/`DEFAULT_PARAMS`, angka-angka di atas tidak lagi berlaku - validasi
ulang dulu pakai `backtest.py` sebelum menganggap kombinasi baru itu aman.

**Catatan disiplin statistik**: JANGAN mencari-cari kombinasi parameter lain hanya dengan
melihat mana yang "menang" di backtest yang sama (itu data dredging lagi, persis kesalahan
yang menghasilkan parameter default LAMA di atas). Kombinasi baru manapun HARUS lolos
validasi out-of-sample (parameter dicari di satu periode, diuji BUTA di periode lain yang
tidak pernah dilihat) sebelum dipercaya. Kelola posisi dengan risiko kecil per trade (lihat
Kalkulator Manajemen Risiko) - ini alat bantu screening dengan edge sedang, bukan mesin uang.

## Penyempurnaan Tab ML Signal, Sentiment (Validasi & Perbaikan)

**ML Signal** (tab 🤖) awalnya diberi nama "ML Signal" tapi BUKAN model machine learning -
cuma ensemble rule-based (Trend+Momentum+Volume+Volatility). Nilai "Confidence"-nya dulu
rumus `agreement*25` yang tidak pernah divalidasi. Sekarang sudah diuji lewat backtest
walk-forward (615 saham x 5 tahun, forward return 10 hari, tanpa lookahead - metodologi
sama seperti Backtest Historis di atas): Score-nya TERBUKTI rank-order dengan return (makin
tinggi Score, makin tinggi rata-rata return), konsisten di IN-SAMPLE maupun OUT-OF-SAMPLE.
TAPI bahkan Score paling rendah rata-rata return historisnya masih POSITIF (karena drift
pasar umum) - jadi label "SELL"/"STRONG SELL" HARUS dibaca sebagai "relatif lebih lemah",
bukan "harga diprediksi turun". "Confidence" sekarang diganti Win Rate & Avg Return
HISTORIS asli dari backtest (`_ML_SIGNAL_BACKTEST_STATS` di `app.py`), bukan rumus karangan.
Tabel "Top 20" juga diperbaiki - dulu cuma scan 50 saham pertama dari `tickers_idx.csv`
(tidak terkait sinyal screener utama sama sekali, bug desain), sekarang scan semua saham
yang sedang di-load dan menandai kolom "Kandidat Utama" kalau saham itu juga lolos
Signal STRONG BUY/BUY di screener utama.

**Sentiment** (tab 📰): query NewsAPI diperbaiki dari `IHSG OR Indonesia stock` (terlalu
longgar - kena artikel PR global yang cuma kebetulan mengandung kata "stock" di boilerplate
disclaimer, tidak ada hubungan ke pasar modal Indonesia) menjadi query spesifik + dibatasi
ke domain berita finansial Indonesia resmi (`cnbcindonesia.com`, `kontan.co.id`, dst.) +
filter kata kunci relevansi tambahan sebelum ditampilkan. Kalau `NEWSAPI_KEY` belum diisi
atau API gagal, sekarang muncul peringatan jelas (dulu diam-diam pakai 3 berita contoh
hardcoded dengan timestamp palsu tanpa tanda apapun).

## Bug Produksi Tambahan yang Ditemukan & Diperbaiki (Babak 2)

- **2 `st.stop()` yang salah tempat** (Fundamental Screener kalau scan gagal/kosong, Jurnal
  Backtest kalau koneksi Google Sheets error saat tes) - keduanya menghentikan render SEMUA
  tab sesudahnya begitu terpicu, persis kategori bug yang sama dengan `sub3` NameError
  sebelumnya (cuma trigger-nya beda: rate-limit Yahoo / error koneksi, bukan Sheets belum
  diisi). Diperbaiki jadi `try/except/else` atau `if/else` biasa - error di satu tab tidak
  lagi mematikan tab lain. Dicek juga dengan `pyflakes` untuk pastikan tidak ada lagi
  variabel dipakai-tapi-tak-terdefinisi sejenis di seluruh file.
- **Time Cycle Gann + Fibonacci diuji historis** (IHSG 10 tahun, 154 pivot terdeteksi lewat
  metode fractal window) - hasilnya hit rate Gann (40.3%) dan Fibonacci (40.4%) SETARA hari
  acak (42.9%) dan baseline semua hari (42.6%). Artinya time cycle ini TIDAK terbukti lebih
  prediktif dari kebetulan untuk IHSG - UI sekarang menampilkan angka ini secara jujur di
  tab IHSG Analysis & Astronacci, bukan cuma disclaimer generik "bukan sains eksak".
- **`portfolio_risk_summary()` di `real_journal.py` ternyata fitur yatim** - sudah ditulis
  lengkap dengan dokumentasi (kenapa penting: menjumlahkan risiko SEMUA posisi OPEN, bukan
  cuma satu-satu) tapi TIDAK PERNAH dipanggil di UI manapun. Disambungkan sekarang ke tab
  **Equity > Ringkasan** (kartu "Risk Portofolio" dengan peringatan kalau risiko agregat
  >10-20% dari modal) dan preview live di tab **Jurnal Real > Catat Trade** sebelum trade
  baru disimpan.
- **Tombol "Execute Order"/"Catat ke Jurnal Saja" di tab Broker mengklaim mencatat ke Jurnal
  Real tapi TIDAK PERNAH benar-benar melakukannya** (`broker.place_order()` cuma placeholder
  string, tidak memanggil `rj.open_trade()` sama sekali) - order BUY yang di-"Execute" lewat
  tab ini hilang, tidak tercatat di manapun, padahal UI bilang "juga dicatat di Jurnal Real".
  Sekarang benar-benar memanggil `rj.open_trade()` (order SELL diarahkan ke tab Tutup Posisi
  karena perlu tahu posisi mana yang ditutup, tidak bisa otomatis dari form Quick Order).
- **`tutorial.py` mencantumkan angka "akurasi" KARANGAN** (Smart Money Flow 70-75%,
  Fibonacci Retracement 65-70%, Elliott Wave 60-65%, Gann Levels 55-60%) - tidak pernah
  dihitung dari data apapun, dan BERTENTANGAN LANGSUNG dengan temuan validasi Time Cycle di
  atas (Gann cuma 40.3%, setara acak). Dihapus, diganti peringatan jujur yang merujuk ke
  satu-satunya angka yang benar-benar diuji (Time Cycle). Rekomendasi parameter Swing Trading
  di tutorial juga diperbarui dari RR 2.5 (usang) ke RR 1.5 (default tervalidasi sekarang).

Audit tambahan (tab Performance, Fundamental > Perbandingan, Value Invest, Jurnal Real >
Edit/Hapus, Equity > Catat Snapshot) tidak menemukan bug sekelas ini - sudah cukup defensif
(cek `.empty`, fallback nilai, dsb). Dicek juga dengan `pyflakes` di seluruh `app.py` setelah
semua perbaikan - tidak ada lagi pola "variabel dipakai tapi tak terdefinisi" seperti `sub3`.

## Validasi Level Harga Gann Square of 9 (Beda dari Time Cycle)

Time Cycle (di atas) soal TANGGAL; Gann Square of 9 (Resistance/Support di tab IHSG
Analysis) soal LEVEL HARGA - beda klaim, diuji terpisah (IHSG 10 tahun, forward return 5
hari, level dihitung dari Close KEMARIN supaya tidak lookahead). Hasilnya:

- Menyentuh Resistance: avg forward return **+0.123%** (baseline semua hari +0.056%) -
  BUKAN turun/reversal seperti prediksi teori Gann, malah arahnya terbalik.
- Menyentuh Support: avg forward return **-0.004%** (baseline +0.056%) - BUKAN naik seperti
  prediksinya, juga terbalik.
- Level-level ini tersentuh **65.7% (Resistance) dan 54.5% (Support) dari SEMUA hari** -
  karena secara matematis levelnya selalu dekat harga kemarin (~0.3-2.5%), bukan level
  istimewa yang jarang terjadi.

Kesimpulan: level harga Gann Square of 9 TIDAK terbukti prediktif untuk IHSG, sama seperti
Time Cycle-nya. UI sekarang menampilkan temuan ini di tab IHSG Analysis.

## Reliabilitas & Position Sizing (Fitur Baru)

**Retry + backoff Yahoo Finance** (`fetch_price_history` di `screener.py`): dulu kalau satu
chunk (80 saham) gagal diambil (rate-limit/timeout - sering & transient di yfinance), kodenya
`except: continue` diam-diam - saham di chunk itu hilang dari hasil scan TANPA ada yang tahu,
seolah scan-nya lengkap. Sekarang retry otomatis sampai 3x dengan backoff (2s, 4s) sebelum
menyerah, dan fungsi ini return `(hasil, daftar_saham_gagal)` - dashboard menampilkan expander
peringatan "N saham gagal diambil" kalau ada yang tetap gagal setelah retry, `auto_run.py` dan
`backtest.py` mencatatnya di log. **Ini mengubah signature fungsi** (dulu return dict saja,
sekarang return tuple) - kalau Bro punya skrip sendiri yang import `fetch_price_history`,
sesuaikan jadi `price_data, failed = fetch_price_history(...)`.

**Position sizing berbasis risiko** (`build_trade_candidates` di `screener.py`): dulu Lot
Auto-BUY di Jurnal Backtest selalu 10 lot flat untuk SEMUA saham, tidak peduli harga saham
atau modal Bro - beli 10 lot saham Rp50.000 (Rp50 juta) diperlakukan sama dengan 10 lot saham
Rp200 (Rp200 ribu), padahal risikonya beda jauh. Sekarang kalau tab **Equity** sudah ada
snapshot terbaru, Lot dihitung otomatis dari `Risiko per Trade (%)` (default 1%, atur di
sidebar) dibagi jarak Entry-Stop Loss saham itu - sama seperti rumus di Kalkulator Manajemen
Risiko, tapi otomatis dipakai saat auto-buy, bukan cuma alat terpisah. Kalau hasil hitungnya
kurang dari 1 lot (jarak Entry-SL terlalu lebar utk risk budget), saham itu DILEWATI sepenuhnya
- bukan fallback ke 10 lot (itu justru melanggar batas risiko yang diminta). Kalau belum ada
snapshot Equity, tetap fallback ke lot default lama (10) seperti sebelumnya - tidak ada
perubahan perilaku kalau fitur ini belum "diaktifkan" (lewat isi snapshot Equity).

## Grafik IHSG Lebih Terbaca + Index Utama & Kinerja Sektor (Fitur Baru)

- **Grafik IHSG di tab IHSG Analysis dulu sumbu Y-nya mulai dari 0** (`fill='tozeroy'` pada
  trace harga memaksa Plotly autorange turun ke 0), padahal pergerakan riil IHSG cuma di
  rentang 5.000-7.200 - jadinya grafik jadi pita tipis di bagian atas dan level Gann/pivot
  sulit dibaca. Sekarang sumbu Y di-zoom eksplisit ke rentang harga + level Gann + pivot
  (padding 5%), sama seperti standar chart trading (TradingView/Bloomberg tidak mulai dari 0
  untuk index/harga).
- **Kartu Index Utama** (IHSG, LQ45, JII) ditambahkan di bawah banner status IHSG - harga
  close + perubahan harian, dari Yahoo Finance (`fetch_index_snapshot()` di `screener.py`).
  **IDX30 dan SRI-KEHATI TIDAK dimasukkan** - sudah dicoba beberapa kemungkinan simbol Yahoo
  Finance (`^IDX30`, `^JKIDX30`, `^JKSRI`, `IDX30.JK`) dan semuanya 404/kosong, tidak ada
  jalan gratis yang ditemukan untuk keduanya.
- **Kartu Kinerja Sektor** (expander di bawah Market Health) - menampilkan SEMUA sektor yang
  muncul di saham yang dipindai (bukan cuma sebagian/top-N), rata-rata "Perubahan %" antar
  saham per sektor + jumlah saham anggotanya, diurutkan dari yang paling naik. **Update:**
  sejak perbaikan universe saham di bawah, sektornya dari klasifikasi IDX-IC resmi (statis,
  instan) - bukan lagi fetch Yahoo Finance opt-in seperti versi awal fitur ini.

**Bug produksi dari fitur ini, ditemukan & diperbaiki sehari setelah rilis**: versi awal
`fetch_index_snapshot()` fetch ulang `^JKSE` sendiri (padahal `fetch_ihsg_history()` sudah
fetch simbol yang sama di tempat lain) - dobel request ke Yahoo Finance untuk simbol yang
sama di setiap load dashboard bikin salah satu panggilan lebih sering kena rate-limit,
sampai suatu saat `fetch_ihsg_history()` pulang DataFrame kosong. `volatility_regime()`
(tab sidebar "Volatility Regime") ternyata tidak pernah menjaga kasus DataFrame kosong ini
(`df['Close'].iloc[-1]` langsung tanpa cek) - jadi `IndexError: single positional indexer
is out-of-bounds` yang mematikan seluruh dashboard begitu rate-limit itu terjadi. Diperbaiki
dua arah: (1) `fetch_index_snapshot()` sekarang menerima `ihsg_hist` yang sudah ada sebagai
parameter alih-alih fetch baru - IHSG tidak lagi dobel request, cuma LQ45 & JII yang benar-benar
request baru; (2) `volatility_regime()` ditambah guard `if df is None or df.empty or
len(df) < period + 1: return None` - konsisten dengan pola fungsi sejenis lain
(`market_regime`, `analyze_ihsg_gann`) yang sudah menjaga kasus ini sejak awal.

## Universe Saham Diperbaiki: 615 → 962 Saham (BUG BESAR Ditemukan & Diperbaiki)

**Temuan**: `tickers_idx.csv` (daftar saham yang dipindai dashboard) ternyata **TIDAK
PERNAH memuat satu pun saham perbankan konvensional** - dicek 33 kode bank yang dikenal
luas (termasuk **BBCA, BBRI, BMRI, BBNI** - 4 perusahaan terbesar di seluruh Bursa Efek
Indonesia dari sisi kapitalisasi pasar), SEMUANYA tidak ada di file. Yang lolos cuma 4 bank
syariah kecil (BANK, BRIS, BTPS, PNBS). Dicek lagi ke 20 perusahaan asuransi/multifinance
konvensional (ADMF, BFIN, PNIN, dst) - 19 dari 20 juga tidak ada.

**Akar masalah**: `tickers_idx.csv` ternyata daftar saham SYARIAH (mirip ISSI), bukan
universe IDX penuh - sementara UI dashboard ("615 saham", "Semua saham") memberi kesan itu
cakupan penuh pasar. Akibatnya screener, Kandidat, Top 10, dan statistik Market Breadth
**selalu kehilangan seluruh sektor perbankan konvensional** (bank terbesar sekalipun) sejak
app ini pertama dibuat.

**Perbaikan**: `tickers_idx.csv` diganti total, dibangun dari dokumen RESMI Bursa Efek
Indonesia (bukan scraping/tebakan):
- Daftar lengkap 962 saham tercatat + 11 breakdown sektor IDX-IC resmi (Energy, Basic
  Materials, Industrials, Consumer Non-Cyclicals, Consumer Cyclicals, Healthcare,
  Financials, Properties & Real Estate, Technology, Infrastructures, Transportation &
  Logistic) - jumlahnya pas 962, tanpa saham bocor atau dobel sektor.
- Pengumuman BEI ISSI Mei 2026 (Peng-00089/BEI.POP/05-2026) - 649 saham anggota resmi
  Indeks Saham Syariah Indonesia, sisanya (313 saham) ditandai Konvensional.
- File sekarang punya 4 kolom: `Kode, Nama, Sektor, Syariah` (dulu cuma `Kode, Nama`).

**Dampak ke kode**:
- `sectors.py` ditulis ulang total - klasifikasi sektor sekarang lookup instan dari kolom
  `Sektor` resmi (statis, 100% saham tercakup), BUKAN lagi fetch live ke Yahoo Finance
  `.info` per saham (lambat, opt-in, cuma pendekatan kasar taksonomi GICS). Checkbox
  "🏷️ Aktifkan Filter Sektor" di sidebar **dihapus** - filter sektor & kartu Kinerja Sektor
  sekarang selalu aktif tanpa perlu diaktifkan manual (karena sudah instan, tidak ada lagi
  alasan opt-in).
- Kartu baru **"☯️ Syariah vs Konvensional"** (expander, di bawah Kinerja Sektor) -
  Market Breadth dipecah per kelompok syariah/konvensional (rata-rata Perubahan %, jumlah
  naik/turun), supaya kelihatan kalau pergerakan pasar hari ini lebih ditopang salah satu
  kelompok - bukan cuma angka gabungan yang menyembunyikan perbedaan itu.
- Slider "Jumlah saham dipindai" (sidebar) ditambah opsi **962** (dulu maksimum 615).
  `auto_run.py` (`N_SCAN`) ikut diperbarui ke 962.

**Risiko yang perlu diperhatikan**: 962 saham = ~56% lebih banyak request ke Yahoo Finance
dibanding 615 - lebih rawan rate-limit (2 insiden serupa sudah terjadi sesi ini). Default
slider TETAP 200 (bukan otomatis 962) - retry+backoff yang sudah ada (lihat bagian
"Reliabilitas & Position Sizing") tetap jalan kalau Bro pilih scan lebih besar.

**Catatan pemeliharaan**: klasifikasi IDX-IC & keanggotaan ISSI dievaluasi ulang BEI tiap 6
bulan (Mei & November). Kalau `tickers_idx.csv` sudah lebih dari ~6 bulan, unduh ulang
dokumen terbaru dari idx.co.id dan minta diproses ulang - bukan sekali dibangun lalu selesai
selamanya.

**Filter Universe Saham** (sidebar) - dropdown baru "Universe Saham" (Semua / Syariah (ISSI)
/ Konvensional) supaya Bro bisa memindai cuma saham syariah atau cuma konvensional saja
kalau perlu, bukan cuma "semua atau tidak sama sekali". Filter ini menentukan saham APA yang
DIPINDAI (bukan cuma disembunyikan di tampilan) - jadi juga mengurangi jumlah request ke
Yahoo Finance kalau Bro pilih salah satu subset.

## Bug Kritis: Baris Harga "Hantu" (OHLC NaN, Volume Terisi) Meracuni Hampir Semua Fitur

**Ditemukan dari laporan user**: tab Kandidat & Semua tiba-tiba cuma menampilkan opsi filter
"⏸️ WAIT" + "⚠️ MODERATE" (SWING TRADE/DAY TRADE/HIGH quality hilang semua), dan Market
Health tiba-tiba bilang "0↑ 0↓ 21 tetap (dari 21 saham)" padahal 194 saham berhasil diambil.

**Akar masalah**: Yahoo Finance kadang mengirim baris TERAKHIR dengan **OHLC semua NaN
tapi Volume terisi** (data sesi terbaru belum settle sempurna di sisi Yahoo - paling sering
kejadian dini hari sebelum bursa buka). `dropna(how="all")` di `_fetch_price_history_cached_v2`
(`screener.py`) TIDAK menangkap baris ini karena "all" cuma trigger kalau SEMUA kolom NaN -
Volume yang terisi bikin baris sampah ini lolos. Akibatnya `df['Close'].iloc[-1]` jadi NaN
untuk **173 dari 200 saham** (87%!) secara serentak - meracuni Score/Signal/Quality di
`compute_metrics()`, Market Breadth, RR di tab Kandidat, dan kemungkinan tempat lain yang
pakai `.iloc[-1]` tanpa cek NaN. Reproduksi manual: `total_valid` breadth turun dari ~194
jadi 21, dan mayoritas kandidat jatuh ke klasifikasi WAIT/MODERATE default krn harga
"sekarang"-nya secara teknis tidak valid.

**Fix**: tambah `df.dropna(subset=["Close"])` SESUDAH `dropna(how="all")` - dibuang di
SUMBER-nya (`_fetch_price_history_cached_v2`), bukan ditambal satu-satu di tiap fungsi yang
memakai harga terbaru. Diverifikasi: reproduksi ulang dgn 200 saham pertama, `total_valid`
breadth balik ke 194 (cuma 6 saham dgn histori genuinely tipis/suspend yang tersisa
dikecualikan), Market Health & Filter Trading kembali normal (DAY TRADE/SWING TRADE/HIGH
muncul lagi), tanpa exception.

**Kolom "Tanggal Harga" (Fitur Baru)** - laporan user lanjutan: harga MLPT di tab Kandidat
nunjukin Rp1.925 padahal closing riil sudah Rp1.740. Dicek langsung ke data mentah Yahoo
Finance: MLPT/MDIA memang belum di-update Yahoo utk closing hari terakhir saat itu (lag data
di sisi Yahoo, bukan bug yang bisa diperbaiki dari kode kita - saham mid/small-cap sering
lebih lambat update dibanding saham besar). Supaya user tidak mengira "Harga"/"Entry" selalu
live hari ini, ditambah kolom **"Tanggal Harga"** di tab Kandidat & Semua (dari
`compute_metrics()` - tanggal baris valid TERAKHIR yang benar-benar dipakai) - kalau
tanggalnya bukan hari ini, itu tanda datanya lag, bukan error di app.

**Default "Jumlah saham dipindai" naik 200 → 400** - laporan user: Kandidat makin sedikit,
Top 10 kosong. Dicek: BUKAN dari kolom Tanggal Harga (itu cuma tampilan) - di 200 saham
alfabetis pertama, **133/194 (68,5%) kena SKIP (ILIKUID)**, tersisa cuma 1 STRONG BUY/0 BUY,
Kandidat Day & Swing jadi kosong total. Sejak universe diperluas ke 962 saham resmi BEI,
proporsi saham tidak likuid ikut naik - sample 200 alfabetis jadi terlalu kecil. Dicoba naikkan
ke 400: STRONG BUY jadi 2, BUY jadi 2, Kandidat Day & Swing masing-masing muncul 1. Default
dinaikkan ke 400 (bisa tetap diturunkan manual via slider kalau mau load lebih cepat).

## Validasi Siklus Planet (Sun-Jupiter Cycle, Venus Synodic, dst - gaya Astronacci/Eye of Future)

User menonton video kreator finansial yang percaya diri memprediksi titik balik IHSG/gold/
bitcoin lewat siklus planet (heliocentric synodic cycle), dengan klaim "terbukti sejalan
bertahun-tahun". Diuji dengan metodologi PERSIS SAMA seperti Time Cycle Gann/Fibonacci di atas
(IHSG 10 tahun, 154 pivot fractal window) - cuma cycle days-nya diganti periode SINODIK planet
asli (angka astronomi standar, bukan reka-reka): Mercury 115.88 hari, Venus 583.92, Mars
779.94, Jupiter 398.88, Saturn 378.09, Uranus 369.66, Neptune 367.49 (dikonversi ke hari
bursa).

**Hasil: hit rate 40.7%** - SETARA kontrol hari acak (42.8%) dan baseline semua hari (42.6%),
persis pola yang sama dengan Gann (40.3%) dan Fibonacci (40.4%). Siklus planet TIDAK terbukti
lebih prediktif untuk IHSG - strike ke-4 untuk kategori "time cycle" setelah Gann, Fibonacci,
dan cross-sectional momentum/rotasi sektor yang juga sudah diuji dan gagal (lihat bagian
eksplorasi pola dagang).

**Kesimpulan yang disampaikan ke user**: testimoni "terbukti membantu hindari bearish market"
kemungkinan besar bukan karena keakuratan siklus planetnya secara spesifik, tapi karena nasihat
umum "hindari beli saat market turun panjang" itu benar dan berguna - dan itu bisa dicapai
dengan cara yang jauh lebih sederhana & sudah tervalidasi statistik di app ini (filter regime
IHSG > MA50), bukan perlu siklus planet. Presenter yang menggambar kotak prediksi di sekitar
titik yang SUDAH terjadi (bukan diverifikasi independen sebelum kejadian) adalah pola
confirmation bias klasik, bukan bukti prediktif.

**Tetap dibangun** (fitur baru "🪐 Siklus Planet (Synodic)" di tab Astronacci) atas permintaan
eksplisit user - sesuai prinsip "jangan hapus fitur eksploratif, buat jujur" yang sudah
diterapkan ke Gann/Fibonacci/ML Signal: ditampilkan APA ADANYA dengan disclaimer jujur di atas
tabel (bukan disembunyikan atau dihapus), supaya user (yang mengaku masih baru belajar di
market) bisa tetap mengamati siklusnya sebagai referensi eksploratif, dengan ekspektasi yang
benar soal keakuratannya.

## Bug Kritis: Posisi OPEN di Luar Window Scan TIDAK PERNAH Bisa Ditutup

**Laporan user**: tombol "Cek TP/SL & Force-Sell" (manual maupun otomatis - dua-duanya
memanggil fungsi yang sama) tidak bisa menutup posisi tertentu, berapa lama pun ditunggu.

**Akar masalah**: `auto_close_positions(price_lookup)` di `gsheet_journal.py` cuma bisa
mengecek TP/SL/force-sell untuk saham yang harganya ADA di `price_lookup` - yang dibangun
dari `table` hasil scan dashboard SAAT ITU (dibatasi "Jumlah saham dipindai", default
alfabetis dari 962 saham). Kalau saham posisi OPEN itu di luar batch yang baru dipindai,
`price_lookup.get(kode)` return `None` dan kode langsung `continue` (skip) - posisi itu
TIDAK PERNAH dicek lagi, walau sudah jauh lewat TP/SL/batas hari force-sell-nya. Dicek
langsung ke sheet POSISI user: **9 dari 14 posisi OPEN saat itu (FILM, ADMR, BELL, GPSO,
FWCT, NICL, TOBA, MBMA, PANI) berada di luar window scan default (400 dari 962 saham)** -
selamanya tidak bisa ditutup otomatis maupun manual, karena keduanya pakai `price_lookup`
yang sama.

**Fix**: `auto_close_positions()` sekarang cari SENDIRI saham OPEN yang tidak ada di
`price_lookup` yang diberikan, fetch harga tambahan khusus untuk itu (`fetch_price_history()`
dari `screener.py`, cuma utk saham yang perlu - bukan fetch ulang semuanya), baru lanjut
proses pengecekan TP/SL/force-sell utk SEMUA posisi OPEN, bukan cuma yang kebetulan masuk
scan. Kalau fetch tambahan itu sendiri gagal (mis. rate-limit), tidak crash - lanjut dgn
apa yang sudah ada.

Test baru (`tests/test_gsheet_journal.py`, 6 test, mock Google Sheets & fetch harga):
memverifikasi saham di luar `price_lookup` tetap ter-fetch & tercek, saham yang sudah ada
di `price_lookup` tidak perlu fetch ulang (efisien), dan kegagalan fetch tambahan tidak
bikin seluruh fungsi crash.

**Follow-up fix**: setelah fix di atas dipush, user lapor tabel debug "Posisi yang dicek"
di tombol "Cek TP/SL & Force-Sell" MASIH menampilkan "N/A" utk saham yang sama - ternyata
tabel debug itu baca `price_lookup` MENTAH (dari caller di `app.py`), BUKAN versi yang sudah
dilengkapi di dalam `auto_close_positions()` - dua sumber data berbeda, jadi user melihat
"N/A" yang menyesatkan padahal logika penutupan sebenarnya (di baliknya) sudah benar.
Diperbaiki dengan mengekstrak logika pelengkapan itu jadi fungsi terpisah
`enrich_price_lookup()`, dipakai BARENG oleh tabel debug DAN `auto_close_positions()` -
supaya apa yang user lihat konsisten dgn apa yang sistem pakai untuk memutuskan. Sekaligus
tombol "Buka Posisi Day/Swing" & "Cek TP/SL" direstruktur - hasilnya (termasuk tabel debug)
sekarang dirender di LUAR kolom 3-tombol (lebar penuh halaman), dulu kejepit di 1/3 lebar
halaman.

## Bug Kritis: Timestamp Jurnal Backtest Tercatat Jam UTC, Dikira Jam WIB

**Laporan user**: posisi baru di sheet POSISI tercatat "Tanggal Open" jam 05:26, terasa
tidak wajar ("barangkali jamnya salah").

**Akar masalah**: `open_positions_from_candidates()` dan `auto_close_positions()` di
`gsheet_journal.py` menulis timestamp pakai `datetime.now()` POLOS (tanpa timezone) -
server (Streamlit Cloud/GitHub Actions) jalan di UTC, jadi jam yang tercatat 7 jam lebih
awal dari WIB sebenarnya ("05:26" yang tercatat itu sebenarnya 12:26 WIB). Ini KELAS BUG
YANG SAMA dengan yang sudah diperbaiki di `get_market_session()` (`app.py`) sebelumnya,
tapi belum pernah diterapkan ke `gsheet_journal.py` - modul yang justru paling sering
menulis timestamp ke data permanen (sheet POSISI).

**Fix**: tambah `WIB = ZoneInfo("Asia/Jakarta")` di `gsheet_journal.py`, dipakai di
`datetime.now(WIB)` utk kolom "Tanggal Open" & "Tanggal Close", dan dikonversi konsisten
(`.replace(tzinfo=None)`) utk hitungan "Hari" di `auto_close_positions()` (perbandingan
dgn `Tanggal Open` yang juga naive). Dicek juga `real_journal.py` & `equity.py` - keduanya
TIDAK punya bug serupa (tidak pakai `datetime.now()` polos utk timestamp permanen).

**Catatan**: baris yang SUDAH ada di sheet SEBELUM fix ini tetap mencerminkan jam UTC lama
(selisih ~7 jam lebih awal dari WIB sebenarnya) - fix ini cuma berlaku ke depan, data lama
tidak diubah otomatis (berisiko kalau ditimpa tanpa verifikasi manual per baris).

Test baru (`tests/test_gsheet_journal.py`, 2 test): verifikasi `WIB` = zona waktu
`Asia/Jakarta` yang benar, dan timestamp yang ditulis `open_positions_from_candidates()`
memang dekat dengan jam WIB saat ini (bukan UTC).

## Efek Musiman IHSG (Seasonality) - Fitur Baru, Beda Kelas dari Gann/Astronacci

User menonton video YouTube yang mengklaim "Juli selalu hijau/bullish untuk IHSG tiap
tahunnya". Diuji dulu ke data harga IHSG asli **36 tahun** (1990-2026, via
`yf.download(period="max")` - bukan 10 tahun spt uji Gann/Astronacci sebelumnya, krn data
musiman butuh sampel sebanyak mungkin) sebelum dipercaya atau dibangun jadi fitur.

**Hasil**: klaim "selalu hijau" TERBUKTI BERLEBIHAN (12 dari 37 Juli justru merah, termasuk
-9,8% di 1996 dan -9,7% di 1999) - TAPI ada tendensi nyata: Juli memang salah satu bulan
terkuat (67,6% tahun hijau, rata-rata +1,7%), walau **Desember justru lebih kuat lagi**
(86,1% hijau, rata-rata +3,8%). Ini BEDA KELAS dari Gann/Fibonacci Time Cycle & siklus
planet Astronacci yang sudah diuji dan gagal - efek musiman ini pola NYATA dari data harga
historis asli (dikenal luas di literatur keuangan sbg "efek kalender"), bukan numerologi.
Tapi tetap cuma tendensi PROBABILISTIK (~50-86% tergantung bulan), bukan garansi, dan
sampel per bulan kalender cuma puluhan titik data (jangan dianggap presisi statistik kuat).

**Fitur baru**: `ihsg_seasonality()` di `screener.py` - resample harga bulanan, hitung
rata-rata return + win rate per bulan kalender dari histori sebanyak yang tersedia.
Ditampilkan di tab **IHSG Analysis** (bagian akhir): kartu "Bulan Ini" (highlight status
historis kuat/lemah/netral bulan berjalan) + tabel 12 bulan lengkap dgn baris bulan-ini
disorot. **SENGAJA TIDAK dimasukkan ke logika Score/Signal/Rekomendasi sistem** - ini
referensi tambahan untuk pertimbangan user sendiri, beda dgn filter regime IHSG > MA50
yang sudah divalidasi ketat lewat backtest realistis + out-of-sample sbg bagian dari
strategi trading aktif.

Test baru (`tests/test_screener.py`, 5 test, data sintetis terkontrol): verifikasi
avg_return & win_rate dihitung persis benar (bukan cuma "jalan tanpa error"), urutan bulan
Jan-Des, dan guard data kosong/terlalu pendek.

**Follow-up - Uji Signifikansi**: user langsung menangkap kelemahannya sendiri ("apakah
sample per bulan tidak dibuat menyeluruh agar lebih valid?"). Jawabannya BUKAN "pool semua
saham jadi ribuan titik data" (itu keliru - 600+ saham bergerak BARENG index di bulan yang
sama, jadi bukan sampel independen, cuma menyamarkan N kecil yang sebenarnya) - tapi 2 uji
tambahan, metodologi SAMA dgn yg sudah dipakai utk Gann/momentum/rotasi sektor sesi ini:

1. **t-test 1-sample** (H0: rata-rata bulan itu = 0) per bulan. Hasil aktual (36 tahun):
   cuma **Desember (p<0.001, kuat)** dan **Juli (p=0.052, marginal)** yang lolos ambang
   signifikan - **10 bulan lain TIDAK beda dari nol secara statistik**, walau win rate
   mentahnya kelihatan tinggi di beberapa (mis. Januari 61% tapi p=0.122 - bisa kebetulan).
2. **Split-half** (paruh 1990-2007 vs 2008-2026) - cek konsistensi ARAH rata-rata. Desember
   konsisten (+4.7% & +2.9%, dua-duanya positif, win rate 83%/89%). **Juli TIDAK konsisten**
   (-0.1%/win rate 50% di paruh pertama vs +3.5%/84% di paruh kedua) - efek "Juli hijau"
   ternyata SELURUHNYA ditarik oleh 18 tahun terakhir, bukan pola sepanjang sejarah 36 tahun.

Kolom "Signifikansi" (p-value + status: 🟢 Signifikan & konsisten / 🟡 Marginal/tidak
konsisten / ⚪ Tidak signifikan) ditambahkan ke tabel & kartu "Bulan Ini" di dashboard,
supaya user langsung lihat mana yang benar-benar valid statistik, bukan cuma angka mentah.
2 test tambahan (93 total): verifikasi p_value terhitung & split_half_konsisten sesuai
arah data sintetis yang dikontrol.

## Scanner Lonjakan Volume (gaya "Tria") - Fitur Baru

User menunjukkan screenshot scanner eksternal (berdagangangka.id) yang punya kolom "Tria"
(dicari yang >1) + "Range (%)" + "AvgValTrx". Dicek: konsepnya **sudah ada** di sistem ini
sejak awal - "Volume Ratio" (Volume hari ini ÷ rata-rata Volume 20 hari) sudah dihitung &
bahkan sudah masuk Score (`vol_ratio > 1` = +2 poin, `>1.5` = +3 poin, `>3` = +2 poin
tambahan). **CATATAN JUJUR**: formula "Tria" mereka proprietary (tidak dipublikasikan) -
tidak bisa dipastikan identik; kemungkinan mereka pakai basis Value Traded (Rupiah), bukan
Volume (lembar saham) seperti di sini.

Ditambahkan 2 hal:
1. **"Range %"** - kolom baru di `compute_metrics()` (`screener.py`): rentang High-Low
   HARI ITU sbg % Close (beda dari ATR yang rata-rata N hari) - kolom ini yang belum ada
   sebelumnya, sekarang ada di tabel "Semua" dan scanner baru.
2. **Expander "🔥 Scanner Lonjakan Volume"** di tab Semua - 2 panel (Naik + Volume Tinggi /
   Turun + Volume Tinggi), filter Volume Ratio > 1 (meniru filter mereka), sortir descending
   by Volume Ratio, tampil Kode/Nama/Harga/Perubahan %/Range %/Volume Ratio/Value Traded.
   **SENGAJA TIDAK dimasukkan ke Score/Signal** - ini penyaring awal ("saham lagi ramai"),
   belum divalidasi sbg strategi trading tersendiri (beda dgn Volume Ratio yang sudah lama
   jadi bagian Score yang tervalidasi).

## Bug Kritis: Tab Kandidat Menampilkan Entry/SL/Target yang BELUM Divalidasi

User bertanya langsung: **"apakah sistem kita (tab Kandidat) sudah pernah dilakukan
backtest?"** Jawaban jujurnya waktu itu: **tidak sepenuhnya**.

**Yang SUDAH divalidasi** (backtest 5 tahun + out-of-sample, lihat "Backtest Historis"):
Score/Signal (STRONG BUY/BUY, ambang score_buy=5) + fungsi `build_trade_candidates()` yang
dipakai tab **Top 10** & **Backtest** - Stop Loss = Donchian Low murni, difilter RR minimum,
Swing digate regime IHSG.

**Yang TIDAK divalidasi** (baru ditemukan di tab Kandidat versi lama):
1. Kolom **"Rekomendasi"** (WAIT/SWING/DAY/AVOID) - dari sistem skor TERPISAH (Quality/Smart
   Money/Momentum), tidak pernah dibacktest.
2. **Stop Loss** dihitung dgn formula BEDA dari yang divalidasi - tab Kandidat pilih yg PALING
   KETAT dari (Donchian Low, MA20, atau 10% di bawah entry), sedangkan backtest yang
   divalidasi cuma pakai Donchian Low murni. Entry/Target/SL/RR yang ditampilkan **berbeda**
   dari yang dibuktikan profitable di backtest.
3. Tab Kandidat **tidak memfilter RR minimum** - semua STRONG BUY/BUY ditampilkan apa
   adanya, beda dari `build_trade_candidates()` yang membuang kandidat RR di bawah ambang.

**Fix**: tab Kandidat sekarang REUSE `cands_day_all`/`cands_swing_all` (dihitung dari
`build_trade_candidates()` yang SAMA persis dipakai tab Top 10/Backtest) - bukan hitung
ulang formula sendiri. Kandidat yang tidak lolos RR/regime **otomatis tidak muncul** lagi
(dulu tetap ditampilkan tanpa filter) - caption baru menjelaskan berapa saham yang "gugur"
dan kenapa. Kolom **"Tipe"** (SWING TRADE/DAY TRADE, warna sesuai yang lolos) menggantikan
peran "Rekomendasi" sbg penanda utama yang SUDAH divalidasi - "Rekomendasi"/Quality tetap
ditampilkan sbg info tambahan, tapi dilabeli jelas "belum divalidasi" di UI & caption.

Diverifikasi: reproduksi manual - dari 17 saham Signal STRONG BUY/BUY, cuma **5** yang lolos
kriteria RR/regime yang divalidasi (BKSL/ANTM Swing, ENRG/BRMS/BUMI Day) - Entry/Target/SL
persis sama dgn yang dihasilkan `build_trade_candidates()`. Dicek live (n_scan berbeda):
caption "22 saham tidak lolos..." tampil benar, filter Tipe & Quality berfungsi, tanpa
exception.

## Regresi: Fix di Atas Ternyata Pakai Formula Stop Loss yang LEBIH BURUK

Setelah fix di atas jalan live, user langsung sadar ada yang aneh: jumlah kandidat jauh lebih
sedikit dari sebelumnya, dan salah satu (KDTN) punya **Risiko% = 42.9%** - tidak masuk akal
untuk dibeli. User bertanya langsung: **"apakah tidak sebaiknya keduanya di backtest, boleh
jadi yang sebelumnya lebih baik"** - dan curiga versi LAMA (formula capped: paling ketat dari
Donchian Low/MA20/10% cap) justru lebih baik dari versi "tervalidasi" (Donchian Low murni)
yang baru dipasang.

**User benar, saya salah.** Klaim "yang divalidasi backtest = Donchian Low murni" di bagian
atas cuma didasarkan pada dokumentasi lama tanpa pernah menguji langsung formula ALTERNATIF
(capped) head-to-head. Dibuat 2 skrip perbandingan langsung (data 615 saham x 5 tahun +
histori IHSG penuh, walk-forward tanpa lookahead), satu tanpa filter regime, satu DENGAN
filter regime IHSG>MA50 (apple-to-apple dgn cara Swing sebenarnya digate):

**Tanpa filter regime:**
| SL Mode | Trade | Win Rate | Avg Return | Total Return | Risiko% avg/max | Risiko%>20% |
|---|---|---|---|---|---|---|
| Donchian murni | 1303 | 35.8% | -0.85% | **-1110.2%** | 16.4% / 75.5% | 27.4% |
| **Capped** | 3044 | 31.3% | +0.64% | **+1958.0%** | 7.6% / 10.0% | 0.0% |

**Dengan filter regime IHSG>MA50:**
| SL Mode | Trade | Win Rate | Avg Return | Total Return | Risiko% avg/max | Risiko%>20% |
|---|---|---|---|---|---|---|
| Donchian murni | 723 | 39.0% | +1.09% | +791.3% | 15.9% / 65.6% | 25.4% |
| **Capped** | 1941 | 33.5% | +1.56% | **+3024.6%** | 7.7% / 10.0% | 0.0% |

Capped menang di **SEMUA** metrik, di kedua skenario - bukan cuma menang tipis. Donchian
murni bahkan **rugi total** (-1110.2%) tanpa filter regime karena beberapa saham punya
Donchian Low yang jauh di bawah entry (channel lebar/gappy), menghasilkan Risiko% sampai
75.5% per trade - satu-dua kali kena SL saja sudah menghapus banyak trade untung kecil.
Formula capped **membuang** entry semacam itu (dibatasi 10% di bawah entry) sehingga jumlah
trade justru lebih banyak (lebih sering RR-nya masih ≥ ambang minimum karena Target tetap
sama tapi Risk lebih kecil) dan hasilnya jauh lebih konsisten (Risiko% tidak pernah lebih dari
10%, vs Donchian murni yang bisa sampai 75.5%).

**Fix**: `build_trade_candidates()` (screener.py) dan `_simulate_realistic_trades_single()`
(backtest.py) **dikembalikan ke formula capped** - SL = MAX (paling ketat/paling dekat entry)
dari (Donchian Low, MA20, 10% di bawah entry), asal masih < entry. Kedua fungsi disamakan
lagi (dulu backtest.py cuma pernah pakai Donchian murni, sekarang keduanya capped) supaya
backtest ke depan menguji formula yang SAMA dengan yang dipakai live. 3 assertion di
`tests/test_backtest.py` yang hardcode SL=900 (asumsi Donchian murni) diupdate ke SL=1004
(nilai capped utk fixture yang sama) - dicek manual: MA20 fixture = (19×1000+1080)/20 = 1004,
lebih ketat dari Donchian Low=900 dan 10%-cap=972, jadi itu yang dipakai. 93 test pytest lolos
semua setelah perbaikan.

**Pelajaran**: dokumentasi "sudah divalidasi" di README sebelumnya cuma berdasar 1 formula
yang PERNAH dibacktest, bukan berarti itu formula TERBAIK - kalau ada alternatif yang belum
diuji head-to-head, jangan asumsikan yang lama otomatis benar. User yang notice kejanggalan
(42.9% risiko) sebelum saya, dan pertanyaan langsungnya ("backtest keduanya") yang memicu
perbaikan ini.

## Konsolidasi Tab: Backtest & Top 10 Digabung ke Kandidat

User notice tab **Backtest** dan **Top 10** sumber datanya SAMA persis dengan tab **Kandidat**
(`cands_day_all`/`cands_swing_all`) - 3 tab utk 1 sumber data = duplikasi, bukan "2 sistem
dalam 1". Tab **Top 10** dihapus total (cuma re-tampilkan tabel Day/Swing tanpa filter
tambahan). Isi tab **Backtest** (statusnya sebenarnya bukan backtest statistik - itu adalah
jurnal paper-trading otomatis: tombol Buka Posisi Day/Swing, Cek TP/SL & Force-Sell, plus
tabel & ringkasan sheet POSISI) dipindah masuk ke tab **Kandidat**, ditaruh setelah tabel
kandidat + tombol Download CSV, sebelum bagian "Kirim ke Jurnal Real". Tab **Kandidat**
sekarang jadi satu tempat: lihat kandidat yang sudah divalidasi → buka posisi otomatis (sistem)
ATAU kirim manual ke Jurnal Real → lihat chart. Backtest statistik historis yang SEBENARNYA
(`run_historical_backtest`/`run_realistic_backtest` di backtest.py) tetap TIDAK ada di UI -
cuma dipakai internal utk validasi (lihat "Backtest Historis" di atas).

Diverifikasi live (`streamlit run app.py` lokal): tab bar sekarang cuma 17 tab (dulu 19), tidak
ada tab Backtest/Top 10, section "Buka Posisi Otomatis" muncul benar di tab Kandidat dengan
caption & warning yang sesuai (Google Sheets belum terhubung → warning yang benar tampil),
tanpa exception maupun error di console.

## Bug: Kandidat Day Trading Hilang Total dari Tabel Gabungan (Kalah Dedup vs Swing)

Efek samping dari konsolidasi di atas: user lihat live, tabel Kandidat gabungan **SEMUA
"SWING TRADE"**, 0 baris "DAY TRADE" - padahal kolom "Rekomendasi" (sinyal eksploratif
terpisah) sering bilang "DAY TRADE" utk saham yang sama. Awalnya saya cuma MENEBAK
sebabnya (dedup `drop_duplicates(subset="Saham", keep RR tertinggi)` pas gabung
cands_day_all+cands_swing_all) dan langsung ubah kode TANPA verifikasi - user tegur:
**"kesalahan kita [berdua] tadi langsung melakukan perubahan tanpa backtest"** - perubahan
langsung dibatalkan (`git checkout`) sebelum di-commit.

**Dicek ulang pakai data riil** (615 saham x 5 tahun, snapshot terakhir cache, replikasi
persis parameter default: lookback Day=10, Swing=20, min_rr Day=2.0, Swing=1.5) - bukan
backtest profitabilitas (ini bukan soal "mana lebih untung"), tapi cek langsung apakah
dedup memang menyembunyikan kandidat valid:

- Dari 14 saham Signal STRONG BUY/BUY yang punya RR terhitung utk KEDUA lookback: **Swing
  RR > Day RR di 13/14 (93%)**, Day RR TIDAK PERNAH lebih tinggi (0/14).
- Ini **struktural**, bukan kebetulan: MA20 & cap 10% (2 dari 3 kandidat SL) identik utk Day
  maupun Swing pada saham yang sama - cuma Donchian Low yang beda. Tapi lookback Swing (20D)
  selalu mencakup lookback Day (10D) sbg subset, jadi Donchian **High** Swing hampir selalu
  ≥ Donchian High Day (Target lebih jauh), sementara Risk sering SAMA (dua-duanya kena MA20
  yang identik) → RR Swing hampir selalu menang di perbandingan dedup.
- Contoh konkret: GPSO, MDIA, GZCO, KOTA, BWPT, ASHA **valid & lolos ambang RR Day (≥2.0)**
  di `cands_day_all`, tapi 100% hilang dari tabel Kandidat karena dedup selalu pilih versi
  Swing-nya.

**Fix**: dedup `drop_duplicates(subset="Saham")` dihapus - 1 saham sekarang BISA muncul
2 baris (Day & Swing) kalau lolos kriteria kedua-nya, sama seperti tab "Top 10" lama (2
tabel terpisah, tanpa filter silang). Dropdown "Pilih Saham" (Kirim ke Jurnal Real & Chart
TradingView) di-dedup terpisah (`drop_duplicates()` cuma di list opsi, bukan di tabel) supaya
tidak muncul nama saham dobel di dropdown. Caption jumlah "saham tidak lolos" diubah dari
`len(picks)` (jumlah BARIS, bisa >1 per saham sekarang) jadi `picks["Kode"].nunique()`
(jumlah saham UNIK) supaya hitungannya tidak jadi negatif/salah kalau ada saham dobel.

Diverifikasi: 93/93 pytest lolos, dicoba live - filter "1️⃣ Tipe" sekarang menampilkan
KEDUA opsi ("⚡ DAY TRADE" dan "🌊 SWING TRADE") sebagai bukti baris Day Trade sudah muncul
lagi (sebelum fix, cuma opsi Swing yang ada di filter krn tidak ada baris Day sama sekali).

## Bug: Force-Sell Untung/Rugi Tidak Terhitung ke Kotak WIN/LOSS

User laporan (screenshot kotak ringkasan "Buka Posisi Otomatis"): 3 posisi baru saja
FORCE SELL (APLN rugi -4%, GDST untung +701%, ANTM untung +156%) - tabel di bawahnya sudah
update benar (Tanggal Close/Harga Jual/P&L terisi), tapi kotak **WIN: 0, LOSS: 0, Win Rate:
0.0%** di atas tidak berubah sama sekali walau ada 2 win besar.

**Akar masalah**: `gsheet_journal.summarize()` menghitung WIN/LOSS cuma dengan cek substring
`"WIN"`/`"LOSS"` pada kolom Status. Status yang ditulis `auto_close_positions()` ada 3 macam:
`"WIN (TP)"`, `"LOSS (SL)"`, atau `"FORCE SELL (N hari)"` - yang terakhir TIDAK mengandung
kata "WIN" maupun "LOSS" sama sekali, jadi tidak pernah terhitung ke salah satu, walau
force-sell tetap punya hasil riil (untung/rugi, cuma exit reason-nya beda dari kena TP/SL
persis). Bug ini SUDAH ADA sebelum sesi ini (bukan regresi dari perubahan terbaru) - baru
kelihatan sekarang krn kotak ringkasan ini pindah dari tab Backtest lama ke tab Kandidat.

**Fix**: force-sell sekarang diklasifikasi WIN/LOSS dari **tanda P&L (%) aktualnya** (P&L>0
= WIN, P&L≤0 = LOSS), bukan dari teks Status. Status "WIN (TP)"/"LOSS (SL)" tetap dihitung
seperti biasa (sudah pasti benar dari cara penulisannya). Tab **Performance** (`t_perf`) TIDAK
kena bug ini - itu sudah lebih dulu hitung win/loss dari tanda `P&L (Rp)` langsung, bukan
teks Status, jadi sebelumnya tab Kandidat & tab Performance bisa menunjukkan Win Rate yang
BEDA utk data yang sama (sekarang konsisten).

4 test baru di `tests/test_gsheet_journal.py::TestSummarizeForceSell` - salah satunya
mereplikasi PERSIS kasus screenshot user (3 FORCE SELL + 10 OPEN, cek total/open/win/loss/
winrate semua benar). 97/97 pytest lolos.

## Audit Menyeluruh: "Buat Screener Terbaik & Profesional"

User minta audit menyeluruh modul-modul yang menangani uang/eksekusi (`screener.py`,
`gsheet_journal.py`, `real_journal.py`, `calculators.py`, `equity.py`, `backtest.py`) untuk
cari bug yang bisa menyebabkan kerugian, lalu menyerahkan keputusan perbaikan sepenuhnya
("saya serahkan kekamu bagaimana screener menjadi screener terbaik dan profesional").
Ditemukan 1 bug nyata + 2 gap struktural, ketiganya diperbaiki:

### 🔴 Bug nyata: `real_journal.py` - nomor trade bisa collide setelah hapus data

`open_trade()` dulu pakai `no = len(existing) + 1` (nomor trade baru = JUMLAH BARIS + 1,
bukan NOMOR TERTINGGI + 1). Skenario nyata: trade No 1,2,3 ada. Hapus No 2 (`delete_trade()`
betul-betul `delete_rows()` di sheet) - tersisa 2 baris. Trade baru berikutnya dihitung
`No = 2+1 = 3` - **padahal No 3 SUDAH ADA**, jadi ada 2 baris dengan No sama.
`close_trade()`/`edit_trade()`/`delete_trade()` semua cari baris via `trades["No"]==no` lalu
ambil `.iloc[0]` (baris PERTAMA yang cocok) - kalau ada 2 baris dengan No sama, sistem diam2
selalu memutakhirkan baris yang PERTAMA muncul di sheet, bukan yang dimaksud. Ini bisa merusak
catatan transaksi uang beneran tanpa pemberitahuan apa pun.

**Fix**: `no = MAX(No yang ada) + 1`, bukan jumlah baris + 1 - tidak collide lagi walau ada
baris yang dihapus. 3 test baru di `tests/test_real_journal.py::TestOpenTradeNumbering`,
termasuk reproduksi PERSIS skenario di atas (No 1,3 tersisa setelah hapus No 2 -> trade baru
harus No 4, bukan No 3).

### 🟡 Gap: TP/SL live cuma dicek dari 1 titik harga (Close), backtest pakai High/Low

`auto_close_positions()` dulu cuma menerima `price_lookup` (1 harga Close per saham) - kalau
harga sempat menembus TP/SL secara intraday lalu balik lagi sebelum sempat dicek dashboard,
tembusan itu TIDAK PERNAH terdeteksi. Ini gap nyata vs metodologi backtest yang sudah
divalidasi (`backtest.py` selalu cek `High>=Target` / `Low<=SL`, bukan cuma harga penutupan) -
artinya hasil LIVE bisa sistematis berbeda dari yang dibuktikan backtest, ke arah manapun
(TP yang terlewat = untung yang hilang, SL yang terlewat = posisi tetap terbuka menembus
level yang seharusnya sudah dipotong rugi).

**Fix**: `auto_close_positions()` sekarang menerima `hl_lookup` opsional (`{kode: (High, Low)
hari ini}`, dibangun dari `price_data` yang sudah difetch screener - tidak ada fetch
tambahan). TP dicek dari **High** hari itu, SL dari **Low** hari itu - jauh lebih dekat ke
apa yang sebenarnya terjadi. Urutan cek juga diseragamkan: **SL dicek LEBIH DULU** (asumsi
konservatif kalau High & Low hari yang sama menembus TP & SL sekaligus - dulu kodenya malah
cek TP dulu, beda urutan dari `backtest.py` yang SL-dulu; sekarang sama). Exit price yang
dicatat juga diubah jadi TEPAT di level TP/SL yang tersentuh (bukan harga Close saat dicek),
supaya P&L live sebanding dgn P&L yang diklaim backtest, bukan angka beda metodologi.
Backward-compatible: kalau `hl_lookup` tidak diisi (caller lama), fallback ke Close-only
seperti perilaku sebelumnya - TIDAK ada fetch tambahan cuma demi High/Low kalau harga
Close-nya sendiri sudah ada (hindari boros kuota Yahoo Finance).

Debug tabel "Posisi yang dicek" di tab Kandidat diupdate sama (High/Low + urutan SL-dulu) -
supaya yang user LIHAT di situ tetap konsisten dgn apa yang sistem SEBENARNYA putuskan,
mengikuti prinsip yang sama dgn fix `enrich_price_lookup()` sebelumnya. 6 test baru
(`TestEnrichHlLookup`, `TestAutoClosePositionsHighLow`), termasuk kasus "TP kesentuh via
High walau Close di bawah TP" dan "SL & TP dua-duanya kesentuh hari yang sama -> SL menang".

### 🟡 Gap: tool validasi resmi (`backtest.py`) tidak punya opsi filter regime IHSG

`backtest.py` (yang dipakai utk membuktikan sistem ini profitable, lihat "Backtest
Historis") tidak punya cara menggate entry ke regime IHSG>MA50 sama sekali - padahal Swing
di LIVE (`build_trade_candidates()`) SELALU digate begitu. Akibatnya kalau tool resmi ini
dijalankan ulang (`python backtest.py`), angkanya UNDERSTATE performa Swing yang sebenarnya.
Perbandingan head-to-head yang membuktikan performa Swing dengan filter regime (dipakai di
bagian "Regresi..." di atas) cuma pernah dijalankan lewat skrip sekali-pakai di luar repo,
bukan tool resmi.

**Fix**: tambah `require_bullish_regime` + `ihsg_df` ke `_simulate_realistic_trades_single()`/
`run_realistic_backtest()` (walk-forward - regime dihitung dari IHSG s.d. tanggal ITU SAJA,
tidak ada lookahead, sama seperti `compute_metrics()`) + flag CLI baru `--regime-filter`.
5 test baru (`TestRegimeFilterBacktest`) memverifikasi: default tidak menggate apa pun
(perilaku lama dipertahankan), regime BULLISH meloloskan trade, regime BEARISH mengosongkan
trade, dan checker regime tidak lookahead (return `None` sebelum MA50 terbentuk).

**Total setelah audit ini: 111/111 pytest lolos** (dari 97 sebelumnya).

### Tidak diperbaiki (keterbatasan struktural, bukan bug kode)

Ditemukan juga 1 risiko struktural yang TIDAK ada perbaikan sederhana: **tidak ada
locking/transaksi di Google Sheets** - kalau GitHub Actions (auto-run terjadwal) dan klik
manual di dashboard kebetulan jalan hampir bersamaan, keduanya bisa lolos cek "belum ada
posisi OPEN" sebelum salah satu selesai menulis -> posisi dobel utk saham yang sama, dan
salah satu baris OPEN bisa "nyangkut" selamanya (`_find_row_number()` cuma nemu baris
PERTAMA yang cocok). Risiko rendah utk pemakaian 1 user, butuh migrasi ke database
sungguhan (bukan Google Sheets) utk benar-benar dihilangkan - di luar scope perbaikan saat
ini, didokumentasikan di sini supaya user tahu risikonya.

## Day Trading Terbukti TIDAK Konsisten - Auto-Open Dimatikan

User bertanya: **"apakah hasil audit terkait saham yang ditangkap screener sudah optimal
untuk cuan?"** - jawaban jujurnya waktu itu: Swing (lookback 20D + regime IHSG>MA50 +
capped SL) sudah punya bukti backtest konsisten, tapi **Day Trading (lookback 10D) belum
PERNAH dibuktikan profitable sendiri** - selama ini cuma "menumpang" validasi Swing padahal
formulanya beda. User lalu minta: pertahankan yang sudah baik, optimalkan/benahi yang belum.

**Diuji independen** (615 saham x 5 tahun, force-sell PERSIS meniru aturan live: BPJS=1
hari, BSJP=2 hari - bukan 15 hari seperti Swing):

| Skenario | Total Return Bersih | Win Rate |
|---|---|---|
| BPJS, TANPA regime (= live sebelumnya) | **-4569.1%** | 34.9% |
| BSJP, TANPA regime (= live sebelumnya) | **-902.5%** | 36.8% |
| BPJS, DENGAN regime IHSG>MA50 | **-1005.3%** | 35.7% |
| BSJP, DENGAN regime IHSG>MA50 | **+2322.7%** | 37.8% |

Kelihatan BSJP+regime positif - TAPI dicek split-half (standar yang dipakai sepanjang
proyek ini, sama seperti yang menggugurkan klaim "Juli selalu hijau" di bagian Efek
Musiman): **GAGAL konsisten**.

| Skenario | Paruh 1 (2021-2024) | Paruh 2 (2024-2026) |
|---|---|---|
| BPJS + regime | -1072.0% | +66.7% (nyaris impas) |
| BSJP + regime | -74.9% (nyaris impas) | **+2397.6%** |

BPJS tetap rugi di kedua paruh (walau paruh 2 mendekati impas). BSJP totalnya positif
TAPI 100% ditarik oleh ~2 tahun terakhir - paruh pertama (2.5 tahun) nyaris impas. Ini
BUKAN pola stabil sepanjang waktu seperti Swing (yang net profit konsisten di KEDUA
paruh) - persis pola "efek yang ditarik periode terakhir" yang sudah gugur di bagian Efek
Musiman IHSG.

**Kesimpulan jujur**: Day Trading (BPJS maupun BSJP) TIDAK memenuhi standar konsistensi
yang dipakai untuk memvalidasi Swing. Bukan berarti pasti tidak akan pernah profitable -
tapi dengan bukti yang ada SEKARANG, tidak bisa disebut tervalidasi.

**Fix diterapkan** (sesuai arahan user - benahi yang belum baik, jangan dipertahankan
seolah sudah tervalidasi):
1. `cands_day_all` (screener.py, dipanggil dari app.py) sekarang JUGA digate filter regime
   IHSG>MA50 - sama seperti Swing. Ini mengurangi rugi terburuk (BPJS -4569%→-1005%, BSJP
   -902%→+2322%) tapi TIDAK membuatnya "tervalidasi" (masih gagal split-half).
2. **Tombol "Buka Posisi Day Trading" otomatis DIHAPUS** dari tab Kandidat - sistem tidak
   lagi bisa membuka posisi (baik ke Jurnal Backtest simulasi maupun potensial diteruskan
   manual ke Jurnal Real) untuk sesuatu yang terbukti tidak konsisten. Tombol "Buka Posisi
   Swing Trading" & "Cek TP/SL & Force-Sell" tetap ada (cuma 2 tombol, bukan 3).
3. Label "Tipe" utk Day Trade diubah jadi `⚠️ DAY TRADE (BPJS/BSJP) - belum konsisten`
   (warna oranye/warning, bukan hijau) - beda jelas dari `🌊 SWING TRADE` (biru, tervalidasi).
   Filter "1️⃣ Tipe" & banner "Panduan Cuan Konsisten" diupdate menjelaskan perbedaan status
   validasi ini secara eksplisit.
4. Day Trade TETAP ditampilkan di tabel Kandidat (bukan disembunyikan total) - transparansi
   tetap dijaga, RR/regime tetap difilter sama ketatnya, cuma tidak bisa di-auto-open dan
   labelnya jujur soal statusnya.

Diverifikasi: py_compile OK, 111/111 pytest lolos, dicoba live - label & warning baru
tampil benar di tab Kandidat.

## Day Trading: Bukan Soal Parameter, Tapi Desain Sinyal

User menolak "matikan saja" - responnya: **"mungkin pertanyaannya adalah bagaimana
membuat sistem day trading yang konsisten profit... karena day trading bukan sesuatu
yang jelek"**, dan menajamkan arah investigasi: coba pisahkan sinyal Day dari Swing
(lookback-nya sendiri, bukan menumpang Signal 20-hari punya Swing) dan cari parameter
yang bikin konsisten.

**Ditemukan kesalahan metodologi di pengujian sebelumnya**: skrip validasi awal LUPA
mengganti `donchian_lookback` - jadi "Day Trading" yang diuji kemarin sebenarnya MASIH
pakai lookback 20 hari (punya Swing) utk Sinyal DAN Entry/Target, cuma masa tahannya yang
dipendekkan (1-2 hari). Bukan pengujian Day Trading yang sesungguhnya.

**Diuji ulang dgn benar**: grid search 27+ kombinasi - lookback ∈ {5,7,10,15,20} (Sinyal
STRONG BUY/BUY dihitung ULANG per lookback, persis usulan user "sinyal dipisah dari
Swing"), hold_days ∈ {1,2,3,4,5,7,10}, selalu dgn filter regime IHSG>MA50 (fase eksplorasi
di subset 150 saham/step=2 dulu, lalu kandidat terbaik dikonfirmasi di 615 saham penuh/
step=1 + split-half):

| lookback | hold | Win Rate | Avg Return | Total Return |
|---|---|---|---|---|
| 5 | 1 | 33.6% | -0.431% | -306.8% |
| 10 | 1 | 34.6% | -0.106% | -99.4% |
| 10 | 3 | 36.2% | +0.296% | +277.9% |
| 15 | 3 | 36.2% | +0.415% | +443.1% |
| 20 | 3 | 36.6% | +0.517% | +583.4% |
| 10 | 10 | 32.2% | +0.964% | +905.9% |
| 15 | 10 | 32.0% | +1.092% | +1166.8% |
| **20** | **10** | **32.9%** | **+1.539%** | **+1737.3%** |

**Pola yang muncul di SEMUA 27 kombinasi, tanpa kecuali**: makin lama hold & makin
panjang lookback, makin baik hasilnya - monoton, tidak ada titik optimal tersendiri di
rentang hold pendek (1-3 hari). hold=1 SELALU rugi, berapapun lookback-nya.

**Konfirmasi split-half di data penuh (615 saham, step=1)** utk 2 kandidat representatif:

| Parameter | Paruh 1 (2021-2024) | Paruh 2 (2024-2026) | Konsisten? |
|---|---|---|---|
| lookback=10, hold=3 ("Day" tercepat yang untung) | -0.008% avg (nyaris impas) | +0.867% avg (total +3250.5%) | ❌ Untung 100% ditarik paruh 2 |
| lookback=20, hold=10 ("jembatan" ke Swing) | +0.107% avg (total +494.3%) | +2.190% avg (total +10136.2%) | ✅ Dua-duanya positif |

**Kesimpulan jujur**: `lookback=10, hold=3` (kandidat Day Trading tercepat yang masih
untung) GAGAL konsisten split-half - sama seperti temuan sebelumnya, untungnya cuma
ditarik 2 tahun terakhir. Yang BARU konsisten (`lookback=20, hold=10`) sudah bukan Day
Trading lagi - lookback-nya SAMA dgn Swing, hold 10 hari cuma sedikit lebih pendek dari
force-sell Swing (15 hari). Polanya membuktikan: **breakout Donchian + target measured-
move butuh waktu berhari-hari utk berkembang** - dipotong di 1-3 hari, sinyalnya belum
punya cukup ruang mencapai target, hasilnya jadi kebetulan (menguntungkan di satu periode,
tidak di periode lain), bukan edge yang stabil.

Ini BUKAN soal "belum ketemu kombinasi parameter yang pas" (sudah diuji 27+ kombinasi,
termasuk memisahkan sinyal dari Swing sesuai usulan user) - ini soal **jenis strategi**:
sistem breakout multi-hari secara struktural tidak cocok utk horizon day-trading (1-3
hari). Day Trading yang beneran konsisten butuh sinyal BERBEDA TOTAL (mis. momentum
intraday, gap-and-go, opening-range breakout, mean-reversion jangka sangat pendek) - yang
semuanya butuh data INTRADAY, bukan data harian gratis dari Yahoo Finance yang dipakai
sistem ini. Membangun itu dari nol di luar scope perbaikan/optimalisasi sistem yang
sudah ada - butuh riset & sumber data baru.

Label di app.py diupdate mengikuti kesimpulan ini: `⚠️ DAY TRADE (...) - perlu desain
sinyal baru` (bukan lagi "belum konsisten" yang menyiratkan cuma butuh tuning lebih
lanjut) - supaya user tidak menunggu update parameter yang tidak akan pernah datang,
dan tahu persis kenapa.

### Riset lanjutan & keputusan akhir: Day Trading dihapus total

Setelah label di atas, user minta lanjut cari sistem yang genuinely profit (bukan cuma
matikan) - dicoba 5 pendekatan lagi pakai data intraday (5 menit & 60 menit, difetch
khusus utk riset ini): ORB dgn jendela benar (15 menit + volume + VWAP, bukan 1 jam),
gap-fade (mean-reversion overnight, data harian - PERNAH profit 2021-2024 tapi RUNTUH
2025-2026), OHOL/Shaven Bottom (Open=Low breakout, tanpa & dengan hold 2 hari, blue-chip
& saham volatile). **Semuanya konsisten rugi**, kecuali gap-fade yang sudah mati.

Sistem "Shaven Bottom" versi lengkap (dari referensi praktisi user) secara eksplisit
mensyaratkan konfirmasi order book real-time ("Makan Kanan") sbg salah satu dari 3 syarat
wajib - data itu TIDAK tersedia di Yahoo Finance atau sumber gratis manapun, jadi versi
yang bisa diuji (OHLCV saja) kemungkinan besar ikut membeli "shaven bottom palsu"
(jebakan bandar) yang seharusnya disaring lewat tape reading. Ini bukan bukti sistemnya
salah kalau dieksekusi manual dgn order book asli - cuma bukti tidak bisa divalidasi
lewat backtest data historis gratis.

**Keputusan akhir**: Day Trading (kolom Tipe, filter, tombol Buka Posisi, semua sisa
kode terkait) **dihapus total** dari app.py - bukan cuma dimatikan/dilabeli. Tab Kandidat
sekarang cuma menampilkan Swing (satu-satunya yang tervalidasi konsisten).

## Pola Open=Low (Shaven Bottom) - Fitur Eksploratif Baru

User berbagi sistem trading praktisi (candle tanpa ekor bawah = "Shaven Bottom"/"Bullish
Marubozu" - psikologi sangat bullish, penjual tidak sempat menekan harga di bawah Open)
dan minta dibuatkan sbg kriteria screener yang bisa dipilih manual - BUKAN diminta
dihapus seperti Day Trading (order book/tape reading tidak bisa dibacktest, tapi eksekusi
manual dgn order book asli tetap valid, beda kasus dari breakout Donchian yang sudah
terbukti gagal di banyak variasi parameter).

**Implementasi**: `compute_metrics()` (screener.py) dapat 2 kolom baru - `Open=Low`
(Low hari ini >= Open x 99.85%, toleransi 0.15%) dan `Setup A Breakout` (Open=Low DAN
Status Breakout=="BREAKOUT" DAN Volume Ratio>1.5x - kombinasi "paling aman" menurut
referensi user). Dihitung dari baris TERAKHIR data harian yang sudah difetch screener
(saat market jam bursa, baris ini = data HARI INI sejauh berjalan) - TIDAK perlu fetch
data intraday tambahan.

UI: expander baru "🕯️ Pola Open=Low" di tab Semua Saham (setelah Scanner Lonjakan
Volume), 2 kolom - "Setup A: Breakout + Volume Tinggi" (kondisi lengkap) dan "Open=Low
tanpa breakout" (shaven bottom saja, konteks Setup B/C dari referensi user harus dinilai
manual). Diberi warning tebal: TIDAK bisa dibacktest (order book "Makan Kanan" tidak ada
di data historis), user WAJIB verifikasi sendiri (volume asli bukan mark-up, tidak di
pucuk rally, jarak ke ARA cukup) sebelum entry - BUKAN sinyal auto-trade, tidak bisa
dikirim ke Jurnal Backtest, cuma manual via Jurnal Real.

4 test baru (`TestOpenLowPattern`) memverifikasi deteksi shaven bottom, gagal deteksi
kalau ada ekor bawah, dan kombinasi Setup A (breakout+volume) vs bukan.

### Audit susulan: label "DAY TRADE" masih nyangkut di sistem Rekomendasi terpisah

User lihat screenshot production menunjukkan kolom **Rekomendasi** (sistem Quality/
Momentum yang SUDAH ADA sebelum riset Day Trading ini, di `get_trade_recommendation()` -
beda total dari sistem Tipe/Donchian yang baru dihapus) masih mengeluarkan label
**"DAY TRADE"** untuk saham bermomentum sangat kuat. User minta diaudit ulang.

Ini bukan bug sisa penghapusan - itu heuristik independen (momentum+akumulasi+trend),
tapi labelnya sekarang menyesatkan (menyiratkan rekomendasi day-trading yang sudah
terbukti tidak konsisten). **Fix pertama**: label diganti jadi "MOMENTUM KUAT" (kondisi
underlying-nya tetap valid sbg info, cuma tidak lagi menyiratkan strategi day-trading).
`tutorial.py` (contoh filter "Agresif"/"Moderat" yg mereferensikan "DAY TRADE") diupdate
sepadan.

**Ditemukan lagi lewat screenshot user** (audit kedua - user tegur "terasa audit yang
kurang hati2"): "MOMENTUM KUAT" (13 karakter) lebih panjang dari "DAY TRADE" (9) atau
"SWING TRADE" (11) yang diganti - kolom Rekomendasi di tabel Kandidat sempit (banyak
kolom lain berbagi lebar), jadi teksnya KEPOTONG jadi "MOMENTUM KU..." di UI - lolos dari
verifikasi pertama krn cuma dicek py_compile/pytest/grep source code, TIDAK dicek lebar
kolom aktual di render live. **Fix final**: dipersingkat jadi **"MOMENTUM"** (8 karakter,
lebih pendek dari "DAY TRADE" yang sudah terbukti pas). Pelajaran: perubahan teks label
di kolom tabel sempit butuh verifikasi VISUAL render live, bukan cuma cek source code -
"terlihat benar di kode" TIDAK sama dengan "terlihat benar di layar".

### Audit ketiga: kolom Tipe & Rekomendasi tumpang tindih kosakata - redesain tabel Kandidat

User lihat screenshot lagi: kolom **Tipe** (selalu "SWING TRADE", sama di SETIAP baris)
berdampingan dengan kolom **Rekomendasi** yang JUGA bisa bilang "SWING TRADE" (sebelum
fix sebelumnya) - dua sistem TERPISAH TOTAL (satu tervalidasi backtest, satu eksploratif)
kelihatan seperti saling menguatkan padahal tidak ada hubungan. User: "ini yang saya
khawatirkan kalau analisis tidak tuntas berisiko sistem yang dibuat adalah sistem yang
bisa rugi" - kekhawatiran yang valid: UI membingungkan bisa bikin user salah baca sinyal
eksploratif sbg setara sinyal tervalidasi.

**Redesain**: kolom **Tipe dihapus dari tabel** (isinya 100% konstan "SWING TRADE" di
setiap baris sejak Day Trading dihapus - tidak informatif sbg kolom) - diganti 1 banner
di atas tabel: "🌊 SEMUA KANDIDAT = SWING TRADE, TERVALIDASI". Filter "1️⃣ Tipe" yang
sekarang percuma (cuma 1 opsi) juga dihapus - tersisa cuma filter Quality.

**Audit lanjutan (user tegur lagi - "jangan cuma ganti kata2", minta formula dipelajari
dulu)**: dicek ulang `get_trade_recommendation()` - kelas "MOMENTUM" dan "TREN KUAT"
(dulu "SWING TRADE") SAMA-SAMA mensyaratkan `trend_stars>=2` - trend_stars BUKAN
pembedanya. Pembeda SEBENARNYA adalah field `momentum` (dari fungsi hitung naik
beruntun+volume, dicek via urutan if/elif): MOMENTUM = trend+akumulasi+momentum harga
SEDANG AKTIF; TREN KUAT = trend+akumulasi/netral TAPI momentum BELUM aktif. Label lama
("SWING TRADE") kebetulan MASIH akurat scr makna (setup trend-following tanpa momentum
kuat = cocok gaya swing) - masalahnya PURE soal tumpang-tindih kosakata dgn kolom Tipe,
bukan salah formula. Kolom "Alasan" (teks penjelasan per baris) sudah dihitung tapi TIDAK
pernah ditampilkan - drpd tambah kolom baru (risiko kepotong lagi), penjelasan pembeda
MOMENTUM vs TREN KUAT dipindah ke caption/help text yang sudah ada (dibaca sekali, bukan
per-baris) - jelas menyebut BUKAN soal trend lebih kuat/lemah, tapi momentum aktif/belum.

Diverifikasi: py_compile OK, 115/115 pytest lolos, dicoba live - banner 1x muncul benar,
caption penjelasan MOMENTUM vs TREN KUAT lengkap & jelas.

### Audit keempat: "MOMENTUM" kategori yang salah utk kolom "Rekomendasi"

User: "rekomendasi tidak cocok dengan istilah momentum, seharusnya kolom itu swing
trade/wait/hold/sell/avoid karena judulnya rekomendasi... jangan cuma ganti kata2, jangan
banyak penjelasan di UI (bikin kurang bersih), penjelasan detail cukup di belakang (kode/
README) saja."

Kesalahan tepat: kolom **Rekomendasi** seharusnya isinya AKSI (SWING TRADE/WAIT/AVOID -
kata kerja/keputusan), bukan DESKRIPSI KONDISI ("MOMENTUM" itu kondisi pasar, bukan
tindakan) - apalagi kolom "Momentum" (deskripsi kondisi momentum_strength) sudah ada
sendiri, jadi Rekomendasi="MOMENTUM" tumpang tindih kategori dgn kolom lain, bukan cuma
tumpang tindih kata seperti kasus SWING TRADE sebelumnya.

**Fix (setia ke desain asli, bukan desain baru)**: kasus "momentum kuat" (dulu DAY TRADE
-> MOMENTUM) digabung balik ke **SWING TRADE** (satu2nya aksi trading valid yg tersisa
di sistem ini) - dibedakan lewat `confidence` (85/70/55) yang sudah ada, BUKAN lewat
label kata baru. Rekomendasi kembali ke 3 nilai bersih: SWING TRADE / WAIT / AVOID -
sama seperti struktur asli (4 aksi -> 3 aksi setelah DAY TRADE dihapus, bukan diganti
jadi istilah kondisi). Caption panjang di UI (penjelasan MOMENTUM vs TREN KUAT) dihapus,
diringkas jadi 1 baris - detail rasional pemetaan tetap ada di komentar kode/README,
tidak ditampilkan ke user (sesuai arahan: UI bersih, penjelasan di belakang).

Diverifikasi: py_compile OK, 115/115 pytest lolos, dicoba live - caption sekarang cuma
2 kalimat.

### Audit kelima: sumber formula kolom "Quality" & bintang Trend yang kosong

User menemukan kombinasi yang tampak kontradiktif: Momentum=VERY_STRONG + Trend=⭐⭐⭐
tapi Quality=LOW. Ditelusuri ke `get_quality_rating()`: Quality = blend TERTIMBANG dari
3 sub-skor independen - Akumulasi/Distribusi 40% (`_detect_accumulation_distribution()`,
window 20 hari) + Trend Score 35% (`_validate_trend_strength()`, window 10 hari) +
Momentum Score 25% (`_count_consecutive_higher_closes()`, window 10 hari). Kolom "Trend"
(bintang) dan "Momentum" (label) yang TAMPIL di tabel bukan skor 0-100 yang dipakai di
rumus - itu label kategori terpisah dari fungsi yang sama. Bintang 3 cuma butuh
`MA5>MA20>MA50` (+35 poin fix dari maksimum 100 trend_score) - bisa terjadi dgn
trend_score minimum 35/100 kalau harga saat ini sudah di bawah semua MA (pullback tajam,
MA-nya lagging). Jadi kombinasi Quality=LOW + Trend=⭐⭐⭐ + Momentum=VERY_STRONG itu
matematis MUNGKIN dan bukan bug - itu sinyal "harga naik beruntun tapi tanpa dukungan
smart money/volume" (akumulasi/distribusi lemah menang bobot 40% terbesar).

Bintang bisa kosong total (`trend_stars=0`, cell blank di `m["Trend"] = "⭐" * stars`,
[screener.py:707](screener.py:707)) di 2 kasus yg TIDAK dibedakan tampilannya: (1) trend
bearish penuh (`MA5<MA20<MA50`, sengaja 0 bintang) vs (2) histori harga < 50 hari
(`INSUFFICIENT`, [screener.py:156-157](screener.py:156), bukan berarti bearish, cuma
belum bisa dihitung). Belum diperbaiki (blank kedua kasus disatukan) - didokumentasikan
dulu, belum ada keputusan mengubah tampilannya.

### Backtest Confidence Tier "SWING TRADE" (85/70/55) - urutan nominal TERBUKTI SALAH

User minta backtest apakah confidence tier (85/70/55) dari `get_trade_recommendation()`
benar2 membedakan kualitas trade. Metodologi: walk-forward di 615 saham/5 tahun (cache
`price_data_615_5y.pkl`), quality/confidence dihitung dari `df.iloc[:t+1]` PERSIS di
titik sinyal (no lookahead), HANYA trade yang lolos filter tervalidasi (Signal STRONG
BUY/BUY + RR>=1.5 + regime IHSG>MA50, exact sama dgn `build_trade_candidates()`) dan
direkomendasikan SWING TRADE. Skrip: `test_swing_confidence_backtest.py` (scratchpad,
tidak masuk repo).

Hasil (1.323 trade SWING TRADE dari 1.941 trade tervalidasi total, 68%):

| Confidence | Trade | Win Rate Bersih | Avg Return Bersih | Total Return |
|---|---|---|---|---|
| 85 | 513 | 38.4% | 1.27% | 651.87% |
| 70 | 773 | 37.0% | **1.94%** | **1498.27%** |
| 55 | 37 | 29.7% | 0.43% | 15.86% |

Split-half (2 paruh waktu): 85 & 70 konsisten positif di kedua paruh. **55 gagal
konsistensi** - paruh 1 avg **-1.24%** (rugi), paruh 2 avg +2.01% (untung) - arah
berbalik, sample kecil (18-19 trade/paruh), tidak bisa dipercaya.

Temuan: filter SWING TRADE (semua confidence) sedikit lebih baik dari baseline tak
tersaring (37.3% WR / avg 1.64% vs baseline 33.5% WR / avg 1.56%) - ada nilai tambah tipis.
TAPI **urutan nominal 85>70>55 TIDAK terbukti** - confidence 70 justru avg & total
return-nya lebih tinggi dari 85 (kombinasi "Trend+Akumulasi solid, momentum belum aktif"
menang atas "Trend+Akumulasi+momentum semua aktif"). Confidence 55 (smart_money=NETRAL,
bukan Akumulasi) jelas paling lemah & tidak konsisten.

**Fix (2 tahap)**: (1) warna badge "Confidence" di tabel Kandidat ([app.py](app.py)
`color_confidence()`) dibuat berdasarkan BUKTI backtest, bukan angka nominal apa adanya -
85 & 70 diberi warna biru kuat yang SETARA (`#1d4ed8`). Kolom "Confidence" ditambahkan ke
tabel Kandidat (sebelumnya dihitung tapi tidak ditampilkan). (2) User: "masuk WAIT saja,
karena yang dibeli tidak semuanya juga" - cabang confidence 55 (`smart_money=NEUTRAL`)
di `get_trade_recommendation()` **DIDOWNGRADE dari SWING TRADE ke WAIT** (confidence 40),
sesuai bukti backtest-nya sendiri (WR 29.7%, avg return bersih 0.43%, arah berbalik antar
split-half). SWING TRADE sekarang cuma tersisa confidence 85/70, yang keduanya konsisten
net-profit di 2 paruh waktu - tidak ada lagi tier SWING TRADE yang terbukti lemah/tidak
konsisten. Diverifikasi: py_compile OK, 115/115 pytest lolos.

### Caption tabel Kandidat dipersingkat - detail dipindah ke sini

User: "sebaiknya ini ada di README saja kalau masih dibutuhkan, diganti dengan pesan
trading... ringkas tapi bagus." Dua caption panjang di tabel Kandidat diringkas jadi
1 baris tebal masing-masing; rasional lengkapnya:

1. **"N sinyal tersembunyi"** - saham dgn Signal STRONG BUY/BUY yang TIDAK muncul di
   tabel Kandidat bukan bug - itu saham yang tidak lolos RR minimum atau regime IHSG>MA50,
   kriteria SAMA yang dipakai `build_trade_candidates()` & tombol "Buka Posisi Otomatis"
   di bawahnya. Sengaja disembunyikan drpd menampilkan Entry/SL/Target yang belum lolos
   validasi RR/regime.
2. **"SWING TRADE TERVALIDASI"** - semua baris yang tampil sudah lolos filter tervalidasi
   backtest (Signal+RR+regime). RR/Entry/Target/Stop Loss = harga MATI, jangan dilanggar.
   Rekomendasi/Quality/Trend/Smart Money/Momentum/Confidence = lapisan eksploratif di
   atasnya, info tambahan saja (lihat audit kelima & "Backtest Confidence Tier" di atas
   utk detail statusnya masing-masing).

Follow-up: user minta caption #1 dihapus TOTAL (bukan cuma diringkas) dan klausa "Kolom
lain = info tambahan" di caption #2 juga dihapus - sekarang tersisa 1 baris pendek
"🌊 SWING TRADE TERVALIDASI - RR/Entry/Target/Stop Loss harga mati." saja. Filter
"Rekomendasi" (multiselect SWING TRADE/WAIT/AVOID) ditambahkan di [app.py](app.py),
sejajar dgn filter "Quality Rating" yang sudah ada.

## Bug KRITIS: gspread numericise() rusak angka P&L locale Indonesia (10x-100x lipat)

User lapor floating loss ~50% di tab Performance, mengira sistemnya jelek. Audit
menemukan akar masalah yang JAUH lebih serius: bukan sinyal tradingnya buruk, tapi
**cara baca data dari Google Sheets salah**, sudah lama, sistematis, di SEMUA P&L.

**Root cause**: `gj.load_positions()` pakai `ws.get_all_records()` bawaan gspread, yang
DEFAULT numericise-kan tiap sel sendiri lewat `gspread.utils.numericise()`. Fungsi itu
menganggap koma = pemisah RIBUAN gaya Inggris & MENGHAPUSNYA sebelum parsing - lihat
docstring-nya sendiri: `numericise("2,000.1") -> 2000.1`. Sel Google Sheets locale
Indonesia (koma = DESIMAL, mis. "131683,2" utk Rp131.683,2) kena salah baca: koma
dihapus -> "1316832" -> diparsing jadi 1.316.832 (bukan 131.683,2) - **inflasi 10x**
kalau 1 digit desimal, **100x** kalau 2 digit (kasus P&L (%), krn 2 digit di belakang
koma). Diverifikasi LANGSUNG dari screenshot sheet POSISI asli user: trade GDST P&L
sungguhan **Rp131.683,2 (+7,01%)**, muncul di tabel Performance sbg **Rp1.316.832
(+701%)**. Trade APLN: asli **-Rp10.846,8 (-0,4%)**, tersebar sbg **-Rp108.468 (-4%)**.
Rumus P&L di `auto_close_positions()` sendiri SUDAH BENAR (diverifikasi manual thd
sheet asli) - bug murni di sisi PEMBACAAN (gspread), bukan di rumus.

**Kenapa ini sudah lama tidak ketahuan**: satu kasus persis ini ("P&L +701%") sudah
pernah muncul SEBELUM audit ini, tapi sesi sebelumnya cuma memperbaiki bug klasifikasi
WIN/LOSS force-sell (lihat "Bug nyata dari laporan user" di `summarize()`,
`gsheet_journal.py`) - MENERIMA angka 701% itu apa adanya sbg data sungguhan, tanpa
menyadari angkanya sendiri sudah salah baca 100x lipat sejak awal.

**Dampak**: SEMUA P&L (Rp) dgn pecahan desimal & SEMUA P&L (%) (yang hampir pasti
berdesimal krn hasil pembagian) di sheet POSISI selama ini terbaca salah - Realized
P/L, Win Rate, Profit Factor, Equity Curve di tab Performance jadi TIDAK BISA
dipercaya sampai fix ini. Karena mayoritas nilai di data user condong rugi, inflasi
ini bikin kesan sistem jauh lebih buruk dari kenyataan (walau arah untung/rugi per
trade tetap benar - cuma MAGNITUDE-nya yang salah, kadang 10-100x lipat).

**Fix**: `numericise_ignore=['all']` di `get_all_records()` (matikan numericise
otomatis gspread sepenuhnya) + parsing manual di `load_positions()` khusus kolom
numerik (`NUMERIC_COLS`) dgn urutan locale Indonesia yang BENAR: hapus titik (pemisah
ribuan) dulu, BARU ganti koma jadi titik (desimal). Kolom tanggal/teks tidak
terpengaruh (gspread tidak pernah menganggapnya angka sejak awal). 4 test regresi
baru (`TestLoadPositionsLocaleParsing`, `tests/test_gsheet_journal.py`) mock
`get_all_records()` dgn nilai locale Indonesia PERSIS dari screenshot sheet asli user
(GDST/APLN/ANTM), assert hasil parsing = nilai asli, BUKAN versi 10x/100x lipat.
119/119 pytest lolos (115 lama + 4 baru).

**Saran ke user**: JANGAN hapus data sheet POSISI dulu - data lama sekarang justru
bisa dibaca ulang dgn BENAR (setelah fix ini, cache `load_positions.clear()` /
refresh app), memberi gambaran performa asli yang jauh lebih baik dari yang tampil
sebelumnya.

## Bug KRITIS #2: Day Trading (BPJS/BSJP) MASIH auto-buy via GitHub Actions, ketinggalan waktu penghapusan

Setelah fix locale P&L di atas, user reboot & lihat data terkoreksi - tapi masih rugi
(Win Rate 20%, Profit Factor 0.08). Ditelusuri lewat "Riwayat Semua Trade": SEMUA 3
trade closed berjenis **BPJS** (Day Trading), bukan Swing - padahal Day Trading sudah
"dihapus total" dari dashboard (`app.py`, lihat "Day Trading dihapus total" di atas).

**Root cause**: `auto_run.py` - script TERPISAH yang dijalankan terjadwal oleh GitHub
Actions (`.github/workflows/auto_backtest.yml`, 2x/hari kerja: 09:15 & 14:45 WIB),
BUKAN dari dashboard - masih memanggil `classify_daytrading_tipe()` +
`build_trade_candidates(..., DONCHIAN_LB_DAY=10, MIN_RR_DAY=2.0)` **TANPA filter
regime IHSG**, membuka posisi BPJS/BSJP otomatis persis seperti sistem Day Trading
lama yang sudah dibuktikan tidak konsisten profit. Penghapusan Day Trading sebelumnya
HANYA menyentuh `app.py` (UI dashboard) - `auto_run.py` (otomasi latar belakang,
sama sekali tidak terlihat dari dashboard) tidak ikut diubah, jadi Day Trading tetap
jalan diam-diam via GitHub Actions setiap hari kerja tanpa disadari siapa pun yang
cuma memantau lewat web.

**Fix**: blok Auto-BUY Day Trading (BPJS/BSJP) di `auto_run.py` dihapus total -
sekarang cuma Auto-BUY Swing (dgn filter regime IHSG, seperti dashboard) + Auto-SELL.
Sekalian dibenahi: Auto-SELL di `auto_run.py` sebelumnya cuma kirim `price_lookup`
(Close-only) ke `auto_close_positions()` - beda dari dashboard yang sudah pakai
`hl_lookup` (High/Low hari itu, lebih presisi, sesuai metodologi backtest) - sekarang
disamakan. Komentar YAML & docstring diperbarui, tidak ada lagi sisa referensi
`day_tipe`/`opened_day`/`DONCHIAN_LB_DAY`/`MIN_RR_DAY` di `auto_run.py`.

**Pelajaran**: kalau ada logika yang sama diduplikasi di lebih dari satu tempat (UI +
automation terjadwal), penghapusan/perubahan HARUS diperiksa di SEMUA tempat, bukan
cuma yang paling terlihat (dashboard). `auto_run.py` sengaja didesain memanggil fungsi
yang sama dgn `app.py` (lihat docstring-nya) justru supaya konsisten - tapi itu tidak
mencegah salah satu sisi lupa diupdate saat keputusan produk berubah.

## Tab "GAP UP/DOWN" & "Open=Low" Dipromosikan Setara "Kandidat"

User berbagi materi umum trading Gap Up/Gap Down (jenis gap - Common/Breakaway/Runaway/
Exhaustion, strategi Gap Fill vs Gap and Go, scoring 0-100, alert Telegram, dashboard,
TradingView Pine Script, Google Sheets scanner, backtest) dan minta dibuatkan sistemnya
"agar ada pilihan terbaik nantinya, buat semua saja". **Sebagian besar materi itu TIDAK
diterapkan apa adanya** - alasannya:

- **Opening range 5-15 menit, VWAP, reaksi harga menit-per-menit** butuh data INTRADAY
  REAL-TIME yang tidak tersedia gratis (Yahoo Finance cuma 60 hari terakhir utk 5m/15m,
  itu pun bukan real-time - lihat README > "Day Trading: Bukan Soal Parameter, Tapi
  Desain Sinyal", riset arc yang sama persis menyimpulkan hal ini utk seluruh Day
  Trading). Membangun "sistem" di atas data yang tidak ada = repeat kesalahan yang sudah
  dibuktikan gagal di Day Trading sebelumnya.
- **Script Telegram terpisah, Google Sheets scanner, Pine Script TradingView** - di luar
  scope: app ini SUDAH SATU sistem terpadu (dashboard + `auto_run.py` + Telegram via
  `telegram_notify.py`, lihat "Bug KRITIS #2" di atas) - menambah 3 stack terpisah lagi
  cuma memecah arsitektur, bertentangan dgn pelajaran "logika terduplikasi di banyak
  tempat lupa disinkron" yang baru saja ditemukan.

**Yang dibangun**: `classify_gap()` di `screener.py` - proxy Gap Up/Down dari data EOD
SAJA (Gap% = Open vs Prev Close hari ini, BUKAN Close vs Close seperti "Perubahan %"),
+ "konfirmasi" (Close tidak membalik penuh ke arah lawan gap - proksi kasar gap-and-go
vs gap-fill dari data harian, bukan bukti intraday sungguhan) + "Gap Breakout" (Gap Up
yg juga breakout Donchian + volume tinggi, semangat "Breakaway Gap"). Disaring likuiditas
sama seperti Kandidat (`Layak Likuiditas`) - sebelumnya pola "Open=Low" JUGA belum
disaring likuiditas, ikut diperbaiki sekalian (user: "yang terpenting adalah kamu tahu
apa kriteria saham yang boleh lolos screener").

**Status tab**: user minta "buat di header karena statusnya setara dengan kandidat, begitu
juga OPEN=LOW dipindah keheader" - keduanya (`t_gap`, `t_openlow`) dipromosikan dari
expander tersembunyi di dalam tab "Semua" jadi TAB TOP-LEVEL sendiri, sejajar visual dgn
"🏆 Kandidat". **Ini status TAMPILAN saja, BUKAN validasi** - keduanya TETAP eksploratif,
BELUM dibacktest, TIDAK masuk Score/Signal/Rekomendasi tervalidasi - caption di tiap tab
menegaskan ini secara eksplisit.

6 test baru (`TestGapUpDown`, `tests/test_screener.py`) - gap up/down terdeteksi & Gap%
dihitung benar, konfirmasi Close vs Open, ambang `gap_min_pct` bisa diatur, kombinasi
dgn breakout+volume. 125/125 pytest lolos (119+6).

### Backtest Gap Up/Down - "Konfirmasi" terbukti bermakna, TAPI bukan sesuai narasi "rebound"

User tempel paket kode generik lain (config/core/notifier/app/backtest/Pine Script/Google
Apps Script terpisah - lihat komit sebelumnya kenapa sebagian besar TIDAK diadopsi) dan
minta "pelajari, kombain sistem yang dibuat agar lebih powerful" + "kita hanya
membandingkan, kalau kita lebih bagus kita pertahankan". Yang diadopsi cuma SATU ide
genuinely baru: metodologi backtest gap-fill vs gap-and-go (entry di Open, ukur return
Close->Close besok, deteksi gap-fill hari yang sama) - dibangun ulang pakai infrastruktur
sendiri (cache 615 saham/5 tahun, `classify_gap()` yang sudah live), BUKAN kode tempelan
mentah (yang pakai universe 20 saham hardcoded, re-fetch Yahoo Finance sendiri, "score"
0-100 generik yang berisiko tabrakan makna dgn kolom "Score" - persis kesalahan yg sudah
diperbaiki berkali-kali sepanjang sesi ini). Skrip: `test_gap_backtest.py` (scratchpad).

Metodologi: walk-forward, disaring `Layak Likuiditas` (SAMA dgn yg ditampilkan live),
ukur return Close[t]->Close[t+1] (no lookahead - keputusan hipotetis di Close[t], t+1
cuma dipakai ukur hasil). Baseline harian pasar (sample 100 saham, tanpa filter gap):
+0,086%/hari.

| Kombinasi | N | Avg Return Next-Day | Split-half (paruh1 / paruh2) |
|---|---|---|---|
| GAP UP + Konfirmasi ✅ | 3.259 | **+0,85%** | +0,66% / +0,95% (konsisten) |
| GAP UP + Konfirmasi ❌ | 5.047 | -0,43% | -0,30% / -0,55% (konsisten negatif) |
| GAP DOWN + Konfirmasi ✅ (lanjut turun) | 2.865 | **-1,39%** | -1,78% / -0,99% (konsisten negatif) |
| GAP DOWN + Konfirmasi ❌ (klaim "rebound") | 3.457 | +0,10% | **-0,07% / +0,45% (BERBALIK ARAH)** |

Temuan:
1. **"Konfirmasi" (proxy EOD gap-fill vs gap-and-go) TERBUKTI bermakna** utk Gap Up (avg
   +0,85% vs baseline +0,09%, ~10x lipat, konsisten 2 periode) dan Gap Down-lanjut-turun
   (-1,39%, konsisten momentum turun beneran).
2. **Klaim umum "Gap Down tanpa konfirmasi = sinyal rebound"** (dari materi trading yang
   dibagikan user) **TIDAK terbukti** di universe IDX ini - arahnya BERBALIK antar paruh
   waktu (rugi tipis di paruh 1, untung di paruh 2) - sample besar (3.457 event) tapi
   TIDAK STABIL, sama persis pola kegagalan confidence-55 SWING TRADE yang sudah
   didowngrade sebelumnya (README > "Backtest Confidence Tier SWING TRADE").
3. Gap Up + Breakout (subset Konfirmasi True + breakout Donchian) avg +1,23% - sedikit
   lebih tinggi dari Konfirmasi True biasa (+0,85%), breakout menambah edge tipis.

**Fix**: caption tab "Gap Up/Down" ([app.py](app.py)) diupdate dgn angka backtest di
atas (bukan lagi "belum dibacktest"). Label kolom "Konfirmasi" utk Gap Down diubah dari
"❌ Tidak (mulai rebound)" jadi "❔ Tidak (arah tidak jelas)" - tidak menyiratkan sinyal
beli yang tidak terbukti. Caption sisi Gap Down juga diperbaiki, tidak lagi menyarankan
"cari kandidat rebound". **Belum diuji**: RR/Entry/SL spesifik utk gap (baru arah return
mentahnya) - jangan jadikan sinyal auto-trade meski sudah ada bukti arah.

### Memperketat filter Gap Up/Down: menaikkan ambang Gap%, BUKAN filter Volume Ratio

User: "10 saham gap down yang masuk screener menurutku terlalu banyak... apa syarat
screener yang kamu buat". Kriteria SEBELUM ini cuma 2: `|Gap%| >= 2%` + `Layak
Likuiditas` (Rp3M/hari) - tidak ada syarat volume tambahan, makanya daftarnya panjang.

Materi trading gap yang dibagikan user (dan intuisi umum) menyarankan tambah filter
**Volume Ratio/RVOL tinggi** sbg penyaring kualitas. **Diuji dulu sebelum diterapkan**
(disiplin sesi ini: jangan tambah aturan tanpa bukti) - hasilnya JUSTRU MENOLAK saran
itu:

| Kombinasi | Tanpa filter volume | Dgn Volume Ratio > 1.5x |
|---|---|---|
| GAP UP + Konfirmasi | +1,22% | **+0,45%** (lebih lemah!) |
| GAP DOWN + Konfirmasi=Tidak | +0,10-0,18% (tidak konsisten) | -0,17% (tetap tidak konsisten) |

Filter Volume Ratio > 1.5x (ambang yang sama dipakai Setup A Breakout & sistem Score)
**MELEMAHKAN** sinyal terbaik (Gap Up+Konfirmasi) dan TIDAK memperbaiki sinyal yang
sudah tidak konsisten (Gap Down tanpa konfirmasi) - kebalikan dari asumsi umum "volume
tinggi = kualitas lebih baik".

**Yang justru terbukti**: menaikkan ambang `gap_min_pct` (2% -> 3%) MEMPERKUAT kedua
sinyal nyata sekaligus mengurangi jumlah kandidat - bukan cuma memfilter, tapi
memperkuat:

| Ambang | GAP UP+Konfirmasi | GAP DOWN+Konfirmasi (lanjut turun) |
|---|---|---|
| 2% | +0,85% | -1,39% |
| **3% (dipakai)** | **+1,42%** | **-2,02%** |
| 4% | +2,19% | -2,54% |

Split-half di ambang 3% tetap konsisten (GAP UP+Konfirmasi: +1,10%/+1,53%; GAP
DOWN+Konfirmasi: -2,55%/-1,49%, keduanya arah sama di 2 periode). Ambang 4% lebih kuat
lagi tapi sample makin kecil - 3% dipilih sbg titik seimbang.

**Fix**: `DEFAULT_PARAMS["gap_min_pct"]` dinaikkan dari 2.0 ke 3.0 di [screener.py](screener.py).
Test di `TestGapUpDown` disesuaikan pakai gap ±4% (bukan persis di garis ambang lama
3%) supaya tidak rapuh kalau ambang diubah lagi ke depan. 125/125 pytest lolos.

### "Gap Trend Aligned" (Harga>MA20>MA50>MA200) - filter terkuat, DIUJI bertahap

User lanjut: "yang paling baik diatas MA200, diatas MA50, diatas MA20... MA50 diatas
MA200... MA20>MA50>MA200" - lalu juga tanya "apakah sudah memperhitungkan momentum?"
dan "apakah filter sudah memperhitungkan volume?". Setiap usulan DIUJI SATU PER SATU
sebelum diterapkan (disiplin sesi ini - jangan tambah aturan tanpa bukti), bertahap dari
sinyal paling sederhana ke paling ketat, semua dgn Gap Up + Konfirmasi sbg basis (avg
+1,42% di ambang 3%):

| Filter tambahan | N | Avg Return Next-Day | Split-half konsisten? |
|---|---|---|---|
| (tanpa filter tren) | - | +1,42% | Ya |
| Harga > MA20 saja | 1.101 | +2,36% | Ya (+1,76% / +2,60%) |
| Harga > MA20 & MA50 & MA200 (urutan bebas) | 853 | +2,55% | Ya |
| + MA50 > MA200 juga | 758 | +2,82% | Ya |
| **Susunan PENUH: Harga>MA20>MA50>MA200** | **674** | **+2,82%** | **Ya (+2,91% / +2,74%)** |
| + Volume Ratio>1,5x (di atas filter penuh) | 320 | +1,27% (LEBIH LEMAH) | - |
| + Volume 5hr naik konsisten (di atas filter penuh) | 455 | +2,68% (tidak lebih baik) | Ya, tapi tidak unggul |

Kesimpulan: **susunan MA penuh (Harga>MA20>MA50>MA200)** adalah filter paling kuat &
konsisten yang ditemukan - dari +1,42% (tanpa filter) jadi **+2,82%** (dgn filter),
sample tersaring dari 1.567 jadi 674 (~43%, sesuai keinginan user "hanya sedikit yang
boleh masuk"). **Volume (baik rasio 1 hari maupun tren rata-rata 5 hari) DIUJI DUA KALI
di atas filter ini juga - KEDUANYA TETAP melemahkan/tidak menambah nilai** - konsisten
dgn temuan sebelumnya (filter Volume Ratio polos), makanya TIDAK dipakai sama sekali di
kriteria final Gap Up, walau disarankan user & materi umum.

**Asimetri penting**: versi bearish simetris (Harga<MA20<MA50<MA200) utk Gap Down
DIUJI TAPI TIDAK terbukti - malah LEBIH LEMAH & tidak konsisten (-2,77% lalu -0,17%
antar paruh, vs -1,97% tanpa filter). Jadi "Gap Trend Aligned" di `classify_gap()`
([screener.py](screener.py)) SELALU `False` utk Gap Down - field ini HANYA valid utk
Gap Up.

**Fix**: `classify_gap()` diperluas menerima `ma20_prev/ma50_prev/ma200_prev` (dihitung
`compute_metrics()` dari Close SEBELUM hari ini, no lookahead), mengembalikan field baru
`trend_aligned`. Tab "Gap Up" ([app.py](app.py)) sekarang **DIFILTER KERAS** (bukan cuma
kolom info) - hanya tampilkan `Gap Konfirmasi=True AND Gap Trend Aligned=True`. Kolom
"Konfirmasi" dihapus dari tampilan (selalu True stlh difilter, redundan - sama alasan
dgn penghapusan kolom "Harga"=Entry sebelumnya). Tab "Gap Down" TIDAK diberi filter tren
(tidak terbukti), tetap informasional seperti sebelumnya.

Bug kecil ikut ditemukan & diperbaiki saat menulis test: `prev_close` di
`compute_metrics()` tidak pernah di-`float()`-kan (beda dari `close`/`open_` yang
sudah) - bikin hasil perbandingan `numpy.bool_` bukan `bool` Python murni (ketahuan
lewat test yang assert `is True/False`, gagal walau nilainya benar). Diperbaiki
sekalian.

4 test baru (`test_trend_aligned_*`, `TestGapUpDown`) - pakai helper baru
`_uptrend_ohlcv()` (histori naik linear 250+ hari, `_flat_ohlcv` tidak cukup krn perlu
MA200 & harga benar-benar uptrend). 129/129 pytest lolos (125+4).

### "Gap Trend Aligned" dibuat OPSIONAL - MA200 lamban saat pergantian rezim

User (2026-08-10): "saya berfikir mungkin screener kita terlalu ketat karena harus
MA20>MA50>MA200... saya saat ini ihsg dari bearing kencang menuju bullish, sehingga
banyak saham2 bagus tidak muncul di screener". Keluhan ini valid secara teknikal, bukan
cuma perasaan: MA200 adalah rata-rata 200 hari - LAMBAN mengikuti perubahan rezim. Saat
IHSG baru berbalik dari bearish tajam ke bullish, saham yang harganya SUDAH uptrend bisa
tetap gagal syarat `Harga>MA20>MA50>MA200` semata krn MA200 masih "mengingat" rezim lama
(butuh waktu lama utk MA200 sendiri berbalik naik/didekati harga). Filter yang tervalidasi
kuat di kondisi pasar NORMAL (+2,82% vs +1,42%, lihat tabel di atas) berisiko membuang
kandidat early-recovery yang genuinely bagus justru di momen paling menguntungkan
(awal tren baru).

**Fix**: filter tidak dihapus (tetap tervalidasi & jadi default), tapi dibuat OPSIONAL.
Checkbox baru "Wajib Trend Aligned (MA20>MA50>MA200)" di tab Gap Up/Down (`app.py`,
default **ON** - mempertahankan perilaku tervalidasi). Kalau di-nonaktifkan, kriteria Gap
Up mundur ke `Gap Konfirmasi=True` saja (avg +1,42%/hari berikutnya - masih positif &
konsisten, tapi lebih lemah & sample lebih besar) + kolom "Trend Aligned" ditampilkan
sbg info (bukan filter) agar user tetap bisa lihat mana yang lolos susunan MA penuh vs
tidak. Help text checkbox menjelaskan tradeoff-nya. Tidak perlu backtest baru - ini murni
memberi kontrol on/off ke user atas filter yg SUDAH diuji, bukan sinyal baru.

### Backtest Open=Low - edge NYATA tapi lebih kecil dari fee, TIDAK divalidasi seperti Gap

User share materi umum "cara trading Open=Low (Shaven Bottom)" (sama gaya dgn materi
Gap sebelumnya) dan minta dipelajari "untuk pengembangan Open=Low... sudah sering pakai
ini cukup bagus, cuma resiko harus dipantau". Klaim lama di kode ("TIDAK bisa
dibacktest, butuh order book real-time") ternyata cuma benar utk KONFIRMASI order book-
nya - ARAH RETURN setelah pola ini muncul tetap bisa diuji EOD, metodologi SAMA dgn Gap
(walk-forward Close[t]->Close[t+1], disaring likuiditas, 615 saham/5 tahun).

| Kombinasi | N | Avg Return Gross | Split-half | Setelah fee 0,4% |
|---|---|---|---|---|
| Setup A (breakout+volume>1.5x) | 1.211 | +0,26% | Konsisten (+0,04%/+0,48%) | **-0,14% (negatif)** |
| Setup B + Trend Aligned (Harga>MA20>MA50>MA200) | 3.847 | +0,30% | Konsisten (+0,10%/+0,50%) | **-0,10% (negatif)** |
| Setup B tanpa filter (baseline) | 17.738 | +0,02% | TIDAK konsisten (-0,06%/+0,10%) | - |

Temuan: pola Open=Low PUNYA edge nyata & konsisten arah (bukan nol/random), TAPI
magnitude-nya (~0,26-0,30%/hari) **lebih kecil dari fee round-trip** (0,15%+0,25%) kalau
exit dipaksa 1 hari - net-nya negatif. Ini **jauh lebih lemah** dari Gap Up (+2,82%
setelah filter tren yang sama). Kemungkinan edge sesungguhnya (yang bikin pengalaman
user "cukup bagus") ada di 2 hal yang TIDAK bisa diuji dgn data historis EOD: (1)
konfirmasi order book real-time "Makan Kanan" saat entry, (2) exit RR/trailing-stop
multi-hari (bukan exit paksa Close hari berikutnya seperti metodologi uji ini).

**Fix**: TIDAK diberi status "sudah divalidasi" atau filter keras seperti Gap Up -
tetap eksploratif. Ditambahkan field "Open=Low Trend Aligned" (`screener.py`, reuse
persis logika `ma20_prev/ma50_prev/ma200_prev` yg sudah dihitung utk `classify_gap()`,
dipindah ke lebih awal di `compute_metrics()` supaya bisa dipakai dua-duanya tanpa
hitung ulang) - ditampilkan sbg kolom info tambahan di Setup B, BUKAN filter keras
(caption di [app.py](app.py) menjelaskan magnitude-nya masih di bawah fee). 2 test baru
(`test_open_low_trend_aligned_*`). 131/131 pytest lolos (129+2).

## Filter Anti-Kejar Harga - build_trade_candidates() menolak entry yang sudah lari jauh dari Open

User lapor kejadian nyata: klik "Buka Posisi Swing Trading" di waktu sembarang (bukan
pas market baru buka), akibatnya beli saham yang SUDAH naik 14% dari harga pembukaan
hari itu - koreksi kecil setelahnya langsung kena Stop Loss (kasus nyata di sheet
POSISI: **SLIS** beli Rp88, LOSS SL di Rp79, **-10,63%**).

**Akar masalah**: `build_trade_candidates()` pakai `entry = float(r["Harga"])` - harga
SEKARANG, apa adanya, tanpa peduli apakah harga itu sudah jauh dari Open hari itu atau
belum. SL dihitung dari Donchian Low/MA20 (level struktural, TIDAK menyesuaikan diri
kalau entry-nya sendiri sudah "kemahalan" krn rally intraday) - jadi kalau beli di
puncak rally lalu ada retracement wajar sedikit saja, SL (yang jaraknya dihitung dari
level lama) lebih mudah tersentuh.

**Backtest** (615 saham/5 tahun, walk-forward, simulasi realistis Entry/SL/Target/RR
SAMA persis dgn `build_trade_candidates()`, dipecah per seberapa jauh Entry sudah naik
dari Open hari itu):

| Naik dari Open saat Entry | N | SL Rate | Avg Net Return | Split-half |
|---|---|---|---|---|
| ≤0% | 1.107 | 60,3% | +3,55% | +1,22% / +5,89% |
| 0-3% | 4.178 | 55,6% | +0,48% | +0,17% / +0,78% |
| 3-6% | 5.016 | 60,2% | +0,15% | -0,07% / +0,37% (tidak konsisten) |
| 6-10% | 3.293 | 65,0% | +0,53% | -0,00% / +1,06% (tidak konsisten) |
| **>10%** | **2.706** | **69,9%** | **-0,19%** | **-0,18% / -0,20% (KONSISTEN NEGATIF)** |

Bucket `>10%` adalah SATU-SATUNYA yang konsisten negatif di kedua paruh waktu (hampir
identik magnitude-nya, -0,18% vs -0,20%) - bucket lain (3-6%, 6-10%) malah tidak
konsisten arahnya, jadi ambang `>10%` dipilih sbg titik potong yang jelas & robust,
bukan cuma yang "kelihatan buruk" di rata-rata gabungan.

**Fix**: `build_trade_candidates()` (`screener.py`) dapat parameter baru
`max_naik_dari_open_pct` (default **10.0**) - kandidat yang "Naik dari Open %"-nya
(kolom baru, `compute_metrics()`: `(Harga - Open) / Open * 100`, BEDA dari "Perubahan %"
yang bandingkan ke Close KEMARIN bukan Open HARI INI) sudah lebih dari ambang ini
otomatis dilewati - berlaku baik utk klik manual di dashboard MAUPUN jadwal otomatis
`auto_run.py` (satu fungsi, dua caller). Kolom "Naik dari Open %" ditambahkan ke tabel
Kandidat ([app.py](app.py)) supaya user bisa lihat langsung seberapa "segar" sinyalnya
saat mau klik beli.

4 test baru (`TestFilterAntiKejarHarga`) - kandidat yg melebihi ambang dilewati, yang
di dalam ambang tetap lolos, ambang bisa diatur manual, dan tabel tanpa kolom ini
(caller lama) tetap jalan tanpa crash. 135/135 pytest lolos (131+4).

## BUY vs SELL Beda Jadwal - auto_run.py cuma scan BUY sore, cek JUAL kapan saja

User tanya "apakah tidak bisa otomatis ditentukan jam kapan beli, kapan sell" - jawabannya
SUDAH otomatis (2x/hari via `auto_run.py` + GitHub Actions, sejak fix "Bug KRITIS #2"),
TAPI diskusi lanjutan ("kita berfikir sejenak... sekarang disepakati apakah swing membeli
pagi hari atau sore hari") menemukan bug desain: BUY dan SELL dijalankan di JAM YANG SAMA
(09:15 & 14:45 WIB) padahal KEBUTUHAN DATANYA BEDA.

**Kerangka yang disepakati** (user): beli saat ada kandidat BUY, tutup kalau kena SL,
kalau batas hari tercapai tapi TP belum kena, atau kalau TP tercapai - ini SUDAH tepat
sesuai implementasi (SL dicek dulu, baru TP, force-sell 15 hari). Yang didiskusikan
adalah JAM-nya.

**Analisis**: SELURUH sistem yang sudah divalidasi sepanjang sesi ini (Score/Signal, Gap
Up/Down, Open=Low) dibacktest dgn asumsi data **1 HARI PENUH/settled** - Volume Ratio vs
rata-rata 20 hari, breakout status, Perubahan %, semuanya perlu data yang representatif
utk hari itu. Kalau scan BUY dijalankan **pagi** (09:15 WIB, 15 menit setelah bursa buka):
Volume Ratio baru mencerminkan sebagian KECIL hari itu (tidak representatif dibanding
rata-rata 20 hari PENUH), breakout/Perubahan % juga belum matang - Score/Signal yang
dihitung DI LUAR asumsi backtest-nya sendiri. Kalau dijalankan **sore** (14:45 WIB,
mendekati penutupan sesi II ~15:49-16:00 WIB): data hampir 1 hari penuh, jauh lebih
representatif & konsisten dgn metodologi backtest.

Sebaliknya, cek **JUAL** (SL/TP posisi yang SUDAH OPEN) tidak punya masalah ini - cuma
membandingkan harga terkini vs level SL/TP yang SUDAH ditetapkan saat entry, tidak butuh
data "1 hari penuh" - aman dicek kapan saja, termasuk pagi.

**Fix**: `auto_run.py` (`main()`) sekarang cek jam (`datetime.now(WIB).hour >= 12`):
- **Pagi** (<12:00 WIB, run 09:15): SKIP scan 962 saham & BUY sepenuhnya (buang2 kuota
  Yahoo Finance kalau tetap discan tapi tidak dipakai) - cuma jalankan
  `gj.auto_close_positions({}, {})` (self-fetch harga khusus saham yg statusnya OPEN,
  jauh lebih ringan) utk cek SL/TP/force-sell.
- **Sore** (>=12:00 WIB, run 14:45): scan penuh 962 saham + BUY (dgn regime filter & filter
  anti-kejar-harga yg sudah ada) + cek JUAL seperti sebelumnya.

Komentar `.github/workflows/auto_backtest.yml` diperbarui menjelaskan pembagian jadwal
ini. Tidak ada perubahan pada `build_trade_candidates()`/`gsheet_journal.py` - murni
`auto_run.py` yang dipecah alur eksekusinya berdasarkan jam.

## Cooldown re-entry 1x/hari + gate BUY manual - lanjutan temuan dari sheet POSISI

User share screenshot sheet POSISI (2026-08-10) dan bertanya "mungkin ini hanya
kegagalan di backtest, bukan sistem/kandidat" - dicek langsung, jawabannya CAMPURAN,
bukan salah satu semata:

1. **BUKAN kegagalan tracking**: baris yang closed **BREAKEVEN** (MCAS, ESTI, SLIS
   -0,4%) itu **trailing stop bekerja SESUAI DESAIN** (README > "Trailing Stop ke
   Breakeven") - harga sempat kena 1R, SL ditarik ke entry, lalu berbalik & closed
   dekat entry (rugi kecil = ongkos transaksi). Ini hasil BAIK, bukan bug.
2. **Sebagian memang data lama (sudah diperbaiki)**: entri paling pagi (09:18 WIB,
   2026-08-07) terjadi SEBELUM fix pemisahan jadwal BUY sore/SELL kapan saja (`cbf9fdb`,
   dideploy 11:35 WIB HARI YANG SAMA) - jadi bukan cerminan sistem saat ini.
3. **TAPI ditemukan 2 celah NYATA & MASIH AKTIF** (bukan soal backtest sama sekali,
   soal *risk management* sistem hidup):
   - **Tidak ada cooldown re-entry**: SLIS/ESTI/PTMP di sheet masing2 dibuka **2x DALAM
     1 HARI** - kena SL pagi/siang, lalu re-entry lagi sore krn masih lolos jadi
     kandidat. Guard lama di `open_positions_from_candidates()` (`gsheet_journal.py`)
     cuma cek "Status == OPEN sekarang", tidak cek "sudah pernah dibuka HARI INI" -
     begitu posisi lama ditutup (menang/rugi/breakeven apapun), sistem bebas beli lagi
     saham yang sama hari itu juga, berpotensi ngejar saham yang baru saja gagal.
   - **Tombol manual "Buka Posisi Swing Trading" (`app.py`, tab Performance) TIDAK
     ikut digate jam** seperti `auto_run.py` - ini kemungkinan ROOT CAUSE komplain user
     paling awal sesi ini ("klik mungkin waktunya, SLIS kena SL, beli diharga agak
     tinggi") - cron GitHub Actions sudah digate (`is_sore`) tapi tombol dashboard,
     yang bisa diklik user kapan saja, TIDAK ikut aturan yang sama.

**Fix**: (a) `open_positions_from_candidates()` sekarang skip saham yg
`Tanggal Open`-nya = hari ini, terlepas dari statusnya (OPEN/closed apapun) - cooldown
1x buka/saham/hari. (b) Tombol "🟢 Buka Posisi Swing Trading" di-`disabled` kalau jam
< 12:00 WIB (sama persis kondisi `is_sore` di `auto_run.py`), dgn caption penjelasan;
"🔴 Cek TP/SL & Force-Sell" TETAP boleh kapan saja (keluar posisi tidak ada alasan
ditunda). 2 test baru (`TestReEntryCooldown`) memverifikasi cooldown skip closed-hari-
ini tapi tetap boleh re-entry di hari yg berbeda. 141/141 pytest lolos.

## Trailing Stop ke Breakeven - DIHAPUS 2026-08-20 (lihat "Target-Lock" di bawah)

> **SUPERSEDED**: mekanisme di bagian ini sudah **DIHAPUS TOTAL** dari kode 2026-08-20 -
> terbukti sistematis MEMOTONG untung (bukan cuma melindungi dari rugi), lihat "Target-Lock:
> Kunci Untung, Bukan Kunci Rugi". Dipertahankan sbg riwayat/pelajaran saja.

## (Riwayat) Trailing Stop ke Breakeven - jawaban atas "apakah bisa memprediksi reversal sebelum TP"

User tanya: "apakah sistem yang kita bangun dapat memprediksi bahwa akan terjadi
reversal sebelum target TP tercapai... kelemahan saya disini... yang saya maksud ada
uang real." Jawaban jujur: **TIDAK bisa memprediksi** - SL/TP di sistem ini statis,
ditetapkan sekali saat entry, tidak pernah disesuaikan lagi. Memprediksi reversal
dengan pasti nyaris mustahil (bahkan trader profesional tidak bisa) - yang REALISTIS
& bisa diuji adalah **trailing stop**: menaikkan SL begitu profit tertentu tercapai,
supaya kalau reversal memang terjadi, untung yang sudah ada terkunci sebagian, tidak
hilang balik ke breakeven/rugi.

**Backtest** (615 saham/5 tahun, walk-forward, simulasi realistis Entry/SL/Target/RR):
dibandingkan SL/TP TETAP (baseline) vs trailing SL ke breakeven begitu profit
(dari High hari itu) mencapai 1x risk awal (Harga Beli - SL Awal):

| | Avg Net Return | Win Rate | Total | Split-half |
|---|---|---|---|---|
| SL/TP TETAP (sebelumnya) | +0,62% | 31,7% | +8.431% | -0,02% / +1,26% |
| **Trailing ke breakeven (1R)** | **+0,78%** | 24,8% (turun) | **+10.579%** | **+0,10% / +1,46%** |

Trailing MENANG di kedua periode uji (selisih +0,12% & +0,20% - konsisten), walau Win
Rate turun (lebih sering exit di breakeven drpd nunggu TP) - itu wajar & memang tujuan
trailing: menukar sebagian "kemenangan penuh" jadi "kemenangan kecil/breakeven", demi
menghindari rugi dalam kalau reversal beneran terjadi.

**Fix**: kolom baru **N: SL Awal** ditambahkan ke struktur sheet POSISI
([gsheet_journal.py](gsheet_journal.py), `HEADERS`) - SL ASLI saat posisi dibuka, TIDAK
PERNAH diubah, beda dari kolom E (SL) yang BISA ditrail naik. `open_positions_from_candidates()`
menulis SL Awal = SL saat buka. `auto_close_positions()`: kalau posisi belum exit hari
itu, cek apakah High hari ini sudah mencapai `Harga Beli + 1x(Harga Beli - SL Awal)` -
kalau iya, SL (kolom E) dinaikkan SEKALI ke Harga Beli (breakeven) via `ws.update()`,
posisi TETAP OPEN. Exit yang kena SL SETELAH ditrail dilabel **"BREAKEVEN"** (bukan
"LOSS (SL)") - `summarize()` diperbaiki sekalian supaya BREAKEVEN diklasifikasi WIN/LOSS
dari tanda P&L-nya (sama kelas bug dgn FORCE SELL yang sudah diperbaiki sebelumnya).
Baris LAMA (dibuka sebelum kolom ini ada, kosong di sheet) fallback ke SL saat ini
sbg SL Awal - tetap bisa trailing (krn baris yg belum pernah ditrail, SL saat ini =
SL asli), TIDAK crash.

`TRAILING_TRIGGER_R = 1.0` (konstanta, `gsheet_journal.py`) - cuma trailing 1 langkah
ke breakeven, BELUM diuji versi bertingkat (mis. trail lagi ke +0.5R setelah +2R, dst).
4 test baru (`TestTrailingStopBreakeven`) - trigger saat profit>=1R, tidak trigger
kalau belum 1R, label BREAKEVEN yang benar, dan baris lama tanpa kolom ini tetap jalan.
139/139 pytest lolos (135+4).

## Bug: "Berita Terkini" Tidak Pernah Berubah - Fallback Statis Dikira Live

User lapor: "berita terkini tidak pernah berubah". Ditelusuri ke `fetch_sentiment_news()`
([app.py](app.py), tab Sentiment): kalau `NEWSAPI_KEY` belum diisi ATAU panggilan API-nya
gagal, fungsi diam2 jatuh ke **3 berita CONTOH yang di-hardcode** (dgn timestamp palsu
"2h ago"/"5h ago" yang MEMANG tidak pernah berubah) - sudah ada peringatan kuning di UI
soal ini, tapi user tidak menyadarinya/inginnya beneran live.

**Kenapa NewsAPI selalu gagal**: `NEWSAPI_KEY` kemungkinan belum diisi di secrets. Bahkan
kalau diisi, NewsAPI free tier ("Developer") per Terms of Service mereka sendiri **TIDAK
BOLEH dipakai di app production/publik** - cuma utk pengembangan lokal. Jadi solusinya
BUKAN sekadar "isi API key", tapi ganti sumber utama ke yang gratis & sah dipakai publik.

**Solusi**: RSS feed publik (TIDAK butuh API key/subscription) - diverifikasi manual satu
per satu (bukan asumsi):

| Sumber | URL | Status |
|---|---|---|
| CNBC Indonesia (Market) | `cnbcindonesia.com/market/rss/` | ✅ Jalan, topik market |
| IDX Channel | `idxchannel.com/rss` | ✅ Jalan, feed umum (disaring kata kunci) |
| Katadata | `katadata.co.id/rss` | ✅ Jalan, feed umum (disaring kata kunci) |
| Kontan | `kontan.co.id/feed`, `rss.kontan.co.id/...` | ❌ 403 (blokir bot) walau User-Agent browser wajar |
| Bisnis.com | `rss.bisnis.com/`, `market.bisnis.com/rss` | ❌ 403 (blokir bot) |

Kontan & Bisnis.com **TIDAK dipaksa** dgn teknik bypass deteksi bot apa pun (di luar
scope yang boleh dibantu, berlaku umum jadi prinsip di seluruh proyek ini) - cuma 3 feed
yang benar-benar merespons normal yang dipakai.

**Fix**: `fetch_sentiment_news()` sekarang coba **RSS dulu** (`_fetch_rss_news()`, gratis,
tanpa key) sbg sumber UTAMA - NewsAPI jadi cadangan KEDUA (kalau RSS kosong & key
tersedia), fallback statis HANYA kalau KEDUANYA gagal. Filter relevansi
(`_NEWS_RELEVANCE_KEYWORDS`) & klasifikasi sentimen (`_classify_sentiment()`, sekarang 1
fungsi dipakai bersama RSS & NewsAPI, tidak lagi ditulis dobel) tetap sama seperti
sebelumnya. Diverifikasi langsung (live network call, bukan asumsi): 5 berita ASLI &
BERBEDA ditemukan dari CNBC Indonesia + IDX Channel dalam satu percobaan - bukan lagi 3
contoh statis yang sama setiap kali dimuat.

## Default Universe Saham: Syariah (ISSI)

Atas permintaan user, dropdown "Universe Saham" di sidebar sekarang default ke **"Syariah
(ISSI)"** (649 saham) - bukan "Semua" (962 saham) lagi. Tetap bisa diganti manual ke "Semua"
atau "Konvensional" kapan saja.

## Cara Kerja Fitur Trading

### Day Trading — BPJS & BSJP
- **BPJS** (Beli Pagi Jual Sore): otomatis dipilih sistem kalau sekarang sebelum jam 13:00 WIB
- **BSJP** (Beli Sore Jual Pagi): otomatis dipilih kalau sekarang jam 13:00 WIB ke atas
- Force-sell otomatis: BPJS ditutup paksa kalau lewat 1 hari, BSJP kalau lewat 2 hari (belum kena TP/SL)

### Swing Trading
- Force-sell otomatis kalau sudah 15 hari dan belum kena TP atau SL
- Bisa dibuka kapan saja (pagi/sore), tidak terikat waktu seperti Day Trading
- **Digate kondisi pasar**: cuma buka posisi baru kalau IHSG di atas MA50 (bisa dimatikan di
  sidebar, tapi hasilnya tidak lagi terjamin sama seperti hasil backtest - lihat bagian
  "Hasil Validasi Parameter Default" di atas)

### Perhitungan Entry / Target / Stop Loss (bukan persen tetap)
- **Entry**: harga saat ini
- **Stop Loss**: yang PALING KETAT (paling dekat entry) dari 3 kandidat - Donchian Low
  (struktural), MA20, atau 10% di bawah entry (cap) - lihat "Regresi: Fix di Atas Ternyata
  Pakai Formula Stop Loss yang LEBIH BURUK" utk bukti backtest kenapa capped dipilih drpd
  Donchian Low murni (menang di semua metrik, Risiko% tidak pernah lebih dari 10%)
- **Target**: proyeksi *measured move* = Donchian High + lebar channel (High − Low)
- **RR (Risk:Reward)**: (Target − Entry) / (Entry − Stop Loss), tabel Kandidat hanya menampilkan
  RR ≥ ambang minimum - default **1.5:1 untuk Swing** (divalidasi), **2.0:1 untuk Day Trading**
  (belum divalidasi ulang, dipertahankan dari default lama)

### Panel Moving Averages & Technical Indicators (tab Grafik Saham)
Format meniru tampilan referensi Bro (MA5-MA200 Simple/Exponential dengan verdict Buy/Sell,
plus RSI/Stochastic/StochRSI/MACD/ADX/CCI/Ultimate Oscillator/Williams %R dengan verdict Buy/Sell/Neutral).
**Catatan jujur**: aturan Buy/Sell di sini pakai konvensi analisis teknikal standar per indikator
(dijelaskan di `indicators.py`) - bukan hasil tiru-persis formula proprietary aplikasi manapun,
jadi verdict-nya bisa beda tipis dari app lain untuk kondisi borderline.


- **Yahoo Finance via `yfinance` tidak resmi** — sewaktu-waktu bisa berubah/berhenti tanpa
  pemberitahuan, sama seperti risiko Power Query di versi Excel. Kalau dashboard tiba-tiba
  error "no data", biasanya itu penyebabnya — coba lagi beberapa saat.
- **Free tier Streamlit Cloud akan "tidur"** kalau tidak diakses ±beberapa hari. Saat dibuka
  lagi, loading pertama bisa 20-30 detik sebelum aktif kembali — normal, bukan error.
- Memindai 615 saham sekaligus makan waktu; gunakan slider **"Jumlah saham dipindai"** di
  sidebar untuk mempercepat (mis. 100-200 saham teratas dulu untuk uji coba).
- Ini bukan rekomendasi keuangan. Semua skor & sinyal adalah alat bantu screening, keputusan
  akhir tetap di tangan Bro.

## Bug: Tutup Posisi di Jurnal Real Diam-diam Salah Sasaran (duplikat "No")

User: "saya akan tutup posisi BWPT target harga 96, tetapi saya jual di harga 91 karena
market lagi bearish. mengapa tidak bisa saya catat tutup diharga 91" - gejalanya: tidak ada
pesan error, tapi setelah disimpan Status BWPT tetap OPEN & Harga Exit tetap kosong.

Dicek ke kode: field "Harga Exit" (`app.py`, tab Jurnal Real > Tutup Posisi) memang BEBAS
isi angka berapa saja, tidak dibatasi harus di TP/SL - jadi 91 seharusnya tersimpan tanpa
masalah. Root cause sebenarnya ada di `real_journal.py`: `close_trade()`/`delete_trade()`/
`edit_trade()` dulu cari baris cuma lewat `trades[trades["No"]==no].iloc[0]` TANPA cek
apakah hasilnya lebih dari 1 baris. Ini PERSIS risiko yang sudah pernah didokumentasikan di
`TestOpenTradeNumbering` (lihat `tests/test_real_journal.py`) saat `open_trade()` diperbaiki
dari `No=len(existing)+1` jadi `No=MAX(No)+1` - TAPI baris yang KADUNG duplikat SEBELUM fix
itu tidak otomatis dibersihkan dari sheet, dan sisi baca (`close_trade` dkk.) tidak pernah
ikut diperbaiki. Kalau "No" BWPT kebetulan sama dengan trade LAIN yang sudah closed lebih
dulu, `close_trade()` diam-diam meng-update baris trade lama itu (berhasil, tidak ada
exception) - BWPT sendiri tidak pernah tersentuh, makanya user tidak lihat pesan error tapi
datanya juga tidak berubah.

**Fix**: helper baru `_find_trade_row()` dipakai oleh ketiga fungsi - kalau ditemukan >1
baris dgn "No" yang sama, TOLAK TEGAS dgn pesan jelas (minta user cek kolom "No" di
spreadsheet) drpd diam-diam update baris yang salah. Khusus `close_trade()` (menutup posisi
yang SPESIFIK sedang OPEN): kalau di antara yang duplikat ada tepat SATU baris berstatus
OPEN, disambiguasi otomatis ke situ dulu (baru dianggap benar2 ambigu kalau masih >1 kandidat
setelah itu) - jadi kasus BWPT (duplikat dgn trade lama yang SUDAH closed) kemungkinan besar
langsung tertangani otomatis tanpa user perlu beberes data manual. 5 test baru
(`TestFindTradeRowDuplicateNo`), 146/146 pytest lolos.

## Lanjutan Bug Duplikat "No": Dropdown "Hilang" & Field Edit Tidak Update

Sesudah fix di atas dipasang (`_find_trade_row()`), 2 masalah LANJUTAN muncul dari kasus
duplikat "No" (BWPT & DOOH sama-sama No=9) yang sama:

1. **"nomor 9 2x muncul dengan saham yang berbeda saya mau hapus bwpt tidak bisa karena
   tidak muncul"** - dropdown "Pilih nomor trade" (tab Tutup Posisi & Edit/Hapus, `app.py`)
   dulu pakai KOLOM "No" sbg VALUE `st.selectbox`. Kalau "No" kembar, Streamlit tidak bisa
   membedakan 2 pilihan dgn value yang identik - salah satu (BWPT) efektif "hilang", tidak
   bisa dipilih terpisah dari yang lain. **Fix**: identitas dropdown diganti pakai INDEX
   BARIS DataFrame (dijamin unik, beda dari "No" yang bisa kembar), dipasangkan dgn 3 fungsi
   baru di `real_journal.py` - `close_trade_at_row()`, `delete_trade_at_row()`,
   `edit_trade_at_row()` - yang menargetkan baris LANGSUNG lewat index, tidak perlu cari
   ulang lewat "No" sama sekali (jadi aman berapa pun banyaknya "No" yang kembar di data
   lama). 4 test baru (`TestCloseEditDeleteAtRow`).

2. **"saya sudah pilih dooh tapi tidak update kolom untuk hapus/edit"** - begitu dropdown
   sudah bisa membedakan BWPT/DOOH, muncul bug LAIN: ganti pilihan dropdown, field2 di
   bawahnya (Tanggal Entry, Lot, Entry, SL, Target, dst.) TIDAK ikut berubah, tetap
   menampilkan data trade SEBELUMNYA. Ini PERSIS pola bug yang SAMA dgn Kalkulator (lihat
   "Fix: pilih saham di Kalkulator..." di atas): field2 itu pakai `value=row_edit[...]` pada
   widget BERKUNCI (`key="e_tgl"` dkk.) - `value=` cuma berlaku di render PERTAMA widget itu,
   ganti pilihan dropdown sesudahnya tidak memicu re-evaluasi `value=`. **Fix**: tambah
   `on_change` di selectbox yang menulis LANGSUNG ke `st.session_state` semua field terkait
   SEBELUM widget2 itu dibuat (fungsi `_isi_form_edit()`), `value=`/`index=` dihapus dari
   semua field edit - konsisten dgn pola yang sudah dipakai di Kalkulator. Render pertama
   (belum pernah ganti dropdown) tetap terisi otomatis lewat pemanggilan manual satu kali
   (`if "e_lot" not in st.session_state: _isi_form_edit()`).

150/150 pytest lolos setelah kedua fix ini.

## Tanggal di Edit/Hapus Jadi Kalender (dulu Harus Diketik)

User: "tanggal di header edit hapus harus diketik" - field "Tanggal Entry" & "Tanggal Exit"
di tab Jurnal Real > Edit/Hapus dulu pakai `st.text_input` polos (format "YYYY-MM-DD" harus
diketik manual), TIDAK konsisten dgn tab "Tutup Posisi" yang sudah pakai `st.date_input`
(klik kalender).

**Fix**: "Tanggal Entry" diganti `st.date_input` langsung (selalu ada isi, tidak pernah
kosong - aman). "Tanggal Exit" beda kasus - bisa KOSONG kalau posisi masih OPEN, dan
`st.date_input` tidak punya konsep "kosong" - diselesaikan lewat checkbox baru "Posisi ini
sudah CLOSED": dicentang baru muncul date_input (klik kalender) + Harga Exit wajib diisi,
tidak dicentang berarti OPEN (Tanggal Exit otomatis dikirim kosong, sama seperti perilaku
lama). String tanggal tersimpan (mis. "2026-07-30") diparse ke objek `date` lewat
`_parse_tanggal_edit()` - fallback ke hari ini kalau kosong/formatnya rusak, drpd crash.

## Bug Performa: build_screener_table() Tidak Di-cache, Diulang Tiap Klik

User: "yang saya rasakan aplikasi ini sangat lambat loadingnya" - lalu dikonfirmasi lambatnya
**TERUS-MENERUS** (bukan cuma sesekali/pas awal buka).

Audit arsitektur: sebagian besar fitur AMAN (Sentiment di-cache 30 menit; Fundamental
Screener/Value Invest/Perbandingan Saham semuanya di balik tombol, tidak auto-jalan). Root
cause sebenarnya: `build_screener_table()` (hitung Score/Signal/MA20/50/200/Donchian/Gap utk
sampai 400 saham) **TIDAK di-cache sama sekali** - padahal fetch harga mentahnya
(`get_price_history_with_report`, via `_fetch_price_history_cached_v2`) SUDAH di-cache 15
menit. Karena `st.tabs()` menjalankan ULANG SELURUH skrip (termasuk ~19 tab, terlepas mana
yang sedang dibuka user - fakta arsitektur yang sudah diverifikasi sesi ini) di SETIAP
interaksi APA PUN di app (klik tab lain, ubah slider di sidebar yang tidak terkait, dst.),
perhitungan CPU berat ini (rolling MA/Donchian/klasifikasi gap utk ratusan saham) diulang
dari nol tiap klik - bukan cuma saat data live benar2 di-refresh.

**Fix**: fetch+compute dibungkus jadi SATU fungsi ter-cache `_scan_dan_bangun_tabel(tickers,
params)` (`app.py`), kunci cache = tickers + params (pola SAMA yang sudah dipakai
`_fetch_price_history_cached_v2` di `screener.py`), ttl 300 detik. **Diverifikasi lewat
preview lokal** (bukan cuma py_compile/pytest): scan awal 398/400 saham berhasil, lalu pindah
tab lain - caption "Terakhir refresh" TETAP menunjukkan jam yang SAMA (bukti cache benar2
dipakai, tidak fetch/hitung ulang). 150/150 pytest tetap lolos (tidak ada regresi fungsional).

## Regresi: "Simpan Perubahan" Error TypeError int64 (dari Fix Dropdown Sendiri)

User klik "Simpan Perubahan" di tab Edit/Hapus, langsung error `TypeError: Object of type
int64 is not JSON serializable` (log Streamlit Cloud). Ini REGRESI dari fix dropdown
"index baris" sesi ini sendiri: `edit_trade_at_row()` dipanggil dgn `row_edit["No"]` - hasil
akses LANGSUNG ke Series pandas (`trades_edit.loc[idx]`) - yang bertipe `numpy.int64`, BUKAN
`int` Python biasa. Kode LAMA (`pilih_edit_no` dari `st.selectbox(options=trades_edit["No"]
.tolist(), ...)`) AMAN krn `.tolist()` otomatis mengonversi numpy.int64 jadi `int` murni -
begitu identitas dropdown diganti ke index baris (utk fix bug "No" duplikat), jalur konversi
implisit ini ikut hilang tanpa disadari.

gspread men-JSON-kan tiap sel sebelum dikirim ke Google Sheets API - tipe numpy (int64/
float64) TIDAK bisa di-JSON-kan langsung oleh `json.dumps()` bawaan Python, beda dari int/
float murni yang bisa.

**Fix**: cast eksplisit SEMUA nilai numerik (`no`, `entry`, `sl`, `target`, `lot`,
`exit_price`) ke tipe Python murni (`int()`/`float()`) tepat sebelum ditulis ke sheet, di
`edit_trade_at_row()`, `edit_trade()`, DAN `_close_at_sheet_row()` (dipakai `close_trade()`/
`close_trade_at_row()`) - drpd berharap semua pemanggil (sekarang & masa depan) selalu kirim
tipe yang benar. Cast tambahan juga di titik panggil (`app.py`: `int(row_edit["No"])`)
sbg lapisan kedua. 2 test baru (`TestNoNumpyLeakKeSheet`) memverifikasi lewat `json.dumps()`
LANGSUNG ke payload yang akan dikirim (bukan cuma cek nilainya benar) - reproduksi persis
kasus numpy.int64 dari DataFrame. 152/152 pytest lolos.

## Referensi Screener Profesional: Evaluasi Menyeluruh Kandidat (Minervini + VCP)

User: "sudah beli krn masuk kandidat STRONG BUY, besoknya naik 1% doang sudah minus, nunggu
berhari2... banyak saham potensial tidak muncul." Diminta evaluasi menyeluruh, bukan cuma
tweak parameter - "kalau hanya fokus ke backtest mungkin kita akan kehilangan peluang untuk
membuat screener yang lebih baik".

### Diagnosis awal: masalah ada di kualitas ENTRY, bukan lebar SL

Dites dulu 350 saham/3 tahun (walk-forward, regime IHSG>MA50, RR>=1.5 - SAMA persis default
live). Baseline: 646 trade, avg return **+1,25%**, tapi **57% kena SL**, cuma 15% kena TP.

Diagnosis: dari 369 trade yang kena SL, dicek apakah SL memang benar (harga tidak pernah
sampai Target dlm sisa max_hold_days) atau whipsaw (SL kena tapi kalau ditahan akhirnya
sampai Target juga) - **93,9% SL BENAR** (arah memang salah dari awal), cuma 6,1% whipsaw.
Kesimpulan: **melebarkan SL TIDAK akan banyak menolong** - masalahnya kualitas sinyal ENTRY.

### Ide yang DIUJI TAPI TIDAK DIPAKAI (cuma perbesar untung, tidak kurangi rugi)

- **Trend Aligned (MA20>MA50>MA200)** sbg filter tambahan di Kandidat: avg return naik
  (+1,65%->+3,16%, split-half konsisten) TAPI SL rate malah naik dikit (55,8%->59,2%,) &
  cakupan turun drastis (cuma 36% kandidat lolos) - TIDAK diterapkan sbg filter keras di
  Kandidat (beda dari Gap Up yang memang sudah pakai ini).
- **Kekuatan Relatif (RS) vs IHSG/Sektor**: pola SAMA - kuartil RS tertinggi avg return jauh
  lebih baik (+4,15% vs +0,39% di RS vs Sektor) TAPI win rate/SL rate TIDAK ikut membaik.
- **Time Stop 3 hari** (keluar cepat kalau blm pernah balik ke breakeven): efek KECIL tapi
  tervalidasi out-of-sample beneran (N dipilih dari paruh1 SAJA, diuji buta di paruh2, tetap
  membaik +1,74%->+1,81%) - kandidat fitur masa depan, BELUM diimplementasi (efeknya kecil,
  prioritas lebih rendah dari 2 fix di bawah).

### Yang DITERAPKAN: referensi Mark Minervini (Trend Template/SEPA) + Volatility Contraction Pattern

Dicari kerangka screener profesional yang terdokumentasi (Minervini, William O'Neil -
CANSLIM, VCP) - 2 kriteria yang BELUM ADA sama sekali di sistem kita, diuji dgn data yg sama:

1. **Posisi vs 52-week High/Low** (Minervini: Entry harus >=25% di atas low 52 minggu DAN
   dalam radius 25% dari high 52 minggu). Kandidat yang GAGAL kriteria ini terbukti MERUGI
   secara konsisten (median **-2,85%**, rata2 **-0,41%** - dua-duanya negatif, bukan cuma
   dibawa outlier; split-half sangat konsisten +2,64%/+2,26% utk yg lolos). BEDA dari
   Trend Aligned/RS di atas: ini benar2 menyaring kandidat yang secara historis buruk, bukan
   cuma memperbesar untung. **Diterapkan sbg FILTER KERAS** (`require_minervini_position`,
   default `True`) di `build_trade_candidates()` (screener.py) DAN `backtest.py` (supaya
   tool validasi tetap konsisten dgn live).
2. **Volatility Contraction Pattern (VCP)** proxy: rasio range harian 10 hari terakhir vs 10
   hari sebelum itu (SEBELUM hari ini, no lookahead) - <0,7 = kontraksi kuat. TERBUKTI
   menaikkan win rate (**45,9%** vs baseline ~33%) & menurunkan SL rate (**46,9%** vs
   ~57-60%) - TAPI **median return kelompoknya TETAP NEGATIF (-1,98%)**, rata2 positifnya
   ditarik sedikit kemenangan BESAR (FORU +60%, FPNI +56%, BTEK +54%) - pola "sering rugi
   kecil, sesekali untung besar", BUKAN sinyal "pasti untung". Karena karakternya beda dari
   filter aman Minervini, **TIDAK dijadikan filter keras** - dipakai sbg kolom info ("VCP
   Kuat" ✅/-) di tabel Kandidat + kunci sort KEDUA (setelah RR, sebelum Score) di
   `build_trade_candidates()` supaya diprioritaskan tanpa membuang kandidat lain. TIDAK
   diikutkan ke formula Score (jaga kalibrasi score_buy/score_strong_buy yg sudah
   divalidasi terpisah tidak ikut bergeser).

**Verifikasi end-to-end** (350 saham/3 tahun, `run_realistic_backtest()` dgn kode yang
BENERAN dipakai live, bukan skrip analisis terpisah): dgn filter Minervini aktif, N turun
dari 646 jadi **375** (58%), avg return naik dari **+1,25% jadi +2,45%** - angka ini PERSIS
cocok dgn analisis manual sebelumnya, membuktikan implementasi benar.

**Fix teknis**: `compute_metrics()` (screener.py) menghitung `Pct Above Low52w`,
`Pct Below High52w`, `Minervini Position OK`, `VCP Rasio Kontraksi`, `VCP Kuat` - SEMUA dari
histori SEBELUM hari ini (`df.iloc[:-1]`, no lookahead, pola sama dgn MA20/50/200 Gap Trend
Aligned). `build_trade_candidates()` dapat parameter baru `require_minervini_position`
(default `True`) + sort kedua `VCP Kuat`. `backtest.py` (`_simulate_realistic_trades_single`/
`run_realistic_backtest`) dapat parameter yang sama (default `True`) supaya tool validasi
resmi tetap mencerminkan perilaku live. Test lama yang fixture-nya (`_flat_ohlcv` 25 hari,
histori terlalu pendek utk 52-week) TIDAK lolos Minervini ditambahi
`require_minervini_position=False` eksplisit (fokus tiap test ke fitur yg diuji, bukan
ketabrak filter baru) - termasuk 3 test `TestTrailingStopBreakeven` yang gagal krn alasan LAIN
(tanggal hardcoded lewat ambang force-sell 15 hari - waktu asli sudah berjalan sejak ditulis),
diperbaiki pakai tanggal relatif ke `datetime.now()`, bukan string tetap. 12 test baru
(`TestMinerviniPosition52w`, `TestMinerviniFilterDiTradeCandidates`, `TestVCPKontraksi`,
`TestVCPBoostRankingDiTradeCandidates`). 163/163 pytest lolos.

### Filter Minervini dibuat OPSIONAL - hari tertentu bisa jauh lebih ketat dari rata-rata

User coba di live: "sepertinya tidak cocok diterapkan, hanya 4 saham yang berhasil di
screener, itupun cuma satu yang lolos". Rata-rata 3 tahun filter ini meloloskan 58%
kandidat, TAPI itu rata-rata - di hari tertentu (mis. pasar baru terkoreksi, banyak saham
belum kembali 25% dari low 52 minggu) bisa jauh lebih ketat, persis yang dialami user.

**Fix**: checkbox baru di sidebar "Wajib posisi 52-minggu (Minervini) di Kandidat" (`app.py`,
default **ON** - mempertahankan perilaku tervalidasi), pola SAMA dgn checkbox regime IHSG &
toggle Gap Trend Aligned - kalau kandidat terasa terlalu sedikit di hari tertentu, user bisa
matikan sendiri drpd terkunci hard-code. `auto_run.py` (skrip otomatis tanpa pengawasan)
SENGAJA tidak ikut toggle ini - tetap `require_minervini_position=True` (default paling
tervalidasi) terlepas apa yang dipilih user di dashboard interaktifnya.

### Ambang Sisi "High" Dilonggarkan 25% -> 35% - Minervini Ditulis utk Modal Besar, User Modal Kecil

User: setelah dibandingkan dgn referensi lain (situs `idx-saham.netlify.app` + spreadsheet
publik yang menampilkan "P&L 2662%" dari 1241 transaksi - ternyata cuma SUM mentah kolom
persentase, BUKAN return portofolio riil, vanity metric yang sama persis dgn keterbatasan
"Max Drawdown -369%" yang sudah diakui jujur di README ini), user angkat poin lebih
mendasar: "menurut bukunya Minervini jarang sekali transaksi, mereka punya uang besar...
sedangkan saya masih murni trader dengan uang sangat kecil". Minervini MEMANG menulis utk
trader/investor bermodal besar yang sengaja SANGAT selektif (nunggu setup langka, masuk
besar) - beda konteks dgn trader modal kecil yang butuh frekuensi transaksi lebih sering
utk membangun modal.

**Bukan dijawab dgn menghapus filter** (data tetap menunjukkan kelompok yang gagal kriteria
ini rata2 MERUGI, -0,41% - utk modal kecil, sering masuk ke trade rugi rata2 justru lebih
berbahaya, bukan kurang) - dicari JALAN TENGAH dgn data:

| Ambang sisi "high" (sisi "low" tetap >=25%) | Kandidat lolos | Avg Return | Kelompok gagal |
|---|---|---|---|
| 25% (awal) | 58% | +2,45% | -0,41% |
| **35% (dipilih)** | **68% (+17% lbh banyak)** | **+2,20%** | **-0,75%** |
| 50% | 76% | +1,66% | -0,05% (nyaris tdk ada beda lg) |

Melonggarkan KEDUA sisi sekaligus ke 35% dicoba dulu tapi HAMPIR TIDAK menambah kandidat
(375->370) - ternyata sisi "harus >=25% dari low 52 minggu" adalah bagian PALING SELEKTIF
& bernilai (tetap dipertahankan). Melonggarkan HANYA sisi "radius dari high 52 minggu" (dari
25% ke 35%) memberi hasil terbaik: ~17% lebih banyak kandidat, avg return msh kuat (+2,20%,
jauh di atas baseline tanpa filter +1,25%), kelompok yg masih tersaring TETAP terbukti rugi
rata2 (-0,75%) - perlindungannya tidak hilang, cuma jadi kurang seketat versi Minervini asli
yang memang dirancang utk gaya trading yang berbeda.

**Fix**: `AMBANG_ABOVE_LOW52W = 25`, `AMBANG_BELOW_HIGH52W = 35` (dulu keduanya 25) di
`compute_metrics()` (screener.py). 164/164 pytest tetap lolos (tidak ada test yg
hardcode asumsi ambang lama scr keliru).

## Bug Serius: "Win Rate 2,1%" Ternyata BREAKEVEN Dihitung Sama Dengan LOSS

User lapor lewat contoh nyata (KIJA, dibeli 10 Agustus): tab Performance menunjukkan
**Win Rate 2,1% (1 WIN, 47 LOSS dari 48 closed), Profit Factor 0,08** - jauh lebih buruk dari
backtest manapun sepanjang sesi ini (terburuk masih ~30% win rate). User curiga "ada yang
keliru", minta diaudit.

**Diagnosis 2 lapis**:
1. **KIJA sendiri** dicek presisi pakai data harga asli: sinyal 10 Agustus (Score=6, Signal
   BUY) menghasilkan Entry=133, SL=129,4 (dari MA20, LEBIH SEMPIT dari Donchian Low=120
   ataupun cap 10%=119,7). Low hari berikutnya (11 Agustus)=124 -> SL kena SATU HARI setelah
   entry, rugi -2,7%. Harga lanjut turun sampai 119 (14 Agustus) baru meledak +35% ke 166
   (18 Agustus) - **whipsaw murni**, persis kelas kejadian yang sudah diukur sebelumnya
   (~6,1% dari semua trade SL, README > "Referensi Screener Profesional"). BUKAN bug -
   KIJA saat itu 63,5% di bawah high 52 minggunya, filter Minervini yang baru dipasang
   JUSTRU akan membuang KIJA dari kandidat (trade ini terjadi sebelum filter itu ada).
2. **Angka Win Rate 2,1% itu sendiri BUG NYATA**: dicek manual dari CSV export sheet POSISI
   (48 closed) - ternyata cuma **28 BENAR kena SL** (rugi -3% s.d -10%, MATCH persis dgn
   baseline SL rate 55-59% yang sudah divalidasi sebelumnya), **19 SISANYA "BREAKEVEN"**
   (SL berhasil ditrail ke breakeven - fitur trailing-stop BEKERJA BENAR, cuma rugi tipis
   -0,4% krn fee) - TAPI keduanya (app.py tab Performance, DAN `gsheet_journal.py`'s
   `summarize()`) menghitung BREAKEVEN SAMA PERSIS dgn LOSS penuh (cuma cek tanda P&L <= 0,
   tidak bedakan Status "BREAKEVEN" dari "LOSS (SL)"). Akibatnya trailing-stop yang
   MELINDUNGI modal malah bikin gambaran performa jauh lebih buruk dari kenyataan: Win Rate
   asli (WIN vs LOSS beneran, BREAKEVEN dipisah) = **1/(1+28) = 3,4%** - masih rendah (masuk
   akal, periode ~1,5 minggu ini memang lagi sepi kemenangan) TAPI kategorinya jujur, bukan
   1/48=2,1% yang menyamarkan 19 posisi yang sebenarnya AMAN.

**Fix**: BREAKEVEN dipisah jadi kategori TERSENDIRI (kotak metrik baru "BREAKEVEN" di tab
Performance) - Win Rate & Profit Factor dihitung dari WIN vs LOSS asli saja, BREAKEVEN
tidak masuk pembilang maupun penyebut keduanya. Diperbaiki di 2 tempat: `app.py` (tab
Performance, kalkulasi inline) dan `gsheet_journal.py`'s `summarize()` (field baru
`"breakeven"` di dict return, walau saat ini belum ada pemanggil aktif - diperbaiki sekalian
utk konsistensi). 1 test baru (`test_breakeven_tidak_dihitung_sbg_loss`) mereproduksi skala
kasus asli (1 WIN, 2 LOSS asli, 2 BREAKEVEN -> winrate harus 1/3, BUKAN 1/5). 164/164 pytest
lolos.

## Batas Posisi Baru per Hari - Risiko Terkonsentrasi, Bukan Kualitas Sinyal

Lanjutan dari investigasi Win Rate di atas: dicek KAPAN 48 trade closed itu dibuka - ternyata
mayoritas dibuka BERBARENGAN di 10-13 Agustus (10 Agustus saja: ARKO, KIJA, HRUM, PAMG,
MCAS, PIPA, EURO, ASPR, MDIA, TMPO - persis `top_n=10` penuh dalam SATU hari). Tepat di
periode itu IHSG terkoreksi tipis (-1,53% tgl 11, -1% tgl 13) - karena SEMUA posisi dibuka
BERBARENGAN & banyak SL cukup sempit (-2% s.d -5%, bukan cuma -10%), koreksi kecil itu
menjatuhkan BANYAK posisi sekaligus dlm beberapa hari. User: "ideal backtest ini
diperlakukan seperti saat membeli saham [beneran], bedanya ini dilakukan oleh sistem" -
trader modal kecil beneran TIDAK PERNAH beli 10 saham berbeda dalam 1 hari, itu memusatkan
risiko bukan menyebarnya.

**Diuji dulu**: membatasi ke top-3/top-5 per hari (dari kandidat yg sudah diurutkan RR/VCP/
Score) **TIDAK memperbaiki avg return per-trade** (top-3: +0,43%, top-5: +1,35%, top-10:
+1,44% - kualitas TIDAK naik dgn batas lebih ketat). Jadi ini murni soal **PENYEBARAN
RISIKO** (smoothness kurva ekuitas / hindari cluster rugi berbarengan), BUKAN klaim "makin
sedikit makin untung". User (modal kecil) diminta pilih batas realistis, memilih **5**.

**Fix**: parameter baru `max_new_per_day` (default 5) di `open_positions_from_candidates()`
(`gsheet_journal.py`) - batas TOTAL posisi baru (semua saham gabung) per HARI KALENDER,
dihitung ULANG dari data sheet tiap panggilan (bukan variabel proses) supaya berlaku
gabungan lintas cron otomatis **dan** klik manual berkali-kali dalam sehari. Sidebar baru
"Maks Posisi Baru per Hari" (`app.py`, default 5) + `auto_run.py` pakai konstanta
`MAX_POSISI_BARU_PER_HARI = 5` yang sama. 4 test baru (`TestMaxPosisiBaruPerHari`).

User lanjut: "saya maunya diatas 10 supaya ada pilihan... karena yang tampil kadang lebih
banyak" - jumlah baris di TABEL Kandidat (utk dipilih manual, mis. via kolom Rekomendasi
SWING TRADE vs WAIT) DIPISAH dari batas AUTO-BUY. Sidebar baru "Jumlah Kandidat Ditampilkan"
(default 20, independen dari "Maks Posisi Baru per Hari") - `open_positions_from_candidates()`
tetap cuma ambil `max_new_per_day` TERATAS (sudah terurut RR/VCP/Score) dari daftar yang
lebih panjang ini, jadi user tetap lihat banyak pilihan tanpa auto-buy jadi lebih agresif.

## Momentum 5 Hari Beruntun + Volume Naik - Pola dari Kursus User, TERVALIDASI Kuat

User: "saya pernah ikut kursus, disitu diajarkan ciri2 saham yang mau naik: setiap candle
close lebih tinggi dari hari sebelumnya selama minimal 5 hari dengan volume meningkat."
Dibacktest dulu (350 saham/3 tahun, walk-forward, no-lookahead) sebelum diterapkan - SAMA
disiplin dgn semua ide baru sesi ini.

**"Volume meningkat" diuji 2 definisi** (istilah ini ambigu, bisa multi-tafsir):
- **LONGGAR**: rata-rata volume selama 5 hari streak > rata-rata volume 20 hari SEBELUM
  streak dimulai (volume keseluruhan lebih tinggi dari biasanya).
- **KETAT**: volume naik SETIAP HARI juga selama 5 hari itu (monoton naik, sama seperti
  closenya).

| Definisi | N sinyal | Return 1D | Return 5D | Split-half |
|---|---|---|---|---|
| **LONGGAR** | **1.124** | **+0,43%** (vs baseline +0,10%) | **+1,51%** (vs baseline +0,48%) | **Konsisten POSITIF kedua paruh** (+0,28%/+0,58% & +1,29%/+1,73%) |
| KETAT | 78 (terlalu kecil) | +0,51% | +0,43% | GAGAL - berbalik arah antar paruh (+2,73%/-1,87%) |

Definisi **LONGGAR** tervalidasi kuat - win rate 40,6-45,7% (lebih tinggi dari Kandidat biasa
~30-35%), avg return 3-4x lipat baseline pasar, DAN split-half benar-benar konsisten POSITIF
di kedua paruh (bukan cuma searah spt VCP - lihat bagian di atas). Definisi KETAT gagal krn
sampelnya terlalu kecil (N=78) - bukti klasik kenapa disiplin walk-forward + split-half
penting sebelum percaya sebuah pola, meski secara intuitif "logis".

**User juga usul pola kebalikan**: "reversal dengan volume semakin mengecil, apalagi di area
support kuat" (selling exhaustion) - DIUJI 5 kombinasi (radius 3-5% dari low N=60/120 hari,
dengan/tanpa syarat awal reversal) - **SEMUA GAGAL**: avg return mendekati nol/negatif
(-0,21% s.d +0,14%, jauh di bawah baseline +0,48%) DAN split-half berbalik arah di hampir
semua kombinasi. **TIDAK diterapkan** - proxy "dekat low historis" yang dipakai kemungkinan
belum menangkap definisi "support kuat" yang sebenarnya (perlu pendekatan lain kalau mau
diuji ulang, mis. level yang sudah diuji/dipantulkan berkali-kali, bukan sekadar dekat low).

**Fix**: field baru `Momentum 5 Hari` (bool) di `compute_metrics()` (screener.py) - 5 hari
terakhir (termasuk hari ini) harus close lebih tinggi dari hari sebelumnya SEMUA, DAN
rata-rata volume 5 hari itu > rata-rata volume 20 hari sebelum streak dimulai (definisi
LONGGAR). Dipakai sbg kolom info ("🚀 Ya"/-) di tabel Kandidat + kunci sort KEDUA di
`build_trade_candidates()` (setelah RR, SEBELUM VCP Kuat - diprioritaskan lebih tinggi krn
buktinya lebih kuat & konsisten). TIDAK diikutkan ke formula Score (jaga kalibrasi yang
sudah divalidasi terpisah). 4 test baru (`TestMomentum5HariBeruntun`). 172/172 pytest lolos.

## Bug: Regime IHSG "Tidak Terhitung" Terus-menerus - Kandidat Selalu Kosong

User: "ini juga selalu muncul sekarang" + screenshot warning "Regime IHSG tidak terhitung
(data kurang) - kandidat Swing disembunyikan" + "tidak ada data yang ditampilkan" - tab
Kandidat kosong terus.

**Root cause**: `fetch_ihsg_history()` (screener.py) dulu (a) **TIDAK di-cache sama
sekali** - dipanggil ULANG di SETIAP interaksi di seluruh app (fakta arsitektur `st.tabs()`
yang sudah diverifikasi sesi ini - README > "Bug Performa"), jauh lebih sering dipanggil
dari yang perlu, memperbesar peluang kena rate-limit Yahoo Finance; (b) **TIDAK ada retry
sama sekali** - beda dari fetch harga saham biasa (`_fetch_price_history_cached_v2`) yang
SUDAH pakai retry+backoff justru krn kegagalan transient Yahoo Finance itu UMUM & sudah
terbukti berulang kali sepanjang sesi ini. Begitu SATU kali gagal (timeout/rate-limit),
fungsi ini nyerah total & balik DataFrame kosong -> `market_regime()` jadi "UNKNOWN" ->
filter regime (default aktif) menyembunyikan SEMUA kandidat sbg "safe default". Efek
sampingnya: `fetch_index_snapshot()` juga ikut kehilangan data "IHSG" (pakai histori yang
sama), makanya box IHSG di header ikut hilang, cuma LQ45/JII yang tampil (fetch terpisah).

**Fix**: `fetch_ihsg_history()` sekarang `@st.cache_data(ttl=300)` (kurangi frekuensi
panggilan drastis - sekali per 5 menit, bukan tiap klik) + retry 3x dgn backoff 2s/4s (pola
SAMA persis dgn fetch harga saham). 172/172 pytest tetap lolos (tidak ada perubahan logika
yang di-test, murni penambahan cache+retry di lapisan network).

## Bug Panjang: "VCP Kuat"/"Momentum 5 Hari" Tidak Pernah Muncul - Ternyata pandas.merge() Suffix

User lapor kolom "VCP Kuat" dan "Momentum 5 Hari" tidak pernah muncul di tabel Kandidat
walau sudah reboot & clear cache berkali-kali. Investigasi ini JAUH LEBIH PANJANG dari
biasanya krn awalnya kelihatan seperti masalah deploy, bukan bug kode - urutan
pembuktiannya, sebelum akhirnya ketemu:

1. Kode di GitHub (app.py DAN screener.py) dicek langsung via raw content - BENAR.
2. Kode lokal dijalankan langsung (build_screener_table -> build_trade_candidates) -
   kolomnya MUNCUL dgn benar.
3. Log deploy Streamlit Cloud dicek - startup app TERJADI SETELAH waktu commit yang benar.
4. Reboot app, Clear Cache (dari menu app itu sendiri, bukan cuma "Reboot app" di panel
   Manage app), buka di browser lain - SEMUA tidak membantu.
5. Dicek jumlah app di akun Streamlit Cloud - cuma SATU "saham-kaya", bukan salah
   deployment.
6. CSV export dari tabel Kandidat dicek headernya - kolomnya BENAR tidak ada di data
   (bukan soal render/scroll browser).
7. **Penanda versi kode di-hardcode LANGSUNG di source** (`st.caption("🔖 Versi kode:
   ...")` di sidebar) - dicek MUNCUL - membuktikan 100% app SUDAH menjalankan kode
   terbaru. Ini mematahkan SEMUA teori deploy/cache sekaligus.

**Root cause sebenarnya** (baru ketemu setelah pembuktian di atas menyingkirkan semua
kemungkinan lain): "VCP Kuat" dan "Momentum 5 Hari" SUDAH ada di `table` (lewat
`build_screener_table()`) DAN ada LAGI di `cands_swing_all`/`cands_valid` (lewat
`build_trade_candidates()`) - keduanya sengaja ditambahkan di 2 tempat berbeda pada sesi
ini. Saat `app.py` melakukan `picks.merge(cands_valid[kolom_merge], on="Kode")` dan KEDUA
sisi (`picks`, dari `table`, DAN `cands_valid`) sama-sama punya kolom bernama "VCP Kuat" -
`pandas.merge()` OTOMATIS menambahkan suffix `_x`/`_y` (default `suffixes=('_x','_y')`)
utk kolom yang bentrok NAMANYA - jadi "VCP Kuat" diam-diam berubah jadi "VCP Kuat_x"/
"VCP Kuat_y", TANPA error atau warning apa pun. Kolom "VCP Kuat" polos yang dicari
`kolom_tampil` jadi genuinely TIDAK ADA - bukan soal render, bukan soal deploy, murni
tabrakan nama kolom saat merge.

**Fix**: hapus "VCP Kuat"/"Momentum 5 Hari" dari `kolom_merge` di `app.py` - TIDAK PERLU
digabung ulang krn `picks` SUDAH punya nilai yang identik langsung dari `table`
(`build_trade_candidates()` sendiri MEMBACA nilai ini dari `table` yang sama, jadi
nilainya pasti sama - menggabungkannya lagi cuma menciptakan tabrakan nama tanpa manfaat).
Diverifikasi ulang lewat reproduksi PERSIS alur `app.py` (bukan cuma test unit terisolasi)
- kolom muncul benar setelah fix. Penanda versi di sidebar tetap dipertahankan (diupdate
tiap fix signifikan) - berguna utk debugging serupa di masa depan tanpa perlu audit
sepanjang ini lagi. 172/172 pytest tetap lolos.

**Pelajaran penting**: kalau menambahkan kolom yang SAMA NAMANYA ke 2 sumber DataFrame
yang nantinya di-`merge()`, SELALU cek dulu kolom mana yang perlu di-merge vs mana yang
SUDAH ada di salah satu sisi - `pandas.merge()` tidak pernah error/warning saat terjadi
tabrakan nama, cuma diam-diam menyisipkan suffix.

## Trailing Lebih Cepat utk Saham Momentum Kuat (0,3R) - DIHAPUS 2026-08-20

> **SUPERSEDED**: seluruh bagian ini (dan "Trailing Stop ke Breakeven" sebelumnya) sudah
> **DIHAPUS TOTAL** dari kode - lihat "Target-Lock: Kunci Untung, Bukan Kunci Rugi" di
> bawah utk penggantinya & alasan lengkapnya. Dipertahankan di sini sbg riwayat/pelajaran,
> BUKAN deskripsi perilaku sistem saat ini.

Latar belakang: user lapor DOOH naik **+178% sejak 13 Juli** (5 minggu), tapi kandidat
saham ini terus di-whipsaw keluar oleh SL sebelum sempat menikmati rally besar - "screener
kita kemarin yang bermasalah". Trailing-ke-breakeven yang sudah ada (README > "Trailing
Stop ke Breakeven") trigger di **1,0R** (profit = risk awal) - untuk saham yang memang
sedang rally kuat, ini kadang terlalu lambat, posisi keburu kena SL asli sebelum
sempat ditrail sama sekali.

**Sempat diuji juga**: (a) ATR-widened SL (memperlebar jarak SL awal, bukan mempercepat
trailing) - REJECTED, menurunkan SL rate tapi tidak menaikkan avg return & split-half
JADI LEBIH TIDAK KONSISTEN. (b) Template Minervini 8-kriteria+RS Rating lengkap sbg
filter kandidat (termasuk diuji utk hold lebih lama, 20/40 hari) - REJECTED total di
semua horizon diuji (lihat bagian di bawah). Pendekatan yang AKHIRNYA tervalidasi:
bukan mengubah filter kandidat atau lebar SL, tapi **mempercepat trigger trailing**
khusus utk saham yang SUDAH terbukti momentum kuat saat kandidat itu muncul.

**Kriteria "Momentum Kuat"**: naik >=30% dalam 20 hari bursa terakhir (before hari ini,
no lookahead) - `screener.py::compute_metrics()`, field `"Momentum Kuat 20D"`. Beda dari
"Momentum 5 Hari" (naik beruntun 5 hari + volume naik, README > "Referensi Screener
Profesional") - itu pola ENTRY jangka pendek, ini murni ukuran SEBERAPA KUAT rally yang
SUDAH terjadi, dipakai HANYA utk kecepatan trailing setelah posisi dibuka.

**Backtest** (206 trade real, walk-forward, simulasi realistis Entry/SL/Target/RR, 3
varian trigger dibandingkan):

| Trigger | Avg Net Return | SL Penuh | BREAKEVEN | Split-half |
|---|---|---|---|---|
| 1,0R (baseline lama) | +1,72% | 83 | 76 | +2,71% / +0,73% |
| 0,5R | +1,51% | 56 | 121 | +1,95% / +1,07% |
| **0,3R** | **+2,17%** | **42** | **136** | **+2,78% / +1,56%** |

0,3R menang di SEMUA metrik: avg return TERTINGGI, SL penuh TURUN HAMPIR SEPARUH (83->42),
dan split-half PALING KONSISTEN dari 3 varian (kedua paruh positif & lebih tinggi dari
baseline). Diterapkan HANYA utk saham Momentum Kuat, BUKAN ke semua populasi (belum diuji
utk populasi umum, dan trailing 1,0R umum sudah tervalidasi terpisah).

**Fix**: kolom baru **O: Momentum Kuat** ditambahkan ke struktur sheet POSISI
([gsheet_journal.py](gsheet_journal.py), `HEADERS`) - direkam SEKALI saat posisi dibuka
(`open_positions_from_candidates()`, dibaca dari `"Momentum Kuat 20D"` hasil
`build_trade_candidates()`), TIDAK PERNAH dihitung ulang setelahnya. `auto_close_positions()`
membaca kolom ini per posisi OPEN: kalau `TRUE`, pakai `TRAILING_TRIGGER_R_MOMENTUM_KUAT
= 0.3` sbg pengali risk awal; kalau `FALSE`/kosong (baris lama sebelum kolom ini ada),
tetap pakai `TRAILING_TRIGGER_R = 1.0` lama - tidak crash, tidak berubah perilaku utk
baris lama. 7 test baru (`TestTrailingLebihCepatMomentumKuat`,
`TestOpenPositionsMerekamMomentumKuat`) - 179/179 pytest lolos.

**Langkah manual diperlukan**: sheet Google Sheets "POSISI" live perlu kolom header baru
`Momentum Kuat` di cell **O1** (sejajar kolom `Lot`/`SL Awal` yang sudah ada) - kode ini
menulis/membaca posisi berdasarkan URUTAN kolom, bukan mencari nama header, jadi baris
BARU akan otomatis terisi benar begitu header-nya ada; tanpa header ini `get_all_records()`
tidak akan memberi nama kolom O sehingga `auto_close_positions()` fallback aman ke
trigger 1,0R lama (bukan error, tapi juga belum memanfaatkan fitur baru).

## Filter Saham Tidak Aktif/Suspen

Laporan user: "hari ini DOOH di suspen, saya mau saham yang tidak aktif dari perdagangan
tidak masuk screener". Sebelumnya TIDAK ada filter khusus utk ini - gate likuiditas yang
sudah ada (`Layak Likuiditas`) pakai **rata-rata volume 20 hari**, jadi saham yang biasanya
likuid tapi SEDANG suspen hari ini tetap lolos (rata-ratanya masih tinggi walau hari ini
nol).

Ditelusuri histori data DOOH sendiri - ditemukan 2 pola suspen yang berbeda, KEDUANYA
harus dideteksi:
1. **Bar hari itu ADA tapi Volume=0** - contoh nyata: bar 6 Agustus DOOH punya
   Open=High=Low=Close=274 (rata sempurna, tidak ada rentang harga sama sekali) dengan
   Volume=0 - tanda pasti tidak ada satupun transaksi hari itu.
2. **Bar hari itu TIDAK ADA sama sekali** - saat suspen SEDANG berlangsung, data provider
   kadang belum/tidak menambah bar baru sama sekali utk hari itu, jadi bar TERAKHIR yang
   tersedia jadi tertinggal dibanding saham lain yang sudah update.

**Fix** (`screener.py::build_screener_table()`): dihitung `tanggal_terbaru_pasar` = MAX
tanggal bar TERAKHIR di seluruh batch scan yang sedang berjalan (bukan hardcode "hari
ini" - supaya tetap benar kalau scan dijalankan sebelum SEMUA saham ter-update: semua
sama2 tertinggal 1 hari, tidak ada yang salah kefilter). Saham dianggap AKTIF kalau
tanggal bar terakhirnya == tanggal_terbaru_pasar DAN Volume hari itu > 0 - gagal salah
satu syarat, saham dikeluarkan SEPENUHNYA dari tabel screener (bukan cuma ditandai),
sesuai permintaan user. Daftar saham yang dikeluarkan di-print ke log server (bukan UI)
utk transparansi debug tanpa menambah komponen visual baru. 4 test baru
(`TestFilterSahamTidakAktifSuspen`) - 183/183 pytest lolos.

## Bug Serius: Posisi Dijual di HARI YANG SAMA Dibeli (Look-Ahead Bug)

Laporan user (screenshot sheet POSISI): FAST/CTTH/KETR/DOOH/APLN dkk dibuka **DAN**
ditutup di **tanggal kalender yang sama**, kadang cuma beda beberapa menit - hampir semua
berakhir BREAKEVEN atau LOSS (SL). Contoh paling jelas: **APLN** - "kemarin hijau, hari
ini naik kencang, tapi tercatat loss".

**Root cause**: `auto_run.py` (cron sore, 14:45 WIB) membeli lalu **LANGSUNG di eksekusi
yang SAMA** mengecek TP/SL/trailing semua posisi OPEN - termasuk yang BARU SAJA dibuka
detik sebelumnya. Entry-nya pakai Close saham (~jam 15:07 WIB stlh fetch data, nyaris
tutup bursa), tapi pengecekan SL/TP-nya pakai **High/Low HARI ITU JUGA** - yang
SEBAGIAN BESAR sudah terjadi SEBELUM jam beli (dari jam buka 09:00). Kalau Low pagi hari
itu kebetulan di bawah SL, posisi langsung "kena SL" dalam hitungan menit - **secara
kausal mustahil**: baru beli jam 15:07, tidak mungkin "kena" harga rendah yang sudah
lewat jam 10 pagi, SEBELUM posisi itu dibeli.

Ini MENYIMPANG dari metodologi `backtest.py::_simulate_realistic_trades_single()` yang
sudah divalidasi ketat sepanjang proyek ini - baris `for d in range(t + 1, ...)`: exit
HANYA dicek MULAI HARI BERIKUTNYA, TIDAK PERNAH di hari yang sama dengan entry. Live
system (`gsheet_journal.py`) tidak punya pengaman yang sama - bug ini sudah ada sejak
awal, baru ketahuan sekarang karena efeknya (hampir semua trade closed di hari yang
sama) baru terlihat jelas setelah beberapa hari data terkumpul di sheet POSISI.

**Fix** (`gsheet_journal.py::auto_close_positions()`): tambah guard di awal loop
pengecekan tiap posisi OPEN - kalau tanggal KALENDER `Tanggal Open` SAMA dengan tanggal
KALENDER sekarang, SKIP total (lanjut ke posisi berikutnya, tidak dicek TP/SL/trailing
sama sekali). Berlaku utk SEMUA pemanggil (cron otomatis MAUPUN tombol manual dashboard
yang bisa diklik berkali-kali hari yang sama) - fix di satu tempat, otomatis melindungi
semua jalur.

Sengaja bandingkan **tanggal kalender** (`.date()`), BUKAN selisih jam
(`timedelta.days`) seperti kolom "Hari" yang sudah ada - selisih jam SALAH dipakai di
sini: posisi dibuka jam 15:07 lalu dicek lagi jam 09:xx BESOK paginya cuma berselisih
~18 jam (`.days` masih 0) padahal itu SUDAH tanggal kalender berikutnya & MEMANG SAH
utk dicek (bukan bug - itu justru alur yang benar: beli sore, jual paling cepat besok
pagi, sesuai jadwal cron yang sudah disepakati - README > "BUY vs SELL Beda Jadwal").

4 test baru (`TestSkipCekSamaHariDenganBuka`) - termasuk test yang membuktikan posisi
"dibuka kemarin sore, dicek pagi ini" (beda tanggal kalender, tapi selisih jam <24 jam)
TETAP diproses normal, tidak ikut ke-skip. 187/187 pytest lolos.

**Data lama tetap tercatat sebagai bukti, TAPI dikecualikan dari ringkasan performa**:
trade yang SUDAH kena bug ini (FAST/CTTH/KETR/DOOH/APLN dkk) tetap ada di sheet POSISI
(tidak dihapus - riwayat harus jujur), tapi `app.py` tab Performance sekarang punya
checkbox baru **"Kecualikan trade 'jual hari sama dgn beli'"** (default AKTIF) yang
mendeteksi pola ini langsung dari data (tanggal kalender Tanggal Open == Tanggal Close,
bukan cutoff tanggal deploy) dan mengeluarkannya dari perhitungan Win Rate/Profit
Factor/Realized P/L. User (2026-08-19): "kita tidak boleh kalah dgn sistem yang kemarin
saya kirimkan" - performa live harus dibandingkan dari data yang BERSIH, bukan yang
tercemar bug eksekusi.

## Target-Lock: Kunci Untung, Bukan Kunci Rugi (2026-08-20)

Latar belakang - user melaporkan pola aneh di sheet POSISI: **hampir semua trade closed
berakhir BREAKEVEN atau LOSS**, padahal saham-saham itu kelihatan bullish - "backtest
harus seiring dengan kondisi kandidat, kalau tidak sistem ini seharusnya tidak bisa
dipakai". Ditelusuri lewat 3 jalur bukti INDEPENDEN sekaligus:

1. **Data live 54 trade real** (sheet POSISI, 2 minggu terakhir) - saham yang closed
   LOSS/BREAKEVEN kita cek harga aslinya 3-5 hari SETELAH kita exit: **55-70% justru
   NAIK LAGI**, avg +2,6% s.d +3,8% (PWON naik ke High 278 sehari setelah breakeven @260;
   BEEF naik ke 498 dua hari setelah breakeven @446).
2. **Backtest besar** (614 sinyal, 350 saham/3 tahun, walk-forward, dipecah per regime
   IHSG): FIXED TP/SL MURNI (SL/TP tetap sejak awal, tidak pernah digeser) menang avg
   return DAN win rate dibanding trailing-ke-breakeven kita (+1,18%/32,7% vs
   +0,99%/24,4%) - **di regime BULLISH maupun BEARISH**, bukan cuma soal 1 periode
   bullish kebetulan.
3. **Sistem referensi milik user sendiri** (spreadsheet pribadi, sudah dipakai lama) -
   TIDAK PERNAH pakai trailing sama sekali, Status cuma `CLOSED-TP`/`CLOSED-SL`/`OPEN`,
   kolom "Hari" antar Open-Close SELALU >=1 (tidak pernah 0) - kelihatan bekerja baik.

**Kesimpulan**: trailing-ke-breakeven (baik versi 1,0R polos maupun versi 0,3R "Momentum
Kuat" - README bagian atas, keduanya SUPERSEDED) MEMOTONG untung (exit di ~0% begitu
harga singgah balik ke harga beli) LEBIH SERING daripada MELINDUNGI dari rugi nyata.
Keduanya **dihapus total**, kolom "Momentum Kuat" (screener.py & sheet POSISI) juga ikut
tidak dipakai lagi.

**Ide penggantinya - dari praktik manual user**: "yang ideal sebenarnya jika target
tercapai geser SL dibawah target, sehingga jika harga balik keuntungan terselamatkan -
itu yang sering saya lakukan secara manual." Beda fundamental dari trailing-ke-breakeven:
itu mengunci di HARGA BELI (upside dikorbankan demi hindari rugi), ini mengunci MENDEKATI
TARGET (untung besar tetap terselamatkan, DAN posisi dibiarkan jalan lebih jauh kalau
tren lanjut - tidak dibatasi Target lagi).

**Diuji** (614 sinyal yang sama, 3 varian jarak kuncian dlm satuan R = risk awal):

| | Avg Return | Win Rate | Avg Return (Bullish) |
|---|---|---|---|
| FIXED (exit tepat di Target) | +1,18% | 32,7% | +1,94% |
| Target − 0,3×Risiko | +2,20% | 32,7% (sama) | +3,39% |
| **Target − 0,5×Risiko** | **+2,23%** | **32,7% (sama)** | **+3,36%** |
| Target − 1,0×Risiko | +2,03% | 32,7% (sama) | +3,15% |

k=0,5R dipilih (avg tertinggi keseluruhan). **Win rate SAMA PERSIS dengan FIXED di semua
varian k** - mekanisme ini HANYA menyalakan diri pada trade yang SUDAH mencapai Target
(sudah pasti menang), jadi ini **strict improvement**, bukan trade-off spt trailing-ke-
breakeven yang lama (yang menukar win rate demi hindari rugi).

**Terbukti selalu untung kalau sampai tersentuh** (matematis): level kuncian = Target −
k×Risiko = Entry + Risiko×(RR − k). Kandidat SWING mensyaratkan RR >= 1,5 (filter
`build_trade_candidates()`), dan k <= 1,0 di semua varian diuji, jadi RR−k selalu > 0 -
level kuncian PASTI di atas harga beli, tidak mungkin jadi breakeven atau rugi.

**Implementasi** (`gsheet_journal.py::auto_close_positions()`): begitu High hari ini
menyentuh Target (kolom D "TP"), posisi **TIDAK ditutup** - SL (kolom E) digeser ke
`Target - TRAIL_AT_TARGET_K * risk_awal` (risk_awal = Harga Beli - SL Awal, kolom N),
posisi TETAP OPEN. Status "target sudah terkunci" dideteksi dari `SL (kolom E) > SL Awal
(kolom N)` - TIDAK perlu kolom baru, cukup bandingkan 2 kolom yang sudah ada. Begitu
target terkunci: TIDAK dicek TP lagi (target sudah "lewat"), cuma tunggu level kuncian
itu tersentuh (`WIN (TARGET TERKUNCI)`) atau force-sell 15 hari (`WIN (FORCE SELL target
terkunci, N hari)` - selalu dilabel WIN, terbukti matematis selalu untung). Baris lama
yang sempat ditrail ke breakeven oleh mekanisme LAMA (sebelum fix ini) otomatis kena
kondisi "target terkunci" juga (SL Awal < harga beli selalu) - transisi yang aman, bukan
bug, cuma diperlakukan sama (tunggu level itu tersentuh) sampai baris itu closed sendiri.

7 test baru (`TestTargetLock`) + 4 test lama yang diupdate (skenario "Target tersentuh"
sekarang mengharapkan SL digeser & posisi tetap OPEN, bukan langsung closed) - 183/183
pytest lolos.

## Riwayat Saham: Satu File Terus Bertambah, Bukan CSV Terpisah Tiap Download

User: "saya berfikir otomatis dalam bentuk excel. juga kelemahannya setiap download
terbentuk file baru. mungkin ada cara supaya selalu dalam satu file. bahkan bisa
diketahui performa setiap saham karena adanya dalam satu tempat. mungkin kamu punya
cara. karena saya lihat ada saham yang cepat naik, turun dll." Diminta memilihkan sendiri
desainnya ("kamu pilih yang menurut kamu terbaik") - 2 keputusan diambil:

1. **Cakupan**: hanya saham Signal **BUY/STRONG BUY** (bukan semua 962 saham) - kalau
   semua saham disimpan tiap hari, sheet akan cepat membengkak tak terkendali (962
   baris/hari bisa kena batas praktis Google Sheets dlm hitungan bulan) - dan yang benar2
   relevan utk "performa saham yang dipertimbangkan" ya yang lolos Signal, bukan semuanya.
2. **Waktu**: SEKALI sehari, di scan SORE saja (bukan 2x/hari ikut jadwal pagi+sore) -
   konsisten dgn alasan yang sudah ada (README > "BUY vs SELL Beda Jadwal"): data pagi
   cuma sebagian kecil hari itu, tidak representatif & tidak sebanding kalau dicampur dgn
   data sore yang sudah hampir 1 hari penuh.

**Implementasi** (`riwayat_journal.py`, modul BARU - sengaja terpisah dari
`gsheet_journal.py` yang tanggung jawabnya beda: itu jurnal TRANSAKSI buka/tutup posisi,
ini LOG SNAPSHOT PASAR tanpa konsep posisi sama sekali): sheet baru **RIWAYAT_SAHAM**
(AUTO-CREATE kalau belum ada - beda dari sheet POSISI yang butuh dibuat manual dulu,
supaya user tidak perlu langkah manual lagi). Tiap kali `auto_run.py` jalan di scan sore,
saham Signal BUY/STRONG BUY hari itu (Kode, Nama, Harga, Perubahan %, Signal, Score,
Volume Ratio, Value Traded) ditambahkan (append) sbg baris baru - TIDAK PERNAH menimpa
baris lama. Guard 1x/hari (cek tanggal baris terakhir di sheet) mencegah duplikat kalau
auto_run.py dipanggil berkali-kali di hari yang sama.

Tab baru **"📜 Riwayat Saham"** di dashboard: pilih 1 kode saham, lihat grafik
pergerakan harganya dari snapshot ke snapshot (HANYA hari-hari saham itu lolos Signal
BUY+, bukan tiap hari bursa - kalau saham itu berhenti muncul di Kandidat beberapa hari
lalu muncul lagi, grafiknya akan "melompat" melewati hari-hari kosong itu, bukan bug),
plus tombol download CSV dan tombol "Tambah Snapshot Sekarang" utk isi manual kalau perlu.

10 test baru (`tests/test_riwayat_journal.py`) - 193/193 pytest lolos.

## Screener Sederhana: Breakout + Posisi 52-Minggu + Volume Rendah (Sistem Live Terpisah)

User: "apakah perlu buat screener pembanding. mungkin lebih sederhana tapi bisa winrate
lebih tinggi dan buy/sellnya tepat" -> "target saya yang penting profit dengan risk
rendah, tetap profesional. mungkin fokus ke screener dulu" -> diminta bikin **sistem live
terpisah** (bukan cuma backtest sekali jalan), dgn catatan: "mungkin versi baru tidak
perlu banyak header, kecuali sudah sukses bisa migrasi yang lama."

**Kenapa ini dibangun**: sistem utama (`build_trade_candidates()`, Score komposit
teknikal+fundamental+RSI) dibandingkan dgn 4 kandidat kriteria entry LEBIH SEDERHANA di
data yang sama (350 saham/3 tahun, walk-forward, dipecah per regime IHSG):

| Kriteria | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| Sistem sekarang (Score komposit) | 614 | +2,16% | 54,2% | 1,68 |
| Breakout + Posisi 52-Minggu | 621 | +7,54% | 60,4% | 3,39 |
| **+ Volume DI BAWAH rata-rata** | 381 | **+9,70%** | **59,1%** | **6,22** |

Breakout dengan **volume RENDAH** (Volume Ratio <=1,0x, KEBALIKAN dari intuisi umum
"volume tinggi = konfirmasi") justru paling bagus - kemungkinan krn breakout itu belum
"ramai" diperhatikan pasar (belum banyak FOMO ikut beli), masih ada ruang naik sebelum
volume/perhatian pasar besar menyusul - konsisten dgn pola VCP (kontraksi sebelum
ekspansi) yang sudah divalidasi sebelumnya. Diuji ulang dgn sampel lebih besar (step=1,
N=381 bukan 132) - hasilnya BERTAHAN, split-half +8,49%/+10,91% (konsisten, malah naik
di paruh kedua, bukan overfitting).

**SL dibatasi 5%** (bukan 10% spt sistem utama) - diuji terpisah (user: "apakah rugi
terburuk bisa diturunkan misal maksimal 5%"): rugi terburuk/trade turun hampir separuh
(-10,4% -> -5,4%), avg return turun sedikit TAPI Profit Factor malah NAIK (3,39 -> 3,79)
- bukan trade-off merugikan.

**Exit 2 lapis** (user: "dalam banyak kasus saya terlambat menjual karena target belum
tercapai sudah balik arah" - Target-Lock yang sudah ada cuma melindungi SETELAH Target
tersentuh, TIDAK ada perlindungan di tengah jalan):
- **Lapis 1 (partial-lock, SEBELUM Target)**: begitu profit (High) capai 0,7x risiko
  awal, SL digeser ke 0,5x risiko awal (BUKAN breakeven penuh spt trailing-ke-breakeven
  lama yang terbukti buruk - MASIH ada jarak, bukan mengunci ke 0). DIUJI: avg return
  cuma turun sedikit (+2,23% -> +2,16% di sistem lama, diterapkan sama di sini) TAPI win
  rate NAIK HAMPIR 2X (32,7% -> 54,2%), performa regime bearish berubah dari rugi jadi
  untung.
- **Lapis 2 (target-lock, SETELAH Target)**: SAMA dgn `gsheet_journal.py` - SL digeser
  ke Target-0,5x risiko, posisi TETAP OPEN, dibiarkan jalan kalau tren lanjut.

**Implementasi**:
- `screener.py::build_simple_candidates()` - entry HANYA 3 syarat, fungsi TERPISAH dari
  `build_trade_candidates()` (sistem lama TIDAK berubah sama sekali).
- `simple_journal.py` (modul BARU) - sheet Google Sheets TERPISAH **POSISI_SEDERHANA**
  (auto-create), struktur kolom SENGAJA lebih ringkas dari POSISI (12 kolom, tanpa
  Tipe/Hari/Momentum Kuat - user: "tidak perlu banyak header"). "Lapis mana yang aktif"
  dideteksi dari perbandingan SL saat ini vs level partial-lock/target-lock yang mungkin
  - TIDAK perlu kolom status tersendiri.
- `auto_run.py` - scan sore yang SAMA (tidak ada fetch data terpisah), buka/tutup posisi
  Screener Sederhana SEJAJAR dgn Swing, TIDAK menghentikan alur utama kalau gagal.
  SENGAJA TIDAK digate regime IHSG (data uji: bearish sudah positif +0,49% utk screener
  ini, beda dari sistem lama) - belum diuji A/B eksplisit, dibiarkan aktif semua regime
  dulu.
- Tab baru **"🔬 Screener Sederhana"** - tampilan MINIMAL (Kode/Entry/Target/SL/RR/Lot/
  Chart saja), tombol buka/cek posisi manual, ringkasan Win Rate/Total P&L dari jurnal
  terpisah.

26 test baru (11 `TestBuildSimpleCandidates` + 15 `tests/test_simple_journal.py`) -
219/219 pytest lolos.

## Zig Zag: Entry Tambahan, Bukan Pengganti Breakout

User, setelah pakai Screener Sederhana: "setelah menggunakan screener saya merasa belum
percaya diri. mungkin kesalahannya adalah terlambat mendeteksi harga akan rebound.
setelah harga sudah tinggi baru ditangkap screener" -> "mungkin perlu diuji juga
penggunaan zig zag."

**Kenapa Zig Zag**: Breakout (`Harga > Donchian High 20-hari`) secara desain baru
menyala SETELAH harga menembus level tertinggi 20 hari - selalu melewatkan sebagian
rally. Zig Zag mendeteksi TITIK BALIK (swing low->high) begitu terbentuk - lebih dini,
sebelum breakout resistance.

**Diuji BERTAHAP, bukan asumsi langsung bagus** (350 saham/3 tahun, walk-forward):

| Tahap | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| Zig Zag Low (5%) + Minervini, SENDIRIAN | 2.741 | +3,18% | 61,6% | 3,04 |
| Breakout (vol<=1,0x) + Minervini, SENDIRIAN | 798 | +6,36% | 55,5% | 3,79 |

Win rate Zig Zag lebih tinggi tapi PF & avg return lebih rendah - trade-off jujur (lebih
banyak sinyal & lebih dini, tapi tiap sinyal untungnya lebih kecil), BUKAN kemenangan
mutlak salah satu arah.

**Uji GABUNGAN (Breakout OR Zig Zag) dengan simulasi realistis** - bukan cuma
menjumlahkan 2 hasil terpisah, krn keduanya berebut slot posisi baru yang SAMA di hari
yang sama: batas 5 posisi baru/hari (`MAX_POSISI_BARU_PER_HARI`), diprioritaskan RR
tertinggi (SAMA logika `open_positions_from_candidates()`):

| | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| **GABUNGAN (Breakout OR Zig Zag)** | 2.280 | +6,10% | 60,1% | **4,91** |
| — via Breakout | 478 | +16,28% | 67,4% | 11,35 |
| — via Zig Zag | 1.802 | +3,41% | 58,2% | 3,18 |

Profit Factor GABUNGAN (4,91) lebih tinggi dari kedua sistem SENDIRIAN (3,79 & 3,04) -
BUKAN didilusi. Karena sortir pakai RR tertinggi, sinyal Breakout yang bagus (RR
biasanya lebih tinggi) tetap menang duluan setiap hari - Zig Zag cuma mengisi slot
KOSONG di hari-hari Breakout TIDAK menyala, menambah ~3-4x jumlah kesempatan tanpa
merebut/merusak kualitas slot Breakout yang sudah bagus. Trade-off yang tetap ada:
avg return gabungan (+6,10%) lebih kecil dari Breakout sendirian (+16,28% dlm gabungan,
+6,36% saat diuji sendirian tanpa slot cap) - krn trade Zig Zag secara alami lebih kecil
untungnya - tapi jumlah total kesempatan & PF keseluruhan naik, jadi pertukarannya
sepadan.

**Implementasi**:
- `screener.py::compute_zigzag_pivots()` - fungsi MURNI, walk-forward-safe, mendeteksi
  rangkaian pivot High/Low (harga berbalik >=threshold% dari extreme yang berjalan,
  threshold default 5%).
- `screener.py::build_simple_candidates()` - entry Zig Zag = hari ini TEPAT 1 hari
  setelah pivot Low baru terkonfirmasi + Minervini Position OK (SAMA syarat posisi
  52-minggu dgn Breakout - SATU2NYA filter yang WAJIB di kedua jalur). TANPA filter
  volume (Zig Zag diuji tanpa itu). Setiap kandidat ditandai kolom "Tipe Sinyal"
  ('Breakout'/'ZigZag') - kalau lolos KEDUA jalur, ditandai 'Breakout'.
- `simple_journal.py` - kolom baru **M: Tipe Sinyal** direkam saat posisi dibuka (label
  saja, TIDAK dipakai di logika exit). Sheet yang sudah live SEBELUM kolom ini ada
  otomatis dilengkapi header-nya oleh `_get_worksheet()` - TIDAK perlu langkah manual.
- Tab "🔬 Screener Sederhana" - kolom "Tipe Sinyal" ditambahkan ke tabel kandidat.

14 test baru (3 `TestComputeZigzagPivots` + 4 `TestBuildSimpleCandidatesZigZag` +
2 `TestOpenPositionsFromCandidates` tambahan + 2 `TestGetWorksheetMigrasiHeader`) -
230/230 pytest lolos.

## Riset Lanjutan: Ide Reversal Ditolak, Threshold Zig Zag Dioptimalkan (2026-08-31)

User: "saya berfikir bagaimana kalau kandidat dihapus, dan screener yang masih
sederhana dihapus, mungkin masih ada cara untuk meningkatkan winrate da profit" ->
diklarifikasi: **riset dulu, JANGAN hapus sistem live** (Kandidat & Screener Sederhana
tetap jalan). Lalu setelah 2 ide baru ditolak: "optimalkan sistem sederhana kalau
memungkinkan."

**2 ide baru DIUJI dan DITOLAK** (350 saham/3 tahun, walk-forward, exit 2-lapis + SL 5%
sama seperti sistem yang sudah ada) - dicatat di sini justru supaya TIDAK diuji ulang
di masa depan:

| Ide | N | Avg Return | Win Rate | Profit Factor | Verdict |
|---|---|---|---|---|---|
| Pullback ke MA20 dlm uptrend | 6.299 | +0,32% | 49,3% | 1,16 | Ditolak - nyaris impas, Bearish PF 0,78 (rugi bersih) |
| Hammer/Bullish Engulfing dekat support | 1.934 | -0,40% | 47,1% | 0,82 | Ditolak - rugi bersih bahkan di Bullish |

Pola yang konsisten: sistem **trend-following** (Breakout, Zig Zag) menang jelas (PF
3-4,9) drpd sistem **mean-reversion/reversal** (pullback ke MA, bentuk candlestick 1-2
hari) yang PF-nya di bawah 1 atau nyaris impas. Di data IDX ini, menebak titik balik
LEBIH DINI dari swing Zig Zag yang sudah terkonfirmasi (>=threshold%) justru
memperlemah edge, bukan memperkuat.

**Optimasi yang BERHASIL: threshold Zig Zag 5% -> 10%.** Disweep 3%-30% dgn simulasi
gabungan+slot-cap yang sama (README > "Zig Zag: Entry Tambahan"):

| Threshold | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| 3% | 3.030 | +4,32% | 54,1% | 3,53 |
| 5% (lama) | 2.910 | +5,84% | 58,3% | 4,29 |
| **10% (baru)** | 2.711 | +7,34% | 59,3% | 4,73 |
| 12% | 2.652 | +7,65% | 59,2% | 4,79 |
| 15% | 2.591 | +7,84% | 58,3% | 4,74 |
| 20-30% | 2.449-2.530 | +8,25-8,57% | 57,5-57,9% | 4,86-4,93 |

PF terus naik sampai 30% TAPI mulai goyang tidak rapi di atas 12% (turun lagi di 15%,
baru naik lagi) sambil N terus menyusut - tanda mulai overfitting kalau dikejar ke
titik ekstrem (sinyal makin sedikit, makin mendekati hanya menangkap swing raksasa yang
langka & tidak representatif). **10% dipilih sbg titik aman**: kenaikan jelas di semua
metrik dibanding baseline 5%, N masih besar (turun cuma ~7%), dan **divalidasi robust**:

| | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| Semua | 2.711 | +7,34% | 59,3% | 4,73 |
| Split-half 1 | 1.355 | +7,72% | 58,3% | 4,80 |
| Split-half 2 | 1.356 | +6,96% | 60,3% | 4,67 |
| Bullish | 1.616 | +9,01% | 60,4% | 5,66 |
| Bearish | 1.095 | +4,87% | 57,7% | 3,42 |

Split-half stabil (tidak menurun tajam di paruh lebih baru) & KEDUA regime naik dibanding
baseline 5% (Bullish PF 5,25->5,66, Bearish PF 3,10->3,42) - bukan cocok-cocokan sesaat.

**Implementasi**: default `zz_threshold_pct` di `build_simple_candidates()` (dan default
`threshold_pct` di `compute_zigzag_pivots()`) diubah dari 5.0 ke 10.0. Tidak ada
pemanggil (`app.py`, `auto_run.py`) yang override parameter ini secara eksplisit, jadi
cukup ubah default. RR minimum (1,5) TIDAK dinaikkan - walau menaikkannya juga sedikit
membantu, menumpuk 2 perubahan sekaligus (threshold + RR min) menambah risiko
overfitting tanpa manfaat yang cukup besar utk sepadan.

**Kolom "% SL"** juga ditambahkan ke tabel tab "🔬 Screener Sederhana" (user: "bagus
kalau ada % SL") - jarak SL riil dari Entry dlm persen, bisa LEBIH KETAT dari cap 5%
kalau Donchian Low/MA20 yang mengikat (bukan cap-nya) - supaya risiko riil per trade
kelihatan, bukan diasumsikan selalu 5%.

## Sinyal Jual Dini: Kunci Untung Sebelum Balik Arah (2026-08-31)

User cerita masalah nyata: "hari ini muncul sinyal buy, lalu besok...harga turun, tapi
masih profit...saya tahan tidak jual karena target belum tercapai...ternyata trader
profesional...sempat jual dalam kondisi profit, sedangkan saya tahan dan akhirnya
rugi/nyangkut...apakah memungkinkan saham yang sudah pernah masuk screener buy tetap
dikawal jika muncul sinyal sell...saya belum sampai dilevel prediksi seperti itu."

**Bukan soal prediksi arah** (yang butuh level analisis tinggi ala Astronacci) - cukup
deteksi pelemahan yang SUDAH terjadi: harga TUTUP hari ini turun >=X% dari titik
TERTINGGI sejak posisi dibuka, SAMBIL masih profit -> jual SEKARANG, jangan menunggu
Target/SL/lapis manapun.

**Diuji sbg tambahan DI ATAS 2-lapis yang sudah ada** (350 saham/3 tahun, walk-forward,
sistem gabungan Breakout+Zig Zag @ threshold 10%):

| Threshold Jual Dini | Avg Return | Win Rate | Profit Factor | % trade keluar via jalur ini |
|---|---|---|---|---|
| (baseline, tanpa rule ini) | +7,34% | 59,3% | 4,73 | - |
| **5% (dipilih)** | +7,91% | 59,4% | **5,03** | ~30% |

Threshold 5% dipilih. **Divalidasi**:

| | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| Semua | 2.711 | +7,91% | 59,4% | 5,03 |
| Split-half 1 | 1.355 | +8,72% | 58,3% | 5,29 |
| Split-half 2 | 1.356 | +7,10% | 60,5% | 4,74 |
| Bullish | 1.616 | +9,03% | 60,5% | 5,67 |
| Bearish | 1.095 | +6,26% | 57,8% | 4,11 |

Trade yang keluar via Sinyal Jual Dini rata-rata untungnya jauh lebih besar drpd sisa
trade yang masih menunggu cara lama - artinya rule ini menyelamatkan untung BESAR yang
dulu dibiarkan jalan sampai balik ke level kuncian lama (jauh dari puncak), persis
masalah yang diceritakan user.

**BUG DITEMUKAN & DIPERBAIKI (2026-08-31, saat mereplikasi ide ini ke Kandidat/Swing -
lihat bagian di bawah)**: versi AWAL (yang angkanya dipublikasikan pertama kali di README
ini, PF 5,27) cek drawdown dari Close TANPA peduli apakah SL hari itu JUGA tersentuh via
Low - menyimpang dari konvensi "SL dicek LEBIH DULU" yang dipakai di seluruh sistem. Fix:
Sinyal Jual Dini SEKARANG dijaga TIDAK aktif kalau Low hari ini sudah <= SL yang berlaku.
Angka di tabel di atas SUDAH memakai urutan yang benar (PF turun tipis dari 5,27 ke 5,03,
tapi tetap perbaikan nyata dari baseline 4,73).

**Implementasi**: kolom baru **"Harga Puncak"** (N) di `simple_journal.py` - melacak
titik tertinggi sejak posisi dibuka, diperbarui tiap hari posisi masih OPEN. Dicek
setelah cek SL hari ini, sebelum lapis partial-lock/target-lock - `SELL_DRAWDOWN_PCT =
5.0`. Sheet yang sudah live otomatis dilengkapi kolom ini oleh `_get_worksheet()` - TIDAK
perlu langkah manual.

## Sinyal Jual Dini di Kandidat/Swing (2026-08-31)

Setelah divalidasi di Screener Sederhana, user tanya: "apakah sinyal jual dini ada di
kandidat dan screener sederhana?" -> "ya uji" (replikasi & uji ke sistem utama). Kandidat
punya mekanisme exit BERBEDA (Target-Lock SAJA, TANPA lapis partial, SL cap 10% bukan
5%) - jadi diuji ULANG dari nol, bukan asumsi hasil yang sama.

**Diuji** (614 sinyal, 350 saham/3 tahun, walk-forward, urutan SL-dicek-dulu yang BENAR
sejak awal - lihat catatan bug di atas):

| | N | Avg Return | Win Rate | Profit Factor |
|---|---|---|---|---|
| Baseline (Target-Lock saja) | 614 | +2,23% | 32,7% | 1,48 |
| **+ Sinyal Jual Dini (threshold 10%)** | 614 | **+2,54%** | **37,3%** | **1,60** |
| — Bullish (baseline vs +Jual Dini) | 426 | +3,36% -> **+3,41%** | 34,0% -> **39,4%** | 1,72 -> **1,81** |
| — Bearish (baseline vs +Jual Dini) | 188 | -0,34% -> **+0,56%** | 29,8% -> 32,4% | 0,93 -> **1,13** (rugi bersih -> profit) |

Threshold 10% (SAMA dgn Screener Sederhana, konsisten) - MENANG di SEMUA regime & SEMUA
metrik sekaligus (beda dari Screener Sederhana yang trade-off avg return sedikit di
Bullish - di sini avg Bullish malah naik juga). Split-half stabil (+2,59%/+2,48%). Uji
threshold lain (8%, 12%, 15%, 20%) menunjukkan 10-15% adalah area optimal (PF naik sampai
~15% lalu mulai turun lagi di 20%) - 10% dipilih utk konsistensi dgn Screener Sederhana,
bukan cuma mengejar titik puncak persis (hindari overfitting ke 1 backtest).

**Implementasi**: kolom baru **"Harga Puncak"** (P, setelah kolom deprecated "Momentum
Kuat" di O) di `gsheet_journal.py`. `_get_worksheet()` SEKARANG melengkapi header yang
belum ada scr OTOMATIS (pola baru, sebelumnya file ini tidak punya migrasi header sama
sekali - user tidak perlu tambah kolom manual lagi, beda dari kolom lama).
`SELL_DRAWDOWN_PCT = 10.0`, dicek setelah SL hari ini, sebelum blok Target-Lock.

## Sinyal Jual Tampil Langsung di Tab Kandidat (2026-08-31)

User: "seingatku posisi hanya untuk backtest. apakah bisa ditambahkan langsung di
kandidat. kalau saham tersebut pernah muncul buy dan besok atau dikemudian hari terjadi
penurunan maka yang berpotensi berlanjut muncul dikandidat sebagai signal sell." - betul,
sebelum ini Sinyal Jual Dini cuma diproses diam-diam oleh `auto_close_positions()` (cron
otomatis/tombol manual di tab lain), TIDAK pernah tampil di tab "🏆 Kandidat" yang
biasa dilihat user tiap hari.

**Implementasi**: `gsheet_journal.py::preview_sinyal_jual_dini()` - fungsi READ-ONLY baru
(TIDAK menutup posisi, TIDAK menulis ke sheet sama sekali) yang menghitung ULANG kriteria
Sinyal Jual Dini yang SAMA (SL hari ini, drawdown dari puncak, guard sama-hari) tanpa efek
samping - sengaja DUPLIKAT logika drpd menambah flag `dry_run` ke `auto_close_positions()`
yang sudah kompleks & sensitif (posisi riil). Tab Kandidat sekarang menampilkan kotak
merah "🔴 SINYAL JUAL" berisi saham OPEN yang memenuhi kriteria ini, plus tombol "Proses
Sinyal Jual Sekarang" yang memanggil `auto_close_positions()` yang SEBENARNYA (bukan
cuma preview) kalau user mau langsung menutup dari situ juga.

**Direplikasi ke Screener Sederhana juga** (user: "lakukan juga discreener sederhana") -
`simple_journal.py::preview_sinyal_jual_dini()`, kotak & tombol yang SAMA di tab "🔬
Screener Sederhana", threshold 5% (SAMA dgn `SELL_DRAWDOWN_PCT` sistem itu).

**Fix diagnosability** (user: "namun saya tidak menemukan kotak merah sinya jual") - versi
AWAL kotak ini CUMA muncul kalau ADA hasilnya (`if not sinyal_jual.empty`), jadi kalau
memang tidak ada posisi yang memenuhi kriteria hari itu (state NORMAL - threshold 5-10%
butuh pullback cukup dalam, tidak setiap hari kejadian), kotak-nya SAMA SEKALI tidak
tampil - user tidak bisa membedakan "memang tidak ada sinyal" dari "fitur tidak jalan".
Fix: kotak SEKARANG SELALU tampil begitu jurnal terhubung - isinya tabel kalau ADA sinyal,
atau pesan info "Tidak ada posisi yang memenuhi kriteria" kalau kosong; exception saat
menghitung ditampilkan sbg pesan error yang jelas (bukan diam-diam jadi kosong).

## Checkbox Gate Likuiditas di Screener Sederhana (2026-08-31)

User minta checkbox serupa yang sudah ada di tab Kandidat. Ditemukan SAAT itu:
`build_simple_candidates()` **TIDAK PERNAH cek "Layak Likuiditas" sama sekali** - beda
dari `build_trade_candidates()` yang dilindungi gate Rp 3 M/hari (lewat Score=-99 di
`compute_metrics()`). Saham tidak likuid bisa lolos jadi kandidat Screener Sederhana
tanpa disaring - gap yang sudah ada sejak fungsi ini dibuat, baru ketemu sekarang.

**Perbaikan**: parameter baru `min_value_traded` (default 0 = nonaktif, SAMA perilaku
sblm ini) di `build_simple_candidates()`. Checkbox baru di sidebar - "Wajib likuiditas
tinggi (Value Traded >= Rp 3 M/hari) di Screener Sederhana" - default AKTIF, mengirim
`DEFAULT_PARAMS["min_value_traded"]` (gate yang SAMA dgn tab Kandidat) kalau dicentang.
`auto_run.py` (cron otomatis) ikut memakai gate ini secara default (tidak ada UI di
sana). Belum ada backtest khusus yang menguji dampak gate ini ke sistem Screener
Sederhana secara spesifik (universe backtest 350 saham kemungkinan sudah cukup likuid
semua) - checkbox ini soal KONSISTENSI & menutup gap yang ditemukan, bukan optimasi yang
divalidasi dgn angka backtest baru.

## Bug Skala: "Modal Awal Backtest" Salah Penyebut, Drawdown Kelihatan 3-4x Lebih Parah (2026-08-31)

User panik: "modal semakin habis", menunjukkan screenshot "Kurva Ekuitas Backtest" -
Equity turun Rp10jt->Rp6,33jt (-29,62%), Max Drawdown **-40,92%** dlm ~3 minggu.

**Akar masalah**: Lot posisi (baik Kandidat maupun Screener Sederhana) dihitung pakai
`total_equity_now` - modal RIIL dari snapshot terbaru tab Equity (user konfirmasi:
Rp35.550.236, dilacak balik & cocok dari beberapa Lot trade nyata: ARKO/KIJA/FILM/DOOH/
BYAN/ICBP/VTNY semua konsisten menunjukkan ~Rp33-40jt). P&L Rupiah yang dihasilkan tiap
trade OTOMATIS berskala modal itu. TAPI tab Performance's "Modal Awal Backtest" SELALU
default Rp10 juta - angka arbitrer TIDAK ADA hubungannya dgn `total_equity_now` - jadi
drawdown % = (P&L Rupiah dari modal 35jt) / (penyebut 10jt) = **salah skala ~3,5x lebih
parah dari kenyataan**. Drawdown SEBENARNYA (thd modal riil 35,55jt) sekitar -10% s.d
-14%, BUKAN -40,92% - masih rugi nyata & perlu perhatian, tapi jauh dari separah yang
ditampilkan.

**Fix**: default "Modal Awal Backtest" SEKARANG pakai `total_equity_now` (modal riil dari
snapshot Equity terbaru) kalau ada, bukan selalu 10 juta - drawdown % yang ditampilkan
jadi konsisten dgn modal yang BENAR-BENAR dipakai sizing Lot. Tetap bisa diubah manual
kalau mau uji skenario modal lain.

**Ditemukan bareng**: "Total Invested" di tab Equity (Rp62,97jt) tidak cocok dgn nilai
riil user (Rp54jt) - kemungkinan salah satu dari 6 sekuritas punya snapshot "Invested"
yang belum diupdate (stale) sejak jual/rebalance, BUKAN bug kode (field ini diisi manual
per sekuritas, bukan dihitung sistem) - user diminta cek tab Equity > Riwayat.

**Belum selesai**: akar penyebab drawdown -10% s.d -14% itu SENDIRI (klaster SL
berbarengan di beberapa hari - 7 saham kena SL bareng 10 Agustus, dari data live yang
user kirim) belum digali tuntas - beberapa trade tertua kemungkinan masih kena bug "jual
hari sama dgn beli" (sudah diperbaiki 19 Agustus, tapi trade LAMA yg kena bug itu baru
closed sekarang) yang MENCEMARI angka mentah - checkbox exclude-nya sudah ada di tab
Performance (default aktif) tapi belum divalidasi silang dgn data live user secara
lengkap (export CSV user tidak ikut kolom "Tanggal Open" yg dibutuhkan filter itu).

## Jalankan di Laptop Sendiri (opsional, sebelum deploy)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Buka `http://localhost:8501` di browser.
