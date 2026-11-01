"""Membuat berkas DICOM sintetis untuk menguji sistem.

Identitas pasien sengaja dibuat berantakan — salah ketik, huruf besar-kecil
campur, nomor rekam medis kosong — karena begitulah citra tiba ketika alat
radiologi tidak menerima daftar kerja (worklist) dan petugas mengetik manual
di konsol. Itulah kondisi yang harus ditangani layar rekonsiliasi.

Pemakaian:
    python3 tools/make_sample_dicom.py --keluaran data/contoh
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
from pathlib import Path

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    CTImageStorage,
    ComputedRadiographyImageStorage,
    ExplicitVRLittleEndian,
    MRImageStorage,
    generate_uid,
)

UKURAN = 256


def citra_gradien(nomor_irisan: int, jumlah_irisan: int) -> bytes:
    """Membuat piksel 16-bit sederhana: cakram terang di atas latar bergradasi.

    Bukan citra medis sungguhan — hanya pola yang jelas terlihat sehingga mudah
    dipastikan viewer benar-benar merender gambar, dan irisan mana yang tampil.
    """
    piksel = bytearray()
    pusat = UKURAN / 2
    # Jari-jari cakram berubah tiap irisan agar perpindahan slice terlihat jelas.
    # Dipakai titik tengah irisan (bukan ujungnya) supaya irisan pertama dan
    # terakhir tidak menghasilkan jari-jari nol — dan citra satu irisan tetap
    # menampilkan cakram penuh.
    kemajuan = (nomor_irisan + 0.5) / jumlah_irisan
    jari_jari = (UKURAN / 2.6) * max(math.sin(math.pi * kemajuan), 0.3)

    for y in range(UKURAN):
        for x in range(UKURAN):
            nilai = int((x + y) / (2 * UKURAN) * 1200)
            jarak = math.hypot(x - pusat, y - pusat)
            if jarak < jari_jari:
                nilai += 2600
            piksel += (nilai & 0xFFFF).to_bytes(2, "little")
    return bytes(piksel)


def buat_instance(
    *,
    sop_class_uid: str,
    study_uid: str,
    series_uid: str,
    nomor_irisan: int,
    jumlah_irisan: int,
    modalitas: str,
    nama_pasien: str,
    id_pasien: str,
    accession: str,
    uraian: str,
    waktu: dt.datetime,
) -> Dataset:
    ds = Dataset()

    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = sop_class_uid
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.ImplementationClassUID = generate_uid()

    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid

    # Identitas: persis seperti yang diketik petugas di konsol alat.
    ds.PatientName = nama_pasien
    ds.PatientID = id_pasien
    ds.PatientBirthDate = ""
    ds.PatientSex = ""

    # Kosong — inilah inti masalahnya. Tanpa worklist, alat tidak punya nomor
    # order, sehingga accession number tidak terisi dan SATUSEHAT tidak bisa
    # mengaitkan citra ini dengan permintaan pemeriksaan mana pun.
    ds.AccessionNumber = accession

    ds.Modality = modalitas
    ds.StudyDescription = uraian
    ds.SeriesDescription = uraian
    ds.StudyDate = waktu.strftime("%Y%m%d")
    ds.StudyTime = waktu.strftime("%H%M%S")
    ds.SeriesDate = ds.StudyDate
    ds.SeriesTime = ds.StudyTime
    ds.StudyID = "1"
    ds.SeriesNumber = 1
    ds.InstanceNumber = nomor_irisan + 1
    ds.Manufacturer = "Simulator Uji"
    ds.InstitutionName = "RS Universitas Sumatera Utara"

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = UKURAN
    ds.Columns = UKURAN
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelSpacing = [r"0.2", r"0.2"]
    # Rentang nilai piksel yang dihasilkan 0–3800, jadi jendela diatur agar
    # seluruhnya terlihat tanpa perlu diatur manual di viewer.
    ds.WindowCenter = 1900
    ds.WindowWidth = 3800
    ds.RescaleIntercept = 0
    ds.RescaleSlope = 1
    if jumlah_irisan > 1:
        ds.SliceThickness = "5.0"
        ds.ImagePositionPatient = [r"0", r"0", str(nomor_irisan * 5)]
        ds.ImageOrientationPatient = [r"1", r"0", r"0", r"0", r"1", r"0"]
        ds.FrameOfReferenceUID = series_uid

    ds.PixelData = citra_gradien(nomor_irisan, jumlah_irisan)
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    return ds


# Setiap entri meniru satu kesalahan ketik yang lazim terjadi di konsol alat.
CONTOH = [
    {
        "map": "cr-thorax",
        "sop": ComputedRadiographyImageStorage,
        "modalitas": "CR",
        "irisan": 1,
        "uraian": "THORAX PA",
        # Nama tertukar urutannya dan memakai sapaan.
        "nama": "TN BUDI SANTOSO",
        "id": "",
        "catatan": "nomor rekam medis tidak diisi petugas",
    },
    {
        "map": "cr-genu",
        "sop": ComputedRadiographyImageStorage,
        "modalitas": "CR",
        "irisan": 1,
        "uraian": "GENU DEXTRA AP",
        # Salah ketik satu huruf pada nama, nomor RM ada tapi salah ketik.
        "nama": "SITI NURHALIZAH",
        "id": "RM-00241",
        "catatan": "nama kelebihan huruf, nomor RM salah format",
    },
    {
        "map": "mr-kepala",
        "sop": MRImageStorage,
        "modalitas": "MR",
        "irisan": 12,
        "uraian": "MRI KEPALA NON KONTRAS",
        "nama": "agus^wijaya",
        "id": "123456",
        "catatan": "huruf kecil, format nama DICOM terbalik",
    },
    {
        "map": "ct-abdomen",
        "sop": CTImageStorage,
        "modalitas": "CT",
        "irisan": 8,
        "uraian": "CT ABDOMEN",
        "nama": "TEST TEST",
        "id": "TEST",
        "catatan": "uji alat, seharusnya ditolak petugas",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keluaran",
        default="data/contoh",
        help="folder tempat berkas DICOM ditulis",
    )
    argumen = parser.parse_args()

    dasar = Path(argumen.keluaran)
    waktu = dt.datetime.now()

    for contoh in CONTOH:
        study_uid = generate_uid()
        series_uid = generate_uid()
        folder = dasar / contoh["map"]
        folder.mkdir(parents=True, exist_ok=True)

        for i in range(contoh["irisan"]):
            ds = buat_instance(
                sop_class_uid=contoh["sop"],
                study_uid=study_uid,
                series_uid=series_uid,
                nomor_irisan=i,
                jumlah_irisan=contoh["irisan"],
                modalitas=contoh["modalitas"],
                nama_pasien=contoh["nama"],
                id_pasien=contoh["id"],
                accession="",
                uraian=contoh["uraian"],
                waktu=waktu,
            )
            ds.save_as(folder / f"{i + 1:04d}.dcm", enforce_file_format=True)

        print(
            f"{contoh['map']:<12} {contoh['modalitas']:<3} "
            f"{contoh['irisan']:>3} citra  — {contoh['catatan']}"
        )

    print(f"\nSelesai. Berkas ada di: {dasar.resolve()}")


if __name__ == "__main__":
    main()
