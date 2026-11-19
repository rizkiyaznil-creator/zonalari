"""Pemeriksaan: rekam, lampirkan berkas, interpretasi, dan pengesahan."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

import audit
from db import get_db
from models import (
    JENIS_PEMERIKSAAN,
    Attachment,
    CtgReading,
    Examination,
    Patient,
    User,
)
from security import require_user
from services import berkas as svc
from templating import templates

router = APIRouter(tags=["pemeriksaan"])


def _angka_opsional(nilai: str, minimum: int = 0, maksimum: int = 10_000) -> int | None:
    nilai = (nilai or "").strip()
    if not nilai:
        return None
    try:
        angka = int(nilai)
    except ValueError:
        return None
    return angka if minimum <= angka <= maksimum else None


def _pilihan(nilai: str, sah: dict[str, str]) -> str | None:
    nilai = (nilai or "").strip()
    return nilai if nilai in sah else None


@router.post("/pasien/{pasien_id}/pemeriksaan")
def buat_pemeriksaan(
    pasien_id: int,
    request: Request,
    kind: str = Form(...),
    performed_at: str = Form(...),
    indication: str = Form(""),
    gestational_weeks: str = Form(""),
    gestational_days: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    pasien = db.get(Patient, pasien_id)
    if pasien is None:
        return RedirectResponse("/pasien", status_code=302)
    if kind not in JENIS_PEMERIKSAAN:
        return RedirectResponse(
            f"/pasien/{pasien_id}?galat=Jenis+pemeriksaan+tidak+dikenal", status_code=302
        )

    try:
        waktu = dt.datetime.fromisoformat(performed_at)
    except ValueError:
        return RedirectResponse(
            f"/pasien/{pasien_id}?galat=Tanggal+pemeriksaan+tidak+sah", status_code=302
        )

    minggu = _angka_opsional(gestational_weeks, 0, 45)
    hari = _angka_opsional(gestational_days, 0, 6)

    # Bila usia kehamilan tidak diisi, dihitung dari HPHT. HPHT sering tidak
    # diketahui pasti, jadi isian manual selalu menang.
    if minggu is None:
        dihitung = pasien.usia_kehamilan(waktu.date())
        if dihitung is not None:
            minggu, hari = dihitung

    pemeriksaan = Examination(
        patient_id=pasien.id,
        kind=kind,
        performed_at=waktu,
        gestational_weeks=minggu,
        gestational_days=hari,
        indication=indication.strip(),
        created_by_id=user.id,
    )
    db.add(pemeriksaan)
    db.flush()

    audit.record(
        db,
        action="pemeriksaan.buat",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"pasien": pasien.mrn, "jenis": kind},
        commit=False,
    )
    db.commit()
    return RedirectResponse(f"/pemeriksaan/{pemeriksaan.id}", status_code=302)


@router.get("/pemeriksaan/{pemeriksaan_id}", response_class=HTMLResponse)
def detail_pemeriksaan(
    pemeriksaan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None:
        return RedirectResponse("/pasien", status_code=302)

    audit.record(
        db,
        action="pemeriksaan.buka",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"pasien": pemeriksaan.patient.mrn},
    )

    return templates.TemplateResponse(
        request,
        "examination_detail.html",
        {
            "user": user,
            "p": pemeriksaan,
            "pasien": pemeriksaan.patient,
            "bacaan": pemeriksaan.reading,
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/pemeriksaan/{pemeriksaan_id}/lampiran")
async def unggah_lampiran(
    pemeriksaan_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None:
        return RedirectResponse("/pasien", status_code=302)

    masuk = 0
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
        sudah_ada = any(l.sha256 == sidik for l in pemeriksaan.attachments)
        if sudah_ada:
            gagal.append(f"{item.filename}: berkas yang sama sudah dilampirkan")
            continue

        nama_simpan = svc.simpan(data, akhiran)
        db.add(
            Attachment(
                examination_id=pemeriksaan.id,
                original_name=(item.filename or "tanpa-nama")[:255],
                stored_name=nama_simpan,
                content_type=item.content_type or "",
                size_bytes=len(data),
                sha256=sidik,
                page_count=svc.jumlah_halaman(nama_simpan),
                thumbnail_name=svc.buat_pratinjau(nama_simpan),
                uploaded_by_id=user.id,
            )
        )
        masuk += 1

    audit.record(
        db,
        action="lampiran.unggah",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"masuk": masuk, "gagal": gagal},
        commit=False,
    )
    db.commit()

    pesan = f"{masuk}+berkas+dilampirkan"
    if gagal:
        pesan += f"&galat={len(gagal)}+berkas+ditolak:+{gagal[0][:80]}"
    return RedirectResponse(
        f"/pemeriksaan/{pemeriksaan.id}?pesan={pesan}", status_code=302
    )


@router.get("/berkas/{lampiran_id}")
def ambil_berkas(
    lampiran_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    lampiran = db.get(Attachment, lampiran_id)
    if lampiran is None:
        return Response(status_code=404)

    jalur = svc.jalur(lampiran.stored_name)
    if not jalur.exists():
        return Response("Berkas tidak ditemukan di arsip.", status_code=410)

    audit.record(
        db,
        action="berkas.buka",
        user=user,
        request=request,
        object_type="attachment",
        object_id=lampiran.id,
        detail={
            "pemeriksaan": lampiran.examination_id,
            "pasien": lampiran.examination.patient.mrn,
            "berkas": lampiran.original_name,
        },
    )

    jenis = "application/pdf" if lampiran.stored_name.endswith(".pdf") else None
    return FileResponse(
        jalur,
        media_type=jenis or lampiran.content_type or "application/octet-stream",
        # inline agar PDF langsung tampil di peramban, bukan terunduh.
        headers={
            "Content-Disposition": f'inline; filename="{lampiran.original_name}"'
        },
    )


@router.get("/berkas/{lampiran_id}/pratinjau")
def ambil_pratinjau(
    lampiran_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    lampiran = db.get(Attachment, lampiran_id)
    if lampiran is None or not lampiran.thumbnail_name:
        return Response(status_code=404)
    jalur = svc.jalur_pratinjau(lampiran.thumbnail_name)
    if not jalur.exists():
        return Response(status_code=404)
    return FileResponse(jalur, media_type="image/png")


@router.post("/lampiran/{lampiran_id}/hapus")
def hapus_lampiran(
    lampiran_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    lampiran = db.get(Attachment, lampiran_id)
    if lampiran is None:
        return RedirectResponse("/pasien", status_code=302)

    pemeriksaan_id = lampiran.examination_id
    if lampiran.examination.reading and lampiran.examination.reading.status == "final":
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}"
            "?galat=Hasil+sudah+disahkan,+lampiran+tidak+boleh+dihapus",
            status_code=302,
        )

    audit.record(
        db,
        action="lampiran.hapus",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan_id,
        detail={"berkas": lampiran.original_name, "sha256": lampiran.sha256},
        commit=False,
    )
    svc.hapus(lampiran.stored_name, lampiran.thumbnail_name)
    db.delete(lampiran)
    db.commit()
    return RedirectResponse(
        f"/pemeriksaan/{pemeriksaan_id}?pesan=Lampiran+dihapus", status_code=302
    )


@router.post("/pemeriksaan/{pemeriksaan_id}/interpretasi")
def simpan_interpretasi(
    pemeriksaan_id: int,
    request: Request,
    baseline_bpm: str = Form(""),
    variability: str = Form(""),
    acceleration: str = Form(""),
    deceleration: str = Form(""),
    contractions_per10: str = Form(""),
    fetal_movement: str = Form(""),
    duration_minutes: str = Form(""),
    conclusion: str = Form(""),
    figo_category: str = Form(""),
    advice: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    from models import (
        AKSELERASI,
        DESELERASI,
        GERAK_JANIN,
        KATEGORI_FIGO,
        KESIMPULAN_NST,
        VARIABILITAS,
    )

    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None:
        return RedirectResponse("/pasien", status_code=302)

    bacaan = pemeriksaan.reading
    if bacaan is None:
        bacaan = CtgReading(examination_id=pemeriksaan.id)
        db.add(bacaan)

    # Hasil yang sudah disahkan tidak boleh diubah diam-diam. Membukanya kembali
    # adalah tindakan tersendiri yang tercatat.
    if bacaan.status == "final":
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}"
            "?galat=Hasil+sudah+disahkan.+Buka+kembali+lebih+dulu+bila+perlu+direvisi",
            status_code=302,
        )

    bacaan.baseline_bpm = _angka_opsional(baseline_bpm, 30, 250)
    bacaan.variability = _pilihan(variability, VARIABILITAS)
    bacaan.acceleration = _pilihan(acceleration, AKSELERASI)
    bacaan.deceleration = _pilihan(deceleration, DESELERASI)
    bacaan.contractions_per10 = _angka_opsional(contractions_per10, 0, 20)
    bacaan.fetal_movement = _pilihan(fetal_movement, GERAK_JANIN)
    bacaan.duration_minutes = _angka_opsional(duration_minutes, 0, 600)
    bacaan.conclusion = _pilihan(conclusion, KESIMPULAN_NST)
    bacaan.figo_category = _pilihan(figo_category, KATEGORI_FIGO)
    bacaan.advice = advice.strip()
    bacaan.note = note.strip()
    bacaan.updated_by_id = user.id

    audit.record(
        db,
        action="interpretasi.simpan",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"kesimpulan": bacaan.conclusion, "figo": bacaan.figo_category},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/pemeriksaan/{pemeriksaan_id}?pesan=Interpretasi+disimpan", status_code=302
    )


def _yang_belum_diisi(pemeriksaan: Examination, bacaan: CtgReading | None) -> str:
    """Menyebutkan apa yang masih kurang sebelum hasil boleh disahkan.

    Syaratnya berbeda menurut jenis pemeriksaan: NST antepartum dinilai reaktif
    atau tidak, CTG intrapartum dinilai dengan kategori FIGO, sedangkan USG
    tidak memakai penilaian CTG sama sekali dan cukup temuan tertulis.
    """
    if bacaan is None:
        return "interpretasi"
    if pemeriksaan.kind == "ctg_nst" and not bacaan.conclusion:
        return "kesimpulan+NST"
    if pemeriksaan.kind == "ctg_intrapartum" and not bacaan.figo_category:
        return "kategori+FIGO"
    if pemeriksaan.kind == "usg" and not bacaan.note.strip():
        return "temuan"
    return ""


@router.post("/pemeriksaan/{pemeriksaan_id}/sahkan")
def sahkan(
    pemeriksaan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Mengesahkan hasil. Hanya dokter — bidan boleh mengisi, tidak mengesahkan."""
    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None:
        return RedirectResponse("/pasien", status_code=302)
    if not user.boleh_mengesahkan:
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}?galat=Hanya+dokter+yang+boleh+mengesahkan",
            status_code=302,
        )

    bacaan = pemeriksaan.reading
    kurang = _yang_belum_diisi(pemeriksaan, bacaan)
    if kurang:
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}?galat=Lengkapi+dulu:+{kurang}",
            status_code=302,
        )
    if not pemeriksaan.attachments:
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}"
            "?galat=Belum+ada+rekaman+yang+dilampirkan",
            status_code=302,
        )

    bacaan.status = "final"
    bacaan.finalized_at = dt.datetime.now(dt.timezone.utc)
    bacaan.finalized_by_id = user.id

    audit.record(
        db,
        action="interpretasi.sahkan",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"pasien": pemeriksaan.patient.mrn, "kesimpulan": bacaan.conclusion},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/pemeriksaan/{pemeriksaan_id}?pesan=Hasil+disahkan", status_code=302
    )


