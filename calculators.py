"""
Dua kalkulator saham:
1. profit_calculator      - hitung untung/rugi transaksi (harga beli/jual, lot, komisi)
2. risk_management_calc   - hitung ukuran posisi berdasar modal & toleransi risiko

PERBAIKAN dibanding referensi gambar:
- profit_calculator: tambah BEP (Break Even Price) - harga jual minimum supaya impas
  setelah komisi, sesuatu yang sering dilupakan trader pemula tapi penting.
- risk_management_calc: tambah input Harga Saham (opsional) supaya "Take Profit" dan
  "Maksimal Beli" bisa dikonversi jadi harga & jumlah LOT riil (dibulatkan ke bawah
  ke kelipatan 1 lot = 100 lembar, sesuai aturan bursa) - bukan cuma angka Rupiah
  mentah yang di gambar referensi tidak jelas cara pakainya.
- Keduanya bisa auto-isi dari saham yang sedang dipilih di dashboard (entry/harga live).
"""

import math

LEMBAR_PER_LOT = 100


def profit_calculator(harga_beli: float, harga_jual: float, lot: float,
                       komisi_beli_pct: float, komisi_jual_pct: float) -> dict:
    lembar = lot * LEMBAR_PER_LOT
    total_beli = harga_beli * lembar * (1 + komisi_beli_pct / 100)
    total_jual = harga_jual * lembar * (1 - komisi_jual_pct / 100)
    untung_rugi = total_jual - total_beli
    untung_rugi_pct = (untung_rugi / total_beli * 100) if total_beli > 0 else 0

    # Break Even Price: harga jual minimum supaya impas setelah komisi beli & jual
    bep = harga_beli * (1 + komisi_beli_pct / 100) / (1 - komisi_jual_pct / 100) if komisi_jual_pct < 100 else None

    return {
        "total_beli": total_beli,
        "total_jual": total_jual,
        "untung_rugi_rp": untung_rugi,
        "untung_rugi_pct": untung_rugi_pct,
        "bep": bep,
        "lembar": lembar,
    }


def average_calculator(harga_awal: float, lot_awal: float, harga_tambahan: float, lot_tambahan: float) -> dict:
    """Hitung harga rata-rata baru setelah beli tambahan (average down kalau harga_tambahan
    lebih rendah dari harga_awal, average up kalau lebih tinggi). Rumus tertimbang standar:
    Avg Baru = (Modal Awal + Modal Tambahan) / (Lot Awal + Lot Tambahan)."""
    lembar_awal = lot_awal * LEMBAR_PER_LOT
    lembar_tambahan = lot_tambahan * LEMBAR_PER_LOT
    modal_awal = harga_awal * lembar_awal
    modal_tambahan = harga_tambahan * lembar_tambahan
    total_lembar = lembar_awal + lembar_tambahan
    if total_lembar <= 0:
        return {"error": "Total lot harus lebih dari 0."}

    avg_baru = (modal_awal + modal_tambahan) / total_lembar
    selisih_pct = (avg_baru - harga_awal) / harga_awal * 100 if harga_awal > 0 else 0
    tipe = "AVERAGE DOWN" if harga_tambahan < harga_awal else (
        "AVERAGE UP" if harga_tambahan > harga_awal else "HARGA SAMA")

    return {
        "avg_baru": avg_baru,
        "total_lot": total_lembar / LEMBAR_PER_LOT,
        "total_modal": modal_awal + modal_tambahan,
        "selisih_pct": selisih_pct,
        "tipe": tipe,
    }


def average_lot_simulator(harga_awal: float, lot_awal: float, target_avg: float, harga_tambahan: float) -> dict:
    """Simulasi: berapa lot tambahan dibutuhkan di harga_tambahan supaya rata-rata turun/naik
    ke target_avg. Rumus dari referensi standar kalkulator average down:
    Lot Tambahan = CEIL((Modal Awal/100 - Target Avg x Lot Awal) / (Target Avg - Harga Tambahan))"""
    if target_avg == harga_tambahan:
        return {"error": "Target rata-rata tidak boleh sama persis dengan harga beli tambahan."}

    lembar_awal = lot_awal * LEMBAR_PER_LOT
    modal_awal = harga_awal * lembar_awal

    # Validasi arah: average down butuh target_avg di ANTARA harga_tambahan dan harga_awal
    if harga_tambahan < harga_awal and not (harga_tambahan < target_avg < harga_awal):
        return {"error": f"Untuk average DOWN, target rata-rata harus di antara "
                          f"Rp{harga_tambahan:,.0f} dan Rp{harga_awal:,.0f}."}
    if harga_tambahan > harga_awal and not (harga_awal < target_avg < harga_tambahan):
        return {"error": f"Untuk average UP, target rata-rata harus di antara "
                          f"Rp{harga_awal:,.0f} dan Rp{harga_tambahan:,.0f}."}

    lot_tambahan_raw = (modal_awal / LEMBAR_PER_LOT - target_avg * lot_awal) / (target_avg - harga_tambahan)
    lot_tambahan = math.ceil(lot_tambahan_raw)
    if lot_tambahan <= 0:
        return {"error": "Hasil perhitungan tidak valid (lot tambahan <= 0) - cek kembali angka target."}

    hasil = average_calculator(harga_awal, lot_awal, harga_tambahan, lot_tambahan)
    modal_tambahan_dibutuhkan = harga_tambahan * lot_tambahan * LEMBAR_PER_LOT
    return {
        "lot_tambahan": lot_tambahan,
        "modal_tambahan_dibutuhkan": modal_tambahan_dibutuhkan,
        "avg_hasil": hasil["avg_baru"],
        "total_lot_hasil": hasil["total_lot"],
    }


def risk_management_calculator(total_modal: float, resiko_pct: float, sl_pct: float,
                                rr_ratio: float, harga_saham: float | None = None) -> dict:
    resiko_rp = total_modal * (resiko_pct / 100)
    if sl_pct <= 0:
        return {"error": "Persen Stop Loss harus lebih dari 0."}

    maksimal_beli_rp = resiko_rp / (sl_pct / 100)
    dibatasi_modal = maksimal_beli_rp > total_modal
    maksimal_beli_rp = min(maksimal_beli_rp, total_modal)  # tidak mungkin beli melebihi modal yang ada

    take_profit_pct = sl_pct * rr_ratio

    out = {
        "resiko_rp": resiko_rp,
        "maksimal_beli_rp": maksimal_beli_rp,
        "take_profit_pct": take_profit_pct,
        "dibatasi_modal": dibatasi_modal,
    }

    if harga_saham and harga_saham > 0:
        lembar_mentah = maksimal_beli_rp / harga_saham
        lot = math.floor(lembar_mentah / LEMBAR_PER_LOT)  # dibulatkan KE BAWAH, sesuai aturan 1 lot = 100 lembar
        lembar = lot * LEMBAR_PER_LOT
        total_saham_rp = lembar * harga_saham
        stop_loss_price = harga_saham * (1 - sl_pct / 100)
        take_profit_price = harga_saham * (1 + take_profit_pct / 100)
        out.update({
            "lot": lot,
            "lembar": lembar,
            "total_saham_rp": total_saham_rp,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "risiko_aktual_rp": lembar * (harga_saham - stop_loss_price),
        })
    return out
