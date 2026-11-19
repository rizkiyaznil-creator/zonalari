"""Skema basis data.

Catatan rancangan: tidak ada DICOM di sini. CTG bukan alat DICOM — keluarannya
PDF rekaman, dan PDF itulah yang disimpan apa adanya. Berkas asli dari alat
tidak pernah diubah; interpretasi disimpan terpisah sebagai data tersendiri.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    BigInteger,
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


# --- Peran -------------------------------------------------------------------
# admin  : kelola pengguna, lihat jejak audit, seluruh akses
# dokter : seluruh data klinis, dan satu-satunya yang boleh mengesahkan hasil
# bidan  : daftar pasien, rekam pemeriksaan, unggah berkas, isi temuan sebagai
#          draf — tetapi tidak mengesahkan
ROLES = ("admin", "dokter", "bidan")

ROLE_LABELS = {
    "admin": "Administrator",
    "dokter": "Dokter",
    "bidan": "Bidan / Perawat",
}

JENIS_PEMERIKSAAN = {
    "ctg_nst": "CTG — NST (antepartum)",
    "ctg_intrapartum": "CTG — intrapartum",
    "usg": "USG",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def boleh_mengesahkan(self) -> bool:
        return self.role in ("dokter", "admin")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mrn: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    birth_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str] = mapped_column(String(40), default="")

    # Riwayat obstetri
    gravida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    para: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abortus: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Hari pertama haid terakhir — dasar perhitungan usia kehamilan.
    hpht: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    examinations: Mapped[list[Examination]] = relationship(
        back_populates="patient", order_by="Examination.performed_at.desc()"
    )

    @property
    def gpa(self) -> str:
        """Ringkasan G/P/A untuk ditampilkan."""
        if self.gravida is None and self.para is None and self.abortus is None:
            return "-"
        bagian = []
        if self.gravida is not None:
            bagian.append(f"G{self.gravida}")
        if self.para is not None:
            bagian.append(f"P{self.para}")
        if self.abortus is not None:
            bagian.append(f"A{self.abortus}")
        return "".join(bagian)

    @property
    def taksiran_persalinan(self) -> dt.date | None:
        """Taksiran persalinan menurut rumus Naegele: HPHT + 280 hari."""
        if self.hpht is None:
            return None
        return self.hpht + dt.timedelta(days=280)

    def usia_kehamilan(self, pada: dt.date) -> tuple[int, int] | None:
        """Usia kehamilan (minggu, hari) pada tanggal tertentu, dihitung dari HPHT."""
        if self.hpht is None:
            return None
        hari = (pada - self.hpht).days
        if hari < 0:
            return None
        return hari // 7, hari % 7


class Examination(Base):
    __tablename__ = "examinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    patient: Mapped[Patient] = relationship(back_populates="examinations")

    kind: Mapped[str] = mapped_column(String(24), index=True)
    performed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # Usia kehamilan saat pemeriksaan. Diisi otomatis dari HPHT bila ada,
    # tetapi tetap bisa ditimpa manual — HPHT sering tidak diketahui pasti,
    # dan usia kehamilan kerap ditetapkan dari USG trimester pertama.
    gestational_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gestational_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    indication: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[User | None] = relationship()

    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="examination", cascade="all, delete-orphan"
    )
    reading: Mapped[CtgReading | None] = relationship(
        back_populates="examination",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def kind_label(self) -> str:
        return JENIS_PEMERIKSAAN.get(self.kind, self.kind)

    @property
    def usia_kehamilan_teks(self) -> str:
        if self.gestational_weeks is None:
            return "-"
        return f"{self.gestational_weeks} mg {self.gestational_days or 0} hr"


class Attachment(Base):
    """Berkas dari alat. Disimpan apa adanya, tidak pernah diubah."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    examination_id: Mapped[int] = mapped_column(
        ForeignKey("examinations.id"), index=True
    )
    examination: Mapped[Examination] = relationship(back_populates="attachments")

    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Sidik jari isi berkas: dipakai mengenali berkas yang sama diunggah dua kali
    # dan memastikan arsip tidak berubah diam-diam.
    sha256: Mapped[str] = mapped_column(String(64), index=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    uploaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    uploaded_by: Mapped[User | None] = relationship()

    @property
    def ukuran_teks(self) -> str:
        ukuran = float(self.size_bytes)
        for satuan in ("B", "KB", "MB", "GB"):
            if ukuran < 1024 or satuan == "GB":
                return f"{ukuran:.0f} {satuan}" if satuan == "B" else f"{ukuran:.1f} {satuan}"
            ukuran /= 1024
        return f"{ukuran:.1f} GB"


# --- Pilihan interpretasi CTG ------------------------------------------------
# Mengikuti istilah yang lazim dipakai (NICHD untuk variabilitas dan deselerasi,
# FIGO untuk kategori). Daftar ini perlu ditinjau dokter sebelum dipakai klinis.
VARIABILITAS = {
    "absent": "Tidak ada (undetectable)",
    "minimal": "Minimal (≤5 dpm)",
    "moderate": "Normal / moderat (6–25 dpm)",
    "marked": "Meningkat (>25 dpm)",
}

AKSELERASI = {
    "ada": "Ada",
    "tidak_ada": "Tidak ada",
}

DESELERASI = {
    "tidak_ada": "Tidak ada",
    "dini": "Dini (early)",
    "variabel": "Variabel",
    "lambat": "Lambat (late)",
    "memanjang": "Memanjang (prolonged)",
}

GERAK_JANIN = {
    "ada": "Ada",
    "tidak_ada": "Tidak ada",
    "tidak_dinilai": "Tidak dinilai",
}

KESIMPULAN_NST = {
    "reaktif": "Reaktif",
    "nonreaktif": "Non-reaktif",
    "meragukan": "Meragukan",
}

KATEGORI_FIGO = {
    "normal": "Normal",
    "mencurigakan": "Mencurigakan (suspicious)",
    "patologis": "Patologis",
}


class CtgReading(Base):
    """Interpretasi CTG.

    Disimpan terpisah dari berkas rekaman: berkas adalah bukti mentah dari alat,
    interpretasi adalah penilaian manusia yang bisa direvisi dan harus jelas
    siapa penanggung jawabnya.
    """

    __tablename__ = "ctg_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    examination_id: Mapped[int] = mapped_column(
        ForeignKey("examinations.id"), unique=True, index=True
    )
    examination: Mapped[Examination] = relationship(back_populates="reading")

    baseline_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variability: Mapped[str | None] = mapped_column(String(16), nullable=True)
    acceleration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    deceleration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contractions_per10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetal_movement: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conclusion: Mapped[str | None] = mapped_column(String(16), nullable=True)
    figo_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    advice: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")

    # draft : masih bisa diubah siapa pun yang berwenang
    # final : sudah disahkan dokter; perubahan setelah ini harus lewat revisi
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_id])

    finalized_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalized_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    finalized_by: Mapped[User | None] = relationship(foreign_keys=[finalized_by_id])

    def label(self, bidang: str) -> str:
        peta = {
            "variability": VARIABILITAS,
            "acceleration": AKSELERASI,
            "deceleration": DESELERASI,
            "fetal_movement": GERAK_JANIN,
            "conclusion": KESIMPULAN_NST,
            "figo_category": KATEGORI_FIGO,
        }[bidang]
        nilai = getattr(self, bidang)
        return peta.get(nilai, "-") if nilai else "-"


class ImportItem(Base):
    """Berkas hasil impor massal dari USB yang belum ditempelkan ke pasien."""

    __tablename__ = "import_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Unik: mencegah berkas yang sama ikut terimpor dua kali saat USB yang sama
    # dicolok ulang.
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Petunjuk identitas yang berhasil dibaca dari isi PDF, bila ada.
    hint_name: Mapped[str] = mapped_column(String(200), default="")
    hint_datetime: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # unmatched : menunggu dicocokkan ke pasien
    # matched   : sudah menjadi lampiran sebuah pemeriksaan
    # rejected  : bukan rekaman pasien (uji alat, berkas rusak)
    status: Mapped[str] = mapped_column(String(12), default="unmatched", index=True)
    rejected_reason: Mapped[str] = mapped_column(Text, default="")

    examination_id: Mapped[int | None] = mapped_column(
        ForeignKey("examinations.id"), nullable=True
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[User | None] = relationship()


class AuditLog(Base):
    """Jejak audit: siapa membuka dan mengubah data pasien."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="-")
    role: Mapped[str] = mapped_column(String(16), default="-")
    action: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(32), default="")
    object_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
