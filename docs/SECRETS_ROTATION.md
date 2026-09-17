# Rotasi Secret — Fase 0.8

**Status: `[ ]` belum · Blocking sebelum repo lama di-import ke monorepo.**

Item 1–9 **ke-commit ke git** di repo lama. Item 10 ketemu waktu Fase 0.3
(`config.yml` di-gitignore jadi gak ada di git — tapi ada di host prod dan
sekarang ada salinannya di laptop, jadi tetap perlu ditangani).

Semua secret di bawah ini Karena ada di
history, semuanya harus dianggap **sudah bocor** — gak cukup cuma dihapus dari
file, nilainya harus diganti di sistem asalnya.

Urutannya penting: **rotasi dulu, baru import repo lama.** Kalau kebalik, blob
yang ke-import bakal bawa kredensial hidup ke repo baru.

> Jangan pernah nge-print atau nge-echo nilai secret waktu ngerjain ini —
> termasuk ke log terminal, CI, atau riwayat shell.

---

## Inventaris

Lokasi baris udah diverifikasi langsung dari source.

| # | Lokasi | Jenis | Aksi |
|---|---|---|---|
| 1 | `ScraperNews/threatActorTrendTele.py:9` | Token API Graylog (`HTTPBasicAuth`) | Cabut di Graylog, terbitkan baru |
| 2 | `ScraperNews/threatActorTrendTele.py:24` | Token bot Telegram | `/revoke` ke BotFather, ambil token baru |
| 3 | `ScraperNews/threatActorTrendTele.py:26` | Chat ID + thread ID Telegram | Bukan secret, tapi pindahin ke config |
| 4 | `ScraperNews/scripts/export_db.py:23` | URI Mongo lengkap + kredensial (`news_db`) | Ganti password user Mongo |
| 5 | `ScraperNews/scripts/export_db.py:37` | URI Mongo lengkap + kredensial (`threatintel`) | Ganti password user Mongo |
| 6 | `ScraperNews/scripts/import_db.py:60` | URI Mongo dgn kredensial (f-string) | Sama, user yang sama |
| 7 | `ScraperNews/scripts/import_db.py:64` | URI Mongo dgn kredensial (f-string) | Sama, user yang sama |
| 8 | `ScraperNewsWeb/insert_to_mongo.py:35` | Kredensial Mongo produksi | Sama — _sedang dikerjakan di task terpisah_ |
| 9 | `ScraperNewsWeb/app/config.py:59-60` | Alamat email internal `@privy.id` hardcoded | Bukan kredensial; pindahin ke `CVE_EMAIL_CC` |
| 10 | `legacy/config.yml` → `devo.token` | **Token collector Devo (SIEM)** | Cabut di Devo. Prioritas rendah — integrasinya di-skip, tapi tokennya udah kesalin ke laptop. |
| 11 | `docs/legacy/rundeck-get-schedule.sh:5` | **Token API Rundeck** | Cabut di Rundeck, terbitkan baru. File udah di-gitignore. |

Catatan: `app/config.py:30` dan `:51` bikin URI dari env var — **itu gak
masalah**, biarin.

---

## Arsitektur secret: sekarang vs produksi

Dua fase, disengaja beda:

| | Sekarang (dev / pra-produksi) | Produksi |
|---|---|---|
| Sumber | `.env`, satu file, dikontrol terpusat | **HashiCorp Vault** |
| `SECRETS_BACKEND` | `env` (default) | `vault` |
| Yang baca | `cti_core.settings` langsung dari env var | `cti_core.settings` lewat client Vault |
| Status Vault | **sudah di `docker-compose.yml`**, opt-in via `docker compose --profile vault up` — mode dev (in-memory, gak persisten), sudah dites: unseal otomatis, KV v2 nyala di path `cti/`, tulis/baca kekonfirmasi | belum — integrasi `cti_core` baca Vault dikerjain di fase testing |

**Kenapa dipisah gini:** integrasi Vault (client, path convention, AppRole/token
auth) itu kerjaan Fase 2/testing yang nyata, bukan yang bisa diselesaikan
sekarang tanpa app code. Naruh Vault di stack SEKARANG artinya integrasinya
bisa mulai diuji kapan aja tanpa nunggu momen "migrasi besar", dan bentuk
path-nya (`cti/telegram`, `cti/mongo`, dst — cocok sama nama section di
`.env.example`) udah bisa dirancang dari sekarang.

**Timing rotasi token asli:** dikerjain pas fase testing, barengan integrasi
Vault beneran — gak perlu dirotasi dua kali (sekali buat `.env`, sekali lagi
buat Vault). Yang wajib sekarang cuma dua:

1. Daftar di bawah lengkap dan akurat
2. Gak ada satu pun yang ke-commit ke repo baru — sudah aman, semua file yang
   berisi kredensial ada di `.gitignore` dan commit pertama udah diverifikasi

⚠️ Satu pengecualian yang gak bisa ditunda: rotasi **sebelum** repo lama
di-import ke monorepo (Fase 1), biar blob yang keikut cuma berisi nilai mati.

