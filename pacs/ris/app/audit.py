"""Pencatatan jejak audit."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog, User


def record(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    request: Request | None = None,
    object_type: str = "",
    object_id: str | int = "",
    detail: dict | None = None,
    commit: bool = True,
) -> None:
    """Menuliskan satu baris audit.

    Dipanggil untuk setiap peristiwa yang menyentuh data pasien: membuka study,
    mengubah identitas, menolak kiriman, keluar-masuk akun.
    """
    ip = ""
    if request is not None:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() or (
            request.client.host if request.client else ""
        )

    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else "-",
            role=user.role if user else "-",
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            detail=detail,
            ip=ip,
        )
    )
    if commit:
        db.commit()
