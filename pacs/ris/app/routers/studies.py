"""Daftar pasien dan pembukaan citra — yang dilihat dokter di poli."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Study, User
from ..security import require_user
from ..templating import templates

router = APIRouter(tags=["study"])

# Peran yang boleh melihat study yang BELUM terverifikasi. Dokter poli tidak
# termasuk: citra yang identitasnya belum dipastikan tidak boleh dipakai
# mengambil keputusan klinis.
PETUGAS_ARSIP = {"admin", "radiografer"}


@router.get("/study", response_class=HTMLResponse)
def cari_study(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    kata = (request.query_params.get("q") or "").strip()

    pernyataan = select(Study)
    if user.role in PETUGAS_ARSIP:
        pernyataan = pernyataan.where(Study.status != "rejected")
    else:
        pernyataan = pernyataan.where(Study.status == "verified")

    if kata:
        pola = f"%{kata}%"
        pernyataan = pernyataan.where(
            or_(
                Study.patient_name.ilike(pola),
                Study.patient_id.ilike(pola),
                Study.accession_number.ilike(pola),
                Study.study_description.ilike(pola),
            )
        )

    studies = db.scalars(
        pernyataan.order_by(Study.received_at.desc()).limit(200)
    ).all()

    if kata:
        audit.record(
            db,
            action="study.cari",
            user=user,
            request=request,
            object_type="study",
            object_id="-",
            detail={"kata_kunci": kata, "jumlah_hasil": len(studies)},
        )

    return templates.TemplateResponse(
        request,
        "studies.html",
        {"user": user, "studies": studies, "kata": kata},
    )


@router.get("/study/{study_id}", response_class=HTMLResponse)
def detail_study(
    study_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    study = db.get(Study, study_id)
    if study is None:
        return RedirectResponse("/study", status_code=302)

    if study.status != "verified" and user.role not in PETUGAS_ARSIP:
        return RedirectResponse("/study", status_code=302)

    # Setiap pembukaan data pasien dicatat — ini syarat audit rekam medis.
    audit.record(
        db,
        action="study.buka",
        user=user,
        request=request,
        object_type="study",
        object_id=study.study_instance_uid,
        detail={"konteks": "detail study", "pasien": study.patient_name},
    )

    # OHIF menyatu di dalam Orthanc sebagai plugin dan diakses lewat Caddy, yang
    # sudah memeriksa sesi login lebih dulu.
    url_viewer = (
        f"/ohif/viewer?StudyInstanceUIDs={study.study_instance_uid}"
        if study.status == "verified" or user.role in PETUGAS_ARSIP
        else None
    )

    return templates.TemplateResponse(
        request,
        "study_detail.html",
        {"user": user, "study": study, "url_viewer": url_viewer},
    )
