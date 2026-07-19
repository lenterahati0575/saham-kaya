import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from screener import (DEFAULT_PARAMS, load_ticker_universe, fetch_price_history, build_screener_table,
                      build_trade_candidates, classify_daytrading_tipe, fetch_ihsg_history)
from telegram_notify import send_telegram_message, format_watchlist_message
import gsheet_journal as gj
import indicators as ind
import calculators as calc
import sectors as sec
import real_journal as rj
import equity as eq

st.set_page_config(page_title="IDX Screener Dashboard", page_icon="📈", layout="wide")


def embed_tradingview_chart(kode: str, height: int = 520):
    """Chart TradingView LIVE tertanam LANGSUNG di halaman (bukan link ke tab baru).

    Sengaja pakai <iframe src="..."> polos, BUKAN <script>TradingView.widget(...)</script>.
    Pendekatan script sempat dicoba tapi sering gagal render blank di dalam iframe Streamlit
    (komponen Streamlit sendiri dirender di dalam iframe, jadi widget TradingView jadi
    iframe-di-dalam-iframe yang bergantung pada timing eksekusi script - rawan gagal).
    Iframe langsung tidak punya masalah timing seperti itu, jadi jauh lebih pasti muncul."""
    src = (
        f"https://s.tradingview.com/widgetembed/?symbol=IDX%3A{kode}"
        f"&interval=D&theme=dark&style=1&locale=id&toolbar_bg=%230e1117"
        f"&hide_top_toolbar=0&allow_symbol_change=1&save_image=0"
    )
    html = f"""
    <iframe src="{src}" width="100%" height="{height}" frameborder="0"
            allowtransparency="true" scrolling="no"></iframe>
    """
    components.html(html, height=height + 10)


def dataframe_with_chart(df_display, kode_col="Kode", height=460, key=None, column_config=None):
    """Tabel yang bisa DIKLIK BARISNYA untuk memunculkan chart TradingView di bawahnya -
    langsung di halaman yang sama, bukan tab baru (menggantikan LinkColumn yang selalu
    dipaksa browser buka tab baru karena tabel Streamlit dirender dalam iframe ter-sandbox)."""
    event = st.dataframe(
        df_display, use_container_width=True, hide_index=True, height=height,
        on_select="rerun", selection_mode="single-row", key=key,
        column_config=column_config or {},
    )
    selected_rows = event.selection.rows if event and hasattr(event, "selection") else []
    if selected_rows:
        kode_selected = df_display.iloc[selected_rows[0]][kode_col]
        st.markdown(f"**📈 Chart TradingView — {kode_selected}**")
        embed_tradingview_chart(kode_selected, height=420)
    else:
        st.caption("💡 Klik salah satu baris di tabel di atas untuk melihat chart TradingView "
                   "langsung di sini (tanpa pindah tab).")

