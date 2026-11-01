"""Titik masuk internal: gerbang izin untuk Caddy dan penitipan berkas dari watcher."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..poller import ingest_study
from ..security import get_current_user
from ..services import orthanc
from ..models import User

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/authz")
def authz(request: Request, user: User | None = Depends(get_current_user)) -> Response:
    """Gerbang izin untuk Caddy sebelum citra boleh diambil.

    Tanpa ini, siapa pun di jaringan RS bisa mengunduh citra pasien langsung
    dari Orthanc tanpa akun. Caddy memanggil endpoint ini untuk setiap permintaan
    ke /dicom-web, /wado, dan Stone Web Viewer.
    """
    if user is None:
        return RedirectResponse("/masuk", status_code=302)
    return Response(
        status_code=200,
        headers={"X-Auth-User": user.username, "X-Auth-Role": user.role},
    )


@router.post("/ingest")
async def ingest(
    request: Request,
    berkas: UploadFile = File(...),
    sumber: str = Form("watcher"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Menerima satu berkas DICOM dari layanan pemantau folder.

    Watcher sengaja tidak menulis langsung ke Orthanc: semua berkas lewat RIS
    agar sumber masuknya tercatat dan study langsung terdaftar di kotak masuk.
    """
    token = request.headers.get("x-ingest-token", "")
    if not settings.ingest_token or not hmac.compare_digest(
        token, settings.ingest_token
    ):
        raise HTTPException(status_code=401, detail="Token penitipan tidak sah")

    data = await berkas.read()
    try:
        hasil = orthanc.upload_instance(data)
    except orthanc.OrthancError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    parent_study = hasil.get("ParentStudy")
    if parent_study:
        ingest_study(db, parent_study, source=sumber)

    return JSONResponse(
        {
            "status": hasil.get("Status", "Success"),
            "instance": hasil.get("ID"),
            "study": parent_study,
        }
    )
