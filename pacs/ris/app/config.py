"""Pengaturan aplikasi, dibaca dari variabel lingkungan."""

import os


class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://orthanc:orthanc@postgres:5432/ris"
    )
    orthanc_url: str = os.environ.get("ORTHANC_URL", "http://orthanc:8042").rstrip("/")
    session_secret: str = os.environ.get("SESSION_SECRET", "")
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    hospital_name: str = os.environ.get(
        "HOSPITAL_NAME", "RS Universitas Sumatera Utara"
    )
    upload_dir: str = os.environ.get("UPLOAD_DIR", "/data/uploads")

    # Token yang dipakai layanan pemantau folder untuk menitipkan berkas ke RIS.
    ingest_token: str = os.environ.get("INGEST_TOKEN", "")

    # Jeda antar-pemeriksaan study baru di Orthanc.
    poll_seconds: float = float(os.environ.get("POLL_SECONDS", "3"))


settings = Settings()

if not settings.session_secret:
    raise RuntimeError(
        "SESSION_SECRET belum diisi. Buat dengan: openssl rand -hex 32"
    )
