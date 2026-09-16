# Artefak Legacy

Barang yang direkam dari sistem lama di Fase 0. Sebagian **gak bisa
direkonstruksi** kalau host prod hilang.

| File | Sumber | Commit? | Kenapa penting |
|---|---|---|---|
| `crontab.txt` | `dump_crontab.sh` | **ya** | Jadwal 206 scraper. Gak pernah ada di repo. Juga satu-satunya cara tahu scraper mana yang live. |
| `../../legacy/static/` | `pull_static.sh` | **ya** | 27 file JS = seluruh frontend. Ke-gitignore di repo lama. Jadi spesifikasi perilaku buat rewrite Next.js. |
| `../../legacy/config.yml` | `pull_config.sh` | **TIDAK** | Berisi kredensial. Dipakai buat mastiin nama DB/collection. |

Dump Mongo dari `backup_mongo.sh` **jangan** ditaruh di sini — simpan di luar
repo dan di luar host prod. Karena cutover mulai dari DB kosong, dump itu
satu-satunya arsip data historis.
