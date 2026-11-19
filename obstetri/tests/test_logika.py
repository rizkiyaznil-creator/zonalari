"""Uji logika yang menentukan: usia kehamilan, pencocokan nama, dan penyaringan berkas.

Dijalankan tanpa basis data maupun jaringan:

    docker compose run --rm -v ./tests:/app/tests app python -m unittest discover -s tests
"""

from __future__ import annotations

import datetime as dt
import unittest

from models import Patient
from routers.imports import _normalkan
from services import berkas


class UjiUsiaKehamilan(unittest.TestCase):
    def setUp(self):
        self.pasien = Patient(mrn="X", name="Uji", hpht=dt.date(2026, 2, 20))

    def test_taksiran_persalinan_naegele(self):
        # HPHT + 280 hari
        self.assertEqual(
            self.pasien.taksiran_persalinan, dt.date(2026, 11, 27)
        )

    def test_usia_kehamilan_dihitung_dari_hpht(self):
        self.assertEqual(
            self.pasien.usia_kehamilan(dt.date(2026, 11, 19)), (38, 6)
        )

    def test_tepat_pada_hpht_adalah_nol(self):
        self.assertEqual(self.pasien.usia_kehamilan(dt.date(2026, 2, 20)), (0, 0))

    def test_tanggal_sebelum_hpht_tidak_masuk_akal(self):
        self.assertIsNone(self.pasien.usia_kehamilan(dt.date(2026, 2, 19)))

    def test_tanpa_hpht_tidak_bisa_dihitung(self):
        tanpa = Patient(mrn="Y", name="Uji", hpht=None)
        self.assertIsNone(tanpa.usia_kehamilan(dt.date(2026, 11, 19)))
        self.assertIsNone(tanpa.taksiran_persalinan)


class UjiRingkasanObstetri(unittest.TestCase):
    def test_gpa_lengkap(self):
        self.assertEqual(
            Patient(mrn="X", name="U", gravida=2, para=1, abortus=0).gpa, "G2P1A0"
        )

    def test_gpa_sebagian(self):
        self.assertEqual(Patient(mrn="X", name="U", gravida=3).gpa, "G3")

    def test_gpa_kosong(self):
        self.assertEqual(Patient(mrn="X", name="U").gpa, "-")


class UjiPenyeragamanNama(unittest.TestCase):
    def test_sapaan_dibuang(self):
        self.assertEqual(_normalkan("NY SITI AMINAH"), "SITI AMINAH")
        self.assertEqual(_normalkan("Ny. Siti Aminah"), "SITI AMINAH")

    def test_caret_jadi_spasi(self):
        self.assertEqual(_normalkan("dewi^lestari"), "DEWI LESTARI")

    def test_tanda_baca_dan_spasi_berlebih(self):
        self.assertEqual(_normalkan("  Ratna,  Sari   Dewi "), "RATNA SARI DEWI")

    def test_kosong_tidak_meledak(self):
        self.assertEqual(_normalkan(""), "")
        self.assertEqual(_normalkan(None), "")


class UjiPenyaringanBerkas(unittest.TestCase):
    """Isi berkas yang diperiksa, bukan namanya — nama mudah dipalsukan."""

    def test_pdf_diterima(self):
        self.assertEqual(
            berkas.periksa("rekaman.pdf", "application/pdf", b"%PDF-1.4\n..."), ".pdf"
        )

    def test_png_dikenali_walau_dinamai_pdf(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        self.assertEqual(berkas.periksa("rekaman.pdf", "application/pdf", png), ".png")

    def test_berkas_bukan_gambar_ditolak(self):
        with self.assertRaises(berkas.BerkasDitolak):
            berkas.periksa("jahat.pdf", "application/pdf", b"MZ\x90\x00 program")

    def test_berkas_kosong_ditolak(self):
        with self.assertRaises(berkas.BerkasDitolak):
            berkas.periksa("kosong.pdf", "application/pdf", b"")

    def test_akhiran_asing_ditolak(self):
        with self.assertRaises(berkas.BerkasDitolak):
            berkas.periksa("skrip.exe", "application/octet-stream", b"MZ\x90\x00")


class UjiTebakWaktu(unittest.TestCase):
    def test_tanggal_dan_jam(self):
        self.assertEqual(
            berkas.tebak_waktu("CTG_20261119_0915.pdf"),
            dt.datetime(2026, 11, 19, 9, 15),
        )

    def test_tanggal_bertanda_hubung(self):
        self.assertEqual(
            berkas.tebak_waktu("2026-11-19 09-15.pdf"),
            dt.datetime(2026, 11, 19, 9, 15),
        )

    def test_tanggal_saja(self):
        self.assertEqual(
            berkas.tebak_waktu("CTG_20261119.pdf"), dt.datetime(2026, 11, 19)
        )

    def test_tanpa_pola_waktu(self):
        self.assertIsNone(berkas.tebak_waktu("rekaman-terakhir.pdf"))

    def test_tanggal_mustahil_tidak_dipaksakan(self):
        self.assertIsNone(berkas.tebak_waktu("CTG_20261345.pdf"))


if __name__ == "__main__":
    unittest.main()
