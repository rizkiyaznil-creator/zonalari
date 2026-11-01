"""Uji logika pencocokan citra dengan order.

Dijalankan tanpa Orthanc maupun PostgreSQL — hanya logika murni, memakai basis
data SQLite di memori. Jalankan dengan:

    docker compose run --rm -v ./ris/tests:/app/tests ris python -m unittest discover -s tests
"""

from __future__ import annotations

import datetime as dt
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Order, Study
from app.services.reconcile import dicom_name, normalize_name, suggest_orders


class UjiPenyeragamanNama(unittest.TestCase):
    def test_membuang_sapaan_dan_tanda_baca(self):
        self.assertEqual(normalize_name("TN BUDI SANTOSO"), "BUDI SANTOSO")
        self.assertEqual(normalize_name("Ny. Siti Nurhaliza"), "SITI NURHALIZA")

    def test_caret_dicom_jadi_spasi(self):
        self.assertEqual(normalize_name("agus^wijaya"), "AGUS WIJAYA")
        self.assertEqual(normalize_name("WIJAYA^AGUS^"), "WIJAYA AGUS")

    def test_nama_kosong_tidak_meledak(self):
        self.assertEqual(normalize_name(""), "")
        self.assertEqual(normalize_name(None), "")

    def test_nama_dicom_dari_order(self):
        order = Order(patient_name="Agus Wijaya")
        self.assertEqual(dicom_name(order), "AGUS WIJAYA")


class UjiSaranPencocokan(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.hari_ini = dt.datetime(2026, 11, 1, 9, 0, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.db.close()

    def _order(self, **ubah) -> Order:
        nilai = dict(
            accession_number=f"ACC{len(self.db.query(Order).all()) + 1:04d}",
            patient_mrn="123456",
            patient_name="Agus Wijaya",
            modality="MR",
            scheduled_for=self.hari_ini,
            status="pending",
        )
        nilai.update(ubah)
        order = Order(**nilai)
        self.db.add(order)
        self.db.commit()
        return order

    def _study(self, **ubah) -> Study:
        nilai = dict(
            study_instance_uid="1.2.3",
            orthanc_id="x",
            original_orthanc_id="x",
            original_patient_id="123456",
            original_patient_name="agus^wijaya",
            modality="MR",
            study_date="20261101",
        )
        nilai.update(ubah)
        return Study(**nilai)

    def test_nomor_rekam_medis_sama_memberi_skor_tertinggi(self):
        benar = self._order(patient_mrn="123456", patient_name="Agus Wijaya")
        self._order(patient_mrn="999999", patient_name="Agus Wijaya")

        saran = suggest_orders(self.db, self._study())

        self.assertEqual(saran[0].order.id, benar.id)
        self.assertIn("nomor rekam medis sama persis", saran[0].reasons)

    def test_modalitas_berbeda_menurunkan_skor(self):
        self._order(modality="MR")
        salah = self._order(modality="CR", patient_mrn="999999")

        saran = {s.order.id: s for s in suggest_orders(self.db, self._study())}

        self.assertLess(saran[salah.id].score, saran[1].score)
        self.assertTrue(
            any("modalitas berbeda" in a for a in saran[salah.id].reasons)
        )

    def test_order_yang_sudah_dicocokkan_tidak_disarankan_lagi(self):
        sudah = self._order()
        sudah.status = "matched"
        self.db.commit()

        self.assertEqual(suggest_orders(self.db, self._study()), [])

    def test_selisih_tanggal_jauh_menurunkan_skor(self):
        dekat = self._order()
        jauh = self._order(
            patient_mrn="999999",
            scheduled_for=self.hari_ini - dt.timedelta(days=30),
        )

        saran = {s.order.id: s for s in suggest_orders(self.db, self._study())}

        self.assertGreater(saran[dekat.id].score, saran[jauh.id].score)

    def test_identitas_kosong_tetap_menghasilkan_urutan(self):
        self._order()
        study = self._study(original_patient_id="", original_patient_name="")

        saran = suggest_orders(self.db, study)

        self.assertEqual(len(saran), 1)
        self.assertGreaterEqual(saran[0].score, 0)


if __name__ == "__main__":
    unittest.main()
