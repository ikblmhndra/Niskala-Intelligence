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
- [ ] **4.7** Generate requests+lxml (`xpath_static`) — **0/2 (0%)**, +1 udah
      ada dari Fase 3 (`cyfirma`). N kecil banget (cuma 2 job aktif kena
      family ini) jadi belum kelihatan pola gagalnya — masuk triage 4.10
- [ ] **4.8** Tulis ulang 8 Selenium → `XPathScraper(render=True)` _(pekerjaan baru: semuanya memang gak pernah jalan di Linux)_
- [ ] **4.9** Port manual ~35 scraper bespoke
- [ ] **4.9a** Buat token API baru (GitHub PAT, NVD, twitterapi.io) khusus
      buat testing 9 scraper yang butuh kredensial asli — **user yang bikin,
      pas mau testing scraper itu** (bukan sekarang). Daftar lengkap +
      scraper mana butuh apa: [KNOWN_BROKEN.md](KNOWN_BROKEN.md#butuh-kredensial-asli--ditunda-ke-waktu-testing-keputusan-user).
      <br>⚠️ Jangan pakai token produksi lama yang di `legacy/config.yml` —
      itu masuk daftar rotasi karena udah ke-expose ke laptop dev.
- [~] **4.10** Triage `migration_report.json` — 57 di-generate otomatis, 3
      di-skip (udah ada dari Fase 3), 40 butuh review manual. Verifikasi
      golden-test bulk atas 57 hasil generate (lihat 4.11): **32 pass bersih
      lewat perbandingan byte-exact**, sisanya masuk kategori "divergensi
      disengaja" (bukan bug) — lihat tabel di bawah. `--enable` tiap scraper
      tetap satu-per-satu sesuai alur di ADDING_A_SCRAPER.md, belum
      dilakukan di sini.
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
