"""Arsip Pemeriksaan Obstetri — titik rakit aplikasi."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from starlette.middleware.sessions import SessionMiddleware

import audit  # noqa: F401  (dipakai router)
from config import settings
from db import SessionLocal, engine, get_db
from models import Base, CtgReading, Examination, ImportItem, Patient, User
from routers import admin, auth, examinations, imports, patients
from security import hash_password, require_user
from services import berkas as svc
from templating import templates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("obstetri")


def siapkan_basis_data() -> None:
    Base.metadata.create_all(engine)

    db: Session = SessionLocal()
    try:
        if db.scalar(select(func.count(User.id))):
            return
        if not settings.admin_password:
            log.error(
                "ADMIN_PASSWORD kosong — akun admin pertama tidak dibuat. "
                "Isi ADMIN_PASSWORD di .env lalu jalankan ulang."
            )
            return
        db.add(
            User(
                username=settings.admin_username.strip().lower(),
                full_name="Administrator Sistem",
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        db.commit()
        log.info("Akun admin pertama dibuat: %s", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for percobaan in range(1, 31):
        try:
            siapkan_basis_data()
            break
        except OperationalError:
            log.info("Menunggu basis data siap (%d/30)...", percobaan)
            await asyncio.sleep(2)
    else:
        raise RuntimeError("Basis data tidak kunjung siap.")

    svc.siapkan_folder()
    yield


app = FastAPI(
    title="Arsip Pemeriksaan Obstetri",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="obstetri_sesi",
    same_site="lax",
    # Untuk produksi di belakang HTTPS, ubah menjadi True.
    https_only=False,
    max_age=10 * 60 * 60,
)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(examinations.router)
app.include_router(imports.router)
app.include_router(admin.router)


@app.exception_handler(HTTPException)
async def tangani_galat(request: Request, exc: HTTPException):
    menerima_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 401 and menerima_html:
        return RedirectResponse("/masuk", status_code=302)
    if exc.status_code == 403 and menerima_html:
        return templates.TemplateResponse(
            request, "error.html", {"kode": 403, "pesan": exc.detail}, status_code=403
        )
    return await http_exception_handler(request, exc)


@app.get("/sehat")
def sehat():
    return {"aplikasi": "ok"}


@app.get("/", response_class=HTMLResponse)
def beranda(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    hari_ini = dt.date.today()
    awal_hari = dt.datetime.combine(hari_ini, dt.time.min)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "jumlah_pasien": db.scalar(select(func.count(Patient.id))) or 0,
            "pemeriksaan_hari_ini": db.scalar(
                select(func.count(Examination.id)).where(
                    Examination.performed_at >= awal_hari
                )
            )
            or 0,
            "menunggu_impor": db.scalar(
                select(func.count(ImportItem.id)).where(ImportItem.status == "unmatched")
            )
            or 0,
            "belum_disahkan": db.scalar(
                select(func.count(CtgReading.id)).where(CtgReading.status == "draft")
            )
            or 0,
            "terbaru": db.scalars(
                select(Examination).order_by(Examination.performed_at.desc()).limit(10)
            ).all(),
        },
    )
