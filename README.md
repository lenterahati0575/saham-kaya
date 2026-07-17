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

## Cara Kerja Fitur Trading

### Day Trading — BPJS & BSJP
- **BPJS** (Beli Pagi Jual Sore): otomatis dipilih sistem kalau sekarang sebelum jam 13:00 WIB
- **BSJP** (Beli Sore Jual Pagi): otomatis dipilih kalau sekarang jam 13:00 WIB ke atas
- Force-sell otomatis: BPJS ditutup paksa kalau lewat 1 hari, BSJP kalau lewat 2 hari (belum kena TP/SL)

### Swing Trading
- Force-sell otomatis kalau sudah 10 hari dan belum kena TP atau SL
- Bisa dibuka kapan saja (pagi/sore), tidak terikat waktu seperti Day Trading

### Perhitungan Entry / Target / Stop Loss (bukan persen tetap)
- **Entry**: harga saat ini
- **Stop Loss**: level terendah Donchian (struktural - beda tiap saham, bukan persen flat)
- **Target**: proyeksi *measured move* = Donchian High + lebar channel (High − Low)
- **RR (Risk:Reward)**: (Target − Entry) / (Entry − Stop Loss), tabel Top 10 hanya menampilkan RR ≥ ambang minimum (default 2:1)

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
