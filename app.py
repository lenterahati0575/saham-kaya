import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from screener import (DEFAULT_PARAMS, load_ticker_universe, fetch_price_history, build_screener_table,
                      build_trade_candidates, classify_daytrading_tipe, fetch_ihsg_history, market_regime,
                      _donchian_levels)
from telegram_notify import send_telegram_message, format_watchlist_message
import gsheet_journal as gj
import indicators as ind
import calculators as calc
import sectors as sec
import real_journal as rj
import equity as eq

st.set_page_config(page_title="IDX Screener Dashboard", page_icon="📈", layout="wide")

def _check_auth() -> bool:
    app_password = st.secrets.get("APP_PASSWORD", "")
    if not app_password:
        st.warning("⚠️ Dashboard ini belum terkunci. `APP_PASSWORD` belum diisi di Settings > Secrets.")
        return True
    if st.session_state.get("_authenticated", False):
        return True
    st.title("🔒 IDX Screener Dashboard")
    st.caption("Dashboard ini berisi data trading pribadi. Masukkan password untuk melanjutkan.")
    with st.form("_login_form"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Masuk", type="primary")
    if submitted:
        if pw == app_password:
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("Password salah.")
    return False

if not _check_auth():
    st.stop()

components.html("""
<script>
(function() {
try {
const doc = window.parent.document;
if (!window.parent.__autoSelectNumberInputs) {
window.parent.__autoSelectNumberInputs = true;
doc.addEventListener('focusin', function(e) {
if (e.target && e.target.tagName === 'INPUT' && e.target.type === 'number') {
e.target.select();
}
});
}
} catch (err) { }
})();
</script>
""", height=0)

def embed_tradingview_chart(kode: str, height: int = 520):
    src = (
        f"https://s.tradingview.com/widgetembed/?symbol=IDX%3A{kode}"
        f"&interval=D&theme=dark&style=1&locale=id&toolbar_bg=%230e1117"
        f"&hide_top_toolbar=0&allow_symbol_change=1&save_image=0"
    )
    html = f'<iframe src="{src}" width="100%" height="{height}" frameborder="0" allowtransparency="true" scrolling="no"></iframe>'
    components.html(html, height=height + 10)

def dataframe_with_chart(df_display, kode_col="Kode", height=460, key=None, column_config=None):
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
        st.caption("💡 Klik salah satu baris di tabel di atas untuk melihat chart TradingView langsung di sini.")

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
</style>
""", unsafe_allow_html=True)

st.title("📈 IDX Screener Dashboard")
st.caption("Data live Yahoo Finance · Gate likuiditas + Donchian 20D Breakout · Gratis & mobile-friendly")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Parameter Filter")
    min_vt = st.number_input("Min. Value Traded (Rp miliar/hari)", min_value=0.0, value=3.0, step=0.5)
    crash_veto = st.slider("Ambang Crash Veto (%)", min_value=-15, max_value=-1, value=-5) / 100
    donchian_lb = st.number_input("Donchian Lookback - Swing (hari bursa)", min_value=5, max_value=60, value=20)
    donchian_lb_day = st.number_input("Donchian Lookback - Day Trading (hari bursa)", min_value=3, max_value=30, value=10)
    min_rr = st.number_input("Minimum Risk:Reward (RR)", min_value=1.0, value=2.0, step=0.1)
    st.divider()
    st.subheader("Ambang Skor Sinyal")
    sb = st.number_input("Skor min. STRONG BUY", value=7)
    b = st.number_input("Skor min. BUY", value=4)
    s = st.number_input("Skor maks. SELL", value=-2)
    ss = st.number_input("Skor maks. STRONG SELL", value=-4)
    st.divider()
    n_scan = st.select_slider("Jumlah saham dipindai", options=[50, 100, 200, 400, 615], value=200)
    refresh = st.button("🔄 Refresh Data Live", use_container_width=True, type="primary")
    st.divider()
    aktifkan_sektor = st.checkbox("🏷️ Aktifkan Filter Sektor", value=False)
    st.divider()
    st.subheader("🌐 Kondisi Pasar (IHSG)")
    filter_market = st.checkbox("Sembunyikan kandidat BUY saat IHSG Bearish", value=False)

params = {
    "min_value_traded": min_vt * 1_000_000_000,
    "crash_veto": crash_veto,
    "donchian_lookback": int(donchian_lb),
    "score_strong_buy": sb, "score_buy": b, "score_sell": s, "score_strong_sell": ss,
}

# ---------------- Load & fetch ----------------
universe = load_ticker_universe()
tickers = universe["Kode"].tolist()[:int(n_scan)]

if refresh:
    st.cache_data.clear()

with st.spinner(f"Mengambil data live untuk {len(tickers)} saham..."):
    price_data = fetch_price_history(tickers)
    table = build_screener_table(price_data, universe, params)

if table.empty:
    st.warning("Belum ada data yang berhasil diambil.")
    st.stop()

if aktifkan_sektor:
    with st.spinner("Mengambil data sektor..."):
        sector_map = sec.fetch_sectors(table["Kode"].tolist())
        table["Sektor"] = table["Kode"].map(sector_map).fillna("TIDAK DIKETAHUI")
else:
    table["Sektor"] = None

st.caption(f"Terakhir refresh: {datetime.now().strftime('%d %b %Y, %H:%M')} · {len(table)}/{len(tickers)} saham")

# ---------------- Kondisi Pasar ----------------
ihsg_hist = fetch_ihsg_history()
regime = market_regime(ihsg_hist)
if regime["status"] == "BEARISH":
    st.error(f"📉 IHSG BEARISH (Close {regime['close']:,.0f} < MA50 {regime['ma']:,.0f})")
elif regime["status"] == "BULLISH":
    st.success(f"📈 IHSG BULLISH (Close {regime['close']:,.0f} > MA50 {regime['ma']:,.0f})")
market_ok = not (filter_market and regime["status"] == "BEARISH")

# ---------------- Kandidat trading ----------------
cands_day_all = build_trade_candidates(table, price_data, int(donchian_lb_day), min_rr, top_n=10)
cands_swing_all = build_trade_candidates(table, price_data, int(donchian_lb), min_rr, top_n=10)
if not market_ok:
    cands_day_all = cands_day_all.iloc[0:0]
    cands_swing_all = cands_swing_all.iloc[0:0]

# ---------------- Tabs ----------------
t_kandidat, t_semua, t_grafik, t_backtest, t_top10, t_real, t_equity, t_perf, t_kalk = st.tabs([
    "🏆 Kandidat Terbaik", " Semua Saham", "📉 Grafik Saham", "📒 Jurnal Backtest",
    "🎯 Top 10 Day/Swing", "💼 Jurnal Real", "💰 Equity", "🚀 Performance", "🧮 Kalkulator"
])

# ============================================================================
# TAB 1: KANDIDAT TERBAIK
# ============================================================================
with t_kandidat:
    picks = table[table["Signal"].isin(["STRONG BUY", "BUY"])].copy()
    if not market_ok:
        st.info("🚦 Kandidat BUY disembunyikan sementara karena IHSG Bearish.")
        picks = picks.iloc[0:0]
    if aktifkan_sektor and not picks.empty:
        sektor_pilih_1 = st.multiselect("🏷️ Filter Sektor", options=sorted(picks["Sektor"].dropna().unique().tolist()), key="sektor_tab1")
        if sektor_pilih_1:
            picks = picks[picks["Sektor"].isin(sektor_pilih_1)]

    # Hitung RR
    if not picks.empty:
        rr_data = []
        for _, row in picks.iterrows():
            kode = row["Kode"]
            df = price_data.get(kode)
            try:
                if df is not None and len(df) >= int(donchian_lb) + 2:
                    hist = df.iloc[-(int(donchian_lb) + 1) : -1]
                    dh, dl = float(hist["High"].max()), float(hist["Low"].min())
                    entry = float(row["Harga"])
                    sl_donchian = dl
                    ma20 = float(df["Close"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else dl
                    sl_max = entry * 0.90
                    sl_type = "Swing (max 10%)"
                    sl_candidates = [x for x in [sl_donchian, ma20, sl_max] if x < entry]
                    stop_loss = max(sl_candidates) if sl_candidates else sl_max
                    target = dh + (dh - dl)
                    risk = entry - stop_loss
                    reward = target - entry
                    rr = reward / risk if risk > 0 else 0
                    risk_pct = (risk / entry) * 100
                    rr_data.append({"Kode": kode, "RR": round(rr, 2), "Entry": round(entry, 0), "Target": round(target, 0), "Stop Loss": round(stop_loss, 0), "Risiko %": round(risk_pct, 1), "SL Type": sl_type})
                else:
                    rr_data.append({"Kode": kode, "RR": 0, "Entry": 0, "Target": 0, "Stop Loss": 0, "Risiko %": 0, "SL Type": ""})
            except Exception:
                rr_data.append({"Kode": kode, "RR": 0, "Entry": 0, "Target": 0, "Stop Loss": 0, "Risiko %": 0, "SL Type": ""})
        picks = picks.merge(pd.DataFrame(rr_data), on="Kode", how="left")

    # === FILTER INTERAKTIF ===
    if not picks.empty and "Rekomendasi" in picks.columns:
        st.markdown("###  Filter Trading")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            available_rec = sorted(picks["Rekomendasi"].dropna().unique().tolist())
            default_rec = [x for x in available_rec if "AVOID" not in x and "WAIT" not in x]
            if not default_rec:
                default_rec = available_rec
            
            rec_filter = st.multiselect(
                "1️⃣ Rekomendasi",
                options=available_rec,
                default=default_rec,
                help="Pilih gaya trading yang sesuai"
            )
            if rec_filter:
                picks = picks[picks["Rekomendasi"].isin(rec_filter)]
        
        with col_f2:
            if "Quality" in picks.columns:
                available_q = sorted(picks["Quality"].dropna().unique().tolist())
                default_q = [x for x in ["✅ HIGH", "⚠️ MODERATE"] if x in available_q]
                if not default_q:
                    default_q = available_q
                
                q_filter = st.multiselect(
                    "2️⃣ Quality Rating",
                    options=available_q,
                    default=default_q,
                    help="HIGH = paling aman, MODERATE = cukup baik"
                )
                if q_filter:
                    picks = picks[picks["Quality"].isin(q_filter)]
        
        with col_f3:
            use_rr_filter = st.checkbox(
                "Filter RR ≥ 2.0",
                value=False,
                help="Aktifkan untuk hanya tampilkan RR ≥ 2.0"
            )
            if use_rr_filter and "RR" in picks.columns:
                picks = picks[picks["RR"] >= 2.0]
                st.success("✅ Filter RR ≥ 2.0 aktif")
            elif "RR" in picks.columns:
                st.info("ℹ️ Menampilkan semua RR (aktifkan filter jika perlu)")
        
        # Panduan
        st.markdown("""
        <div style="background: #1f2937; padding: 12px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #16a34a;">
            <b>💡 Panduan Cuan Konsisten:</b><br>
            1. <b>Prioritas 1:</b> Quality = ✅ HIGH + RR ≥ 2.0 + SWING/DAY TRADE<br>
            2. <b>Prioritas 2:</b> Quality = ️ MODERATE + RR ≥ 1.5 + SWING TRADE<br>
            3. <b>Hindari:</b> RR < 1.0 atau AVOID<br>
            4. <b>Entry</b> di harga sekarang, pasang <b>Stop Loss</b> dan <b>Target</b> sesuai kolom. <b>JANGAN DILANGGAR!</b>
        </div>
        """, unsafe_allow_html=True)

    # Sorting
    if not picks.empty and "RR" in picks.columns:
        picks = picks.sort_values(["RR", "Quality Score"], ascending=[False, False])

    # Tampilkan Tabel
    if picks.empty:
        st.info("Tidak ada saham yang lolos filter. Coba longgarkan filter di atas.")
    else:
        show = picks.copy()
        show["Harga"] = show["Harga"].map(lambda x: f"Rp{x:,.0f}")
        show["Perubahan %"] = (picks["Perubahan %"] * 100).map(lambda x: f"{x:+.2f}%")
        show["Value Traded (Rp)"] = picks["Value Traded (Rp)"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        show["Volume Ratio"] = picks["Volume Ratio"].map(lambda x: f"{x:.1f}x")
        
        if "Quality Score" in show.columns:
            show["Quality Score"] = show["Quality Score"].map(lambda x: f"{float(x):.1f}" if pd.notnull(x) and x != "" else "-")
        
        if "Risiko %" in show.columns:
            show["Risiko %"] = show["Risiko %"].map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "-")
        
        for col in ["RR", "Entry", "Target", "Stop Loss"]:
            if col in show.columns:
                if col == "RR":
                    show[col] = show[col].map(lambda x: f"{x:.2f}x" if pd.notnull(x) and x > 0 else "-")
                else:
                    show[col] = show[col].map(lambda x: f"Rp{x:,.0f}" if pd.notnull(x) and x > 0 else "-")

        kolom_tampil = [
            "Kode", "Nama", "Signal", "Score", 
            "Rekomendasi", "RR", "Risiko %", "Entry", "Target", "Stop Loss", "SL Type",
            "Quality", "Quality Score", "Trend", "Smart Money", "Momentum",
            "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)", "Status Breakout"
        ]
        if aktifkan_sektor:
            kolom_tampil.insert(2, "Sektor")
        kolom_tampil = [col for col in kolom_tampil if col in show.columns]

        def color_rec(val):
            val = str(val)
            if "DAY TRADE" in val: return "background-color: #16a34a; color: white; font-weight: bold;"
            if "SWING TRADE" in val: return "background-color: #2563eb; color: white; font-weight: bold;"
            if "AVOID" in val: return "background-color: #dc2626; color: white; font-weight: bold;"
            if "WAIT" in val: return "background-color: #eab308; color: black; font-weight: bold;"
            return ""
        
        def color_q(val):
            val = str(val)
            if "HIGH" in val: return "background-color: #065f46; color: white; font-weight: bold;"
            if "MODERATE" in val: return "background-color: #92400e; color: white; font-weight: bold;"
            return ""
        
        def color_rr(val):
            try:
                rr = float(str(val).replace("x", "").strip())
                if rr >= 3.0: return "background-color: #16a34a; color: white; font-weight: bold;"
                elif rr >= 2.0: return "background-color: #2563eb; color: white; font-weight: bold;"
                elif rr >= 1.5: return "background-color: #eab308; color: black; font-weight: bold;"
                else: return "background-color: #dc2626; color: white; font-weight: bold;"
            except:
                return ""

        styler = show[kolom_tampil].style
        if "Rekomendasi" in kolom_tampil:
            styler = styler.map(color_rec, subset=["Rekomendasi"])
        if "Quality" in kolom_tampil:
            styler = styler.map(color_q, subset=["Quality"])
        if "RR" in kolom_tampil:
            styler = styler.map(color_rr, subset=["RR"])

        st.dataframe(styler, use_container_width=True, hide_index=True, height=460, key="df_kandidat_final")

        st.download_button("⬇️ Download CSV", show[kolom_tampil].to_csv(index=False).encode("utf-8"), file_name=f"kandidat_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
  
            # === TOMBOL KIRIM KE JURNAL REAL ===
    st.divider()
    st.markdown("###  Kirim ke Jurnal Real")
    st.caption("Pilih saham dari tabel di atas, lalu data akan otomatis terisi di tab Jurnal Real")
    
    cat1, cat2, cat3 = st.columns([2, 1, 1])
    with cat1:
        pilih_catat = st.selectbox(
            "Pilih Saham:",
            options=["-- Pilih Saham --"] + show["Kode"].tolist(),
            key="pilih_catat_kandidat"
        )
    with cat2:
        lot_catat = st.number_input("Lot", min_value=1, value=10, step=1, key="lot_catat_kandidat")
    with cat3:
        setup_catat = st.selectbox("Setup", options=rj.SETUP_OPTIONS, index=0, key="setup_catat_kandidat")
    
    if st.button(" Kirim ke Jurnal Real", type="primary", use_container_width=True, key="btn_catat_kandidat"):
        if pilih_catat == "-- Pilih Saham --":
            st.error("⚠️ Pilih saham terlebih dahulu!")
        else:
            row_data = show[show["Kode"] == pilih_catat].iloc[0]
            
            def clean_number(value):
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    cleaned = value.replace("Rp", "").replace(",", "").replace(" ", "").strip()
                    try:
                        return float(cleaned)
                    except:
                        return 0.0
                return 0.0
            
            st.session_state['auto_fill_trade'] = {
                'kode': pilih_catat,
                'entry': clean_number(row_data.get('Entry', row_data.get('Harga', 0))),
                'stop_loss': clean_number(row_data.get('Stop Loss', 0)),
                'target': clean_number(row_data.get('Target', 0)),
                'setup': setup_catat,
                'lot': lot_catat,
                'rekomendasi': row_data.get('Signal', ''),
                'rr': clean_number(row_data.get('RR', 0))
            }
                        
        st.success(f"✅ Data {pilih_catat} siap! Buka tab **Jurnal Real**.")
        st.info(f"📊 Entry: Rp{st.session_state['auto_fill_trade']['entry']:,.0f} | SL: Rp{st.session_state['auto_fill_trade']['stop_loss']:,.0f} | Target: Rp{st.session_state['auto_fill_trade']['target']:,.0f}")

      
        st.divider()
        st.markdown("### 📈 Chart TradingView")
        chart_kode = st.selectbox("Pilih saham untuk melihat chart:", options=["-- Pilih Saham --"] + show["Kode"].tolist(), key="chart_selector")
        if chart_kode and chart_kode != "-- Pilih Saham --":
            embed_tradingview_chart(chart_kode, height=500)

# ============================================================================
# TAB 2: SEMUA SAHAM
# ============================================================================
with t_semua:
    colf1, colf2, colf3 = st.columns([2, 1, 1])
    with colf1:
        search = st.text_input("Cari kode/nama saham", "")
    with colf2:
        sig_filter = st.multiselect("Filter Signal", options=sorted(table["Signal"].unique().tolist()), default=[])
    with colf3:
        sektor_filter = []
        if aktifkan_sektor:
            sektor_filter = st.multiselect("🏷️ Filter Sektor", options=sorted(table["Sektor"].dropna().unique().tolist()), default=[], key="sektor_tab2")
    
    view = table.copy()
    if search:
        mask = view["Kode"].str.contains(search.upper()) | view["Nama"].str.upper().str.contains(search.upper())
        view = view[mask]
    if sig_filter:
        view = view[view["Signal"].isin(sig_filter)]
    if sektor_filter:
        view = view[view["Sektor"].isin(sektor_filter)]
        
    view_display = view.copy()
    view_display["Harga"] = view_display["Harga"].map(lambda x: f"Rp{x:,.0f}")
    view_display["Perubahan %"] = (view_display["Perubahan %"] * 100).map(lambda x: f"{x:+.2f}%")
    view_display["Value Traded (Rp)"] = view_display["Value Traded (Rp)"].map(lambda x: f"Rp{x/1e9:,.1f} M")
    view_display["Volume Ratio"] = view_display["Volume Ratio"].map(lambda x: f"{x:.1f}x")
    
    kolom_tampil2 = ["Kode", "Nama", "Signal", "Score", "Quality", "Quality Score", "Trend", "Smart Money", "Momentum", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)", "Status Breakout", "Layak Likuiditas"]
    if aktifkan_sektor:
        kolom_tampil2.insert(2, "Sektor")
    kolom_tampil2 = [col for col in kolom_tampil2 if col in view_display.columns]
    
    dataframe_with_chart(view_display[kolom_tampil2], kode_col="Kode", height=520, key="df_semua")
    st.caption(f"Menampilkan {len(view)} dari {len(table)} saham")
    st.download_button("⬇️ Download CSV", view_display[kolom_tampil2].to_csv(index=False).encode("utf-8"), file_name=f"semua_saham_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

# ============================================================================
# TAB 3: GRAFIK SAHAM
# ============================================================================
with t_grafik:
    pilih = st.selectbox("Pilih saham", options=table["Kode"].tolist())
    if pilih in price_data:
        df_full = price_data[pilih]
        df = df_full.tail(90)
        row = table[table["Kode"] == pilih].iloc[0]
        
        chart_mode = st.radio("Sumber grafik", ["Dashboard (Plotly + Donchian + Swing HL)", "TradingView Live (tertanam di halaman ini)"], horizontal=True, label_visibility="collapsed")
        
        if chart_mode.startswith("TradingView"):
            embed_tradingview_chart(pilih)
            st.caption("Chart TradingView muncul langsung di halaman ini (tidak pindah tab) - bisa ganti timeframe/indikator langsung di dalam chart-nya.")
            sh, sl_pts = ind.find_swing_points(df_full, order=3)
            swing_df = ind.classify_swings(sh, sl_pts)
        else:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name=pilih))
            ma_colors = {5: "#facc15", 20: "#38bdf8", 50: "#a78bfa"}
            for p, c in ma_colors.items():
                if len(df_full) >= p:
                    ma_line = df_full["Close"].rolling(p).mean().tail(90)
                    fig.add_trace(go.Scatter(x=ma_line.index, y=ma_line, mode="lines", name=f"MA{p}", line=dict(width=1.4, color=c)))
            fig.add_hline(y=row["Donchian High"], line_dash="dash", line_color="#22c55e", annotation_text=f"Donchian High {int(donchian_lb)}D")
            fig.add_hline(y=row["Donchian Low"], line_dash="dash", line_color="#ef4444", annotation_text=f"Donchian Low {int(donchian_lb)}D")
            
            sh, sl_pts = ind.find_swing_points(df_full, order=3)
            swing_df = ind.classify_swings(sh, sl_pts)
            swing_recent = swing_df[swing_df["Tanggal"] >= df.index.min()]
            for _, sp in swing_recent.iterrows():
                color = "#22c55e" if sp["Label"] in ("HH", "HL") else "#ef4444"
                fig.add_annotation(x=sp["Tanggal"], y=sp["Harga"], text=sp["Label"], showarrow=True, arrowhead=1, arrowcolor=color, font=dict(color=color, size=10), ay=-25 if sp["Tipe"] == "H" else 25)
            
            fig.update_layout(height=520, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), title=f"{pilih} — {row['Nama']}", legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)
            
        cols = st.columns(4)
        cols[0].metric("Harga", f"Rp{row['Harga']:,.0f}", f"{row['Perubahan %']*100:+.2f}%")
        cols[1].metric("Signal", row["Signal"])
        cols[2].metric("Score", int(row["Score"]))
        cols[3].metric("Breakout", row["Status Breakout"])
        st.divider()
        
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
                st.markdown(f"**Summary** &nbsp; <span class='{badge_class}'>{overall}</span>", unsafe_allow_html=True)
                st.caption(f"Moving Averages: **{ma_sum['overall']}** (Buy {ma_sum['buy']} · Sell {ma_sum['sell']}) · Technical Indicators: **{ti_sum['overall']}** (Buy {ti_sum['buy']} · Neutral {ti_sum['neutral']} · Sell {ti_sum['sell']})")
            
            def _color_action(val):
                color = {"Buy": "#16a34a", "Sell": "#dc2626", "Neutral": "#6b7280"}.get(val, "")
                return f"background-color:{color}; color:white; font-weight:600;" if color else ""
            def _color_combined(val):
                val = str(val)
                if val.endswith("Buy"): color = "#16a34a"
                elif val.endswith("Sell"): color = "#dc2626"
                elif val.endswith("Neutral"): color = "#6b7280"
                else: return ""
                return f"background-color:{color}; color:white; font-weight:600;"
            def _style_table(df_in, subset_cols, color_fn=_color_action):
                styler = df_in.style
                if hasattr(styler, "map"): return styler.map(color_fn, subset=subset_cols)
                return styler.applymap(color_fn, subset=subset_cols)
            
            mcol, tcol = st.columns(2)
            with mcol:
                st.markdown("**Moving Averages**")
                st.dataframe(_style_table(ma_table[["MA", "Simple", "Exponential"]], ["Simple", "Exponential"], _color_combined), use_container_width=True, hide_index=True, height=250)
            with tcol:
                st.markdown("**Technical Indicators**")
                st.dataframe(_style_table(ti_table, ["Action"], _color_action), use_container_width=True, hide_index=True, height=340)
        else:
            st.info("Panel MA/Technical Indicators butuh minimal 50 hari data historis (saat ini baru tersedia sebagian) - akan lengkap otomatis saat data historis bertambah.")
            
        st.markdown("**Swing High/Low Terakhir**")
        if not swing_df.empty:
            st.dataframe(swing_df.tail(6).sort_values("Tanggal", ascending=False), use_container_width=True, hide_index=True, height=210)
        else:
            st.caption("Belum ada swing point terdeteksi pada rentang data ini.")
    else:
        st.info("Data grafik untuk saham ini belum tersedia di batch saat ini.")

# ============================================================================
# TAB 4: JURNAL BACKTEST
# ============================================================================
with t_backtest:
    if not gj.is_configured():
        st.warning("Jurnal backtest belum terhubung ke Google Sheets. Isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Settings > Secrets. Langkah lengkap ada di README bagian 'Setup Google Sheets untuk Jurnal Backtest'.")
    else:
        try:
            test_conn = gj.load_positions()
            st.success(f"✅ Google Sheets terhubung - {len(test_conn)} posisi tercatat")
        except Exception as e:
            st.error(f"❌ Error koneksi: {str(e)}")
            st.stop()
        
        # ---- AUTO-CLOSE OTOMATIS SAAT LOAD TAB ----
        price_lookup = dict(zip(table["Kode"], table["Harga"]))
        try:
            with st.spinner("🔍 Mengecek auto-close otomatis (TP/SL/Force-Sell)..."):
                auto_closed = gj.auto_close_positions(price_lookup)
            if auto_closed:
                st.success(f"🔴 Auto-close otomatis: {', '.join(auto_closed)}")
                st.balloons()
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error auto-close otomatis: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            
        day_tipe = classify_daytrading_tipe()
        st.caption(f"Waktu sekarang WIB terdeteksi sebagai tipe **{day_tipe}** untuk Day Trading ({'Beli Pagi, rencana Jual Sore' if day_tipe=='BPJS' else 'Beli Sore, rencana Jual besok Pagi'}).")
        st.write(f"📊 **Kandidat Day Trading tersedia:** {len(cands_day_all)}")
        st.write(f"📊 **Kandidat Swing Trading tersedia:** {len(cands_swing_all)}")
        
        if not cands_swing_all.empty:
            with st.expander("👁️ Lihat Kandidat Swing Trading"):
                st.dataframe(cands_swing_all[["Saham", "Entry", "Stop Loss", "Target", "RR"]].head(10))
                
        colb1, colb2, colb3 = st.columns(3)
        with colb1:
            if st.button(f"🟢 Buka Posisi Day Trading ({day_tipe})", use_container_width=True, key="btn_open_day"):
                try:
                    with st.spinner("Membuka posisi Day Trading..."):
                        if cands_day_all.empty:
                            st.warning("⚠️ Tidak ada kandidat Day Trading - mungkin belum ada yang lolos filter")
                        else:
                            opened = gj.open_positions_from_candidates(cands_day_all, day_tipe)
                            if opened:
                                st.success(f"✅ Berhasil dibuka: {', '.join(opened)}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.warning("⚠️ Tidak ada posisi baru dibuka (semua sudah ada)")
                except Exception as e:
                    st.error(f"❌ Error buka Day Trading: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    
        with colb2:
            if st.button("🟢 Buka Posisi Swing Trading", use_container_width=True, key="btn_open_swing"):
                try:
                    with st.spinner("Membuka posisi Swing Trading..."):
                        if cands_swing_all.empty:
                            st.warning("⚠️ **Tidak ada kandidat Swing Trading!**")
                            st.info("""
                            Kemungkinan penyebab:
                            1. Belum ada saham yang lolos screening untuk Swing
                            2. Filter RR (Risk:Reward) terlalu ketat - coba turunkan di sidebar
                            3. Donchian lookback terlalu panjang - coba turunkan di sidebar
                            4. IHSG sedang Bearish dan filter pasar aktif
                            **Solusi:**
                            - Turunkan "Minimum Risk:Reward (RR)" di sidebar (mis. dari 2.0 ke 1.5)
                            - Refresh data live
                            - Cek tab "Top 10 Day/Swing" untuk melihat kandidat
                            """)
                        else:
                            st.write("🎯 **Kandidat yang akan dibuka:**")
                            st.dataframe(cands_swing_all[["Saham", "Entry", "Stop Loss", "Target", "RR"]].head(10))
                            opened = gj.open_positions_from_candidates(cands_swing_all, "SWING")
                            if opened:
                                st.success(f"✅ Berhasil dibuka: {', '.join(opened)}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.warning("⚠️ Tidak ada posisi baru dibuka (semua sudah ada di sheet)")
                except Exception as e:
                    st.error(f"❌ Error buka Swing Trading: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    
        with colb3:
            if st.button("🔴 Cek TP/SL & Force-Sell", use_container_width=True, key="btn_check_close"):
                try:
                    with st.spinner("Mengecek posisi OPEN..."):
                        positions = gj.load_positions()
                        open_positions = positions[positions["Status"] == "OPEN"] if not positions.empty else pd.DataFrame()
                        st.write(f"📋 Total posisi: {len(positions)}")
                        st.write(f"🟢 Posisi OPEN: {len(open_positions)}")
                        
                        closed = []  # <-- INISIALISASI DI SINI supaya tidak NameError
                        
                        if open_positions.empty:
                            st.info("ℹ️ Tidak ada posisi OPEN untuk dicek")
                        else:
                            st.write("**📊 Posisi yang dicek:**")
                            debug_df = open_positions[["Saham", "Harga Beli", "TP", "SL", "Tipe", "Lot", "Tanggal Open"]].copy()
                            debug_df["Harga Sekarang"] = debug_df["Saham"].map(lambda x: f"Rp{price_lookup.get(x, 0):,.0f}" if x in price_lookup else "N/A")
                            
                            def check_status(row):
                                saham = row["Saham"]
                                if saham not in price_lookup: return "⚠️ Harga tidak tersedia"
                                current = price_lookup[saham]
                                tp = float(row["TP"]) if pd.notna(row["TP"]) else None
                                sl = float(row["SL"]) if pd.notna(row["SL"]) else None
                                if tp and current >= tp: return f"✅ HIT TP"
                                elif sl and current <= sl: return f"❌ HIT SL"
                                else: return f"⏳ HOLD"
                                
                            debug_df["Status"] = debug_df.apply(check_status, axis=1)
                            st.dataframe(debug_df, use_container_width=True)
                            st.write("\n🔄 **Memproses penutupan posisi...**")
                            closed = gj.auto_close_positions(price_lookup)
                            
                        if closed:
                            st.success(f"✅ Berhasil ditutup: {', '.join(closed)}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.info("ℹ️ Belum ada yang perlu ditutup (belum kena TP/SL atau belum waktunya force-sell)")
                except Exception as e:
                    st.error(f"❌ Error cek TP/SL: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    
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
        st.caption("Aturan force-sell otomatis: SWING maksimal 10 hari, BPJS maksimal 1 hari, BSJP maksimal 2 hari kalau belum kena TP/SL. Auto-close sekarang juga berjalan otomatis saat tab ini dibuka.")

# ============================================================================
# TAB 5: TOP 10 DAY/SWING
# ============================================================================
with t_top10:
    st.caption(f"Entry = harga sekarang · Stop Loss = Donchian Low (struktural) · "
               f"Target = proyeksi measured-move dari lebar channel Donchian · hanya RR ≥ {min_rr:.1f}:1")
    day_tipe = classify_daytrading_tipe()
    
    st.subheader(f"⚡ Top 10 Day Trading (Donchian {int(donchian_lb_day)} hari) — tipe {day_tipe}")
    cands_day = cands_day_all
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
    cands_swing = cands_swing_all
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
# ============================================================================
# TAB 6: KALKULATOR
# ============================================================================
with t_kalk:
    st.subheader("🧮 Kalkulator Profit & Risiko")
    kalk_col1, kalk_col2 = st.columns(2)
    
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
                badge = "📉 AVERAGE DOWN" if ra["tipe"] == "AVERAGE DOWN" else (
                    "📈 AVERAGE UP" if ra["tipe"] == "AVERAGE UP" else "⚪ HARGA SAMA")
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

# ============================================================================
# TAB 7: PERFORMANCE
# ============================================================================
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

# ============================================================================
# TAB 8: JURNAL REAL (DENGAN AUTO-FILL) - SUB 1
# ============================================================================
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
            ["➕ Catat Trade", "🔓 Tutup Posisi", " Performance Real", "⚙️ Sekuritas", "✏️ Edit/Hapus"]
        )
        
        # --- Catat trade baru ---
        with sub1:
            st.markdown("**Catat posisi baru (OPEN)**")
            brokers_df = rj.load_brokers()
            broker_options = brokers_df["Sekuritas"].tolist() if not brokers_df.empty else ["Lainnya"]
            
            # === AUTO-FILL DARI KANDIDAT TERBAIK ===
            auto_data = st.session_state.get('auto_fill_trade', None)
            
            if auto_data:
                st.success(f"🎯 Auto-fill aktif: **{auto_data['kode']}** ({auto_data['rekomendasi']})")
                with st.expander("📋 Detail Auto-fill", expanded=True):
                    st.write(f"**Entry:** Rp{auto_data['entry']:,.0f}")
                    st.write(f"**Stop Loss:** Rp{auto_data['stop_loss']:,.0f}")
                    st.write(f"**Target:** Rp{auto_data['target']:,.0f}")
                    st.write(f"**RR:** {auto_data['rr']}x")
                    st.write(f"**Setup:** {auto_data['setup']}")
                    st.write(f"**Lot:** {auto_data['lot']}")
                if st.button("🗑️ Batal Auto-fill", key="btn_cancel_autofill"):
                    del st.session_state['auto_fill_trade']
                    for k in ["saham_rj", "setup_rj", "lot_rj", "entry_rj", "sl_rj", "target_rj", "catatan_rj"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
                st.divider()
            
            # === SET WIDGET DEFAULTS VIA SESSION STATE ===
            # Streamlit ignores 'value=' if the widget key already exists in session_state.
            # We MUST set session_state BEFORE creating the widget.
            if auto_data:
                st.session_state["saham_rj"] = str(auto_data.get('kode', ''))
                setup_val = auto_data.get('setup', rj.SETUP_OPTIONS[0])
                st.session_state["setup_rj"] = setup_val if setup_val in rj.SETUP_OPTIONS else rj.SETUP_OPTIONS[0]
                st.session_state["lot_rj"] = int(auto_data.get('lot', 10))
                st.session_state["entry_rj"] = float(auto_data.get('entry', 0))
                st.session_state["sl_rj"] = float(auto_data.get('stop_loss', 0))
                st.session_state["target_rj"] = float(auto_data.get('target', 0))
                st.session_state["catatan_rj"] = f"Auto-fill dari Kandidat Terbaik - {auto_data.get('rekomendasi', '')}"
                # Hapus supaya tidak terus-terusan override saat user edit manual
                del st.session_state['auto_fill_trade']
            
            # === FORM INPUT ===
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                tgl_entry = st.date_input("Tanggal Entry", value=datetime.now(), key="tgl_entry_rj")
            with fc2:
                sekuritas_in = st.selectbox("Sekuritas", options=broker_options, key="sekuritas_rj")
            with fc3:
                # Jangan pakai value=, karena default sudah diatur via session_state di atas
                saham_in = st.text_input("Kode Saham", key="saham_rj").upper()
            
            fc4, fc5 = st.columns(2)
            with fc4:
                setup_in = st.selectbox("Setup", options=rj.SETUP_OPTIONS, key="setup_rj")
            with fc5:
                lot_in2 = st.number_input("Lot", min_value=1, step=1, key="lot_rj")
            
            fc6, fc7, fc8 = st.columns(3)
            with fc6:
                entry_in2 = st.number_input("Entry (Rp)", min_value=0.0, step=1.0, key="entry_rj")
            with fc7:
                sl_in2 = st.number_input("Stop Loss (Rp)", min_value=0.0, step=1.0, key="sl_rj")
            with fc8:
                target_in2 = st.number_input("Target (Rp)", min_value=0.0, step=1.0, key="target_rj")
            
            catatan_in = st.text_area("Catatan", height=70, key="catatan_rj")
            
            if st.button("💾 Simpan Trade (OPEN)", type="primary", key="btn_open_rj"):
                if not saham_in or entry_in2 <= 0:
                    st.error("Kode saham dan Entry wajib diisi.")
                else:
                    no = rj.open_trade(
                        tgl_entry.strftime("%Y-%m-%d"), sekuritas_in, saham_in, setup_in,
                        entry_in2, sl_in2, target_in2, lot_in2, catatan_in,
                    )
                    st.success(f"Trade #{no} ({saham_in}) berhasil dicatat.")
                    # Bersihkan widget state supaya form fresh lagi
                    for k in ["saham_rj", "setup_rj", "lot_rj", "entry_rj", "sl_rj", "target_rj", "catatan_rj"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()

        # --- Sub 2: Tutup Posisi ---
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
                if st.button("🔓 Tutup Posisi Ini", type="primary", key="btn_close_rj"):
                    if exit_price_in <= 0:
                        st.error("Harga Exit wajib diisi.")
                    else:
                        ok, msg = rj.close_trade(pilih_no, tgl_exit_in.strftime("%Y-%m-%d"), exit_price_in)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # --- Sub 3: Performance Real ---
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
                st.divider()
                pb1, pb2 = st.columns(2)
                with pb1:
                    st.markdown("**Performance per Sekuritas**")
                    st.dataframe(rj.performance_by_broker(trades_all), use_container_width=True, hide_index=True)
                with pb2:
                    st.markdown("**Performance per Setup**")
                    st.dataframe(rj.performance_by_setup(trades_all), use_container_width=True, hide_index=True)
                                st.divider()

                # =========================================================================
                # ⬇️ TAMBAHAN: GRAFIK PERBANDINGAN PORTOFOLIO vs IHSG
                # =========================================================================
                try:
                    closed = trades_all[trades_all["Status"] == "CLOSE"].copy()
                    if not closed.empty and not ihsg_hist.empty:
                        # Pastikan tanggal dalam format datetime
                        closed["Tanggal Exit"] = pd.to_datetime(closed["Tanggal Exit"])
                        closed = closed.sort_values("Tanggal Exit")

                        # Deteksi nama kolom P&L dan Entry/Lot (otomatis menyesuaikan)
                        pl_col = next((c for c in ["P&L (Rp)", "Net P/L", "Profit (Rp)", "PnL (Rp)"] if c in closed.columns), None)
                        entry_col = next((c for c in ["Entry (Rp)", "Harga Beli", "Entry"] if c in closed.columns), None)
                        lot_col = next((c for c in ["Lot", "lot"] if c in closed.columns), None)

                        if pl_col and entry_col and lot_col:
                            # Hitung cumulative P/L
                            closed["Cum_PnL"] = closed[pl_col].cumsum()

                            # Modal awal = nilai transaksi trade pertama sebagai proxy
                            modal = float(closed.iloc[0][entry_col]) * float(closed.iloc[0][lot_col]) * 100
                            if modal <= 0:
                                modal = 1_000_000  # fallback 1 juta

                            # Return % portofolio
                            closed["Port_Return_%"] = ((modal + closed["Cum_PnL"]) / modal - 1) * 100

                            # Filter IHSG sesuai rentang tanggal trade
                            fd = closed["Tanggal Exit"].min()
                            ld = closed["Tanggal Exit"].max()
                            ihsg_range = ihsg_hist[(ihsg_hist.index >= fd) & (ihsg_hist.index <= ld)].copy()

                            if not ihsg_range.empty and len(ihsg_range) >= 2:
                                ihsg_base = float(ihsg_range["Close"].iloc[0])
                                ihsg_range["IHSG_Return_%"] = ((ihsg_range["Close"] / ihsg_base) - 1) * 100

                                fig_cmp = go.Figure()

                                # Garis Portofolio
                                fig_cmp.add_trace(go.Scatter(
                                    x=closed["Tanggal Exit"],
                                    y=closed["Port_Return_%"],
                                    mode="lines+markers",
                                    name="🟦 Portofolio Jurnal Real",
                                    line=dict(color="#38bdf8", width=2.5),
                                    fill="tozeroy",
                                    fillcolor="rgba(56,189,248,0.10)",
                                ))

                                # Garis IHSG
                                fig_cmp.add_trace(go.Scatter(
                                    x=ihsg_range.index,
                                    y=ihsg_range["IHSG_Return_%"],
                                    mode="lines",
                                    name="🟨 IHSG (Benchmark)",
                                    line=dict(color="#fbbf24", width=2.5, dash="dash"),
                                ))

                                fig_cmp.update_layout(
                                    height=350,
                                    template="plotly_dark",
                                    title="📊 Perbandingan Return Kumulatif: Portofolio vs IHSG",
                                    yaxis_title="Return Kumulatif (%)",
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                    margin=dict(l=10, r=10, t=50, b=10),
                                    hovermode="x unified",
                                )
                                st.plotly_chart(fig_cmp, use_container_width=True)

                                # Ringkasan selisih
                                lp = closed["Port_Return_%"].iloc[-1]
                                li = ihsg_range["IHSG_Return_%"].iloc[-1]
                                delta = lp - li
                                if delta > 0:
                                    st.success(
                                        f"🚀 Portofolio mengungguli IHSG sebesar **{delta:+.2f}%** "
                                        f"(Portofolio: {lp:+.2f}% vs IHSG: {li:+.2f}%)"
                                    )
                                else:
                                    st.warning(
                                        f"📉 Portofolio di bawah IHSG sebesar **{delta:+.2f}%** "
                                        f"(Portofolio: {lp:+.2f}% vs IHSG: {li:+.2f}%)"
                                    )
                        else:
                            st.caption("⚠️ Kolom P&L/Entry/Lot tidak ditemukan — grafik perbandingan dilewati.")
                except Exception as e:
                    st.caption(f"⚠️ Grafik perbandingan IHSG belum tersedia: {e}")
                # =========================================================================
                # ⬆️ AKHIR TAMBAHAN
                # =========================================================================
                
                st.markdown("**Riwayat Semua Trade**")
                st.dataframe(trades_all, use_container_width=True, hide_index=True, height=350)
                st.download_button(
                    "⬇️ Download CSV", trades_all.to_csv(index=False).encode("utf-8"),
                    file_name=f"jurnal_real_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
                    key="dl_jurnal_real",
                )

        # --- Sub 4: Sekuritas ---
        with sub4:
            st.markdown("**Daftar Sekuritas & Biaya Transaksi**")
            brokers_now = rj.load_brokers()
            st.dataframe(brokers_now, use_container_width=True, hide_index=True)
            st.markdown("**Tambah / Update Sekuritas**")
            bc1, bc2, bc3 = st.columns(3)
            nama_broker_in = bc1.text_input("Nama Sekuritas", key="nama_broker_rj")
            biaya_beli_in2 = bc2.number_input("Biaya Beli (%)", min_value=0.0, value=0.15, step=0.01, key="bb_broker")
            biaya_jual_in2 = bc3.number_input("Biaya Jual (%)", min_value=0.0, value=0.25, step=0.01, key="bj_broker")
            if st.button("💾 Simpan Sekuritas", key="btn_save_broker"):
                if not nama_broker_in:
                    st.error("Nama sekuritas wajib diisi.")
                else:
                    rj.add_broker(nama_broker_in, biaya_beli_in2, biaya_jual_in2)
                    st.success(f"Sekuritas '{nama_broker_in}' disimpan.")

        # --- Sub 5: Edit/Hapus ---
        with sub5:
            st.caption("Salah input harga/lot/sekuritas? Pilih nomor trade di bawah, koreksi, lalu simpan.")
            trades_edit = rj.load_trades()
            if trades_edit.empty:
                st.info("Belum ada trade untuk diedit.")
            else:
                pilih_edit_no = st.selectbox(
                    "Pilih nomor trade",
                    options=trades_edit["No"].tolist(),
                    format_func=lambda n: f"#{n} - {trades_edit.loc[trades_edit['No']==n,'Saham'].values[0]}",
                    key="pilih_edit_no_rj",
                )
                row_edit = trades_edit[trades_edit["No"] == pilih_edit_no].iloc[0]
                broker_options_edit = rj.load_brokers()["Sekuritas"].tolist()
                ec1, ec2, ec3 = st.columns(3)
                e_tgl_entry = ec1.text_input("Tanggal Entry (YYYY-MM-DD)", value=str(row_edit["Tanggal Entry"]), key="e_tgl")
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
                ec9, ec10 = st.columns(2)
                e_tgl_exit = ec9.text_input("Tanggal Exit (YYYY-MM-DD, kosongkan kalau OPEN)", value=str(row_edit["Tanggal Exit"] or ""), key="e_tgl_exit")
                e_exit_price = ec10.number_input("Harga Exit (Rp, 0 = OPEN)", min_value=0.0, value=float(row_edit["Exit (Rp)"] or 0), step=1.0, key="e_exit_price")
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

# ============================================================================
# TAB 9: EQUITY
# ============================================================================
with t_equity:
    if not gj.is_configured():
        st.warning("Equity Tracking butuh koneksi Google Sheets yang sama dengan Jurnal Real/Backtest.")
    else:
        sub_ringkasan, sub_catat, sub_riwayat = st.tabs(["📊 Ringkasan", "➕ Catat Snapshot", " Riwayat"])
        equity_df = eq.load_equity()
        
        with sub_ringkasan:
            if equity_df.empty:
                st.info("Belum ada data equity. Isi snapshot pertama di tab 'Catat Snapshot'.")
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
                fig_eq2.update_layout(height=300, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Rp")
                st.plotly_chart(fig_eq2, use_container_width=True)
                
                st.markdown("**🏦 Equity per Sekuritas (Snapshot Terbaru)**")
                latest_broker = eq.latest_per_sekuritas(equity_df)
                if not latest_broker.empty:
                    bc1, bc2 = st.columns([1.3, 1])
                    with bc1:
                        show_broker_eq = latest_broker[["Sekuritas", "Tanggal", "Total Equity (Rp)", "Cash (Rp)", "Invested (Rp)", "Max Risk/Trade (%)", "Max Position/Stock (%)"]]
                        st.dataframe(show_broker_eq, use_container_width=True, hide_index=True)
                    with bc2:
                        fig_pie = go.Figure(data=[go.Pie(
                            labels=latest_broker["Sekuritas"],
                            values=pd.to_numeric(latest_broker["Total Equity (Rp)"], errors="coerce"),
                            hole=0.5,
                        )])
                        fig_pie.update_layout(height=260, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
                        st.plotly_chart(fig_pie, use_container_width=True)

        with sub_catat:
            st.caption("Isi angka ini dari aplikasi sekuritas Bro (halaman Portfolio/RDN).")
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
                sc6, sc7 = st.columns(2)
                s_max_risk = sc6.number_input("Max Risk/Trade (%)", min_value=0.0, value=2.0, step=0.5, key="eq_maxrisk")
                s_max_pos = sc7.number_input("Max Position/Stock (%)", min_value=0.0, value=20.0, step=1.0, key="eq_maxpos")
                if st.button("💾 Simpan Snapshot", type="primary", key="btn_save_equity"):
                    if s_total_equity <= 0:
                        st.error("Total Equity wajib diisi lebih dari 0.")
                    else:
                        ok, msg = eq.add_equity_snapshot(s_tanggal, s_sekuritas, s_total_equity, s_cash, s_invested, s_max_risk, s_max_pos)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

        with sub_riwayat:
            if equity_df.empty:
                st.info("Belum ada riwayat snapshot.")
            else:
                st.dataframe(equity_df.sort_values("Tanggal", ascending=False), use_container_width=True, hide_index=True, height=400)
                st.download_button(
                    "️ Download CSV", equity_df.to_csv(index=False).encode("utf-8"),
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
st.caption("️ Data diambil dari Yahoo Finance (yfinance), bukan API resmi. Bukan rekomendasi keuangan. Selalu lakukan riset & kelola risiko sendiri.")



