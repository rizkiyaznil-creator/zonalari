"""Membuat berkas PDF rekaman CTG tiruan untuk menguji sistem.

Berkas yang dihasilkan meniru keluaran alat CTG: kop berisi identitas yang
diketik operator, kisi kertas, kurva denyut jantung janin, dan kurva kontraksi.
Nama pasien sengaja dibuat tidak rapi — salah ketik, sapaan, huruf kecil —
karena begitulah identitas tiba dari alat.

Tidak membutuhkan pustaka apa pun di luar Python, supaya bisa dijalankan
langsung di komputer mana pun termasuk milik RS.

Pemakaian:
    python3 tools/buat_contoh_ctg.py --keluaran contoh
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

# A4 mendatar, satuan titik (1/72 inci).
LEBAR, TINGGI = 842.0, 595.0

# Bidang gambar kurva denyut jantung janin dan kontraksi.
FHR_ATAS, FHR_BAWAH = 500.0, 320.0
TOCO_ATAS, TOCO_BAWAH = 270.0, 160.0
KIRI, KANAN = 60.0, 800.0

FHR_MIN, FHR_MAKS = 50, 210
TOCO_MIN, TOCO_MAKS = 0, 100


def _y_fhr(dpm: float) -> float:
    bagian = (dpm - FHR_MIN) / (FHR_MAKS - FHR_MIN)
    return FHR_BAWAH + bagian * (FHR_ATAS - FHR_BAWAH)


def _y_toco(nilai: float) -> float:
    bagian = (nilai - TOCO_MIN) / (TOCO_MAKS - TOCO_MIN)
    return TOCO_BAWAH + bagian * (TOCO_ATAS - TOCO_BAWAH)


def _x(menit: float, total_menit: float) -> float:
    return KIRI + (menit / total_menit) * (KANAN - KIRI)


def _teks(x: float, y: float, isi: str, ukuran: float = 9.0) -> str:
    aman = isi.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return f"BT /F1 {ukuran:.1f} Tf 1 0 0 1 {x:.1f} {y:.1f} Tm ({aman}) Tj ET\n"


def _garis(titik: list[tuple[float, float]], tebal: float, abu: float) -> str:
    if len(titik) < 2:
        return ""
    bagian = [f"{abu:.2f} G {tebal:.2f} w\n"]
    bagian.append(f"{titik[0][0]:.2f} {titik[0][1]:.2f} m\n")
    for x, y in titik[1:]:
        bagian.append(f"{x:.2f} {y:.2f} l\n")
    bagian.append("S\n")
    return "".join(bagian)


def _kisi(total_menit: float) -> str:
    keluar = []

    for dpm in range(FHR_MIN, FHR_MAKS + 1, 10):
        tebal, abu = (0.7, 0.55) if dpm % 30 == 0 else (0.3, 0.8)
        y = _y_fhr(dpm)
        keluar.append(_garis([(KIRI, y), (KANAN, y)], tebal, abu))
        if dpm % 30 == 0:
            keluar.append(_teks(KIRI - 26, y - 3, str(dpm), 7))

    for nilai in range(TOCO_MIN, TOCO_MAKS + 1, 10):
        tebal, abu = (0.7, 0.55) if nilai % 50 == 0 else (0.3, 0.8)
        y = _y_toco(nilai)
        keluar.append(_garis([(KIRI, y), (KANAN, y)], tebal, abu))
        if nilai % 50 == 0:
            keluar.append(_teks(KIRI - 26, y - 3, str(nilai), 7))

    # Garis menit. Kecepatan kertas 1 cm/menit adalah yang lazim dipakai.
    menit = 0
    while menit <= total_menit:
        x = _x(menit, total_menit)
        tebal, abu = (0.7, 0.55) if menit % 5 == 0 else (0.3, 0.85)
        keluar.append(_garis([(x, FHR_BAWAH), (x, FHR_ATAS)], tebal, abu))
        keluar.append(_garis([(x, TOCO_BAWAH), (x, TOCO_ATAS)], tebal, abu))
        if menit % 5 == 0:
            keluar.append(_teks(x - 5, TOCO_BAWAH - 13, f"{menit}", 7))
        menit += 1

    keluar.append(_teks(KIRI - 48, FHR_ATAS + 8, "DJJ (dpm)", 8))
    keluar.append(_teks(KIRI - 48, TOCO_ATAS + 8, "TOCO", 8))
    keluar.append(_teks(KANAN - 90, TOCO_BAWAH - 13, "menit  ·  1 cm/menit", 7))
    return "".join(keluar)


def _kurva_djj(
    acak: random.Random,
    total_menit: float,
    dasar: float,
    variabilitas: float,
    akselerasi: int,
    deselerasi_lambat: list[float],
) -> list[tuple[float, float]]:
    """Membangkitkan kurva denyut jantung janin.

    Bukan simulasi fisiologis — hanya pola yang bentuknya menyerupai rekaman
    sungguhan agar tampilan, pratinjau, dan alur kerja bisa diuji.
    """
    langkah = 0.05  # menit per titik
    titik: list[tuple[float, float]] = []
    puncak_akselerasi = sorted(
        acak.uniform(2, total_menit - 2) for _ in range(akselerasi)
    )

    menit = 0.0
    while menit <= total_menit:
        nilai = dasar
        nilai += variabilitas * math.sin(menit * 11.0) * 0.5
        nilai += variabilitas * math.sin(menit * 29.0) * 0.25
        nilai += acak.uniform(-variabilitas, variabilitas) * 0.25

        for puncak in puncak_akselerasi:
            jarak = menit - puncak
            if abs(jarak) < 0.9:
                nilai += 22 * math.exp(-((jarak / 0.42) ** 2))

        for mulai in deselerasi_lambat:
            jarak = menit - mulai
            if -0.4 < jarak < 1.6:
                nilai -= 32 * math.exp(-(((jarak - 0.6) / 0.5) ** 2))

        nilai = max(FHR_MIN + 5, min(FHR_MAKS - 5, nilai))
        titik.append((_x(menit, total_menit), _y_fhr(nilai)))
        menit += langkah

    return titik


def _kurva_toco(
    total_menit: float, kontraksi_per_10: int, mulai_kontraksi: list[float]
) -> list[tuple[float, float]]:
    langkah = 0.05
    titik: list[tuple[float, float]] = []
    menit = 0.0
    while menit <= total_menit:
        nilai = 8.0
        for mulai in mulai_kontraksi:
            jarak = menit - mulai
            if -0.2 < jarak < 1.8:
                nilai += 58 * math.exp(-(((jarak - 0.7) / 0.45) ** 2))
        titik.append((_x(menit, total_menit), _y_toco(min(nilai, TOCO_MAKS))))
        menit += langkah
    return titik


def _halaman(
    nama_pasien: str,
    no_rm: str,
    tanggal: str,
    jam: str,
    judul: str,
    total_menit: float,
    djj: list[tuple[float, float]],
    toco: list[tuple[float, float]],
) -> str:
    bagian = [
        _teks(KIRI, TINGGI - 40, "KARDIOTOKOGRAFI", 15),
        _teks(KIRI, TINGGI - 58, judul, 9),
        # Identitas persis seperti yang diketik operator di alat.
        _teks(KIRI + 430, TINGGI - 40, f"Nama: {nama_pasien}", 10),
        _teks(KIRI + 430, TINGGI - 55, f"No. RM: {no_rm}", 9),
        _teks(KIRI + 430, TINGGI - 69, f"Tanggal: {tanggal}  Jam: {jam}", 9),
        _teks(KIRI + 430, TINGGI - 83, f"Durasi: {total_menit:.0f} menit", 9),
        _kisi(total_menit),
        _garis(djj, 1.1, 0.1),
        _garis(toco, 1.0, 0.35),
        _teks(
            KIRI,
            40,
            "Rekaman tiruan untuk pengujian sistem. Bukan data pasien.",
            8,
        ),
    ]
    return "".join(bagian)


def _tulis_pdf(tujuan: Path, halaman: list[str]) -> None:
    objek: list[bytes] = []

    def tambah(isi: bytes) -> int:
        objek.append(isi)
        return len(objek)

    nomor_halaman: list[int] = []
    nomor_isi: list[int] = []
    for isi in halaman:
        data = isi.encode("latin-1", errors="replace")
        nomor_isi.append(tambah(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(data), data)))

    nomor_font = tambah(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    nomor_pages = len(objek) + len(halaman) + 1

    for isi_ref in nomor_isi:
        nomor_halaman.append(
            tambah(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (nomor_pages, int(LEBAR), int(TINGGI), nomor_font, isi_ref)
            )
        )

    anak = b" ".join(b"%d 0 R" % n for n in nomor_halaman)
    nomor_pages_asli = tambah(
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (anak, len(nomor_halaman))
    )
    assert nomor_pages_asli == nomor_pages, "nomor objek Pages tidak sesuai perkiraan"
    nomor_root = tambah(b"<< /Type /Catalog /Pages %d 0 R >>" % nomor_pages)

    keluar = bytearray(b"%PDF-1.4\n")
    posisi: list[int] = []
    for i, isi in enumerate(objek, start=1):
        posisi.append(len(keluar))
        keluar += b"%d 0 obj\n" % i + isi + b"\nendobj\n"

    awal_xref = len(keluar)
    keluar += b"xref\n0 %d\n" % (len(objek) + 1)
    keluar += b"0000000000 65535 f \n"
    for p in posisi:
        keluar += b"%010d 00000 n \n" % p
    keluar += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objek) + 1,
        nomor_root,
        awal_xref,
    )

    tujuan.write_bytes(bytes(keluar))


CONTOH = [
    {
        "berkas": "CTG_20261119_0915.pdf",
        "nama": "NY SITI AMINAH",
        "rm": "RM-00817",
        "jam": "09:15",
        "judul": "Non-Stress Test (antepartum)",
        "menit": 20,
        "dasar": 142,
        "variabilitas": 12,
        "akselerasi": 4,
        "deselerasi": [],
        "kontraksi": [],
        "catatan": "NST reaktif — akselerasi jelas, tanpa deselerasi",
    },
    {
        "berkas": "CTG_20261119_1042.pdf",
        "nama": "dewi^lestari",
        "rm": "",
        "jam": "10:42",
        "judul": "Non-Stress Test (antepartum)",
        "menit": 20,
        "dasar": 148,
        "variabilitas": 4,
        "akselerasi": 0,
        "deselerasi": [],
        "kontraksi": [],
        "catatan": "NST non-reaktif — variabilitas minimal, tanpa akselerasi; nomor RM tidak diisi",
    },
    {
        "berkas": "CTG_20261119_1320.pdf",
        "nama": "Ratna Sari Dewi",
        "rm": "RM-00912",
        "jam": "13:20",
        "judul": "CTG intrapartum",
        "menit": 30,
        "dasar": 138,
        "variabilitas": 8,
        "akselerasi": 1,
        "deselerasi": [6.5, 13.0, 19.5, 26.0],
        "kontraksi": [6.0, 12.5, 19.0, 25.5],
        "catatan": "Intrapartum dengan deselerasi lambat berulang",
    },
    {
        "berkas": "CTG_TEST_20261119.pdf",
        "nama": "TEST",
        "rm": "TEST",
        "jam": "07:00",
        "judul": "Uji alat",
        "menit": 10,
        "dasar": 150,
        "variabilitas": 2,
        "akselerasi": 0,
        "deselerasi": [],
        "kontraksi": [],
        "catatan": "Uji alat — seharusnya ditolak petugas saat pencocokan",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keluaran", default="contoh", help="folder tujuan")
    argumen = parser.parse_args()

    tujuan = Path(argumen.keluaran)
    tujuan.mkdir(parents=True, exist_ok=True)

    for nomor, contoh in enumerate(CONTOH):
        acak = random.Random(1000 + nomor)
        djj = _kurva_djj(
            acak,
            contoh["menit"],
            contoh["dasar"],
            contoh["variabilitas"],
            contoh["akselerasi"],
            contoh["deselerasi"],
        )
        toco = _kurva_toco(contoh["menit"], 0, contoh["kontraksi"])
        halaman = _halaman(
            contoh["nama"],
            contoh["rm"] or "-",
            "19-11-2026",
            contoh["jam"],
            contoh["judul"],
            contoh["menit"],
            djj,
            toco,
        )
        _tulis_pdf(tujuan / contoh["berkas"], [halaman])
        print(f"{contoh['berkas']:<28} {contoh['catatan']}")

    print(f"\nSelesai. Berkas ada di: {tujuan.resolve()}")


if __name__ == "__main__":
    main()
