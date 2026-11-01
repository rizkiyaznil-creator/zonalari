# Catatan teknis

Keputusan yang mahal dipelajari ulang. Ditulis agar tidak ada yang "merapikan"
salah satunya lalu kehilangan citra pasien.

## 1. Kombinasi parameter Orthanc yang menghapus citra tanpa peringatan

**Jangan pernah** memanggil `/studies/{id}/modify` atau `/patients/{id}/modify`
dengan `Keep` berisi `SOPInstanceUID` sementara `KeepSource` bernilai `false`.

Orthanc menjawab **HTTP 200**, dan study **lenyap dari arsip**. Tidak ada galat,
tidak ada peringatan, job berstatus `Success`.

Hasil pengujian pada Orthanc 25.1.0, satu study MR 12 instance, diulang tiga kali:

| `Keep` | `KeepSource` | Hasil |
|---|---|---|
| `StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID` | `false` | **Citra hilang seluruhnya** |
| *(kosong — UID baru)* | `false` | Berhasil, UID study ikut berganti |
| *(kosong — UID baru)* | `true` | Berhasil, tetapi sumber lama tertinggal sebagai duplikat |
| `StudyInstanceUID` saja | `true` | Berhasil, tetapi seri lama dan baru menumpuk dalam satu study |
| **`StudyInstanceUID` saja** | **`false`** | **Benar: UID study terjaga, instance ber-UID baru, tanpa kehilangan maupun duplikat** |

Yang dipakai sistem ini adalah baris terakhir. Instance memperoleh UID baru —
sebagaimana mestinya untuk objek DICOM yang diubah — sementara StudyInstanceUID
dipertahankan agar pemeriksaan tetap dapat dirujuk dengan nomor yang sama oleh
alat, SIMRS, dan SATUSEHAT.

Lihat `ris/app/services/orthanc.py`, fungsi `modify_study()` dan `modify_patient()`.

## 2. Modifikasi harus diminta sinkron

Orthanc menjalankan modifikasi tingkat study dan pasien sebagai *job* asinkron
bila tidak diminta sebaliknya. Pemanggil yang langsung memakai ID lama akan
mendapat 404 karena job sudah menghapus sumbernya. Karena itu setiap pemanggilan
menyertakan `"Asynchronous": False`.

## 3. ID internal Orthanc berubah setelah modifikasi

ID resource Orthanc diturunkan dari identitas DICOM, sehingga berubah begitu
identitas pasien ditulis ulang. Setiap ID yang disimpan RIS menjadi usang.

Penanganannya ada dua lapis:
- `find_study_id_by_uid()` mencari ID terbaru dari StudyInstanceUID yang terjaga.
- `_segarkan_id_orthanc()` menyapu baris study lain yang ID-nya ikut berubah
  ketika rekam pasien diluruskan.

## 4. Mengapa rekam pasien perlu diluruskan lebih dulu

Orthanc menyimpan satu rekam pasien per PatientID, dan menolak memasang study
pada pasien yang sudah ada bila demografinya berbeda:

> Trying to change patient tags in a study. The Patient already exists and has
> other studies.

Kondisi ini bukan kasus langka — justru yang paling sering: beberapa pemeriksaan
masuk di bawah satu nomor rekam medis dengan nama salah ketik yang sama, lalu
dikoreksi satu per satu. Melengkapi seluruh tag utama pasien **tidak** membuat
Orthanc menerimanya; rekam pasiennya memang harus diluruskan lebih dulu, dan
Orthanc sendiri menyarankan `/patients/../modify` lewat pesan galatnya.

Konsekuensinya: menyelaraskan satu pasien ikut mengubah study lain milik nomor
rekam medis yang sama. Itu dikehendaki — satu nomor rekam medis berarti satu
pasien — tetapi cakupannya luas, sehingga selalu dicatat tersendiri di jejak
audit sebagai `pasien.selaraskan` beserta jumlah study yang terdampak.

Study lain yang ikut diluruskan **tetap berstatus belum terverifikasi**: nama
pasiennya benar, tetapi ia masih butuh ordernya sendiri untuk memperoleh
accession number.

## 5. Urutan direktif Caddy

`respond` lepas dievaluasi **setelah** `handle`, sehingga blok penolakan yang
ditulis sebagai `respond @matcher ... 403` tidak pernah kena bila ada `handle`
penangkap-semua di bawahnya. Penolakan akses langsung ke Orthanc karena itu
dibungkus `handle`.

## 6. Gerbang izin ada di proxy, bukan di Orthanc

Autentikasi bawaan Orthanc dimatikan (`AuthenticationEnabled: false`) dan Orthanc
tidak pernah diekspos ke jaringan RS. Perlindungannya ada pada Caddy, yang
memanggil `/internal/authz` di RIS untuk setiap permintaan ke `/dicom-web`,
`/wado`, dan `/ohif` sebelum meneruskannya.

Artinya: **jangan pernah menerbitkan port 8042 Orthanc ke jaringan RS.** Begitu
port itu terbuka, seluruh arsip citra dapat diunduh siapa saja tanpa akun.

## 7. Viewer adalah plugin Orthanc, bukan kontainer terpisah

OHIF dijalankan sebagai plugin di dalam Orthanc (`OHIF_PLUGIN_ENABLED`). Dipilih
begitu agar viewer berada pada asal (origin) yang sama dengan RIS, sehingga
cookie sesi berlaku dan tidak perlu menangani CORS maupun kebocoran kredensial
antar-port.

Stone Web Viewer tidak tersedia pada image `orthancteam/orthanc:25.1.0`
(`libStoneWebViewer.so` tidak ada); yang tersedia antara lain `libOrthancOHIF.so`.

## 8. Build Docker bisa gagal diam-diam

Dua hal yang sempat menyesatkan selama pengembangan:

- `docker compose up -d --build` pernah gagal membangun ulang sementara kontainer
  lama tetap berjalan, sehingga perbaikan kode seolah tidak berpengaruh. Bila
  sebuah perbaikan tampak tidak bekerja, **periksa kode yang benar-benar ada di
  dalam kontainer** sebelum menyalahkan logikanya.
- Batas laju Docker Hub (HTTP 429) membuat build gagal pada tahap resolusi base
  image meski image-nya sudah ada di lokal. Jalan keluarnya memakai builder lama:
  `DOCKER_BUILDKIT=0 docker compose build ris`.

## 9. Folder sertifikat yang boleh kosong

`ris/certs/` dan `watcher/certs/` ada agar RS yang memakai proxy pemeriksa TLS
bisa menaruh CA miliknya di situ. Pada pemasangan biasa folder ini kosong dan
tidak berpengaruh apa-apa — jangan dihapus, karena `Dockerfile` menyalinnya.
