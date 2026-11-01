# Perbandingan biaya terhadap penawaran vendor

Pembanding: **Surat Penawaran CV Binary Art (periksa.id)**, No. 426.8/BD/SRT/10-2026,
tertanggal 22 Oktober 2026, kepada Direktur RS Universitas Sumatera Utara.
Masa berlaku penawaran 14 hari kalender.

Seluruh angka penawaran di bawah dikutip apa adanya dari surat tersebut dan
aritmetikanya sudah diperiksa ulang — semuanya benar.

## Isi penawaran

**I. Server PACS, beli putus**

| Komponen | Jumlah |
|---|---|
| Server + monitor + UPS 1200VA | Rp 90.062.500 |
| Setup & konfigurasi | Rp 7.000.000 |
| Maintenance, 6 bulan @ Rp 1.000.000 | Rp 6.000.000 |
| Subtotal | Rp 103.062.500 |
| PPN 11% | Rp 11.336.875 |
| **Total di muka** | **Rp 114.399.375** |

Belum termasuk akomodasi dan transportasi untuk konfigurasi di lokasi RS, serta
biaya pengiriman perangkat.

**II. Layanan software PACS & RIS, berlangganan**

| Komponen | Jumlah |
|---|---|
| Terkoneksi 4 alat | Rp 7.000.000 / bulan |
| Penambahan koneksi per alat | Rp 2.500.000 / bulan |
| Integrasi sekali bayar, bila SIMRS bukan Periksa.id | Rp 3.500.000 |

## Biaya 5 tahun

Asumsi yang dipakai ditulis terbuka: maintenance berlanjut Rp 1.000.000/bulan
setelah 6 bulan yang tercakup (penawaran tidak menyebut tarif setelahnya), dan
SIMRS RS USU bukan Periksa.id sehingga biaya integrasi berlaku.

| | 4 alat | 6 alat |
|---|---|---|
| Biaya di muka | Rp 114.399.375 | Rp 114.399.375 |
| Lisensi software 60 bulan | Rp 420.000.000 | Rp 720.000.000 |
| Maintenance bulan 7–60 *(asumsi)* | Rp 54.000.000 | Rp 54.000.000 |
| Integrasi SIMRS | Rp 3.500.000 | Rp 3.500.000 |
| **Perkiraan total 5 tahun** | **± Rp 591.900.000** | **± Rp 891.900.000** |

PPN atas biaya bulanan tidak disebutkan dalam penawaran. Bila dikenakan 11%,
tambahkan sekitar Rp 46 juta (4 alat) atau Rp 79 juta (6 alat).

**Bacaan pentingnya:** biaya sesungguhnya bukan Rp 114 juta, melainkan langganan
bulanan yang berjalan selamanya. Lisensi software saja sudah tiga sampai enam
kali lipat biaya di muka.

## Perbedaan yang menentukan

| | Penawaran vendor | Sistem ini |
|---|---|---|
| Lisensi software | Rp 7 juta/bulan, selamanya | Rp 0 (Orthanc + OHIF, sumber terbuka) |
| Menambah alat | Rp 2,5 juta/bulan per alat | Rp 0 |
| Bila berhenti berlangganan | Layanan berhenti | Sistem tetap jalan |
| Kepemilikan & lokasi data | Tidak disebut dalam penawaran | Di server RS, format DICOM standar |
| Pindah sistem di kemudian hari | Tidak disebut | Arsip DICOM standar, bisa dipindahkan |
| Dukungan & SLA | Ada vendor | **Tidak ada** — bergantung tim IT RS |
| Tanggung jawab bila rusak | Ada pihak yang dituntut | Ada pada RS sendiri |

Dua baris terakhir adalah harga sesungguhnya dari membangun sendiri, dan tidak
boleh diremehkan. Menghemat Rp 400 juta tidak berarti apa-apa bila tidak ada
orang di RS yang sanggup memulihkan arsip saat server bermasalah pada hari Minggu.

## Catatan atas spesifikasi server yang ditawarkan

Tiga hal perlu ditanyakan kembali sebelum penawaran diterima:

1. **Yang ditawarkan adalah PC desktop, bukan server.** Intel Core Ultra 7 265
   adalah prosesor desktop konsumen, sistem operasinya Windows 11 Pro (bukan
   Windows Server), dan ada kartu WiFi 7 di dalamnya. Tidak disebutkan RAID,
   memori ECC, catu daya redundan, maupun disk yang bisa diganti saat menyala.
2. **Tidak ada RAID pada mesin penyimpan rekam medis.** Satu disk rusak berarti
   arsip citra hilang. Untuk data yang wajib disimpan bertahun-tahun, ini risiko
   yang tidak sepadan.
3. **Storage 1 TB SSD + 2 TB HDD kemungkinan besar terlalu kecil.** CT dan MR
   memakan ratusan MB per pemeriksaan. Penawaran tidak menyebut biaya perluasan
   storage, backup, maupun kebijakan retensi.

## Pertanyaan yang sebaiknya diajukan ke vendor

Pertanyaan ini berguna baik bila penawaran diterima maupun ditolak:

1. Siapa pemilik data citra, dan di mana data disimpan?
2. Bila kerja sama berakhir, bagaimana seluruh arsip diserahkan ke RS, dalam
   format apa, berapa lama, dan berapa biayanya?
3. Apakah angka Rp 7 juta/bulan dapat dikunci untuk jangka tertentu, atau bisa
   naik sewaktu-waktu?
4. Apakah pengiriman ke SATUSEHAT (DICOM Router dan NIDR) sudah termasuk, atau
   terpisah?
5. Berapa tarif maintenance setelah bulan keenam?
6. Apakah ada jaminan waktu tanggap bila sistem mati pada jam pelayanan?
7. Apakah penyambungan 4 alat memerlukan perubahan konfigurasi pada alat — yang
   berarti perlu mendatangkan vendor masing-masing alat beserta biayanya?
8. Berapa biaya menambah kapasitas storage, dan siapa yang menanggung backup?

Pertanyaan nomor 7 patut diperhatikan: bila vendor memasang PACS dengan cara
biasa, alat harus diarahkan ke server baru, dan itu umumnya memerlukan teknisi
vendor alat — biaya yang tidak muncul di penawaran mana pun.

## Yang jujur harus dikatakan

Sistem ini **belum** menyamai yang ditawarkan vendor. Yang sudah jalan: arsip,
empat jalur citra masuk, hak akses, rekonsiliasi identitas, daftar pasien,
viewer, dan jejak audit. Yang belum: modul ekspertise, penyambungan SIMRS
langsung, pengiriman ke SATUSEHAT, serta pengerasan produksi.

Perbandingan biaya di atas membandingkan **struktur biaya**, bukan kesiapan hari
ini. Keputusan yang masuk akal adalah menilai berapa lama dan berapa besar usaha
untuk menyelesaikan sisanya, lalu menimbangnya terhadap Rp 420 juta lisensi
selama lima tahun — dan terhadap kenyataan bahwa tanggung jawab teknisnya
berpindah ke RS.
