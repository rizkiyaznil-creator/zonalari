"""Skema basis data RIS.

Catatan penting soal identitas pasien: nilai asli yang diketik petugas di konsol
alat TIDAK pernah dibuang. Kolom `original_*` menyimpannya selamanya agar setiap
perubahan identitas bisa ditelusuri balik saat audit rekam medis.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Peran pengguna ----------------------------------------------------------
# admin       : kelola pengguna, lihat audit, semua akses
# radiografer : kelola order, kotak masuk, rekonsiliasi, unggah manual
# radiolog    : baca study terverifikasi, tulis ekspertise
# dokter      : baca study terverifikasi + hasil ekspertise milik pasiennya
ROLES = ("admin", "radiografer", "radiolog", "dokter")

ROLE_LABELS = {
    "admin": "Administrator",
    "radiografer": "Radiografer",
    "radiolog": "Dokter Radiolog",
    "dokter": "Dokter Pengirim",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


class Order(Base):
    """Permintaan pemeriksaan radiologi.

    Accession number lahir di sini. Inilah satu-satunya sumber yang sah untuk
    accession number, dan SATUSEHAT mensyaratkan nomor ini sudah ada sejak order
    dibuat — bukan dikarang belakangan oleh PACS.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accession_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    patient_mrn: Mapped[str] = mapped_column(String(64), index=True)
    patient_name: Mapped[str] = mapped_column(String(160), index=True)
    patient_birth_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(1), nullable=True)

    modality: Mapped[str] = mapped_column(String(16), index=True)
    study_description: Mapped[str] = mapped_column(String(200), default="")
    referring_clinician: Mapped[str] = mapped_column(String(160), default="")

    scheduled_for: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # pending  : menunggu citra masuk
    # matched  : sudah dicocokkan dengan study
    # cancelled: dibatalkan
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # manual | csv | simrs
    source: Mapped[str] = mapped_column(String(16), default="manual")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    studies: Mapped[list[Study]] = relationship(back_populates="order")


class Study(Base):
    """Satu pemeriksaan yang citranya sudah masuk ke arsip."""

    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_instance_uid: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )

    # ID study di Orthanc. Berubah setelah rekonsiliasi, karena menulis ulang
    # identitas menghasilkan study baru di Orthanc.
    orthanc_id: Mapped[str] = mapped_column(String(64), index=True)
    original_orthanc_id: Mapped[str] = mapped_column(String(64))

    # Identitas apa adanya saat citra tiba — diketik manual di konsol alat.
    original_patient_id: Mapped[str] = mapped_column(String(128), default="")
    original_patient_name: Mapped[str] = mapped_column(String(200), default="")

    # Identitas setelah dicocokkan dengan order. Kosong selama belum terverifikasi.
    patient_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accession_number: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    modality: Mapped[str] = mapped_column(String(16), default="", index=True)
    study_date: Mapped[str] = mapped_column(String(16), default="")
    study_time: Mapped[str] = mapped_column(String(16), default="")
    study_description: Mapped[str] = mapped_column(String(200), default="")
    series_count: Mapped[int] = mapped_column(Integer, default=0)
    instance_count: Mapped[int] = mapped_column(Integer, default=0)

    # unverified: di karantina — tidak terlihat di poli, tidak dikirim ke SATUSEHAT
    # verified  : sudah dicocokkan, identitas sudah ditulis ulang
    # rejected  : bukan pemeriksaan sah (uji alat, salah kirim, citra rusak)
    status: Mapped[str] = mapped_column(String(16), default="unverified", index=True)

    # cstore | watcher | upload
    ingest_source: Mapped[str] = mapped_column(String(16), default="cstore")

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    order: Mapped[Order | None] = relationship(back_populates="studies")

    received_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    verified_by: Mapped[User | None] = relationship()
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    """Jejak audit.

    Wajib ada: sistem ini menyimpan rekam medis, sehingga setiap pembukaan data
    pasien dan setiap perubahan identitas harus bisa ditelusuri.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="-")
    role: Mapped[str] = mapped_column(String(32), default="-")
    action: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(32), default="")
    object_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")


class PollerState(Base):
    """Posisi terakhir pembacaan antrean perubahan Orthanc.

    Disimpan agar RIS yang direstart tidak melewatkan study yang masuk saat mati.
    """

    __tablename__ = "poller_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_change_seq: Mapped[int] = mapped_column(Integer, default=0)