# ---------------- Style ----------------
st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
div[data-testid="stMetric"] {
    background: #111827; border-radius: 12px; padding: 12px 14px; border: 1px solid #1f2937;
    overflow: hidden;
}
div[data-testid="stMetricValue"] {
    font-size: 1.35rem !important; white-space: normal !important; overflow-wrap: break-word;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
}
.signal-strongbuy {background:#065f46; color:white; padding:2px 8px; border-radius:6px; font-weight:600;}
.signal-buy {background:#16a34a; color:white; padding:2px 8px; border-radius:6px; font-weight:600;}
.signal-hold {background:#374151; color:#d1d5db; padding:2px 8px; border-radius:6px;}
.signal-sell {background:#b91c1c; color:white; padding:2px 8px; border-radius:6px; font-weight:600;}
.signal-skip {background:#1f2937; color:#6b7280; padding:2px 8px; border-radius:6px;}
.badge-buy {background:#16a34a; color:white; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem;}
.badge-sell {background:#dc2626; color:white; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem;}
.badge-neutral {background:#4b5563; color:white; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem;}
.month-card {border-radius:10px; padding:10px 6px; text-align:center; margin-bottom:6px;}
.month-card-pos {background:rgba(22,163,74,0.18); border:1px solid #16a34a;}
.month-card-neg {background:rgba(220,38,38,0.18); border:1px solid #dc2626;}
.month-label {font-size:0.72rem; color:#9ca3af; text-transform:uppercase; letter-spacing:0.03em;}
.month-value-pos {font-size:1.05rem; font-weight:700; color:#4ade80;}
.month-value-neg {font-size:1.05rem; font-weight:700; color:#f87171;}
.cumulative-box {background:linear-gradient(135deg,#111827,#1f2937); border:1px solid #374151;
    border-radius:14px; padding:22px; text-align:center;}
.cumulative-label {font-size:0.85rem; color:#9ca3af; text-transform:uppercase; letter-spacing:0.05em;}
.cumulative-value {font-size:2.4rem; font-weight:800;}
</style>
""", unsafe_allow_html=True)

st.title("📈 IDX Screener Dashboard")
st.caption("Data live Yahoo Finance · Gate likuiditas + Donchian 20D Breakout · Gratis & mobile-friendly")

# ---------------- Sidebar: parameter ----------------
with st.sidebar:
    st.header("⚙️ Parameter Filter")
    min_vt = st.number_input(
        "Min. Value Traded (Rp miliar/hari)", min_value=0.0, value=3.0, step=0.5,
        help="Saham dengan nilai transaksi harian di bawah ini otomatis di-skip (anti gorengan).",
    )
    crash_veto = st.slider(
        "Ambang Crash Veto (%)", min_value=-15, max_value=-1, value=-5,
        help="Penurunan harga di bawah ini kena penalti besar, tidak bisa lolos jadi BUY.",
    ) / 100
    donchian_lb = st.number_input("Donchian Lookback - Swing (hari bursa)", min_value=5, max_value=60, value=20)
    donchian_lb_day = st.number_input("Donchian Lookback - Day Trading (hari bursa)", min_value=3, max_value=30, value=10,
                                       help="Contoh dari Bro: lookback 10 -> garis Donchian 10 hari untuk Day Trading.")
    min_rr = st.number_input("Minimum Risk:Reward (RR)", min_value=1.0, value=2.0, step=0.1,
                              help="Kandidat Top 10 Day/Swing hanya yang RR-nya di atas ini.")
    st.divider()
    st.subheader("📒 Jurnal Backtest (Auto Buy/Sell)")
    st.caption("Entry/Target/Stop Loss Day & Swing dihitung struktural (Donchian + measured-move), "
               "bukan persen tetap - lihat tab 'Top 10 Day/Swing'.")
    st.divider()
    st.subheader("Ambang Skor Sinyal")
    sb = st.number_input("Skor min. STRONG BUY", value=7)
    b = st.number_input("Skor min. BUY", value=4)
    s = st.number_input("Skor maks. SELL", value=-2)
    ss = st.number_input("Skor maks. STRONG SELL", value=-4)
    st.divider()
    n_scan = st.select_slider(
        "Jumlah saham dipindai", options=[50, 100, 200, 400, 615], value=200,
        help="Makin banyak, makin lama waktu refresh (Yahoo Finance dipanggil per-batch).",
    )
    refresh = st.button("🔄 Refresh Data Live", use_container_width=True, type="primary")
    st.divider()
    aktifkan_sektor = st.checkbox(
        "🏷️ Aktifkan Filter Sektor", value=False,
        help="Fetch data sektor dari Yahoo Finance per saham - butuh waktu tambahan saat "
             "pertama kali (di-cache 7 hari setelahnya, jadi kunjungan berikutnya cepat).",
    )

params = {
    "min_value_traded": min_vt * 1_000_000_000,
    "crash_veto": crash_veto,
    "donchian_lookback": int(donchian_lb),
    "score_strong_buy": sb, "score_buy": b, "score_sell": s, "score_strong_sell": ss,
}

# ---------------- Load & fetch ----------------
universe = load_ticker_universe()
tickers = universe["Kode"].tolist()[: int(n_scan)]

if refresh:
    st.cache_data.clear()

with st.spinner(f"Mengambil data live untuk {len(tickers)} saham dari Yahoo Finance..."):
    price_data = fetch_price_history(tickers)

table = build_screener_table(price_data, universe, params)

if table.empty:
    st.warning(
        "Belum ada data yang berhasil diambil. Ini normal kalau dijalankan di sandbox tanpa "
        "internet — coba jalankan di Streamlit Cloud / lokal dengan koneksi internet aktif."
    )
    st.stop()

if aktifkan_sektor:
    with st.spinner(f"Mengambil data sektor untuk {len(table)} saham dari Yahoo Finance..."):
        sector_map = sec.fetch_sectors(table["Kode"].tolist())
    table["Sektor"] = table["Kode"].map(sector_map).fillna(sec.TIDAK_DIKETAHUI)
else:
    table["Sektor"] = None

st.caption(f"Terakhir refresh: {datetime.now().strftime('%d %b %Y, %H:%M')} · "
           f"{len(table)}/{len(tickers)} saham berhasil diambil")

# ---------------- Kotak Pencarian Cepat ----------------
st.subheader("🔍 Cari Saham")
search_col1, search_col2 = st.columns([3, 1])
with search_col1:
    quick_search = st.selectbox(
        "Ketik kode atau nama saham",
        options=[""] + table["Kode"].tolist(),
        format_func=lambda k: "" if k == "" else f"{k} — {table.loc[table['Kode']==k,'Nama'].values[0]}",
        index=0,
        placeholder="Contoh: BBCA, TLKM, ADRO...",
    )
if quick_search:
    row = table[table["Kode"] == quick_search].iloc[0]
    signal_class = {
        "STRONG BUY": "signal-strongbuy", "BUY": "signal-buy", "HOLD": "signal-hold",
        "SELL": "signal-sell", "STRONG SELL": "signal-sell", "SKIP (ILIKUID)": "signal-skip",
    }.get(row["Signal"], "signal-hold")
    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    qc1.metric("Harga", f"Rp{row['Harga']:,.0f}", f"{row['Perubahan %']*100:+.2f}%")
    qc2.markdown(f"**Signal**<br><span class='{signal_class}'>{row['Signal']}</span>", unsafe_allow_html=True)
    qc3.metric("Score", int(row["Score"]))
    qc4.metric("Volume Ratio", f"{row['Volume Ratio']:.1f}x")
    qc5.metric("Status Breakout", row["Status Breakout"])
    if quick_search in price_data:
        st.line_chart(price_data[quick_search]["Close"].tail(60), height=180)
    st.caption("Buka tab **Grafik Saham** di bawah untuk candlestick lengkap + garis Donchian.")

st.divider()

# ---------------- KPI cards ----------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Dipindai", len(table))
c2.metric("STRONG BUY", int((table["Signal"] == "STRONG BUY").sum()))
c3.metric("BUY", int((table["Signal"] == "BUY").sum()))
c4.metric("Breakout Donchian", int((table["Status Breakout"] == "BREAKOUT").sum()))
c5.metric("Skip (Ilikuid)", int((table["Signal"] == "SKIP (ILIKUID)").sum()))

st.divider()

t_kandidat, t_semua, t_grafik, t_backtest, t_top10, t_real, t_equity, t_perf, t_kalk = st.tabs([
    "🏆 Kandidat Terbaik", "📋 Semua Saham", "📉 Grafik Saham", "📒 Jurnal Backtest",
    "🎯 Top 10 Day/Swing", "💼 Jurnal Real", "💰 Equity", "🚀 Performance", "🧮 Kalkulator"
])

# ---------------- TAB 1: kandidat terbaik ----------------
with t_kandidat:
    picks = table[table["Signal"].isin(["STRONG BUY", "BUY"])].copy()
    if aktifkan_sektor and not picks.empty:
        sektor_pilih_1 = st.multiselect(
            "🏷️ Filter Sektor", options=sorted(picks["Sektor"].dropna().unique().tolist()),
            key="sektor_tab1",
        )
        if sektor_pilih_1:
            picks = picks[picks["Sektor"].isin(sektor_pilih_1)]
    if picks.empty:
        st.info("Tidak ada saham yang lolos filter saat ini. Coba longgarkan parameter di sidebar.")
    else:
        show = picks.copy()
        show["Harga"] = show["Harga"].map(lambda x: f"Rp{x:,.0f}")
        show["Perubahan %"] = (picks["Perubahan %"] * 100).map(lambda x: f"{x:+.2f}%")
        show["Value Traded (Rp)"] = picks["Value Traded (Rp)"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        show["Volume Ratio"] = picks["Volume Ratio"].map(lambda x: f"{x:.1f}x")
        kolom_tampil = ["Kode", "Nama", "Signal", "Score", "Harga", "Perubahan %",
                         "Volume Ratio", "Value Traded (Rp)", "Status Breakout"]
        if aktifkan_sektor:
            kolom_tampil.insert(2, "Sektor")
        dataframe_with_chart(show[kolom_tampil], kode_col="Kode", height=460, key="df_kandidat")
        st.download_button(
            "⬇️ Download CSV", show[kolom_tampil].to_csv(index=False).encode("utf-8"),
            file_name=f"kandidat_terbaik_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
        )

        st.divider()
        st.subheader("📲 Kirim ke Telegram")
        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        msg_preview = format_watchlist_message(table)
        with st.expander("Lihat preview pesan"):
            st.text(msg_preview)
        if st.button("Kirim Watchlist Sekarang", type="primary"):
            if not bot_token or not chat_id:
                st.error("Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di Settings > Secrets terlebih dulu (lihat README).")
            else:
                ok, info = send_telegram_message(bot_token, chat_id, msg_preview)
                if ok:
                    st.success(info)
                else:
                    st.error(info)

# ---------------- TAB 2: semua saham ----------------
with t_semua:
    colf1, colf2, colf3 = st.columns([2, 1, 1])
    with colf1:
        search = st.text_input("Cari kode/nama saham", "")
    with colf2:
        sig_filter = st.multiselect(
            "Filter Signal", options=sorted(table["Signal"].unique().tolist()),
            default=[]
        )
    with colf3:
        sektor_filter = []
        if aktifkan_sektor:
            sektor_filter = st.multiselect(
                "🏷️ Filter Sektor", options=sorted(table["Sektor"].dropna().unique().tolist()),
                default=[], key="sektor_tab2",
            )
    view = table.copy()
    if search:
        mask = view["Kode"].str.contains(search.upper()) | view["Nama"].str.upper().str.contains(search.upper())
        view = view[mask]
    if sig_filter:
        view = view[view["Signal"].isin(sig_filter)]
    if sektor_filter:
        view = view[view["Sektor"].isin(sektor_filter)]

    view_display = view.copy()
    view_display["Harga"] = view["Harga"].map(lambda x: f"Rp{x:,.0f}")
    view_display["Perubahan %"] = (view["Perubahan %"] * 100).map(lambda x: f"{x:+.2f}%")
    view_display["Value Traded (Rp)"] = view["Value Traded (Rp)"].map(lambda x: f"Rp{x/1e9:,.1f} M")
    view_display["Volume Ratio"] = view["Volume Ratio"].map(lambda x: f"{x:.1f}x")
    kolom_tampil2 = ["Kode", "Nama", "Signal", "Score", "Harga", "Perubahan %",
                      "Volume Ratio", "Value Traded (Rp)", "Status Breakout", "Layak Likuiditas"]
    if aktifkan_sektor:
        kolom_tampil2.insert(2, "Sektor")
    dataframe_with_chart(view_display[kolom_tampil2], kode_col="Kode", height=520, key="df_semua")
    st.caption(f"Menampilkan {len(view)} dari {len(table)} saham")
    st.download_button(
        "⬇️ Download CSV", view_display[kolom_tampil2].to_csv(index=False).encode("utf-8"),
        file_name=f"semua_saham_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
    )

# ---------------- TAB 3: grafik candlestick + Donchian + MA + Technical Indicators + Swing HL ----------------
with t_grafik:
    pilih = st.selectbox("Pilih saham", options=table["Kode"].tolist())
    if pilih in price_data:
        df_full = price_data[pilih]
        df = df_full.tail(90)
        row = table[table["Kode"] == pilih].iloc[0]

        chart_mode = st.radio(
            "Sumber grafik", ["Dashboard (Plotly + Donchian + Swing HL)", "TradingView Live (tertanam di halaman ini)"],
            horizontal=True, label_visibility="collapsed",
        )

        if chart_mode.startswith("TradingView"):
            embed_tradingview_chart(pilih)
            st.caption("Chart TradingView muncul langsung di halaman ini (tidak pindah tab) - bisa ganti "
                       "timeframe/indikator langsung di dalam chart-nya.")
            sh, sl_pts = ind.find_swing_points(df_full, order=3)
            swing_df = ind.classify_swings(sh, sl_pts)
        else:
            # ===== Grafik full-width (Plotly + Donchian + MA + Swing HL) =====
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                name=pilih,
            ))
            ma_colors = {5: "#facc15", 20: "#38bdf8", 50: "#a78bfa"}
            for p, c in ma_colors.items():
                if len(df_full) >= p:
                    ma_line = df_full["Close"].rolling(p).mean().tail(90)
                    fig.add_trace(go.Scatter(x=ma_line.index, y=ma_line, mode="lines",
                                              name=f"MA{p}", line=dict(width=1.4, color=c)))

            fig.add_hline(y=row["Donchian High"], line_dash="dash", line_color="#22c55e",
                          annotation_text=f"Donchian High {int(donchian_lb)}D")
            fig.add_hline(y=row["Donchian Low"], line_dash="dash", line_color="#ef4444",
                          annotation_text=f"Donchian Low {int(donchian_lb)}D")

            sh, sl_pts = ind.find_swing_points(df_full, order=3)
            swing_df = ind.classify_swings(sh, sl_pts)
            swing_recent = swing_df[swing_df["Tanggal"] >= df.index.min()]
            for _, sp in swing_recent.iterrows():
                color = "#22c55e" if sp["Label"] in ("HH", "HL") else "#ef4444"
                fig.add_annotation(x=sp["Tanggal"], y=sp["Harga"], text=sp["Label"],
                                    showarrow=True, arrowhead=1, arrowcolor=color,
                                    font=dict(color=color, size=10),
                                    ay=-25 if sp["Tipe"] == "H" else 25)

            fig.update_layout(
                height=520, template="plotly_dark", xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=30, b=10),
                title=f"{pilih} — {row['Nama']}",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

        cols = st.columns(4)
        cols[0].metric("Harga", f"Rp{row['Harga']:,.0f}", f"{row['Perubahan %']*100:+.2f}%")
        cols[1].metric("Signal", row["Signal"])
        cols[2].metric("Score", int(row["Score"]))
        cols[3].metric("Breakout", row["Status Breakout"])

        st.divider()

        # ===== Panel MA + Technical Indicators, full-width DI BAWAH grafik =====
        if len(df_full) >= 50:
            ma_table, ma_sum = ind.moving_averages_panel(df_full)
            ti_table, ti_sum = ind.technical_indicators_panel(df_full)
            score = ind.smart_score(ma_sum, ti_sum)
            overall = ind.overall_summary(ma_sum, ti_sum)
            badge_class = {"Buy": "badge-buy", "Sell": "badge-sell", "Neutral": "badge-neutral"}[overall]

            sc1, sc2 = st.columns([1, 3])
            with sc1:
                st.metric("Smart Score", f"{score}/100")
            with sc2:
                st.markdown(f"**Summary** &nbsp; <span class='{badge_class}'>{overall}</span>",
                             unsafe_allow_html=True)
                st.caption(
                    f"Moving Averages: **{ma_sum['overall']}** (Buy {ma_sum['buy']} · Sell {ma_sum['sell']}) &nbsp;·&nbsp; "
                    f"Technical Indicators: **{ti_sum['overall']}** "
                    f"(Buy {ti_sum['buy']} · Neutral {ti_sum['neutral']} · Sell {ti_sum['sell']})"
                )

            def _color_action(val):
                color = {"Buy": "#16a34a", "Sell": "#dc2626", "Neutral": "#6b7280"}.get(val, "")
                return f"background-color:{color}; color:white; font-weight:600;" if color else ""

            def _color_combined(val):
                val = str(val)
                if val.endswith("Buy"):
                    color = "#16a34a"
                elif val.endswith("Sell"):
                    color = "#dc2626"
                elif val.endswith("Neutral"):
                    color = "#6b7280"
                else:
                    return ""
                return f"background-color:{color}; color:white; font-weight:600;"

            def _style_table(df_in, subset_cols, color_fn=_color_action):
                styler = df_in.style
                if hasattr(styler, "map"):  # pandas >= 2.1
                    return styler.map(color_fn, subset=subset_cols)
                return styler.applymap(color_fn, subset=subset_cols)  # pandas lama

            mcol, tcol = st.columns(2)
            with mcol:
                st.markdown("**Moving Averages**")
                st.dataframe(
                    _style_table(ma_table[["MA", "Simple", "Exponential"]], ["Simple", "Exponential"], _color_combined),
                    use_container_width=True, hide_index=True, height=250,
                )
            with tcol:
                st.markdown("**Technical Indicators**")
                st.dataframe(
                    _style_table(ti_table, ["Action"], _color_action),
                    use_container_width=True, hide_index=True, height=340,
                )
        else:
            st.info("Panel MA/Technical Indicators butuh minimal 50 hari data historis "
                    "(saat ini baru tersedia sebagian) - akan lengkap otomatis saat data historis bertambah.")

        st.markdown("**Swing High/Low Terakhir**")
        if not swing_df.empty:
            st.dataframe(
                swing_df.tail(6).sort_values("Tanggal", ascending=False),
                use_container_width=True, hide_index=True, height=210,
            )
        else:
            st.caption("Belum ada swing point terdeteksi pada rentang data ini.")
    else:
        st.info("Data grafik untuk saham ini belum tersedia di batch saat ini.")

# ---------------- TAB 4: Jurnal Backtest (Google Sheets) ----------------
with t_backtest:
    if not gj.is_configured():
        st.warning(
            "Jurnal backtest belum terhubung ke Google Sheets. Isi `gcp_service_account` dan "
            "`GOOGLE_SHEET_ID` di Settings > Secrets. Langkah lengkap ada di README bagian "
            "'Setup Google Sheets untuk Jurnal Backtest'."
        )
    else:
        day_tipe = classify_daytrading_tipe()
        st.caption(f"Waktu sekarang WIB terdeteksi sebagai tipe **{day_tipe}** untuk Day Trading "
                   f"({'Beli Pagi, rencana Jual Sore' if day_tipe=='BPJS' else 'Beli Sore, rencana Jual besok Pagi'}).")
        colb1, colb2, colb3 = st.columns(3)
        with colb1:
            if st.button(f"🟢 Buka Posisi Day Trading ({day_tipe})", use_container_width=True):
                cands_day = build_trade_candidates(table, price_data, int(donchian_lb_day), min_rr, top_n=10)
                with st.spinner("Membuka posisi Day Trading..."):
                    opened = gj.open_positions_from_candidates(cands_day, day_tipe)
                if opened:
                    st.success(f"Dibuka: {', '.join(opened)}")
                else:
                    st.info("Tidak ada posisi baru dibuka.")
        with colb2:
            if st.button("🟢 Buka Posisi Swing Trading", use_container_width=True):
                cands_swing = build_trade_candidates(table, price_data, int(donchian_lb), min_rr, top_n=10)
                with st.spinner("Membuka posisi Swing Trading..."):
                    opened = gj.open_positions_from_candidates(cands_swing, "SWING")
                if opened:
                    st.success(f"Dibuka: {', '.join(opened)}")
                else:
                    st.info("Tidak ada posisi baru dibuka.")
        with colb3:
            if st.button("🔴 Cek TP/SL & Force-Sell", use_container_width=True):
                price_lookup = dict(zip(table["Kode"], table["Harga"]))
                with st.spinner("Mengecek posisi OPEN (TP/SL/waktu force-sell)..."):
                    closed = gj.auto_close_positions(price_lookup)
                if closed:
                    st.success(f"Ditutup: {', '.join(closed)}")
                else:
                    st.info("Belum ada yang perlu ditutup.")

        st.divider()
        positions = gj.load_positions()
        stats = gj.summarize(positions)
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Posisi", stats["total"])
        s2.metric("Sedang OPEN", stats["open"])
        s3.metric("WIN", stats["win"])
        s4.metric("LOSS", stats["loss"])
        s5.metric("Win Rate", f"{stats['winrate']:.1f}%")

        st.dataframe(positions, use_container_width=True, hide_index=True, height=420)
        st.caption(
            "Aturan force-sell otomatis: SWING maksimal 10 hari, BPJS maksimal 1 hari, BSJP maksimal 2 hari "
            "kalau belum kena TP/SL. Auto-BUY & Auto-SELL tidak berjalan sendiri di background - tekan tombol "
            "di atas tiap buka dashboard, atau jadwalkan lewat Google Apps Script trigger harian."
        )

# ---------------- TAB 5: Top 10 Day Trading & Swing Trading (RR > min_rr) ----------------
with t_top10:
    st.caption(f"Entry = harga sekarang · Stop Loss = Donchian Low (struktural) · "
               f"Target = proyeksi measured-move dari lebar channel Donchian · hanya RR ≥ {min_rr:.1f}:1")

    day_tipe = classify_daytrading_tipe()
    st.subheader(f"⚡ Top 10 Day Trading (Donchian {int(donchian_lb_day)} hari) — tipe {day_tipe}")
    cands_day = build_trade_candidates(table, price_data, int(donchian_lb_day), min_rr, top_n=10)
    if cands_day.empty:
        st.info("Tidak ada kandidat Day Trading yang lolos RR minimum saat ini. Coba turunkan Min. RR di sidebar.")
    else:
        show_day = cands_day.copy()
        show_day["Nilai Transaksi"] = show_day["Nilai Transaksi"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        show_day = show_day.drop(columns=["Chart"], errors="ignore")
        dataframe_with_chart(show_day, kode_col="Saham", height=400, key="df_top10_day")
        st.download_button(
            "⬇️ Download CSV", show_day.to_csv(index=False).encode("utf-8"),
            file_name=f"top10_daytrading_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
            key="dl_day",
        )

    st.divider()
    st.subheader(f"🌊 Top 10 Swing Trading (Donchian {int(donchian_lb)} hari)")
    cands_swing = build_trade_candidates(table, price_data, int(donchian_lb), min_rr, top_n=10)
    if cands_swing.empty:
        st.info("Tidak ada kandidat Swing Trading yang lolos RR minimum saat ini. Coba turunkan Min. RR di sidebar.")
    else:
        show_swing = cands_swing.copy()
        show_swing["Nilai Transaksi"] = show_swing["Nilai Transaksi"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        show_swing = show_swing.drop(columns=["Chart"], errors="ignore")
        dataframe_with_chart(show_swing, kode_col="Saham", height=400, key="df_top10_swing")
        st.download_button(
            "⬇️ Download CSV", show_swing.to_csv(index=False).encode("utf-8"),
            file_name=f"top10_swing_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
            key="dl_swing",
        )

# ---------------- TAB 6: Kalkulator ----------------
with t_kalk:
    kalk_col1, kalk_col2 = st.columns(2)

    # ===== Kalkulator Profit Saham =====
    with kalk_col1:
        st.subheader("🧮 Kalkulator Profit Saham")
        st.caption("Hitung untung/rugi transaksi, termasuk komisi beli & jual.")

        pilih_isi = st.selectbox(
            "Isi harga otomatis dari saham (opsional)",
            options=[""] + table["Kode"].tolist(), key="kalk_profit_pilih",
            format_func=lambda k: "-- pilih manual --" if k == "" else k,
        )
        harga_acuan = float(table.loc[table["Kode"] == pilih_isi, "Harga"].values[0]) if pilih_isi else 0.0

        cp1, cp2 = st.columns(2)
        harga_beli_in = cp1.number_input("Harga Beli (Rp)", min_value=0.0, value=harga_acuan, step=1.0, key="hb")
        harga_jual_in = cp2.number_input("Harga Jual (Rp)", min_value=0.0,
                                          value=harga_acuan * 1.05 if harga_acuan else 0.0, step=1.0, key="hj")
        lot_in = st.number_input("Lot (1 lot = 100 lembar)", min_value=1, value=10, step=1, key="lot")
        cp3, cp4 = st.columns(2)
        komisi_beli_in = cp3.number_input("Komisi Beli (%)", min_value=0.0, value=0.15, step=0.01, key="kb",
                                           help="Umumnya 0.15%-0.19% tergantung broker.")
        komisi_jual_in = cp4.number_input("Komisi Jual (%)", min_value=0.0, value=0.25, step=0.01, key="kj",
                                           help="Umumnya 0.25%-0.29% (sudah termasuk pajak final penjualan 0.1%).")

        if st.button("Hitung Profit", type="primary", use_container_width=True):
            r = calc.profit_calculator(harga_beli_in, harga_jual_in, lot_in, komisi_beli_in, komisi_jual_in)
            rc1, rc2 = st.columns(2)
            rc1.metric("Total Beli", f"Rp{r['total_beli']:,.0f}")
            rc2.metric("Total Jual", f"Rp{r['total_jual']:,.0f}")
            rc3, rc4 = st.columns(2)
            rc3.metric("Total Untung/Rugi", f"Rp{r['untung_rugi_rp']:,.0f}")
            rc4.metric("Total Untung/Rugi (%)", f"{r['untung_rugi_pct']:+.2f}%")
            if r["bep"]:
                st.info(f"💡 **Break Even Price**: Rp{r['bep']:,.2f} — harga jual minimum supaya impas "
                        f"(sudah memperhitungkan komisi beli & jual).")

    # ===== Kalkulator Manajemen Risiko =====
    with kalk_col2:
        st.subheader("🛡️ Kalkulator Manajemen Risiko")
        st.caption("Hitung ukuran posisi ideal berdasar modal & toleransi risiko.")

        pilih_isi2 = st.selectbox(
            "Isi harga saham otomatis (opsional)",
            options=[""] + table["Kode"].tolist(), key="kalk_risk_pilih",
            format_func=lambda k: "-- pilih manual --" if k == "" else k,
        )
        harga_saham_default = float(table.loc[table["Kode"] == pilih_isi2, "Harga"].values[0]) if pilih_isi2 else 0.0

        modal_in = st.number_input("Total Modal (Rp)", min_value=0.0, value=10_000_000.0, step=500_000.0, key="modal")
        resiko_in = st.number_input("Resiko per Transaksi (%)", min_value=0.1, value=1.0, step=0.1, key="resiko",
                                     help="Berapa % dari modal yang rela hilang kalau kena Stop Loss. Umumnya 1-2%.")
        sl_in = st.number_input("Persen Stop Loss (%)", min_value=0.1, value=5.0, step=0.5, key="slpct")
        rr_in = st.number_input("Risk Reward Ratio", min_value=0.5, value=2.0, step=0.5, key="rrin")
        harga_saham_in = st.number_input("Harga Saham (Rp) - opsional, untuk hasil dalam LOT",
                                          min_value=0.0, value=harga_saham_default, step=1.0, key="hs")

        if st.button("Hitung Manajemen Risiko", type="primary", use_container_width=True):
            r2 = calc.risk_management_calculator(modal_in, resiko_in, sl_in, rr_in,
                                                   harga_saham_in if harga_saham_in > 0 else None)
            if "error" in r2:
                st.error(r2["error"])
            else:
                if r2["dibatasi_modal"]:
                    st.warning("⚠️ Ukuran posisi ideal melebihi modal - dibatasi otomatis ke total modal yang ada.")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Resiko (Rp)", f"Rp{r2['resiko_rp']:,.0f}")
                rc2.metric("Maksimal Beli (Rp)", f"Rp{r2['maksimal_beli_rp']:,.0f}")
                rc3.metric("Target Profit (%)", f"{r2['take_profit_pct']:.1f}%")
                if "lot" in r2:
                    rc4, rc5, rc6 = st.columns(3)
                    rc4.metric("Jumlah Lot", f"{r2['lot']} lot ({r2['lembar']:,} lembar)")
                    rc5.metric("Stop Loss (Rp)", f"Rp{r2['stop_loss_price']:,.0f}")
                    rc6.metric("Take Profit (Rp)", f"Rp{r2['take_profit_price']:,.0f}")
                    st.caption(f"Total dana terpakai: Rp{r2['total_saham_rp']:,.0f} · "
                               f"Risiko aktual (sudah dibulatkan ke lot): Rp{r2['risiko_aktual_rp']:,.0f}")
                else:
                    st.caption("Isi 'Harga Saham' di atas untuk mendapat hasil dalam satuan LOT, "
                               "harga Stop Loss & Take Profit riil.")

    st.divider()
    st.subheader("📉📈 Kalkulator Average Down / Average Up")
    st.caption(
        "Average Down = beli tambahan saat harga TURUN untuk menurunkan harga rata-rata. "
        "Average Up = beli tambahan saat harga NAIK (menambah posisi pemenang). "
        "Rumus tertimbang standar: Avg Baru = (Modal Awal + Modal Tambahan) / (Lot Awal + Lot Tambahan)."
    )
    avg_tab1, avg_tab2 = st.tabs(["🧮 Hitung Average", "🎯 Simulasi Lot Tambahan (target average)"])

    with avg_tab1:
        pilih_isi3 = st.selectbox(
            "Isi harga sekarang otomatis (opsional)", options=[""] + table["Kode"].tolist(),
            key="kalk_avg_pilih", format_func=lambda k: "-- pilih manual --" if k == "" else k,
        )
        harga_now = float(table.loc[table["Kode"] == pilih_isi3, "Harga"].values[0]) if pilih_isi3 else 0.0

        ac1, ac2 = st.columns(2)
        with ac1:
            st.markdown("**Posisi Awal (yang sudah dimiliki)**")
            harga_awal_in = st.number_input("Harga Beli Awal (Rp)", min_value=0.0, value=1000.0, step=1.0, key="avg_ha")
            lot_awal_in = st.number_input("Lot Awal", min_value=0.0, value=10.0, step=1.0, key="avg_la")
        with ac2:
            st.markdown("**Pembelian Tambahan**")
            harga_tambah_in = st.number_input("Harga Beli Tambahan (Rp)", min_value=0.0,
                                               value=harga_now if harga_now else 900.0, step=1.0, key="avg_ht")
            lot_tambah_in = st.number_input("Lot Tambahan", min_value=0.0, value=10.0, step=1.0, key="avg_lt")

        if st.button("Hitung Average", type="primary", use_container_width=True, key="btn_avg"):
            ra = calc.average_calculator(harga_awal_in, lot_awal_in, harga_tambah_in, lot_tambah_in)
            if "error" in ra:
                st.error(ra["error"])
            else:
                badge = "🟢 AVERAGE DOWN" if ra["tipe"] == "AVERAGE DOWN" else (
                    "🔴 AVERAGE UP" if ra["tipe"] == "AVERAGE UP" else "⚪ HARGA SAMA")
                st.markdown(f"**{badge}**")
                rac1, rac2, rac3 = st.columns(3)
                rac1.metric("Harga Rata-Rata Baru", f"Rp{ra['avg_baru']:,.2f}", f"{ra['selisih_pct']:+.2f}%")
                rac2.metric("Total Lot", f"{ra['total_lot']:,.0f} lot")
                rac3.metric("Total Modal", f"Rp{ra['total_modal']:,.0f}")
                st.caption("Setelah average, harga saham cukup naik/turun ke angka Harga Rata-Rata Baru "
                           "di atas untuk balik modal (belum termasuk komisi transaksi).")

    with avg_tab2:
        st.caption("Isi target harga rata-rata yang diinginkan, kalkulator hitung berapa lot "
                   "tambahan yang dibutuhkan di harga tertentu untuk mencapainya.")
        sc1, sc2 = st.columns(2)
        with sc1:
            sim_harga_awal = st.number_input("Harga Beli Awal (Rp)", min_value=0.0, value=4500.0, step=1.0, key="sim_ha")
            sim_lot_awal = st.number_input("Lot Awal", min_value=0.0, value=10.0, step=1.0, key="sim_la")
        with sc2:
            sim_harga_tambah = st.number_input("Harga Beli Tambahan Rencana (Rp)", min_value=0.0,
                                                value=3700.0, step=1.0, key="sim_ht")
            sim_target_avg = st.number_input("Target Harga Rata-Rata (Rp)", min_value=0.0,
                                              value=4000.0, step=1.0, key="sim_ta")

        if st.button("Hitung Lot Tambahan", type="primary", use_container_width=True, key="btn_sim"):
            rs = calc.average_lot_simulator(sim_harga_awal, sim_lot_awal, sim_target_avg, sim_harga_tambah)
            if "error" in rs:
                st.error(rs["error"])
            else:
                rsc1, rsc2 = st.columns(2)
                rsc1.metric("Lot Tambahan Dibutuhkan", f"{rs['lot_tambahan']:,} lot")
                rsc2.metric("Modal Tambahan Dibutuhkan", f"Rp{rs['modal_tambahan_dibutuhkan']:,.0f}")
                st.caption(f"Hasil akhir: rata-rata jadi **Rp{rs['avg_hasil']:,.2f}** dengan total "
                           f"**{rs['total_lot_hasil']:,.0f} lot**.")

# ---------------- TAB 7: Performance (dihitung dari transaksi riil di sheet POSISI) ----------------
with t_perf:
    if not gj.is_configured():
        st.warning(
            "Performance dihitung dari transaksi yang tercatat di sheet POSISI (Google Sheets). "
            "Belum terhubung - isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets "
            "(lihat README bagian 'Setup Google Sheets')."
        )
    else:
        positions_perf = gj.load_positions()
        perf = gj.monthly_performance(positions_perf)

        if perf["n_closed"] == 0:
            st.info(
                "Belum ada transaksi yang CLOSE (WIN/LOSS/FORCE SELL) di sheet POSISI, jadi belum ada "
                "performance untuk ditampilkan. Begitu ada posisi yang tertutup (lewat tombol Auto-SELL "
                "di tab Jurnal Backtest), grafik ini otomatis terisi - tidak perlu sheet terpisah."
            )
        else:
            cum = perf["cumulative_pct"]
            cum_class = "month-value-pos" if cum >= 0 else "month-value-neg"
            st.markdown(f"""
            <div class="cumulative-box">
                <div class="cumulative-label">AKUMULASI PROFIT (SIGNAL STOCKS)</div>
                <div class="cumulative-value {cum_class}">{cum:+.2f}%</div>
                <div style="color:#9ca3af; font-size:0.85rem; margin-top:4px;">
                    Rata-rata {perf['avg_per_month']:+.2f}% / bulan · dari {perf['n_closed']} transaksi closed
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Profit per Bulan**")
            month_cols = st.columns(min(6, len(perf["monthly"])) or 1)
            for i, row in perf["monthly"].iterrows():
                col = month_cols[i % len(month_cols)]
                pos = row["Profit %"] >= 0
                card_cls = "month-card-pos" if pos else "month-card-neg"
                val_cls = "month-value-pos" if pos else "month-value-neg"
                bulan_label = pd.to_datetime(row["Bulan"] + "-01").strftime("%b %Y").upper()
                col.markdown(f"""
                <div class="month-card {card_cls}">
                    <div class="month-label">{bulan_label}</div>
                    <div class="{val_cls}">{row['Profit %']:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)

            st.divider()
            stats_perf = gj.summarize(positions_perf)
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Win Rate", f"{stats_perf['winrate']:.1f}%")
            p2.metric("Total WIN", stats_perf["win"])
            p3.metric("Total LOSS", stats_perf["loss"])
            p4.metric("Posisi OPEN", stats_perf["open"])

            st.markdown("**🏅 Transaksi Terbaik (Top 10)**")
            top_display = perf["top_trades"].copy()
            top_display["Profit %"] = top_display["Profit %"].map(lambda x: f"{x:+.2f}%")
            st.dataframe(top_display, use_container_width=True, hide_index=True)

            st.markdown("**📈 Kurva Ekuitas (Kumulatif)**")
            monthly_sorted = perf["monthly"].sort_values("Bulan").copy()
            monthly_sorted["Kumulatif %"] = monthly_sorted["Profit %"].cumsum()
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=monthly_sorted["Bulan"], y=monthly_sorted["Kumulatif %"],
                mode="lines+markers", line=dict(color="#4ade80", width=2.5),
                fill="tozeroy", fillcolor="rgba(74,222,128,0.12)",
            ))
            fig_eq.update_layout(
                height=280, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="Akumulasi Profit (%)",
            )
            st.plotly_chart(fig_eq, use_container_width=True)

            st.caption(
                "Profit per bulan = jumlah P&L(%) semua transaksi yang CLOSE di bulan itu (penjumlahan "
                "sederhana, bukan compounding riil) - dihitung langsung dari sheet POSISI, jadi selalu "
                "sinkron dengan jurnal transaksi tanpa perlu sheet terpisah."
            )

# ---------------- TAB 8: Jurnal Trading REAL (multi-sekuritas, transaksi uang beneran) ----------------
with t_real:
    st.caption(
        "Catatan transaksi UANG BENERAN Bro - terpisah total dari Jurnal Backtest (simulasi) supaya "
        "tidak tercampur. Tersimpan di sheet 'JURNAL_REAL' & 'SEKURITAS' (dibuat otomatis kalau belum ada)."
    )

    if not gj.is_configured():
        st.warning(
            "Jurnal Real butuh koneksi Google Sheets yang sama dengan Jurnal Backtest. Isi "
            "`gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets dulu "
            "(lihat README bagian 'Setup Google Sheets')."
        )
    else:
        sub1, sub2, sub3, sub4, sub5 = st.tabs(
            ["➕ Catat Trade", "🔓 Tutup Posisi", "📊 Performance Real", "⚙️ Sekuritas", "✏️ Edit/Hapus"]
        )

        # --- Catat trade baru ---
        with sub1:
            st.markdown("**Catat posisi baru (OPEN)**")
            brokers_df = rj.load_brokers()
            broker_options = brokers_df["Sekuritas"].tolist() if not brokers_df.empty else ["Lainnya"]

            fc1, fc2, fc3 = st.columns(3)
            tgl_entry = fc1.date_input("Tanggal Entry", value=datetime.now(), key="tgl_entry_rj")
            sekuritas_in = fc2.selectbox("Sekuritas", options=broker_options, key="sekuritas_rj")
            saham_in = fc3.text_input("Kode Saham", key="saham_rj").upper()

            fc4, fc5 = st.columns(2)
            setup_in = fc4.selectbox("Setup", options=rj.SETUP_OPTIONS, key="setup_rj")
            lot_in2 = fc5.number_input("Lot", min_value=1, value=10, step=1, key="lot_rj")

            fc6, fc7, fc8 = st.columns(3)
            entry_in2 = fc6.number_input("Entry (Rp)", min_value=0.0, step=1.0, key="entry_rj")
            sl_in2 = fc7.number_input("Stop Loss (Rp)", min_value=0.0, step=1.0, key="sl_rj")
            target_in2 = fc8.number_input("Target (Rp)", min_value=0.0, step=1.0, key="target_rj")

            catatan_in = st.text_area("Catatan (opsional)", height=70, key="catatan_rj")

            if st.button("💾 Simpan Trade (OPEN)", type="primary", key="btn_open_rj"):
                if not saham_in or entry_in2 <= 0:
                    st.error("Kode saham dan Entry wajib diisi.")
                else:
                    no = rj.open_trade(
                        tgl_entry.strftime("%Y-%m-%d"), sekuritas_in, saham_in, setup_in,
                        entry_in2, sl_in2, target_in2, lot_in2, catatan_in,
                    )
                    st.success(f"Trade #{no} ({saham_in}) berhasil dicatat sebagai OPEN.")

        # --- Tutup posisi ---
        with sub2:
            trades_now = rj.load_trades()
            open_trades = trades_now[trades_now["Status"] == "OPEN"] if not trades_now.empty else pd.DataFrame()
            if open_trades.empty:
                st.info("Tidak ada posisi OPEN saat ini.")
            else:
                st.markdown("**Posisi yang masih terbuka**")
                st.dataframe(
                    open_trades[["No", "Tanggal Entry", "Sekuritas", "Saham", "Setup",
                                  "Entry (Rp)", "Stop Loss (Rp)", "Target (Rp)", "Lot"]],
                    use_container_width=True, hide_index=True,
                )
                pilih_no = st.selectbox(
                    "Pilih nomor trade yang mau ditutup",
                    options=open_trades["No"].tolist(),
                    format_func=lambda n: f"#{n} - {open_trades.loc[open_trades['No']==n,'Saham'].values[0]}",
                    key="pilih_no_rj",
                )
                cc1, cc2 = st.columns(2)
                tgl_exit_in = cc1.date_input("Tanggal Exit", value=datetime.now(), key="tgl_exit_rj")
                exit_price_in = cc2.number_input("Harga Exit (Rp)", min_value=0.0, step=1.0, key="exit_price_rj")
                if st.button("🔒 Tutup Posisi Ini", type="primary", key="btn_close_rj"):
                    if exit_price_in <= 0:
                        st.error("Harga Exit wajib diisi.")
                    else:
                        ok, msg = rj.close_trade(pilih_no, tgl_exit_in.strftime("%Y-%m-%d"), exit_price_in)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

        # --- Performance Real ---
        with sub3:
            trades_all = rj.load_trades()
            stats_rj = rj.compute_stats(trades_all)
            if stats_rj["total"] == 0:
                st.info("Belum ada trade tercatat. Mulai dari tab 'Catat Trade'.")
            else:
                r1, r2, r3 = st.columns(3)
                r1.metric("Win Rate", f"{stats_rj['winrate']:.1f}%")
                pf_display = "∞" if stats_rj["profit_factor"] == float("inf") else f"{stats_rj['profit_factor']:.2f}"
                r2.metric("Profit Factor", pf_display)
                r3.metric("Total Trade", f"{stats_rj['total']} ({stats_rj['win']}W · {stats_rj['loss']}L · {stats_rj['open']} OPEN)")

                r4, r5 = st.columns(2)
                r4.metric("Total Transaction Value", f"Rp{stats_rj['total_transaction_value']:,.0f}")
                r5.metric("Net P/L", f"Rp{stats_rj['net_pl']:,.0f}")

                r6, r7, r8, r9 = st.columns(4)
                ada_closed = (stats_rj["win"] + stats_rj["loss"]) > 0
                r6.metric("Max Profit", f"Rp{stats_rj['max_profit_rp']:,.0f}",
                          f"{stats_rj['max_profit_pct']:+.2f}%" if ada_closed else None)
                r7.metric("Max Loss", f"Rp{stats_rj['max_loss_rp']:,.0f}",
                          f"{stats_rj['max_loss_pct']:+.2f}%" if ada_closed else None)
                r8.metric("Avg. Profit", f"Rp{stats_rj['avg_profit_rp']:,.0f}" if ada_closed else "Belum ada data")
                r9.metric("Avg. Loss", f"Rp{stats_rj['avg_loss_rp']:,.0f}" if ada_closed else "Belum ada data")
                st.metric("Expectancy (rata-rata P/L per trade)", f"Rp{stats_rj['expectancy']:,.0f}")

                st.divider()
                pb1, pb2 = st.columns(2)
                with pb1:
                    st.markdown("**Performance per Sekuritas**")
                    st.dataframe(rj.performance_by_broker(trades_all), use_container_width=True, hide_index=True)
                with pb2:
                    st.markdown("**Performance per Setup**")
                    st.dataframe(rj.performance_by_setup(trades_all), use_container_width=True, hide_index=True)

                st.markdown("**🏅 Top Gainer per Saham**")
                top_gainer = rj.performance_by_stock(trades_all)
                if not top_gainer.empty:
                    tg_display = top_gainer.copy()
                    tg_display["Net P/L (Rp)"] = tg_display["Net P/L (Rp)"].map(lambda x: f"Rp{x:,.0f}")
                    tg_display["Rata-rata Return %"] = tg_display["Rata-rata Return %"].map(lambda x: f"{x:+.2f}%")
                    st.dataframe(tg_display, use_container_width=True, hide_index=True)
                else:
                    st.caption("Belum ada transaksi closed untuk dirangkum per saham.")

                eq_curve_rj = rj.equity_curve(trades_all)
                if not eq_curve_rj.empty:
                    st.markdown("**📈 Kurva Ekuitas (Kumulatif, Rp)**")
                    fig_rj = go.Figure()
                    fig_rj.add_trace(go.Scatter(
                        x=eq_curve_rj["Tanggal Exit"], y=eq_curve_rj["Kumulatif (Rp)"],
                        mode="lines+markers", line=dict(color="#38bdf8", width=2.5),
                        fill="tozeroy", fillcolor="rgba(56,189,248,0.12)",
                    ))
                    fig_rj.update_layout(height=300, template="plotly_dark",
                                          margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Kumulatif (Rp)")
                    st.plotly_chart(fig_rj, use_container_width=True)

                st.caption(
                    "💡 Untuk bandingkan Total Equity portofolio Bro (bukan cuma per-transaksi) dengan "
                    "pergerakan IHSG, lihat tab **📐 Equity** - itu memakai data equity riil per sekuritas, "
                    "lebih akurat daripada dihitung dari jurnal transaksi saja (karena ada faktor cash/uang "
                    "menganggur yang tidak tercatat di jurnal per-transaksi)."
                )

                st.markdown("**Riwayat Semua Trade**")
                st.dataframe(trades_all, use_container_width=True, hide_index=True, height=350)
                st.download_button(
                    "⬇️ Download CSV", trades_all.to_csv(index=False).encode("utf-8"),
                    file_name=f"jurnal_real_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
                    key="dl_jurnal_real",
                )

        # --- Kelola Sekuritas ---
        with sub4:
            st.markdown("**Daftar Sekuritas & Biaya Transaksi**")

            with st.expander("🧪 Tes Formula (klik untuk cek apakah kode yang aktif sudah benar)"):
                st.caption(
                    "Tes ini memanggil LANGSUNG fungsi dari file real_journal.py yang ter-deploy "
                    "(bukan hitung terpisah) - supaya benar-benar membuktikan versi kode yang aktif. "
                    "Contoh baku: Entry Rp458, Exit Rp494, Lot 10, fee 0.15%/0.25%. "
                    "Kalau kode yang aktif BENAR, hasilnya harus PROFIT +Rp34.078 (+7.44%)."
                )
                _t = rj._calculate_trade_result(458, 494, 10, 0.15, 0.25)
                _formula_ok = abs(_t["biaya"] - 1922) < 1
                tcol1, tcol2, tcol3 = st.columns(3)
                tcol1.metric("Biaya (harus Rp1.922)", f"Rp{_t['biaya']:,.0f}")
                tcol2.metric("Net P/L (harus +Rp34.078)", f"Rp{_t['net_pl']:,.0f}")
                tcol3.metric("Return % (harus +7.44%)", f"{_t['return_pct']:+.2f}%")
                if _formula_ok:
                    st.success(
                        "✅ BENAR - file real_journal.py yang aktif di deployment ini sudah versi yang "
                        "benar. Kalau trade real Bro masih salah, berarti itu trade LAMA yang perlu "
                        "di-edit ulang (bukan file kodenya lagi)."
                    )
                else:
                    st.error(
                        "❌ SALAH - file real_journal.py yang AKTIF DI DEPLOYMENT INI masih versi lama/"
                        "salah, walaupun mungkin sudah di-upload ulang. Coba: (1) hapus dulu file "
                        "real_journal.py di GitHub (jangan cuma edit/timpa), (2) upload file baru dari "
                        "awal, (3) di Streamlit Cloud, buka Manage app > titik tiga > Reboot app supaya "
                        "tidak ada versi lama yang ke-cache."
                    )
            st.caption("Tiap broker beda fee - isi sesuai yang tertera di aplikasi sekuritas Bro masing-masing.")
            brokers_now = rj.load_brokers()
            def _flag_high_fee(val):
                try:
                    return "background-color:#7f1d1d; color:white; font-weight:600;" if float(val) > 1.0 else ""
                except (ValueError, TypeError):
                    return ""
            styler_brokers = brokers_now.style
            fee_cols = ["Biaya Beli (%)", "Biaya Jual (%)"]
            if hasattr(styler_brokers, "map"):
                styler_brokers = styler_brokers.map(_flag_high_fee, subset=fee_cols)
            else:
                styler_brokers = styler_brokers.applymap(_flag_high_fee, subset=fee_cols)
            st.dataframe(styler_brokers, use_container_width=True, hide_index=True)
            if (pd.to_numeric(brokers_now["Biaya Beli (%)"], errors="coerce") > 1.0).any() or \
               (pd.to_numeric(brokers_now["Biaya Jual (%)"], errors="coerce") > 1.0).any():
                st.error(
                    "🚩 Ada sekuritas dengan fee di atas 1% (ditandai merah) - ini kemungkinan besar "
                    "salah input (mis. '15' padahal maksudnya '0.15'). Trade yang sudah dihitung pakai "
                    "fee salah ini perlu dikoreksi ulang lewat tab Edit/Hapus setelah fee-nya dibetulkan."
                )

            st.markdown("**Tambah / Update Sekuritas**")
            st.caption("⚠️ Isi dalam bentuk PERSEN kecil, mis. **0.15** untuk 0,15% (bukan ketik '15'). "
                       "Fee broker IDX pada umumnya 0,1%-0,3% - kalau lebih dari 1%, cek ulang dulu.")
            bc1, bc2, bc3 = st.columns(3)
            nama_broker_in = bc1.text_input("Nama Sekuritas", key="nama_broker_rj")
            biaya_beli_in2 = bc2.number_input("Biaya Beli (%)", min_value=0.0, max_value=5.0,
                                               value=0.15, step=0.01, key="bb_broker")
            biaya_jual_in2 = bc3.number_input("Biaya Jual (%)", min_value=0.0, max_value=5.0,
                                               value=0.25, step=0.01, key="bj_broker")
            if biaya_beli_in2 > 1.0 or biaya_jual_in2 > 1.0:
                st.warning(
                    f"Fee {biaya_beli_in2}% / {biaya_jual_in2}% terlihat sangat tinggi untuk broker IDX "
                    "(biasanya di bawah 0,3%). Kemungkinan Bro salah ketik (mis. '15' padahal maksud "
                    "'0.15'). Pastikan benar sebelum simpan."
                )
            if st.button("💾 Simpan Sekuritas", key="btn_save_broker"):
                if not nama_broker_in:
                    st.error("Nama sekuritas wajib diisi.")
                else:
                    rj.add_broker(nama_broker_in, biaya_beli_in2, biaya_jual_in2)
                    st.success(f"Sekuritas '{nama_broker_in}' disimpan.")

            st.divider()
            st.markdown("**Hapus Sekuritas**")
            brokers_for_delete = rj.load_brokers()
            if not brokers_for_delete.empty:
                dc1, dc2 = st.columns([3, 1])
                nama_hapus = dc1.selectbox(
                    "Pilih sekuritas yang mau dihapus", options=brokers_for_delete["Sekuritas"].tolist(),
                    key="pilih_hapus_broker",
                )
                konfirmasi_hapus_broker = dc2.checkbox("Yakin hapus?", key="konfirmasi_hapus_broker")
                if st.button("🗑️ Hapus Sekuritas", key="btn_delete_broker", disabled=not konfirmasi_hapus_broker):
                    ok_del, msg_del = rj.delete_broker(nama_hapus)
                    if ok_del:
                        st.success(msg_del)
                    else:
                        st.error(msg_del)
                st.caption(
                    "⚠️ Menghapus sekuritas tidak mengubah trade yang sudah tercatat memakai fee sekuritas "
                    "ini - trade lama tetap tersimpan seperti aslinya."
                )

        # --- Edit / Hapus (koreksi salah input) ---
        with sub5:
            st.caption("Salah input harga/lot/sekuritas? Pilih nomor trade di bawah, koreksi, lalu simpan. "
                       "Kalau memang batal dicatat sama sekali, pakai tombol Hapus.")
            trades_edit = rj.load_trades()
            if trades_edit.empty:
                st.info("Belum ada trade untuk diedit.")
            else:
                pilih_edit_no = st.selectbox(
                    "Pilih nomor trade",
                    options=trades_edit["No"].tolist(),
                    format_func=lambda n: f"#{n} - {trades_edit.loc[trades_edit['No']==n,'Saham'].values[0]} "
                                           f"({trades_edit.loc[trades_edit['No']==n,'Status'].values[0]})",
                    key="pilih_edit_no_rj",
                )
                row_edit = trades_edit[trades_edit["No"] == pilih_edit_no].iloc[0]
                broker_options_edit = rj.load_brokers()["Sekuritas"].tolist()
                sudah_closed = row_edit["Status"] != "OPEN"

                def _parse_tanggal_fleksibel(nilai, default=None):
                    """Coba baca tanggal dari beberapa format yang mungkin tersimpan dari data lama
                    (YYYY-MM-DD atau DD/MM/YYYY) - supaya data lama yang formatnya beda tetap kebaca,
                    bukan malah error. Selalu ditulis balik sebagai YYYY-MM-DD yang konsisten."""
                    nilai = str(nilai).strip()
                    if not nilai or nilai.lower() == "nan":
                        return default or datetime.now().date()
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                        try:
                            return datetime.strptime(nilai, fmt).date()
                        except ValueError:
                            continue
                    return default or datetime.now().date()

                ec1, ec2, ec3 = st.columns(3)
                e_tgl_entry_date = ec1.date_input(
                    "Tanggal Entry", value=_parse_tanggal_fleksibel(row_edit["Tanggal Entry"]), key="e_tgl",
                )
                e_tgl_entry = e_tgl_entry_date.strftime("%Y-%m-%d")
                idx_broker = broker_options_edit.index(row_edit["Sekuritas"]) if row_edit["Sekuritas"] in broker_options_edit else 0
                e_sekuritas = ec2.selectbox("Sekuritas", options=broker_options_edit, index=idx_broker, key="e_sek")
                e_saham = ec3.text_input("Kode Saham", value=str(row_edit["Saham"]), key="e_saham").upper()

                ec4, ec5 = st.columns(2)
                idx_setup = rj.SETUP_OPTIONS.index(row_edit["Setup"]) if row_edit["Setup"] in rj.SETUP_OPTIONS else 0
                e_setup = ec4.selectbox("Setup", options=rj.SETUP_OPTIONS, index=idx_setup, key="e_setup")
                e_lot = ec5.number_input("Lot", min_value=1.0, value=float(row_edit["Lot"] or 1), step=1.0, key="e_lot")

                ec6, ec7, ec8 = st.columns(3)
                e_entry = ec6.number_input("Entry (Rp)", min_value=0.0, value=float(row_edit["Entry (Rp)"] or 0), step=1.0, key="e_entry")
                e_sl = ec7.number_input("Stop Loss (Rp)", min_value=0.0, value=float(row_edit["Stop Loss (Rp)"] or 0), step=1.0, key="e_sl")
                e_target = ec8.number_input("Target (Rp)", min_value=0.0, value=float(row_edit["Target (Rp)"] or 0), step=1.0, key="e_target")

                e_catatan = st.text_area("Catatan", value=str(row_edit["Catatan"] or ""), height=70, key="e_catatan")

                st.markdown("**Data Exit** (centang 'Masih OPEN' kalau posisi ini belum/tidak jadi ditutup)")
                masih_open = st.checkbox("Masih OPEN (belum exit)", value=not sudah_closed, key="e_masih_open")
                ec9, ec10 = st.columns(2)
                if masih_open:
                    ec9.date_input("Tanggal Exit", value=datetime.now().date(), disabled=True, key="e_tgl_exit_disabled")
                    e_tgl_exit = ""
                    ec10.number_input("Harga Exit (Rp)", value=0.0, disabled=True, key="e_exit_price_disabled")
                    e_exit_price = 0.0
                else:
                    e_tgl_exit_date = ec9.date_input(
                        "Tanggal Exit",
                        value=_parse_tanggal_fleksibel(row_edit["Tanggal Exit"], default=datetime.now().date()),
                        key="e_tgl_exit",
                    )
                    e_tgl_exit = e_tgl_exit_date.strftime("%Y-%m-%d")
                    e_exit_price = ec10.number_input("Harga Exit (Rp)", min_value=0.0,
                                                      value=float(row_edit["Exit (Rp)"] or 0), step=1.0, key="e_exit_price")

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("💾 Simpan Perubahan", type="primary", use_container_width=True, key="btn_edit_rj"):
                        if not e_saham or e_entry <= 0:
                            st.error("Kode saham dan Entry wajib diisi.")
                        else:
                            ok, msg = rj.edit_trade(
                                pilih_edit_no, e_tgl_entry, e_sekuritas, e_saham, e_setup,
                                e_entry, e_sl, e_target, e_lot, e_catatan,
                                tanggal_exit=e_tgl_exit if e_exit_price > 0 else "",
                                exit_price=e_exit_price if e_exit_price > 0 else None,
                            )
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                with bcol2:
                    if st.button("🗑️ Hapus Trade Ini", use_container_width=True, key="btn_delete_rj"):
                        st.session_state["confirm_delete_rj"] = pilih_edit_no

                if st.session_state.get("confirm_delete_rj") == pilih_edit_no:
                    st.warning(f"Yakin mau hapus trade #{pilih_edit_no} ({row_edit['Saham']})? Tidak bisa dibatalkan.")
                    yes_col, no_col = st.columns(2)
                    if yes_col.button("Ya, hapus", type="primary", key="btn_confirm_delete_rj"):
                        ok, msg = rj.delete_trade(pilih_edit_no)
                        del st.session_state["confirm_delete_rj"]
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    if no_col.button("Batal", key="btn_cancel_delete_rj"):
                        del st.session_state["confirm_delete_rj"]
                        st.rerun()

# ---------------- TAB: Equity (snapshot modal per sekuritas + perbandingan IHSG) ----------------
with t_equity:
    if not gj.is_configured():
        st.warning(
            "Equity Tracking butuh koneksi Google Sheets yang sama dengan Jurnal Real/Backtest. "
            "Isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets."
        )
    else:
        sub_ringkasan, sub_catat, sub_riwayat = st.tabs(["📊 Ringkasan", "➕ Catat Snapshot", "📋 Riwayat"])

        equity_df = eq.load_equity()

        # ===== Sub-tab: Ringkasan =====
        with sub_ringkasan:
            if equity_df.empty:
                st.info(
                    "Belum ada data equity. Isi snapshot pertama di tab 'Catat Snapshot' - "
                    "ambil angkanya dari aplikasi sekuritas Bro masing-masing (Total Equity, Cash, "
                    "Invested), tidak bisa dihitung otomatis karena Yahoo Finance tidak tahu isi RDN Bro."
                )
            else:
                total_series = eq.total_equity_over_time(equity_df)
                latest_total = total_series["Total Equity (Rp)"].iloc[-1] if not total_series.empty else 0
                first_total = total_series["Total Equity (Rp)"].iloc[0] if not total_series.empty else 0
                total_return = ((latest_total / first_total - 1) * 100) if first_total > 0 else 0

                ec1, ec2, ec3 = st.columns(3)
                ec1.metric("Total Equity (Semua Sekuritas)", f"Rp{latest_total:,.0f}")
                ec2.metric("Return Sejak Snapshot Pertama", f"{total_return:+.2f}%")
                ec3.metric("Jumlah Sekuritas Aktif", equity_df["Sekuritas"].nunique())

                st.markdown("**📈 Kurva Total Equity**")
                fig_eq2 = go.Figure()
                fig_eq2.add_trace(go.Scatter(
                    x=total_series["Tanggal"], y=total_series["Total Equity (Rp)"],
                    mode="lines+markers", line=dict(color="#4ade80", width=2.5),
                    fill="tozeroy", fillcolor="rgba(74,222,128,0.12)", name="Total Equity",
                ))
                fig_eq2.update_layout(height=300, template="plotly_dark",
                                       margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Rp")
                st.plotly_chart(fig_eq2, use_container_width=True)

                st.markdown("**⚖️ Portofolio vs IHSG (Return %)**")
                with st.spinner("Mengambil data IHSG..."):
                    ihsg_df = fetch_ihsg_history(period="1y")
                if ihsg_df.empty:
                    st.caption("Data IHSG sedang tidak bisa diambil - coba refresh beberapa saat lagi.")
                else:
                    port_ret = eq.portfolio_return_pct(total_series)
                    ihsg_ret = ihsg_df[["Close"]].copy()
                    if ihsg_ret.index.tz is not None:  # jaga-jaga kalau yfinance kembalikan index tz-aware
                        ihsg_ret.index = ihsg_ret.index.tz_localize(None)
                    ihsg_ret["Return %"] = (ihsg_ret["Close"] / ihsg_ret["Close"].iloc[0] - 1) * 100
                    # potong data IHSG mulai dari tanggal snapshot equity pertama Bro, biar adil dibandingkan
                    tgl_awal = port_ret["Tanggal"].min()
                    ihsg_ret = ihsg_ret[ihsg_ret.index >= tgl_awal]
                    if not ihsg_ret.empty:
                        ihsg_ret["Return %"] = (ihsg_ret["Close"] / ihsg_ret["Close"].iloc[0] - 1) * 100

                    fig_cmp = go.Figure()
                    fig_cmp.add_trace(go.Scatter(
                        x=port_ret["Tanggal"], y=port_ret["Return %"],
                        mode="lines+markers", name="Portofolio Saya", line=dict(color="#4ade80", width=2.5),
                    ))
                    fig_cmp.add_trace(go.Scatter(
                        x=ihsg_ret.index, y=ihsg_ret["Return %"],
                        mode="lines", name="IHSG", line=dict(color="#a78bfa", width=2),
                    ))
                    fig_cmp.update_layout(
                        height=340, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10),
                        yaxis_title="Return (%)", legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig_cmp, use_container_width=True)
                    ihsg_return_now = ihsg_ret["Return %"].iloc[-1] if not ihsg_ret.empty else 0
                    selisih = total_return - ihsg_return_now
                    warna_selisih = "🟢" if selisih >= 0 else "🔴"
                    st.caption(f"Portofolio Bro: {total_return:+.2f}% · IHSG periode sama: {ihsg_return_now:+.2f}% "
                               f"· Selisih: {warna_selisih} {selisih:+.2f}% dibanding pasar")

                st.divider()
                st.markdown("**🏦 Equity per Sekuritas (Snapshot Terbaru)**")
                latest_broker = eq.latest_per_sekuritas(equity_df)
                if not latest_broker.empty:
                    bc1, bc2 = st.columns([1.3, 1])
                    with bc1:
                        show_broker_eq = latest_broker[["Sekuritas", "Tanggal", "Total Equity (Rp)", "Cash (Rp)",
                                                         "Invested (Rp)", "Max Risk/Trade (%)", "Max Position/Stock (%)"]]
                        st.dataframe(show_broker_eq, use_container_width=True, hide_index=True)
                    with bc2:
                        fig_pie = go.Figure(data=[go.Pie(
                            labels=latest_broker["Sekuritas"],
                            values=pd.to_numeric(latest_broker["Total Equity (Rp)"], errors="coerce"),
                            hole=0.5,
                        )])
                        fig_pie.update_layout(height=260, template="plotly_dark",
                                               margin=dict(l=10, r=10, t=10, b=10),
                                               showlegend=True)
                        st.plotly_chart(fig_pie, use_container_width=True)

        # ===== Sub-tab: Catat Snapshot =====
        with sub_catat:
            st.caption(
                "Isi angka ini dari aplikasi sekuritas Bro (halaman Portfolio/RDN) - Total Equity = "
                "Cash + nilai saham yang dipegang saat ini. Max Risk/Trade & Max Position/Stock adalah "
                "BATAS yang Bro tetapkan sendiri untuk manajemen risiko (bukan hasil hitungan otomatis)."
            )
            broker_options_eq = rj.load_brokers()["Sekuritas"].tolist()
            if not broker_options_eq:
                st.warning("Belum ada sekuritas terdaftar - tambahkan dulu di tab Jurnal Real > Sekuritas.")
            else:
                sc1, sc2 = st.columns(2)
                s_tanggal = sc1.text_input("Tanggal (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d"), key="eq_tgl")
                s_sekuritas = sc2.selectbox("Sekuritas", options=broker_options_eq, key="eq_sek")

                sc3, sc4, sc5 = st.columns(3)
                s_total_equity = sc3.number_input("Total Equity (Rp)", min_value=0.0, step=100000.0, key="eq_total")
                s_cash = sc4.number_input("Cash (Rp)", min_value=0.0, step=100000.0, key="eq_cash")
                s_invested = sc5.number_input("Invested (Rp)", min_value=0.0, step=100000.0, key="eq_invested")

                if s_total_equity > 0 and abs(s_total_equity - (s_cash + s_invested)) > 1:
                    st.caption(f"ℹ️ Cash + Invested = Rp{s_cash + s_invested:,.0f}, beda dengan Total Equity "
                               f"yang diisi (Rp{s_total_equity:,.0f}) - tidak masalah kalau memang beda "
                               f"(mis. ada dividen belum dicairkan), tapi cek ulang kalau ini tidak disengaja.")

                sc6, sc7 = st.columns(2)
                s_max_risk = sc6.number_input("Max Risk/Trade (%)", min_value=0.0, value=2.0, step=0.5, key="eq_maxrisk",
                                               help="Batas maksimal risiko yang rela ditanggung per transaksi, dari Total Equity.")
                s_max_pos = sc7.number_input("Max Position/Stock (%)", min_value=0.0, value=20.0, step=1.0, key="eq_maxpos",
                                              help="Batas maksimal alokasi ke satu saham, dari Total Equity.")

                if st.button("💾 Simpan Snapshot", type="primary", key="btn_save_equity"):
                    if s_total_equity <= 0:
                        st.error("Total Equity wajib diisi lebih dari 0.")
                    else:
                        ok, msg = eq.add_equity_snapshot(
                            s_tanggal, s_sekuritas, s_total_equity, s_cash, s_invested, s_max_risk, s_max_pos
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

        # ===== Sub-tab: Riwayat =====
        with sub_riwayat:
            if equity_df.empty:
                st.info("Belum ada riwayat snapshot.")
            else:
                st.dataframe(
                    equity_df.sort_values("Tanggal", ascending=False),
                    use_container_width=True, hide_index=True, height=400,
                )
                st.download_button(
                    "⬇️ Download CSV", equity_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"equity_log_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
                )

                st.divider()
                st.markdown("**🗑️ Hapus Snapshot**")
                del1, del2 = st.columns(2)
                del_tgl = del1.selectbox("Tanggal", options=sorted(equity_df["Tanggal"].unique(), reverse=True), key="del_eq_tgl")
                opsi_broker_del = equity_df[equity_df["Tanggal"] == del_tgl]["Sekuritas"].tolist()
                del_sek = del2.selectbox("Sekuritas", options=opsi_broker_del, key="del_eq_sek")
                if st.button("Hapus Snapshot Ini", key="btn_del_equity"):
                    ok, msg = eq.delete_equity_row(del_tgl, del_sek)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

st.divider()
st.caption(
    "⚠️ Data diambil dari Yahoo Finance (yfinance), bukan API resmi - bisa berhenti/berubah sewaktu-waktu. "
    "Bukan rekomendasi keuangan. Selalu lakukan riset & kelola risiko sendiri."
)
