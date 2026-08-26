# Catatan keputusan teknis

Berisi keputusan yang diambil selama pengembangan beserta alasannya.
Format: keputusan, konteks, alasan, konsekuensi.

---

## 1. Menyimpan lapisan `raw` apa adanya

**Keputusan.** Respons API disimpan ke skema `raw` tanpa transformasi apa pun.

**Alasan.** Kalau logika transformasi ternyata salah, data bisa dibangun ulang
tanpa memanggil API lagi. Ini juga membuat batas tanggung jawab jelas:
ingestion hanya memindahkan data, dbt yang mengubah bentuknya.

**Konsekuensi.** Penyimpanan lebih boros, dan ada satu lapisan tambahan yang
harus dipelihara.

---

## 2. Semua waktu disimpan dalam UTC

**Keputusan.** Kolom `observed_at` bertipe `TIMESTAMPTZ` dan selalu UTC.
Konversi ke waktu lokal dilakukan di lapisan marts.

**Alasan.** Enam kota berada di empat zona waktu berbeda. Menyimpan waktu lokal
membuat perbandingan antar kota rawan salah, terutama saat mengagregasi per jam.

**Konsekuensi.** Query untuk analisis harian per kota perlu konversi eksplisit.

---

## 3. Kunci primer gabungan, bukan surrogate key, di lapisan raw

**Keputusan.** `(location_key, observed_at, variable, source)` sebagai primary key.

**Alasan.** Membuat proses pemuatan idempotent — menjalankan ulang ingestion
untuk rentang tanggal yang sama tidak menggandakan baris. Ini penting karena
API kadang gagal di tengah jalan dan harus diulang.

**Konsekuensi.** Penulisan harus memakai `ON CONFLICT DO UPDATE`, sedikit lebih
lambat dibanding `INSERT` biasa.

---

<!-- TODO: tambahkan keputusan berikutnya seiring pengerjaan -->

## 4. Data disimpan dalam bentuk panjang, bukan lebar

**Keputusan.** Tabel fakta memakai satu baris per variabel
(`location x waktu x variabel x sumber`), bukan satu kolom per variabel.

**Alasan.** Daftar variabel akan bertambah seiring waktu. Bentuk lebar
memaksa perubahan skema setiap kali ada polutan atau variabel cuaca baru,
sementara bentuk panjang cukup menambah baris.

**Konsekuensi.** Query perbandingan antar variabel perlu operasi pivot, dan
jumlah barisnya jauh lebih banyak. Untuk kebutuhan analisis harian, ini
diatasi oleh model agregat `agg_daily_air_quality`.

---

## 5. Kelengkapan data ikut dilaporkan, bukan disembunyikan

**Keputusan.** `agg_daily_air_quality` menyertakan kolom
`measurement_completeness_pct`.

**Alasan.** Rata-rata harian dari 3 jam data tidak setara dengan rata-rata
dari 24 jam. Menyajikan keduanya sebagai angka tunggal tanpa keterangan akan
menyesatkan pengguna data.

**Konsekuensi.** Pengguna data harus memutuskan sendiri ambang kelengkapan
yang dapat diterima.

---

## 6. Waktu lokal dihitung di lapisan marts

**Keputusan.** Kolom `observed_at_local` dihitung di `fct_hourly_measurement`
memakai zona waktu dari `dim_location`, bukan disimpan sejak lapisan raw.

**Alasan.** Lapisan raw harus netral dan tidak kehilangan informasi. Zona
waktu adalah keputusan penyajian, bukan fakta pengukuran.

**Konsekuensi.** Perubahan zona waktu suatu kota cukup diperbaiki di seed,
tanpa memuat ulang data dari API.

---

## 7. Versi dbt dikunci tepat, bukan sebagai rentang

**Keputusan.** `dbt-core==1.11.14` dan `dbt-postgres==1.11.0`, bukan `dbt-postgres>=1.8,<2.0`.

**Alasan.** Dua masalah nyata muncul saat memakai rentang. Pertama, `dbt-postgres`
menyatakan kebutuhannya sebagai `dbt-core<2.0,>=1.8.0rc1`; karena batas bawahnya
pra-rilis, pip ikut memilih pra-rilis dan memasang dbt 2.0 beta, yang belum
mendukung PostgreSQL. Kedua, `dbt-core` 1.12 menambah dependensi yang harus
diunduh saat instalasi, sehingga pemasangan menjadi rapuh terhadap gangguan jaringan.

**Konsekuensi.** Pembaruan versi harus dilakukan sengaja, tidak otomatis. Itu justru
yang diinginkan: repo yang jalan hari ini harus tetap jalan bulan depan tanpa satu
baris kode pun berubah.
