# Progress Tracker — CTI Platform Revamp

Dokumen ini satu-satunya sumber kebenaran soal "udah sampai mana".
Update checkbox-nya tiap kali ada item selesai. Jangan tandai fase selesai
sebelum **semua exit criteria**-nya hijau.

**Legend:** `[ ]` belum · `[~]` jalan · `[x]` selesai · `[!]` keblokir

Plan lengkap: `~/.claude/plans/oke-bro-jadi-gini-sparkling-fern.md`

---

## Ringkasan

| # | Fase | Status | Perkiraan | Exit criteria |
|---|---|---|---|---|
| 0 | [Salvage & prep](phases/PHASE_0_SALVAGE.md) | `[~]` 0.2 & 0.5 gagal, ulangi | 3–5 hari | `static/` aman, crontab terekam, fixture terekam, secret dirotasi |
| 1 | Skeleton monorepo | `[~]` | 1 minggu | `uv sync` hijau, CI jalan |
| 2 | `cti-core` + skema Postgres | `[ ]` | 2–3 minggu | Alembic up, repo + model ada test |
| 3 | Framework scraper | `[ ]` | 2 minggu | 5 scraper referensi lolos golden test |
| 4 | Migrasi scraper (**100 aktif**) | `[ ]` | ~2 minggu | ≥95% fixture identik, semua modul ke-import |
| 5 | `cti-enrich` | `[ ]` | 2–3 minggu | Output cocok dgn baseline, tiap cabang routing ada test |
| 6 | Celery + beat | `[ ]` | 1–2 minggu | 5 loop web pindah, beat singleton terverifikasi |
| 7 | `apps/api` | `[ ]` | 4–6 minggu | Semua endpoint ada snapshot test |
| 8 | `apps/web` (Next.js) | `[ ]` | 4–6 minggu | Semua tab lama ada padanannya |
| 9 | Control plane scraper | `[ ]` | 1 minggu | Scraper mati kedeteksi dlm 3 interval |
| 10 | Cutover | `[ ]` | 1 minggu | Semua checklist cutover hijau |

> **Realistis: 4–6 bulan untuk satu developer.** Fase 0–4 udah ngasih nilai
> nyata (framework + scraper jalan) walaupun fase sesudahnya mundur.

---

## Fase 0 — Salvage & prep `[~]`

Runbook lengkap: **[phases/PHASE_0_SALVAGE.md](phases/PHASE_0_SALVAGE.md)**

Fase ini **blocking**. Big-bang tanpa baseline itu gak bisa diverifikasi.

> **Soal 3 hari perekaman:** yang ngeblok cuma **hari ke-1**. Format fixture
> nyimpen per tanggal dan digabung, jadi hari ke-2 dan ke-3 numpuk belakangan
> tanpa ngulang apa pun. Satu respons RSS juga udah berisi 10–20 item, jadi
> variasi bentuk item sebagian besar ketangkep di hari pertama — hari
> berikutnya nilainya buat bentuk yang jarang muncul.

> **Audit terakhir: 2026-09-16.** Dua item kelihatan selesai padahal **belum**
> — baca catatannya, jangan cuma lihat checkbox.

- [x] **0.1** Tarik `ScraperNewsWeb/static/` dari prod
      <br>**29 file (28 `.js`, 1 `.css`)** di `legacy/static/`. Sesuai harapan (~27).
      <br>**Sudah di-commit** (`641e6c1`). Gak lagi bergantung satu laptop.
