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
8. Simpan, app otomatis restart. Tab **Jurnal Backtest** akan aktif dan bisa baca/tulis ke sheet POSISI.

### Tombol TradingView (kolom "TV")
Setiap tabel saham punya kolom "TV" berisi tombol yang membuka chart TradingView saham itu
langsung di TAB YANG SAMA (bukan tab baru), memakai format `IDX:KODE`.

### Tab Performance
Menghitung performa transaksi RIIL dari sheet POSISI (bukan sheet terpisah yang harus
disinkronkan manual) - begitu ada posisi yang ditutup (WIN/LOSS/FORCE SELL) lewat tombol
Auto-SELL di tab Jurnal Backtest, tab Performance otomatis menampilkan: akumulasi profit,
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
- **Stop Loss**: level terendah Donchian (struktural - beda tiap saham, bukan persen flat)
- **Target**: proyeksi *measured move* = Donchian High + lebar channel (High − Low)
- **RR (Risk:Reward)**: (Target − Entry) / (Entry − Stop Loss), tabel Top 10 hanya menampilkan
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
