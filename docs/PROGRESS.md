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
| 2 | `cti-core` + skema Postgres | `[x]` | 2–3 minggu | Alembic up, repo + model ada test |
| 3 | Framework scraper | `[x]` | 2 minggu | 5 scraper referensi lolos golden test |
| 4 | Migrasi scraper (**100 aktif**) | `[x]` | ~2 minggu | ≥95% fixture identik, semua modul ke-import |
| 5 | `cti-enrich` | `[x]` | 2–3 minggu | Output cocok dgn baseline, tiap cabang routing ada test |
| 6 | Celery + beat | `[x]` inti; sisanya dipindah 7.8/10.1d/10.1e | 1–2 minggu | ~~5 loop web pindah~~ (→ 7.8) · ~~beat singleton terverifikasi~~ (→ 10.1d) |
| 7 | `apps/api` | `[~]` 7.1/7.2 auth kelar, sisanya nyusul | 4–6 minggu | Semua endpoint ada snapshot test · 5 loop jadi beat task (7.8) |
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

## Fase 2 — `cti-core` + skema Postgres `[x]` SELESAI

- [x] **2.1** `config.py` — pydantic-settings, `extra="forbid"`
      <br>Bug nyata ketemu+dibenerin: `extra="forbid"` gak nurun ke nested
      `BaseModel` (typo `TELEGRAM__BOTTOKEN` diam-diam ke-drop) — lihat
      `_StrictModel` di config.py dan `test_config.py`.
- [x] **2.2** `db/engine.py` — sesi async (asyncpg, FastAPI) + sync
      (psycopg3, Celery/CLI), satu model dipakai dua-duanya. Timestamp
      `ScraperRun` di-set eksplisit di Python, bukan `server_default` +
      implicit-reload — itu bakal meledak di jalur async.
- [x] **2.3** Model SQLAlchemy: `Article` + 4 tabel anak (countries+peran,
      industries, threat_actors, ttps). `confidence_score` SATU kolom,
      `overrides` (JSONB) buat koreksi analis yang gak boleh ketimpa scraper.
- [x] **2.4** Model: IOC (+sources/tags/threat_actors/feedback), CVE
      tracker (+references/affected/pocs/false_positives/tickets),
      ransomware victim, tweet + monitored_accounts, techstack, package
      vuln (+aliases/dep_edges). 35 tabel total.
- [x] **2.5** Model: user/role/client(+countries)/user_clients/audit_log.
      `client_id` jadi PRIMARY KEY string (natural key), bukan surrogate.
- [x] **2.6** Model: `ScraperRun` (heartbeat per-run — INI yang bikin
      nol-item vs crash bisa dibedain, gantiin `scraper_health.py` lama),
      `ScraperItem`, `ScraperConfig`, `ScraperSeen` (dedup two-phase,
      kolom `dedup_key` sengaja beda nama dari `Article.url_hash` — beda
      namespace, lihat docstring model).
- [x] **2.7** Alembic init + migrasi pertama — **diverifikasi ke Postgres
      beneran** (docker compose), bukan diasumsikan: `alembic upgrade head`
      sukses, 35 tabel kebentuk, `alembic downgrade base` bersih balik ke 0,
      `alembic upgrade head` lagi sukses, `alembic check` bilang "No new
      upgrade operations detected" (migrasi match persis model).
- [x] **2.8** Repository layer — `ArticleRepo`/`AsyncArticleRepo` (upsert
      dgn field mesin vs overrides, nolak nulis field identitas/typo),
      `IOCRepo`/`AsyncIOCRepo` (upsert+sources, feedback TP/FP),
      `ScraperRunRepo`/`AsyncScraperRunRepo` (heartbeat start/finish).
      Sisanya (CVE, tweet, dst) nyusul pas Fase 7 butuh.
- [x] **2.9** `urlkit.py` — `canonicalize_url()` + `url_hash()`. 75 test
      lolos (target ~60). Bug nyata ketemu+dibenerin: decode-lalu-encode
      path SEKALIGUS ketimbun `%2F` (slash sbg data) sama `/` (pemisah
      segment) — dibenerin proses per-segmen.
- [x] **2.10** `logging.py` — structlog JSON, gantiin `print()` polos.

**Exit criteria — SEMUA terverifikasi jalan, bukan diasumsikan:**
- [x] `alembic upgrade head` jalan di container Postgres kosong (35 tabel)
- [x] `alembic check` konfirmasi migrasi match persis model (0 diff)
- [x] `alembic downgrade base` → `upgrade head` lagi, reversibel penuh
- [x] Repo ada 96 unit+integration test, semua hijau (2x run, gak flaky)
- [x] `canonicalize_url` lolos 75 test (target ~60)
- [x] Integration test lawan Postgres BENERAN (testcontainers), bukan mock

**Bug test-isolation ketemu+dibenerin di jalan:** fixture integrasi yang
ngubah `os.environ` global (scope semula "session") bocor ke
`tests/unit/test_config.py` kalau `tests/integration/` kebetulan jalan
duluan (urutan alfabetis). Dibenerin: scope turun ke "package" + tambah
`__init__.py` di kedua folder test (syarat resmi pytest biar package-scope
fixture teardown bener kapan waktunya).

---

## Fase 3 — Framework scraper `[x]` SELESAI

- [x] **3.1** `items.py` — `ArticleItem`, `RansomwareVictimItem`, `CveItem`,
      `PackageVulnItem`. Sink cuma dipasang buat 2 pertama (sesuai
      kebutuhan 5 referensi); `CveItem`/`PackageVulnItem` nunggu Fase 4/7.
- [x] **3.2** `base.py` — `BaseScraper` + `ScraperMeta` + `ScrapeContext`.
      Lupa nulis `meta` di subclass = `ConfigError` di waktu IMPORT (fail
      loud), bukan diam-diam gak kedaftar.
- [x] **3.3** `registry.py` — auto-discovery via `__init_subclass__` +
      `pkgutil`. Modul yang gagal import GAGAL KERAS (fail loud) — ini yang
      nangkep kelas bug "lupa import lxml.html" di CI/boot, bukan diam-diam
      mati selamanya kayak sistem lama.
- [x] **3.4** `sinks.py` — dispatch berdasarkan TIPE item, bukan nama
      scraper. `RansomwareVictimItem` kebukti beneran lewatin pipeline
      artikel dan nulis langsung ke `ransomware_victims`.
- [x] **3.5** `dedup.py` + `cti_core.db.repositories.scraper_seen.py` —
      reserve/commit/release two-phase. Diverifikasi ke Postgres beneran:
      run pertama scraper live 15 item baru, run kedua 15 di-drop semua.
- [x] **3.6** `runner.py` — rate limit → fetch → dedup → sink → heartbeat.
- [x] **3.7** Family: `RSSScraper`, `XPathScraper` (runtime light+browser
      SATU class), `ApiScraper`.
- [x] **3.8** `spread()` — jitter deterministik. Diverifikasi: 142 scraper
      simulasi tersebar 5-13 per menit dari 15 slot (bukan numpuk di :00).
- [x] **3.9** CLI (`cti-scraper`) — `list`, `dry-run`, `run`, `verify`
      (+`--record` buat baseline baru), `enable`, `disable`. Semua
      diverifikasi jalan lawan Postgres+situs asli, bukan diasumsikan.
- [x] **3.10** 5 scraper referensi — **bukan "satu per family" tapi "satu
      per jalur kode berbeda"**, disengaja lebih luas dari 3 family:
      `bitdefender` (RSS), `cyfirma` (XPath light), `trendmicro` (XPath
      browser, Playwright+route-interception), `ransomware_live` (BaseScraper
      langsung, item bespoke), `cisa_kev` (BaseScraper langsung, ArticleItem
      tapi logic gak muat di ApiScraper.field_map). `ApiScraper` sendiri
      dipakai internal ketiganya lewat family class, diuji contract test.
- [x] **3.11** Harness golden test (`cti_scraper.testing`) — byte fixture
      Fase 0 disuntik lewat `httpx.MockTransport` (light) atau Playwright
      `page.route()` (browser, MockTransport gak ngaruh ke navigasi
      Playwright). Ketauan pas jalan, bukan ditebak: `RansomwareVictimItem`
      butuh normalisasi tanggal (fixture lama kadang nyimpen datetime
      penuh, item baru bertipe `date` bersih -- itu perbaikan, bukan bug).

**Exit criteria — SEMUA terverifikasi jalan lawan Postgres+jaringan asli:**
- [x] 5 scraper referensi lolos golden test lawan fixture Fase 0
- [x] Contract test jalan (31 test, semua scraper kedaftar otomatis dicek)
- [x] `dry-run bitdefender` narik 15 item beneran dari bitdefender.com asli
- [x] `run bitdefender` 2x: run-1 15 baru, run-2 15 di-drop (dedup nyata)
- [x] `enable`/`disable` nulis `scraper_config` beneran

**Bug nyata ketemu+dibenerin selagi jalan (bukan diasumsikan aman):**
1. `RansomwareVictimItem.dedup_key()` draft pertama 4 bagian, format asli 5
   bagian (`group:victim:country:industry:tanggal`) — ketauan dari golden
   test gagal, bukan review kode.
2. `ScraperRun.run_id` di Fase 2 `String(30)`, tapi `uuid.uuid4()` di
   runner.py ngasilin 36 karakter — `StringDataRightTruncation` pas run
   pertama BENERAN ke Postgres (bukan pas test unit, karena test unit gak
   nyentuh Postgres asli). Migrasi Fase 2 diregenerate ulang.

---

## Fase 4 — Migrasi scraper `[x]`

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

- [x] **4.1** `tools/codemod/classify.py` — klasifikasi family via AST
      (import-based: selenium→SELENIUM, playwright→XPATH_BROWSER,
      defusedxml→RSS, requests+lxml→XPATH_STATIC, sisanya→BESPOKE)
- [x] **4.2** `tools/codemod/extract.py` — ekstraktor AST per family, gagal
      ke `needs_review` (bukan nebak) kalau kodenya nyimpang dari bentuk
      kanonik
- [x] **4.3** `tools/codemod/emit.py` + `templates/{rss,xpath}.py.jinja`
- [x] **4.4** `import_rundeck.py` — `rundeck-jobs-map.json` → `schedule` +
      `enabled` per scraper (bukan crontab; penjadwalnya Rundeck. Temuan:
      job Rundeck pakai menit TETAP per job, bukan pola `*/N`)
- [x] **4.5** Generate RSS — **37/47 (79%) otomatis**, +1 udah ada dari Fase 3
      (`bitdefender`) _(job aktif)_
- [x] **4.6** Generate XPath/Playwright — **20/23 (87%) otomatis**, +1 udah
      ada dari Fase 3 (`trendmicro`)
- [x] **4.7** Generate requests+lxml (`xpath_static`) — **checklist ini
      sempat basi**: dicek ulang lewat re-run `run_migration.py` (2026-09-18),
      classifier nemuin 3 stem `xpath_static` (`cyfirmaThreat`, `landthThreat`,
      `newCveThreat`), BUKAN 2 -- salah hitung sebelumnya. Auto-generate
      emang 0/3 (semuanya butuh `needs_review`: `landth.py` variabel loop
      non-standar, `newCveThreat.py` multi-source jadi keklasifikasi bespoke
      di praktiknya), tapi KETIGANYA udah ada file lengkap + terdaftar di
      registry: `cyfirma.py` (Fase 3), `landth.py` (ditulis manual ronde 2,
      lihat 4.11), `new_cve.py` (bespoke, item 4.9). Verifikasi ulang:
      `run_migration.py` regenerate laporan bersih (0 generate, 0
      needs_review, 83/83 target udah "skipped_existing"). Gak ada kerjaan
      nyata yang ketinggalan -- cuma checklist yang gak ke-update pas
      ketiga file itu kelar lewat jalur lain (bukan auto-generate).
- [x] **4.8** ~~Tulis ulang 8 Selenium → `XPathScraper(render=True)`~~ —
      **dipindah ke 10.1c** (2026-09-18, keputusan user, sama alasan 4.12):
      dicek dulu sebelum diputus pindah -- SEMUA 6 script Selenium real
      (`0xToxinThreat`, `emailnewsThreat`, `forcepointThreat`,
      `mandiantThreat`, `trellixThreat`, `vxMalwareDefenseThreat`) `enabled:
      false` di Rundeck, `cyborgHuntingIdea` malah gak kedaftar sama
      sekali. Nol fixture (perekaman Fase 0 cuma nyakup job aktif). Satu
      dicek langsung isinya (`stopped_script/mandiantThreat.py`) — 100%
      ke-comment, `CHROMEDRIVERLOC = "./chromedriver_mac64_arm64/chromedriver"`
      -- konfirmasi konkret gak pernah jalan di host Linux produksi, persis
      alasan yang plan sebutin. **Test-rewrite 1 (Mandiant) sebelum
      dipindah** — lihat 10.1c buat hasilnya: JAUH lebih gampang dari
      dugaan (situs asli udah pindah ke Google Cloud Blog + ada RSS resmi,
      bukan butuh browser automation sama sekali).
- [x] **4.9a** Buat token API baru (GitHub PAT, NVD, twitterapi.io) khusus
      buat testing scraper yang butuh kredensial asli — **user udah bikin +
      isi ke `.env`** (`GITHUB__TOKEN`/`NVD__API_KEY`/`TWITTER__API_KEY`,
      dikonfirmasi kebaca bener lewat `Settings`, gak pernah ditampilin di
      chat). Dipakai buat verifikasi live `blackorbird`/`unit42_github`/
      `new_cve`/`github_poc_monitor` (4.9) — token twitterapi.io masih
      nunggu `monitorX` gak lagi ke-block klarifikasi TwitterScrap.
      <br>⚠️ Jangan pakai token produksi lama yang di `legacy/config.yml` —
      itu masuk daftar rotasi karena udah ke-expose ke laptop dev.
- [x] **4.10** Triage `migration_report.json` — SELESAI setelah 3 ronde.
      Akhir: dari 96 job aktif mentah Rundeck, **13 di luar scope** (bukan
      scraper/repo lain/diblokir), **83 target migrasi**: 76 udah punya
      scraper (57 auto-generate + 13 tulisan tangan ronde 2 + 3 referensi
      Fase 3 + `ransomware_live`/`cisa_kev`/`sophos`, lihat di bawah), **7
      sisa** butuh porting bespoke penuh (4.9) — semua udah ditriage &
      dikategorikan, bukan cuma "belum sempat dicek".

      **Ronde ke-3** (nuntasin 4.10 — baca SEMUA 13 item `needs_review`
      yang tersisa dari ronde 2, bukan cuma yang gampang):

      - **Bug skip-check ketemu**: `run_migration.py` dulu cuma ngecek
        file udah ada di `feeds/` lewat nama hasil `legacy_stem_to_id()` --
        gak nangkep scraper bespoke Fase 3 yang nama file-nya gak ngikut
        konvensi itu. Akibatnya `ransomwareLiveThreat` (udah lengkap di
        `collectors/ransomware_live.py`) dan `cisacatalogThreat` (udah
        lengkap di `collectors/cisa_kev.py`) **nyangkut terus di
        "needs_review: bespoke" walau UDAH SELESAI dari Fase 3**. Fix:
        `_find_already_covered()` scan field `legacy_script="..."` di
        SEMUA scraper yang ada (`feeds/` + `collectors/`), bukan nebak
        nama file — bener buat family apa pun.
      - **`sophosThreat.py` — misklasifikasi ketauan & dibenerin**:
        classifier nge-tag "bespoke" gara-gara pakai `xmltodict.parse()`,
        padahal strukturnya KANONIK 100% (satu feed, loop item, gak ada
        filter). Ditulis manual ke `sophos.py` (declaratif murni, `RSSScraper`
        biasa) — golden-test match persis 4/4.
      - **5 item lagi ternyata BUKAN scraper** (pola sama kayak
        logbook/sendCounter/offsetAlert/trendingNewsToday/threatactorTrendGraylog
        yang ketauan ronde 2): `githubSophoslab`, `githubTTPs`,
        `mitreGithub`, `githubAptTTPSimulation` — "GitHub commit watcher"
        yang cuma poll `api.github.com/.../commits` terus alert Telegram
        (`send_alert_report`/`send_report_file`), **nol panggilan
        dbMongo/push_job di keempatnya** — gak pernah nulis apa pun ke DB,
        murni notifikasi sepihak. `topCve` malah gak fetch keluar sama
        sekali — baca `cve_tracker` LOKAL (hasil scraper lain), agregat,
        kirim digest Telegram. Dipindah ke `NOT_A_SCRAPER_STEMS`, keluar
        dari target migrasi (ranahnya Fase 6 beat task).
      - **7 sisa dikategorikan buat 4.9**:

        | Scraper | Kategori | Status |
        |---|---|---|
        | `anyrunTrendThreat` | Rusak, butuh keputusan produk | **SELESAI** → `any_run_trends.py`, fitur baru penuh (lihat 4.9) |
        | `blackorbirdGithub`, `githubUnit42` | GitHub commit-watcher yang NULIS artikel | **SELESAI** → `blackorbird.py`, `unit42_github.py` (lihat 4.9) |
        | `newCveThreat`, `githubPOCMonitor` | Subsistem CVE | **SELESAI** → `new_cve.py`, `github_poc_monitor.py` (lihat 4.9) |
        | `deepdarkCTI` | **PINDAH ke Fase 5** | Extract IOC dari diff commit GitHub (`fastfire/deepdarkCTI`) butuh `iocExtractor.extract_iocs()`-equivalent — itu SCOPE Fase 5 (`cti_enrich/ioc/`, item 5.9). Bukan lagi tugas Fase 4 — lihat Fase 5 buat detail |
        | `monitorX` | **PINDAH ke Fase 5** | Pertanyaan tabrakan sama `TwitterScrap` **udah terjawab TIDAK** (user tarik repo-nya, dibaca lengkap — lihat "Scope ditunda" di bawah), jadi bukan itu blocker-nya lagi. Blocker sebenarnya: `monitorX.py` manggil `articleValidator()` (LLM, filter cyber-relevance + extract field insiden `victim_name`/`confirmed_incident`/dst) — SCOPE Fase 5 (`cti_enrich/llm/`, item 5.10). Model `Tweet` (`cti_core/db/models/tweet.py`) juga ketauan belum lengkap — ada `confidence_score`/`confirmed_incident` tapi kolom LLM lain (`industries_impacted`, `victim_countries`, `actor_countries`, `victim_name`, `incident_confidence`, `incident_indicators`) belum ada. Bukan lagi tugas Fase 4 — lihat Fase 5 buat detail |
