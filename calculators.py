def profit_calculator(harga_beli, harga_jual, lot, komisi_beli, komisi_jual):
    """Kalkulator profit saham"""
    lembar = lot * 100
    total_beli = harga_beli * lembar * (1 + komisi_beli / 100)
    total_jual = harga_jual * lembar * (1 - komisi_jual / 100)
    untung_rugi_rp = total_jual - total_beli
    untung_rugi_pct = (untung_rugi_rp / total_beli) * 100 if total_beli > 0 else 0
    bep = total_beli / lembar / (1 - komisi_jual / 100) if lembar > 0 else 0

    return {
        "total_beli": total_beli,
        "total_jual": total_jual,
        "untung_rugi_rp": untung_rugi_rp,
        "untung_rugi_pct": untung_rugi_pct,
        "bep": bep,
    }

def risk_management_calculator(modal, resiko_pct, sl_pct, rr, harga_saham=None):
    """Kalkulator manajemen risiko"""
    if modal <= 0 or resiko_pct <= 0 or sl_pct <= 0:
        return {"error": "Modal, resiko, dan SL harus > 0"}

    resiko_rp = modal * (resiko_pct / 100)
    maksimal_beli_rp = resiko_rp / (sl_pct / 100)
    tp_pct = sl_pct * rr

    result = {
        "resiko_rp": resiko_rp,
        "maksimal_beli_rp": maksimal_beli_rp,
        "take_profit_pct": tp_pct,
        "dibatasi_modal": maksimal_beli_rp > modal,
    }

    if harga_saham and harga_saham > 0:
        lot = int(maksimal_beli_rp / (harga_saham * 100))
        lembar = lot * 100
        total_saham = harga_saham * lembar
        sl_price = harga_saham * (1 - sl_pct / 100)
        tp_price = harga_saham * (1 + tp_pct / 100)
        risiko_aktual = (harga_saham - sl_price) * lembar

        result.update({
            "lot": lot,
            "lembar": lembar,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "total_saham_rp": total_saham,
            "risiko_aktual_rp": risiko_aktual,
        })

    return result

def average_calculator(harga_awal, lot_awal, harga_tambah, lot_tambah):
    """Kalkulator average down/up"""
    if lot_awal <= 0 or lot_tambah <= 0:
        return {"error": "Lot harus > 0"}

    modal_awal = harga_awal * lot_awal * 100
    modal_tambah = harga_tambah * lot_tambah * 100
    total_lot = lot_awal + lot_tambah
    total_modal = modal_awal + modal_tambah
    avg_baru = total_modal / (total_lot * 100)

    tipe = "AVERAGE DOWN" if harga_tambah < harga_awal else ("AVERAGE UP" if harga_tambah > harga_awal else "HARGA SAMA")
    selisih_pct = ((avg_baru / harga_awal) - 1) * 100

    return {
        "avg_baru": avg_baru,
        "total_lot": total_lot,
        "total_modal": total_modal,
        "tipe": tipe,
        "selisih_pct": selisih_pct,
    }

def average_lot_simulator(harga_awal, lot_awal, target_avg, harga_tambah):
    """Simulasi lot tambahan untuk target average"""
    if harga_awal <= 0 or lot_awal <= 0 or target_avg <= 0 or harga_tambah <= 0:
        return {"error": "Semua nilai harus > 0"}

    modal_awal = harga_awal * lot_awal * 100
    target_total_modal = target_avg * lot_awal * 100  # approximation

    # Target: (modal_awal + lot_tambah * harga_tambah * 100) / ((lot_awal + lot_tambah) * 100) = target_avg
    # modal_awal + lot_tambah * harga_tambah * 100 = target_avg * (lot_awal + lot_tambah) * 100
    # modal_awal + lot_tambah * harga_tambah * 100 = target_avg * lot_awal * 100 + target_avg * lot_tambah * 100
    # lot_tambah * (harga_tambah * 100 - target_avg * 100) = target_avg * lot_awal * 100 - modal_awal

    numerator = target_avg * lot_awal * 100 - modal_awal
    denominator = (harga_tambah - target_avg) * 100

    if denominator == 0:
        return {"error": "Harga tambah sama dengan target average"}

    lot_tambahan = numerator / denominator
    if lot_tambahan < 0:
        return {"error": "Tidak mungkin mencapai target average dengan harga tersebut"}

    lot_tambahan = round(lot_tambahan, 0)
    modal_tambahan = lot_tambahan * harga_tambah * 100
    total_lot = lot_awal + lot_tambahan
    avg_hasil = (modal_awal + modal_tambahan) / (total_lot * 100)

    return {
        "lot_tambahan": int(lot_tambahan),
        "modal_tambahan_dibutuhkan": modal_tambahan,
        "avg_hasil": avg_hasil,
        "total_lot_hasil": total_lot,
    }
