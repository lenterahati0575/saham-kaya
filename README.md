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

## Jalankan di Laptop Sendiri (opsional, sebelum deploy)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Buka `http://localhost:8501` di browser.
