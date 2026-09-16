# Fase 0 — Salvage & Prep

**Status: `[~]` jalan · Blocking — jangan mulai Fase 1 sebelum ini kelar.**

## Kenapa fase ini blocking

Lu milih **big-bang rewrite**. Big-bang cuma aman kalau ada cara ngebuktiin
hasil rewrite masih bener. Ada tiga hal yang cuma hidup di server produksi dan
**gak bisa direkonstruksi dari source**:

| Aset | Kenapa gak bisa direkonstruksi | Kalau hilang |
|---|---|---|
| `ScraperNewsWeb/static/` | Ke-gitignore, 27 file JS, gak ada di repo | Seluruh frontend hilang — dan itu spesifikasi perilaku buat rewrite Next.js |
| Crontab | Gak pernah ada di repo | Gak tahu scraper mana yang live dan tiap berapa lama |
| `ScraperNews/config/config.yml` | Ke-gitignore | Gak tahu nama DB/collection dan struktur config asli |

Plus satu hal yang harus direkam **selagi scraper lama masih jalan**:
**fixture** — output scraper lama, buat dibandingin sama hasil rewrite.
Begitu script lama dihapus, baseline-nya hilang selamanya.

> **Prioritas #1 hari ini: `pull_static.sh`.** Kalau host prod mati sebelum itu
> ditarik, frontend lu hilang. Ini ngalahin semua risiko teknis lain di plan.

---

## Prasyarat

```bash
export CTI_PROD_HOST=user@prod-server        # sesuaikan
export CTI_PROD_WEB=/opt/ScraperNewsWeb
export CTI_PROD_SCRAPER=/opt/ScraperNewsRevamp   # NB: nama dir beda dari nama repo
```

Cek dulu path-nya bener:
```bash
ssh "$CTI_PROD_HOST" 'ls -d /opt/ScraperNewsWeb /opt/ScraperNewsRevamp 2>&1'
```

> **Catatan transport.** Dua hal yang udah ketemu di lapangan:
>
> - `/usr/bin/rsync` di macOS itu **openrsync** (kompatibel rsync 2.6.9), bukan
>   rsync 3.x — flag `--info=progress2` ditolak. Script-nya probe dan fallback
>   ke `--progress`. Mau rsync asli: `brew install rsync`.
> - **Host prod gak punya rsync.** `pull_static.sh` otomatis turun ke
>   tar-over-ssh (`tar -czf - | tar -xzf -`), dan kalau tar juga gak ada,
>   ke `scp -r`. Gak ada yang perlu di-install di prod.
>
> Host ini masih pakai **password auth**, jadi script pakai SSH ControlMaster
> biar password cuma ditanya sekali per run. Buat ngilangin prompt sama sekali
> (dan bikin script fase 0 lain lebih enak):
>
> ```bash
> ssh-copy-id "$CTI_PROD_HOST"
> ```

---

## 0.1 — Tarik `static/` `[ ]`

```bash
./tools/salvage/pull_static.sh
```

Nyalin `$CTI_PROD_WEB/static/` ke `legacy/static/`. Harusnya dapet ~27 file JS
(`api.js`, `core.js`, `newsroom/*.js`, dst) plus CSS.

**Verifikasi:**
```bash
find legacy/static -name '*.js' | wc -l      # harapkan ~27
```

**Langsung commit.** Jangan nunggu sampai fase ini kelar.

---

## 0.2 — Rekam crontab `[ ]`

```bash
./tools/salvage/dump_crontab.sh
```

Nangkep crontab semua user, `/etc/crontab`, `/etc/cron.d/*`, dan systemd timer
ke `docs/legacy/crontab.txt`.

**Verifikasi:** file berisi baris-baris yang mirip
`*/15 * * * * cd /opt/... && .../python3 bleepcompThreat.py`

**Kalau crontab udah gak ada**, cadangannya: rekonstruksi cadence dari data —
`threatintel.offsets.seen_at` di-group per `script`, ambil median jarak antar
cluster run. Ini lower bound yang lumayan. Cadangan terakhir: default per family
(RSS 15m, XPath statis 30m, browser 2j) lewat `spread()`.

