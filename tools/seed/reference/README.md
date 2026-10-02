# Data referensi bawaan (fresh deployment tanpa Mongo lama)

Tiga koleksi kecil yang dibutuhkan platform baru supaya fiturnya hidup, disalin apa adanya dari
dump Mongo legacy (`mongodump`, struktur `<database>/<koleksi>.bson`). Isinya data umum, bukan rahasia:

| File | Isi | Baris | Tabel tujuan |
|---|---|---|---|
| `threatintel/groups.bson` | kamus nama threat actor (sumber: malpedia, eternal-library, threat-card, mstic, orkl, ransomlook, mitre, dll) | 3991 | `threat_actor_groups` |
| `threatintel/apac-people.bson` | demonym/nasionalitas APAC (BUKAN nama orang) | 30 | `monitored_people` |
| `news_db/ioc_allowlist.bson` | IP/domain yang jangan dihitung sebagai IOC | 9 | `ioc_allowlist_entries` |

Tanpa `threat_actor_groups`, scoring tidak menemukan threat actor sama sekali: dropdown TA kosong dan PIR
berbasis TA selalu 0 hasil (temuan QA staging 2026-10-01).

`tools/ops/fresh_deploy.sh` memuatnya otomatis lewat `tools/seed/fase5_reference_data.py --dump-dir`.
Idempoten: dijalankan ulang tidak menggandakan baris dan tidak menimpa perubahan dari UI.

Cara menambah/memperbarui: ganti file `.bson` dengan hasil `mongodump` baru (jaga nama dan lokasinya).
Data kurasi lain (client, techstack, akun X yang dipantau, PIR, dst) TIDAK ikut -- itu diisi lewat UI,
atau lewat `tools/seed/fase10_reference_data.py` kalau punya dump Mongo lama.