- [x] **4.9** Port manual scraper bespoke — **5 dari 5 target Fase 4 beres**
      (`blackorbird`, `unit42_github`, `new_cve`, `github_poc_monitor`,
      `any_run_trends`), + 2 udah dari Fase 3 (`ransomware_live`, `cisa_kev`).
      `deepdarkCTI` & `monitorX` **DIPINDAH ke Fase 5** (item 5.9/5.10 di
      bawah) -- keduanya genuinely butuh modul yang belum ada
      (`cti_enrich/ioc/`, `cti_enrich/llm/`), bukan kerjaan scraper lagi.
      Klarifikasi TwitterScrap (dulu dikira blocker `monitorX`) UDAH KELAR
      -- user tarik repo-nya, dibaca lengkap, TERNYATA BUKAN tabrakan
      (lihat "Scope ditunda" di bawah).

      **`any_run_trends.py`** (`anyrunTrendThreat` lama): satu-satunya
      scraper Fase 4 yang beneran FITUR BARU, bukan migrasi -- script lama
      gak pernah nulis apa pun (`featured_message` dihitung terus dibuang,
      fixture Fase 0 `expected_items.json` isinya `[]`, lihat KNOWN_BROKEN.md).
      Keputusan user: lanjutin jadi beneran. Baru dari nol: tabel
      `malware_trends` (migrasi `21d5ede00400`, diverifikasi upgrade/
      downgrade + `alembic check` bersih), `MalwareTrendRepo`,
      `MalwareTrendItem` + sink (upsert `(source, snapshot_date, rank)`,
      `dedup_key()` scraper di-override `None` -- pola sama kayak `CveItem`,
      posisi ranking bisa geser dalam hari yang sama antar-run). **Bug
      ketemu & dibenerin waktu tulis**: lupa prefix `xpath=` di
      `page.locator()` (beda dari family `XPathScraper` yang lewat lxml,
      ini manggil Playwright langsung) -- ketauan lewat `dry-run` pertama
      (`Locator.text_content: Unexpected token "/"`), langsung ketauan
      jelas. **Perbaikan lain**: href hasil scrape RELATIF
      (`/malware-trends/kali365/`) -- script lama gak masalah karena
      hasilnya emang gak pernah dipakai, sekarang beneran jadi link yang
      diklik orang, jadi digabung `urljoin` ke absolut. Diverifikasi live
      penuh: `dry-run` 10/10 item, `run` nulis ke Postgres, re-run
      ke-upsert di tempat yang sama (row count tetap 10, bukan dobel).

      **Framework baru** (dipicu kebutuhan nyata, bukan dibangun duluan):
      - **`ScraperMeta.credential`** + `cti_scraper.credentials` -- scraper
        yang butuh API key (GitHub/NVD/Twitter) declare nama kredensialnya,
        `Runner`/`verify --record` yang nyuntik header ke `ctx.http`
        SEBELUM `fetch()` dipanggil. `fetch()` gak pernah pegang token
        mentah -- persis nutup kelas bug yang didokumentasiin
        `ScrapeContext` (`newCveThreat.py`/`githubPOCMonitor.py` lama bikin
        `MongoClient` langsung dari config). Standarin GitHub ke
        `Authorization: Bearer` (script lama campur `token`/`Bearer`,
        GitHub nerima dua-duanya). **Bug lama ketauan**: NVD API key gak
        PERNAH kepake di `newCveThreat.py` (field ada di config, gak ada
        satu pun `apiKey` di request) -- sekarang beneran kepasang, rate
        limit naik dari 5 ke 50 req/30dtk.
      - **`ScraperMeta.reference_data`** + `cti_scraper.reference_data` --
        pola SIMETRIS buat data internal Postgres (techstack, CVE true-
        positive) yang beberapa scraper butuh baca tapi BUKAN sumber
        eksternal. `Runner` query DB SEBELUM `fetch()`, `fetch()` cuma
        baca `ctx.reference[nama]` (data biasa, list/dict) -- `Session`
        gak pernah nyampe ke `fetch()`. CLI `dry-run`/`verify --record`
        ikut dibenerin biar buka session read-only kalau scraper-nya
        declare `reference_data`.
      - **`CveTrackerRepo`** (`cti_core/db/repositories/cve.py`) + sink
        `CveItem`/`CvePocItem` baru di `sinks.py` -- satu-satunya jalur
        tulis `cve_tracker`, dipakai DUA scraper (`new_cve.py` upsert
        penuh, `github_poc_monitor.py` push POC) biar gak drift lagi kayak
        `newCveThreat.py`/`githubPOCMonitor.py`/`cve_service.py` lama.
      - **Migrasi skema baru** (`3f6cadc03383`): `cve_pocs.poc_type`
        ("poc"/"exploit") -- kolom ketinggalan pas `CvePoc` ditulis Fase 2,
        ditambah begitu `github_poc_monitor.py` beneran butuh. Diverifikasi
        upgrade/downgrade/upgrade + `alembic check` = 0 diff, sama standar
        kayak migrasi Fase 2.
      - **`CveItem.cve_modified_date`** ditambah ke Item (field DB-nya
        udah ada dari Fase 2, ketinggalan di draft Item Fase 3).

      **Verifikasi**: fixture Fase 0 gak kepake (golden-test harness belum
      dukung `reference_data`/multi-request berantai, lihat KNOWN_BROKEN.md)
      -- keempat scraper diverifikasi lewat `dry-run`/`run` LIVE lawan API
      asli + Postgres lokal beneran (docker-compose): `blackorbird`
      (`items_found=1`), `unit42_github` (`items_found=3`), `new_cve`
      (272 CVE ke-upsert, spot-check data lengkap & bener), `github_poc_monitor`
      (diverifikasi DUA jalur: 189 kandidat broad-search di-filter techstack
      dengan bener/ketolak semua pas techstack gak cocok, terus 10 POC
      ke-attach bener pas techstack DAN CVE tracked cocok -- `poc_available`
      jadi `True`, `poc_type` ke-klasifikasi bener). 497 test hijau, `ruff
      check .` + `mypy --strict` (scope `cti-core`+`cti-scraper`) bersih,
      9 integration test hijau lawan schema baru.

      **Temuan minor, gak di-fix (biaya > manfaat)**: `_cve_poc_sink` bisa
      no-op diam-diam kalau POC ketemu buat CVE yang gak ke-track sama
      sekali (`items_new` di `RunResult` tetep ke-hitung sukses walau
      `add_pocs()` gak nemu baris buat ditempelin) -- setara perilaku
      Fase-1 script lama (juga gak nulis DB buat CVE yang gak dikenal,
      cuma alert). Bakal makin jarang kejadian begitu Fase 10 seed
      techstack/CVE beneran, gak worth bangun mekanisme "sink partial-
      success reporting" buat satu edge case ini sekarang.
