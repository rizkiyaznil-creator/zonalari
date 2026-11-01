"""Order pemeriksaan — tempat accession number diterbitkan."""

from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Order, User
from ..security import require_roles
from ..templating import templates

router = APIRouter(tags=["order"])

PETUGAS = require_roles("admin", "radiografer")

MODALITAS = ["CR", "DX", "CT", "MR", "US", "XA", "MG", "NM", "RF"]


def terbitkan_accession_number(db: Session) -> str:
    """Menerbitkan accession number baru.

    SATUSEHAT mensyaratkan nomor ini berasal dari sisi pemesan (SIMRS/RIS), bukan
    dikarang PACS setelah citra datang. Selama SIMRS belum tersambung, RIS yang
    menerbitkannya — dan saat SIMRS tersambung, nomor dari SIMRS yang dipakai.
    """
    hari_ini = dt.date.today()
    awalan = f"RSU{hari_ini:%Y%m%d}"
    terpakai = db.scalar(
        select(func.count(Order.id)).where(Order.accession_number.like(f"{awalan}%"))
    )
    urut = int(terpakai or 0) + 1
    while True:
        kandidat = f"{awalan}{urut:04d}"
        if db.scalar(
            select(Order).where(Order.accession_number == kandidat)
        ) is None:
            return kandidat
        urut += 1


@router.get("/order", response_class=HTMLResponse)
def daftar_order(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    orders = db.scalars(select(Order).order_by(Order.created_at.desc()).limit(200)).all()
    return templates.TemplateResponse(
        request,
        "orders.html",
        {
            "user": user,
            "orders": orders,
            "modalitas": MODALITAS,
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/order")
def buat_order(
    request: Request,
    patient_mrn: str = Form(...),
    patient_name: str = Form(...),
    modality: str = Form(...),
    study_description: str = Form(""),
    referring_clinician: str = Form(""),
    patient_birth_date: str = Form(""),
    patient_sex: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    tanggal_lahir = None
    if patient_birth_date:
        try:
            tanggal_lahir = dt.date.fromisoformat(patient_birth_date)
        except ValueError:
            return RedirectResponse(
                "/order?galat=Format+tanggal+lahir+tidak+sah", status_code=302
            )

    order = Order(
        accession_number=terbitkan_accession_number(db),
        patient_mrn=patient_mrn.strip(),
        patient_name=patient_name.strip(),
        patient_birth_date=tanggal_lahir,
        patient_sex=(patient_sex or "").strip().upper()[:1] or None,
        modality=modality.strip().upper(),
        study_description=study_description.strip(),
        referring_clinician=referring_clinician.strip(),
        scheduled_for=dt.datetime.now(dt.timezone.utc),
        source="manual",
    )
    db.add(order)
    db.flush()

    audit.record(
        db,
        action="order.buat",
        user=user,
        request=request,
        object_type="order",
        object_id=order.accession_number,
        detail={"pasien": order.patient_name, "modalitas": order.modality},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/order?pesan=Order+{order.accession_number}+dibuat", status_code=302
    )


@router.post("/order/impor-csv")
async def impor_csv(
    request: Request,
    berkas: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    """Impor order massal dari CSV.

    Dipakai selama SIMRS belum tersambung: petugas mengekspor daftar order
    harian dari SIMRS lalu mengunggahnya ke sini. Kolom yang dibaca:
    accession_number (boleh kosong), patient_mrn, patient_name, modality,
    study_description, patient_birth_date (YYYY-MM-DD), patient_sex.
    """
    isi = (await berkas.read()).decode("utf-8-sig", errors="replace")
    pembaca = csv.DictReader(io.StringIO(isi))

    masuk = 0
    dilewati = 0
    for baris in pembaca:
        mrn = (baris.get("patient_mrn") or "").strip()
        nama = (baris.get("patient_name") or "").strip()
        modalitas = (baris.get("modality") or "").strip().upper()
        if not (mrn and nama and modalitas):
            dilewati += 1
            continue

        accession = (baris.get("accession_number") or "").strip()
        if accession and db.scalar(
            select(Order).where(Order.accession_number == accession)
        ):
            dilewati += 1
            continue

        tanggal_lahir = None
        mentah = (baris.get("patient_birth_date") or "").strip()
        if mentah:
            try:
                tanggal_lahir = dt.date.fromisoformat(mentah)
            except ValueError:
                tanggal_lahir = None

        db.add(
            Order(
                accession_number=accession or terbitkan_accession_number(db),
                patient_mrn=mrn,
                patient_name=nama,
                patient_birth_date=tanggal_lahir,
                patient_sex=(baris.get("patient_sex") or "").strip().upper()[:1] or None,
                modality=modalitas,
                study_description=(baris.get("study_description") or "").strip(),
                referring_clinician=(baris.get("referring_clinician") or "").strip(),
                scheduled_for=dt.datetime.now(dt.timezone.utc),
                source="csv",
            )
        )
        db.flush()
        masuk += 1

    audit.record(
        db,
        action="order.impor_csv",
        user=user,
        request=request,
        object_type="order",
        object_id="-",
        detail={"masuk": masuk, "dilewati": dilewati, "berkas": berkas.filename},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/order?pesan={masuk}+order+diimpor,+{dilewati}+dilewati", status_code=302
    )


@router.post("/order/{order_id}/batal")
def batalkan_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(PETUGAS),
):
    order = db.get(Order, order_id)
    if order is None or order.status == "matched":
        return RedirectResponse(
            "/order?galat=Order+tidak+bisa+dibatalkan", status_code=302
        )
    order.status = "cancelled"
    audit.record(
        db,
        action="order.batal",
        user=user,
        request=request,
        object_type="order",
        object_id=order.accession_number,
        commit=False,
    )
    db.commit()
    return RedirectResponse("/order?pesan=Order+dibatalkan", status_code=302)
