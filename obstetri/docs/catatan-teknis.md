# Catatan teknis

Keputusan yang diambil sadar, beserta alasannya.

## 1. Tidak memakai DICOM sama sekali

CTG bukan alat DICOM. Monitor janin (Philips Avalon, Edan, Bionet) tersambung ke
sistem perinatal milik vendor masing-masing — IntelliSpace Perinatal, FetaLink,
central station — yang mengeluarkan PDF, bukan objek DICOM. Penelusuran
dokumentasi vendor tidak menemukan DICOM conformance statement untuk monitor
janin.

Membungkus PDF CTG menjadi DICOM Encapsulated PDF mungkin dilakukan, tetapi
menambah server DICOM, basis data indeksnya, dan seluruh kerumitannya tanpa
manfaat klinis pada tahap ini. Arsip berkas biasa sudah cukup dan jauh lebih
sedikit bagian yang bisa rusak.

Keputusan ini bisa dibalik belakangan tanpa membongkar apa pun: lampiran sudah
bertipe bebas, jadi jalur DICOM untuk USG bisa ditambahkan di sampingnya.

## 2. pypdfium2, bukan poppler

Pembacaan dan perenderan PDF memakai `pypdfium2`, yang membawa mesin PDFium
sendiri sebagai paket Python. Alternatifnya `poppler-utils` lewat `apt`, tetapi
itu menambah ketergantungan pada paket sistem — dan memang gagal dipasang di
lingkungan pengembangan ini karena repositori Debian tidak terjangkau.

Hasilnya image lebih sederhana dan pemasangan di RS tidak bergantung pada
jaringan apt.

## 3. Berkas disaring dari isinya, bukan namanya

`services/berkas.py` memeriksa angka ajaib di awal berkas (`%PDF-`, `\xff\xd8\xff`,
`\x89PNG`), bukan akhiran namanya. Berkas bernama `rekaman.pdf` yang isinya
program akan ditolak. Nama berkas terlalu mudah dipalsukan untuk dijadikan dasar.

## 4. Duplikat dikenali dari sidik jari isi

Setiap berkas disimpan bersama SHA-256 isinya. Pada antrean impor, sidik jari ini
bersifat unik di basis data, sehingga USB yang sama dicolok ulang tidak
menghasilkan rekaman ganda — dan petugas tidak perlu mengingat berkas mana yang
sudah diimpor.

## 5. Interpretasi terpisah dari berkas

Berkas rekaman adalah bukti mentah dari alat dan tidak pernah diubah.
Interpretasi adalah penilaian manusia yang bisa direvisi dan harus jelas siapa
penanggung jawabnya. Keduanya disimpan sebagai data terpisah, bukan dijadikan
satu dokumen.

## 6. Pengesahan mengunci, pembukaan kembali wajib beralasan

Setelah disahkan, interpretasi terkunci dan lampiran tidak bisa dihapus.
Membukanya kembali adalah tindakan tersendiri yang menuntut alasan dan tercatat
di jejak audit — karena hasil yang sudah disahkan mungkin sudah dipakai
mengambil keputusan klinis.

## 7. Syarat pengesahan berbeda per jenis pemeriksaan

Semula pengesahan selalu menuntut kesimpulan NST. Itu keliru: NST reaktif /
non-reaktif berlaku untuk pemeriksaan antepartum, sedangkan CTG intrapartum
dinilai dengan kategori FIGO, dan USG tidak memakai penilaian CTG sama sekali.
Aturannya sekarang mengikuti jenis pemeriksaan — lihat `_yang_belum_diisi()` di
`routers/examinations.py`.

Daftar istilah variabilitas dan deselerasi mengikuti NICHD, kategori mengikuti
FIGO. **Daftar ini disusun dari rujukan umum dan perlu ditinjau dokter
penanggung jawab sebelum dipakai klinis.**

## 8. Lembar hasil dicetak dari peramban

Lembar hasil adalah halaman HTML dengan aturan `@media print`, bukan PDF yang
dibuat di server. Pilihan ini menghemat satu pustaka berat dan menjaga lembar
hasil tetap persis mengikuti identitas visual RS. Dokter menekan Ctrl+P untuk
mencetak atau menyimpannya sebagai PDF.

Bila kelak lembar hasil perlu ikut diarsipkan sebagai berkas, barulah pembuatan
PDF di server sepadan ditambahkan.

## 9. Build Docker bisa menyesatkan

Kode disalin ke dalam image saat build, jadi `docker compose restart app` **tidak**
memuat perubahan kode — hanya menjalankan ulang image lama. Perbaikan yang tampak
tidak bekerja hampir selalu karena ini.

```bash
DOCKER_BUILDKIT=0 docker compose build app
docker compose up -d --force-recreate app
```

`DOCKER_BUILDKIT=0` dipakai karena batas laju Docker Hub (HTTP 429) membuat
builder baru gagal pada tahap resolusi base image meski image-nya sudah ada di
lokal.

## 10. Folder sertifikat yang boleh kosong

`app/certs/` ada agar jaringan yang memakai proxy pemeriksa TLS bisa menaruh CA
miliknya di situ. Pada pemasangan biasa folder ini kosong dan tidak berpengaruh —
jangan dihapus, karena `Dockerfile` menyalinnya.

## Yang belum dikerjakan

- Integrasi SIMRS (tarik data pasien, kirim hasil balik)
- Pengiriman ke SATUSEHAT
- TLS, backup yang pernah diuji pulih, kebijakan retensi, pemantauan kapasitas
- Jalur DICOM untuk USG — baru masuk akal setelah
  [daftar periksa USG](daftar-periksa-usg.md) terisi
