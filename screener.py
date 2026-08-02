import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

# Default parameters
DEFAULT_PARAMS = {
    "min_value_traded": 3_000_000_000,
    "crash_veto": -0.05,
    "donchian_lookback": 20,
    "score_strong_buy": 7,
    "score_buy": 4,
    "score_sell": -2,
    "score_strong_sell": -4,
}

# Daftar saham IDX lengkap (sample)
IDX_TICKERS = [
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "PGAS", "PTBA", "ANTM", "INDF",
    "ICBP", "KLBF", "MYOR", "GGRM", "HM Sampoerna", "EXCL", "TBIG", "SRIL", "ACES", "AMRT",
    "ARTO", "AUTO", "BALI", "BANK", "BAPA", "BATA", "BAYU", "BBHI", "BBKP", "BBLD",
    "BBMD", "BBNI", "BBRM", "BBSI", "BBTN", "BDMN", "BEKS", "BEST", "BFIN", "BGTG",
    "BIKA", "BIPI", "BIPP", "BIRD", "BISI", "BJBR", "BJTM", "BKSL", "BLTA", "BLTZ",
    "BMAS", "BMTR", "BORN", "BRMS", "BRNA", "BRPT", "BSDE", "BSIM", "BSSR", "BTPN",
    "BUDI", "BUKA", "BUMI", "BUVA", "BVIC", "BWPT", "BYAN", "CAMP", "CANI", "CARS",
    "CASS", "CEKA", "CENT", "CFIN", "CINT", "CITA", "CITY", "CLAY", "CLEO", "CMNP",
    "CNKO", "CNTX", "COWL", "CPIN", "CPRI", "CSAP", "CTRA", "CTTH", "DADA", "DART",
    "DAYA", "DEWI", "DGIK", "DILD", "DKFT", "DLTA", "DMAS", "DOID", "DPNS", "DSFI",
    "DSNG", "DSSA", "DUTI", "DVLA", "DYAN", "ECII", "EDGE", "EKA", "EKAD", "ELSA",
    "ELTY", "EMTK", "ENRG", "EPMT", "ERAA", "ESSA", "ESTI", "ETWA", "EXCL", "FAPA",
    "FASW", "FILM", "FINN", "FIRE", "FISH", "FMII", "FORU", "FPNI", "FREN", "GEMA",
    "GEMS", "GGRM", "GIAA", "GJTL", "GMTD", "GOLD", "GOLL", "GOOD", "GPRA", "GSMF",
    "GTBO", "GWSA", "GYRO", "HADE", "HDFA", "HEAL", "HERO", "HEXA", "HITS", "HMSP",
    "HOPE", "HOTL", "HRUM", "IATA", "IBFN", "IBST", "ICBP", "ICON", "IDEA", "IDPR",
    "IFII", "IFSH", "IGAR", "IIKP", "IKAI", "IKBI", "IMAS", "IMJS", "IMPC", "INAF",
    "INAI", "INCI", "INDF", "INDO", "INDR", "INDS", "INDX", "INKP", "INOV", "INPC",
    "INPP", "INRU", "INTA", "INTD", "INTP", "IPOL", "ISAT", "ISSP", "ITMA", "ITMG",
    "JAST", "JAWA", "JECC", "JIHD", "JKON", "JKSW", "JMAS", "JPFA", "JRPT", "JSKY",
    "JSMR", "JTPE", "KARW", "KBLI", "KBLV", "KBRI", "KDSI", "KEJU", "KIAS", "KICI",
    "KIJA", "KING", "KJEN", "KKGI", "KOBU", "KOIN", "KONI", "KOPI", "KOTA", "KPIG",
    "KRAH", "KRAS", "KREN", "LAPD", "LCGP", "LEAD", "LINK", "LION", "LMAS", "LMPI",
    "LMSH", "LPCK", "LPGI", "LPIN", "LPKR", "LPLI", "LPPF", "LRNA", "LSIP", "LTLS",
    "MABA", "MAGP", "MAIN", "MAMI", "MAPA", "MAPB", "MAPI", "MARI", "MARK", "MASA",
    "MAYA", "MBAP", "MBSS", "MBTO", "MCAS", "MCOL", "MDIA", "MDKA", "MDLN", "MEGA",
    "MERK", "META", "MFIN", "MGLV", "MICE", "MINA", "MIRA", "MITI", "MKNT", "MLBI",
    "MLIA", "MLPT", "MMLP", "MNCN", "MPMX", "MPPA", "MRAT", "MREI", "MSIN", "MSKY",
    "MTDL", "MTFN", "MTLA", "MTSM", "MYOH", "MYOR", "MYTX", "NASA", "NELY", "NFCX",
    "NICK", "NIKL", "NIPS", "NOBU", "NRCA", "NUSA", "OBCI", "OBLI", "OCAP", "OILS",
    "OMRE", "OPMS", "PADI", "PALM", "PANI", "PANR", "PANS", "PBID", "PBRX", "PBSA",
    "PDES", "PEGE", "PEHA", "PGAS", "PGLI", "PGUN", "PICO", "PJAA", "PKPK", "PLAS",
    "PLIN", "PNBN", "PNBS", "PNIN", "PNLF", "PNSE", "POLA", "POLI", "POLL", "PORT",
    "POSA", "POWR", "PPRO", "PRAS", "PSAB", "PSDN", "PSGO", "PSKT", "PSSI", "PTBA",
    "PTIS", "PTPP", "PTPW", "PUDP", "PWON", "PYFA", "RAJA", "RALS", "RANC", "RBMS",
    "RDTX", "REAL", "RELI", "RICY", "RIGS", "RIMO", "RISE", "RODA", "ROTI", "RUIS",
    "SAFE", "SAME", "SAMF", "SAPX", "SATU", "SBAT", "SCCO", "SCMA", "SDMU", "SDPC",
    "SEMA", "SGER", "SGRO", "SHID", "SHIP", "SIDO", "SILO", "SIMA", "SIMP", "SINI",
    "SIPD", "SKBM", "SKLT", "SLIG", "SMAR", "SMBR", "SMCB", "SMGR", "SMMA", "SMMT",
    "SMRA", "SMSM", "SOCI", "SOHO", "SOLL", "SONA", "SPMA", "SPTO", "SQMI", "SRAJ",
    "SRIL", "SRSN", "SRTG", "SSIA", "SSMS", "STAR", "STTP", "SULI", "SUPR", "SURE",
    "SWAT", "TAMU", "TARA", "TAXI", "TBLA", "TBMS", "TCID", "TELE", "TFCO", "TGKA",
    "TGRA", "TIFA", "TINS", "TIRA", "TKIM", "TLKM", "TMAS", "TOBA", "TOLL", "TPIA",
    "TPMA", "TRAM", "TRIL", "TRIM", "TRIO", "TRIS", "TRJA", "TRST", "TRUE", "TRUK",
    "TSPC", "TURI", "ULTJ", "UNIC", "UNIQ", "UNSP", "UNTR", "UNVR", "VICI", "VICO",
    "VIDO", "VIVA", "VOKS", "VRNA", "WAPO", "WEGE", "WICO", "WIIM", "WIKA", "WINS",
    "WOMF", "WOOD", "WOWS", "WSBP", "WTON", "YELO", "YPAS", "YULE", "ZBRA", "ZINC",
]

