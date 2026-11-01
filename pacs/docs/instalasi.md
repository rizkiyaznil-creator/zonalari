# Pemasangan

## Yang dibutuhkan

- Satu server Linux di jaringan RS (lihat catatan spesifikasi di bawah)
- Docker dan Docker Compose
- Alamat IP tetap, dan jalur jaringan dari ruang radiologi ke server

## Langkah

```bash
git clone <repositori> && cd pacs
cp .env.example .env
```

Buka `.env` dan ganti **seluruh** nilainya:

```bash
openssl rand -hex 16   # POSTGRES_PASSWORD
openssl rand -hex 32   # SESSION_SECRET
openssl rand -hex 32   # INGEST_TOKEN
```

`ADMIN_PASSWORD` diisi kata sandi admin pertama. Akun ini dibuat otomatis saat
aplikasi pertama kali jalan, dan hanya saat basis data masih kosong.

```bash
docker compose up -d
docker compose ps          # semua layanan harus "Up"
curl http://localhost:8080/sehat
```

Jawaban yang diharapkan: `{"ris":"ok","orthanc":"ok"}`.

Buka `http://<alamat-server>:8080`, masuk sebagai admin, lalu segera buat akun
untuk tiap petugas lewat menu **Pengguna**. Jangan dipakai bersama-sama satu akun:
jejak audit menjadi tidak berguna bila semua tindakan tercatat atas nama "admin".

## Menyambungkan alat radiologi

### Jalur 1 — ambil alih IP dan AE Title tujuan lama (paling rapi)

Periksa pada tiap alat apakah sudah ada tujuan DICOM yang pernah dikonfigurasi:
workstation lama, PACS lama, atau printer film. Bila ada, catat **IP, port, dan
AE Title**-nya, pastikan perangkat lama itu sudah tidak dipakai, lalu berikan
alamat IP tersebut kepada server ini dan samakan `DICOM_PORT` di `.env`.

Alat tidak perlu diubah sama sekali. Orthanc sudah dikonfigurasi menerima
kiriman apa pun AE Title-nya (`DicomCheckCalledAet: false`), sehingga alat
tidak menyadari tujuannya berganti.

Uji dari sisi alat dengan fitur "DICOM Echo"/"Verify" bila tersedia.

### Jalur 2 — folder pantauan

Untuk alat yang menyimpan hasil ke folder. Bagikan folder itu lewat jaringan,
pasang (mount) di server, lalu arahkan ke `data/watch`:

```yaml
# docker-compose.yml, bagian watcher
volumes:
  - /mnt/cr-ruang-1:/data/watch
```

Watcher menunggu berkas berhenti bertambah selama beberapa detik sebelum
mengirim, agar berkas yang masih disalin tidak terkirim separuh. Berkas yang
berhasil dipindahkan ke `data/processed`, yang gagal ke `data/quarantine`.
**Periksa `data/quarantine` secara berkala** — isinya berarti ada citra yang
tidak masuk arsip.

### Jalur 3 dan 4 — unggah manual dan CD pasien

Lewat menu **Unggah** di aplikasi. Untuk CD rujukan, pilih seluruh isi folder
`DICOM` pada CD; berkas non-DICOM dilewati otomatis.

## Untuk produksi

Yang berikut **belum** disiapkan dan harus diselesaikan sebelum menyentuh data
pasien sungguhan:

1. **TLS.** Ganti `:8080` di `caddy/Caddyfile` dengan nama domain RS dan hapus
   `auto_https off`. Caddy akan menerbitkan sertifikat sendiri. Setelah itu ubah
   `https_only=True` pada `SessionMiddleware` di `ris/app/main.py`.
2. **Backup yang pernah diuji pulih.** Dua hal harus ikut: basis data PostgreSQL
   (`pg_dump`) dan direktori berkas DICOM (volume `orthanc-storage`). Backup yang
   belum pernah diuji pulih sama saja dengan tidak punya backup.
3. **Kebijakan retensi** sesuai ketentuan rekam medis, beserta pemantauan sisa
   ruang disk.
4. **Pemantauan.** Minimal: `/sehat` dipantau, dan ada yang memeriksa
   `data/quarantine` tiap hari.
5. **Proxy TLS RS.** Bila jaringan RS memakai proxy yang memeriksa TLS, letakkan
   berkas `.crt` milik proxy di `ris/certs/` dan `watcher/certs/` sebelum build.

## Spesifikasi server

Spesifikasi tepatnya bergantung pada jumlah pemeriksaan per hari dan lama
penyimpanan, jadi angkanya harus dihitung dari data RS sendiri. Yang **tidak**
boleh ditawar untuk mesin penyimpan rekam medis:

- **RAID** pada penyimpanan citra. Satu disk mati tanpa RAID berarti arsip
  hilang. Ini syarat mutlak, bukan tambahan.
- **Memori ECC** dan catu daya redundan pada mesin yang menyala terus.
- **UPS**, agar mati listrik tidak merusak basis data.
- Garansi dengan layanan di tempat, karena mesin ini tidak boleh lama mati.

Ukuran kasar per pemeriksaan sebagai titik awal perhitungan: CR/DX puluhan MB,
CT dan MR ratusan MB. Kalikan dengan jumlah pemeriksaan per hari dan jumlah hari
penyimpanan yang diwajibkan, lalu tambahkan ruang untuk backup.
