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

st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
div[data-testid="stMetric"] {background: #111827; border-radius: 12px; padding: 12px 14px; border: 1px solid #1f2937; overflow: hidden;}
div[data-testid="stMetricValue"] {font-size: 1.35rem !important; white-space: normal !important; overflow-wrap: break-word;}
div[data-testid="stMetricLabel"] {font-size: 0.8rem !important;}
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
.cumulative-box {background:linear-gradient(135deg,#111827,#1f2937); border:1px solid #374151; border-radius:14px; padding:22px; text-align:center;}
.cumulative-label {font-size:0.85rem; color:#9ca3af; text-transform:uppercase; letter-spacing:0.05em;}
.cumulative-value {font-size:2.4rem; font-weight:800;}
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
    st.warning("Belum ada data yang berhasil diambil. Coba Refresh Data Live lagi.")
    st.stop()

if aktifkan_sektor:
    with st.spinner("Mengambil data sektor..."):
        sector_map = sec.fetch_sectors(table["Kode"].tolist())
        table["Sektor"] = table["Kode"].map(sector_map).fillna("TIDAK DIKETAHUI")
else:
    table["Sektor"] = None

st.caption(f"Terakhir refresh: {datetime.now().strftime('%d %b %Y, %H:%M')} · {len(table)}/{len(tickers)} saham berhasil")

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
    "🏆 Kandidat Terbaik", "📋 Semua Saham", "📉 Grafik Saham", "📒 Jurnal Backtest",
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
                    rekomendasi = str(row.get("Rekomendasi", ""))
                    
                    sl_donchian = dl
                    ma20 = float(df["Close"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else dl
                    sl_max = entry * 0.95 if "DAY TRADE" in rekomendasi else entry * 0.90
                    sl_type = "Day (max 5%)" if "DAY TRADE" in rekomendasi else "Swing (max 10%)"
                    
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

    if not picks.empty and "Rekomendasi" in picks.columns:
        st.markdown("### 🎯 Filter Trading")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            available_rec = sorted(picks["Rekomendasi"].dropna().unique().tolist())
            default_rec = [x for x in available_rec if "AVOID" not in x and "WAIT" not in x] or available_rec
            rec_filter = st.multiselect("1️⃣ Rekomendasi", options=available_rec, default=default_rec)
            if rec_filter: picks = picks[picks["Rekomendasi"].isin(rec_filter)]
        with col_f2:
            if "Quality" in picks.columns:
                available_q = sorted(picks["Quality"].dropna().unique().tolist())
                default_q = [x for x in ["✅ HIGH", "⚠️ MODERATE"] if x in available_q] or available_q
                q_filter = st.multiselect("2️⃣ Quality Rating", options=available_q, default=default_q)
                if q_filter: picks = picks[picks["Quality"].isin(q_filter)]
        with col_f3:
            use_rr_filter = st.checkbox("Filter RR ≥ 2.0", value=False)
            if use_rr_filter and "RR" in picks.columns:
                picks = picks[picks["RR"] >= 2.0]
                st.success("✅ Filter RR ≥ 2.0 aktif")

    if not picks.empty and "RR" in picks.columns:
        picks = picks.sort_values(["RR", "Quality Score"], ascending=[False, False])

    if picks.empty:
        st.info("Tidak ada saham yang lolos filter.")
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
        
        kolom_tampil = ["Kode", "Nama", "Signal", "Score", "Rekomendasi", "RR", "Risiko %", "Entry", "Target", "Stop Loss", "SL Type", "Quality", "Quality Score", "Trend", "Smart Money", "Momentum", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)", "Status Breakout"]
        if aktifkan_sektor: kolom_tampil.insert(2, "Sektor")
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
            except: return ""

        styler = show[kolom_tampil].style
        if "Rekomendasi" in kolom_tampil: styler = styler.map(color_rec, subset=["Rekomendasi"])
        if "Quality" in kolom_tampil: styler = styler.map(color_q, subset=["Quality"])
        if "RR" in kolom_tampil: styler = styler.map(color_rr, subset=["RR"])

        st.dataframe(styler, use_container_width=True, hide_index=True, height=460, key="df_kandidat_final")

        # === AUTO-FILL BUTTON ===
        st.divider()
        st.markdown("### 📝 Kirim ke Jurnal Real")
        cat1, cat2, cat3 = st.columns([2, 1, 1])
        with cat1:
            pilih_catat = st.selectbox("Pilih Saham:", options=["-- Pilih Saham --"] + show["Kode"].tolist(), key="pilih_catat_kandidat")
        with cat2:
            lot_catat = st.number_input("Lot", min_value=1, value=10, step=1, key="lot_catat_kandidat")
        with cat3:
            setup_catat = st.selectbox("Setup", options=rj.SETUP_OPTIONS, index=0, key="setup_catat_kandidat")
        
        if st.button("📝 Kirim ke Jurnal Real", type="primary", use_container_width=True, key="btn_catat_kandidat"):
            if pilih_catat == "-- Pilih Saham --":
                st.error("⚠️ Pilih saham terlebih dahulu!")
            else:
                row_data = show[show["Kode"] == pilih_catat].iloc[0]
        
                  # === FUNGSI BANTU: Bersihkan format Rp dan koma ===
                def clean_number(value):
                    """Hapus 'Rp', koma, dan spasi, lalu convert ke float"""
                    if isinstance(value, (int, float)):
                        return float(value)
                    if isinstance(value, str):
                        # Hapus 'Rp', koma, spasi
                        cleaned = value.replace("Rp", "").replace(",", "").replace(" ", "").strip()
                        try:
                            return float(cleaned)
                        except ValueError:
                            return 0.0
                    return 0.0
                # ================================================
        
                st.session_state['auto_fill_trade'] = {
                    'kode': pilih_catat,
                    'entry': clean_number(row_data.get('Entry', row_data['Harga'])),
                    'stop_loss': clean_number(row_data.get('Stop Loss', 0)),
                    'target': clean_number(row_data.get('Target', 0)),
                    'setup': setup_catat,
                    'lot': lot_catat,
                    'rekomendasi': row_data.get('Rekomendasi', ''),
                    'rr': clean_number(row_data.get('RR', 0))
        }
        
        st.success(f"✅ Data {pilih_catat} siap! Buka tab **Jurnal Real**.")
        st.info(f"📊 Entry: Rp{st.session_state['auto_fill_trade']['entry']:,.0f} | SL: Rp{st.session_state['auto_fill_trade']['stop_loss']:,.0f} | Target: Rp{st.session_state['auto_fill_trade']['target']:,.0f}")
               

        st.download_button("⬇️ Download CSV", show[kolom_tampil].to_csv(index=False).encode("utf-8"), file_name=f"kandidat_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        
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
    with colf1: search = st.text_input("Cari kode/nama saham", "")
    with colf2: sig_filter = st.multiselect("Filter Signal", options=sorted(table["Signal"].unique().tolist()), default=[])
    with colf3:
        sektor_filter = []
        if aktifkan_sektor: sektor_filter = st.multiselect("🏷️ Filter Sektor", options=sorted(table["Sektor"].dropna().unique().tolist()), default=[], key="sektor_tab2")
    
    view = table.copy()
    if search: view = view[view["Kode"].str.contains(search.upper()) | view["Nama"].str.upper().str.contains(search.upper())]
    if sig_filter: view = view[view["Signal"].isin(sig_filter)]
    if sektor_filter: view = view[view["Sektor"].isin(sektor_filter)]
    
    view_display = view.copy()
    view_display["Harga"] = view_display["Harga"].map(lambda x: f"Rp{x:,.0f}")
    view_display["Perubahan %"] = (view_display["Perubahan %"] * 100).map(lambda x: f"{x:+.2f}%")
    view_display["Value Traded (Rp)"] = view_display["Value Traded (Rp)"].map(lambda x: f"Rp{x/1e9:,.1f} M")
    view_display["Volume Ratio"] = view_display["Volume Ratio"].map(lambda x: f"{x:.1f}x")
    
    kolom_tampil2 = ["Kode", "Nama", "Signal", "Score", "Quality", "Quality Score", "Trend", "Smart Money", "Momentum", "Harga", "Perubahan %", "Volume Ratio", "Value Traded (Rp)", "Status Breakout", "Layak Likuiditas"]
    if aktifkan_sektor: kolom_tampil2.insert(2, "Sektor")
    kolom_tampil2 = [col for col in kolom_tampil2 if col in view_display.columns]
    
    dataframe_with_chart(view_display[kolom_tampil2], kode_col="Kode", height=520, key="df_semua")
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
        embed_tradingview_chart(pilih)
        st.divider()
        cols = st.columns(4)
        cols[0].metric("Harga", f"Rp{row['Harga']:,.0f}", f"{row['Perubahan %']*100:+.2f}%")
        cols[1].metric("Signal", row["Signal"])
        cols[2].metric("Score", int(row["Score"]))
        cols[3].metric("Breakout", row["Status Breakout"])

# ============================================================================
# TAB 4: JURNAL BACKTEST
# ============================================================================
with t_backtest:
    if not gj.is_configured():
        st.warning("Jurnal backtest belum terhubung ke Google Sheets. Isi `gcp_service_account` dan `GOOGLE_SHEET_ID` di Secrets.")
    else:
        st.success(f"✅ Google Sheets terhubung")
        day_tipe = classify_daytrading_tipe()
        st.caption(f"Tipe Day Trading saat ini: **{day_tipe}**")
        colb1, colb2, colb3 = st.columns(3)
        with colb1:
            if st.button(f"🟢 Buka Posisi Day Trading ({day_tipe})", use_container_width=True):
                if not cands_day_all.empty:
                    opened = gj.open_positions_from_candidates(cands_day_all, day_tipe)
                    if opened: st.success(f"✅ Berhasil dibuka: {', '.join(opened)}"); st.rerun()
        with colb2:
            if st.button("🟢 Buka Posisi Swing Trading", use_container_width=True):
                if not cands_swing_all.empty:
                    opened = gj.open_positions_from_candidates(cands_swing_all, "SWING")
                    if opened: st.success(f"✅ Berhasil dibuka: {', '.join(opened)}"); st.rerun()
        with colb3:
            if st.button("🔍 Cek TP/SL & Force-Sell", use_container_width=True):
                price_lookup = dict(zip(table["Kode"], table["Harga"]))
                closed = gj.auto_close_positions(price_lookup)
                if closed: st.success(f"✅ Berhasil ditutup: {', '.join(closed)}"); st.rerun()
                else: st.info("ℹ️ Belum ada yang perlu ditutup.")
        
        positions = gj.load_positions()
        stats = gj.summarize(positions)
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Posisi", stats["total"])
        s2.metric("Sedang OPEN", stats["open"])
        s3.metric("WIN", stats["win"])
        s4.metric("LOSS", stats["loss"])
        s5.metric("Win Rate", f"{stats['winrate']:.1f}%")
        st.dataframe(positions, use_container_width=True, hide_index=True, height=420)

# ============================================================================
# TAB 5: TOP 10 DAY/SWING
# ============================================================================
with t_top10:
    st.subheader(f"⚡ Top 10 Day Trading")
    if not cands_day_all.empty:
        show_day = cands_day_all.copy()
        show_day["Nilai Transaksi"] = show_day["Nilai Transaksi"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        dataframe_with_chart(show_day.drop(columns=["Chart"], errors="ignore"), kode_col="Saham", height=400, key="df_top10_day")
    st.divider()
    st.subheader(f"🌊 Top 10 Swing Trading")
    if not cands_swing_all.empty:
        show_swing = cands_swing_all.copy()
        show_swing["Nilai Transaksi"] = show_swing["Nilai Transaksi"].map(lambda x: f"Rp{x/1e9:,.1f} M")
        dataframe_with_chart(show_swing.drop(columns=["Chart"], errors="ignore"), kode_col="Saham", height=400, key="df_top10_swing")

# ============================================================================
# TAB 6: KALKULATOR
# ============================================================================
with t_kalk:
    st.subheader("🧮 Kalkulator Profit & Risiko")
    kalk_col1, kalk_col2 = st.columns(2)
    with kalk_col1:
        harga_beli_in = st.number_input("Harga Beli (Rp)", min_value=0.0, value=1000.0, step=1.0, key="hb")
        harga_jual_in = st.number_input("Harga Jual (Rp)", min_value=0.0, value=1050.0, step=1.0, key="hj")
        lot_in = st.number_input("Lot", min_value=1, value=10, step=1, key="lot")
        if st.button("Hitung Profit", type="primary", use_container_width=True):
            r = calc.profit_calculator(harga_beli_in, harga_jual_in, lot_in, 0.15, 0.25)
            st.metric("Total Untung/Rugi", f"Rp{r['untung_rugi_rp']:,.0f}", f"{r['untung_rugi_pct']:+.2f}%")
    with kalk_col2:
        modal_in = st.number_input("Total Modal (Rp)", min_value=0.0, value=10_000_000.0, step=500_000.0, key="modal")
        resiko_in = st.number_input("Resiko per Transaksi (%)", min_value=0.1, value=1.0, step=0.1, key="resiko")
        sl_in = st.number_input("Persen Stop Loss (%)", min_value=0.1, value=5.0, step=0.5, key="slpct")
        if st.button("Hitung Manajemen Risiko", type="primary", use_container_width=True):
            r2 = calc.risk_management_calculator(modal_in, resiko_in, sl_in, 2.0, None)
            if "error" not in r2:
                st.metric("Maksimal Beli (Rp)", f"Rp{r2['maksimal_beli_rp']:,.0f}")

# ============================================================================
# TAB 7: PERFORMANCE
# ============================================================================
with t_perf:
    if not gj.is_configured():
        st.warning("Performance butuh koneksi Google Sheets.")
    else:
        positions_perf = gj.load_positions()
        perf = gj.monthly_performance(positions_perf)
        if perf["n_closed"] > 0:
            st.markdown(f"**AKUMULASI PROFIT: {perf['cumulative_pct']:+.2f}%**")
            stats_perf = gj.summarize(positions_perf)
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Win Rate", f"{stats_perf['winrate']:.1f}%")
            p2.metric("Total WIN", stats_perf["win"])
            p3.metric("Total LOSS", stats_perf["loss"])
            p4.metric("Posisi OPEN", stats_perf["open"])

# ============================================================================
# TAB 8: JURNAL REAL (DENGAN AUTO-FILL)
# ============================================================================
with t_real:
    if not gj.is_configured():
        st.warning("Jurnal Real butuh koneksi Google Sheets.")
    else:
        sub1, sub2 = st.tabs(["➕ Catat Trade", "🔓 Tutup Posisi"])
        with sub1:
            st.markdown("**Catat posisi baru (OPEN)**")
            brokers_df = rj.load_brokers()
            broker_options = brokers_df["Sekuritas"].tolist() if not brokers_df.empty else ["Lainnya"]
            
            # === AUTO-FILL DARI KANDIDAT TERBAIK ===
            auto_data = None
            if 'auto_fill_trade' in st.session_state:
                auto_data = st.session_state['auto_fill_trade']
                st.success(f"🎯 Auto-fill aktif: **{auto_data['kode']}** ({auto_data['rekomendasi']})")
                with st.expander("📋 Detail Auto-fill", expanded=True):
                    st.write(f"**Entry:** Rp{auto_data['entry']:,.0f} | **SL:** Rp{auto_data['stop_loss']:,.0f} | **Target:** Rp{auto_data['target']:,.0f}")
                if st.button("🗑️ Batal Auto-fill", key="btn_cancel_autofill"):
                    del st.session_state['auto_fill_trade']
                    st.rerun()
                st.divider()
            
            fc1, fc2, fc3 = st.columns(3)
            tgl_entry = fc1.date_input("Tanggal Entry", value=datetime.now(), key="tgl_entry_rj")
            sekuritas_in = fc2.selectbox("Sekuritas", options=broker_options, key="sekuritas_rj")
            default_saham = auto_data['kode'] if auto_data else ""
            saham_in = fc3.text_input("Kode Saham", value=default_saham, key="saham_rj").upper()
            
            fc4, fc5 = st.columns(2)
            default_setup_idx = rj.SETUP_OPTIONS.index(auto_data['setup']) if auto_data and auto_data['setup'] in rj.SETUP_OPTIONS else 0
            setup_in = fc4.selectbox("Setup", options=rj.SETUP_OPTIONS, index=default_setup_idx, key="setup_rj")
            lot_in2 = fc5.number_input("Lot", min_value=1, value=auto_data['lot'] if auto_data else 10, step=1, key="lot_rj")
            
            fc6, fc7, fc8 = st.columns(3)
            entry_in2 = fc6.number_input("Entry (Rp)", min_value=0.0, value=auto_data['entry'] if auto_data else 0.0, step=1.0, key="entry_rj")
            sl_in2 = fc7.number_input("Stop Loss (Rp)", min_value=0.0, value=auto_data['stop_loss'] if auto_data else 0.0, step=1.0, key="sl_rj")
            target_in2 = fc8.number_input("Target (Rp)", min_value=0.0, value=auto_data['target'] if auto_data else 0.0, step=1.0, key="target_rj")
            
            default_catatan = f"Auto-fill dari Kandidat Terbaik - {auto_data['rekomendasi']}" if auto_data else ""
            catatan_in = st.text_area("Catatan", value=default_catatan, height=70, key="catatan_rj")
            
            if st.button("💾 Simpan Trade (OPEN)", type="primary", key="btn_open_rj"):
                if not saham_in or entry_in2 <= 0:
                    st.error("Kode saham dan Entry wajib diisi.")
                else:
                    no = rj.open_trade(tgl_entry.strftime("%Y-%m-%d"), sekuritas_in, saham_in, setup_in, entry_in2, sl_in2, target_in2, lot_in2, catatan_in)
                    st.success(f"Trade #{no} ({saham_in}) berhasil dicatat.")
                    if 'auto_fill_trade' in st.session_state:
                        del st.session_state['auto_fill_trade']
                    st.rerun()
        
        with sub2:
            trades_now = rj.load_trades()
            open_trades = trades_now[trades_now["Status"] == "OPEN"] if not trades_now.empty else pd.DataFrame()
            if open_trades.empty:
                st.info("Tidak ada posisi OPEN saat ini.")
            else:
                st.dataframe(open_trades[["No", "Saham", "Entry (Rp)", "Stop Loss (Rp)", "Target (Rp)", "Lot"]], use_container_width=True, hide_index=True)
                pilih_no = st.selectbox("Pilih nomor trade yang mau ditutup", options=open_trades["No"].tolist(), key="pilih_no_rj")
                exit_price_in = st.number_input("Harga Exit (Rp)", min_value=0.0, step=1.0, key="exit_price_rj")
                if st.button("🔓 Tutup Posisi Ini", type="primary", key="btn_close_rj"):
                    if exit_price_in <= 0:
                        st.error("Harga Exit wajib diisi.")
                    else:
                        ok, msg = rj.close_trade(pilih_no, datetime.now().strftime("%Y-%m-%d"), exit_price_in)
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)

# ============================================================================
# TAB 9: EQUITY
# ============================================================================
with t_equity:
    if not gj.is_configured():
        st.warning("Equity Tracking butuh koneksi Google Sheets.")
    else:
        equity_df = eq.load_equity()
        if equity_df.empty:
            st.info("Belum ada data equity. Isi snapshot pertama di tab 'Catat Snapshot'.")
        else:
            total_series = eq.total_equity_over_time(equity_df)
            latest_total = total_series["Total Equity (Rp)"].iloc[-1] if not total_series.empty else 0
            first_total = total_series["Total Equity (Rp)"].iloc[0] if not total_series.empty else 0
            total_return = ((latest_total / first_total - 1) * 100) if first_total > 0 else 0
            st.metric("Total Equity (Semua Sekuritas)", f"Rp{latest_total:,.0f}", f"{total_return:+.2f}%")
            st.dataframe(equity_df.sort_values("Tanggal", ascending=False), use_container_width=True, hide_index=True, height=400)

st.divider()
st.caption("⚠️ Data diambil dari Yahoo Finance. Bukan rekomendasi keuangan. Selalu lakukan riset & kelola risiko sendiri.")