---

## 0.3 — Ambil `config.yml` `[ ]`

```bash
./tools/salvage/pull_config.sh
```

Ditaruh di `legacy/config.yml` — **jangan di-commit** (ada kredensial; udah
masuk `.gitignore`). Gunanya buat mastiin nama DB/collection asli sebelum
skema Postgres dirancang.

---

## 0.4 — Backup Mongo + tes restore `[ ]`

```bash
./tools/salvage/backup_mongo.sh
```

Dump `news_db` + `threatintel`, lalu **restore ke container scratch** dan
bandingin jumlah dokumen per collection. Script-nya udah ngelakuin ini —
backup yang belum dites restore itu bukan backup.

Karena cutover mulai dari DB kosong, dump ini jadi **satu-satunya** arsip data
historis. Simpan di luar host prod.

---

## 0.5–0.7 — Rekam fixture (3 hari) `[ ]`

```bash
./tools/salvage/record_fixtures.py --scrapers-dir ../ScraperNews --out ../cti-platform/tests/fixtures
```

Buat tiap scraper lama, script ini:
1. Nge-patch `push_job` dan `is_new_and_mark` biar **gak nulis apa-apa** —
   cuma ngumpulin `(title, url)`
2. Nyimpen byte HTTP mentahnya → `<scraper>/<tanggal>.input.*`
3. Nyimpen item yang dihasilkan → `<scraper>/expected_items.json`

Nanti di Fase 4, plugin baru dikasih byte yang sama dan **harus** ngeluarin
item yang sama. Ini gate cutover-nya.

**Kenapa 3 hari:** feed itu muter. Snapshot sehari bikin ngerasa cakupannya
udah cukup padahal belum — parser yang cuma jalan di satu bentuk item bakal
lolos di hari 1 dan gagal di produksi.

**Verifikasi:**
```bash
ls tests/fixtures | wc -l                    # harapkan ≥200
```

### Prasyarat: venv perekam

Script lama butuh dependency fetch/parse-nya. Tapi **tidak** butuh stack NLP
(spacy/sumy) karena `modules.nlp` di-stub, jadi env-nya ringan:

```bash
./tools/salvage/setup_legacy_env.sh      # bikin .venv-legacy
.venv-legacy/bin/python tools/salvage/record_fixtures.py ...
```

### Prasyarat: context file

Sebagian scraper baca konfigurasi dari MongoDB. Kalau itu kosong, mereka
ngehasilkan **0 item dan fixture-nya bohong**. Ambil datanya dari prod:

```bash
mongosh "$MONGO_URI" --quiet --eval \
  'JSON.stringify(db.getSiblingDB("threatintel").techstack.distinct("name"))'
```

Masukin ke file bergaya `tools/salvage/fixture_context.example.json`, lalu:

```bash
... record_fixtures.py --context tools/salvage/fixture_context.json ...
```

Kena ke `cisacatalogThreat`, `newCveThreat`, `techstackNPM`, `monitorX`.
File ini juga jadi basis **seed data referensi di Fase 10.1** — karena cutover
mulai dari DB kosong, `techstack` wajib di-seed atau pipeline CVE mati.

---

## Realitas lapangan (dari uji coba harness)

Harness-nya udah diuji ke scraper beneran. Tiga mode kegagalan yang bakal lu
temuin, dan cara ngebedainnya:

### 1. Diblokir situsnya — fixture TIDAK valid

```
[  2/3] gbHackerThreat            0 item  BLOCKED
  gbHackerThreat    https://gbhackers.com/feed/
```

`gbhackers.com` balikin halaman challenge Cloudflare, bukan RSS. Scraper lama
masuk cabang `else`, print error, selesai — diam-diam nol item. Persis jenis
kegagalan yang selama ini gak kedeteksi.

**Artinya: rekam fixture dari IP yang sama dengan host produksi**, karena di
situlah scraper lama beneran jalan. Ngerekam dari laptop bakal ngasih fixture
palsu buat semua situs yang mem-filter berdasarkan IP/geo. Cara paling gampang:
rsync repo ke host prod, jalanin perekam di sana, tarik hasilnya.

