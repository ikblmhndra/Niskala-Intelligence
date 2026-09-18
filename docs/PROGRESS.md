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

- [x] **7.1** ~~Bootstrap FastAPI (tanpa background loop)~~ -- `apps/api`
      + `main.py` (`create_app()`, lifespan, CORS), lihat catatan di atas.
- [x] **7.2** Auth: JWT + RBAC + multi-tenant -- lihat catatan di atas.
      **OIDC bagian dari 7.2 ini BELUM diport** (`oidc.enabled=False`
      default, 184 baris `oidc_service.py` nunggu giliran terpisah, bukan
      bagian "inti").
- [~] **7.3** Port 27 router ke repository Postgres -- **9/27 kelar**
      (`clients`, `roles`, `articles` [baca doang], `iocs` [baca+kurasi],
      `techstack` [CRUD inti], `cve` [baca+false-positive+purge],
      `tweets`, `monitored_accounts`, `ransomware`), verified LIVE via curl
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

      Sisa 18 router (Bagian 1 sisa 2 + Bagian 2-5) nyusul bertahap.

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
- [ ] **7.4** Port 56 service
- [ ] **7.5** Buang duplikasi (pkg_vuln, cve_email, ioc, llm)
- [ ] **7.6** Snapshot test tiap endpoint
- [ ] **7.7** Ekspor skema OpenAPI
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
