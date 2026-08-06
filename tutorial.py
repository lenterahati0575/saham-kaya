"""
Tutorial Interaktif untuk IDX Screener Dashboard
Bisa di-import dan dipanggil dari app.py
"""
import streamlit as st

def show_tutorial():
    st.title("📚 Tutorial Penggunaan Sistem")
    st.caption("Panduan lengkap untuk memaksimalkan penggunaan dashboard ini")
    
    # Navigation
    tutorial_tabs = st.tabs([
        "🚀 Quick Start",
        "🏆 Trading Harian",
        "📊 Analisis Teknikal",
        "💼 Manajemen Portofolio",
        " Analisis Fundamental",
        "⚙️ Tips & Trik"
    ])
    
    with tutorial_tabs[0]:
        show_quick_start()
    
    with tutorial_tabs[1]:
        show_daily_trading()
    
    with tutorial_tabs[2]:
        show_technical_analysis()
    
    with tutorial_tabs[3]:
        show_portfolio_management()
    
    with tutorial_tabs[4]:
        show_fundamental_analysis()
    
    with tutorial_tabs[5]:
        show_tips_and_tricks()

def show_quick_start():
    st.header(" Quick Start - Mulai dalam 5 Menit")
    
    st.markdown("""
    ### 🎯 Langkah Pertama
    """)
    
    steps = [
        ("1️⃣", "Setup Sidebar", "Atur parameter filter sesuai gaya trading Anda"),
        ("2️⃣", "Refresh Data", "Klik tombol '🔄 Refresh Data Live' untuk data terbaru"),
        ("3️⃣", "Lihat Kandidat", "Buka tab '🏆 Kandidat' untuk melihat saham terbaik"),
        ("4️⃣", "Filter Saham", "Gunakan filter Rekomendasi, Quality, dan RR"),
        ("5️⃣", "Kirim ke Jurnal", "Pilih saham dan kirim ke Jurnal Real"),
    ]
    
    for icon, title, desc in steps:
        with st.expander(f"{icon} {title}", expanded=False):
            st.write(desc)
    
    st.divider()
    
    st.markdown("### ⚙️ Konfigurasi Sidebar yang Direkomendasikan")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Untuk Day Trading:**")
        st.code("""
        Min. Value Traded: 3.0 miliar
        Donchian Lookback Day: 10 hari
        Min RR: 2.0
        Skor min STRONG BUY: 7
        """)
    
    with col2:
        st.markdown("**Untuk Swing Trading:**")
        st.code("""
        Min. Value Traded: 5.0 miliar
        Donchian Lookback Swing: 20 hari
        Min RR: 1.5 (default tervalidasi backtest)
        Skor min BUY: 5
        Filter IHSG Bearish: AKTIF
        """)
        st.caption("Angka di atas BUKAN saran sembarangan - sudah diuji lewat backtest realistis "
                   "+ out-of-sample (lihat README > Backtest Historis). Kalau Bro ubah manual, "
                   "validasi ulang dulu pakai `backtest.py` sebelum percaya hasilnya.")

