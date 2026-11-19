# Alur kerja harian

Untuk bidan, perawat, dan dokter yang memakai sistem ini setiap hari.

## Sekali di awal: daftarkan pasien

Menu **Pasien** → isi nomor rekam medis, nama, dan **HPHT**.

HPHT membuat usia kehamilan dan taksiran persalinan terhitung sendiri di setiap
pemeriksaan, sehingga tidak perlu dihitung ulang manual. Bila HPHT tidak
diketahui pasti — sering terjadi — kosongkan saja, lalu isi usia kehamilan
manual pada tiap pemeriksaan. Isian manual selalu menang atas hitungan HPHT.

## Setiap hari: impor rekaman dari USB

1. Colok USB alat CTG ke komputer.
2. Menu **Impor dari USB** → pilih semua berkas rekaman sekaligus → Unggah.
3. Berkas yang sudah pernah diimpor otomatis dilewati, jadi USB yang sama aman
   dicolok berulang kali. Tidak perlu menghapus isi USB.

## Cocokkan rekaman ke pasien

Tiap rekaman di antrean dibuka satu per satu:

- Sistem membaca nama yang tercetak pada rekaman dan mengurutkan pasien yang
  mirip. **Angka kecocokan hanya alat bantu urut, bukan keputusan.**
- Buka rekamannya bila perlu dipastikan.
- Pilih pasien, jenis pemeriksaan, dan waktu pemeriksaan.

Nama pada rekaman berasal dari ketikan operator di alat, jadi sering tidak sama
persis dengan data pasien. **Kalau ragu, jangan dicocokkan.** Rekaman yang
dibiarkan di antrean tidak merusak apa pun; salah pasang merusak catatan dua
pasien sekaligus.

Untuk rekaman uji alat atau berkas rusak: **Tandai bukan rekaman pasien** dan
tulis alasannya. Berkasnya tidak dihapus, hanya dikeluarkan dari antrean.

## Isi interpretasi

Di halaman pemeriksaan. Bidan dan perawat boleh mengisi — hasilnya tersimpan
sebagai **draf**.

Yang wajib terisi berbeda menurut jenis pemeriksaan:

- **CTG NST (antepartum)** → kesimpulan NST
- **CTG intrapartum** → kategori FIGO
- **USG** → temuan tertulis (kolom CTG tidak ditampilkan)

## Pengesahan oleh dokter

Hanya dokter yang bisa menekan **Sahkan hasil**. Setelah disahkan:

- Interpretasi terkunci dan tidak bisa diubah
- Lampiran tidak bisa dihapus
- Nama dan waktu pengesahan tercetak pada lembar hasil

Bila hasil yang sudah disahkan perlu direvisi, dokter membuka kembali dengan
menuliskan **alasan**, yang tercatat di jejak audit. Ini disengaja: hasil yang
sudah disahkan mungkin sudah dipakai mengambil keputusan klinis.

## Cetak lembar hasil

Tombol **Cetak lembar hasil** di halaman pemeriksaan membuka lembar berkop RS.
Tekan Ctrl+P, lalu cetak atau simpan sebagai PDF.

Lembar yang dicetak sebelum disahkan diberi tanda **DRAF — belum disahkan dokter**
agar tidak tertukar dengan hasil resmi.

## Hal yang perlu diperhatikan

**Setiap orang memakai akunnya sendiri.** Setiap pembukaan data pasien tercatat
atas nama akun yang dipakai; akun bersama membuat jejak audit tidak ada gunanya.

**Berkas asli tidak pernah diubah.** Yang tersimpan di arsip persis berkas dari
alat. Interpretasi disimpan terpisah, sehingga penilaian bisa direvisi tanpa
menyentuh bukti rekamannya.

**Periksa antrean impor sebelum pulang.** Rekaman yang tertinggal di antrean
berarti ada pemeriksaan yang belum masuk catatan pasien.
