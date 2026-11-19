"""Penyimpanan berkas pemeriksaan.

Berkas dari alat disimpan apa adanya. Yang dihasilkan di sini hanyalah turunan
untuk kemudahan: sidik jari isi, jumlah halaman, dan gambar pratinjau.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import uuid
from pathlib import Path

from config import settings

log = logging.getLogger("berkas")

JENIS_DITERIMA = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# Beberapa alat dan peramban mengirim tipe yang kurang tepat, jadi akhiran nama
# berkas ikut dipertimbangkan.
AKHIRAN_DITERIMA = {".pdf", ".jpg", ".jpeg", ".png"}


class BerkasDitolak(ValueError):
    pass


def _dir_arsip() -> Path:
    return settings.berkas_dir


def _dir_pratinjau() -> Path:
    return settings.berkas_dir / "pratinjau"


def siapkan_folder() -> None:
    _dir_arsip().mkdir(parents=True, exist_ok=True)
    _dir_pratinjau().mkdir(parents=True, exist_ok=True)


def sidik_jari(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def periksa(nama: str, tipe: str, data: bytes) -> str:
    """Memastikan berkas layak disimpan, lalu mengembalikan akhiran yang dipakai."""
    if not data:
        raise BerkasDitolak("berkas kosong")

    batas = settings.maks_ukuran_mb * 1024 * 1024
    if len(data) > batas:
        raise BerkasDitolak(
            f"ukuran {len(data) / 1024 / 1024:.0f} MB melebihi batas "
            f"{settings.maks_ukuran_mb} MB"
        )

    akhiran = Path(nama).suffix.lower()
    if akhiran not in AKHIRAN_DITERIMA and tipe not in JENIS_DITERIMA:
        raise BerkasDitolak("hanya menerima PDF, JPG, atau PNG")

    # Isi berkas diperiksa, bukan hanya namanya — nama berkas mudah dipalsukan.
    if data[:5] == b"%PDF-":
        return ".pdf"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    raise BerkasDitolak("isi berkas bukan PDF, JPG, maupun PNG")


def simpan(data: bytes, akhiran: str) -> str:
    """Menulis berkas ke arsip dan mengembalikan nama simpanannya."""
    siapkan_folder()
    nama_simpan = f"{uuid.uuid4().hex}{akhiran}"
    (_dir_arsip() / nama_simpan).write_bytes(data)
    return nama_simpan


def jalur(nama_simpan: str) -> Path:
    return _dir_arsip() / nama_simpan


def jalur_pratinjau(nama_pratinjau: str) -> Path:
    return _dir_pratinjau() / nama_pratinjau


def hapus(nama_simpan: str | None, nama_pratinjau: str | None = None) -> None:
    for berkas in (
        jalur(nama_simpan) if nama_simpan else None,
        jalur_pratinjau(nama_pratinjau) if nama_pratinjau else None,
    ):
        if berkas is not None:
            berkas.unlink(missing_ok=True)


def _buka_pdf(nama_simpan: str):
    """Membuka PDF dengan pypdfium2. Pemanggil bertanggung jawab menutupnya."""
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(str(jalur(nama_simpan)))


def jumlah_halaman(nama_simpan: str) -> int | None:
    if not nama_simpan.lower().endswith(".pdf"):
        return 1
    try:
        pdf = _buka_pdf(nama_simpan)
    except Exception:  # noqa: BLE001 - berkas rusak tidak boleh menggagalkan unggahan
        log.warning("Tidak bisa membaca jumlah halaman %s", nama_simpan, exc_info=True)
        return None
    try:
        return len(pdf)
    finally:
        pdf.close()


def buat_pratinjau(nama_simpan: str) -> str | None:
    """Membuat gambar pratinjau halaman pertama.

    Kegagalan di sini tidak pernah menggagalkan pengarsipan: pratinjau hanya
    kenyamanan, sedangkan berkas aslinya yang penting sudah tersimpan.
    """
    if not nama_simpan.lower().endswith(".pdf"):
        return None

    siapkan_folder()
    keluaran = _dir_pratinjau() / f"{Path(nama_simpan).stem}.png"
    try:
        pdf = _buka_pdf(nama_simpan)
        try:
            # Skala 1 setara 72 dpi; cukup untuk gambar kecil di daftar, dan
            # rekaman CTG yang panjang tidak membengkak jadi berkas raksasa.
            gambar = pdf[0].render(scale=1.1).to_pil()
        finally:
            pdf.close()
        gambar.save(keluaran, format="PNG", optimize=True)
    except Exception:  # noqa: BLE001
        log.warning("Gagal membuat pratinjau untuk %s", nama_simpan, exc_info=True)
        keluaran.unlink(missing_ok=True)
        return None

    return keluaran.name


# Pola tanggal-waktu yang lazim muncul pada nama berkas keluaran alat,
# misalnya "CTG_20261119_0930.pdf" atau "2026-11-19 09-30.pdf".
_POLA_WAKTU = [
    (re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})[ _T-]+(\d{2})[-_:]?(\d{2})"), True),
    (re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})"), False),
]


def tebak_waktu(nama: str) -> dt.datetime | None:
    """Menebak waktu pemeriksaan dari nama berkas.

    Hanya tebakan untuk memudahkan pencocokan; petugas tetap yang menentukan.
    """
    for pola, ada_jam in _POLA_WAKTU:
        cocok = pola.search(nama)
        if not cocok:
            continue
        bagian = [int(x) for x in cocok.groups()]
        try:
            if ada_jam:
                return dt.datetime(bagian[0], bagian[1], bagian[2], bagian[3], bagian[4])
            return dt.datetime(bagian[0], bagian[1], bagian[2])
        except ValueError:
            return None
    return None


def tebak_nama_pasien(nama_simpan: str) -> str:
    """Membaca nama pasien dari teks halaman pertama PDF, bila tercetak di situ.

    Alat CTG umumnya mencetak identitas yang diketik operator pada kepala
    rekaman. Bila terbaca, dipakai sebagai petunjuk saat mencocokkan — bukan
    sebagai kebenaran.
    """
    if not nama_simpan.lower().endswith(".pdf"):
        return ""
    try:
        pdf = _buka_pdf(nama_simpan)
        try:
            teks = pdf[0].get_textpage().get_text_bounded() or ""
        finally:
            pdf.close()
    except Exception:  # noqa: BLE001
        return ""

    for baris in teks.splitlines():
        cocok = re.search(
            r"(?:nama|name|patient)\s*[:\-]\s*(.+)", baris, re.IGNORECASE
        )
        if cocok:
            return cocok.group(1).strip()[:200]
    return ""