def show_daily_trading():
    st.header("🏆 Trading Harian - Workflow Lengkap")
    
    st.markdown("### 📋 Alur Kerja Trading Harian")
    
    workflow = {
        "🌅 Pagi (08:00 - 09:30)": {
            "icon": "☀️",
            "steps": [
                "Buka tab **🏆 Kandidat**",
                "Cek RR ≥ 2.0 + Quality HIGH (semua kandidat = Swing tervalidasi)",
                "Pilih 2-3 saham terbaik",
                "Kirim ke Jurnal Real",
                "Cek chart di TradingView"
            ]
        },
        "📈 Sesi 1 (09:30 - 12:00)": {
            "icon": "📊",
            "steps": [
                "Monitor harga entry",
                "Entry saat harga sesuai",
                "Pasang Stop Loss & Target",
                "Catat di Jurnal Real"
            ]
        },
        "🌆 Sesi 2 (13:30 - 15:00)": {
            "icon": "🌇",
            "steps": [
                "Monitor posisi",
                "Exit sesuai plan (TP/SL)",
                "Update Jurnal Real",
                "Review performance"
            ]
        }
    }
    
    for time_slot, data in workflow.items():
        with st.expander(f"{data['icon']} {time_slot}", expanded=False):
            for i, step in enumerate(data['steps'], 1):
                st.write(f"{i}. {step}")
    
    st.divider()
    
    st.markdown("### 🎯 Filter yang Efektif")
    
    filter_options = {
        "Konservatif": {
            "quality": ["✅ HIGH"],
            "rr": "≥ 3.0",
            "deskripsi": "Untuk trader yang ingin risiko minimal"
        },
        "Moderat": {
            "quality": ["✅ HIGH", "⚠️ MODERATE"],
            "rr": "≥ 2.0",
            "deskripsi": "Balance antara risiko dan opportunity"
        },
        "Agresif": {
            "quality": ["✅ HIGH", "⚠️ MODERATE"],
            "rr": "≥ 1.5",
            "deskripsi": "Untuk trader berpengalaman dengan risk tolerance tinggi"
        }
    }

    for style, config in filter_options.items():
        with st.expander(f"💡 Gaya {style}", expanded=False):
            st.write(f"**Deskripsi:** {config['deskripsi']}")
            st.write(f"**Quality:** {', '.join(config['quality'])}")
            st.write(f"**RR:** {config['rr']}")

def show_technical_analysis():
    st.header("📊 Analisis Teknikal - Membaca Grafik")
    
    st.markdown("### 📈 Komponen Grafik")
    
    chart_components = {
        "🕯️ Candlestick": {
            "fungsi": "Menampilkan harga Open, High, Low, Close",
            "cara_baca": "Hijau = naik, Merah = turun",
            "tips": "Perhatikan pola candle untuk sinyal reversal"
        },
        "📊 Moving Average": {
            "fungsi": "Rata-rata harga periode tertentu",
            "cara_baca": "MA5 (kuning), MA20 (biru), MA50 (ungu)",
            "tips": "Golden cross (MA5 > MA20) = bullish signal"
        },
        "📉 Donchian Channel": {
            "fungsi": "Level breakout berdasarkan high/low N hari",
            "cara_baca": "Garis hijau = resistance, merah = support",
            "tips": "Breakout di atas Donchian High = sinyal beli kuat"
        },
        "🎯 Swing Points": {
            "fungsi": "Titik pivot high dan low",
            "cara_baca": "HH/HL = uptrend, LH/LL = downtrend",
            "tips": "Gunakan untuk konfirmasi trend direction"
        }
    }
    
    for component, info in chart_components.items():
        with st.expander(f"{component}", expanded=False):
            st.write(f"**Fungsi:** {info['fungsi']}")
            st.write(f"**Cara Baca:** {info['cara_baca']}")
            st.write(f"**Tips:** {info['tips']}")
    
    st.divider()
    
    st.markdown("### 🔬 Analisis Profesional")
    
    st.warning("⚠️ **Koreksi penting**: versi tutorial sebelumnya mencantumkan angka \"akurasi\" "
               "(70-75%, 65-70%, dst.) untuk keempat metode di bawah - angka itu KARANGAN, tidak "
               "pernah dihitung dari data apapun. Sudah dihapus. Satu-satunya yang benar-benar "
               "diuji secara historis di dashboard ini adalah **Gann Time Cycle** (tab IHSG "
               "Analysis) - hasilnya hit rate 40.3% (Gann) / 40.4% (Fibonacci), SETARA hari acak "
               "42.9%, alias TIDAK terbukti prediktif untuk IHSG. Anggap 4 metode di bawah sebagai "
               "kerangka konsep klasik untuk dipelajari, bukan alat dengan bukti win-rate.")

    pro_analysis = {
        "💰 Smart Money Flow": {
            "indikator": "VWAP + Volume Ratio",
            "sinyal_beli": "Harga > VWAP + Volume tinggi",
            "sinyal_jual": "Harga < VWAP + Volume tinggi",
        },
        "📐 Fibonacci Retracement": {
            "indikator": "Level 23.6%, 38.2%, 50%, 61.8%",
            "sinyal_beli": "Harga di level 38.2% atau 50%",
            "sinyal_jual": "Harga di level 61.8% atau 78.6%",
        },
        "🌊 Elliott Wave": {
            "indikator": "Pola 5 wave atau 3 wave",
            "sinyal_beli": "Impulse wave (1-2-3-4-5)",
            "sinyal_jual": "Corrective wave (A-B-C)",
        },
        "🔷 Gann Levels": {
            "indikator": "Support/Resistance berbasis sudut Gann",
            "sinyal_beli": "Harga di support Gann",
            "sinyal_jual": "Harga di resistance Gann",
        }
    }

    for analysis, info in pro_analysis.items():
        with st.expander(f"{analysis}", expanded=False):
            st.write(f"**Indikator:** {info['indikator']}")
            st.write(f"**Sinyal Beli:** {info['sinyal_beli']}")
            st.write(f"**Sinyal Jual:** {info['sinyal_jual']}")

