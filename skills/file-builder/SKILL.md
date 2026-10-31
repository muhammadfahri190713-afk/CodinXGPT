---
name: file-builder
description: Membuat file/proyek baru dengan benar (struktur, isi lengkap, verifikasi) memakai write/bash.
---
# Membuat file
1. `list`/`glob` dulu: jangan menimpa file yang sudah ada tanpa membacanya.
2. Tulis isi LENGKAP dengan `write` (tanpa placeholder "...").
3. Jalankan/validasi: `python3 -m py_compile`, `node --check`, `bash -n`, `npm run build`, dll.
4. Setelah setiap `write` atau `edit`, tampilkan ringkasan hasil dalam tabel ringkas (file, status, jumlah baris, ukuran); jangan menambahkan banner/dekorasi.
5. Letakkan petunjuk `↓ Geser ke bawah untuk melihat detail dan keluaran berikutnya.` tepat di bawah tabel hasil.
6. Laporkan path file yang dibuat dalam `backtick` dan cara menjalankannya.
Untuk banyak file: buat rencana `todowrite` dan kerjakan satu per satu; rangkum semua file dalam satu tabel akhir.
