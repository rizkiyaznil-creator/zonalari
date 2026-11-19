# Daftar periksa mesin USG

Dipakai sebelum memutuskan bagaimana citra USG masuk ke arsip. Isi satu lembar
untuk tiap mesin. Pemeriksaannya cukup dilakukan operator — tidak perlu
mendatangkan vendor.

## Identitas mesin

| Hal | Isian |
|---|---|
| Merek dan tipe | |
| Nomor seri | |
| Tahun pengadaan | |
| Versi perangkat lunak | |
| Lokasi (poli / VK / OK) | |

Versi perangkat lunak biasanya ada di menu `Setup` → `System Information`,
`About`, atau `Service` → `Version`.

## 1. Apakah ada menu DICOM?

Telusuri menu berikut — penamaannya berbeda antar merek:

| Merek | Jalur menu yang biasa |
|---|---|
| GE (Voluson, Logiq) | `Utility` → `Connectivity` → `Dataflow` / `Device` |
| Samsung Medison | `Setup` → `DICOM` |
| Mindray | `Setup` → `Network Preset` → `DICOM` |
| Philips (Affiniti, ClearVue) | `Setup` → `Connectivity` → `DICOM Settings` |
| Siemens (Acuson) | `System` → `Configuration` → `Connectivity` |
| Chison / SonoScape | `Setup` → `DICOM` atau `Network` |

Yang dicari di dalamnya: **AE Title**, **Remote IP / Host**, **Port**, dan tombol
**Verify / Ping / Echo**.

- [ ] Menu DICOM ada dan bisa dibuka
- [ ] Menu DICOM ada tetapi **abu-abu / terkunci** → lisensi belum dibeli
- [ ] Tidak ada menu DICOM sama sekali

## 2. Apakah lisensi DICOM aktif?

Cari daftar opsi terpasang: `Setup` → `Option` / `License` / `Feature`.
Catat apakah ada baris bertuliskan **DICOM**, **DICOM Storage**, atau
**DICOM Connectivity**, dan statusnya.

| Hal | Isian |
|---|---|
| Daftar opsi memuat DICOM? | ya / tidak |
| Status | aktif / percobaan / terkunci |

Kalau terkunci, **tanyakan harganya ke vendor sebelum mencari jalan lain.**
Lisensi DICOM kerap lebih murah daripada ongkos kerja manual bertahun-tahun —
dan jalur DICOM jauh lebih rapi daripada memindahkan berkas lewat USB.

## 3. Apa saja format ekspor ke USB?

Colok USB, lakukan satu pemeriksaan percobaan, lalu coba simpan. Catat pilihan
format yang muncul:

- [ ] DICOM (`.dcm`) — **paling baik**, metadata pasien ikut terbawa
- [ ] JPEG / BMP / PNG — gambar saja, tanpa metadata
- [ ] AVI / MP4 — untuk rekaman gerak
- [ ] PDF laporan

Banyak mesin bisa mengekspor **DICOM ke USB walau lisensi DICOM jaringan tidak
aktif.** Ini sering terlewat, jadi periksa betul daftar formatnya.

| Hal | Isian |
|---|---|
| Format yang tersedia | |
| Nama berkas yang dihasilkan (contoh) | |
| Identitas pasien ikut tercetak pada gambar? | ya / tidak |

## 4. Apakah ada jalur jaringan?

| Hal | Isian |
|---|---|
| Ada port LAN (RJ45)? | ya / tidak |
| Sudah tersambung ke jaringan RS? | ya / tidak |
| Alamat IP sekarang (bila ada) | |
| Bisa kirim ke folder jaringan (SMB/FTP)? | ya / tidak |

## 5. Apakah sudah ada tujuan pengiriman lama?

Bila mesin pernah dikonfigurasi mengirim ke suatu tujuan — workstation lama,
PACS lama, atau printer — **catat IP, port, dan AE Title-nya.** Bila perangkat
lama itu sudah tidak dipakai, server arsip bisa mengambil alih alamat yang sama,
sehingga mesin tidak perlu diubah sama sekali.

| Hal | Isian |
|---|---|
| Ada tujuan DICOM tersimpan? | ya / tidak |
| AE Title tujuan | |
| IP dan port tujuan | |
| Perangkat tujuan masih dipakai? | ya / tidak |

## 6. Minta DICOM Conformance Statement

Minta ke vendor, sebutkan merek dan tipe persis. Dokumen ini menyatakan hitam di
atas putih apa yang bisa dan tidak bisa dilakukan mesin. Kalau vendor tidak bisa
menyediakannya, itu sendiri sudah jawaban.

---

## Kesimpulan jalur masuk

Setelah daftar di atas terisi:

| Temuan | Jalur yang dipakai |
|---|---|
| DICOM aktif, ada jaringan | Kirim langsung ke server (perlu pengembangan tambahan) |
| DICOM terkunci, harga wajar | Beli lisensi, lalu seperti di atas |
| Ekspor DICOM ke USB | Impor lewat halaman Impor, seperti CTG |
| Hanya JPEG/PNG ke USB | Impor lewat halaman Impor — **sudah didukung sekarang** |
| Tidak ada ekspor sama sekali | Foto layar sebagai jalan terakhir; mutunya menurun |

Tiga baris terakhir bisa langsung dipakai dengan sistem ini hari ini. Dua baris
pertama memerlukan penambahan jalur DICOM, yang baru masuk akal dikerjakan
setelah daftar periksa ini terisi.