- [x] **0.2** Rekam jadwal scraper
      <br>**Penjadwalnya Rundeck, bukan cron.** Itu sebabnya dump crontab kosong.
      <br>`rundeck_export_full.sh` udah jalan → `rundeck-jobs-full.json` +
      `rundeck-jobs-map.json`. **233 job, 100 aktif, 229 ada path script.**
      <br>Jadwalnya per-jam dengan menit distagger (`:15`, `:30`, `:31`, `:46`) —
      Rundeck udah ngelakuin *spread* yang direncanain di plan.
      <br>**96 dari 100 job aktif** kecocokan ke `ScraperNews/`: 91 langsung,
      4 lewat `python3 -m supportFile.X`, 2 beda penamaan
      (`threatactorTrendGraylog` vs `threatActorTrendGraylog`,
      `threatactorTrendTelegram` vs `threatActorTrendTele.py` — di Linux yang
      case-sensitive, dua job ini kemungkinan gagal diam-diam).
      <br>⚠️ Job `Offset Checker` manggil `supportFile.offsetAlert` yang
      **udah rusak** sejak dedup pindah ke Mongo — dijadwalin tapi sia-sia.
- [x] **0.3** Ambil `config/config.yml`
      <br>`legacy/config.yml` (2.911 byte). Mode file **644, harusnya 600**.
      <br>Ngungkap 2 hal baru: key **`devo:`** (SIEM, ada token — masuk daftar
      rotasi) dan referensi **`cve_db`**.
- [x] **0.4** `mongodump` + **tes restore**
      <br>**Restore terverifikasi** ke container lokal `cti-mongo-legacy`
      (`mongodb://localhost:27017`) pakai `tools/salvage/restore_local.sh`.
      <br>`news_db` 34 collection / 86.250 dok · `threatintel` 14 / 107.580 dok ·
      `test_backup` 4.354 dok · **`cve_db` 0 dok**.
      <br>Container ini dipertahankan: jadi sumber data asli buat rancang skema
      Postgres di Fase 2, tanpa perlu nyentuh produksi.
