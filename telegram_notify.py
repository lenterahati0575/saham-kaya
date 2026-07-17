"""Kirim pesan ke Telegram lewat Bot API. Butuh BOT_TOKEN & CHAT_ID di st.secrets."""

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "BOT_TOKEN atau CHAT_ID belum diisi di secrets."
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "Terkirim."
        return False, f"Gagal ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Error: {e}"


def format_watchlist_message(df, signal_filter=("STRONG BUY", "BUY")) -> str:
    picks = df[df["Signal"].isin(signal_filter)].copy()
    if picks.empty:
        return "Tidak ada saham yang lolos filter hari ini."
    lines = [f"<b>📊 IDX Watchlist — {len(picks)} saham lolos filter</b>\n"]
    for _, row in picks.iterrows():
        emoji = "🟢🟢" if row["Signal"] == "STRONG BUY" else "🟢"
        lines.append(
            f"{emoji} <b>{row['Kode']}</b> — {row['Signal']} "
            f"(Score {row['Score']}) | Rp{row['Harga']:,.0f} "
            f"({row['Perubahan %']*100:+.2f}%) | {row['Status Breakout']}"
        )
    return "\n".join(lines)
