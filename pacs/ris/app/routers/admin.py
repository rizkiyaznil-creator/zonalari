"""Administrasi: pengguna dan jejak audit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import ROLES, AuditLog, User
from ..security import hash_password, require_roles
from ..templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN = require_roles("admin")


@router.get("/pengguna", response_class=HTMLResponse)
def daftar_pengguna(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN),
):
    pengguna = db.scalars(select(User).order_by(User.username)).all()
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "user": user,
            "pengguna": pengguna,
            "peran": ROLES,
            "pesan": request.query_params.get("pesan"),
            "galat": request.query_params.get("galat"),
        },
    )


@router.post("/pengguna")
def buat_pengguna(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN),
):
    username = username.strip().lower()
    if role not in ROLES:
        return RedirectResponse("/admin/pengguna?galat=Peran+tidak+dikenal", status_code=302)
    if len(password) < 8:
        return RedirectResponse(
            "/admin/pengguna?galat=Kata+sandi+minimal+8+karakter", status_code=302
        )
    if db.scalar(select(User).where(User.username == username)):
        return RedirectResponse(
            "/admin/pengguna?galat=Nama+pengguna+sudah+dipakai", status_code=302
        )

    baru = User(
        username=username,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role,
    )
    db.add(baru)
    db.flush()
    audit.record(
        db,
        action="pengguna.buat",
        user=user,
        request=request,
        object_type="user",
        object_id=baru.username,
        detail={"peran": role},
        commit=False,
    )
    db.commit()
    return RedirectResponse(
        f"/admin/pengguna?pesan=Pengguna+{username}+dibuat", status_code=302
    )


@router.post("/pengguna/{user_id}/nonaktif")
def nonaktifkan(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN),
):
    target = db.get(User, user_id)
    if target is None:
        return RedirectResponse("/admin/pengguna", status_code=302)
    if target.id == user.id:
        return RedirectResponse(
            "/admin/pengguna?galat=Tidak+bisa+menonaktifkan+akun+sendiri",
            status_code=302,
        )
    target.is_active = not target.is_active
    audit.record(
        db,
        action="pengguna.ubah_status",
        user=user,
        request=request,
        object_type="user",
        object_id=target.username,
        detail={"aktif": target.is_active},
        commit=False,
    )
    db.commit()
    return RedirectResponse("/admin/pengguna?pesan=Status+pengguna+diubah", status_code=302)


@router.get("/audit", response_class=HTMLResponse)
def jejak_audit(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN),
):
    baris = db.scalars(
        select(AuditLog).order_by(AuditLog.ts.desc()).limit(300)
    ).all()
    return templates.TemplateResponse(
        request, "admin_audit.html", {"user": user, "baris": baris}
    )
