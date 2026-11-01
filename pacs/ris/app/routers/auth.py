"""Masuk dan keluar akun."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import User
from ..security import (
    get_current_user,
    login_user,
    logout_user,
    verify_password,
)
from ..templating import templates

router = APIRouter(tags=["akun"])


@router.get("/masuk", response_class=HTMLResponse)
def form_masuk(request: Request, user: User | None = Depends(get_current_user)):
    if user is not None:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"galat": None})


@router.post("/masuk", response_class=HTMLResponse)
def proses_masuk(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.username == username.strip().lower()))

    # Pesan galat sengaja dibuat sama untuk username salah maupun kata sandi
    # salah, agar tidak bisa dipakai menebak akun mana yang ada.
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        audit.record(
            db,
            action="akun.masuk.gagal",
            request=request,
            object_type="user",
            object_id=username,
        )
        return templates.TemplateResponse(
            request,
            "login.html",
            {"galat": "Nama pengguna atau kata sandi salah."},
            status_code=401,
        )

    login_user(request, user)
    audit.record(
        db,
        action="akun.masuk",
        user=user,
        request=request,
        object_type="user",
        object_id=user.id,
    )
    return RedirectResponse("/", status_code=302)


@router.get("/keluar")
def keluar(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        audit.record(
            db,
            action="akun.keluar",
            user=user,
            request=request,
            object_type="user",
            object_id=user.id,
        )
    logout_user(request)
    return RedirectResponse("/masuk", status_code=302)