- [x] **0.5** Rekam fixture — **hari 1-2, ditutup**
      <br>Harness diperbaiki bertahap: guard interpreter, auto-stub `modules.*`,
      timeout adaptif, dependency ketinggalan (`yaml`/`pycountry`/`packaging`/
      `telegram`), config dummy otomatis buat 9 scraper yang buka
      `config/config.yml` langsung.
      <br>⚠️ **Ketemu risiko nyata waktu ngerjain ini**: `newCveThreat.py` +
      `githubPOCMonitor.py` bikin `MongoClient` langsung dari config (bisa
      nulis ke Mongo produksi), dan `threatActorTrendTele.py` punya token bot
      Telegram + Graylog **hardcoded di source** (bisa ngirim pesan asli).
      Ketiganya ditambal di level harness (`pymongo.MongoClient` +
      `telegram.Bot` dibikin inert, `threatActorTrendTele` diblokir permanen
      di `SKIP` — menang lawan `--only` eksplisit, udah diverifikasi paksa).
      Detail: [SECRETS_ROTATION.md](SECRETS_ROTATION.md#-bahaya-operasional-yang-ketemu-di-lapangan-bukan-cuma-di-git-history).
      <br>**Hasil final: 53 dari 96 job aktif (55%) punya baseline valid.**
      Di bawah target awal, tapi sesuai keputusan: **sisanya gak ngeblok** —
      masuk `verify` satu-per-satu pas Fase 4 (baseline direkam live saat itu,
      lihat [ADDING_A_SCRAPER.md](ADDING_A_SCRAPER.md)). Rincian lengkap:
      [KNOWN_BROKEN.md](KNOWN_BROKEN.md#hasil-final-perekaman-fase-05-2026-09-16--17).
      <br>9 di antaranya butuh **token API asli** (GitHub/NVD/Twitter) —
      **user bikin token baru pas mau testing scraper itu, bukan sekarang.**
- [x] **0.6-0.7** Hari ke-2/3 — **gak diperlukan lagi**
      <br>Target "3 hari" awalnya buat nangkep variasi bentuk item. Karena
      sisa yang belum ada baseline sekarang ditangani `verify` on-demand
      (bukan snapshot statis), gak ada nilai tambah nunggu hari ke-3.
- [x] **0.8** Arsitektur secret diputuskan + Vault masuk stack
      <br>**Keputusan final:** `.env` satu sumber terpusat sekarang, Vault
      dipakai beneran pas produksi. Bukan cuma dicatat — **sudah diverifikasi
      jalan**: `docker-compose.yml` punya service `vault` (profile opt-in),
      dites nyala → healthy → unseal otomatis → KV v2 aktif di `cti/` →
      tulis/baca sukses → dimatiin lagi (dev-mode, gak ada state yang perlu
      dipertahankan).
      <br>Yang **belum** dan sengaja ditunda ke fase testing: `cti_core`
      belum baca dari Vault (`SECRETS_BACKEND=env` masih satu-satunya jalur),
      dan token asli (11 item di [SECRETS_ROTATION.md](SECRETS_ROTATION.md))
      belum dirotasi — dirotasi sekali aja pas integrasi Vault beneran jalan.
      <br>⚠️ Rotasi tetap wajib **sebelum** repo lama di-import ke monorepo
      (Fase 1) — itu satu-satunya bagian yang gak bisa ditunda.
- [x] **0.9** Verifikasi `torch` / `bert-extractive-summarizer` gak kepake
      <br>**Terkonfirmasi nol importer.** Yang kepake cuma `sumy.LsaSummarizer`.
- [x] **0.10** Verifikasi cakupan bug regex `\b` di `nlp.py`
      <br>**Cuma L421 yang rusak** (raw string). L35/396/400/414 pakai f-string
      non-raw dan sudah benar — **jangan ikut diubah**.

Temuan dari uji coba harness → lihat [KNOWN_BROKEN.md](KNOWN_BROKEN.md)

**Exit criteria fase 0:**
- [x] `legacy/static/` ada, 28 file `.js`
- [x] `legacy/static/` ke-commit (29 file)
- [x] Penjadwal teridentifikasi: **Rundeck**, 233 job / 100 aktif
- [x] `rundeck-jobs-map.json` ada, 96/100 job aktif kecocokan eksak
- [x] `legacy/config.yml` ada di lokal, gak di-commit
- [x] Restore dump Mongo terverifikasi
- [x] Fixture: 53/96 (55%) baseline valid + jalur `verify`-menangkap-baseline
      buat sisanya — **gate dipenuhi lewat kombinasi, bukan angka tunggal**
- [x] Arsitektur secret diputuskan + Vault terverifikasi di stack
- [ ] 11 secret dirotasi, `gitleaks` bersih _(ditunda ke fase testing, disengaja)_

## Fase 1 — Skeleton monorepo `[~]`

- [x] **1.1** Struktur direktori `cti-platform/`
- [x] **1.2** `pyproject.toml` workspace root + 4 package member
- [x] **1.3** `.python-version` (3.12)
- [x] **1.4** `uv sync` berhasil, `uv.lock` ke-commit
      <br>4 package (`cti-core`, `cti-scraper`, `cti-enrich`, `cti-alerts`)
      resolve tanpa konflik. `apps/api`/`apps/worker` DIKELUARIN dari
      workspace members buat sementara -- direktori masih kosong, baru
      masuk lagi pas Fase 6/7 nulis kode beneran di sana.
      <br>Dikonfirmasi: **gak ada `pymongo`** di dependency tree manapun --
      konsisten sama keputusan pindah ke Postgres.
- [x] **1.5** `.gitignore` + `.env.example` (semua key, tanpa nilai)
- [x] **1.6** `git init` + commit pertama (`641e6c1`, 54 file)
- [x] **1.7** CI: ruff, mypy, pytest, gitleaks
      <br>`.github/workflows/ci.yml` (4 job) + `.gitleaks.toml`. **Keempat
      check dijalanin lokal dan dipastiin hijau sebelum di-commit** --
      bukan cuma ditulis, karena `tools/salvage/record_fixtures.py` yang
      ditulis lewat patch manual belum pernah lewat `ruff format`
      (3 lint error + 1 file gak ke-format, sekarang beres).
      <br>`mypy --strict` cuma di `cti-core`+`cti-scraper` sesuai plan §12 --
      `cti_scrapers/feeds/` hasil migrasi digate golden test (Fase 4), bukan mypy.
      <br>Ditambah 1 test nyata (`test_workspace_skeleton.py`): keempat
      package ke-import. Bukan placeholder buat nutup exit-code pytest --
      pytest exit 5 kalau 0 test, dan test ini genuinely berguna: kalau
      salah satu package berhenti bisa di-import, ketahuan di sini duluan.
- [~] **1.8** `docker-compose.yml` — **cukup buat Fase 1, belum final**
      <br>postgres + redis + vault (opt-in) pakai image resmi, gak butuh
      Dockerfile custom. Dites jalan (lihat commit `3829d5c`).
      <br>Belum ada, disengaja: Dockerfile + service `api`/`worker`/`web` --
      nunggu kode fase-nya masing-masing (2/6/7/8). Checklist ini ditutup
      total pas Fase 9 (`docker compose up -d` full stack).

**Exit criteria:** `uv sync` hijau · `pytest` jalan (boleh 0 test) · CI hijau

---

## Fase 2 — `cti-core` + skema Postgres `[ ]`

- [ ] **2.1** `config.py` — pydantic-settings, `extra="forbid"`
- [ ] **2.2** `db/engine.py` — session async (asyncpg) + sync (psycopg3)
- [ ] **2.3** Model SQLAlchemy: artikel + relasi normalisasi
- [ ] **2.4** Model: IOC, CVE, ransomware, tweet, techstack, package
- [ ] **2.5** Model: user, role, client, audit
- [ ] **2.6** Model: `scraper_runs` (heartbeat per-run), `scraper_seen`, `scraper_config`
- [ ] **2.7** Alembic init + migrasi pertama
- [ ] **2.8** Repository layer
- [ ] **2.9** `urlkit.py` — `canonicalize_url()` + `url_hash()`
- [ ] **2.10** `logging.py` — structlog JSON

**Exit criteria:** `alembic upgrade head` jalan di container kosong · repo ada unit test · `canonicalize_url` lolos tabel ~60 kasus

---

## Fase 3 — Framework scraper `[ ]`

- [ ] **3.1** `items.py` — `ArticleItem`, `RansomwareVictimItem`, `CveItem`, dst
- [ ] **3.2** `base.py` — `BaseScraper` + `ScraperMeta` + `ScrapeContext`
- [ ] **3.3** `registry.py` — auto-discovery via `__init_subclass__` + `pkgutil`
- [ ] **3.4** `sinks.py` — sink registry (jalan keluar scraper bespoke)
- [ ] **3.5** `dedup.py` — two-phase reserve/commit + TTL + cold-start guard
- [ ] **3.6** `runner.py` — rate limit → fetch → dedup → sink → heartbeat
- [ ] **3.7** Family: `RssScraper`, `XPathScraper`, `ApiScraper`
- [ ] **3.8** `spread()` — jitter jadwal biar 142 RSS gak barengan
- [ ] **3.9** CLI — **ini permukaan DX-nya, lihat [ADDING_A_SCRAPER.md](ADDING_A_SCRAPER.md)**
      <br>`new` (scaffold) · `dry-run` (jalan beneran, gak nulis apa-apa) ·
      `verify` (adu sama fixture) · `enable` · `list` · `run`
      <br>`dry-run` yang paling penting: sekarang **gak ada cara nguji scraper
      selain nyalain di produksi dan nungguin**.
- [ ] **3.10** 5 scraper referensi (satu per family) — dibikin lewat CLI,
      bukan ditulis tangan. Kalau alurnya kerasa maksa, benerin CLI-nya dulu.
- [ ] **3.11** Harness golden test

**Exit criteria:** 5 scraper referensi lolos golden test lawan fixture fase 0 · contract test jalan

---

## Fase 4 — Migrasi scraper `[ ]`

> **Scope dikoreksi dari temuan Rundeck:** yang dimigrasi **~91 scraper aktif**
> dulu, bukan 241. Sisanya masuk backlog terpisah, digarap setelah cutover.
> Ini motong Fase 4 dari 3–4 minggu jadi sekitar 2 minggu.

> **Pendekatan: satu per satu lewat jalur yang sama kayak nambah scraper baru**
> ([ADDING_A_SCRAPER.md](ADDING_A_SCRAPER.md)). Codemod bikin kandidatnya, tapi
> tiap scraper tetap lewat `dry-run` → `verify` → `enable` satu-satu.
>
> Alasannya bukan kehati-hatian, tapi supaya **kontraknya ke-uji**. Migrasi 91
> scraper = 91 kali nyoba alur "nambah scraper". Kalau ada langkah yang kerasa
> maksa di scraper ke-12, itu ketahuan pas masih murah dibenerin — bukan nanti
> pas orang lain nambah scraper ke-92.
>
> Aturannya: **kalau migrasi butuh akalan di file scraper, itu bug framework.**
> Benerin framework-nya, jangan diakalin per file.

- [ ] **4.1** `tools/codemod/classify.py` — klasifikasi family via AST
- [ ] **4.2** `tools/codemod/extract.py` — ekstraktor AST per family
- [ ] **4.3** `tools/codemod/emit.py` — template Jinja
- [ ] **4.4** `import_rundeck.py` — `rundeck-jobs-map.json` → `schedule` +
      `enabled` per scraper (bukan crontab; penjadwalnya Rundeck)
- [ ] **4.5** Generate RSS — target ~90% otomatis _(dibatasi ke job aktif)_
- [ ] **4.6** Generate XPath/Playwright (~45) — target ~73%
- [ ] **4.7** Generate requests+lxml (~11)
- [ ] **4.8** Tulis ulang 8 Selenium → `XPathScraper(render=True)` _(pekerjaan baru: semuanya memang gak pernah jalan di Linux)_
- [ ] **4.9** Port manual ~35 scraper bespoke
- [ ] **4.9a** Buat token API baru (GitHub PAT, NVD, twitterapi.io) khusus
      buat testing 9 scraper yang butuh kredensial asli — **user yang bikin,
      pas mau testing scraper itu** (bukan sekarang). Daftar lengkap +
      scraper mana butuh apa: [KNOWN_BROKEN.md](KNOWN_BROKEN.md#butuh-kredensial-asli--ditunda-ke-waktu-testing-keputusan-user).
      <br>⚠️ Jangan pakai token produksi lama yang di `legacy/config.yml` —
      itu masuk daftar rotasi karena udah ke-expose ke laptop dev.
- [ ] **4.10** Triage `migration_report.json`
- [ ] **4.11** Catat gesekan DX yang ketemu waktu migrasi → balik benerin
      framework. Ini output nyata dari pendekatan satu-per-satu.
- [ ] **4.12** Backlog: job nonaktif — diarsipkan, digarap pasca-cutover

**Exit criteria:** 241 modul ke-import semua · contract test hijau · ≥95% fixture identik · sisa delta ada waiver tertulis

---

## Fase 5 — `cti-enrich` `[ ]`

- [ ] **5.1** Stage `fetch_text` (trafilatura + fallback render)
- [ ] **5.2** Stage `classify` — LLM structured output _(fix parse `.replace("json","")`)_
- [ ] **5.3** Stage `summarize` (sumy LSA)
- [ ] **5.4** Stage `extract_ttps`, `extract_iocs`, `extract_cves`
- [ ] **5.5** Stage `score`
- [ ] **5.6** `routing.py` — **fungsi murni**, tiap cabang ada test _(fix `best_practice` yang gak pernah ke-route)_
- [ ] **5.7** Stage `persist` — **satu-satunya penulis**
- [ ] **5.8** Stage `alert` — terpisah dari persist
- [ ] **5.9** SATU IOC extractor (buang 4 fork)
- [ ] **5.10** SATU LLM client (buang 2 fork)
- [ ] **5.11** SATU `send_alert(topic, msg)` (buang 14 fungsi)
- [ ] **5.12** Fix regex zero-day `nlp.py:421`

**Exit criteria:** 200 artikel historis menghasilkan output setara · tiap cabang routing ada test · IOC extractor byte-identik dgn fork lama di korpus 500 artikel

> **Disiplin:** port logika apa adanya. Perbaiki **hanya** bug yang sudah
> disebut. Kalau enrichment dan scraping berubah semantik barengan, diff
> verifikasi jadi gak bisa dibaca.

---

## Fase 6 — Celery + beat `[ ]`

- [ ] **6.1** `app.py` + config (`acks_late`, `visibility_timeout` > task terlama)
- [ ] **6.2** Queue: `scrape.light`, `scrape.browser`, `enrich`, `io`, `control`
- [ ] **6.3** Router dinamis baca `runtime` dari registry
- [ ] **6.4** Beat schedule di-generate dari registry
- [ ] **6.5** Token bucket Redis per-domain
- [ ] **6.6** Pindahkan 5 loop web → beat task
- [ ] **6.7** Lock singleton (cegah double-fire)
- [ ] **6.8** Guard backpressure antrian enrich

**Exit criteria:** 5 loop web hilang dari `main.py` · uvicorn jalan multi-worker · beat singleton terverifikasi (restart, cek gak double-fire)

---

## Fase 7 — `apps/api` `[ ]`

- [ ] **7.1** Bootstrap FastAPI (tanpa background loop)
- [ ] **7.2** Auth: JWT + OIDC + RBAC + multi-tenant
- [ ] **7.3** Port 27 router ke repository Postgres
- [ ] **7.4** Port 56 service
- [ ] **7.5** Buang duplikasi (pkg_vuln, cve_email, ioc, llm)
- [ ] **7.6** Snapshot test tiap endpoint
- [ ] **7.7** Ekspor skema OpenAPI

**Exit criteria:** semua endpoint ada snapshot test · gak ada import `cti_scraper`/`cti_enrich` dari API

---

## Fase 8 — `apps/web` (Next.js) `[ ]`

- [ ] **8.1** Setup Next.js App Router + TS
- [ ] **8.2** Generate client API dari OpenAPI
- [ ] **8.3** Auth + session
- [ ] **8.4** Route: `/dashboard` `/newsroom` `/cve` `/intelligence`
- [ ] **8.5** Route: `/exec` `/xintel` `/recap` `/admin/users`
- [ ] **8.6** Halaman control plane scraper

**Exit criteria:** tiap tab lama ada padanannya · `static/` lama dipakai sebagai spesifikasi perilaku, bukan di-port

---

## Fase 9 — Control plane scraper `[ ]`

- [ ] **9.1** API: list/detail/runs/items
- [ ] **9.2** API: trigger + **dry-run** _(endpoint paling berguna, sekarang gak ada)_
- [ ] **9.3** API: enable/disable/schedule
- [ ] **9.4** API: reset dedup
- [ ] **9.5** Health sweep: `dead` / `degraded` / `zero_yield` / `stale`
- [ ] **9.6** Alert digest (satu pesan, bukan 198)

**Exit criteria:** scraper yang dimatiin kedeteksi `dead` dalam 3 interval · selector yang dirusak kedeteksi `parse_error` dalam 1 interval

---

## Fase 10 — Cutover `[ ]`

- [ ] **10.1** Seed data referensi: `techstack` _(pipeline CVE mati tanpa ini)_, `monitored_accounts`, `ioc_allowlist`, user/role/client
- [ ] **10.2** Verifikasi cold-start guard
- [ ] **10.3** Stop cron lama + systemd unit lama
- [ ] **10.4** Arsipkan dump Mongo final
- [ ] **10.5** `docker compose up -d`
- [ ] **10.6** Pantau 4 jam
- [ ] **10.7** Hypercare 1 minggu

**Checklist cutover — semua wajib hijau:**
- [ ] `static/` ke-commit dan dilayani container web
- [ ] Tiap scraper live punya golden test hijau **atau** waiver tertulis
- [ ] Semua secret dirotasi, `gitleaks` bersih, gak ada secret di layer image
- [ ] Backup Mongo <24 jam, sudah dites restore
- [ ] Stack lama bisa dinyalakan lagi <5 menit (sudah dilatih)
- [ ] Health sweep terbukti bisa deteksi scraper mati (tes di staging)
- [ ] Beat terverifikasi singleton
- [ ] Data referensi ter-seed

---

## Pertanyaan terbuka

- ~~**`/opt/HuntingScript/`**~~ dan ~~**`/opt/alertRundeck/`**~~ — **kelar:
  Rundeck gak jadwalin keduanya.** Di luar scope.
- _(kosong)_
- ~~**`cve_db`**~~ — **kelar: 0 dokumen.** Database mati. Gak usah masuk skema
  Postgres.
- ~~**Devo (SIEM)**~~ — **di-skip**, gak masuk scope revamp. Token-nya tetap
  ada di daftar rotasi karena `config.yml` udah disalin ke laptop.

---

## Scope ditunda — 3 codebase di luar ScraperNews

**Keputusan: dicatat dulu, belum digarap.** Bukan blocker Fase 0.

Export Rundeck ngungkap 9 job (6 aktif) yang nunjuk ke kode di luar
`/opt/ScraperNews` — dan ketiganya **gak ada di checkout ini**:

| Repo | Job | Script | Jadwal | Status |
|---|---|---|---|---|
| `BreachForums` | Breachforums Capture  | `BFcapture.py` | `20 * * *` | nonaktif |
| `BreachForums` | Breachforums Scraping  | `BFurl.py` | `10 * * *` | nonaktif |
| `TwitterScrap` | Twitter CVE Trending | `trendingCve.py` | `0/15 * * *` | **aktif** |
| `TwitterScrap` | Twitter Scrap (1 Hour) | `twitter.py` | `0 * * *` | **aktif** |
| `TwitterScrap` | Twitter Scrap (1.30 Hour) | `twitter30.py` | `30 * * *` | **aktif** |
| `TwitterScrap` | Twitter Chris Sanders | `investigateScenario.py` | `0 * * *` | nonaktif |
| `techstackLibrary` | TechStack Golang | `techstackGO.py` | `46 * * *` | **aktif** |
| `techstackLibrary` | TechStack NPM | `techstackNPM.py` | `46 * * *` | **aktif** |
| `techstackLibrary` | TechStack PyPi | `techstackPYPI.py` | `46 * * *` | **aktif** |

Yang perlu diperhatiin nanti:

- **`techstackLibrary` kemungkinan sumber sebenarnya.** `techstackNPM.py` juga
  ada di `ScraperNews/`, tapi yang dijadwalin Rundeck versi
  `/opt/techstackLibrary`. Salinan di ScraperNews kemungkinan fork yang basi.
  Ini juga nyambung ke duplikasi package-vuln yang udah dicatat di plan
  (`pkg_vuln_service.py` 1109 baris vs `pkgVulnScanner.py` 419 baris) — jadi
  fitur ini kemungkinan dibangun **tiga kali**, bukan dua.
- **`TwitterScrap` berpotensi tabrakan sama `monitorX.py`.** ScraperNews punya
  `monitorX.py` (427 baris, X/Twitter via twitterapi.io) yang nulis ke
  collection `tweets`. `/opt/TwitterScrap` punya `twitter.py` + `twitter30.py`
  yang jalan tiap jam. Perlu dicek: dua jalur ingestion ke data yang sama, atau
  beda fungsi.
- **`BreachForums` dua-duanya nonaktif** — prioritas paling rendah.

**Kalau nanti mau digarap:** butuh isi ketiga folder itu dari prod
(`/opt/TwitterScrap`, `/opt/techstackLibrary`, `/opt/BreachForums`) buat
dianalisa. Detail jadwal tiap job udah ada di `docs/legacy/rundeck-jobs-map.json`.