def load_ticker_universe():
    """Load universe saham IDX"""
    data = []
    for kode in IDX_TICKERS[:615]:
        data.append({"Kode": kode, "Nama": f"{kode} Indonesia"})
    return pd.DataFrame(data)

def fetch_price_history(tickers, period="6mo"):
    """Fetch harga historis dari Yahoo Finance"""
    price_data = {}
    for kode in tickers:
        try:
            ticker = yf.Ticker(f"{kode}.JK")
            hist = ticker.history(period=period)
            if not hist.empty and len(hist) > 20:
                price_data[kode] = hist
        except Exception:
            pass
    return price_data

def _donchian_levels(df, lookback=20):
    """Hitung Donchian Channel levels"""
    if df is None or len(df) < lookback:
        return 0, 0
    high = float(df["High"].tail(lookback).max())
    low = float(df["Low"].tail(lookback).min())
    return high, low

def build_screener_table(price_data, universe, params):
    """Build tabel screening"""
    rows = []
    for _, row in universe.iterrows():
        kode = row["Kode"]
        df = price_data.get(kode)
        if df is None or len(df) < 5:
            continue

        close = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) > 1 else close
        change = (close - prev) / prev if prev > 0 else 0
        volume = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0
        vol_avg = df["Volume"].tail(20).mean() if "Volume" in df.columns and len(df) >= 20 else volume
        vol_ratio = volume / vol_avg if vol_avg > 0 else 1
        value_traded = close * volume

        # Donchian
        dh, dl = _donchian_levels(df, params.get("donchian_lookback", 20))

        # Signal scoring (simplified)
        score = 0
        if close > df["Close"].rolling(20).mean().iloc[-1]:
            score += 3
        if vol_ratio > 1.5:
            score += 2
        if change > 0.02:
            score += 2

        if score >= params.get("score_strong_buy", 7):
            signal = "STRONG BUY"
        elif score >= params.get("score_buy", 4):
            signal = "BUY"
        elif score <= params.get("score_strong_sell", -4):
            signal = "STRONG SELL"
        elif score <= params.get("score_sell", -2):
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # Trend
        ma20 = df["Close"].rolling(20).mean().iloc[-1] if len(df) >= 20 else close
        trend = "UP" if close > ma20 else "DOWN"

        # Smart Money (dummy)
        sm = "ACCUMULATING" if vol_ratio > 1.5 and close > ma20 else "DISTRIBUTING" if vol_ratio > 1.5 else "NEUTRAL"

        # Momentum
        momentum = "BULLISH" if change > 0.02 else "BEARISH" if change < -0.02 else "NEUTRAL"

        # Breakout status
        status = "BREAKOUT" if close >= dh * 0.995 else "NORMAL"

        # Quality
        quality = "HIGH" if score >= 6 else "MODERATE" if score >= 3 else "LOW"
        q_score = min(10, score / 2)

        rows.append({
            "Kode": kode,
            "Nama": row["Nama"],
            "Harga": close,
            "Perubahan %": change,
            "Volume Ratio": vol_ratio,
            "Value Traded (Rp)": value_traded,
            "Donchian High": dh,
            "Donchian Low": dl,
            "Signal": signal,
            "Score": score,
            "Trend": trend,
            "Smart Money": sm,
            "Momentum": momentum,
            "Status Breakout": status,
            "Quality": quality,
            "Quality Score": q_score,
            "Rekomendasi": "SWING TRADE" if score >= 5 else "DAY TRADE" if score >= 3 else "WAIT",
            "Layak Likuiditas": value_traded >= params.get("min_value_traded", 3e9),
        })

    return pd.DataFrame(rows)

