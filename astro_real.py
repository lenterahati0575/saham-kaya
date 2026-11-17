"""Posisi planet NYATA (geosentris, tropis) dari elemen Keplerian JPL - E.M. Standish, "Keplerian Elements for Approximate
Positions of the Major Planets" (Tabel 1, valid 1800-2050 M). Python murni, tanpa unduhan ephemeris.

Dibuat 2026-11-17 menggantikan hitungan lama di app.py (astro_cycle_analysis) yg memakai "hari sejak 2000-01-01 mod periode
orbit" - itu menganggap SEMUA planet berada di 0 derajat pada 1 Jan 2000 & orbit lingkaran heliosentris, hasilnya meleset
15-50 derajat dari posisi sebenarnya (mis. Mars/Jupiter tampil di Cancer padahal di Leo, Saturn di Aquarius padahal Aries).

AKURASI: ~1 derajat utk planet luar, lebih baik utk planet dalam (cukup utk tanda zodiak & konjungsi kasar; BUKAN ephemeris
resmi). Diverifikasi ke peristiwa yg diketahui: konjungsi Jupiter-Saturn 21 Des 2020 (0,13 deg), Mars-Saturn 1 Apr 2020
(0,10 deg), Venus-Jupiter 1 Mar 2023 (1,17 deg). Hasil uji statistik: posisi/konjungsi planet TIDAK terbukti memprediksi IHSG
(README > "Siklus Planet" & "Mengapa Tab Astronacci Membingungkan")."""
import math
from datetime import datetime

# (a, da, e, de, I, dI, L, dL, varpi, dvarpi, Omega, dOmega)  - nilai awal J2000 + laju per abad
_EL = {
    "earth":   (1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668, 100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0),
    "mercury": (0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749, 252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081),
    "venus":   (0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890, 181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418),
    "mars":    (1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131, -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343),
    "jupiter": (5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714, 34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106),
    "saturn":  (9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609, 49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794),
}
PLANET_DEFAULT = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
_R = math.radians


def _julian_date(dt: datetime) -> float:
    return 2440587.5 + (dt - datetime(1970, 1, 1)).total_seconds() / 86400.0


def _helio_xyz(nama: str, T: float):
    a0, da, e0, de, i0, di, l0, dl, w0, dw, o0, do = _EL[nama]
    a, e, inc, L, wbar, om = a0 + da * T, e0 + de * T, i0 + di * T, l0 + dl * T, w0 + dw * T, o0 + do * T
    w = wbar - om
    M = (L - wbar + 180.0) % 360.0 - 180.0
    E = M + math.degrees(e) * math.sin(_R(M))
    for _ in range(30):                                   # persamaan Kepler (Newton-Raphson)
        dE = (M - (E - math.degrees(e) * math.sin(_R(E)))) / (1.0 - e * math.cos(_R(E)))
        E += dE
        if abs(dE) < 1e-10:
            break
    xp, yp = a * (math.cos(_R(E)) - e), a * math.sqrt(1.0 - e * e) * math.sin(_R(E))
    cw, sw, co, so, ci, si = math.cos(_R(w)), math.sin(_R(w)), math.cos(_R(om)), math.sin(_R(om)), math.cos(_R(inc)), math.sin(_R(inc))
    return ((cw * co - sw * so * ci) * xp + (-sw * co - cw * so * ci) * yp,
            (cw * so + sw * co * ci) * xp + (-sw * so + cw * co * ci) * yp,
            (sw * si) * xp + (cw * si) * yp)


def bujur_geosentris(planet: str, dt: datetime) -> float:
    """Bujur ekliptika geosentris (0-360 deg, tropis) planet pada `dt` (naive, dianggap UTC)."""
    T = (_julian_date(dt) - 2451545.0) / 36525.0
    px, py, _ = _helio_xyz(planet.lower(), T)
    ex, ey, _ = _helio_xyz("earth", T)
    return math.degrees(math.atan2(py - ey, px - ex)) % 360.0


def posisi_planet(dt: datetime, planets=PLANET_DEFAULT) -> dict:
    """{nama planet: bujur geosentris (deg, 1 desimal)} - struktur SAMA dgn hitungan lama di app.py."""
    return {p: round(bujur_geosentris(p, dt), 1) for p in planets}


def selisih_sudut(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def konjungsi_planet(posisi: dict, orb: float = 15.0) -> list:
    """Pasangan planet dgn selisih bujur < `orb` deg -> list string "Mars-Jupiter (0.4°)" (format sama dgn app lama)."""
    nama = list(posisi)
    out = []
    for i in range(len(nama)):
        for j in range(i + 1, len(nama)):
            s = selisih_sudut(posisi[nama[i]], posisi[nama[j]])
            if s < orb:
                out.append(f"{nama[i]}-{nama[j]} ({s:.1f}°)")
    return out
