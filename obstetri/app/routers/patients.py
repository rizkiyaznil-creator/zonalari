"""Pasien: daftar, pencarian, dan riwayat pemeriksaan."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

import audit
from db import get_db
from models import Examination, Patient, User
from security import require_user
from templating import templates

router = APIRouter(tags=["pasien"])


def _tanggal_opsional(nilai: str) -> dt.date | None:
    if not nilai:
        return None
    try:
        return dt.date.fromisoformat(nilai)
    except ValueError:
        return None


def _angka_opsional(nilai: str) -> int | None:
    nilai = (nilai or "").strip()
    if not nilai:
        return None
    try:
        angka = int(nilai)
    except ValueError:
        return None
    return angka if angka >= 0 else None


@router.get("/pasien", response_class=HTMLResponse)
def daftar_pasien(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    kata = (request.query_params.get("q") or "").strip()

    pernyataan = select(Patient)
    if kata:
        pola = f"%{kata}%"
        pernyataan = pernyataan.where(
            or_(Patient.name.ilike(pola), Patient.mrn.ilike(pola))
        )

    pasien = db.scalars(pernyataan.order_by(Patient.name).limit(200)).all()

    jumlah = {
        pid: n
        for pid, n in db.execute(
            select(Examination.patient_id, func.count(Examination.id)).group_by(
                Examination.patient_id
            )
        ).all()
    }

    if kata:
        audit.record(
            db,
            action="pasien.cari",
            user=user,
            request=request,
            object_type="patient",
            detail={"kata_kunci": kata, "jumlah_hasil": len(pasien)},
        )

    return templates.TemplateResponse(
        request,
        "patients.html",
        {
            "user": user,
            "pasien": pasien,
            "kata": kata,
            "jumlah_pemeriksaan": jumlah,
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/pasien")
def tambah_pasien(
    request: Request,
    mrn: str = Form(...),
    name: str = Form(...),
    birth_date: str = Form(""),
    phone: str = Form(""),
    gravida: str = Form(""),
    para: str = Form(""),
    abortus: str = Form(""),
    hpht: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    mrn = mrn.strip()
    if db.scalar(select(Patient).where(Patient.mrn == mrn)):
        return RedirectResponse(
            "/pasien?galat=Nomor+rekam+medis+sudah+terdaftar", status_code=302
        )

    pasien = Patient(
        mrn=mrn,
        name=name.strip(),
        birth_date=_tanggal_opsional(birth_date),
        phone=phone.strip(),
        gravida=_angka_opsional(gravida),
        para=_angka_opsional(para),
        abortus=_angka_opsional(abortus),
        hpht=_tanggal_opsional(hpht),
        note=note.strip(),
    )
    db.add(pasien)
    db.flush()

    audit.record(
        db,
        action="pasien.tambah",
        user=user,
        request=request,
        object_type="patient",
        object_id=pasien.mrn,
        detail={"nama": pasien.name},
        commit=False,
    )
    db.commit()
    return RedirectResponse(f"/pasien/{pasien.id}", status_code=302)


@router.get("/pasien/{pasien_id}", response_class=HTMLResponse)
def detail_pasien(
    pasien_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    pasien = db.get(Patient, pasien_id)
    if pasien is None:
        return RedirectResponse("/pasien", status_code=302)

    audit.record(
        db,
        action="pasien.buka",
        user=user,
        request=request,
        object_type="patient",
        object_id=pasien.mrn,
        detail={"nama": pasien.name},
    )

    return templates.TemplateResponse(
        request,
        "patient_detail.html",
        {
            "user": user,
            "pasien": pasien,
            "hari_ini": dt.date.today(),
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/pasien/{pasien_id}/ubah")
def ubah_pasien(
    pasien_id: int,
    request: Request,
    name: str = Form(...),
    birth_date: str = Form(""),
    phone: str = Form(""),
    gravida: str = Form(""),
    para: str = Form(""),
    abortus: str = Form(""),
    hpht: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    pasien = db.get(Patient, pasien_id)
    if pasien is None:
        return RedirectResponse("/pasien", status_code=302)

    sebelum = {
        "name": pasien.name,
        "birth_date": str(pasien.birth_date or ""),
        "hpht": str(pasien.hpht or ""),
    }

    pasien.name = name.strip()
    pasien.birth_date = _tanggal_opsional(birth_date)
    pasien.phone = phone.strip()
    pasien.gravida = _angka_opsional(gravida)
    pasien.para = _angka_opsional(para)
    pasien.abortus = _angka_opsional(abortus)
    pasien.hpht = _tanggal_opsional(hpht)
    pasien.note = note.strip()

    audit.record(
        db,
        action="pasien.ubah",
        user=user,
        request=request,
        object_type="patient",
        object_id=pasien.mrn,
        detail={
            "sebelum": sebelum,
            "sesudah": {
                "name": pasien.name,
                "birth_date": str(pasien.birth_date or ""),
                "hpht": str(pasien.hpht or ""),
            },
        },
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/pasien/{pasien.id}?pesan=Data+pasien+diperbarui", status_code=302
    )
