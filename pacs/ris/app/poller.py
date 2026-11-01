"""Pemantau study baru di Orthanc.

Orthanc menyimpan antrean perubahan (`/changes`). RIS membacanya secara berkala
dan memindahkan setiap study yang sudah "stabil" ke kotak masuk. Posisi baca
terakhir disimpan di basis data, sehingga RIS yang sempat mati tidak melewatkan
kiriman yang datang saat itu.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import settings
from .db import SessionLocal
from .models import PollerState, Study
from .services import orthanc

log = logging.getLogger("ris.poller")


def ingest_study(db: Session, orthanc_id: str, source: str = "cstore") -> Study | None:
    """Mendaftarkan sebuah study Orthanc ke kotak masuk RIS.

    Aman dipanggil berulang: study yang sudah terdaftar hanya disegarkan
    jumlah series/instance-nya, bukan dibuat ganda. Ini penting karena setelah
    rekonsiliasi Orthanc memunculkan lagi peristiwa untuk study yang sama.
    """
    detail = orthanc.get_study(orthanc_id)
    if detail is None:
        return None

    tags = detail.get("MainDicomTags") or {}
    patient_tags = detail.get("PatientMainDicomTags") or {}
    uid = tags.get("StudyInstanceUID")
    if not uid:
        log.warning("Study %s tanpa StudyInstanceUID, dilewati", orthanc_id)
        return None

    try:
        stats = orthanc.get_study_statistics(orthanc_id)
        series_count = int(stats.get("CountSeries", 0))
        instance_count = int(stats.get("CountInstances", 0))
    except (orthanc.OrthancError, ValueError, TypeError):
        series_count = len(detail.get("Series") or [])
        instance_count = 0

    modalities = orthanc.get_study_modalities(orthanc_id)

    existing = db.scalar(select(Study).where(Study.study_instance_uid == uid))
    if existing is not None:
        existing.orthanc_id = orthanc_id
        existing.series_count = series_count
        existing.instance_count = instance_count
        if not existing.modality and modalities:
            existing.modality = modalities[0]
        db.commit()
        return existing

    study = Study(
        study_instance_uid=uid,
        orthanc_id=orthanc_id,
        original_orthanc_id=orthanc_id,
        original_patient_id=patient_tags.get("PatientID", ""),
        original_patient_name=patient_tags.get("PatientName", ""),
        modality=modalities[0] if modalities else "",
        study_date=tags.get("StudyDate", ""),
        study_time=tags.get("StudyTime", ""),
        study_description=tags.get("StudyDescription", ""),
        accession_number=tags.get("AccessionNumber") or None,
        series_count=series_count,
        instance_count=instance_count,
        status="unverified",
        ingest_source=source,
    )
    db.add(study)

    audit.record(
        db,
        action="study.received",
        object_type="study",
        object_id=uid,
        detail={
            "sumber": source,
            "identitas_dari_alat": {
                "PatientID": study.original_patient_id,
                "PatientName": study.original_patient_name,
            },
            "modalitas": modalities,
            "jumlah_instance": instance_count,
        },
        commit=False,
    )
    db.commit()
    log.info(
        "Study baru masuk kotak masuk: %s (%s, %d instance)",
        uid,
        study.modality or "?",
        instance_count,
    )
    return study


def _poll_once() -> None:
    db = SessionLocal()
    try:
        state = db.get(PollerState, 1)
        if state is None:
            state = PollerState(id=1, last_change_seq=0)
            db.add(state)
            db.commit()

        while True:
            data = orthanc.get_changes(state.last_change_seq, limit=100)
            for change in data.get("Changes", []):
                if change.get("ChangeType") == "StableStudy":
                    try:
                        ingest_study(db, change["ID"])
                    except orthanc.OrthancError:
                        log.exception("Gagal mendaftarkan study %s", change.get("ID"))

            last = int(data.get("Last", state.last_change_seq))
            if last != state.last_change_seq:
                state.last_change_seq = last
                db.commit()

            if data.get("Done", True):
                break
    finally:
        db.close()


async def run_poller() -> None:
    """Loop utama pemantau, dijalankan sebagai tugas latar aplikasi."""
    log.info("Pemantau study dimulai (jeda %.1f detik)", settings.poll_seconds)
    while True:
        try:
            await asyncio.to_thread(_poll_once)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - loop tidak boleh mati karena satu galat
            log.exception("Galat pada pemantau study; mencoba lagi")
        await asyncio.sleep(settings.poll_seconds)