Perekam nandain ini `BLOCKED` (403/429/5xx) dan nyimpen `http_status` +
`blocked_urls` ke `meta.json`, jadi fixture jelek gak diam-diam kepake.

### 2. Nol item yang SAH — feed lagi sepi

```
[  1/3] cisacatalogThreat         0 item  EMPTY
```

`cisacatalogThreat` nyaring `dateAdded` ke hari ini/kemarin. Katalog CISA
terakhir rilis beberapa hari lalu, jadi nol itu **benar**.

**Ini alasan perekaman 3 hari itu wajib.** "EMPTY" gak bisa dibedain dari
"rusak" cuma dari satu hari — dan ketidakmampuan ngebedain dua hal ini persis
masalah #2 yang mau dibenerin revamp ini.

### 3. Script yang emang rusak — temuan gratis

```
securityaffairsThreat    NameError: name 'html' is not defined
theRecordThreat          5 item, lalu NameError: name 'message_list' is not defined
```

`securityaffairsThreat` udah dikenali sebelumnya (`lxml.html` gak di-import).
`theRecordThreat` **temuan baru** — dia push 5 item terus crash, jadi selama
ini jalan separuh tanpa ada yang tahu.

Catat semuanya di `KNOWN_BROKEN.md`. Script yang rusak **gak butuh golden
test** — gak ada perilaku benar yang mau dipertahankan. Yang perlu diputuskan
per script: diperbaiki waktu rewrite, atau dibuang.

---

## 0.8 — Rotasi secret `[ ]`

Lihat **[../SECRETS_ROTATION.md](../SECRETS_ROTATION.md)**.

Rotasi **sebelum** repo lama di-import ke monorepo, biar blob yang ke-import
cuma berisi nilai mati.

---

## 0.9 — Verifikasi `torch` `[x]` SELESAI

```
torch                   → 0 importer
bert-extractive-summarizer → 0 importer
transformers            → 0 importer
sumy                    → dipakai (nlp.py, nlp_worker.py)
```

**Kesimpulan:** `torch` dan `bert-extractive-summarizer` dead weight di
`requirements.txt`. Buang. Image enrich turun ~2.5 GB, jadi pemisahan image
bukan lagi kendala berat — tetap dilakukan (Chromium & spaCy gak ada urusan
di image API), tapi jauh lebih murah dari perkiraan awal di plan.

---

## 0.10 — Verifikasi bug regex `\b` `[x]` SELESAI

```python
# nlp.py:35,396,400,414 — f-string NON-raw → "\\b" jadi \b → BENAR
if re.search(f"\\b{str(keyword).lower()}\\b", ...)

# nlp.py:421 — raw string → "\\b" tetap literal backslash+b → RUSAK
zero_day_list = re.findall(r"\\b(zero|0)[-.]day\\b", ...)
```

**Kesimpulan:** cuma **L421** yang rusak. Deteksi zero-day gak pernah cocok.
Empat baris lainnya sudah benar — **jangan ikut "diperbaiki"**, nanti malah
merusak yang jalan. Plan udah dikoreksi.

---

## Exit criteria

Fase 0 selesai kalau semua ini benar:

- [ ] `legacy/static/` ke-commit, ~27 file JS
- [ ] `docs/legacy/crontab.txt` ke-commit, isinya jadwal beneran
- [ ] `legacy/config.yml` ada di lokal (gak di-commit)
- [ ] Dump Mongo ada, **restore udah dites**, disimpan off-host
- [ ] Fixture ≥200 scraper × 3 hari
- [ ] 7 secret dirotasi, `gitleaks` bersih
- [x] Temuan `torch` terverifikasi
- [x] Cakupan bug `\b` terverifikasi

**Kalau 0.5–0.7 gak bisa dituntasin** (host udah gak keakses, feed di balik
auth), stop dan kabarin. Tanpa fixture, gak ada cara ngebuktiin 206 parser
hasil rewrite masih bener, dan strateginya harus turun jadi per-family — lama
dihapus satu family sekaligus, sambil stack lama tetap jalan buat pembanding.
