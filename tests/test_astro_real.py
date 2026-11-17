"""Posisi planet nyata (2026-11-17) - diverifikasi ke peristiwa astronomi yg diketahui, tanpa jaringan."""
from datetime import datetime

from astro_real import bujur_geosentris, konjungsi_planet, posisi_planet, selisih_sudut


def _sep(a, b, dt):
    return selisih_sudut(bujur_geosentris(a, dt), bujur_geosentris(b, dt))


class TestPosisiPlanetNyata:
    def test_konjungsi_peristiwa_diketahui(self):
        assert _sep("Jupiter", "Saturn", datetime(2020, 12, 21)) < 0.5     # konjungsi besar 21 Des 2020
        assert _sep("Mars", "Saturn", datetime(2020, 4, 1)) < 0.5          # ~31 Mar - 1 Apr 2020
        assert _sep("Venus", "Jupiter", datetime(2023, 3, 1)) < 2.0        # konjungsi dekat awal Mar 2023

    def test_posisi_17_nov_2026_beda_dari_hitungan_lama(self):
        p = posisi_planet(datetime(2026, 11, 17, 12))
        assert list(p) == ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        assert 120 <= p["Mars"] < 150 and 120 <= p["Jupiter"] < 150        # Leo (hitungan lama: Cancer, 90-120)
        assert 0 <= p["Saturn"] < 30                                       # Aries (hitungan lama: Aquarius ~328)
        assert 195 <= p["Venus"] < 210                                     # Libra (hitungan lama: Scorpio)
        assert all(0 <= v < 360 for v in p.values())

    def test_konjungsi_mars_jupiter_nyata_17_nov_2026(self):
        konj = konjungsi_planet(posisi_planet(datetime(2026, 11, 17, 12)))
        assert any(k.startswith("Mars-Jupiter") for k in konj)
        assert not any(k.startswith("Mars-Saturn") for k in konj)

    def test_selisih_sudut_membungkus_360(self):
        assert selisih_sudut(359.0, 1.0) == 2.0 and selisih_sudut(10.0, 190.0) == 180.0
        assert konjungsi_planet({"A": 359.0, "B": 3.0, "C": 180.0}, orb=10.0) == ["A-B (4.0°)"]