def build_trade_candidates(table, price_data, lookback, min_rr, top_n=10):
    """Build kandidat trading dengan RR calculation"""
    if table.empty:
        return pd.DataFrame()

    cands = []
    for _, row in table.iterrows():
        kode = row["Kode"]
        df = price_data.get(kode)
        if df is None or len(df) < lookback + 2:
            continue

        entry = float(row["Harga"])
        hist = df.iloc[-(lookback + 1):-1]
        dh = float(hist["High"].max())
        dl = float(hist["Low"].min())

        sl = dl
        target = dh + (dh - dl)
        risk = entry - sl
        reward = target - entry
        rr = reward / risk if risk > 0 else 0

        if rr >= min_rr and risk > 0:
            cands.append({
                "Saham": kode,
                "Entry": entry,
                "Stop Loss": sl,
                "Target": target,
                "RR": round(rr, 2),
                "Nilai Transaksi": row["Value Traded (Rp)"],
            })

    df_cands = pd.DataFrame(cands)
    if not df_cands.empty:
        df_cands = df_cands.sort_values("RR", ascending=False).head(top_n)
    return df_cands

def classify_daytrading_tipe():
    """Klasifikasi tipe day trading berdasarkan waktu"""
    hour = datetime.now().hour
    if hour < 12:
        return "BPJS"  # Beli Pagi Jual Sore
    else:
        return "BSJP"  # Beli Sore Jual Pagi

def fetch_ihsg_history(period="1y"):
    """Fetch data IHSG"""
    try:
        ticker = yf.Ticker("^JKSE")
        hist = ticker.history(period=period)
        return hist
    except Exception:
        return pd.DataFrame()

def market_regime(ihsg_hist):
    """Analisis regime pasar IHSG"""
    if ihsg_hist is None or ihsg_hist.empty or len(ihsg_hist) < 50:
        return {"status": "UNKNOWN", "close": 0, "ma": 0}

    close = float(ihsg_hist["Close"].iloc[-1])
    ma50 = float(ihsg_hist["Close"].rolling(50).mean().iloc[-1])

    if close > ma50:
        status = "BULLISH"
    else:
        status = "BEARISH"

    return {"status": status, "close": close, "ma": ma50}


def gann_square_of_9(price):
    """Hitung Gann Square of 9 untuk harga saham"""
    import math
    if price <= 0:
        return {"error": "Harga harus > 0"}

    # Square root method
    sr = math.sqrt(price)

    # Key angles: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    levels = {}

    for angle in angles:
        # Gann formula: (sqrt(price) + angle/360)^2
        factor = angle / 360.0
        level_price = (sr + factor) ** 2
        levels[f"{angle}°"] = round(level_price, 2)

    # Support and resistance
    support = levels.get("315°", price * 0.95)
    resistance = levels.get("45°", price * 1.05)

    return {
        "base_price": price,
        "square_root": round(sr, 4),
        "levels": levels,
        "support": support,
        "resistance": resistance,
        "cardinal": {
            "0°": levels.get("0°"),
            "90°": levels.get("90°"),
            "180°": levels.get("180°"),
            "270°": levels.get("270°"),
        },
        "diagonal": {
            "45°": levels.get("45°"),
            "135°": levels.get("135°"),
            "225°": levels.get("225°"),
            "315°": levels.get("315°"),
        }
    }

