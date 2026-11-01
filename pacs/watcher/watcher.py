"""Pemantau folder hasil alat radiologi.

Dipakai untuk alat yang tidak bisa (atau tidak boleh) dikonfigurasi mengirim
lewat DICOM C-STORE, tetapi menyimpan hasilnya ke sebuah folder — folder itu
dibagikan lewat jaringan lalu dipetakan ke WATCH_DIR.

Berkas sengaja dititipkan lewat RIS, bukan langsung ke Orthanc, supaya sumber
masuknya tercatat dan study langsung terdaftar di kotak masuk.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s watcher: %(message)s",
)
log = logging.getLogger("watcher")

RIS_URL = os.environ.get("RIS_URL", "http://ris:8000").rstrip("/")
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")
WATCH_DIR = Path(os.environ.get("WATCH_DIR", "/data/watch"))
PROCESSED_DIR = Path(os.environ.get("PROCESSED_DIR", "/data/processed"))
QUARANTINE_DIR = Path(os.environ.get("QUARANTINE_DIR", "/data/quarantine"))
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "5"))

# Berkas dianggap selesai ditulis jika ukurannya tidak berubah selama sekian
# detik. Tanpa jeda ini, berkas yang masih disalin alat akan terkirim separuh.
STABLE_SECONDS = float(os.environ.get("STABLE_SECONDS", "3"))

ABAIKAN = {"DICOMDIR", "AUTORUN.INF", ".DS_STORE", "THUMBS.DB"}


def berkas_dicom(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(132)[128:132] == b"DICM"
    except OSError:
        return False


def sudah_stabil(path: Path, terlihat: dict[Path, tuple[int, float]]) -> bool:
    try:
        ukuran = path.stat().st_size
    except OSError:
        return False

    sebelumnya = terlihat.get(path)
    sekarang = time.monotonic()
    if sebelumnya is None or sebelumnya[0] != ukuran:
        terlihat[path] = (ukuran, sekarang)
        return False
    return (sekarang - sebelumnya[1]) >= STABLE_SECONDS


def pindahkan(path: Path, tujuan_dasar: Path) -> None:
    relatif = path.relative_to(WATCH_DIR)
    tujuan = tujuan_dasar / relatif
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    if tujuan.exists():
        tujuan = tujuan.with_name(f"{tujuan.stem}-{int(time.time())}{tujuan.suffix}")
    shutil.move(str(path), str(tujuan))


def titipkan(path: Path, klien: httpx.Client) -> None:
    with path.open("rb") as f:
        respons = klien.post(
            "/internal/ingest",
            headers={"X-Ingest-Token": INGEST_TOKEN},
            files={"berkas": (path.name, f, "application/dicom")},
            data={"sumber": "watcher"},
        )
    if respons.status_code == 200:
        pindahkan(path, PROCESSED_DIR)
        log.info("Terkirim: %s", path.name)
    else:
        log.error(
            "Ditolak RIS (%s): %s — %s",
            respons.status_code,
            path.name,
            respons.text[:200],
        )
        pindahkan(path, QUARANTINE_DIR)


def satu_putaran(terlihat: dict[Path, tuple[int, float]], klien: httpx.Client) -> None:
    for path in sorted(WATCH_DIR.rglob("*")):
        if not path.is_file() or path.name.upper() in ABAIKAN:
            continue
        if not sudah_stabil(path, terlihat):
            continue

        if not berkas_dicom(path):
            log.warning("Bukan berkas DICOM, dikarantina: %s", path.name)
            pindahkan(path, QUARANTINE_DIR)
            terlihat.pop(path, None)
            continue

        try:
            titipkan(path, klien)
        except httpx.HTTPError as exc:
            # Berkas sengaja DIBIARKAN di tempat agar dicoba lagi putaran
            # berikutnya — jangan sampai citra pasien hilang karena RIS
            # kebetulan sedang restart.
            log.error("Gagal menghubungi RIS untuk %s: %s", path.name, exc)
        finally:
            terlihat.pop(path, None)


def main() -> None:
    if not INGEST_TOKEN:
        raise SystemExit("INGEST_TOKEN belum diisi.")

    for folder in (WATCH_DIR, PROCESSED_DIR, QUARANTINE_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    log.info("Memantau %s (jeda %.1f detik)", WATCH_DIR, POLL_SECONDS)
    terlihat: dict[Path, tuple[int, float]] = {}

    with httpx.Client(base_url=RIS_URL, timeout=httpx.Timeout(60.0)) as klien:
        while True:
            try:
                satu_putaran(terlihat, klien)
            except Exception:  # noqa: BLE001 - pemantau tidak boleh mati
                log.exception("Galat tak terduga saat memindai folder")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
