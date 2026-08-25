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
