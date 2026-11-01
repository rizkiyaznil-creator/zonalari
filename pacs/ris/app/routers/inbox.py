"""Kotak masuk dan rekonsiliasi — jantung alur kerja tanpa Modality Worklist."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Order, Study, User
from ..poller import ingest_study
from ..security import require_roles
from ..services import orthanc, reconcile
from ..templating import templates

router = APIRouter(tags=["kotak masuk"])

PETUGAS = require_roles("admin", "radiografer")


@router.get("/kotak-masuk", response_class=HTMLResponse)
def daftar_kotak_masuk(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    studies = db.scalars(
        select(Study)
        .where(Study.status == "unverified")
        .order_by(Study.received_at.desc())
    ).all()
    jumlah_order = db.scalar(
        select(Order).where(Order.status == "pending").order_by(Order.id)
    )
    return templates.TemplateResponse(
        request,
        "inbox_list.html",
        {
            "user": user,
            "studies": studies,
            "ada_order": jumlah_order is not None,
        },
    )


@router.get("/kotak-masuk/{study_id}", response_class=HTMLResponse)
def detail_kotak_masuk(
    study_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    study = db.get(Study, study_id)
    if study is None:
        return RedirectResponse("/kotak-masuk", status_code=302)

    saran = reconcile.suggest_orders(db, study)
    order_lain = db.scalars(
        select(Order).where(Order.status == "pending").order_by(Order.patient_name)
    ).all()

    audit.record(
        db,
        action="study.buka",
        user=user,
        request=request,
        object_type="study",
        object_id=study.study_instance_uid,
        detail={"konteks": "kotak masuk"},
    )

    return templates.TemplateResponse(
        request,
        "inbox_detail.html",
        {
            "user": user,
            "study": study,
            "saran": saran,
            "order_lain": order_lain,
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/kotak-masuk/{study_id}/verifikasi")
def verifikasi(
    study_id: int,
    request: Request,
    order_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    study = db.get(Study, study_id)
    order = db.get(Order, order_id)
    if study is None or order is None:
        return RedirectResponse("/kotak-masuk?galat=Data+tidak+ditemukan", status_code=302)

    try:
        reconcile.verify(db, study, order, user, request)
    except (ValueError, orthanc.OrthancError) as exc:
        return RedirectResponse(
            f"/kotak-masuk/{study_id}?galat={exc}", status_code=302
        )

    return RedirectResponse(f"/study/{study.id}", status_code=302)


@router.post("/kotak-masuk/{study_id}/tolak")
def tolak(
    study_id: int,
    request: Request,
    alasan: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    study = db.get(Study, study_id)
    if study is None:
        return RedirectResponse("/kotak-masuk", status_code=302)
    reconcile.reject(db, study, alasan.strip(), user, request)
    return RedirectResponse("/kotak-masuk", status_code=302)


@router.get("/unggah", response_class=HTMLResponse)
def form_unggah(request: Request, user: User = Depends(PETUGAS)):
    return templates.TemplateResponse(
        request, "upload.html", {"user": user, "hasil": None}
    )


@router.post("/unggah", response_class=HTMLResponse)
async def proses_unggah(
    request: Request,
    berkas: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    """Unggah manual: berkas DICOM lepas maupun isi CD pasien rujukan."""
    berhasil = 0
    gagal: list[str] = []
    study_ids: set[str] = set()

    for item in berkas:
        data = await item.read()
        if not data:
            continue
        # Berkas non-DICOM (mis. DICOMDIR, README, autorun) dilewati diam-diam
        # agar petugas bisa memilih seluruh isi CD sekaligus.
        if len(data) < 132 or data[128:132] != b"DICM":
            gagal.append(f"{item.filename}: bukan berkas DICOM")
            continue
        try:
            hasil = orthanc.upload_instance(data)
            berhasil += 1
            if hasil.get("ParentStudy"):
                study_ids.add(hasil["ParentStudy"])
        except orthanc.OrthancError as exc:
            gagal.append(f"{item.filename}: {exc}")

    for orthanc_study_id in study_ids:
        ingest_study(db, orthanc_study_id, source="upload")

    audit.record(
        db,
        action="study.unggah",
        user=user,
        request=request,
        object_type="study",
        object_id=",".join(sorted(study_ids)) or "-",
        detail={"berhasil": berhasil, "gagal": len(gagal)},
    )

    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "user": user,
            "hasil": {
                "berhasil": berhasil,
                "gagal": gagal,
                "jumlah_study": len(study_ids),
            },
        },
    )