## ⚠️ Bahaya operasional yang ketemu di lapangan (bukan cuma di git history)

Waktu ngerekam fixture Fase 0.5, ketemu sesuatu yang lebih serius dari
"secret ke-commit": **script yang bisa BENERAN NGIRIM pesan/nulis data
produksi kalau dijalanin sembarangan**, independen dari config apa pun yang
disuapin.

| File | Bahaya | Status |
|---|---|---|
| `ScraperNews/threatActorTrendTele.py` | Token bot Telegram + token API Graylog **hardcoded di source** (bukan dari config.yml). Kalau ke-eksekusi, ngirim pesan BENERAN ke chat/thread Telegram asli dan query BENERAN ke `privy.graylog.cloud`. | **Diblokir permanen** di `record_fixtures.py` (`DANGEROUS_LIVE_SIDE_EFFECTS`), menang bahkan lawan `--only`. Diverifikasi: gak pernah ke-eksekusi di run manapun. |
| `ScraperNews/newCveThreat.py` | Bikin `MongoClient` langsung dari `config.yml`, manggil `bulk_write` — bisa nulis ke `news_db.cve_tracker` produksi kalau dikasih config asli. | Ditambal di sumbernya: `pymongo.MongoClient` ditambal jadi inert di harness perekam, apa pun config yang disuapin. |
| `ScraperNews/githubPOCMonitor.py` | Sama — `MongoClient` langsung dari `config.yml`. | Sama, ditambal di level `pymongo.MongoClient`. |

**Kenapa ini nyaris kejadian:** `threatActorTrendTele.py` gak pernah kepanggil
di run normal cuma karena kebetulan nama file (`threatActorTrendTele.py`)
beda dari nama script di job Rundeck (`threatactorTrendTelegram.py`) — bukan
karena ada yang sengaja ngelindungin. Kalau nanti ketidakcocokan nama itu
dibenerin (memang salah satu item perbaikan), atau siapa pun manggil
`--only threatActorTrendTele` buat tes satu-satu, token itu bakal beneran
kepake. Makanya pertahanannya ditaruh di `SKIP` — menang lawan `--only`
apa pun — bukan cuma diandalkan dari ketidakcocokan nama.

**Pelajaran buat framework baru (Fase 3):** `BaseScraper` gak boleh kasih
scraper akses langsung ke `MongoClient`/`telegram.Bot`/kredensial mentah sama
sekali — cuma lewat sink yang disediakan framework. Kelas bug ini (script
bypass abstraksi dan pegang kredensial langsung) gak boleh mungkin secara
struktural di platform baru, bukan cuma "jangan dilakuin".

## Prosedur

### 1. Token bot Telegram
1. BotFather → `/revoke` untuk bot yang dipakai
2. Simpan token baru ke secret store, **jangan** ke file
3. Bakal dibaca lewat `TELEGRAM__BOT_TOKEN` di platform baru

> Ini nge-nonaktifin alerting sampai token baru ke-deploy. Kerjain di jam sepi.

### 2. Token API Graylog
1. Cabut token lama di Graylog
2. Graylog `graylogLogging.py` **dibuang di platform baru** (2 importer, 1
   udah di-comment) — jadi gak perlu token pengganti kecuali
   `threatActorTrendGraylog.py` mau dipertahankan

### 3. Password user Mongo
Kena ke item 4–8 (user yang sama muncul di beberapa file).

```javascript
// di mongosh, sebagai admin
db.getSiblingDB("admin").changeUserPassword("<user>", passwordPrompt())
```

`passwordPrompt()` bikin password gak masuk riwayat shell.

Update di semua tempat yang masih jalan **sebelum** password lama dimatiin:
`config/config.yml` di prod, `.env` web app, systemd unit.

> Kalau cutover mulai dari DB kosong, akhirnya bakal ada user Mongo baru buat
> platform baru. Tapi kredensial lama tetap harus dirotasi — stack lama masih
> jalan sampai cutover, dan nilai lamanya ada di git.

### 4. Alamat email
Pindahin dari `app/config.py:59-60` ke `CVE_EMAIL_CC` di env.

---

## Cegah kejadian lagi

Pasang di repo baru sebelum commit pertama:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks: [{id: gitleaks}]
```

Plus gate di CI:
```bash
gitleaks detect --no-git --redact --exit-code 1
```

`--redact` bikin CI gak nge-print temuannya.

---

## Checklist

- [ ] Token bot Telegram dicabut + diganti
- [ ] Token API Graylog dicabut
- [ ] Password user Mongo diganti (kena 5 lokasi)
- [ ] Semua konsumen yang masih jalan diupdate sebelum kredensial lama mati
- [ ] Email dipindah ke env
- [ ] Token Devo dicabut + diganti (`devo.token` di config.yml)
- [ ] Token API Rundeck dicabut + diganti; pakai `$RD_TOKEN` dari env, jangan hardcode
- [ ] `gitleaks` jalan di repo baru, hasilnya bersih
- [ ] Hook pre-commit terpasang
- [ ] Baru setelah semua ini: import repo lama ke monorepo
