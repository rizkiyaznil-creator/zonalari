# PACS + RIS RS USU

Sistem arsip dan tampilan citra radiologi untuk RS Universitas Sumatera Utara:
citra dari alat MRI, CT, dan CR masuk ke satu arsip, lalu bisa dibuka dari
komputer mana pun di jaringan RS lewat browser — tanpa pemasangan apa pun di
komputer poli.

Dibangun dengan syarat: **konfigurasi alat radiologi tidak boleh disentuh.**

## Mengapa ada langkah verifikasi

Karena alat tidak boleh dikonfigurasi, alat tidak bisa diarahkan ke server
daftar kerja (Modality Worklist). Akibatnya petugas mengetik identitas pasien
langsung di konsol alat, dan citra tiba dengan nama salah ketik, nomor rekam
medis kosong, serta **tanpa accession number**.

Padahal SATUSEHAT mensyaratkan accession number yang terbit dari SIMRS/RIS sejak
order dibuat. Celah itulah yang ditutup sistem ini:

```
Order (accession number terbit)
        │
        │   citra difoto — identitas diketik manual di alat
        ▼
KOTAK MASUK (karantina — belum jadi rekam medis, tidak tampil di poli)
        │   petugas mencocokkan citra ↔ order
        ▼
Identitas ditulis ulang ke berkas DICOM (nomor RM, nama, accession number)
        ▼
ARSIP TERVERIFIKASI ──► viewer di poli · ekspertise · SATUSEHAT
```

Aturan yang dipegang sistem: **hanya pemeriksaan terverifikasi yang terlihat di
poli dan boleh dikirim ke SATUSEHAT.**

## Susunan layanan

| Layanan | Peran |
|---|---|
| `orthanc` | Arsip DICOM. Menerima kiriman alat lewat C-STORE, menyediakan DICOMweb dan viewer OHIF |
| `ris` | Aplikasi web: login & hak akses, order, kotak masuk, rekonsiliasi, daftar pasien, jejak audit |
| `watcher` | Memantau folder hasil alat yang tidak mengirim lewat C-STORE |
| `postgres` | Basis data indeks Orthanc dan basis data RIS (terpisah) |
| `caddy` | Satu-satunya pintu dari jaringan RS; memeriksa sesi login sebelum citra boleh diambil |

Orthanc dan PostgreSQL **tidak pernah** diekspos langsung ke jaringan RS.

## Empat jalur citra masuk, tanpa menyentuh alat

1. **Ambil alih IP dan AE Title tujuan lama** — bila alat sudah pernah diarahkan
   ke suatu tujuan (workstation lama, PACS lama, printer film), pasang server ini
   pada alamat yang sama. Alat tidak diubah sama sekali. Jalur paling rapi.
2. **Folder pantauan** — untuk alat yang menyimpan hasil ke folder; folder itu
   dibagikan lewat jaringan dan dipetakan ke `data/watch`.
3. **Unggah manual** — berkas DICOM lepas, lewat halaman Unggah.
4. **CD pasien rujukan** — pilih seluruh isi folder `DICOM` pada CD; berkas
   non-DICOM otomatis dilewati.

Semua jalur bermuara ke kotak masuk yang sama dan tetap wajib diverifikasi.

## Menjalankan

```bash
cp .env.example .env     # lalu ganti SEMUA nilainya
docker compose up -d
```

Buka `http://<alamat-server>:8080` dan masuk dengan akun admin dari `.env`.

Petunjuk lengkap: [docs/instalasi.md](docs/instalasi.md)

## Dokumen lain

- [docs/operasional-rekonsiliasi.md](docs/operasional-rekonsiliasi.md) — cara
  kerja harian petugas radiologi, dan apa yang harus dilakukan saat ragu
- [docs/biaya-vs-penawaran-vendor.md](docs/biaya-vs-penawaran-vendor.md) —
  perbandingan terhadap penawaran vendor
- [docs/catatan-teknis.md](docs/catatan-teknis.md) — keputusan teknis yang
  mahal dipelajari ulang, termasuk satu kombinasi parameter Orthanc yang
  menghapus citra tanpa peringatan

## Menguji

```bash
# Membuat citra DICOM sintetis dengan identitas sengaja berantakan
python3 tools/make_sample_dicom.py --keluaran data/contoh

# Mengirimkannya seperti alat radiologi sungguhan
python3 tools/send_cstore.py data/contoh/cr-thorax --host 127.0.0.1 --port 4242

# Uji logika pencocokan
docker compose run --rm -v ./ris/tests:/app/tests ris python -m unittest discover -s tests
```

Perkakas di `tools/` membutuhkan `pydicom` dan `pynetdicom`:
`pip install pydicom pynetdicom`.

## Status

Tahap 1 selesai dan berjalan: arsip, empat jalur masuk, login dan hak akses,
kotak masuk dan rekonsiliasi, daftar pasien, viewer, jejak audit.

Belum ada: modul ekspertise, penyambungan SIMRS langsung, pengiriman ke
SATUSEHAT, serta pengerasan produksi (TLS, backup teruji, retensi, pemantauan).
**Jangan dipakai untuk pasien sungguhan sebelum bagian itu selesai.**

## Lisensi komponen

Orthanc berlisensi GPLv3 dan sebagian plugin-nya AGPL. Aman untuk pemakaian
internal RS. Perlu ditinjau ulang bila kelak sistem ini dikomersialkan.