def show_portfolio_management():
    st.header("💼 Manajemen Portofolio")
    
    st.markdown("### 📊 Tracking Equity")
    
    equity_steps = [
        {
            "step": "1️⃣ Catat Snapshot Pertama",
            "action": "Buka tab  Equity > Catat Snapshot",
            "detail": "Isi Total Equity, Cash, dan Invested dari aplikasi sekuritas Anda",
            "tips": "Lakukan di akhir hari bursa untuk akurasi maksimal"
        },
        {
            "step": "2️ Update Berkala",
            "action": "Catat snapshot setiap minggu/bulan",
            "detail": "Pastikan semua sekuritas dicatat di tanggal yang sama",
            "tips": "Konsistensi lebih penting daripada frekuensi"
        },
        {
            "step": "3️⃣ Monitor Performance",
            "action": "Lihat tab  Equity > Ringkasan",
            "detail": "Perhatikan Total Return, Max Drawdown, dan Cash Ratio",
            "tips": "Cash Ratio ideal: 10-20% untuk buffer"
        },
        {
            "step": "4️⃣ Bandingkan dengan IHSG",
            "action": "Lihat grafik Equity vs IHSG",
            "detail": "Apakah portofolio Anda outperform atau underperform?",
            "tips": "Target minimal: mengalahkan IHSG + 2-3% per tahun"
        }
    ]
    
    for item in equity_steps:
        with st.expander(f"{item['step']}", expanded=False):
            st.write(f"**Action:** {item['action']}")
            st.write(f"**Detail:** {item['detail']}")
            st.write(f"**Tips:** {item['tips']}")
    
    st.divider()
    
    st.markdown("### 📈 Risk Metrics yang Penting")
    
    risk_metrics = {
        "Sharpe Ratio": {
            "formula": "(Return - Risk Free) / Volatility",
            "interpretasi": {
                "> 1.5": "🟢 Excellent",
                "0.5 - 1.5": "🟡 Good",
                "< 0.5": " Poor"
            },
            "tips": "Semakin tinggi semakin baik (return per unit risiko)"
        },
        "Max Drawdown": {
            "formula": "(Peak - Trough) / Peak × 100%",
            "interpretasi": {
                "< 10%": "🟢 Aman",
                "10-20%": "🟡 Waspada",
                "> 20%": "🔴 Berbahaya"
            },
            "tips": "Ukuran kerugian maksimal dari peak"
        },
        "Cash Ratio": {
            "formula": "Cash / Total Equity × 100%",
            "interpretasi": {
                "10-25%": "🟢 Ideal",
                "< 10%": "🟡 Terlalu rendah",
                "> 25%": "🟡 Terlalu tinggi"
            },
            "tips": "Buffer untuk opportunity dan emergency"
        }
    }
    
    for metric, info in risk_metrics.items():
        with st.expander(f" {metric}", expanded=False):
            st.write(f"**Formula:** {info['formula']}")
            st.write("**Interpretasi:**")
            for threshold, label in info['interpretasi'].items():
                st.write(f"  - {threshold}: {label}")
            st.write(f"**Tips:** {info['tips']}")

