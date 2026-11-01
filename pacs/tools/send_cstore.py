"""Mengirim berkas DICOM lewat C-STORE, meniru alat radiologi sungguhan.

Dipakai untuk menguji jalur masuk yang sama persis dengan yang dipakai alat
MRI/CT/CR di lapangan — termasuk saat kita mengambil alih IP dan AE Title
tujuan lama tanpa menyentuh konfigurasi alat.

Pemakaian:
    python3 tools/send_cstore.py data/contoh/cr-thorax --host 127.0.0.1 --port 4242
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydicom import dcmread
from pynetdicom import AE
from pynetdicom.sop_class import (
    CTImageStorage,
    ComputedRadiographyImageStorage,
    MRImageStorage,
)

KELAS_SOP = [
    ComputedRadiographyImageStorage,
    CTImageStorage,
    MRImageStorage,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sumber", help="berkas .dcm atau folder berisi berkas .dcm")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4242)
    parser.add_argument(
        "--called-aet",
        default="RSUSUPACS",
        help="AE Title tujuan (Orthanc menerima apa pun karena DicomCheckCalledAet dimatikan)",
    )
    parser.add_argument(
        "--calling-aet",
        default="MODALITAS_UJI",
        help="AE Title pengirim, meniru identitas alat",
    )
    argumen = parser.parse_args()

    sumber = Path(argumen.sumber)
    berkas = (
        sorted(sumber.rglob("*.dcm")) if sumber.is_dir() else [sumber]
    )
    if not berkas:
        print(f"Tidak ada berkas .dcm di {sumber}", file=sys.stderr)
        return 1

    ae = AE(ae_title=argumen.calling_aet)
    for kelas in KELAS_SOP:
        ae.add_requested_context(kelas)

    asosiasi = ae.associate(
        argumen.host, argumen.port, ae_title=argumen.called_aet
    )
    if not asosiasi.is_established:
        print(
            f"Gagal membuka asosiasi DICOM ke {argumen.host}:{argumen.port}",
            file=sys.stderr,
        )
        return 2

    berhasil = 0
    gagal = 0
    try:
        for path in berkas:
            ds = dcmread(path)
            status = asosiasi.send_c_store(ds)
            if status and status.Status == 0x0000:
                berhasil += 1
            else:
                gagal += 1
                print(f"Ditolak: {path.name} (status {status})", file=sys.stderr)
    finally:
        asosiasi.release()

    print(f"Terkirim {berhasil} citra, gagal {gagal}, dari {sumber}")
    return 0 if gagal == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