def time_cycle_analysis(df, lookback=60):
    """Analisis time cycle dari data historis"""
    if df is None or len(df) < lookback:
        return {"error": "Data tidak cukup"}

    close = df["Close"].tail(lookback)

    # Hitung cycle menggunakan FFT-like approach (simplified)
    import numpy as np

    returns = close.pct_change().dropna()
    if len(returns) < 10:
        return {"error": "Data tidak cukup untuk analisis cycle"}

    # Simple cycle detection using autocorrelation
    autocorr = []
    for lag in range(1, min(30, len(returns)//2)):
        corr = returns.autocorr(lag=lag)
        autocorr.append((lag, corr if not np.isnan(corr) else 0))

    # Find dominant cycle
    autocorr_sorted = sorted(autocorr, key=lambda x: abs(x[1]), reverse=True)
    dominant_cycle = autocorr_sorted[0][0] if autocorr_sorted else 7

    # Next cycle dates
    from datetime import datetime, timedelta
    last_date = df.index[-1]
    next_cycle = last_date + timedelta(days=dominant_cycle)

    return {
        "dominant_cycle_days": dominant_cycle,
        "cycle_strength": round(abs(autocorr_sorted[0][1]), 3) if autocorr_sorted else 0,
        "last_date": last_date.strftime("%Y-%m-%d"),
        "next_cycle_date": next_cycle.strftime("%Y-%m-%d"),
        "autocorrelation": autocorr[:5],
        "trend_alignment": "BULLISH" if close.iloc[-1] > close.iloc[-dominant_cycle] else "BEARISH",
    }

def astro_cycle_analysis(date=None):
    """Analisis astro-cycle (simplified)"""
    from datetime import datetime
    import math

    if date is None:
        date = datetime.now()

    # Moon phase calculation (simplified)
    # Known new moon: 2000-01-06
    known_new_moon = datetime(2000, 1, 6)
    days_since = (date - known_new_moon).days
    lunar_cycle = 29.53059
    moon_age = days_since % lunar_cycle

    # Phase: 0-7.4 (new), 7.4-14.8 (waxing), 14.8-22.1 (full), 22.1-29.5 (waning)
    if moon_age < 7.4:
        phase = "New Moon"
        sentiment = "ACCUMULATION"
    elif moon_age < 14.8:
        phase = "Waxing Crescent"
        sentiment = "BULLISH"
    elif moon_age < 22.1:
        phase = "Full Moon"
        sentiment = "DISTRIBUTION"
    else:
        phase = "Waning Crescent"
        sentiment = "BEARISH"

    # Mercury retrograde (simplified approximation)
    # Mercury retrograde ~3-4 times per year, ~3 weeks each
    # Approximate: check if day of year falls in known retrograde windows
    doy = date.timetuple().tm_yday
    # Simplified: retrograde windows (approximate for 2024-2026)
    retrograde_windows = [
        (1, 25),    # Jan
        (50, 75),   # Feb-Mar
        (120, 145), # Apr-May
        (190, 215), # Jul
        (240, 265), # Aug-Sep
        (300, 325), # Oct-Nov
    ]

    is_mercury_retrograde = any(start <= doy <= end for start, end in retrograde_windows)

    return {
        "date": date.strftime("%Y-%m-%d"),
        "moon_phase": phase,
        "moon_age_days": round(moon_age, 1),
        "sentiment": sentiment,
        "mercury_retrograde": is_mercury_retrograde,
        "mercury_advice": "HATI-HATI trading" if is_mercury_retrograde else "Normal",
    }

def analyze_ihsg_gann(ihsg_hist):
    """Analisis Gann + Time Cycle untuk IHSG"""
    if ihsg_hist is None or ihsg_hist.empty:
        return None

    close = float(ihsg_hist["Close"].iloc[-1])

    gann = gann_square_of_9(close)
    cycle = time_cycle_analysis(ihsg_hist)
    astro = astro_cycle_analysis()

    return {
        "gann": gann,
        "current": {
            "price": close,
            "date": ihsg_hist.index[-1].strftime("%Y-%m-%d"),
        },
        "cycle": cycle,
        "astro": astro,
    }
