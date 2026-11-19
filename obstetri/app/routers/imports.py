"""Impor massal rekaman dari USB.

Alat CTG umumnya menyimpan rekaman ke USB sebagai sekumpulan PDF. Berkas-berkas
itu diunggah sekaligus ke sini, lalu dicocokkan satu per satu ke pasien. Tidak
ada pencocokan otomatis: nama yang diketik operator di alat terlalu sering
berbeda dengan data pasien untuk dipercaya mentah-mentah.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

import audit
from db import get_db
from models import (
    JENIS_PEMERIKSAAN,
    Attachment,
    Examination,
    ImportItem,
    Patient,
    User,
)
from security import require_user
from services import berkas as svc
from templating import templates

router = APIRouter(tags=["impor"])


@dataclass
class Saran:
    pasien: Patient
    skor: int
    alasan: list[str]


# Sapaan yang lazim diketik operator di alat dan tidak membedakan pasien.
_SAPAAN = {"NY", "NYONYA", "TN", "NN", "SDR", "SDRI", "AN", "BY", "MRS", "MR", "MS"}


def _normalkan(teks: str) -> str:
    """Menyeragamkan nama untuk dibandingkan.

    Tanda ^ ikut dibersihkan karena sebagian alat memakai format nama DICOM
    ("KELUARGA^DEPAN") meski berkas keluarannya PDF biasa.
    """
    kasar = (teks or "").upper().replace("^", " ")
    kasar = "".join(huruf if huruf.isalnum() else " " for huruf in kasar)
    return " ".join(kata for kata in kasar.split() if kata not in _SAPAAN)


def saran_pasien(db: Session, item: ImportItem, batas: int = 6) -> list[Saran]:
    """Mengurutkan pasien yang paling mungkin cocok dengan sebuah berkas.

    Hanya alat bantu urut. Keputusan tetap di tangan petugas.
    """
    petunjuk = _normalkan(item.hint_name)
    if not petunjuk:
        return []

    hasil: list[Saran] = []
    for pasien in db.scalars(select(Patient)).all():
        rasio = SequenceMatcher(None, petunjuk, _normalkan(pasien.name)).ratio()
        if rasio < 0.5:
            continue
        alasan = ["nama sama persis" if rasio >= 0.95 else "nama mirip"]
        hasil.append(Saran(pasien=pasien, skor=int(rasio * 100), alasan=alasan))

    hasil.sort(key=lambda s: s.skor, reverse=True)
    return hasil[:batas]


@router.get("/impor", response_class=HTMLResponse)
def halaman_impor(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    menunggu = db.scalars(
        select(ImportItem)
        .where(ImportItem.status == "unmatched")
        .order_by(ImportItem.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "import_list.html",
        {
            "user": user,
            "menunggu": menunggu,
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/impor")
async def unggah_impor(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    masuk = 0
    duplikat = 0
    gagal: list[str] = []

    for item in files:
        data = await item.read()
        if not data:
            continue
        try:
            akhiran = svc.periksa(item.filename or "", item.content_type or "", data)
        except svc.BerkasDitolak as exc:
            gagal.append(f"{item.filename}: {exc}")
            continue

        sidik = svc.sidik_jari(data)
        if db.scalar(select(ImportItem).where(ImportItem.sha256 == sidik)):
            duplikat += 1
            continue

        nama_simpan = svc.simpan(data, akhiran)
        db.add(
            ImportItem(
                original_name=(item.filename or "tanpa-nama")[:255],
                stored_name=nama_simpan,
                content_type=item.content_type or "",
                size_bytes=len(data),
                sha256=sidik,
                page_count=svc.jumlah_halaman(nama_simpan),
                thumbnail_name=svc.buat_pratinjau(nama_simpan),
                hint_name=svc.tebak_nama_pasien(nama_simpan),
                hint_datetime=svc.tebak_waktu(item.filename or ""),
                created_by_id=user.id,
            )
        )
        masuk += 1

    audit.record(
        db,
        action="impor.unggah",
        user=user,
        request=request,
        object_type="import",
        detail={"masuk": masuk, "duplikat": duplikat, "gagal": gagal},
        commit=False,
    )
    db.commit()

    pesan = f"{masuk}+berkas+masuk"
    if duplikat:
        pesan += f",+{duplikat}+sudah+pernah+diimpor"
    return RedirectResponse(f"/impor?pesan={pesan}", status_code=302)


@router.get("/impor/{item_id}", response_class=HTMLResponse)
def cocokkan_halaman(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(ImportItem, item_id)
    if item is None or item.status != "unmatched":
        return RedirectResponse("/impor", status_code=302)

    return templates.TemplateResponse(
        request,
        "import_match.html",
        {
            "user": user,
            "item": item,
            "saran": saran_pasien(db, item),
            "semua_pasien": db.scalars(select(Patient).order_by(Patient.name)).all(),
            "sekarang": (item.hint_datetime or dt.datetime.now()).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "galat": request.query_params.get("galat"),
        },
    )


@router.get("/impor/{item_id}/berkas")
def berkas_impor(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(ImportItem, item_id)
    if item is None:
        return Response(status_code=404)
    jalur = svc.jalur(item.stored_name)
    if not jalur.exists():
        return Response(status_code=410)
    jenis = "application/pdf" if item.stored_name.endswith(".pdf") else "image/jpeg"
    return FileResponse(
        jalur,
        media_type=jenis,
        headers={"Content-Disposition": f'inline; filename="{item.original_name}"'},
    )


@router.get("/impor/{item_id}/pratinjau")
def pratinjau_impor(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(ImportItem, item_id)
    if item is None or not item.thumbnail_name:
        return Response(status_code=404)
    jalur = svc.jalur_pratinjau(item.thumbnail_name)
    if not jalur.exists():
        return Response(status_code=404)
    return FileResponse(jalur, media_type="image/png")


@router.post("/impor/{item_id}/cocokkan")
def cocokkan(
    item_id: int,
    request: Request,
    patient_id: int = Form(...),
    kind: str = Form(...),
    performed_at: str = Form(...),
    indication: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(ImportItem, item_id)
    pasien = db.get(Patient, patient_id)
    if item is None or item.status != "unmatched" or pasien is None:
        return RedirectResponse("/impor?galat=Data+tidak+ditemukan", status_code=302)
    if kind not in JENIS_PEMERIKSAAN:
        return RedirectResponse(
            f"/impor/{item_id}?galat=Jenis+pemeriksaan+tidak+dikenal", status_code=302
        )

    try:
        waktu = dt.datetime.fromisoformat(performed_at)
    except ValueError:
        return RedirectResponse(
            f"/impor/{item_id}?galat=Tanggal+pemeriksaan+tidak+sah", status_code=302
        )

    usia = pasien.usia_kehamilan(waktu.date())
    pemeriksaan = Examination(
        patient_id=pasien.id,
        kind=kind,
        performed_at=waktu,
        gestational_weeks=usia[0] if usia else None,
        gestational_days=usia[1] if usia else None,
        indication=indication.strip(),
        created_by_id=user.id,
    )
    db.add(pemeriksaan)
    db.flush()

    db.add(
        Attachment(
            examination_id=pemeriksaan.id,
            original_name=item.original_name,
            stored_name=item.stored_name,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            page_count=item.page_count,
            thumbnail_name=item.thumbnail_name,
            uploaded_by_id=user.id,
        )
    )

    item.status = "matched"
    item.examination_id = pemeriksaan.id

    audit.record(
        db,
        action="impor.cocokkan",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={
            "berkas": item.original_name,
            "petunjuk_nama_di_berkas": item.hint_name,
            "pasien_dipilih": pasien.mrn,
            "nama_pasien": pasien.name,
        },
        commit=False,
    )
    db.commit()
    return RedirectResponse(f"/pemeriksaan/{pemeriksaan.id}", status_code=302)


@router.post("/impor/{item_id}/tolak")
def tolak(
    item_id: int,
    request: Request,
    alasan: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Menandai berkas sebagai bukan rekaman pasien.

    Berkasnya tidak dihapus — menghapus arsip adalah tindakan tersendiri.
    """
    item = db.get(ImportItem, item_id)
    if item is None:
        return RedirectResponse("/impor", status_code=302)

    item.status = "rejected"
    item.rejected_reason = alasan.strip()

    audit.record(
        db,
        action="impor.tolak",
        user=user,
        request=request,
        object_type="import",
        object_id=item.id,
        detail={"berkas": item.original_name, "alasan": item.rejected_reason},
        commit=False,
    )
    db.commit()
    return RedirectResponse("/impor?pesan=Berkas+ditandai+bukan+rekaman+pasien", status_code=302)
