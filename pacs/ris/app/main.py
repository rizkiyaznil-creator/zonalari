"""Aplikasi RIS — titik rakit seluruh bagian."""

from __future__ import annotations

import asyncio
import contextlib
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

from .config import settings
from .db import SessionLocal, engine, get_db
from .models import Base, Order, Study, User
from .poller import run_poller
from .routers import admin, auth, inbox, internal, orders, studies
from .security import hash_password, require_user
from .services import orthanc
from .templating import templates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("ris")


def siapkan_basis_data() -> None:
    """Membuat tabel dan akun admin pertama."""
    Base.metadata.create_all(engine)

    db: Session = SessionLocal()
    try:
        sudah_ada = db.scalar(select(func.count(User.id)))
        if sudah_ada:
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

    tugas = asyncio.create_task(run_poller())
    try:
        yield
    finally:
        tugas.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tugas


app = FastAPI(title="PACS RS USU", lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="ris_sesi",
    same_site="lax",
    # Untuk produksi di belakang HTTPS, ubah menjadi True.
    https_only=False,
    max_age=8 * 60 * 60,
)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(inbox.router)
app.include_router(orders.router)
app.include_router(studies.router)
app.include_router(admin.router)


@app.exception_handler(HTTPException)
async def tangani_galat_http(request: Request, exc: HTTPException):
    """Pengunjung yang belum masuk diarahkan ke halaman login, bukan diberi JSON."""
    menerima_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 401 and menerima_html:
        return RedirectResponse("/masuk", status_code=302)
    if exc.status_code == 403 and menerima_html:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"kode": 403, "pesan": exc.detail},
            status_code=403,
        )
    return await http_exception_handler(request, exc)


@app.get("/sehat")
def sehat():
    """Dipakai pemantauan untuk memastikan aplikasi dan Orthanc masih hidup."""
    return {"ris": "ok", "orthanc": "ok" if orthanc.is_alive() else "tidak terjangkau"}


@app.get("/", response_class=HTMLResponse)
def beranda(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    belum_verifikasi = db.scalar(
        select(func.count(Study.id)).where(Study.status == "unverified")
    )
    terverifikasi = db.scalar(
        select(func.count(Study.id)).where(Study.status == "verified")
    )
    order_menunggu = db.scalar(
        select(func.count(Order.id)).where(Order.status == "pending")
    )

    statistik_arsip = None
    try:
        statistik_arsip = orthanc.server_statistics()
    except orthanc.OrthancError:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "belum_verifikasi": belum_verifikasi or 0,
            "terverifikasi": terverifikasi or 0,
            "order_menunggu": order_menunggu or 0,
            "statistik_arsip": statistik_arsip,
            "orthanc_hidup": statistik_arsip is not None,
        },
    )
