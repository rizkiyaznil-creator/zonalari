"""Penyiapan template bersama."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from config import settings
from models import (
    AKSELERASI,
    DESELERASI,
    GERAK_JANIN,
    JENIS_PEMERIKSAAN,
    KATEGORI_FIGO,
    KESIMPULAN_NST,
    ROLE_LABELS,
    VARIABILITAS,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

templates.env.globals.update(
    hospital_name=settings.hospital_name,
    unit_name=settings.unit_name,
    role_labels=ROLE_LABELS,
    jenis_pemeriksaan=JENIS_PEMERIKSAAN,
    pilihan_variabilitas=VARIABILITAS,
    pilihan_akselerasi=AKSELERASI,
    pilihan_deselerasi=DESELERASI,
    pilihan_gerak=GERAK_JANIN,
    pilihan_kesimpulan=KESIMPULAN_NST,
    pilihan_figo=KATEGORI_FIGO,
)

_BULAN = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def tanggal(nilai) -> str:
    if nilai is None:
        return "-"
    return f"{nilai.day} {_BULAN[nilai.month]} {nilai.year}"


def tanggal_jam(nilai) -> str:
    if nilai is None:
        return "-"
    return f"{tanggal(nilai)}, {nilai:%H:%M}"


def umur(tanggal_lahir) -> str:
    if tanggal_lahir is None:
        return "-"
    import datetime as dt

    hari_ini = dt.date.today()
    tahun = hari_ini.year - tanggal_lahir.year
    if (hari_ini.month, hari_ini.day) < (tanggal_lahir.month, tanggal_lahir.day):
        tahun -= 1
    return f"{tahun} tahun"


templates.env.filters["tanggal"] = tanggal
templates.env.filters["tanggal_jam"] = tanggal_jam
templates.env.filters["umur"] = umur