@router.post("/pemeriksaan/{pemeriksaan_id}/buka-kembali")
def buka_kembali(
    pemeriksaan_id: int,
    request: Request,
    alasan: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Membuka kembali hasil yang sudah disahkan untuk direvisi.

    Alasannya wajib dan tercatat: hasil yang sudah disahkan mungkin sudah
    dipakai mengambil keputusan klinis.
    """
    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None or pemeriksaan.reading is None:
        return RedirectResponse("/pasien", status_code=302)
    if not user.boleh_mengesahkan:
        return RedirectResponse(
            f"/pemeriksaan/{pemeriksaan_id}?galat=Hanya+dokter+yang+boleh+membuka+kembali",
            status_code=302,
        )

    pemeriksaan.reading.status = "draft"
    audit.record(
        db,
        action="interpretasi.buka_kembali",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"alasan": alasan.strip()},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/pemeriksaan/{pemeriksaan_id}?pesan=Hasil+dibuka+kembali+untuk+revisi",
        status_code=302,
    )


@router.get("/pemeriksaan/{pemeriksaan_id}/cetak", response_class=HTMLResponse)
def cetak(
    pemeriksaan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Lembar hasil berkop RS, siap dicetak atau disimpan sebagai PDF dari peramban."""
    pemeriksaan = db.get(Examination, pemeriksaan_id)
    if pemeriksaan is None:
        return RedirectResponse("/pasien", status_code=302)

    audit.record(
        db,
        action="hasil.cetak",
        user=user,
        request=request,
        object_type="examination",
        object_id=pemeriksaan.id,
        detail={"pasien": pemeriksaan.patient.mrn},
    )

    return templates.TemplateResponse(
        request,
        "print.html",
        {
            "user": user,
            "p": pemeriksaan,
            "pasien": pemeriksaan.patient,
            "bacaan": pemeriksaan.reading,
            "dicetak_pada": dt.datetime.now(),
        },
    )
