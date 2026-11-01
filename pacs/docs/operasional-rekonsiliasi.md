# Alur kerja harian — kotak masuk dan rekonsiliasi

Dokumen ini untuk petugas radiologi yang menjalankan sistem setiap hari.

## Mengapa ada pekerjaan tambahan ini

Alat radiologi di RS ini tidak menerima daftar kerja dari sistem, sehingga
identitas pasien diketik manual di konsol alat. Citra lalu tiba dengan nama
salah ketik, nomor rekam medis kosong atau salah, dan tanpa nomor order.

Selama identitas itu belum dipastikan, citra **tidak dianggap rekam medis**:
tidak muncul di poli dan tidak dikirim ke SATUSEHAT. Mencocokkannya dengan order
adalah pekerjaan yang membuat citra sah.

## Urutan kerja

### 1. Order dibuat lebih dulu

Sebelum pasien difoto, buat order di menu **Order** — atau impor daftar order
harian dari SIMRS lewat CSV. Saat order dibuat, sistem menerbitkan **accession
number**; nomor inilah yang nanti ditulis ke berkas DICOM dan dipakai SATUSEHAT.

Order yang belum ada membuat citranya tidak bisa diverifikasi. Jadi: **order
dulu, baru foto.**

### 2. Pasien difoto seperti biasa

Ketik identitas di konsol alat sebaik mungkin. Yang paling menolong adalah
**nomor rekam medis yang benar** — itu petunjuk terkuat saat pencocokan nanti.

### 3. Cocokkan di kotak masuk

Buka menu **Kotak Masuk**. Tiap baris adalah pemeriksaan yang menunggu.
Klik **Cocokkan**, lalu:

- Periksa identitas apa adanya dari alat di panel kiri.
- Bila ragu, klik **Lihat citra sebelum mencocokkan** — misalnya untuk
  memastikan sisi kanan/kiri atau bagian tubuh yang difoto sesuai order.
- Pilih order yang cocok. Sistem mengurutkan kandidat berdasarkan kesamaan nomor
  rekam medis, nama, modalitas, dan tanggal, lengkap dengan alasannya.

**Angka kecocokan hanya alat bantu urut, bukan keputusan.** Tidak ada
pencocokan otomatis: salah memasang identitas pada rekam medis jauh lebih mahal
daripada beberapa detik kerja manual.

Setelah dicocokkan, sistem menulis ulang nomor rekam medis, nama, tanggal lahir,
jenis kelamin, dan accession number pada berkas DICOM. Nilai asli dari alat tetap
disimpan dan perubahannya tercatat dalam jejak audit atas nama Anda.

### 4. Bila bukan pemeriksaan pasien

Untuk uji kalibrasi alat, salah kirim, atau citra rusak: pakai **Tandai bukan
pemeriksaan** dan tulis alasannya. Berkasnya tidak dihapus, hanya dikeluarkan
dari antrean.

## Hal yang perlu diperhatikan

### Satu nomor rekam medis = satu pasien

Bila nomor rekam medis tujuan sudah ada di arsip dengan nama berbeda — lazimnya
karena pemeriksaan sebelumnya masuk dengan nama salah ketik — sistem akan
meluruskan nama pada rekam pasien itu mengikuti order, **termasuk pemeriksaan
lain milik nomor rekam medis yang sama.**

Itu memang yang dikehendaki. Tetapi artinya: **pastikan nomor rekam medis pada
order benar-benar milik pasien yang difoto.** Nomor rekam medis yang salah tidak
hanya merusak satu pemeriksaan, tetapi ikut mengubah riwayat pasien lain.

Pemeriksaan lain yang ikut diluruskan namanya **tetap belum terverifikasi** dan
masih harus dicocokkan dengan ordernya masing-masing.

### Saat ragu, jangan dicocokkan

Pemeriksaan yang dibiarkan di kotak masuk tidak merusak apa pun — ia hanya
belum terlihat di poli. Pencocokan yang salah merusak rekam medis dua pasien
sekaligus dan sudah terkirim ke sistem lain sebelum ketahuan.

Bila ragu: tinggalkan, tanyakan ke petugas yang memfoto, baru cocokkan.

### Periksa folder karantina

Untuk alat yang memakai folder pantauan, berkas yang gagal masuk tertahan di
`data/quarantine`. Isinya berarti ada citra pasien yang tidak sampai ke arsip.
Periksa setiap hari.

## Siapa boleh apa

| Peran | Kewenangan |
|---|---|
| Administrator | Semua, termasuk kelola pengguna dan baca jejak audit |
| Radiografer | Order, kotak masuk, rekonsiliasi, unggah citra |
| Dokter Radiolog | Baca pemeriksaan terverifikasi, tulis ekspertise (menyusul) |
| Dokter Pengirim | Baca pemeriksaan terverifikasi saja |

Dokter pengirim **tidak** melihat citra yang masih di karantina. Itu disengaja:
citra yang identitasnya belum dipastikan tidak boleh dipakai mengambil keputusan
klinis.

Setiap pembukaan data pasien tercatat dalam jejak audit. Karena itu setiap orang
harus memakai akunnya sendiri.
