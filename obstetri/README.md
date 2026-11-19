# Arsip Pemeriksaan Obstetri — CTG & USG

Arsip elektronik hasil pemeriksaan kebidanan: rekaman CTG dan citra USG tersimpan
per pasien, bisa dibuka lagi saat kontrol berikutnya, dan dicetak sebagai lembar
hasil berkop RS.

Dibangun untuk kondisi nyata di lapangan: **alat tidak perlu disentuh vendor.**
Rekaman diambil dari USB alat, lalu dicocokkan ke pasien di sini.

## Mengapa bukan PACS/DICOM

CTG bukan alat DICOM. Monitor janin tersambung ke sistem perinatal milik vendor
masing-masing dan mengeluarkan PDF, bukan objek DICOM. Memaksa rekaman CTG masuk
arsip DICOM hanya menambah bagian yang bisa rusak tanpa manfaat klinis.

Karena itu sistem ini mengarsipkan berkas apa adanya — PDF rekaman dari alat
tidak pernah diubah — dan menyimpan interpretasi sebagai data tersendiri.

Bila kelak USG di RS ternyata mendukung DICOM, jalur DICOM bisa ditambahkan
tanpa membongkar apa pun di sini. Lihat
[docs/daftar-periksa-usg.md](docs/daftar-periksa-usg.md) untuk cara memastikannya.

## Alur kerja

```
Pasien didaftarkan (HPHT → usia kehamilan & taksiran persalinan otomatis)
        │
        │   pemeriksaan dilakukan; identitas diketik di alat seadanya
        ▼
Rekaman disimpan ke USB alat
        │
        ▼
Impor massal dari USB  ──►  antrean pencocokan
        │   petugas mencocokkan tiap rekaman ke pasien
        ▼
Pemeriksaan tercatat + rekaman terlampir
        │
        ▼
Interpretasi (draf)  ──►  disahkan dokter  ──►  lembar hasil berkop RS
```

Dua hal yang dijaga sistem:

- **Berkas yang sama tidak masuk dua kali.** Dikenali dari isinya, bukan namanya,
  jadi USB yang sama aman dicolok ulang.
- **Hasil yang sudah disahkan terkunci.** Interpretasi tidak bisa diubah dan
  lampiran tidak bisa dihapus; membuka kembali adalah tindakan tersendiri yang
  wajib disertai alasan dan tercatat di jejak audit.

## Peran

| Peran | Kewenangan |
|---|---|
| Administrator | Semua, termasuk kelola pengguna dan baca jejak audit |
| Dokter | Seluruh data klinis, dan satu-satunya yang boleh **mengesahkan** hasil |
| Bidan / Perawat | Daftarkan pasien, rekam pemeriksaan, impor dan cocokkan rekaman, isi interpretasi sebagai draf |

Setiap pembukaan data pasien tercatat, jadi setiap orang memakai akunnya sendiri.

## Interpretasi

Syarat pengesahan berbeda menurut jenis pemeriksaan:

| Jenis | Yang wajib terisi |
|---|---|
| CTG — NST (antepartum) | Kesimpulan NST (reaktif / non-reaktif / meragukan) |
| CTG — intrapartum | Kategori FIGO (normal / mencurigakan / patologis) |
| USG | Temuan tertulis — kolom penilaian CTG tidak ditampilkan |

Istilah variabilitas dan deselerasi mengikuti NICHD, kategori mengikuti FIGO.
**Daftar pilihan ini perlu ditinjau dokter penanggung jawab sebelum dipakai
klinis** — saya menyusunnya dari rujukan umum, bukan dari protokol RS.

## Menjalankan

```bash
cp .env.example .env     # lalu ganti SEMUA nilainya
docker compose up -d
```

Buka `http://<alamat-server>:8090` dan masuk dengan akun admin dari `.env`.

## Menguji

```bash
# Membuat rekaman CTG tiruan — tanpa pustaka tambahan
python3 tools/buat_contoh_ctg.py --keluaran contoh

# Uji logika usia kehamilan, pencocokan nama, dan penyaringan berkas
docker compose run --rm -v ./tests:/app/tests app python -m unittest discover -s tests
```

Berkas contoh sengaja dibuat dengan identitas tidak rapi — "NY SITI AMINAH",
`dewi^lestari`, nomor rekam medis kosong — karena begitulah rekaman tiba dari alat.

## Dokumen lain

- [docs/daftar-periksa-usg.md](docs/daftar-periksa-usg.md) — cara memastikan
  kemampuan mesin USG sebelum memutuskan jalur masuknya
- [docs/operasional.md](docs/operasional.md) — alur kerja harian petugas
- [docs/catatan-teknis.md](docs/catatan-teknis.md) — keputusan teknis dan jebakannya

## Status

Berjalan dan sudah diuji ujung ke ujung dengan rekaman tiruan: pendaftaran pasien,
impor massal dari USB, pencocokan, interpretasi, pengesahan, dan cetak lembar hasil.

Belum ada: integrasi SIMRS, pengiriman ke SATUSEHAT, dan pengerasan produksi
(TLS, backup teruji, retensi). **Belum boleh dipakai sebagai satu-satunya catatan
untuk pasien sungguhan sebelum bagian itu selesai.**
