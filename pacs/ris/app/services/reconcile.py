"""Rekonsiliasi: mencocokkan citra yang masuk dengan order, lalu memperbaiki identitas.

Inilah bagian yang menggantikan Modality Worklist. Karena konfigurasi alat
radiologi tidak boleh disentuh, identitas pasien diketik manual di konsol alat
dan citra tiba tanpa accession number. Modul ini yang menutup celah itu.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..models import Order, Study, User
from . import orthanc


def normalize_name(raw: str) -> str:
    """Menyeragamkan nama untuk dibandingkan.

    Nama DICOM berformat "KELUARGA^DEPAN^TENGAH". Gelar, tanda baca, dan sapaan
    seperti "Tn"/"Ny" dibuang karena petugas tidak konsisten menuliskannya.
    """
    text = (raw or "").replace("^", " ").upper()
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    words = [w for w in text.split() if w not in _NOISE_WORDS]
    return " ".join(words)


_NOISE_WORDS = {"TN", "NY", "NN", "AN", "SDR", "SDRI", "BY", "MR", "MRS", "MS"}


def _parse_dicom_date(value: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


@dataclass
class Suggestion:
    order: Order
    score: int
    reasons: list[str]


def suggest_orders(db: Session, study: Study, limit: int = 5) -> list[Suggestion]:
    """Mengurutkan order yang paling mungkin cocok dengan sebuah study.

    Skor ini HANYA alat bantu urut. Keputusan tetap di tangan petugas — tidak ada
    pencocokan otomatis, karena salah pasang identitas pada rekam medis jauh lebih
    mahal daripada beberapa detik kerja manual.
    """
    orders = db.scalars(
        select(Order).where(Order.status == "pending").order_by(Order.created_at.desc())
    ).all()

    study_name = normalize_name(study.original_patient_name)
    study_date = _parse_dicom_date(study.study_date)

    suggestions: list[Suggestion] = []
    for order in orders:
        score = 0
        reasons: list[str] = []

        # Nomor rekam medis yang diketik benar adalah petunjuk terkuat.
        if (
            study.original_patient_id
            and order.patient_mrn
            and study.original_patient_id.strip().upper()
            == order.patient_mrn.strip().upper()
        ):
            score += 45
            reasons.append("nomor rekam medis sama persis")

        if study_name:
            ratio = SequenceMatcher(
                None, study_name, normalize_name(order.patient_name)
            ).ratio()
            score += int(ratio * 40)
            if ratio >= 0.95:
                reasons.append("nama sama persis")
            elif ratio >= 0.75:
                reasons.append("nama mirip")

        if study.modality and order.modality:
            if study.modality.upper() == order.modality.upper():
                score += 10
                reasons.append("modalitas cocok")
            else:
                score -= 20
                reasons.append(
                    f"modalitas berbeda ({study.modality} vs {order.modality})"
                )

        if study_date and order.scheduled_for:
            selisih = abs((study_date - order.scheduled_for.date()).days)
            if selisih == 0:
                score += 10
                reasons.append("tanggal sama")
            elif selisih <= 1:
                score += 5
                reasons.append("selisih tanggal 1 hari")
            elif selisih > 7:
                score -= 10
                reasons.append(f"selisih tanggal {selisih} hari")

        suggestions.append(
            Suggestion(order=order, score=max(score, 0), reasons=reasons)
        )

    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions[:limit]


def dicom_name(order: Order) -> str:
    """Menyusun PatientName format DICOM dari nama order.

    Nama Indonesia umumnya tidak terbagi keluarga/depan, jadi seluruh nama
    ditaruh di komponen pertama — ini cara yang lazim dipakai PACS di Indonesia.
    """
    return (order.patient_name or "").strip().upper().replace("^", " ")


def verify(
    db: Session,
    study: Study,
    order: Order,
    user: User,
    request: Request | None = None,
) -> Study:
    """Mengikat study ke order dan menuliskan identitas yang benar ke berkas DICOM."""
    if study.status == "verified":
        raise ValueError("Study ini sudah terverifikasi.")
    if order.status == "cancelled":
        raise ValueError("Order ini sudah dibatalkan.")

    # Keempat tag utama pasien WAJIB disertakan seluruhnya, termasuk yang
    # kosong. Orthanc menolak perubahan identitas yang hanya sebagian ketika
    # pasien lama sudah memiliki study lain — dan itu justru kondisi yang paling
    # sering terjadi: beberapa pemeriksaan tersimpan di bawah satu identitas
    # salah ketik yang sama, lalu dikoreksi satu per satu.
    replace = {
        "PatientID": order.patient_mrn,
        "PatientName": dicom_name(order),
        "PatientBirthDate": (
            order.patient_birth_date.strftime("%Y%m%d")
            if order.patient_birth_date
            else ""
        ),
        "PatientSex": order.patient_sex or "",
        "AccessionNumber": order.accession_number,
    }
    if order.study_description:
        replace["StudyDescription"] = order.study_description

    sebelum = {
        "PatientID": study.original_patient_id,
        "PatientName": study.original_patient_name,
        "AccessionNumber": study.accession_number or "",
    }

    tag_pasien = {
        k: v for k, v in replace.items() if k.startswith("Patient")
    }
    pasien_diselaraskan = _selaraskan_pasien(db, order, tag_pasien, user, request)

    # ID internal study bisa berubah bila rekam pasiennya baru saja diluruskan.
    orthanc_id = (
        orthanc.find_study_id_by_uid(study.study_instance_uid) or study.orthanc_id
    )
    new_orthanc_id = orthanc.modify_study(orthanc_id, replace)

    study.orthanc_id = new_orthanc_id
    study.patient_id = order.patient_mrn
    study.patient_name = order.patient_name
    study.accession_number = order.accession_number
    study.order_id = order.id
    study.status = "verified"
    study.verified_at = dt.datetime.now(dt.timezone.utc)
    study.verified_by_id = user.id

    order.status = "matched"

    audit.record(
        db,
        action="study.verify",
        user=user,
        request=request,
        object_type="study",
        object_id=study.study_instance_uid,
        detail={
            "sebelum": sebelum,
            "sesudah": replace,
            "order_id": order.id,
            "accession_number": order.accession_number,
            "orthanc_id_lama": study.original_orthanc_id,
            "orthanc_id_baru": new_orthanc_id,
            "pasien_diselaraskan": pasien_diselaraskan,
        },
        commit=False,
    )
    db.commit()
    _segarkan_id_orthanc(db)
    return study


def _selaraskan_pasien(
    db: Session,
    order: Order,
    tag_pasien: dict[str, str],
    user: User,
    request: Request | None,
) -> dict | None:
    """Meluruskan demografi rekam pasien tujuan bila sudah ada dan berbeda.

    Orthanc menyimpan satu rekam pasien per PatientID. Bila nomor rekam medis
    tujuan sudah ada di arsip dengan nama atau tanggal lahir yang berbeda —
    lazimnya karena pemeriksaan sebelumnya masuk dengan nama salah ketik —
    Orthanc menolak memasang study baru di bawahnya. Rekam pasien itu
    diluruskan lebih dulu mengikuti data order, yang berasal dari SIMRS dan
    karenanya menjadi acuan.

    Ini ikut mengubah study lain milik nomor rekam medis yang sama, jadi
    cakupannya dicatat tersendiri di jejak audit.
    """
    pasien = orthanc.find_patient_by_id(order.patient_mrn)
    if pasien is None:
        return None

    tag_lama = pasien.get("MainDicomTags") or {}
    beda = {
        k: (tag_lama.get(k, ""), v)
        for k, v in tag_pasien.items()
        if tag_lama.get(k, "") != v
    }
    if not beda:
        return None

    jumlah_study = len(pasien.get("Studies") or [])
    orthanc.modify_patient(pasien["ID"], tag_pasien)

    audit.record(
        db,
        action="pasien.selaraskan",
        user=user,
        request=request,
        object_type="patient",
        object_id=order.patient_mrn,
        detail={
            "alasan": "nomor rekam medis sudah ada di arsip dengan demografi berbeda",
            "perubahan": {k: {"dari": a, "menjadi": b} for k, (a, b) in beda.items()},
            "jumlah_study_terdampak": jumlah_study,
        },
        commit=False,
    )
    return {
        "perubahan": {k: {"dari": a, "menjadi": b} for k, (a, b) in beda.items()},
        "jumlah_study_terdampak": jumlah_study,
    }


def _segarkan_id_orthanc(db: Session) -> None:
    """Menyegarkan ID internal Orthanc yang berubah akibat modifikasi.

    Modifikasi di Orthanc menerbitkan ID internal baru walau StudyInstanceUID
    dipertahankan, sehingga baris study lain milik pasien yang sama bisa
    menunjuk ID yang sudah tidak ada.
    """
    for baris in db.scalars(select(Study)).all():
        if orthanc.get_study(baris.orthanc_id) is not None:
            continue
        id_baru = orthanc.find_study_id_by_uid(baris.study_instance_uid)
        if id_baru:
            baris.orthanc_id = id_baru
    db.commit()


def reject(
    db: Session,
    study: Study,
    reason: str,
    user: User,
    request: Request | None = None,
) -> Study:
    """Menandai kiriman sebagai bukan pemeriksaan sah.

    Dipakai untuk uji alat, salah kirim, atau citra rusak. Berkasnya TIDAK
    dihapus — penghapusan arsip adalah tindakan tersendiri yang hanya boleh
    dilakukan administrator setelah ditinjau.
    """
    study.status = "rejected"
    study.rejected_reason = reason
    study.verified_at = dt.datetime.now(dt.timezone.utc)
    study.verified_by_id = user.id

    audit.record(
        db,
        action="study.reject",
        user=user,
        request=request,
        object_type="study",
        object_id=study.study_instance_uid,
        detail={"alasan": reason},
        commit=False,
    )
    db.commit()
    return study