def show_fundamental_analysis():
    st.header(" Analisis Fundamental")
    
    st.markdown("### 📊 Screener Fundamental")
    
    fundamental_filters = {
        "Value Investing": {
            "P/E": "< 15",
            "P/B": "< 1.5",
            "ROE": "> 15%",
            "Debt/Equity": "< 0.5",
            "Dividend Yield": "> 2%",
            "kategori": "🟨 Classic Value"
        },
        "Growth Investing": {
            "P/E": "< 25",
            "PEG": "< 1.5",
            "ROE": "> 15%",
            "Earnings Growth": "> 15%",
            "Revenue Growth": "> 10%",
            "kategori": "🟩 GARP"
        },
        "Dividend Investing": {
            "P/E": "< 15",
            "Dividend Yield": "> 3%",
            "Payout Ratio": "< 70%",
            "ROE": "> 10%",
            "Debt/Equity": "< 1.0",
            "kategori": "🟦 Dividend Aristocrat"
        },
        "Deep Value": {
            "P/E": "< 10",
            "P/B": "< 1.0",
            "Margin of Safety": "> 30%",
            "ROE": "> 10%",
            "Debt/Equity": "< 0.5",
            "kategori": "🟥 Deep Value"
        }
    }
    
    for strategy, filters in fundamental_filters.items():
        with st.expander(f"💡 Strategi {strategy}", expanded=False):
            st.write(f"**Kategori:** {filters['kategori']}")
            st.write("**Filter:**")
            for key, value in filters.items():
                if key != 'kategori':
                    st.write(f"  - {key}: {value}")
    
    st.divider()
    
    st.markdown("### 🏛️ Value Investing (Buffett Style)")
    
    buffett_checklist = [
        {
            "kriteria": "ROE > 15%",
            "alasan": "Bisnis menghasilkan return tinggi untuk pemegang saham",
            "cara_cek": "Lihat kolom ROE % di tabel fundamental"
        },
        {
            "kriteria": "Debt/Equity < 0.5",
            "alasan": "Bisnis tidak bergantung pada utang",
            "cara_cek": "Lihat kolom Debt/Eq"
        },
        {
            "kriteria": "P/E < 20",
            "alasan": "Harga tidak terlalu mahal",
            "cara_cek": "Lihat kolom P/E"
        },
        {
            "kriteria": "Margin of Safety > 25%",
            "alasan": "Beli dengan diskon aman dari nilai wajar",
            "cara_cek": "Lihat kolom MOS %"
        },
        {
            "kriteria": "EPS Growth konsisten",
            "alasan": "Earnings tumbuh stabil",
            "cara_cek": "Lihat kolom EPS Growth %"
        },
        {
            "kriteria": "Dividend (opsional)",
            "alasan": "Prefer bisnis yang bagi dividen",
            "cara_cek": "Lihat kolom Div Yield %"
        }
    ]
    
    for item in buffett_checklist:
        with st.expander(f"✅ {item['kriteria']}", expanded=False):
            st.write(f"**Alasan:** {item['alasan']}")
            st.write(f"**Cara Cek:** {item['cara_cek']}")

