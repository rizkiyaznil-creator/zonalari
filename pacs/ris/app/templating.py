"""Penyiapan template bersama."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from .config import settings
from .models import ROLE_LABELS

TEMPLATE_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals["hospital_name"] = settings.hospital_name
templates.env.globals["role_labels"] = ROLE_LABELS


def status_label(status: str) -> str:
    return {
        "unverified": "Belum diverifikasi",
        "verified": "Terverifikasi",
        "rejected": "Ditolak",
        "pending": "Menunggu citra",
        "matched": "Sudah dicocokkan",
        "cancelled": "Dibatalkan",
    }.get(status, status)


def source_label(source: str) -> str:
    return {
        "cstore": "Kiriman alat (C-STORE)",
        "watcher": "Folder pantauan",
        "upload": "Unggah manual",
        "manual": "Dibuat manual",
        "csv": "Impor CSV",
        "simrs": "SIMRS",
    }.get(source, source)


def format_dicom_date(value: str) -> str:
    if value and len(value) == 8 and value.isdigit():
        return f"{value[6:8]}-{value[4:6]}-{value[0:4]}"
    return value or "-"


templates.env.filters["status_label"] = status_label
templates.env.filters["source_label"] = source_label
templates.env.filters["tanggal_dicom"] = format_dicom_date
