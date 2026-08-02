import streamlit as st
import requests

def send_telegram_message(message):
    """Kirim pesan ke Telegram"""
    try:
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False

def format_watchlist_message(df):
    """Format watchlist untuk Telegram"""
    lines = ["📊 *Watchlist Hari Ini*"]
    for _, row in df.head(10).iterrows():
        lines.append(f"• {row['Kode']} — {row['Signal']} @ Rp{row['Harga']:,.0f}")
    return "\n".join(lines)