def show_tips_and_tricks():
    st.header("⚙️ Tips & Trik")
    
    st.markdown("### 🎯 Tips Trading")
    
    tips = [
        {
            "kategori": "📊 Manajemen Risiko",
            "tips": [
                "Jangan risiko lebih dari 2% modal per trade",
                "Selalu pasang Stop Loss sebelum entry",
                "Risk:Reward minimal 2:1",
                "Diversifikasi maksimal 5-7 saham"
            ]
        },
        {
            "kategori": " Psikologi Trading",
            "tips": [
                "Jangan FOMO (Fear of Missing Out)",
                "Ikuti plan, jangan emosi",
                "Cut loss cepat, let profit run",
                "Review jurnal setiap minggu"
            ]
        },
        {
            "kategori": "📈 Analisis Teknikal",
            "tips": [
                "Konfirmasi sinyal dengan minimal 2 indikator",
                "Perhatikan volume saat breakout",
                "Gunakan multiple timeframe analysis",
                "Jangan trade melawan trend besar"
            ]
        },
        {
            "kategori": "💼 Manajemen Portofolio",
            "tips": [
                "Rebalance portofolio setiap bulan",
                "Jaga cash ratio 10-20%",
                "Catat equity snapshot rutin",
                "Bandingkan performance dengan benchmark"
            ]
        }
    ]
    
    for tip in tips:
        with st.expander(f"{tip['kategori']}", expanded=False):
            for i, item in enumerate(tip['tips'], 1):
                st.write(f"{i}. {item}")
    
    st.divider()
    
    st.markdown("### 🔧 Fitur Tersembunyi")
    
    hidden_features = [
        {
            "fitur": "Auto-Refresh",
            "lokasi": "Sidebar > Checkbox '🔄 Auto Refresh (5 menit)'",
            "fungsi": "Data otomatis refresh setiap 5 menit saat market hours",
            "tips": "Aktifkan saat monitoring live trading"
        },
        {
            "fitur": "Download CSV",
            "lokasi": "Setiap tabel ada tombol '⬇️ Download CSV'",
            "fungsi": "Export data untuk analisis di Excel",
            "tips": "Backup data secara berkala"
        },
        {
            "fitur": "Chart TradingView",
            "lokasi": "Klik baris di tabel atau pilih di dropdown",
            "fungsi": "Lihat chart interaktif dengan indikator lengkap",
            "tips": "Bisa ganti timeframe dan tambah indikator"
        },
        {
            "fitur": "Telegram Alert",
            "lokasi": "Sidebar > Tombol '📤 Kirim Alert ke Telegram'",
            "fungsi": "Kirim notifikasi alert ke Telegram",
            "tips": "Setup bot token di Settings > Secrets"
        },
        {
            "fitur": "Auto-Fill Jurnal",
            "lokasi": "Tab Kandidat > Pilih saham > Kirim ke Jurnal Real",
            "fungsi": "Data entry, SL, target otomatis terisi",
            "tips": "Hemat waktu catat transaksi"
        }
    ]
    
    for feature in hidden_features:
        with st.expander(f"✨ {feature['fitur']}", expanded=False):
            st.write(f"**Lokasi:** {feature['lokasi']}")
            st.write(f"**Fungsi:** {feature['fungsi']}")
            st.write(f"**Tips:** {feature['tips']}")
    
    st.divider()
    
    st.markdown("### 📞 Bantuan")
    
    st.info("""
    **Jika ada pertanyaan atau masalah:**
    1. Cek tutorial ini dulu
    2. Lihat README di repository GitHub
    3. Buka issue di GitHub jika ada bug
    4. Cek log error di Streamlit Cloud (Manage app > Logs)
    
    **Resources:**
    - [Streamlit Documentation](https://docs.streamlit.io)
    - [Yahoo Finance API](https://pypi.org/project/yfinance/)
    - [TradingView Widgets](https://www.tradingview.com/widget/)
    """)

# Untuk testing standalone
if __name__ == "__main__":
    show_tutorial()
