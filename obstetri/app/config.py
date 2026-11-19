"""Pengaturan aplikasi."""

import os
from pathlib import Path


class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://obstetri:obstetri@postgres:5432/obstetri",
    )
    session_secret: str = os.environ.get("SESSION_SECRET", "")
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    hospital_name: str = os.environ.get(
        "HOSPITAL_NAME", "RS Universitas Sumatera Utara"
    )
    unit_name: str = os.environ.get(
        "UNIT_NAME", "Instalasi Kebidanan dan Kandungan"
    )
    berkas_dir: Path = Path(os.environ.get("BERKAS_DIR", "/data/berkas"))

    # Batas ukuran satu berkas. Rekaman CTG satu jam umumnya jauh di bawah ini.
    maks_ukuran_mb: int = int(os.environ.get("MAKS_UKURAN_MB", "200"))


settings = Settings()

if not settings.session_secret:
    raise RuntimeError("SESSION_SECRET belum diisi. Buat dengan: openssl rand -hex 32")
