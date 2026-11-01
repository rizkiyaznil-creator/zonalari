"""Klien REST untuk Orthanc.

Hanya modul ini yang boleh berbicara langsung dengan Orthanc, agar seluruh
perubahan terhadap arsip DICOM melewati satu pintu yang bisa diaudit.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.orthanc_url, timeout=_TIMEOUT)


class OrthancError(RuntimeError):
    pass


def _raise(response: httpx.Response) -> None:
    raise OrthancError(
        f"Orthanc menolak permintaan ({response.status_code}): {response.text[:400]}"
    )


def is_alive() -> bool:
    try:
        with _client() as c:
            return c.get("/system").status_code == 200
    except httpx.HTTPError:
        return False


def get_changes(since: int, limit: int = 100) -> dict[str, Any]:
    """Membaca antrean perubahan Orthanc sejak nomor urut tertentu."""
    with _client() as c:
        r = c.get("/changes", params={"since": since, "limit": limit})
        if r.status_code != 200:
            _raise(r)
        return r.json()


def get_study(orthanc_id: str) -> dict[str, Any] | None:
    with _client() as c:
        r = c.get(f"/studies/{orthanc_id}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            _raise(r)
        return r.json()


def get_study_statistics(orthanc_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/studies/{orthanc_id}/statistics")
        if r.status_code != 200:
            _raise(r)
        return r.json()


def get_study_modalities(orthanc_id: str) -> list[str]:
    """Mengumpulkan modalitas dari seluruh series dalam satu study."""
    with _client() as c:
        r = c.get(f"/studies/{orthanc_id}/series", params={"expand": ""})
        if r.status_code != 200:
            _raise(r)
        series = r.json()

    modalities: list[str] = []
    for s in series:
        modality = (s.get("MainDicomTags") or {}).get("Modality", "")
        if modality and modality not in modalities:
            modalities.append(modality)
    return modalities


def modify_study(
    orthanc_id: str, replace: dict[str, str]
) -> str:
    """Menulis ulang tag identitas sebuah study, lalu mengembalikan ID barunya.

    UID study, series, dan instance sengaja DIPERTAHANKAN. Yang dikoreksi di sini
    adalah identitas pasien, bukan isi citranya, sehingga pemeriksaan tetap
    merupakan objek yang sama — rujukan dari alat, SIMRS, maupun SATUSEHAT tidak
    ikut berubah. Ini mengikuti pola rekonsiliasi pasien yang lazim di PACS.

    `Force` diperlukan karena Orthanc menganggap penulisan ulang PatientID dan
    mempertahankan SOPInstanceUID sebagai tindakan berisiko — memang benar, dan
    itulah sebabnya setiap pemanggilan fungsi ini selalu disertai baris audit.
    """
    payload = {
        "Replace": replace,
        # HANYA StudyInstanceUID yang dipertahankan.
        #
        # Ini bukan pilihan gaya, melainkan hasil pengujian: bila SeriesInstanceUID
        # dan SOPInstanceUID ikut dipertahankan sementara sumbernya dihapus,
        # Orthanc menjawab HTTP 200 tetapi study LENYAP dari arsip — citra hilang
        # tanpa peringatan. Dengan hanya StudyInstanceUID yang dijaga, instance
        # memperoleh UID baru (sebagaimana mestinya untuk objek yang diubah),
        # pemeriksaannya tetap dapat dirujuk dengan UID yang sama, dan tidak ada
        # data yang hilang maupun seri yang terduplikasi.
        "Keep": ["StudyInstanceUID"],
        "Force": True,
        "KeepSource": False,
        # Orthanc menjalankan modifikasi tingkat study sebagai job asinkron bila
        # tidak diminta sebaliknya. Pemanggil di sini butuh ID baru segera, jadi
        # dipaksa sinkron.
        "Asynchronous": False,
    }
    with _client() as c:
        r = c.post(f"/studies/{orthanc_id}/modify", json=payload)
        if r.status_code not in (200, 201):
            _raise(r)
        return r.json()["ID"]


def find_patient_by_id(patient_id: str) -> dict[str, Any] | None:
    """Mencari rekam pasien di Orthanc berdasarkan PatientID (nomor rekam medis)."""
    if not patient_id:
        return None
    with _client() as c:
        r = c.post(
            "/tools/find",
            json={
                "Level": "Patient",
                "Query": {"PatientID": patient_id},
                "Expand": True,
                "Limit": 2,
            },
        )
        if r.status_code != 200:
            _raise(r)
        hasil = r.json()
    return hasil[0] if hasil else None


def modify_patient(orthanc_id: str, replace: dict[str, str]) -> str:
    """Menyelaraskan demografi sebuah rekam pasien beserta seluruh study-nya.

    Diperlukan ketika nomor rekam medis tujuan sudah ada di arsip dengan nama
    atau tanggal lahir berbeda — misalnya beberapa pemeriksaan pernah masuk
    dengan nama salah ketik. Orthanc menolak memasang study pada pasien yang
    demografinya tidak sama, jadi rekam pasiennya diluruskan lebih dulu.

    Tindakan ini ikut mengubah study lain milik pasien yang sama. Itu memang
    yang dikehendaki — satu nomor rekam medis berarti satu pasien — tetapi
    karena cakupannya luas, pemanggilnya WAJIB menuliskannya ke jejak audit.
    """
    payload = {
        "Replace": replace,
        # HANYA StudyInstanceUID yang dipertahankan.
        #
        # Ini bukan pilihan gaya, melainkan hasil pengujian: bila SeriesInstanceUID
        # dan SOPInstanceUID ikut dipertahankan sementara sumbernya dihapus,
        # Orthanc menjawab HTTP 200 tetapi study LENYAP dari arsip — citra hilang
        # tanpa peringatan. Dengan hanya StudyInstanceUID yang dijaga, instance
        # memperoleh UID baru (sebagaimana mestinya untuk objek yang diubah),
        # pemeriksaannya tetap dapat dirujuk dengan UID yang sama, dan tidak ada
        # data yang hilang maupun seri yang terduplikasi.
        "Keep": ["StudyInstanceUID"],
        "Force": True,
        "KeepSource": False,
        # Sinkron, supaya study lama benar-benar sudah tergantikan sebelum
        # pemanggil melanjutkan — lihat keterangan di modify_study().
        "Asynchronous": False,
    }
    with _client() as c:
        r = c.post(f"/patients/{orthanc_id}/modify", json=payload)
        if r.status_code not in (200, 201):
            _raise(r)
        return r.json()["ID"]


def find_study_id_by_uid(study_instance_uid: str) -> str | None:
    """Mencari ID Orthanc sebuah study dari StudyInstanceUID-nya.

    Dipakai setelah modifikasi, karena Orthanc menerbitkan ID internal baru
    meski StudyInstanceUID sengaja dipertahankan.
    """
    hasil = find_studies({"StudyInstanceUID": study_instance_uid}, limit=1)
    return hasil[0]["ID"] if hasil else None


def delete_study(orthanc_id: str) -> None:
    with _client() as c:
        r = c.delete(f"/studies/{orthanc_id}")
        if r.status_code not in (200, 404):
            _raise(r)


def upload_instance(data: bytes) -> dict[str, Any]:
    """Mengunggah satu berkas DICOM. Orthanc sendiri yang menolak duplikat."""
    with _client() as c:
        r = c.post(
            "/instances",
            content=data,
            headers={"Content-Type": "application/dicom"},
        )
        if r.status_code not in (200, 201):
            _raise(r)
        return r.json()


def find_studies(query: dict[str, str], limit: int = 200) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.post(
            "/tools/find",
            json={
                "Level": "Study",
                "Query": query,
                "Expand": True,
                "Limit": limit,
            },
        )
        if r.status_code != 200:
            _raise(r)
        return r.json()


def server_statistics() -> dict[str, Any]:
    with _client() as c:
        r = c.get("/statistics")
        if r.status_code != 200:
            _raise(r)
        return r.json()