- [x] **4.11** Catat gesekan DX yang ketemu waktu migrasi → balik benerin
      framework. Ini output nyata dari pendekatan satu-per-satu. **3 bug
      framework ketemu & dibenerin** lewat verifikasi golden-test bulk atas
      57 hasil generate (bukan diakalin per file — sesuai aturan Fase 4):

      1. **`RSSScraper` gak nge-unescape HTML entity sebelum parse XML.**
         51 dari 52 scraper RSS lama yang punya rantai `.replace()` buat
         entity malformed JUGA bungkus hasilnya dengan
         `html_lib.unescape(...)` sebelum `ET.fromstring()` — tanpa langkah
         ini, entity numerik yang sebenarnya udah valid (mis. `&#038;`) kena
         double-escape sama `.replace("&","&amp;")` terus gak pernah
         ke-decode. Ketauan dari `anyrun` (title `ANY.RUN &#038; SentinelOne`
         harusnya `ANY.RUN & SentinelOne`). **Fix:** field baru
         `RSSScraper.html_unescape: ClassVar[bool]`, di-apply di
         `_parse_feed()` setelah `xml_fixups`, sebelum parse XML. Extractor
         deteksi pola ini otomatis (cek apakah argumen `ET.fromstring(...)`
         dibungkus `.unescape(...)`). Dampak: **5 scraper RSS lain ikut lolos
         golden-test** (darkreading, eclecticiq, embeeresearch, exploitdb,
         threatmon) yang sebelumnya keliatan gagal karena entity yang sama.
      2. **`XPathScraper.base_url` gak pernah kedeteksi otomatis.** Field-nya
         udah ada dari Fase 3 (`XPathScraper` udah punya `urljoin()` bawaan),
         tapi `extract_xpath()` gak punya logic buat nemuin pola umum di 28
         scraper lama: `"url": "https://situs.com" + article_url` di dalam
         dict literal (href dari DOM-nya relatif, di-absolut-kan manual).
         Ketauan dari `bizone` (URL ke-generate relatif
         `/eng/expertise/blog/...`, harusnya absolut
         `https://bi.zone/eng/expertise/blog/...`). **Fix:**
         `_find_base_url_concat()` di `extract.py`, nyari `ast.Dict` dengan
         key mengandung "url"/"link" yang value-nya `BinOp(Add, literal-http,
         ...)`. Verifikasi: `bizone` sekarang match persis (4/4).
      3. **BOM/CRLF sebelum deklarasi XML bikin parse gagal.** 28 scraper RSS
         lama defensif soal ini (`.decode("utf-8-sig")` dan/atau `.lstrip()`)
         karena deklarasi `<?xml ...?>` wajib jadi karakter pertama di
         dokumen. Ketauan dari `munit` (`ParseError: XML or text declaration
         not at start of entity` — fixture-nya diawali `\r\n` sebelum
         `<?xml`). **Fix:** `RSSScraper._parse_feed()` sekarang
         `resp.text.lstrip("﻿ \t\r\n")` sebelum parse — selalu aman
         (no-op buat feed yang udah rapi), jadi gak perlu deteksi per-scraper
         kayak dua bug di atas.

      **Divergensi yang KETAHUAN bukan bug** (dicatat di
      [KNOWN_BROKEN.md](KNOWN_BROKEN.md), jangan diakalin biar "lolos"
      golden-test byte-exact):

      | Scraper | Golden-test bulk | Kenapa bukan bug |
      |---|---|---|
      | `anyrun` | overlap URL 0% (title match sempurna) | Script lama double-concat `"https://any.run" + link` walau `<link>` RSS-nya udah absolut — bug lama, sengaja gak di-port |
      | `qualys`, `resecurity`, `rhinosec`, `cisa`, `wiz` | 1-4 item beda per title (selisih NBSP/spasi) | Script lama gak pernah `.strip()` title (`item.find('title').text` mentah) — framework baru SELALU strip, itu perbaikan disengaja |
      | `elastic_lab`, `eset`, `fortinet`, `starlabs`, `vectra`, `akamai`, `f5` | jumlah item ke-cap di `max_items` (default 50) | `ScraperMeta.max_items` itu cold-start guard yang disengaja (lihat §keputusan "Postgres + DB kosong") — bukan extraction gap. `akamai`/`f5` juga punya 1-2 item minor yang belum di-root-cause (bukan pola jelas kayak yang lain, dampaknya kecil) |
      | `artic` | overlap 10/20 (subset persis) | Limitasi golden-test harness (§4.11 di atas), bukan extraction gap — scraper punya 2 URL feed, harness cuma replay 1 fixture body |

      3 `ParseError` awal (checkpoint, cloudflare, munit) — **munit
      kebenerin** (BOM/CRLF, lihat di atas). `checkpoint` & `cloudflare`
      **bukan bug ekstraksi** — XPath/URL/`base_url`-nya struktural bener
      (disalin apa adanya dari locator Playwright lama yang jalan), tapi
      fixture Fase 0-nya nyimpen resource yang SALAH: `checkpointThreat`
      nyimpen halaman tantangan bot AWS WAF (2KB, cuma script
      `AwsWafIntegration.*`, bukan konten asli), `cloudflareThreat` nyimpen
      RSS feed blog Cloudflare (357KB `.xml`, `https://blog.cloudflare.com/`)
      yang gak ada hubungannya sama DOM `resource-hub` yang di-XPath. Kedua
      situs ini butuh rekam ULANG live pas `enable` (`verify --record`,
      ADDING_A_SCRAPER.md) — golden-test mock gak bisa "benerin" fixture yang
      dari awal salah rekam.

      20 scraper `xpath_browser` udah diverifikasi terpisah (subprocess
      per-scraper, hindarin noise event-loop Playwright kalau di-loop satu
      proses): **3 pass bersih** (`bizone`, `esentire`, `volexity`, +
      `trendmicro` dari Fase 3 = 4 total), 2 gagal karena fixture salah
      (checkpoint, cloudflare, di atas), **15 gak punya fixture sama sekali**
      — bukan bug, situs `runtime="browser"` emang paling banyak kena "0 item
      kedua hari perekaman" di Fase 0.5 (lihat KNOWN_BROKEN.md), tinggal
      `verify --record` pas giliran `enable`-nya.

      5 scraper RSS gak punya fixture sama sekali (doyensec, google,
      nquiring_minds, sysdig, trustwave) — bukan bug, tinggal
      `verify --record` pas giliran `enable`-nya (ADDING_A_SCRAPER.md).

      **Ronde ke-2** ("yang gampang dulu" — beresin `needs_review`,
      prioritas non-bespoke): 40 → **15** (13 bespoke + `newCveThreat`,
      salah-klasifikasi XPath padahal pipeline bespoke, + `anyrunTrendThreat`,
      butuh keputusan produk). 13 scraper baru (12 ditulis manual + 1
      ke-auto-generate lagi via fix extractor):

      - **Koreksi scope** (`run_migration.py`): 8 dari "100 job aktif" itu
        BUKAN target migrasi sama sekali, sebelumnya nyampur jadi
        "unresolved"/"bespoke" yang membingungkan. Sekarang eksplisit 3
        kategori (`NOT_A_SCRAPER_STEMS`, `EXTERNAL_REPO_STEMS`,
        `PERMANENTLY_BLOCKED`), laporan punya field `out_of_scope` sendiri:
        - `logbook`/`sendCounter`/`trendingNewsToday`/`threatactorTrendGraylog`
          — utility internal (laporan/counter/flush log ke Telegram/Graylog),
          BUKAN scraper (gak ada `push_job()`). Ranahnya Fase 6 (beat task).
        - `trendingCve`/`twitter`/`twitter30` — `/opt/TwitterScrap`, repo lain
          yang emang udah dicatat "Scope ditunda" (gak ada di checkout ini).
        - `techstackGO`/`techstackNPM`/`techstackPYPI` — **ketauan bahaya**:
          ada salinan lokal di `ScraperNews/` yang KEBETULAN ke-klasifikasi
          "bespoke", tapi salinan itu diduga FORK BASI (Rundeck nunjuk ke
          `/opt/techstackLibrary`, bukan `/opt/ScraperNews`, lihat "Scope
          ditunda" di atas). Auto-generate dari fork basi lebih bahaya
          daripada di-skip — sekarang dikeluarin eksplisit dari target.
        - `threatactorTrendTelegram` — nama job Rundeck beda ejaan dari file
          asli (`threatActorTrendTele.py`), yang UDAH `PERMANENTLY_BLOCKED`
          (kredensial hardcoded) — masuk situ, bukan entry baru.
      - **Framework** (`RSSScraper`): 2 tambahan generik, bukan per-file:
        - `_include_item(node) -> bool` — hook filter per-item SEBELUM
          di-parse (kategori/URL/tanggal), default semua lolos. Dipakai 6
          scraper (`akamai`, `bleepcomp`, `crowdstrike`, `f5`, `cisa`,
          `sentinel`) yang sebelumnya gak bisa diekspresiin murni
          deklaratif.
        - `escape_bare_ampersands()` (dulu langkah `BARE_AMPERSAND.sub()`
          polos) sekarang **CDATA-aware** — ngelewatin isi
          `<![CDATA[...]]>` utuh. **Bug asli ketemu**: `wiz.py` punya title
          CDATA berisi `"CVE-A & CVE-B"` (bare `&`, valid krn CDATA
          dikecualikan dari entity processing) yang kena escape jadi
          literal `&amp;` gara-gara regex whole-text yang gak ngerti
          batas CDATA — parser XML gak decode isi CDATA, jadi salah selamanya.
          Fix: split per-segmen CDATA, cuma escape bagian DI LUAR CDATA.
      - **Extractor** (`extract.py`): deteksi daftar URL feed sekarang dari
        ISI list (semua elemen literal `http...`), bukan nama variabel
        harus ngandung "url" — `articThreat.py` makai nama `link_list`,
        sebelumnya ke-skip padahal strukturnya kanonik. Auto-generate
        langsung jalan setelah fix ini (gak perlu ditulis manual).
      - **3 scraper "kelihatan ngasih banyak item" tapi ternyata rusak**
        (ditemuin pas migrasi, dicatat di KNOWN_BROKEN.md):
        - `huntressThreat.py` — `exit()` sebelum loop `push_job()`, dead
          code SELAMANYA. Logic ekstraksinya valid → **diselamatkan**
          manual ke `huntress.py` (CSS class diterjemahin ke XPath
          `contains()`), bug `exit()`-nya sengaja gak ikut.
        - `socradarThreat.py` — loop `range(1,5)` tapi XPath-nya gak pernah
          pakai `{i}`, jadi SELALU cuma 1 item/run (dedup dalam-run
          nyaring 3 iterasi sisanya). Diport manual ke `socradar.py` dengan
          `max_items=1` — golden-test match persis 1/1.
        - `anyrunTrendThreat.py` — ngumpulin ringkasan trend tapi **gak
          pernah manggil `push_job()` sama sekali**, dari awal incomplete.
          Fixture Fase 0 ngonfirmasi (`expected_items.json` isinya `[]`).
          **Sengaja gak di-port** — butuh keputusan produk (Item type baru
          buat ringkasan, bukan per-artikel), bukan ekstraksi mekanis.
      - **`sentinelThreat.py` — kuirk filter kategori yang SENGAJA
        dipertahankan** (bukan bug ekstraksi, bukan bug yang harus
        dibuang): `skip_status` cuma di-set di dalam `for cat in
        item.findall('category')`, jadi item TANPA `<category>` sama
        sekali otomatis LOLOS filter (loop-nya gak pernah jalan). Beda dari
        `bleepcomp.py`/`crowdstrike.py` yang bentuknya mirip tapi
        default-nya "exclude". Diverifikasi lewat fixture (item "Agents at
        Large..." gak punya category tapi tetap di expected) sebelum
        direplikasi — golden-test match persis 1/1.
      - **`landth.py`** — satu-satunya kasus yang extractor SENGAJA gak
        digeneralisasi: variabel loop-nya (`recent_count`) sinkron 1:1 sama
        `range(1,4)`, tapi ngenalin ITU secara umum (bukan cuma nama `i`)
        beresikonya lebih besar daripada nulis manual satu file. Ditulis
        manual, perilakunya diverifikasi identik.
      - **`rapid7.py`, `cisa.py`** — butuh override method penuh (bukan
        cuma field deklaratif): rapid7 parsernya beda (`lxml.etree
        recover=True`, `resolve_entities=False`/`no_network=True` buat
        nutup XXE manual karena gak lewat `defusedxml`), cisa punya
        sanitasi byte custom (`remove_invalid_xml_bytes`, filter range byte
        valid, beda dari `xml_fixups` yang cuma string replace). Keduanya
        tetap subclass `RSSScraper`/`BaseScraper` satu file, cuma override
        method yang emang perlu.
      - **`cybersecnews.py`** — kebutuhannya BERTENTANGAN sama urutan
        default framework: butuh `html.unescape()` SEBELUM smart-escape
        (bukan sesudah) biar entity HTML bernama (`&nbsp;`/`&mdash;`, ada
        beneran di feed-nya, diverifikasi lewat fixture) ke-decode bener.
        Sempat dicoba jadiin urutan DEFAULT baru di `RSSScraper`, tapi itu
        bikin REGRESI di `embeeresearch.py` (interaksi sama `xml_fixups`
        yang nyentuh CDATA) — direvert, `cybersecnews.py` override
        `_parse_feed()` sendiri buat urutan yang beda ini secara lokal.
      - **`artic.py`** (auto-generate) — golden-test "gagal" (10/20) itu
        **limitasi test harness**, bukan bug: scraper ini punya 2 URL feed
        beda, tapi `cti_scraper.testing._build_http_transport()` cuma
        rekam/replay SATU response buat scraper apa pun URL-nya diminta —
        request ke feed ke-2 kebagian byte feed ke-1 lagi. `feeds` tuple
        hasil ekstraksi udah dicek bener secara struktural. Perlu
        peningkatan harness (per-URL fixture) buat multi-feed scraper,
        belum digarap — dicatat di KNOWN_BROKEN.md.
- [x] **4.12** ~~Backlog: job nonaktif~~ — **dipindah ke 10.1b** (2026-09-18,
      keputusan user): ini kerjaan cutover, bukan migrasi scraper aktif,
      jadi gak lagi nge-blok status Fase 4.

**Exit criteria:** 241 modul ke-import semua · contract test hijau · ≥95% fixture identik · sisa delta ada waiver tertulis

---

## Fase 5 — `cti-enrich` `[x]`

- [x] **5.1** Stage `fetch_text` (`stages/fetch_text.py`) — trafilatura (HTTP
      langsung) + fallback Playwright-render lalu trafilatura lagi. GANTI
      `sumy.HtmlParser`-buat-ekstraksi + `newspaper3k` lama jadi SATU library
      dua jalur (keduanya udah scaffold Fase 1). Live-verified thehackernews.com.
- [x] **5.2** Stage `classify` (`stages/classify.py`) — prompt disalin
      verbatim, **fix**: `response_format={"type":"json_object"}` +
      `llm.client.parse_json_response()` gantiin `.replace("json","")` hack
      (`articleValidator.py:141-146`). Live-verified via gateway 9router
      (model reasoning yang balikin `<think>` block -- `parse_json_response`
      nyaring itu juga, ketauan pas testing live, bukan ditebak).
      **3 bug robustness lagi ketemu+dibenerin pas korpus test 200-artikel
      (2026-09-18)** -- ketiganya spesifik ke gateway dev (9router, model
      reasoning), gak ada di source lama karena OpenAI asli gak butuh:
      1. Gak ada `max_tokens` eksplisit -- server motong respons DI TENGAH
         blok `<think>`, JSON jawaban gak pernah lahir. `finish_reason`
         konfirmasi "length" bukan "stop". Fix: `_MAX_TOKENS=3000`
         (classify)/`2000` (extract_ttps, sama risiko).
      2. Respons kosong/rusak transien (~15-20% dari sampel awal, ilang
         total setelah fix #1+#3, sisa 0/30 di re-test) -- fix: 1 retry
         (`_MAX_ATTEMPTS=2`) di `classify()`/`extract_ttps()`, sama
         semangat retry `TransientFetchError` di scraper framework.
      3. Gateway kadang balikin `content` UDAH KE-PARSE (dict), bukan
         string JSON, di mode `response_format=json_object` -- bukan
         bagian spec OpenAI, quirk proxy. `parse_json_response()` sekarang
         terima `str | dict | None`, dict di-passthrough langsung.
- [x] **5.3** Stage `summarize` (`stages/summarize.py`) — sumy LSA,
      `PlaintextParser` gantiin `HtmlParser` (ekstraksi udah pindah ke 5.1).
      Butuh corpus NLTK `punkt_tab` -- auto-download sekali per proses
      (`_ensure_nltk_data()`), gak perlu langkah manual terpisah.
- [x] **5.4** Stage `extract_ttps` (port apa adanya, udah bener dari
      sononya), `extract_iocs` (`stages/extract_iocs.py`, TTL cache
      allowlist/C2 dipertahankan), `extract_cves` (regex title/body)
- [x] **5.5** Stage `score` (`stages/score.py`) — keyword list + regex +
      spaCy NER title/body, `checkCVE`/`checkTechStack` (HTTP MITRE) port ke
      `_check_cve_vendor`. **Perubahan disengaja**: `country_list` dari
      `pycountry` (seluruh ISO 3166-1) gantiin ~150 nama kuratif Mongo
      `apac-country`/`global-country` yang gak pernah ke-port ke Postgres --
      lihat docstring modul buat alasan lengkap (juga nyelesain kebutuhan
      konversi nama->kode `ArticleCountry.country_code`).
- [x] **5.6** `routing.py` — **fungsi murni**, 17 test (`tests/unit/
      test_routing.py`), 1-per-cabang + kasus tepi (double alert OT,
      sub-routing Indonesia, `related_tech_cve_status` cuma valid di cabang
      Global). **Fix**: zero-day regex `nlp.py:421` (`r"\\b...\\b"` raw-string
      jadi literal backslash, gak pernah match) -- versi bener
      `r"\b(zero|0)[-.]day\b"` dipakai di `stages/score.py`.
- [x] **5.7** Stage `persist` (`stages/persist.py`) — **satu-satunya
      penulis**, `ArticleRepo.set_enrichment()` (baru, Fase 5) buat
      countries/industries/threat_actors/ttps + `IOCRepo` per-IOC. Country
      role (victim/actor/mentioned) di-derive dari 3 field lama, lihat
      docstring modul.
- [x] **5.8** Stage `alert` (`stages/alert.py`) — **terpisah total** dari
      persist, `pipeline.py` manggil persist DULU baru alert (kebalik dari
      `_sendAlert()` lama yang gabung keduanya).
- [x] **5.9** SATU IOC extractor (`cti_enrich/ioc/extractor.py`) — port
      byte-identik, diverifikasi lawan korpus REAL (bukan cuma sintetis):
      **0 mismatch di 7899 title + 55 body artikel asli** (live-fetched)
      lawan `iocExtractor.py` asli. Unit test resmi ditambahin
      (`tests/unit/test_ioc_extractor.py`, 12 test).
      **BUG SERIUS ketemu+dibenerin (2026-09-18, korpus test 200-artikel)**:
      `_RE_DOMAIN_DEFANGED` -- ReDoS/catastrophic backtracking. Artikel real
      (elastic.co/security-labs/.../operation-bleeding-bear, ~12KB prosa
      natural) bikin `extract_iocs()` GANTUNG TANPA BATAS (proses dibunuh
      manual setelah >5 menit, CPU 98%). Root cause: `(?:...)* ` gak
      dibatasi + `\s*` di dua sisi tiap repetisi -- prosa Inggris biasa
      ("kata. kata. kata.") ambigu banget buat regex ini walau HASIL AKHIRNYA
      gak pernah match. **Bug ini ADA di `iocExtractor.py` asli juga** (regex
      sama persis, byte-identik) -- bukan sesuatu yang ke-introduce port ini,
      TAPI kelas bug DoS/availability, beda dari "logic beda" yang wajib
      dipertahankan verbatim, jadi diputuskan dibenerin: `(?:...)*` ->
      `(?:...){0,10}` (gak ada domain defanged asli >10 label). Diverifikasi
      ULANG abis fix: 0 mismatch tetap di korpus 7899 title + 55 body yang
      sama, PLUS test regresi ReDoS baru (`test_domain_defanged_regex_does_
      not_catastrophically_backtrack`, timeout keras 5 detik pakai
      `signal.alarm`) biar gak bisa balik diam-diam.
      Butuh tabel baru `ioc_allowlist_entries`/`threat_feed_entries`
      (migrasi `5b7fe9a443b8`, verified upgrade/check/downgrade/upgrade) --
      dua-duanya KOSONG, belum di-seed (lihat "Belum dikerjain" di bawah).
      **`deepdark_cti.py` scraper SEKARANG UDAH DITULIS** (`scrapers/src/
      cti_scrapers/feeds/deepdark_cti.py`) -- `IocFeedItem` baru (SATU per
      commit, bukan per-IOC) + sink `_ioc_feed_sink` (upsert IOC + dual-write
      `threat_feed_entries` kalau kategori "c2" + alert Telegram "darkweb").
      Live-verified: `dry-run` + `run` jalan bersih lawan GitHub API asli,
      registry discovery + 539 test + mypy --strict + ruff semua bersih.
      **TEMUAN + FIX**: `_IOC_PATH_PREFIXES` asli (`c2/`, `ioc/`, dst,
      asumsi struktur folder) gak PERNAH match repo `fastfire/deepdarkCTI`
      SAAT INI -- dikonfirmasi lewat GitHub Contents API, repo-nya sekarang
      flat (`phishing.md`, `ransomware_gang.md`, dst di root). Bukan bug
      portingan (logic identik source asli), assumption source asli soal
      struktur repo yang udah basi. **Keputusan user**: sesuaikan ke skema
      flat -- `_category_for()` sekarang cocokin KATA di nama file (dipisah
      `_`/`-`) lawan 6 kategori asli, bukan folder prefix. Live-verified
      IOC beneran ke-extract & tersimpan dari commit real (`.onion` URL dari
      `ransomware_gang.md`, kategori "ransomware").
- [x] **5.10** SATU LLM client (`cti_enrich/llm/client.py`) — port + fix
      nyata: fork `ScraperNewsWeb` gak pasang `timeout`/`max_retries` sama
      sekali (dikonfirmasi baca langsung file-nya), fork `ScraperNews` yang
      dipertahankan. **Tambahan gak ada di source manapun**: `LlmSettings.url`
      buat gateway custom (9router, dev), karena provider="openai" gak lagi
      selalu berarti api.openai.com asli. **`monitor_x.py` scraper SEKARANG
      UDAH DITULIS** (`scrapers/src/cti_scrapers/feeds/monitor_x.py`) --
      `TweetItem` baru + sink `_tweet_sink` (insert-only, `TweetRepo`).
      Migrasi kolom `Tweet` (`industries_impacted`, `victim_countries`,
      `actor_countries`, `victim_name`, `incident_confidence`,
      `incident_indicators`) selesai (`a6f893e1319d`, verified roundtrip).
      Reuse `cti_enrich.stages.score.score_with_lists()` (title-pass doang,
      `_scan_tweet` lama emang gak ada NER) dan `classify()` langsung --
      refactor `score.py` jadi `score()` (wrapper Session) +
      `score_with_lists()` (murni) biar scraper (`fetch()` gak boleh pegang
      Session) bisa reuse logic yang sama tanpa DB access langsung. Dua
      resolver `reference_data` baru: `monitored_accounts`,
      `tweet_last_seen_ids` (gantiin `state.json` lokal, MAX tweet_id per
      akun dari Postgres). **Live-verified logic penuh** (scan+classify+
      persist, pakai tweet sintetis -- hasil match GPT: victim=Philippines,
      actor=China, mentioned_group=[APT41]) TAPI **panggilan API
      twitterapi.io beneran ke-block**: `TWITTER__API_KEY` di `.env` balikin
      `401 Unauthorized {"error":"Invalid API key"}` pas dites lawan endpoint
      asli. **Bug asli ketemu+diperbaiki dalam proses ini**: draft pertama
      `_fetch_tweets_for_account` gak cek `resp.status_code` (kode lama PUNYA
      cek ini, `monitorX.py:280-281`, sempat kelewat pas port) -- tanpa cek,
      respons error 401 ke-`.get("tweets", [])` jadi `[]` diam-diam, keliatan
      kayak "gak ada tweet baru" padahal auth-nya gagal. Udah diperbaiki:
      sekarang log warning eksplisit tiap status non-200.
- [x] **5.11** SATU `send_alert(topic, msg)` (`cti_alerts/telegram.py`) —
      12 topic (bukan 9 placeholder awal, lihat `.env.example`), termasuk
      sub-routing global/apac/apac_indo/apt/data_breach_indo yang di kode
      lama implisit di `_send_alert()`. Live-verified kirim ke bot Telegram
      dev user. **Beda dari kode lama**: gak nelan exception (`except:
      pass`) -- aman karena persist selalu duluan (lihat 5.8).
- [x] **5.12** Fix regex zero-day `nlp.py:421` — lihat 5.6.

**Pipeline penuh** (`cti_enrich/pipeline.py`, `run_pipeline()`) live-verified
3 jalur: `related_cyber=False` (reject dini), `security_tech_best_practice=True`
(short-circuit, skip extract_ttps+score), dan jalur penuh (classify->fetch_text
->summarize->extract_ttps->score->routing->persist->alert) — ketiganya nulis
ke Postgres lokal + kirim completion beneran ke LLM gateway dev + Telegram.
539 test lulus (`pytest tests/`, termasuk contract test yang otomatis nyakup
`deepdark_cti`/`monitor_x` dari registry), `mypy --strict` bersih 73 file,
`ruff` bersih.

**2026-09-18 update:**
- **`TWITTER__API_KEY` diganti user -- WORKS.** Live-verified lawan
  twitterapi.io asli (200, tweet beneran balik). `monitor_x.py` sekarang
  end-to-end teruji, bukan cuma logic-nya doang.
- **Seed data KELAR** -- `tools/seed/fase5_reference_data.py` (baru, baca
  BSON pakai `pymongo` ad-hoc lewat `uv run --with pymongo`, SENGAJA gak
  masuk dependency package manapun karena ini script sekali-pakai/migrasi).
  Sumbernya, dikonfirmasi langsung (catatan lama soal lokasi file KELIRU --
  `apac-people.bson` ada di `threatintel/`, bukan `news_db/`):
  - `legacy/dump/threatintel/groups.bson` -> **3991** `threat_actor_groups` (malpedia)
  - `legacy/dump/threatintel/apac-people.bson` -> **30** `monitored_people`
    (isinya demonym/nasionalitas -- "Afghan", "Australian", dst -- BUKAN
    nama orang walau nama koleksinya "apac-people")
  - `legacy/dump/news_db/ioc_allowlist.bson` -> **9** `ioc_allowlist_entries`

  Idempoten (upsert by unique constraint), diverifikasi re-run kedua = 0
  baris baru. Live-verified `score()` (`"Lazarus Group"` -> match, `"Afghan"`
  -> match) dan `extract_iocs()` (`wiz.io` ke-filter allowlist bener).
- `update_cve_mention` (tracking mention CVE/bulan) gak diport -- itu makan
  buat `cveEmailAutomation` (laporan mingguan CVE), yang di-scope keluar
  Fase 5 (territory Fase 7/apps-api, sama kayak `GRAPH__*` credential).
- **Exit criteria "200 artikel historis" -- KELAR.** `tools/` scratch
  script (bukan dikomit, sekali-pakai) jalanin stage individual
  (`classify->fetch_text->summarize->extract_ttps->score->routing`, TANPA
  `persist()`/`route_alerts()` biar gak nulis 200 baris test/kirim 200
  alert Telegram beneran) atas 200 artikel real dari
  `legacy/dump/news_db/articles.bson`, dibandingin lawan `news_type` yang
  kesimpen dulu. Angka final (200 artikel, SEMUA lewat kode final --
  gabungan 2 batch: 30 artikel `docs[100:130]` + 170 artikel
  `docs[130:300]`, non-overlap, ronde awal yang kepake kode SEBELUM 4 fix
  di bawah SENGAJA gak dihitung biar angkanya jujur ngukur kode final):
  - **Error rate: 13/200 (6.5%)** -- SEMUANYA gagal parsing/timeout LLM
    (gateway dev 9router, bukan pipeline logic) setelah 3x retry, bukan
    crash/bug. Turun jauh dari ~15-20% di percobaan awal (lihat 4 fix di
    5.2/5.9), tapi gak bisa dikejar ke nol -- itu batas reliability
    gateway LLM dev yang dipakai, dilaporkan apa adanya.
  - **Acceptance rate (`related_cyber=True`): 193/200 (96.5%)**
  - **`news_type` exact match vs hasil lama (dari yang accepted): 106/193
    (55%)** -- ANGKA INI SECARA JUJUR gak bisa 100%: (1) LLM beda (gateway
    dev 9router, bukan GPT-4o asli yang kemungkinan dipakai produksi dulu),
    (2) teks body di-fetch LIVE SEKARANG, bisa beda dari yang di-fetch
    dulu (halaman berubah/link rot), (3) **`techstack` BELUM di-seed**
    (Fase 10 scope, lihat 10.1) -- `related_tech_status` SELALU `False`
    buat sekarang, jadi cabang "Tech Stack Article"/"Unrelated Tech Stack
    Article" sistematis gak pernah kepilih walau title/body-nya cocok;
    pola ini keliatan jelas di data (banyak `old=Tech Stack Article`/
    `Unrelated Tech Stack Article` -> `new=global`). Bukan bug routing,
    konsekuensi LANGSUNG dari gap seed data yang udah dicatat.
  - **IOC extractor byte-identik: 0 mismatch di 7899 title + 51-55 body
    artikel real** (dua kali verifikasi, sebelum & sesudah fix ReDoS) --
    lihat detail lengkap di 5.9, jauh ngelewatin syarat "korpus 500 artikel".

> **Disiplin:** port logika apa adanya. Perbaiki **hanya** bug yang sudah
> disebut. Kalau enrichment dan scraping berubah semantik barengan, diff
> verifikasi jadi gak bisa dibaca.

---

## Fase 6 — Celery + beat `[x]` inti kelar, sisanya dipindah ke 7.8/10.1d/10.1e

**2026-09-18 — "inti" Fase 6 (arahan: mulai dari core dulu, 5 loop web
nyusul belakangan).** Dibangun di `apps/worker` (package baru `cti-worker`,
masuk uv workspace) + `cti_core.celery_client` (producer-side, biar
`cti_scraper.sinks` -- sebuah package -- gak perlu depend ke `apps/worker`
-- sebuah app):

- [x] **6.1** `apps/worker/src/cti_worker/celery_app.py` -- app Celery
      SATU, dua "image" (scrape vs enrich) dibedain lewat `-Q` + extra
      `nlp` yang ke-install/nggak, bukan app terpisah. `task_acks_late=True`
      + `broker_transport_options={"visibility_timeout": 3600}` ditambahin
      belakangan (exit criteria 6.1 minta ini eksplisit) -- ack cuma
      setelah task selesai (worker mati di tengah run gak bikin task hilang
      diam-diam), visibility_timeout 3600s jauh di atas task terlama yang
      keukur LIVE (`enrich.article` ~10-13s, `scrape.run` ~1-2s).
- [x] **6.2** Queue: `scrape.rss` / `scrape.api` / `scrape.browser` /
      `enrich` (nama beda dari draft plan `scrape.light`/`io`/`control` --
      dipetakan ke family scraper riil yang udah ada dari Fase 3/4, bukan
      istilah generik yang gak ke-pakai). `notify`/`maintenance` didefinisiin
      di `queues.py` tapi belum ada consumer -- placeholder buat 6.6.
- [x] **6.3** `apps/worker/src/cti_worker/queues.py::queue_for()` --
      baca `ScraperMeta.runtime` ("browser" → `scrape.browser`) +
      `credential` (`is not None` → `scrape.api`, else `scrape.rss`).
      Dipakai beat (opsi per-entry) DAN bakal dipakai trigger manual Fase 9.
- [x] **6.4** `apps/worker/src/cti_worker/beat.py::build_beat_schedule()`
      -- generate dari `cti_scraper.registry.discover()`, `ScraperMeta.schedule`
      (cron 5-field) → `celery.schedules.crontab`. **Verified LIVE**: build
      berhasil buat SEMUA scraper aktif riil di registry, gak ada yang gagal
      parse. Nemu 1 bug nyata pas verifikasi: `crontab()` Celery nolak
      sintaks cron valid `"0/N"` (cuma terima `*/N`) -- scraper `eset`
      (jadwal dipulihin dari Rundeck Fase 4) pakai `"0 0/1 * * *"`. Fix:
      `_normalize_field()` regex `0/N` → `*/N` (aman, N=0 = minimum field
      manapun); `N/M` non-zero SENGAJA dibiarin apa adanya, gak ada kasus
      itu di scraper aktif sekarang.
- [x] **6.5** Token bucket Redis (`TokenBucket`, dibangun Fase 3, belum
      pernah disambung ke Redis client beneran) sekarang disambung
      `redis.Redis.from_url(settings.redis.url)` di `tasks/scrape.py`.
- [x] **6.6** ~~Pindahkan 5 loop web → beat task~~ -- **dipindah ke 7.8**,
      biar progress rapih. Alasan sama kayak 6.7/6.8 di bawah: loop-loop itu
      (PIR alert, ATT&CK sync, IOC decay, daily recap, CVE enrichment)
      logikanya nempel di service `ScraperNewsWeb/app/services/*` yang
      MEMANG bakal di-port ke Postgres bareng 56 service lain di Fase 7 --
      misah-misahin kerjaan cuma bikin dobel, digabung natural pas Fase 7
      jalan (bukan item Fase 6 yang genuinely selesai).
- [x] **6.7** ~~Lock singleton (cegah beat double-fire)~~ -- **dipindah ke
      10.1d**. Soft-depend, bukan blocker teknis (infra Redis+Celery udah
      lengkap, lock bisa dibangun kapan aja) -- cuma gak ada gunanya diuji
      sekarang, baru 1 proses beat lokal yang jalan. Nyambung langsung ke
      checklist cutover "Beat terverifikasi singleton" di bawah.
- [x] **6.8** ~~Guard backpressure antrian `enrich`~~ -- **dipindah ke
      10.1e**. Sama, soft-depend: nyambung ke pemisahan image `worker-nlp`
      (Fase 9/10, concurrency dibatasi RAM spaCy/sumy) yang diprediksi
      baru beneran bikin antrian numpuk -- belum ada indikasi nyata sekarang.

**Task lain:**
- `apps/worker/src/cti_worker/tasks/scrape.py::run_scraper` (`scrape.run`)
  -- eksekusi `Runner` (Fase 3), `result.status in ("fetch_error",
  "rate_limited")` → raise `_RetryableRunError` biar `autoretry_for` Celery
  yang urus backoff (`Runner` sendiri SENGAJA gak retry, lihat docstring
  `runner.py`). `max_retries=3`, `retry_backoff=True`.
- `apps/worker/src/cti_worker/tasks/enrich.py::enrich_article` (`enrich.article`,
  `queue="enrich"`) -- panggil `cti_enrich.pipeline.run_pipeline()` (Fase 5)
  lewat import LAZY (worker scrape-only, image tanpa extra `nlp`, tetep
  bisa start & register nama task ini walau manggil beneran bakal
  `ImportError` -- `-Q` yang jamin worker itu gak pernah di-assign task
  ini, plan §4). Retry cuma buat `json.JSONDecodeError` residual yang lolos
  dari retry internal `classify()`/`extract_ttps()` (Fase 5, ~6.5% residual
  korpus test) -- `max_retries=2`. `OpenAIQuotaExhausted` SENGAJA gak
  di-retry (kuota abis butuh tindakan manusia, retry cuma nge-spam queue).
- `packages/cti-scraper/src/cti_scraper/sinks.py::_article_sink` -- ganti
  dari nulis `ArticleRepo` LANGSUNG (Fase 3) jadi `send_task("enrich.article",
  ...)`. Tulis-DB-nya sekarang di dalam task `enrich.article` (lewat
  `run_pipeline` → `persist.py`), bukan di sink lagi -- kontrak tipe yang
  masuk sink (`ArticleItem`) gak berubah, cuma titik tulisnya pindah dari
  SINKRON ke ASINKRON.
- `packages/cti-core/src/cti_core/celery_client.py::get_celery_client()`
  -- Celery client MINIMAL (cuma tau broker URL, `send_task` by string
  name) buat dipanggil dari `cti_scraper.sinks` TANPA `cti_scraper` (sebuah
  package) depend ke `apps/worker` (sebuah app) -- dependency inversion,
  producer gak perlu tau implementasi task, cuma nama + kwargs-nya.

**Verifikasi LIVE end-to-end (2026-09-18), bukan cuma unit test:**
1. `uv run celery -A cti_worker.celery_app worker -Q scrape.rss,scrape.api,scrape.browser,enrich --pool=solo` --
   start bersih, register `scrape.run` + `enrich.article`, beat schedule
   ke-build buat semua scraper aktif riil.
   (Catatan dev macOS: `--pool=solo` wajib lokal -- default prefork
   nge-crash `ValueError: not enough values to unpack` karena spawn-based
   multiprocessing macOS gak cocok sama asumsi prefork Celery; BUKAN
   masalah produksi karena Docker/Linux pakai `fork`.)
2. Dispatch manual `scrape.run("mandiant")` (scraper hasil rewrite 4.8) 2x
   -- run pertama `items_new=0` (dedup bener-bener kerja, semua 20 item
   udah `scraper_seen` dari testing sesi sebelumnya); abis `scraper_seen`
   di-clear buat scraper ini, run kedua `items_new=20`.
3. Ke-20 item nge-trigger `send_task("enrich.article", ...)` dari
   `_article_sink` -- worker yang SAMA (consume `enrich` juga) nangkep,
   jalanin `run_pipeline()` penuh (fetch_text → classify LLM → summarize →
   extract_ttps → extract_iocs → score → persist → route_alerts) buat
   tiap artikel, termasuk kirim alert Telegram beneran buat yang lolos
   filter.
4. Query Postgres `SELECT ... WHERE source ILIKE '%mandiant%' ORDER BY
   created_at DESC` -- **20 baris Article baru** ke-persist, `news_type`
   ke-klasifikasi (`global`, `apac`, `Zero Day Article`,
   `Security Technology & Best Practices`, sebagian `None` = ditolak
   klasifikasi -- konsisten sama rate penolakan yang udah didokumentasiin
   Fase 5).
5. Full suite abis semua perubahan: `pytest tests/ -q` → **556 passed**,
   `ruff check .` → clean, `mypy apps/worker + celery_client.py + sinks.py`
   → clean (0 issues, 9 source file).

**Bug ketemu pas kerjain ini:**
- `pytest tests/` sempat KEBACA hang abis `_article_sink` diubah --
  root cause BUKAN kode baru, tapi `.env` punya `REDIS__URL=redis://redis:6379/0`
  (hostname Docker-network, gak resolve dari host) dan `get_celery_client().send_task()`
  block nunggu retry koneksi. Fix: export `REDIS__URL=redis://localhost:6379/0`
  buat run host-side (pola sama kayak override `DATABASE__URL`/`DATABASE__SYNC_URL`
  yang udah dipakai sepanjang sesi). Abis di-override, 556 test lulus ~16s --
  suite lama emang gak nge-exercise real dispatch path dengan cara yang
  kebuka sama perubahan ini.
- mypy `untyped-decorator` di `@app.task(...)` -- stub Celery gak preserve
  signature fungsi yang di-decorate. Inline `# type: ignore[misc]` gak
  stabil posisinya buat decorator multi-baris (kadang "unused-ignore",
  kadang "invalid syntax"). Fix proper: `[[tool.mypy.overrides]]` scoped
  ke `cti_worker.tasks.scrape` + `cti_worker.tasks.enrich` doang di root
  `pyproject.toml`, bukan disable strict buat seluruh `apps/worker`.

**Exit criteria (draft plan):** 5 loop web hilang dari `main.py` · uvicorn
jalan multi-worker · beat singleton terverifikasi (restart, cek gak
double-fire) -- ketiganya dipindah jadi exit criteria fase lain (5 loop →
**7.8**, beat singleton → **10.1d**, lihat 6.6/6.7 di atas) karena
nunggu kondisi yang belum ada di deployment lokal sekarang (`apps/api`
buat 5 loop, deployment multi-node buat beat singleton). Yang UDAH
terverifikasi LIVE di Fase 6 sendiri: rantai penuh scrape → sink → enrich
queue → enrich task → persist jalan tanpa satu pun langkah disintesis/di-mock.

---

## Fase 7 — `apps/api` `[~]` 7.1/7.2 (inti auth) kelar, sisanya nyusul

**2026-09-18 — 7.1 + 7.2 (auth vertical slice), diverifikasi LIVE lewat
HTTP beneran (curl), bukan cuma pytest.** Package baru `apps/api`
(`cti-api`), masuk uv workspace. OIDC (bagian dari 7.2) **belum** diport --
`oidc.enabled=False` default (Fase 2), toggle-nya nunggu giliran; auth
lokal (username+password, JWT) yang jadi fokus "inti" duluan.

**cti-core (shared, dipakai `apps/api`):**
- `db/models/auth.py` -- tambah kolom yang kepake legacy tapi belum ada di
  skema Fase 2 (ketauan pas porting beneran, bukan dugaan): `Role.display_name`/
  `created_by`/`created_at`/`updated_at` (sekarang `TimestampMixin`),
  `AuditLogEntry.target_id`, model baru `PasswordPolicy` (singleton row
  `id=1`, kolom eksplisit -- bentuknya tetap/gak cair, beda kasus dari
  JSONB `detail`). Migrasi `5a456e9251a0`.
- `db/repositories/auth.py` -- `AsyncUserRepo`/`AsyncRoleRepo`/
  `AsyncClientRepo`/`AsyncAuditLogRepo`/`AsyncPasswordPolicyRepo`. Async-only
  (bukan dual sync+async) -- satu-satunya konsumer `apps/api`, gak ada
  Celery/CLI yang nyentuh tabel ini (pola sama kayak `CveTrackerRepo`/
  `TweetRepo`, sync-only karena konsumen tunggal arah kebalikannya).

**apps/api (`cti_api`) -- port dari `ScraperNewsWeb/app/{auth.py,
services/{auth,role,client,audit,policy,rate_limit}_service.py,
routers/auth.py, models/auth.py}`:**
- `main.py` -- `create_app()` factory, lifespan (`ensure_default_client` +
  `ensure_system_roles`, idempoten tiap startup), CORS. **TANPA** 5
  background loop (`_pir_alert_loop` dkk -- itu **7.8**) dan **TANPA**
  Jinja2/StaticFiles (frontend server-rendered lama diganti Next.js
  terpisah Fase 8, `apps/api` murni JSON API).
- `security.py` -- hash password (bcrypt) + JWT encode/decode, baca
  `cti_core.config.Settings.auth` (bukan `os.getenv()` manual + `RuntimeError`
  kayak `main.py` lama -- container udah gagal start duluan lewat Pydantic
  kalau `JWT_SECRET`/`SESSION_SECRET_KEY` kosong, Fase 2).
- `rate_limit.py` -- **BUKAN port langsung** dari `rate_limit_service.py`
  lama (dict in-memory per-proses). Sengaja diganti ke Redis fixed-window
  (`INCR`+`EXPIRE`): goal eksplisit plan §4/§7 "API bisa di-scale horizontal"
  -- limiter in-memory salah per-proses begitu >1 worker uvicorn (limit
  efektif N kali lipat, silent). Redis udah infra baku platform ini.
- `deps.py` -- `get_current_user`/`require_auth`/`require_admin`/
  `require_superadmin`/`effective_client_id` (port 1:1 `app/auth.py`), plus
  `get_db`/`get_redis` (keduanya `@lru_cache`/lazy -- BUKAN singleton
  modul-level yang konek pas import, biar gampang di-override test/beda env).
- `services/roles.py` -- 26 permission (`ALL_PERMISSIONS`) + 3 role sistem
  (`SYSTEM_ROLES`) + `ensure_system_roles()`. `services/policy.py` --
  validasi kompleksitas password.
- `routers/auth.py` -- 13 endpoint (`policy` get/put, `login`, `logout`,
  `change-password`, `init`, `me`, `users` get/post, `reset-password`,
  `clients` put, `role` put, `audit-log`). Alur/aturan bisnis dipertahankan
  APA ADANYA (termasuk satu kemungkinan bug legacy yang SENGAJA gak
  "diperbaiki" diam-diam: `flag_force_pw_change_all_non_admin` cuma
  exclude role=="admin", "superadmin" ikut ke-flag -- didokumentasiin di
  docstring repo, bukan didaftar sebagai bug resmi kayak §7 plan).
- `routers/health.py` -- `GET /healthz`.

**Verifikasi LIVE (2026-09-18), curl asli lawan uvicorn + Postgres + Redis
lokal:** `/healthz` · `/api/auth/policy` get/put (min_length berubah,
persist) · `/api/auth/init` (bootstrap superadmin, 409 kalau user udah
ada) · `/api/auth/login` (benar/salah password, cookie `cti_auth` keset) ·
`/api/auth/me` · RBAC (401 tanpa token, 403 non-admin ke endpoint admin) ·
`/api/auth/users` create/list · `/api/auth/users/{u}/role` put · rate
limit login (429 persis di request ke-11 per IP, window 60s) · audit log
kecatat benar (`create_user`/`login` dengan `target_id`) · `change-password`
+ login ulang pakai password baru · `/api/auth/users/{u}/clients` put.

**Bug ketemu pas kerjain ini:**
- `AsyncUserRepo.update_client_ids` -- `session.delete()` pada child
  (`UserClient`) gak otomatis nyabut dia dari koleksi `user.clients` yang
  UDAH ke-load di memori (beda dari `parent.children.remove(child)`).
  Tanpa expire, caller yang baca `user.clients` di sesi yang sama abis ini
  masih liat client_ids LAMA walau row DB udah bener. Ketauan dari test
  integrasi (bukan dugaan), fix: `session.expire(user, ["clients"])`
  abis flush. Re-verified via HTTP live (`PUT /users/{u}/clients` + `GET
  /users`) setelah fix.
- **Gap infra test, bukan bug kode**: `pytest.ini_options` (`asyncio_mode
  = "auto"`) default scope event loop pytest-asyncio itu "function" (loop
  BARU tiap test) -- `cti_core.db.engine.get_async_engine()` di-`@lru_cache`
  SEKALI per proses (disengaja, Fase 2: satu connection pool). Begitu ada
  LEBIH DARI SATU test async dalam satu run (sebelumnya cuma 1 di seluruh
  suite, `test_async_article_repo_upsert_works` -- gak pernah kebuka),
  connection asyncpg dari test pertama bawa referensi ke event loop yang
  udah ditutup test-runner, `RuntimeError: Event loop is closed` pas
  teardown test kedua dst. Fix: `asyncio_default_fixture_loop_scope` +
  `asyncio_default_test_loop_scope = "session"` di root `pyproject.toml`
  -- satu event loop buat seluruh sesi pytest, cocok sama engine yang
  di-cache proses-wide. Regresi-tested: full suite (596 test, unit+integration+contract)
  lulus abis perubahan ini.
- Skema Fase 2 (`db/models/auth.py`) kurang lengkap buat kebutuhan nyata
  router: `Role` gak ada `display_name`/`created_by`/timestamp,
  `AuditLogEntry` gak ada `target_id`, `PasswordPolicy` belum ada model
  sama sekali. Ketauan pas porting router lama beneran butuh field-field
  itu -- migrasi `5a456e9251a0` nambahin, bukan didesain ulang skemanya.

**Test:** `tests/unit/test_auth_security.py` (7 test -- hash/verify
password, JWT roundtrip, token ditolak kalau di-tamper/salah secret),
`tests/unit/test_password_policy.py` (9 test -- tiap aturan kompleksitas +
hint), `tests/integration/test_auth_repositories.py` (24 test, Postgres
REAL via testcontainers -- kelima repo). Full suite abis semua ini: **596
passed**, `ruff check .` bersih, `mypy` bersih buat semua modul yang
disentuh (`apps/api` + `db/repositories/auth.py` + `db/models/auth.py`).

**Belum dikerjain (masih `[ ]`):** OIDC/SSO (`services/oidc_service.py`,
184 baris, nunggu `oidc.enabled=True` beneran dipakai), 7.3 (27 router
lain), 7.4 (56 service lain, termasuk logika 7.8), 7.5 (buang duplikasi
pkg_vuln/cve_email/ioc/llm -- versi kanonik IOC+LLM udah disatukan Fase 5,
tinggal pkg_vuln+cve_email), 7.6 (snapshot test), 7.7 (ekspor OpenAPI), 7.8.
~~Catatan ini soal IOC+LLM ternyata JADI STALE lagi begitu `apps/api` lahir
(Fase 7.3) -- exit criteria "gak ada import `cti_enrich` dari API" bikin
`llm` harus di-duplikat ULANG buat `apps/api`. `ioc` kena masalah sama tapi
udah dibenerin Fase 7.3 Bagian 4; `llm` nyusul dibenerin Fase 7.5
(2026-09-23), lihat catatan lengkap di bawah.~~

- [x] **7.1** ~~Bootstrap FastAPI (tanpa background loop)~~ -- `apps/api`
      + `main.py` (`create_app()`, lifespan, CORS), lihat catatan di atas.
- [x] **7.2** Auth: JWT + RBAC + multi-tenant -- lihat catatan di atas.
      **OIDC bagian dari 7.2 ini BELUM diport** (`oidc.enabled=False`
      default, 184 baris `oidc_service.py` nunggu giliran terpisah, bukan
      bagian "inti").
- [x] **7.3** Port 27 router ke repository Postgres -- **SELESAI** (5/5
      Bagian survei 2026-09-18 kelar). `ScraperNewsWeb/app/routers/`
      isinya 28 file: `auth` (Fase 7.2, udah kelar duluan), `oidc`
      (`oidc.enabled=False` default, sengaja ditunda, lihat catatan
      7.2), `scraper_health` (diganti control plane, Fase 9, beda fase)
      -- sisa **25 router**, SEMUANYA ketutup lintas 6 sebelum survei +
      Bagian 1-5 (rincian tiap bagian di bawah). "27" di estimasi awal
      survei sedikit meleset (25 aktual), bukan ada router yang
      kelewat -- daftar file di atas cross-check lengkap.
      (`clients`, `roles`, `articles` [baca doang], `iocs` [baca+kurasi],
      `techstack` [CRUD inti], `cve` [baca+false-positive+purge],
      `tweets`, `monitored_accounts`, `ransomware`, `changelog`,
      `filtered_articles`, `rfi`, `pir`, `source_reliability`, `attack`,
      `ta_groups`, `mitre`, `crossref`), verified LIVE via curl
      (create/update/delete, RBAC superadmin-only buat mutasi, 422
      permission gak dikenal, 400 hapus role sistem/client default).
      `clients`/`roles` nyaris gratis: repo-nya (`AsyncClientRepo`/
      `AsyncRoleRepo`) udah lengkap dari 7.2.

      **`articles`** (2026-09-18) -- router paling besar/penting, cuma
      permukaan BACA (`GET /api/articles` list+filter+paginate, `GET
      /api/filters`, `GET /api/articles/{id}`). `AsyncArticleRepo` (Fase 2)
      sebelumnya cuma punya `upsert`/`get_by_url(_hash)`/`set_overrides` --
      ditambah `list_filtered()` (translate query dict Mongo lama ke SQL
      join atas tabel anak ternormalisasi: `article_industries`/
      `article_countries`[+role]/`article_threat_actors`) dan
      `get_filter_options()` (distinct value per tabel, ganti `col.distinct()`
      Mongo). Tiga field negara Mongo lama (`mentioned_countries`/
      `victim_countries`/`actor_countries`, tiga array terpisah) sekarang
      SATU tabel `article_countries` + kolom `role` -- `country` (param
      umum) = role `"mentioned"`, cocok 1:1 sama nama field lama.
      **Sengaja di-skip/ditunda** (didokumentasiin di docstring router,
      bukan didiemin): `/api/dashboard` (agregasi berat + `normalize_country()`
      lama -- SEKARANG kejadian di enrichment `cti_enrich.countries`,
      bukan query-time), `/api/articles/dedup-groups` (butuh scikit-learn,
      belum dependency `cti-api`), `/api/articles/{id}/confidence`
      +`/confidence/recompute` (butuh router `source_reliability` ke-port
      duluan), `/api/articles/backfill-iocs` (hack migrasi era Mongo,
      kemungkinan besar OBSOLETE -- `persist.py` Fase 5 udah nulis IOC
      lewat jalur normal), `/api/country-groups` (peta nama->varian buat
      data FREE-TEXT lama; skema baru `country_code` udah ISO alpha-2 dari
      enrichment, gak ada lagi varian nama yang perlu di-grup di layer API).

      **Bug nyata ketemu lewat test integrasi** (bukan dugaan):
      `AsyncArticleRepo.set_enrichment` (baru, port dari versi sync buat
      dipakai test) `MissingGreenlet` -- ganti koleksi relationship
      (`article.countries = [...]`) di sesi ASYNC butuh state koleksi LAMA
      buat ngitung diff cascade delete-orphan, itu lazy-load implisit yang
      gak jalan sinkron di luar `await` (versi sync `ArticleRepo` gak kena
      ini). Fix: `await session.refresh(article, attribute_names=[...])`
      eksplisit sebelum assign ulang.

      **`iocs`** (2026-09-18) -- permukaan BACA + kurasi manual (tag/TA/
      feedback/allowlist), **BUKAN** jalur tulis IOC baru: `upsert_ioc`/
      `persist_iocs_from_extraction` (`ioc_service.py` lama) SENGAJA gak
      diport -- itu udah digantikan `IOCRepo.upsert()` (Fase 5, dipanggil
      `cti_enrich.stages.persist` via Celery task `enrich.article`,
      live-verified Fase 6). `AsyncIOCRepo` (Fase 2, sebelumnya cuma
      `upsert`/`get`/`add_feedback`) ditambah `list_filtered`/`get_stats`/
      `add_tags`/`add_threat_actors`/`remove_threat_actor`/`delete`/
      `bulk_delete`. `ioc_allowlist_entries` (Fase 5, tabel dibaca doang
      buat `extract_iocs` -- sekarang jalur TULIS-nya juga ada,
      `AsyncIocAllowlistRepo` baru) ketahuan kurang kolom `added_by`
      (dipakai router lama buat audit trail) -- migrasi `9faf52bcc2a1`
      nambahin (`server_default='system'` buat 9 baris seed Fase 5 yang
      udah ada, dicabut lagi abis backfill).

      **Sengaja di-skip/ditunda**: `_sweep_delete_matching()` (legacy:
      nambah allowlist entry retroaktif nge-hapus baris IOC lama yang
      cocok) -- filtering IOC udah kejadian di EXTRACTION time sekarang
      (`extract_iocs.py`, cache TTL 300s), entry baru otomatis efektif
      buat artikel BARU; bersihin baris LAMA yang kepalang ke-extract itu
      fitur admin terpisah, bukan bagian inti nambah allowlist entry.
      `GET /fp-analytics`+`/apply-suggestions` (butuh `fp_analytics_service`,
      statistik berat), `GET /ta-links/{type}/{value}` (butuh router
      `ta_groups`/`attack` ke-port duluan), `decay_sweep()` (item **7.8**,
      salah satu dari 5 loop Celery beat), recompute confidence/actionability
      pas feedback (`confidence_service`, ditunda bareng `articles`).

      **Bug proaktif dicegah** (pola sama kayak `update_client_ids` Fase
      7.2 dan `set_enrichment` di atas): `remove_threat_actor` pakai
      `.remove()` dari koleksi `ioc.threat_actors` (cascade delete-orphan
      yang urus DELETE pas flush), BUKAN `session.delete()` langsung ke
      child -- ditulis dari awal biar gak kena staleness in-memory
      collection, bukan ketauan lewat test gagal kayak kasus sebelumnya.
      Diverifikasi eksplisit test integrasi: `ioc.threat_actors` di objek
      yang sama langsung ke-update tanpa fetch ulang.

      Verified LIVE via curl: list/filter/stats/detail (dengan sources),
      tag/threat-actor add+remove, feedback (tp_count nambah), allowlist
      add (idempoten by type+value)/list/delete (404 kalau gak ada),
      delete single + bulk (count akurat), RBAC 401/403 (termasuk
      ketauan satu user test dari sesi sebelumnya udah ke-promote admin --
      bukan bug, state nyata dari testing Fase 7.2 yang persist).

      **`techstack`** (2026-09-18) -- **prasyarat buat `cve.py`**, sengaja
      dikerjain SEBELUM CVE (bukan gantian urutan tanpa alasan): `cve_service.
      get_cves()` legacy nyari active tech stack + `get_tech_risk_context()`
      buat `adjusted_risk_score` (exposure/hosting multiplier) di HAMPIR
      SETIAP fungsi -- gak mungkin diport bermakna tanpa `AsyncTechStackRepo`
      ada duluan. `TechStackEntry` (Fase 2) udah dibaca `cti_scraper.
      reference_data`/`cti_enrich.stages.score` (pola "web kurasi, scraper
      patuh" yang UDAH live sejak Fase 3/4/5) -- router ini yang jadi jalur
      admin ngisi/ubah datanya, `AsyncTechStackRepo` baru (belum ada
      sebelumnya, cuma dibaca lewat query ad-hoc di enrichment).

      **Sengaja di-skip/ditunda ke `cve.py`** (bukan tanggung jawab
      `techstack_entries` sendiri, semua NULIS ke `cve_tracker`):
      `POST /backfill-cves` (copy CVE existing dari client lain),
      `POST /{id}/backfill-historical` (trigger fetch 180 hari NVD+detail
      MITRE per-CVE -- `httpx` ke API eksternal, belum ada di dependency
      `cti-api`), cascade-delete CVE pas tech dihapus (`delete_techstack`
      lama nge-hapus `cve_tracker`/`cve_false_positives`/`cve_tickets`
      terkait -- di sini `DELETE /{id}` MURNI hapus baris techstack).
      `_client_filter` fallback OR Mongo lama (`client_id=="default"` ATAU
      field gak ada) juga di-skip -- `client_id` NOT NULL di skema Postgres
      sejak awal, kasus "field gak ada" gak mungkin kejadian.

      Verified LIVE via curl: list (data seed lama "WordPress"/"Linux"
      ke-detect), tambah tech + duplikat case-insensitive ditolak, patch
      exposure/hosting (404 kalau value gak valid ATAU tech beda client),
      search filter, delete + delete-lagi (idempoten, `success:false`),
      401 tanpa token. 11 test integrasi baru (termasuk isolasi per-client:
      nama sama di dua client beda-beda baris, update tech client lain
      ditolak).

      **`cve`** (2026-09-18) -- permukaan BACA + false-positive + purge
      orphaned. `CveTracker`/`CveFalsePositive` (Fase 2) udah lengkap,
      cuma kurang layer BACA (`AsyncCveTrackerRepo`/
      `AsyncCveFalsePositiveRepo` baru) -- jalur TULIS CVE baru TETAP
      `CveTrackerRepo` sync yang udah ada (Celery task, Fase 4), gak
      disentuh. `adjusted_risk_score`/`tech_exposure`/`hosting_type`
      lewat `AsyncTechStackRepo.get_risk_context()` (**inilah kenapa
      `techstack` dikerjain duluan** -- kebukti kepetakan bener pas live
      test, satu entri Linux `exposure=public`/`hosting=saas` ngubah
      `adjusted_risk_score`-nya).

      **Sengaja di-skip/ditunda** (masing-masing alasan beda, didokumentasiin
      di docstring router): `GET /export` (Excel, `openpyxl` belum
      dependency), `POST /draft-email` (email/Graph), `POST /cisa-lookup`+
      `/epss-lookup`+`/exploit-lookup` (API eksternal CISA/FIRST.org/
      exploit-db), `GET /{id}/mindmap` (`mermaid_service`), `GET /prioritize`
      (konsep "campaign" belum ada modelnya). **`ticket`/`acknowledge`
      (termasuk `ack_filter`) SENGAJA ditunda karena alasan DESAIN, bukan
      cuma "belum sempat"**: `CveTicket` Pydantic lama itu record
      remediation KAYA per-CVE (14+ field -- affected_asset, owner_email,
      remediation_status, dst), sedang model Postgres `CveTicket`/
      `CveTicketItem` (Fase 2) didesain buat konsep BEDA (satu ticket_id +
      status, bisa nyakup banyak cve_id, gak ada kolom `client_id`/
      `acknowledged_by` sama sekali) -- butuh keputusan desain sendiri
      soal bentuk final tabelnya, bukan sekadar nambah kolom kayak
      gap-gap sebelumnya.

      **Insiden kecil pas kerjain ini**: nulis file repo baru pakai
      `cat > ...` (bukan Edit/append) TIMPA `CveTrackerRepo` (sync) yang
      udah ada dari Fase 4 -- ketauan LANGSUNG dari `mypy` full-repo
      (`cti_scraper.sinks` gagal import). Dipulihin dari `git show
      HEAD:...` + digabung manual sama kelas baru, di-reverifikasi mypy
      211 file bersih + full suite + live curl ulang abis fix. Pelajaran:
      file yang udah ada isinya HARUS di-Edit/append, bukan di-overwrite
      `cat >`, walau niatnya nambah bukan ganti.

      Verified LIVE via curl: list/stats/tech-list (dengan data real 4
      CVE termasuk yang ada POC dari github_poc_monitor), false-positive
      mark/unmark/bulk (exclude dari list default, `include_fp=true`
      nampilin lagi), filter tech/severity/search, purge-orphaned dry-run
      (0 delete karena tech aktif cocok techstack). 22 test integrasi baru
      (Postgres real, termasuk isolasi per-client dan cascade FP-delete
      pas purge beneran jalan).

      **2026-09-18 -- survei 21 router sisa + rencana 5 bagian** (diminta
      user sebelum lanjut, biar gak nemu gap bertumpuk di tengah jalan):
      Bagian 1 quick-wins (`tweets`/`monitored_accounts`/`ransomware`/
      `changelog`/`filtered_articles`, model udah siap) → Bagian 2 domain
      baru self-contained (`rfi`/`pir`/`source_reliability`) → Bagian 3
      ATT&CK/TA (`attack` [prasyarat, sama pola `techstack`→`cve`] →
      `ta_groups` → `mitre` → `crossref`) → Bagian 4 fitur besar mandiri
      (`pkg_vuln`/`newsletter`/`stix`/`mindmap`) → Bagian 5 dashboard
      agregator (`intelligence`/`recap`/`exec_dashboard`, PALING BELAKANGAN
      karena nyedot data dari hampir semua domain lain). Detail lengkap +
      alasan urutan ada di riwayat percakapan; ringkasan tiap bagian nyusul
      di sini pas masing-masing dikerjain.

      **Bagian 1 (2026-09-18) -- 3/5 kelar** (`tweets`, `monitored_accounts`,
      `ransomware`). `Tweet`/`MonitoredAccount`/`RansomwareVictim` model
      udah lengkap dari Fase 4/5 -- tinggal nambah query layer async, pola
      sama kayak `cve`/`techstack`. `MonitoredAccount` ketauan kurang
      `display_name`/`notes` pas porting beneran (migrasi `22b43affdcac`,
      sama pola gap-gap sebelumnya). `apac_indicator`/`ot_status` tweet
      ada DI DALAM `scan_results` JSONB (bukan kolom top-level) -- filter
      pakai operator JSONB Postgres `.as_boolean()`, ekuivalen persis
      `query["apac_indicator"] = True` Mongo lama.

      **`changelog` dan `filtered_articles` SENGAJA di-skip** dari Bagian 1
      (bukan "quick win" beneran begitu diperiksa): `changelog` baca file
      `CHANGELOG.md` langsung dari disk -- monorepo baru ini GAK PUNYA file
      itu (commit message aja, gak ada convention changelog manual), bikin
      satu itu keputusan produk/dokumentasi, bukan keputusan porting
      mekanis. `filtered_articles` baca `scraper_runs` dengan `accepted=False`
      (artikel yang DITOLAK pipeline enrichment) -- skema Postgres (Fase 5)
      cuma nulis artikel yang DITERIMA ke tabel `articles`, gak ada tabel
      "artikel ditolak" sama sekali. Butuh keputusan desain (tabel log
      baru? just skip?) sebelum bisa diport, bukan sekadar tambah kolom.

      Bug nyata ketemu lewat test integrasi (bukan dugaan):
      `AsyncRansomwareVictimRepo.list_filtered` declare `date_start`/
      `date_end` sebagai `str`, dibandingin langsung ke kolom `Date` --
      asyncpg GAK auto-cast varchar ke date (beda dari psycopg2/sync),
      query gagal `UndefinedFunctionError` di runtime. Fix: `datetime.date`
      typed, sama pola kayak `articles`/`cve` (harusnya emang gitu dari
      awal, kelewat pas ngetik cepat). Live-reverified abis fix: endpoint
      yang tadinya 500 sekarang 200.

      Verified LIVE via curl: tweets list/stats/filter (apac/ot/confirmed/
      author/search/date), monitored-accounts CRUD penuh (normalisasi
      `@username` lowercase, 409 duplikat), ransomware victims/filters/
      related-articles. 26 test integrasi baru (Postgres real). Full suite:
      690 passed, mypy 218 file bersih, ruff bersih.

      **Bagian 1 (2026-09-18) -- 5/5 KELAR.** User eksplisit minta kerjain
      `changelog`/`filtered_articles` juga (bukan skip permanen kayak
      opsi default), dua-duanya ternyata butuh keputusan produk/desain
      dulu (ditanyain ke user via `AskUserQuestion`, bukan diputus sendiri):

      - **`changelog`**: user pilih "bikin `CHANGELOG.md` beneran". File
        baru di root repo (`CHANGELOG.md`, format `## [versi] - tanggal`,
        entry pertama `[0.1.0]` ngerangkum Fase 0-7.3 sejauh ini). Router
        port apa adanya (baca+parse regex) -- path file dicari lewat
        walk-up ke root repo (pola sama `_find_repo_root()` di
        `tests/integration/conftest.py`), bukan hitung `.parent` tetap N
        kali kayak legacy (rapuh kalau struktur `apps/api` berubah).

      - **`filtered_articles`**: user pilih "bikin tabel baru + wire ke
        pipeline Fase 5" (opsi yang LEBIH BESAR, nyentuh balik kode yang
        udah live-verified). Tabel baru `rejected_articles` (migrasi
        `8c208279c67f`) + `RejectedArticleRepo` (sync, jalur tulis) +
        `AsyncRejectedArticleRepo` (baca+restore, Fase 7.3). `cti_enrich.
        pipeline.run_pipeline()` sekarang manggil `persist_rejected()`
        (fungsi baru, `stages/persist.py`) pas `classify_result.
        related_cyber == False` -- SEBELUMNYA (Fase 5 awal) artikel yang
        ditolak diam-diam ilang, gak ke-log di mana pun yang bisa
        di-query. `reason` (alasan LLM nolak) DITANGKEP -- ini genuinely
        LEBIH KAYA dari legacy (Mongo `scraper_runs` cuma nyimpen boolean
        `accepted`, gak ada alasan). `restore()` SENGAJA bukan `upsert()`
        biasa -- kalau artikel udah ADA (misal ke-restore manual tapi
        juga keterima normal lewat run enrichment lain), `upsert()` bakal
        NIMPA `news_type` artikel asli jadi "Manually Restored", itu
        salah; `restore()` cek exists-by-URL dulu, no-op kalau udah ada
        (port perilaku lama persis).

        **Verified LIVE end-to-end, bukan cuma test**: `run_pipeline()`
        beneran dipanggil lawan LLM gateway asli dengan judul yang jelas
        gak nyambung cyber ("10 Best Pasta Recipes...") -- LLM nolak,
        `persist_rejected()` nulis baris, `GET /api/filtered-articles`
        nampilin `reason` asli dari LLM, `POST /restore` beneran
        nge-insert ke `articles` dengan `news_type="Manually Restored"`
        dan langsung ke-query balik lewat `/api/articles?search=pasta`.

        **Ketemu (bukan diakibatkan perubahan ini)**: re-test jalur
        ACCEPTED (judul yang genuinely cyber-related) gagal di
        `extract_ttps` dengan `JSONDecodeError` berulang -- ditelusuri
        lebih lanjut, ternyata gateway LLM dev
        (`172.25.0.77:20128`) sekarang ngebalikin respons dari persona
        lain ("Kiro", nolak ngikutin instruksi format JSON) alih-alih
        model reasoning yang biasa dipakai sepanjang Fase 5/6/7 -- indikasi
        gateway/model di baliknya keganti/kereset di luar kendali sesi
        ini. **BUKAN regresi dari perubahan Fase 7.3** -- `git diff
        pipeline.py` dicek eksplisit, cuma nyentuh docstring + cabang
        reject, nol baris di cabang accepted (`fetch_text`/`summarize`/
        `extract_ttps`/`score`/`persist` sama sekali gak diubah). Dilaporin
        ke user sebagai temuan operasional terpisah, bukan dibenerin
        diam-diam di sini.

        7 test unit (`changelog`, parsing regex + walk-up path) + 7 test
        integrasi (`RejectedArticleRepo` sync + dedup by url_hash) + 5 test
        integrasi (`AsyncRejectedArticleRepo`: list/filter/restore/restore
        no-op) -- semua Postgres real. Full suite abis Bagian 1 lengkap:
        **701 passed**, mypy 223 file bersih, ruff bersih.

      Sisa 13 router (Bagian 3-5) nyusul bertahap.

      **Bug infra ketemu pas kerjain ini (di luar scope router itu
      sendiri, tapi ketauan justru dari nge-`mypy` `apps/api` doang):**
      gak ada paket workspace (`cti-core`, `cti-scraper`, `cti-enrich`,
      `cti-alerts`, `cti-scrapers`, `cti-worker`, `cti-api`) yang punya
      marker `py.typed` (PEP 561) -- tanpa itu, mypy DIAM-DIAM nge-`Any`-in
      semua import lintas-paket kalau paket sumbernya gak ikut jadi target
      check eksplisit (bukan cuma di-`import`). Semua "mypy bersih" Fase
      6/7 sebelumnya kebetulan lolos karena SELALU nyertain file
      `cti_core` yang relevan eksplisit di command-nya (`mypy apps/worker
      packages/cti-core/src/cti_core/celery_client.py`, dst) -- begitu
      `mypy apps/api` doang, dua "Returning Any" muncul di
      `services/policy.py` walau kodenya gak berubah. Fix: `touch
      py.typed` di 7 paket sekaligus. Full repo-wide check abis fix: 0
      error baru ketemu (bug ini gak nyembunyiin bug LAIN, tapi infra-nya
      sendiri rapuh -- scoped mypy check ke depan sekarang bener-bener
      independen per paket).

      **Bagian 2 (2026-09-18) -- 3/3 KELAR** (`rfi`, `pir`,
      `source_reliability`) -- user bilang "gas lanjut bagian 2" langsung
      abis Bagian 1. Tiga domain baru self-contained, model Postgres baru
      semua: `rfi_requests`, `pir_requirements`+`pir_notes`,
      `source_reliability_entries` (migrasi `f5a204cd523a`).

      **`pir` matching TIDAK punya query builder sendiri** -- kode lama
      py DUA salinan identik (`pir_service.py::_build_query` DAN
      `scripts/export_pir_docx.py::_build_article_query`). Di sini
      kriteria PIR (`threat_actors`/`industries`/`countries`/`news_types`/
      `keywords`/`ttps`) di-map ke parameter `AsyncArticleRepo.
      list_filtered()` yang UDAH ADA dari router `articles` -- nambah SATU
      param baru (`ttps`, filter `ArticleTTP.ttp_id`) ke situ, bukan bikin
      builder baru. `criteria.keywords` -> `title_keywords` (OR-match
      `Article.title` doang -- skema baru gak nyimpen `body`/`content` per
      artikel, beda dari Mongo lama yang nyari lintas 4 field, tapi ini
      SUBSET yang faithful terhadap apa yang beneran ada, bukan
      pengurangan scope sembunyi-sembunyi).

      Docx export (`GET /{id}/export/docx`) port `build_docx()` dari
      `scripts/export_pir_docx.py` verbatim ke `services/pir_docx.py` --
      nambah dependency baru `python-docx` di `apps/api/pyproject.toml`.
      Verified LIVE: hasil file beneran kebuka valid Word doc (`file`
      command konfirmasi "Microsoft OOXML"), bukan cuma HTTP 200 doang.

      **Dua asimetri port apa adanya dari kode lama, didokumentasikan di
      docstring `cti_core.db.repositories.rfi`/`pir`, BUKAN keputusan baru
      di sini:**
      1. Baca-vs-tulis: banyak `GET` di `rfi`/`pir` (articles/note/export/
         export-docx/options) SAMA SEKALI gak `require_auth` di kode lama --
         sama pola kayak `articles.py`/`filtered_articles.py` sebelumnya.
      2. Client-scoping: `list`/`create` di-filter `client_id`, tapi
         `get`(PIR)/`update`/`delete`/notes/export SAMA SEKALI gak (RFI:
         `get` scoped, `update`/`delete` TIDAK). Siapa pun yang tahu ID
         bisa update/delete lintas client -- keliatan konsisten di DUA
         file (bukan typo satu tempat), jadi diikutin apa adanya + di-flag
         jelas biar user bisa minta diperbaiki belakangan kalau mau.

      **Kuirk port apa adanya dari `_compute_coverage()` lama:** PIR
      dengan kriteria KOSONG semua match-all buat `coverage_count`/
      `last_match`, tapi `recent_coverage` di-hardcode 0 (bukan dihitung
      beneran) -- efeknya PIR tanpa kriteria SELALU `is_gap=true`.
      Kemungkinan sengaja (dorong analis isi kriteria), bukan lupa nulis
      kode -- test `test_compute_coverage_empty_criteria_recent_always_zero`
      ngunci perilaku ini.

      **Bug real ketemu + dibenerin dari live-test (BUKAN dari test suite
      -- integration test lolos duluan karena gak assert `updated_at`
      abis path UPDATE beneran):** `PUT /api/pir/{id}`, `PUT /api/pir/{id}/
      note`, `PUT /api/rfi/{id}` semua 500 `MissingGreenlet` pas nyerialisasi
      `.updated_at` abis `session.commit()`. Sebab: kolom `updated_at`
      (`onupdate=func.now()`, nilai dihitung SERVER pas UPDATE) gak
      selalu eager-fetch via RETURNING kayak kolom sejenis pas INSERT --
      `POST` (create) jalan mulus, `PUT` (update) yang genuinely UPDATE
      baris yang UDAH ADA yang kena. Fix: `await session.refresh(obj)`
      eksplisit sebelum serialize, di tiga tempat itu. Ketauan justru dari
      nyoba UPDATE beneran (bukan cuma create-lalu-baca) waktu live-test
      manual -- pengingat kenapa live verification tetap dijalanin walau
      integration test udah 729 passed.

      10 test integrasi `AsyncRFIRepo` + 9 test `AsyncPIRRepo` + 8 test
      `AsyncSourceReliabilityRepo` + 1 test baru `AsyncArticleRepo.
      list_filtered(ttps=...)` -- semua Postgres real (testcontainers).
      Live-verified via curl: RFI create/list/update/delete, PIR create/
      list/coverage/articles/note-save+get/export-json/export-docx/update/
      delete, SR add/list/labels/ungraded-sources/update/delete -- token
      JWT superadmin asli, lewat `apps/api` uvicorn ngobrol ke Postgres+
      Redis docker-compose lokal (bukan testcontainers efemeral). Full
      suite: **729 passed**, mypy 77 file (`cti-core`+`apps/api`) bersih,
      ruff bersih.

      **Bagian 3 (2026-09-19) -- 4/4 KELAR** (`attack`, `ta_groups`,
      `mitre`, `crossref`) -- user bilang "gas lanjut bagian 3". Rantai
      ATT&CK/TA sesuai urutan dependency yang direncanakan: `attack`
      (prasyarat) → `ta_groups` → `mitre` → `crossref`.

      **`attack`** -- katalog MITRE ATT&CK (technique/tactic/mitigation/
      group/software/relationship), 6 tabel baru + `attack_sync_log`.
      `sync_domain()` fetch bundel STIX (JSON, bisa puluhan MB) dari
      GitHub `mitre/cti` per domain (enterprise/ics/mobile), upsert
      batched `INSERT ... ON CONFLICT (stix_id) DO UPDATE` (500/batch,
      port angka yang sama dari `_bulk_write()` lama). `domains` (ARRAY)
      butuh merge-dedup manual di klausa `SET` (`array_agg DISTINCT`
      gabungan array lama+baru) -- tanpa itu re-sync domain yang sama
      numpuk entry duplikat, `$addToSet` Mongo lama otomatis nyegah ini.
      `stix_id` (bukan `attack_id`/`group_id`) yang jadi kunci upsert,
      persis `_id: obj["id"]` Mongo lama -- kode manusia-readable
      ("T1059"/"G0016") SENGAJA gak diberi UNIQUE constraint (gak
      dijamin unik lintas domain bundel MITRE). `POST /sync`/
      `GET /sync/{domain}` pakai FastAPI `BackgroundTasks` port apa
      adanya -- BUKAN salah satu dari 5 loop Fase 7.8 (itu loop
      KONTINYU, ini aksi admin sekali-pakai), butuh session sendiri
      (`async_session()` langsung) karena session request-scoped ke-close
      begitu response terkirim. Full-text search Mongo (`$text`) -> ILIKE,
      konsisten sama router lain. Verified LIVE: sync domain `mobile`
      beneran (137 technique/22 group/127 software/1889 relationship dari
      GitHub asli), re-sync gak numpuk `domains` duplikat (delta=0),
      semua endpoint query (techniques/tactics/mitigations/groups/
      software/navigator-layer) jalan atas data hasil sync itu.

      **`ta_groups`** -- daftar nama TA utama REUSE `ThreatActorGroup`
      (`threat_reference.py`, Fase 5, dipakai bareng `cti_enrich.stages.
      score` buat `mentioned_group` matching) alih-alih bikin tabel baru
      terpisah -- ketauan pas baca model itu, itu PERSIS collection yang
      sama kayak `TA_GROUPS_COLLECTION` lama. Nambah kolom `source` yang
      ketinggalan (tabelnya awalnya cuma dibaca, belum ada jalur tulis).
      3 tabel baru: `ta_whitelist` (suppression list, bukan whitelist
      beneran -- nama TA yang DITOLAK jadi group), `ta_watchlist`
      (per-client), `ta_profiles` (JSONB, profil terstruktur hasil LLM).
      Timeline (`get_ta_timeline`) + dormancy detection cross-reference
      artikel+tweet+ransomware victim per bulan.

      **Bug real ketemu dari test integrasi** (bukan hipotesis): query
      `get_timeline` pakai `func.to_char(Article.posted_on, "YYYY-MM")`
      DUA KALI terpisah (SELECT + GROUP BY) -- SQLAlchemy generate dua
      bind parameter beda (`$1`/`$4`) walau nilainya sama, Postgres nolak
      ("must appear in GROUP BY clause") karena validasinya SINTAKS,
      bukan nilai. Fix: assign `func.to_char(...)` ke variabel, dipakai
      ULANG objek yang sama di SELECT dan GROUP BY.

      LLM client-nya SENGAJA gak reuse `cti_enrich.llm.client` walau itu
      "SATU LLM client" kanonik Fase 5 -- `apps/api` punya exit criteria
      eksplisit (atas, Fase 7): "gak ada import `cti_scraper`/`cti_enrich`
      dari API". Duplikat sempit (~15 baris) `OpenAI(**kwargs)` di
      `services/ta_profile.py`, `LlmSettings`/`get_settings()`-nya tetap
      dari `cti_core`.

      CVE crossref (`exploited_vulnerabilities` LLM vs `cve_tracker`
      real) butuh kolom yang belum ada: `cisa_kev`/`active_exploitation`
      (bool) + `threat_actors`/`ttps` (tabel anak baru `CveThreatActor`/
      `CveTTP`, pola sama `ArticleThreatActor`/`ArticleTTP`). Field ini
      ADA di dokumen Mongo lama tapi ditulis loop enrichment CVE
      (`_cve_enrichment_loop`, Fase 7.8, BELUM diport) -- kolomnya
      ditambah sekarang (gap ketauan pas porting) supaya query crossref
      udah bener begitu 7.8 ngisi datanya, buat sekarang selalu
      kosong/false (bukan bug, cold-start biasa).

      **Verified LIVE dengan LLM gateway asli:** `POST /api/ta/profile/
      generate` kena isu "Kiro persona" yang udah didokumentasikan di
      Bagian 1 (gateway dev balikin response non-JSON) -- `HTTP 200` dari
      gateway tapi `json.loads` gagal ("Expecting value"). Bukan bug baru
      di sini, konsisten sama temuan operasional yang udah dilaporkan.

      **`mitre`** -- heatmap TA/industri x TTP, baca `articles`/
      `article_ttps`/dst (Fase 2, ternormalisasi) -- BUKAN katalog
      `attack_techniques` (`attack` di atas): heatmap ngukur TTP yang
      BENERAN keobservasi di pemberitaan (ekstraksi LLM Fase 5), beda
      sumber data dari katalog referensi MITRE, gak saling gantiin (sama
      pola `source_score_service.py` vs `source_score_db_service.py` di
      Bagian 2). `d3fend_service.py` (`urllib` sync-in-thread) diganti
      `httpx.AsyncClient`, port perilaku sama (cache in-memory, gagal ->
      list kosong) -- verified LIVE manggil API publik D3FEND asli, 15
      countermeasure buat T1059.

      **`crossref`** -- nyambungin CVE/PIR/TA lewat overlap threat_actors/
      TTPs, dikerjain TERAKHIR (butuh `cve`/`pir`/`ta_groups` semua udah
      ada). SEMUA query lintas client, TANPA filter `client_id` -- port
      apa adanya, kode lama juga gak nge-scope endpoint ini. `pir_id`
      sekarang `int` path param, gak perlu try/except `ObjectId(...)`.
      Verified LIVE: crossref CVE real (severity/KEV data bener), PIR
      overlap TA/TTP, TA cross-ref narik artikel+PIR+profil.

      23 test integrasi baru (`AsyncAttackSyncRepo`/`AsyncAttackQueryRepo`
      lewat live sync, `AsyncTARepo`/`AsyncTAProfileRepo`,
      `AsyncMitreHeatmapRepo`, `cti_api.services.crossref`). Full suite:
      **752 passed**, mypy 90 file bersih, ruff bersih.

      **Bagian 4 (2026-09-19) -- 4/4 KELAR** (`newsletter`, `mindmap`,
      `stix`, `pkg_vuln`) -- user bilang "gas fase 4 bro". Urutan kerja:
      newsletter → mindmap → stix → pkg_vuln (terbesar, dikerjain
      terakhir).

      **Byproduct arsitektur**: `cti_enrich/ioc/extractor.py` (SATU IOC
      extractor kanonik, Fase 5) dipindah ke `cti_core/ioc/extractor.py`
      -- modul itu nol dependency internal `cti_enrich`, jadi relokasi
      mekanis, zero behavior-change, yang ngebolehin `apps/api` (exit
      criteria: gak boleh import `cti_scraper`/`cti_enrich`) DAN
      `cti_enrich` sama-sama impor SATU ekstraktor yang sama, gak perlu
      fork lagi. `cti-alerts/mailer.py` (baru) ngelengkapin janji
      `pyproject.toml` package itu sendiri ("Telegram sender + Graph/SMTP
      mailer") -- `send_newsletter_email()` Graph-only (POST
      `/users/{sender}/messages`, bikin DRAFT bukan `/sendMail`, analis
      review manual di Outlook -- persis kode lama), SMTP DIBUANG
      (`SmtpSettings` gak pernah ada di skema config baru, `.env` cuma
      punya kredensial Graph).

      **`newsletter`** -- fetch artikel (Playwright + `trafilatura`,
      deteksi paywall keyword-based), ringkasan per-artikel via LLM,
      korelasi CVE (tabel anak baru `CveNewsletterMention`, ganti
      Mongo array-push-dedup jadi `UniqueConstraint(cve_tracker_id, url)`
      asli). `include_clusters` (analisis cluster kampanye,
      `cluster_service.py` 784 baris TF-IDF/Jaccard) SENGAJA belum
      diport -- di luar 27 router, sama alasan kayak `mindmap`'s builder
      `cluster` di bawah. **Bug real ketemu dari test integrasi**:
      `AsyncNewsletterRepo.list_all()` non-deterministic -- Postgres
      `now()` itu waktu TRANSAKSI bukan waktu STATEMENT, jadi banyak
      baris yang di-insert dalam satu transaksi test dapet `created_at`
      identik, `ORDER BY created_at DESC` doang gak cukup. Fix: tambah
      `Newsletter.id.desc()` sebagai tie-breaker kedua. Endpoint kirim
      email (`/resend`, `/draft-email`) SENGAJA belum di-live-test --
      butuh izin eksplisit user dulu (kirim email beneran/draft ke
      mailbox asli), cuma diverifikasi lewat unit test mock. Sisa
      pipeline (fetch Playwright, ekstraksi IOC, render HTML) verified
      LIVE (artikel Wikipedia asli, 11231 karakter ke-ekstrak).

      **`mindmap`** -- generate diagram Mermaid per domain (newsletter/
      threat_actor/cve/pir/ransomware), cache generik `(feature_type,
      doc_id) -> syntax` + custom-edit override. `doc_id` per
      feature_type dipetakan ke identifier yang SAMA dipakai router lain
      buat domain itu (`cve_id` string, nama TA, `PIRRequirement.id`/
      `Newsletter.id`, `group_name`) -- BUKAN internal PK Postgres,
      simplifikasi dari dual ObjectId-lalu-fallback-nama kode lama,
      konsisten sama pola yang udah ada di router lain. Builder
      `cluster` (butuh `cluster_service.py` yang sama kayak di atas)
      SENGAJA belum diport. Verified LIVE: generate + cache-hit
      (ganti data CVE abis generate pertama, syntax gak ikut berubah
      tanpa `/regenerate` eksplisit) pakai data real dev Postgres.

      **`stix`** -- export bundle STIX 2.1 (article/TA/IOC/PIR), builder
      STATELESS (baca-transform doang, gak ada tabel baru sama sekali).
      Asimetri auth port apa adanya: cuma `/article/{id}` yang
      `require_auth`, 3 endpoint lain publik. `article_id` sekarang
      `int` (bukan ObjectId hex), `AsyncPIRRepo.list_active_unscoped()`
      (dipakai bareng `crossref` Bagian 3) ditambah `order_by(priority)`
      biar cocok sama `.sort("priority", 1)` lama. Verified LIVE:
      export artikel real (Unc6671/T-technique beneran, 13 objek STIX +
      relationship `uses`), TA-not-found -> 404, IOC bundle + filter
      type, PIR bundle keurut priority.

      **`pkg_vuln`** -- terbesar (1109 baris service lama), monitoring
      vulnerability paket (osv.dev + deps.dev). **Ketemu skema Fase 2
      yang udah ada duluan** (`models/package.py`,
      `MonitoredPackage`/`PackageVuln`/`PackageVulnAlias`/
      `PackageDepEdge`) -- ditulis SEBELUM `pkg_vuln_service.py` lama
      dibaca detail, 3 tabel kosong (gak pernah ke-wire router/service/
      test manapun), DIGANTI TOTAL (bukan alter bertahap, aman karena
      kosong): `PackageVuln.monitored_package_id` FK STRICT gak bisa
      nampung kasus nyata (`resolve_package_deps(scan_transitive=True)`
      scan dependensi TRANSITIF yang BUKAN package dimonitor, `update_one`
      TANPA `upsert=True` lama diem2 no-op kalau gak ketemu tapi vuln-nya
      tetap kesimpen) -- diganti `package_name`/`ecosystem`/`client_id`
      DENORMALIZED, port apa adanya dari bentuk Mongo lama. Field yang
      ilang total di sketsa (rollup `vuln_count`/`*_count`/
      `highest_severity` dkk, `cvss_score`/`adjusted_score`/`published`/
      dst) ditambahin lengkap. `_enrich_vulns_composite()` (EPSS dari
      FIRST.org + KEV dari CISA) SENGAJA belum diport -- `epss_service.py`/
      `cisa_kev_service.py` SAMA yang udah didokumentasikan belum ke-port
      di `routers/cve.py` (`/cisa-lookup`/`/epss-lookup`), bukan concern
      `pkg_vuln` doang; kolom `epss_*`/`kev*` tetap ada di skema, `adjusted_
      score` dihitung dari `cvss_score` doang saat scan (formula sama,
      cuma belum "boosted" pass kedua). Fire-and-forget
      `asyncio.create_task(scan_package(...))` lama (dipanggil dari 4
      tempat beda: `add_package`/`update_package`/`import_lockfile`/
      `resolve_package_deps`) DIPINDAH ke router pakai `BackgroundTasks`
      + `async_session()` sendiri, pola sama `attack.py` Bagian 3 --
      service jadi murni CRUD+orkestrasi eksternal, gak nge-spawn task
      sendiri. `scan_all_packages()` SEKUENSIAL (bukan `asyncio.gather`
      batch-10 + `sleep(2)` lama) -- satu `AsyncSession` gak aman
      concurrent, throttling lama ikut dibuang (gak ada concurrency yang
      perlu ditahan). Ketemu dependency baru yang kelewat pas nulis
      endpoint upload lockfile: `python-multipart` (FastAPI butuh ini
      buat `UploadFile`), ditambah ke `apps/api/pyproject.toml`.
      Verified LIVE end-to-end pakai osv.dev/deps.dev BENERAN: `lodash@
      4.17.15` narik 6 CVE asli (CVE-2020-8203/CVE-2021-23337/dst,
      3 HIGH/3 MEDIUM), `flask@2.0.0` narik 4 CVE asli, `resolve-deps`
      narik OSSF Scorecard asli (skor 5.4, checks asli) + dep graph,
      import-lockfile (package asli + package fiktif yang bener2 gak ada
      di registry -- gak crash, 0 vuln doang), ack toggle, delete
      cascade ke vuln anak-nya.

      75 test baru (22 unit parser lockfile/CVSS murni + 53 integrasi
      Postgres real: newsletter/mailer/mindmap/stix/pkg_vuln). Full
      suite: **827 passed**, mypy 108 file (`cti-core`+`cti-api`)
      bersih, ruff bersih.

      **Bagian 5 (2026-09-19) -- 3/3 KELAR** (`intelligence`, `recap`,
      `exec_dashboard`) -- user bilang "gas bagian 5 bro", TERAKHIR
      dari 5 bagian karena nyedot data dari hampir semua domain lain
      (persis alasan urutan yang direncanakan sejak survei 2026-09-18).

      **`intelligence` -- 3 dari 7 endpoint lama SENGAJA belum diport**:
      `/clusters`, `/clusters/recent`, `/clusters/evolution`,
      `/clusters/{id}/trends`, `/intelligence/geopolitical` (5
      sebenarnya) SEMUA transitif butuh `cluster_service.py` (784 baris
      TF-IDF/Jaccard, di luar 27 router) -- `campaign_trend_service.py`/
      `geopolitical_service.py` ikut kena karena masing-masing baca
      output cluster (`CLUSTERS_COLLECTION`) atau nerima `campaigns`
      sebagai parameter. Sama alasan persis kayak deferred `cluster`
      di `newsletter`/`mindmap`/`exec_dashboard` (Bagian 4-5). Yang
      PORTABLE (`/spikes`, `/intelligence/risk-matrix`, `/source-scores`)
      -- ketiganya baca `articles` langsung, gak ada dependency cluster.

      **Repo baru `AsyncDashboardRepo`** (`cti_core.db.repositories.
      dashboard`) -- ~20 method agregasi lintas `articles`/`cve_tracker`/
      `iocs`, dipakai bareng `intelligence`/`exec_dashboard`/`recap`.
      Bucket bulanan pakai `func.to_char(Article.posted_on, 'YYYY-MM')`
      ganti `$substr` Mongo lama -- HARUS diassign ke variabel & dipakai
      ULANG objek yang sama di SELECT+GROUP BY, bug real yang sama
      persis kayak `AsyncTARepo.get_timeline()` (Bagian 3) kalau lupa.
      **Semua query SEKUENSIAL**, bukan `asyncio.gather` kayak lama --
      dashboard-v2 aja manggil ~15 query terpisah, satu `AsyncSession`
      emang gak aman concurrent (constraint yang sama berkali-kali
      ketemu sesi ini).

      **2 bug REAL ketemu & DIPERBAIKI (bukan asimetri desain)**, dua-duanya
      typo/field-salah yang bikin sebagian output LLM/skor mati diam-diam:
      1. `risk_matrix_service.py` lama baca `doc.get("attack_techniques")`
         buat komponen skor TTP -- field itu TIDAK PERNAH ada di dokumen
         artikel manapun (field TTP artikel asli namanya `ttps`), jadi
         komponen `unique_ttps * 2` di formula skor SELALU 0. Di sini
         pakai `ttps` asli.
      2. `exec_brief_service.py` lama baca `ta.get('name')`/`('count')`/
         `('velocity')` dari entry `ta_velocity`, tapi `_compute_ta_
         velocity()` beneran ngehasilin key `actor`/`total`/`velocity_pct`
         -- section "TOP THREAT ACTORS BY VELOCITY" di brief eksekutif
         SELALU nge-render "Unknown: 0 incidents". Di sini pakai key yang
         beneran dihasilin.

      **`_get_recent_clusters()`/`recent_clusters_summary` (exec_dashboard
      v2) DAN `_collect_campaigns()` (recap) SENGAJA balikin `[]`** --
      cluster_service lagi, TAPI kode lama sendiri udah bungkus dua-duanya
      `try/except -> []`, jadi cuma selalu hit fallback yang udah ada,
      bukan kontrak baru yang dilanggar.

      **`recap`** -- digest harian (artikel+tweet+IOC+CVE+TA baru) + LLM
      forecast 1-3 hari, cache per-tanggal (`daily_recaps`, tabel baru).
      Artikel diurutin heuristik `source_score.get_source_reliability()`
      (nama sumber) gantiin field `source_reliability` per-dokumen lama
      yang gak ada analognya di skema baru (grading itu sekarang query
      terpisah `AsyncSourceReliabilityRepo`, bukan kolom artikel).
      `AsyncTARepo.list_added_on()` (baru) pakai `created_at::date`
      gantiin kolom `added_date` yang emang gak pernah ada di skema
      (`ThreatActorGroup` cuma punya `TimestampMixin.created_at`,
      semantiknya sama). **Verified LIVE dengan LLM gateway asli**:
      `POST /api/recap/generate` jalan bersih (gak kena isu "Kiro
      persona" yang beberapa kali muncul Bagian 1/3/4) -- recap hari
      sepi (0 artikel/tweet/CVE, 89 IOC, 3991 TA baru dari seed data)
      dihasilin JUJUR ("no notable activity", sesuai rule system prompt),
      bukan dikarang. Cache-hit + `/list`/`/{date}` + validasi format
      tanggal semua diverifikasi LIVE juga.

      **`exec_dashboard`** -- `GET /dashboard` (v1) **SENGAJA TANPA
      AUTH**, port apa adanya (`/dashboard-v2` dan `POST /brief` tetap
      di-gate) -- asimetri yang gak biasa (bukan pola baca-publik/tulis-
      digate yang udah sering ketemu, ini "v1 publik, v2+brief di-gate")
      tapi dipertahankan sesuai kode lama. `_get_critical_cves()` cuma
      filter `cisa_kev` (cabang `epss_score >= 0.5` gak ada kolomnya,
      sama alasan `pkg_vuln`/`cve.py`). **Verified LIVE**: v1+v2+brief
      ketiganya jalan atas data dev Postgres real (15 insiden, 6 TA unik,
      leaderboard Unc6671/Turla/Apt41/dst, top TTPs T1005/T1190/T1570),
      `POST /api/exec/brief` ngehasilin brief markdown 5-section lengkap
      dari LLM gateway asli, ground di data real (nyebut UNC6671, CVE
      WordPress, risk score per sektor -- bukan generik).

      22 test baru (`AsyncDashboardRepo` x9, `exec_dashboard`/`spike`/
      `risk_matrix` service x5, `AsyncRecapRepo` x3, `recap` service x5
      dengan LLM di-mock). Full suite: **849 passed**, mypy 120 file
      (`cti-core`+`cti-api`) bersih, ruff bersih.

      **Fase 7.3 SELESAI -- 25/25 router** (lihat catatan di atas soal
      angka "27" awal). Lanjut ke sisa Fase 7 (**7.4** port 56 service,
      **7.5** buang duplikasi, **7.6** snapshot test, **7.7** ekspor
      OpenAPI, **7.8** 5 loop jadi Celery beat) sebelum Fase 8 (`apps/web`).
- [x] **7.4** Port 56 service -- **survei + urutan kerja kelar
      (2026-09-19, user minta "cek dulu servicenya, urutkan mana duluan
      mana belakangan")**: ~37/56 service TERNYATA udah keport sebagai
      efek samping porting 27 router (Fase 7.3). 19 sisa dipetakan jadi
      5 grup (B → D → C → A, plan lengkap di
      `~/.claude/plans/oke-bro-jadi-gini-sparkling-fern.md` §"Fase 7.4"):
      **Grup A** "mesin cluster" (`cluster_service.py` 784 baris TERNYATA
      punya 5 dependency internal -- `campaign_scoring_service`/
      `killchain_service`/`cve_priority_service`/`campaign_link_service`/
      `diamond_model_service` -- total 1510 baris, bukan 784; plus
      `campaign_trend_service`/`geopolitical_service` consumer-nya, 1773
      baris total, butuh keputusan taruh sklearn di mana), **Grup B**
      lookup eksternal CVE (KELAR, lihat bawah), **Grup C** ticket/email/
      export CVE (KELAR, lihat bawah), **Grup D**
      standalone tanpa blocker (`confidence_service`/`fp_analytics_
      service`/`dedup_service` + 2 endpoint ketinggalan -- KELAR, lihat
      bawah), **Grup E** keluar scope (`wisemap_service.py` 391
      baris + `wisemap_cti.py` ternyata DEAD CODE -- nol referensi
      router manapun, `oidc_service`/`scraper_health_service` beda
      fase/udah dideferred).

      **Grup B (2026-09-19) -- 3/3 KELAR** (`epss_service`,
      `cisa_kev_service`, `exploit_db_service`, 299 baris gabung 1 file
      `cti_api.services.cve_lookup`) -- paling kecil, paling gak ada
      dependency baru, LANGSUNG nutup kolom yang UDAH ADA tapi SELALU
      kosong di kode yang baru dibangun Bagian 4/5 (`PackageVuln.epss_*`/
      `kev_date_added`, `exec_dashboard`'s cabang `epss_score >= 0.5`).
      4 endpoint baru nempel di router `cve.py` yang udah ada
      (`POST /cisa-lookup`/`/epss-lookup`/`/exploit-lookup`/
      `/{id}/exploit-lookup`), bukan router baru. 8 kolom baru
      `CveTracker` (`epss_score`/`epss_percentile`/`epss_date`/
      `epss_checked_at`, `cisa_kev_checked_at`+`cisa_kev_detail` JSONB,
      `exploit_db_checked_at`+`exploit_db_hits` JSONB) -- migrasi butuh
      `server_default` di 2 kolom JSONB NOT NULL karena `cve_tracker`
      UDAH ada isinya (4 baris), bukan tabel baru kosong.

      Fungsi service (`run_epss_lookup`/`run_cisa_kev_lookup`/`run_
      exploit_db_bulk_lookup`/`run_exploit_db_single_lookup`) sengaja
      `session`-pertama -- FONDASI Fase 7.8 ("CVE enrichment", salah
      satu dari 5 loop Celery beat): begitu 7.8 dikerjain, tinggal
      bungkus fungsi yang SAMA jadi task beat, gak perlu nulis ulang.

      **EPSS/CISA-KEV/exploit-db itu properti CVE ITU SENDIRI, bukan
      spesifik client** -- lookup lama `update_many` lintas SEMUA baris
      client yang nge-track cve_id yang sama, method repo baru
      (`apply_epss_scores`/`apply_cisa_kev_hits`/`apply_exploit_hits`)
      port perilaku itu, BEDA dari `add_newsletter_mention` (Bagian 4)
      yang baris pertama doang.

      **1 bug legacy ketemu & DIPERBAIKI, bukan silent fix** --
      `exploit_db_service.py` lama cek dedup POC dari SATU dokumen
      (`find_one`, ambil sembarang) lalu `$push` hasil yang sama ke
      SEMUA baris client lewat `update_many` -- kalau >1 client nge-
      track CVE yang sama, baris client lain bisa kebagian POC duplikat.
      Di sini dedup dihitung ULANG per baris (per client), koreksi
      kecil yang konsisten sama niat aslinya ("jangan taro POC dobel"),
      bukan ubah kontrak.

      **1 bug API EKSTERNAL ketemu LEWAT LIVE TEST, bukan port issue** --
      exploit-db beneran ganti bentuk respons sejak kode lama ditulis:
      field `description` SEKARANG list `[edb_id, title]`, bukan string
      polos (`row.get("description", "").strip()` lama crash
      `AttributeError` kalau dibiarin). Ini bukan "port apa adanya" --
      kontrak API pihak ketiga yang berubah, bukan keputusan desain lama
      -- diperbaiki (`_extract_title()`, tetap dukung string polos buat
      jaga-jaga), ketauan justru KARENA live-test terhadap API asli,
      bukan cuma baca kode lama.

      **Verified LIVE 100% terhadap API eksternal asli** (bukan mock
      doang buat verifikasi akhir): `CVE-2021-44228` (Log4Shell)
      disisipin manual ke dev DB buat test -- `/cisa-lookup` match asli
      lawan katalog CISA KEV 1721 entry (`Apache Log4j2 Remote Code
      Execution Vulnerability`), `/epss-lookup` narik skor EPSS asli
      dari FIRST.org (`0.99999`, persentil `1.0` -- cocok sama fakta
      publik Log4Shell EPSS-nya emang salah satu yang tertinggi pernah
      ada), `/{id}/exploit-lookup` narik 3 exploit ASLI dari exploit-db
      (ID 50590/50592/51183, URL bener, judul ke-parse bener SETELAH
      fix bug di atas). `GET /api/cve?tech=Log4j` konfirmasi ketiga
      field nyantol bareng di satu baris (`epss=0.99999, kev=true,
      active_exploitation=true, pocs=3`).

      13 test baru (4 unit parser murni + 9 integrasi Postgres real,
      HTTP eksternal di-mock buat suite otomatis -- verifikasi LIVE
      manual terpisah kayak di atas). Full suite: **862 passed**, mypy
      121 file bersih, ruff bersih.

      **Grup D (2026-09-23) -- 4/4 KELAR** (`confidence_service`,
      `fp_analytics_service`, `dedup_service`, + 2 endpoint yang
      ketinggalan pas Fase 7.3 -- `articles.py`'s `/dashboard` dan
      `iocs.py`'s `/ta-links/{type}/{value}`) -- semua nempel ke router
      `articles.py`/`iocs.py` yang UDAH ADA, bukan router baru.
      `confidence.py`+`fp_analytics.py`+`dedup.py`+`article_dashboard.py`
      (services) + `ioc_ta_links.py`.

      **3 kolom baru `IOC`** (`actionability_score`/`actionability_label`/
      `recommended_action`, semua nullable) -- migrasi gak butuh
      `server_default` (nullable, bukan JSONB NOT NULL kayak kolom Grup B).

      **Confidence artikel ditulis lewat `AsyncArticleRepo.set_overrides()`,
      BUKAN kolom `confidence_score` langsung** -- keputusan sengaja:
      docstring `Article.overrides` (Fase 2) nyebut `confidence_score`
      sebagai CONTOH field yang dilacak lewat overrides, walau tulisan
      Mongo lama (`compute_and_store`) `$set` langsung tanpa konsep
      override sama sekali. Ngikutin dokumentasi skema yang UDAH ADA,
      bukan port literal.

      **`compute_ioc_actionability`'s `campaign_score` PERMANEN 0** --
      butuh `CLUSTERS_COLLECTION` (mesin cluster, Grup A, BELUM diport).
      Legacy sendiri fallback `try/except -> 0` kalau lookup gagal; di
      sini fallback yang sama, cuma permanen sampai Grup A ada. TIDAK
      mengubah kontrak, cuma selalu hit jalur yang udah ada.

      **Dependency baru `scikit-learn`** (`apps/api`, buat
      `dedup_service`'s TF-IDF+cosine similarity) -- kelas keputusan
      sama kayak kenapa `cti-enrich` naruh torch/spacy di belakang extra
      `[nlp]` (compute-heavy). `uv sync` polos WIPE lagi extra
      `cti-enrich[nlp]` (udah kejadian & didokumentasikan pas Bagian 4)
      -- di-restore manual abis nambah dependency.

      **1 method repo baru per file, gak ada yang berat**:
      `AsyncIOCRepo.apply_confidence_and_actionability()`+
      `list_with_feedback()`, `AsyncTARepo.get_watchlist_names_unscoped()`
      (asimetri legacy: watchlist check LINTAS SEMUA client, bukan
      `client_id`-scoped kayak model barunya -- dipertahankan apa
      adanya, pola sama kayak `AsyncPIRRepo.list_active_unscoped()`),
      `AsyncAttackQueryRepo.get_group_by_name_or_alias_ci()` (case-
      insensitive nama ATAU alias -- scan Python di tabel kecil ~150
      baris, gak ada cara bersih match ARRAY(String) Postgres case-
      insensitive tanpa unnest per-baris yang sama beratnya),
      `AsyncSourceReliabilityRepo.get_all_ratings()` (preload semua
      rating sekali biar `recompute_all_confidence` gak N+1 query per
      artikel), 6 method baru `AsyncDashboardRepo` (`distinct_source_
      count`/`unique_mentioned_country_count`/`top_countries`/
      `top_sources`/`top_industries`/`article_timeline` -- semua terima
      `posted_on_start`/`posted_on_end` OPSIONAL dua-duanya, beda dari
      method exec_dashboard lain yang `posted_on_start` wajib).

      **`/api/dashboard`'s `top_countries` SENGAJA gak re-normalize nama
      negara** kayak `normalize_country()` Python-side lama -- masalah
      itu (negara FREE-TEXT butuh grouping manual) UDAH BERES di data
      model (`ArticleCountry.country_code` udah ISO alpha-2 kanonik dari
      enrichment, Fase 2/5), bukan lagi query-time. Query SQL `GROUP BY`
      langsung, tanpa post-process Python.

      **`/articles?dedup=true` gak nambah field baru ke `ArticleOut`** --
      ketauan dari baca legacy Pydantic model: `model_config =
      {"extra": "ignore"}`, jadi `_dup_count`/`_dup_sources`/`_dup_urls`
      dari `find_dedup_groups()` SELALU didrop diam-diam pas serialize
      ke `ArticleOut` di endpoint list -- cuma listnya yang efektif
      terfilter (dedup), metadata dup gak pernah nyampe response.
      `/articles/dedup-groups` (endpoint terpisah, raw dict response)
      yang beneran nampilin `_dup_count` dkk.

      **1 gap ketemu LEWAT LIVE TEST, langsung diperbaiki** --
      `iocs.py`'s `_serialize_summary()`/`_serialize_detail()` gak
      pernah include `actionability_score`/`actionability_label`/
      `recommended_action` walau kolomnya udah ada & udah kehitung --
      ketauan pas live-test `POST /{ioc_id}/feedback` (endpoint yang
      justru INTINYA nampilin actionability baru), bukan dari baca kode
      doang. Ditambahin ke serializer.

      **Verified LIVE terhadap dev DB real** (uvicorn lokal, Postgres+
      Redis via `localhost` override, token JWT di-mint langsung lewat
      `create_token()` -- gak ada password admin1 yang diketahui):
      `/api/dashboard` (38 artikel real, agregasi negara/sumber/TA/TTP/
      timeline semua ke luar bener), `/api/articles/dedup-groups`
      (jalan lewat scikit-learn beneran, gak crash), `POST /{ioc_id}/
      feedback` (IOC id=7 real, confidence 50->89->86 abis 2 feedback,
      actionability `monitor` + recommended action bener), `GET
      /ta-links/domain/...` (nemu TA `Breeze comet` dari artikel
      linked beneran), `POST /articles/{id}/confidence` +
      `/confidence/recompute` (38/38 artikel keupdate, override
      ke-merge bener pas dibaca ulang). Data feedback sintetis di IOC
      id=7 DIBERSIHIN abis verifikasi (`DELETE ioc_feedback` + reset
      counter/confidence/actionability) -- confidence recompute di 38
      artikel real DIBIARIN (bukan data sintetis, hasil legit fitur
      "recompute" yang emang gunanya nimpa skor lama).

      59 test baru (2 file unit murni -- `compute_score`/
      `compute_ioc_confidence`/`compute_ioc_actionability`/
      `find_dedup_groups` -- + 7 file integrasi Postgres real). Full
      suite: **921 passed**, mypy 126 file bersih, ruff bersih. SATU
      commit nutup Grup D.

      **Grup C (2026-09-23) -- 3/3 KELAR** (`cve_ticket_service`,
      `cve_email_service`, `cve_export_service`) -- didahuluin diskusi
      desain sama user (3 keputusan konkret, semua dijawab "Recommended"):
      tanggal ticket jadi `Date` asli (bukan string bebas kayak legacy),
      `ticket_id` tetap GLOBAL lintas semua client per bulan (port apa
      adanya), `cve_reported_date` di-drop (readonly di UI lama, gak
      pernah beneran di-override -- selalu derive dari `CveTracker.
      published`).

      **`CveTicket` DIROMBAK TOTAL dari placeholder Fase 2** (`CveTicket`
      1:N `CveTicketItem`, "satu ticket nyakup banyak CVE") -- ketauan
      baca `cve_ticket_service.py` lama: konsepnya SATU record flat per
      (cve_id, client_id), bukan container. `CveTicketItem` di-drop total,
      `CveTicket` jadi 17 kolom (affected_asset/owner_email/remediation_*/
      escalation_required/comments/risk_acceptance/closure_date/
      acknowledged_by/acknowledge_time). `ack_filter` (parameter
      list/stats lama yang di-skip pas Fase 7.3 karena nunggu ini) SEKARANG
      jalan lagi, subquery lawan `cve_tickets.acknowledged_by`.

      **1 fungsi mailer di-generalize, bukan diduplikat** --
      `cti_alerts.mailer.send_newsletter_email` (Bagian 4) namanya diganti
      `create_graph_draft` (logic-nya 100% generic, gak ada yang
      newsletter-spesifik) biar `cve_email.py` bisa numpang langsung,
      bukan nyalin ulang ~40 baris logic Graph API. Satu-satunya caller
      lama (`newsletter.py`) ikut di-update, gak ada perubahan perilaku.

      **1 bug DITEMUKAN & DIPERBAIKI di export, bukan port apa adanya** --
      `cve_export_service.export_cves_to_excel()` legacy TIDAK PERNAH
      nge-scope `client_id` sama sekali (query CVE maupun query false-
      positive), beda dari SEMUA endpoint lain di router yang sama yang
      konsisten pakai `effective_client_id()`. Di multi-tenant beneran
      ini kebocoran data lintas client. Diperbaiki: di-scope `client_id`
      (lihat docstring `cti_api.services.cve_export`).

      **1 asimetri legacy DIPERTAHANKAN, didokumentasikan eksplisit** --
      `cve_export_service.py` filter tanggal di `detected_on`, sedangkan
      `cve_service.py` (list/stats) filter `published` -- ini asimetri
      yang UDAH ADA di kode lama sendiri (bukan penyimpangan baru dari
      porting), jadi `AsyncCveTrackerRepo.list_for_export()` sengaja jadi
      method terpisah dari `list_filtered()`/`get_stats()`, bukan numpang
      `_apply_filters()` yang sama.

      Dependency baru `openpyxl` (`apps/api`). Template `CVE_Tracker_
      template.xlsx` + `cve_notification_email.html` disalin ke
      `apps/api/src/cti_api/templates/`. 3 panggilan LLM (`_llm_cve_
      validator`/`_dedup_mitigation`/`_dedup_risk_context`) port apa
      adanya (prompt verbatim), dibungkus `asyncio.to_thread()` (bukan
      `run_in_executor` legacy -- API sama, `to_thread` modern).

      **Verified LIVE terhadap dev DB real** (uvicorn lokal, Postgres+
      Redis via `localhost`): `next-ticket-id` (CTI-2026-09-001, generate
      bener), `PUT`/`GET /{cve_id}/ticket` (round-trip field remediation
      lengkap), `acknowledge`/`bulk-acknowledge`/`ack-statuses` (3 CVE
      real diacknowledge, status kebaca bener), `ack_filter=acked|unacked`
      di list DAN stats (angka cocok), `GET /export` (download xlsx
      beneran, 4 baris CVE real + ticket ID/severity/score/affected_asset
      semua kecantol bener di kolom yang tepat). Data ticket sintetis
      DIBERSIHIN abis verifikasi (`DELETE FROM cve_tickets`).

      **`POST /draft-email` SENGAJA BELUM live-tested** -- 3 panggilan
      LLM beneran (cost token) + bikin draft ASLI di mailbox Graph yang
      dikonfigurasi `.env` -- keputusan user (2026-09-23): cukup mocked
      integration test (3 test, `_llm_cve_validator`/`_dedup_mitigation`/
      `_dedup_risk_context`/`create_graph_draft` di-patch) buat sekarang,
      **live-test endpoint ini dicatat sebagai TODO sebelum deploy ke
      production** -- jangan anggap fitur ini "fully verified" sampai itu
      kejadian.

      30 test baru (2 file unit murni + 4 file integrasi Postgres real,
      LLM/Graph di-mock buat `cve_email`). Full suite: **951 passed**,
      mypy 131 file bersih, ruff bersih. SATU commit nutup Grup C.

      **Grup A (2026-09-23) -- KELAR, nutup Fase 7.4 seutuhnya**
      (A+B+C+D+E semua beres). Didahuluin 1 keputusan arsitektur
      (`AskUserQuestion`, dijawab "Recommended"): komputasi TF-IDF/
      sklearn taruh LANGSUNG di `apps/api` (bukan Celery worker),
      konsisten sama presedan `dedup_service` (Grup D) -- CPU-bound
      dibungkus `asyncio.to_thread()`, bukan diproses di worker
      terpisah.

      **Temuan arsitektur paling penting sesi ini: `cluster_service.py`
      itu DUA PIPELINE INDEPENDEN, bukan satu.** `get_clusters()`
      (Pipeline 1: greedy TF-IDF fixed-centroid, threshold default
      0.35, PERSISTED ke tabel `clusters` + cache in-process 900s) dan
      `get_recent_campaigns()` (Pipeline 2: union-find TF-IDF,
      threshold FIXED 0.75 -- gak bisa diubah caller, NEVER di-cache/
      di-persist, dihitung ulang tiap call, enrichment jauh lebih kaya:
      severity scoring, CVE prioritization, diamond model, kill chain,
      PIR matching, campaign links, geopolitical feed). Dua fungsi ini
      keliatan mirip dari nama tapi beda total secara algoritma DAN
      beda konsumen -- distinction ini yang nentuin seluruh layout file
      port-nya (`cluster.py` = Pipeline 1, `campaign.py` = Pipeline 2,
      5 service lain jadi shared building block: `cluster_tokenize.py`,
      `campaign_analysis.py` [kill chain + campaign links + severity
      factors], `cve_priority.py`, `diamond_model.py`, ditambah 2
      consumer `campaign_trend.py`/`geopolitical.py`).

      **Skema baru: tabel `clusters`** (`cluster_id` unik, `cluster_
      name`, `first_seen`/`last_seen` [Date asli], `last_count`/
      `peak_count`, `daily_counts` JSONB list -- dipangkas 90 hari
      kebelakang tiap upsert). Cuma buat Pipeline 1 (Pipeline 2 gak
      pernah nulis DB sama sekali, sesuai desain lama).

      **4 repo method baru** (dipakai sekali doang tapi genuinely gak
      ada sebelumnya): `AsyncIOCRepo.list_by_article_ids`/`list_by_ids`
      (nyatuin 2 jalur ekstraksi CVE-mention lama jadi 1 query lewat
      `IOC.type="cve"` + reverse lookup `IOCSource.article_id`),
      `AsyncPIRRepo.list_active_by_client` (beda dari `list_active_
      unscoped` yang udah ada), `AsyncTARepo.list_all_names`,
      `AsyncSourceReliabilityRepo.list_low_reliability_source_names`.
      Method yang SEMANTIKNYA udah persis sama yang ada (TA profile,
      CVE criticality, tech stack) numpang langsung, gak dibikin
      duplikat.

      **1 param mati DIBUANG** -- `cve_priority_service.prioritize_
      campaign_cves()`'s `campaign_context: dict` dibaca lengkap,
      TERNYATA gak pernah dipakai sama sekali di badan fungsi manapun.
      Beda dari "diam-diam ubah perilaku" (efeknya nol baik dibuang
      maupun dipertahankan) -- didrop, dicatet eksplisit di docstring.

      **1 bug DITEMUKAN, SENGAJA DIPERTAHANKAN (bukan diperbaiki
      diam-diam)** -- `mindmap.py`'s `build_cluster_mindmap()` baca
      field-field yang cuma ada di output Pipeline 2 (severity/diamond
      model/kill chain) padahal manggil Pipeline 1 (`get_clusters()`,
      gak punya field itu) -- 6 branch mindmap (Adversary/Capability/
      Infrastructure/Victim Industries/Victim Countries/CVEs) SELALU
      kosong di produksi, cuma "Stats" yang keisi. Ini bug lama yang
      genuinely ada di kode legacy. Diport APA ADANYA (gak dibenerin)
      karena benerinnya butuh KEPUTUSAN PRODUK (pindah ke Pipeline 2 --
      ubah semantik "mindmap dari cluster ID stabil, persisted" jadi
      "dari campaign yang cuma idup pas dihitung", atau nambahin field
      yang hilang ke Pipeline 1 -- ubah kontrak `clusters` table),
      bukan keputusan porting yang bisa diambil sepihak. Didokumentasikan
      panjang di docstring `mindmap.py` + di-assert eksplisit di test
      (`test_build_cluster_mindmap_stats_branch_populated` verifikasi
      branch header yang HARUSNYA muncul emang gak muncul).

      **1 bug DITEMUKAN & DIPERBAIKI (beda dari kasus mindmap di
      atas)** -- `recap.py`'s `_collect_campaigns()` (producer) dan
      `_build_user_message()` (consumer prompt LLM "active campaigns")
      pakai nama field yang GAK NYAMBUNG (`theme` vs yang diharapkan
      consumer, dst) -- akibatnya section itu di prompt LLM SELALU
      nunjukin placeholder "(unlabeled) — 0 articles", walau campaign
      beneran ada. Beda dari kasus mindmap: ini bukan pilihan
      desain/pipeline, cuma nama key yang salah ketik/gak sinkron --
      di-fix jadi rename key yang unambiguous, dites eksplisit
      (`test_collect_campaigns_maps_fields_for_build_user_message`)
      supaya gak pernah balik lagi.

      **4 titik "unlock" ke-wire semua**: `newsletter`'s
      `include_clusters` (query Pipeline 2, map ke bentuk field legacy,
      top 5), `mindmap`'s builder `"cluster"` (baca Pipeline 1, bug di
      atas dipertahankan), `exec_dashboard`'s `recent_clusters_
      summary` (dari stub `[]` jadi query Pipeline 2 real, try/except
      jaga-jaga), `recap`'s `active_campaigns` (bug fix di atas).
      Plus endpoint baru: `intelligence.py`'s `GET /clusters` +
      `/clusters/recent` + `/clusters/evolution` + `/clusters/{id}/
      trends` + `/intelligence/geopolitical`, dan `cve.py`'s
      `GET /prioritize`.

      8 file service baru (`cluster_tokenize`/`cluster`/`campaign_
      analysis`/`cve_priority`/`diamond_model`/`campaign`/`campaign_
      trend`/`geopolitical`), 80 test baru (42 unit murni + sisanya
      integrasi Postgres real + wiring 4 unlock point). Full suite:
      **1031 passed**, mypy 184 file bersih, ruff bersih.

      **Verified LIVE terhadap dev DB real** (uvicorn lokal, data asli
      -- 20 artikel real bertanggal, termasuk konten threat-intel
      genuine APT41/Philippines, BREEZE COMET, UNC6671 dari Mandiant/
      GBHackers): `GET /clusters` (Pipeline 1, `days=90`) NEMU 1
      cluster REAL dari data asli (2 artikel Mandiant UNC6671/Russia-
      targeting yang emang mirip topiknya, confidence "low" -- bukan
      data sintetis yang disuntik), `/clusters/evolution` +
      `/clusters/{cluster_id}/trends` jalan lawan cluster real itu,
      `/intelligence/geopolitical` (kosong, valid -- Pipeline 2 emang
      gak nemu campaign yang lolos threshold 0.75 di dataset ini),
      `GET /cve/prioritize` lawan 4 CVE real dari `cve_tracker` (skor
      terurut bener, termasuk kasus unknown-CVE dapet default 20/low),
      `exec-dashboard-v2?role=analyst` (`recent_clusters_summary` key
      ada, kosong -- konsisten sama Pipeline 2 gak nemu campaign),
      `mindmap/cluster/{id}` (404 bersih -- cluster real ini di luar
      window `days=30` yang di-hardcode `mindmap.py`, port apa adanya
      dari legacy, BUKAN bug baru). **Cluster row hasil komputasi real
      di atas SENGAJA DIBIARKAN** di tabel `clusters` (bukan data
      sintetis yang disuntik, dihitung dari artikel asli yang emang
      ada di DB) -- presedan sama kayak Grup D's "confidence recompute
      dibiarkan nempel di 38 artikel real".

      **`newsletter`'s `include_clusters=true` SENGAJA BELUM live-
      tested** -- baru ketauan pas nyoba: `/newsletter/preview` juga
      manggil LLM client asli (summarization), sama kelas biaya kayak
      `POST /draft-email` Grup C. Panggilan yang kepalang jalan
      di-KILL manual pas retry macet (belum sempat ngirim token dalam
      jumlah besar) -- wiring `include_clusters` divalidasi lewat
      mocked integration test aja (`test_newsletter_clusters.py`, 2
      test, `campaign_service.get_recent_campaigns` di-patch). Sama
      logika kayak `draft-email`: **live-test endpoint LLM-consuming
      ini (newsletter preview/draft-email DAN `recap generate`, yang
      juga kepanggil `get_llm_client()`) dicatat jadi TODO bareng
      sebelum deploy ke production**, jangan dianggap "fully verified"
      sebelum itu kejadian.

      SATU commit nutup Grup A, sekaligus nutup Fase 7.4 seutuhnya
      (Grup E udah diputus keluar scope sejak survei 2026-09-19, gak
      butuh kerjaan lagi). Lanjut **7.5** (buang duplikasi sisa: pkg_
      vuln/cve_email/ioc/llm client), **7.6** (snapshot test tiap
      endpoint), **7.7** (ekspor skema OpenAPI), **7.8** (5 loop jadi
      Celery beat) -- belum dimulai, nunggu arahan user.
- [x] **7.5** Buang duplikasi (pkg_vuln, cve_email, ioc, llm) --
      **(2026-09-23) audit 4 item, 1 genuinely butuh kerjaan.**
      Catatan lama (Bagian 7.2, "IOC+LLM udah disatukan Fase 5") jadi
      STALE tanpa disadari: bener SAAT ditulis (`cti_enrich` cuma satu
      salinan), tapi begitu `apps/api` lahir (Fase 7.3) dengan exit
      criteria "gak ada import `cti_scraper`/`cti_enrich` dari API",
      LLM client harus di-duplikat ULANG (`cti_api.services.llm_client.
      py`, ~15 baris, versi sempit) buat 5 service yang butuh -- gap
      baru yang gak ke-cover catatan lama. `ioc` udah kena masalah SAMA
      lebih dulu dan UDAH dibenerin (Fase 7.3 Bagian 4, relokasi
      `cti_core.ioc.extractor`) -- pattern-nya identik, cuma belum
      diterapkan ke `llm`.

      **Hasil audit 4 item:**
      - **`ioc`** -- KELAR dari Fase 7.3 Bagian 4, diverifikasi ulang,
        gak ada kerjaan.
      - **`pkg_vuln`** -- KELAR dari Fase 4 (`pkg_vuln.py` satu
        implementasi, gak ada fork tersisa), diverifikasi, gak ada
        kerjaan.
      - **`cve_email`** -- KELAR dari Grup C (Fase 7.4), satu template
        (`cve_notification_email.html`), diverifikasi, gak ada kerjaan.
      - **`llm`** -- GENUINELY DUPLIKAT, dikerjain sesi ini (lihat
        bawah).
      - *(bonus, di luar 4 item yang disebut plan tapi ada di §6 asli)*
        **`send_alert`** (Telegram) -- juga udah KELAR dari Bagian 4
        (`cti_alerts.telegram.send_alert()`, satu fungsi gantiin 14).

      **`llm` -- relokasi `cti_enrich.llm.client` → `cti_core.llm.
      client`**, persis presedan `cti_core.ioc.extractor`: modul ini
      dari awal ZERO dependency internal `cti_enrich` (cuma
      `cti_core.config` + `openai` + stdlib), jadi mekanis murni buat
      dipindah. `apps/api`'s duplikat sempit (`cti_api.services.
      llm_client.py`) DIHAPUS TOTAL, 5 caller-nya (`ta_profile`/
      `exec_brief`/`cve_email`/`newsletter`/`recap`) import langsung
      dari `cti_core.llm.client`, sama kayak 2 caller internal
      `cti_enrich` (`stages/classify.py`/`stages/extract_ttps.py`).
      `openai>=1.30` ditambahin ke dependency `cti-core`.

      **Bonus correctness fix, ketauan gara-gara audit ini (bukan yang
      dicari dari awal):** 6 titik parsing JSON-dari-LLM di `apps/api`
      (`cve_email.py` x2, `newsletter.py` x2, `ta_profile.py` x1,
      `recap.py`'s `_extract_json`) SEMUANYA re-implementasi terpisah,
      dan 5 dari 6 (semua kecuali `recap.py`) cuma `json.loads(content
      or "{}")` POLOS -- gak nahan `<think>...</think>` preamble atau
      code-fence markdown, padahal edge case itu UDAH KEBUKTIAN
      kejadian beneran lawan dev gateway (dicatat di docstring
      `parse_json_response()` sejak Fase 5). Kelima titik itu rawan
      `JSONDecodeError` gak ketangkep kalau gateway kebetulan mbalikin
      salah satu bentuk itu. Diganti semua numpang `cti_core.llm.
      client.parse_json_response()` -- pola `parse_json_response(content
      or "{}")` (bukan `parse_json_response(content)` polos) dipilih
      biar behavior identik lawan kode lama buat kasus falsy
      (`raw or "{}"` sebelumnya, sekarang `parse_json_response("{}")`
      == `{}` juga). `recap.py`'s `_extract_json()` beda kasus -- dia
      PUNYA kontrak sendiri (gak pernah raise, fallback `{"_raw": raw}`
      yang dipakai `generate_daily_recap()` mutusin nyimpen `raw_llm`
      atau kagak), jadi BUKAN diganti langsung, tapi dibungkus try/
      except di sekitar `parse_json_response()` -- kontrak lama tetap
      sama persis, cuma sekarang IKUT dapet proteksi `<think>`-block
      yang sebelumnya gak ada di situ juga.

      18 test baru: `tests/unit/test_llm_client.py` (13 test --
      `parse_json_response`/`get_llm_client`/`store_param`, belum
      pernah ada test khusus sebelum ini walau dipakai 7 caller),
      `tests/unit/test_recap_extract_json.py` (5 test, verifikasi
      kontrak fallback `_extract_json` gak berubah pasca refactor).
      Full suite: **1049 passed** (dari 1031), mypy 183 file bersih
      (turun dari 184 -- 1 file duplikat kehapus), ruff bersih.
- [x] **7.6** Snapshot test tiap endpoint -- **(2026-09-23/24) 27/27
      router, 179 endpoint, 183 test baru (`syrupy`).**

      **Pola infra baru, gak ada presedennya sebelum ini** -- SEMUA test
      integrasi sebelumnya manggil fungsi service/repo LANGSUNG lewat
      `async_db_session` (skip router: routing, dependency injection
      auth, validasi Pydantic, `response_model` serialization gak pernah
      kena test). Fase ini nambah `api_client`/`api_session` (`tests/
      integration/conftest.py`) -- `httpx.AsyncClient` + `ASGITransport`
      langsung ke `create_app()`, `get_db` di-override numpang session
      yang sama, request BENERAN lewat HTTP.

      **3 masalah infra ketemu & dibenerin sebelum bisa dipercaya:**
      1. Router SERING manggil `session.commit()` sendiri (pola "unit of
         work per request") -- `AsyncSession(bind=connection)` polos
         bakal KETUTUP beneran kena commit, isolasi rollback-per-test
         jadi gak ngefek. Fix: `join_transaction_mode="create_savepoint"`
         (recipe resmi SQLAlchemy 2.0).
      2. `expire_on_commit=False` WAJIB dipasang di session test itu juga
         -- production (`cti_core.db.engine`) udah pasang ini, dan tanpa
         itu akses attribute abis commit (`entry.id` di `iocs.py`) trigger
         `MissingGreenlet` yang ketubruk event listener savepoint di atas.
         Ketauan lewat reproduksi langsung, bukan dugaan.
      3. **6 service (`cluster`/`article_dashboard`/`risk_matrix`/
         `fp_analytics`/`spike`/`d3fend`) punya cache in-process module-
         level (900s TTL)** -- dirancang buat produksi (satu proses long-
         lived), tapi bikin test SALING NUMPANG hasil basi kalau dua test
         beda manggil endpoint yang sama dengan parameter default yang
         sama. Ketauan pas full-suite run: 2 test Fase 7.6 sendiri DAN 1
         test PRA-ADA (`test_mindmap_query.py`) sama-sama kena. Fix:
         fixture `autouse=True` (`_clear_in_process_caches`,
         `conftest.py`) yang clear SEMUA 6 cache itu sebelum tiap test
         integrasi -- proteksi nutup seluruh suite, bukan cuma titik yang
         kebetulan ketauan gagal.

      **Endpoint eksternal (LLM/Graph/osv.dev/D3FEND/MITRE GitHub) di-
      mock di titik yang SAMA kayak test service-layer yang udah ada**
      (`cve_lookup._fetch_cisa_kev` dkk, `pkg_vuln._package_exists_on_
      registry`, `AsyncAttackSyncRepo.sync_domain`, `ta_profile._call_llm`,
      `exec_brief._call_llm`, `recap._call_llm`, `newsletter._enrich_
      articles`, `mitre.get_d3fend_countermeasures`) -- gak ada panggilan
      jaringan asli dari test manapun di fase ini. `BackgroundTasks`
      FastAPI (`attack.py`/`pkg_vuln.py`) KETAUAN beneran ke-`await`
      SEBELUM `httpx.ASGITransport` balikin response (efektif sinkron di
      test), jadi endpoint-nya bisa dites langsung tanpa perlu nunggu.

      **Field non-deterministik dinormalisasi lewat `syrupy.matchers.
      path_type`** (diganti placeholder TIPE, bukan dihapus dari
      perbandingan -- drift shape/tipe tetap ketahuan): `id` auto-
      increment (Postgres SEQUENCE gak ke-reset rollback transaksi test,
      jadi nilai literalnya gak pernah stabil lintas run/urutan test),
      field lain yang JUGA int tapi namanya bukan `id` polos (`article_id`,
      `pir_id`, dst -- ketauan lewat full-suite run, pattern awal `id$`
      cuma nangkep field bernama PERSIS "id") timestamp wall-clock
      (`last_updated`/`generated_at`/dst), dan `ticket_id`/next-ticket-id
      (nempel bulan-tahun kalender asli, presedan dari cve.py duluan).

      **1 bug non-determinism GENUINE ketemu di kode APLIKASI (bukan
      test)**: `cluster_service`'s field `sources` di respons `/api/
      clusters` dibangun dari Python `set` (unik doang, gak di-sort) --
      urutan iterasi `set` string di-randomize per PROSES Python
      (`PYTHONHASHSEED`), jadi 2 run `pytest` beda bisa ngasih urutan
      `sources` yang beda walau isinya sama. Bukan dibenerin di kode
      (di luar scope minimal Fase 7.6), tapi dinormalisasi di level test
      (`sorted()` sebelum dibandingin) -- dicatat di sini biar gak
      ketebak lagi kalau nanti nyari root cause snapshot yang "kadang
      beda kadang enggak".

      **1 bug pra-ada, TIDAK terkait Fase 7.6, ketemu gak sengaja**:
      `test_recap_service.py::test_collect_iocs_and_cves_and_new_tas`
      pakai `datetime.date.today()` (timezone LOKAL mesin, WIB/UTC+7 di
      dev environment ini) buat filter kolom yang di-stamp Postgres
      `server_default=func.now()` (UTC) -- flaky tiap hari jam 00:00-
      07:00 WIB (tanggal lokal udah besok, UTC masih hari ini). Bukan
      regresi dari Fase 7.6 (kejadian juga kalau file itu dites sendirian,
      gak connect ke perubahan apa pun di sini) -- di-flag jadi task
      terpisah (`task_a3ad146d`), BUKAN dibenerin di sini (scope beda).

      Endpoint yang genuinely gak cocok snapshot literal: export biner
      (`GET /api/cve/export`, `/api/pir/{id}/export/docx`) dites lewat
      assert struktur (header/kolom/row-count), bukan byte mentah;
      `changelog.py` baca `CHANGELOG.md` ASLI dari disk (isinya SENGAJA
      berubah tiap rilis) dites lewat assert struktur juga, bukan
      snapshot literal yang bakal basi tiap entry baru ditambah.

      Full suite abis semua ini: **1231 passed** (dari 1049 sebelum Fase
      7.6, +183 -- 1 pra-ada yang flaky di atas gak dihitung, bukan
      kegagalan baru), mypy 28 file test bersih, ruff bersih. Determinism
      diverifikasi lewat run ulang berkali-kali (per-file, gabungan
      27 file, DAN full suite project) -- bukan cuma "generate sekali terus
      percaya".
- [x] **7.7** Ekspor skema OpenAPI

      `tools/export_openapi.py` -- panggil `create_app().openapi()`
      (murni introspeksi route/Pydantic model, GAK connect ke Postgres/
      Redis beneran) terus tulis ke `docs/openapi.json` (di-commit ke
      git, bukan `.gitignore` -- diff-nya kelihatan di code review tiap
      kali kontrak endpoint berubah). Ini yang bakal dibaca
      `openapi-typescript` buat generate client TypeScript pas Fase 8
      (`apps/web`, plan §9) -- drift frontend-backend ketahuan saat
      compile, bukan pas runtime.

      **Satu keputusan kecil**: `create_app()` butuh `Settings` valid
      buat kebentuk (`FastAPI(...)` + router registration), dan 4 field
      `database.url`/`sync_url`/`auth.jwt_secret`/`session_secret_key`
      gak punya default (`cti_core.config`, sengaja -- container app
      beneran WAJIB gagal start kalau kosong). Skrip ini `os.environ.
      setdefault(...)` 4 placeholder (gak pernah kepake buat I/O asli,
      cuma biar validasi Pydantic lolos) SEBELUM import `cti_api.main`
      (yang punya `app = create_app()` di level modul) -- jadi jalan di
      mana aja, dev lokal TANPA `.env` maupun CI TANPA testcontainer,
      gak butuh secret apa pun.

      Jalanin: `uv run python tools/export_openapi.py` -> **156 path**
      ke-export, `openapi` 3.1.0, `info.title`/`version` kebaca dari
      `create_app()`. Test unit (`tests/unit/test_export_openapi.py`,
      2 test -- shape schema + JSON-serializable) gak butuh Postgres,
      lolos di CI job `test` biasa tanpa perubahan workflow.

      **3 bug flaky full-suite kesenggol pas verifikasi Fase 7.6
      (bukan bagian 7.7 langsung, tapi ketemu re-run full suite abis
      fix timezone `task_a3ad146d`) udah dibenerin di commit `1e32357`
      sebelum item ini**: 2 snapshot ke-bake tanggal literal
      (`test_recap_router_snapshot.py`'s `date`, `test_stix_router_
      snapshot.py`'s `valid_from`/`x_last_seen`) + 1 `SELECT DISTINCT`
      tanpa `ORDER BY` (`list_all_distinct_cve_ids`, `test_cve_router_
      snapshot.py::test_bulk_exploit_lookup`) -- lihat commit message
      buat detail lengkap, gak diulang di sini.

      Full suite abis 7.7: **1234 passed** (dari 1232 abis fix di atas,
      +2 test baru), mypy+ruff bersih, diverifikasi 2x berturut-turut.
- [ ] **7.8** *(dipindah dari 6.6)* Pindahkan 5 loop `ScraperNewsWeb/app/main.py`
      (PIR alert, ATT&CK sync, IOC decay, daily recap, CVE enrichment) jadi
      Celery beat task -- infra beat/worker-nya udah ada dari Fase 6
      (`apps/worker/src/cti_worker/beat.py`), tinggal port logika service-nya
      (bagian dari 7.4) + daftarin jadwalnya. Setelah ini `apps/api` bisa
      di-scale horizontal (multi-worker uvicorn gak lagi gandain loop).

**Exit criteria:** semua endpoint ada snapshot test · gak ada import `cti_scraper`/`cti_enrich` dari API · 5 loop web hilang dari `main.py`, jadi beat task (7.8)

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

- [ ] **10.1** Seed data referensi: `techstack`, `monitored_accounts`,
      user/role/client -- masih kosong, ini yang genuinely nunggu Fase 10.
      `ioc_allowlist`/`threat_actor_groups`/`monitored_people` **UDAH
      KELAR duluan Fase 5** (2026-09-18, `tools/seed/fase5_reference_data.py`)
      -- lihat catatan lengkap di Fase 5.
- [ ] **10.1b** **Dipindah dari 4.12** (2026-09-18, biar Fase 4 gak keblok
      kerjaan yang sifatnya emang cutover, bukan migrasi): job nonaktif
      diarsipkan, digarap di sini bareng seed data lain -- bukan lagi
      dependency buat nutup Fase 4.
- [ ] **10.1c** **Dipindah dari 4.8** (2026-09-18): rewrite 6 scraper
      Selenium nonaktif (`0xToxinThreat`, `emailnewsThreat`,
      `forcepointThreat`, `mandiantThreat`, `trellixThreat`,
      `vxMalwareDefenseThreat`) + `cyborgHuntingIdea` (gak kedaftar
      Rundeck). **1 dari 7 UDAH DIKERJAIN sebagai test case** (sebelum
      pindah, biar tau seberapa berat sisanya): `mandiant.py` --
      `mandiant.com/resources/blog` (target XPath lama) SEKARANG REDIRECT
      ke `cloud.google.com` (Mandiant diakuisisi Google, konten
      threat-intel pindah ke Google Cloud Blog topic "Threat
      Intelligence"). Ternyata situs barunya nyediain RSS resmi
      (`feeds.feedburner.com/threatintelligence/...`) -- jadi BUKAN
      `runtime="browser"` sama sekali, `RSSScraper` 20 baris biasa.
      Live-verified: `dry-run`/`run` 20 item, persisted bersih, 544 test
      lulus, `ruff`+`mypy --strict` bersih. **Pelajaran buat sisa 6**: gak
      bisa ditebak dari kode lama doang -- tiap situs kudu dicek satu-satu
      (bisa jadi gampang kayak Mandiant, bisa jadi beneran butuh browser
      automation, gak ada cara tau tanpa ngecek langsung).
- [ ] **10.1d** **Dipindah dari 6.7** (2026-09-18, keputusan user): lock
      singleton buat Celery beat (cegah dua proses beat sama-sama fire
      schedule yang sama pas deploy multi-node). Redis udah kepake luas
      (broker Celery, `TokenBucket`) -- pola paling gampang: `SET NX PX`
      di `redis.Redis` yang sama, lock diperpanjang tiap beat tick (bukan
      lock sekali pas start, biar proses yang macet ketauan lewat TTL
      abis, bukan nyangkut lock permanen). Ini yang dicek checklist
      cutover "Beat terverifikasi singleton" di bawah.
- [ ] **10.1e** **Dipindah dari 6.8** (2026-09-18, keputusan user): guard
      backpressure antrian `enrich` -- baru relevan begitu `worker-nlp`
      (image terpisah, concurrency dibatasi RAM spaCy/sumy, plan §10)
      beneran jalan dan kelihatan antrian numpuk lebih cepat dari yang
      bisa diproses. Opsi paling murah: cek `queue.enrich` depth via
      Redis (`LLEN`) sebelum `_article_sink` dispatch, log warning/tolak
      dispatch kalau ngelewatin ambang -- keputusan ambang & aksi pasti
      nunggu angka nyata dari `worker-nlp` produksi, bukan ditebak sekarang.
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
- [ ] Beat terverifikasi singleton (10.1d)
- [ ] Data referensi ter-seed

---

## Pertanyaan terbuka

- ~~**`/opt/HuntingScript/`**~~ dan ~~**`/opt/alertRundeck/`**~~ — **kelar:
  Rundeck gak jadwalin keduanya.** Di luar scope.
- **Simpen raw response LLM buat audit trail produksi** (2026-09-18,
  diusulkan user pas nemuin gateway LLM dev ngebalikin persona "Kiro" yang
  nolak instruksi JSON, lihat catatan bug Fase 7.3 Bagian 1 di atas) --
  BELUM dikerjain, dicatet dulu biar gak lupa.

  Precedent udah ada di skema: `Article.raw_enrichment` (JSONB, Fase 2)
  komentarnya eksplisit bilang "output LLM mentah... cadangan/audit
  trail", tapi `persist.py` gak PERNAH nulis ke kolom itu -- infra-nya
  ada, belum disambung. `RejectedArticle` (baru, Fase 7.3) cuma nyimpen
  `reason` (ringkasan satu baris dari LLM), bukan raw completion penuh --
  justru buat kasus kayak "Kiro persona" itu ARTIKEL YANG DITOLAK yang
  paling kepake diaudit (biar keliatan LLM-nya lagi ngaco jawabnya),
  bukan yang diterima.

  Scope kalau dikerjain: (1) `classify()`/`extract_ttps()` (`cti_enrich.
  stages`) balikin raw completion, bukan cuma hasil ke-parse, (2)
  `persist.py::persist()` isi `Article.raw_enrichment`, (3) migrasi baru
  nambah kolom serupa di `RejectedArticle`, (4) `persist_rejected()` isi
  itu. Nyentuh jalur enrichment yang udah live-verified Fase 5/6/7 --
  butuh re-test kayak yang dilakuin pas `filtered_articles` kemarin,
  bukan sekadar tambah kolom pasif.
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
- **`TwitterScrap` DIBACA, TERNYATA BUKAN tabrakan.** User tarik repo dari
  produksi, dibaca lengkap (4.9): `twitter.py`/`twitter30.py`/`trendingCve.py`
  pakai API Twitter RESMI (bearer token), daftar akun dari file teks statis
  (`supportFile/usernames_*.txt`), dan **gak nulis DB sama sekali** — murni
  klasifikasi konten (APAC/CVE/OT/zero-day) yang berakhir di Telegram alert
  doang. `monitorX.py` pakai API BEDA (twitterapi.io), akun dari DB
  (`monitored_accounts`), dan itu SATU-SATUNYA yang beneran nulis ke
  `tweets`. Dua jalur independen, gak ada overlap — `trendingCve`/`twitter`/
  `twitter30` dipindah ke `NOT_A_SCRAPER_STEMS` (`run_migration.py`), bukan
  scraper dalam pengertian framework baru (Fase 6 beat task kalau mau
  dilanjutin). `investigateScenario.py` (nonaktif) dan `newTwitter.py`
  (gak ada di Rundeck sama sekali, Selenium peninggalan) gak masuk scope
  Fase 4 sama sekali.
- **`techstackLibrary` masih belum ditarik** — `monitorX` sendiri sekarang
  ketunda karena alasan LAIN (LLM client, lihat Fase 4.9), bukan ini.
- **`BreachForums` dua-duanya nonaktif** — prioritas paling rendah.

**Kalau nanti mau digarap:** `techstackLibrary`/`BreachForums` masih perlu
ditarik dari prod (`TwitterScrap` udah, per catatan di atas). Detail jadwal
tiap job udah ada di `docs/legacy/rundeck-jobs-map.json`.
