# Banding Legacy vs Platform Baru (sebelum legacy dimatikan)

Ceklis ini dipakai SETELAH platform baru jalan paralel di samping app legacy (keputusan user
2026-09-30: staging jadi kandidat produksi, legacy TIDAK dimatikan langsung -- dibandingin dulu).
Beda dari `CUTOVER_RUNBOOK.md` 10.6/10.7 (pantau 4 jam + hypercare 1 minggu, itu ngecek platform
baru SEHAT SENDIRIAN -- queue depth, error log, resource) -- dokumen ini ngecek platform baru
ngasilin **output yang konsisten sama legacy** buat sumber yang sama di periode yang sama. Dua-duanya
dipakai bareng, bukan pengganti satu sama lain.

> **Status prasyarat (2026-10-01):** fix QA 10.H (`docs/PROGRESS.md`) sudah ke-merge DAN sudah
> ke-deploy ke staging (~08:40 UTC, DB `c3a7e9d1f2b4`, `threat_actor_groups` 3995, beat + watchdog
> aktif). Prasyarat yang tersisa di §0: data/kredensial uji dibersihkan, keputusan aturan TTP, dan
> kredit twitterapi.io. Banding TTP khususnya perlu hati-hati -- remap staging menghasilkan beberapa
> label janggal (lihat `PROGRESS.md` 10.H, "Kualitas remap TTP").

---

## 0. WAJIB dicek SEBELUM mulai banding (sekali, bukan harian)

> ⚠️ **Risiko terbesar periode paralel: user asli kebanjiran alert DOBEL.** Kalau platform baru
> dan legacy dua-duanya ngirim ke channel/thread Telegram PRODUKSI yang sama buat artikel yang
> sama, tiap berita nyampe 2x. Cek SEKALI sebelum mulai:

- [ ] `.env` platform baru (di host yang jadi kandidat prod ini) pakai `TELEGRAM__BOT_TOKEN` /
      `TELEGRAM__CHAT_ID` **BEDA** dari yang dipakai legacy, ATAU kalau sengaja pakai channel yang
      sama, matiin dulu pengiriman salah satu sisi sampai periode banding kelar (legacy biasanya
      lebih gampang: `systemctl stop` / disable job Rundeck yang ngirim, TANPA matiin scraping-nya
      -- kalau ada cara begitu; kalau enggak, platform baru yang diarahkan ke chat test dulu).
      Cek TANPA nge-print token: `grep -q "^TELEGRAM__BOT_TOKEN=." .env && echo terisi`.
- [ ] Kedua sistem nge-scrape sumber yang **sama** (bukan subset beda) buat periode banding --
      cross-check scraper yang `enabled=True` di platform baru vs job yang masih aktif di Rundeck
      legacy (`docker exec cti-worker python -c "from cti_scraper.registry import discover;
      [print(c.meta.id) for c in discover()]"` vs daftar job Rundeck aktif).
- [ ] Sepakati **zona waktu** pembanding -- platform baru jalan UTC (beat), legacy kemungkinan
      jalan jam lokal server (cek `date` di host legacy). Salah asumsi = "beda 1 hari" yang keliatan
      kayak bug tapi cuma offset jam.
- [x] **Fix QA 10.H sudah ke-deploy + post-deploy dijalankan** -- DIPENUHI di staging 2026-10-01
      ~08:40 UTC (lihat `docs/PROGRESS.md` 10.H). Cek ulang tiap kali host di-deploy ulang atau
      dipindah: tanpa ini banding TA/Risk Matrix/PIR/TTP gak ada artinya (sebelum deploy
      `threat_actor_groups` KOSONG: dropdown TA kosong, PIR berbasis TA 0 artikel, TTP belum dinormalisasi).
      ```bash
      PSQL="docker compose --env-file docker/stack.env --profile app exec -T postgres psql -U cti -d cti -tAc"
      $PSQL "SELECT version_num FROM alembic_version"      # harus c3a7e9d1f2b4 (atau lebih baru)
      $PSQL "SELECT count(*) FROM threat_actor_groups"     # harus > 0 (harapan ~3991)
      ```
- [ ] **Scheduler (beat) sehat dan tetap sehat** -- lihat §1a. Kalau beat mati sebentar pun, hari itu
      jangan dihitung sebagai data banding (staging pernah mati ~97 jam tanpa ada yang sadar).
- [ ] Data uji dan kredensial uji di host kandidat prod sudah dibersihkan (whitelist TA `testactor`/
      `testing`, password `stg-admin` + sisa kredensial dev Fase 9) -- data uji yang ikut kebawa bikin
      hitungan platform baru "lebih banyak" dari legacy tanpa alasan nyata.
- [ ] Versi yang jalan di host = `origin/main` yang dimaksud. Staging itu **file-sync, bukan git
      checkout**: `git log` di host gak bisa dipercaya, pakai revisi DB (cek di atas) + tag image
      sebagai patokan.

---

## 1. Coverage artikel per scraper/source (paling penting, cek harian)

Tujuan: buktikan platform baru nangkep artikel yang SAMA, bukan cuma "sama-sama ada artikel masuk".

```bash
# Legacy (Mongo) -- jumlah artikel per source, hari tertentu. `posted_on` DI MONGO TERSIMPAN
# SEBAGAI STRING "YYYY-MM-DD" (diverifikasi langsung dari dump 2026-09-30), BUKAN tipe Date --
# bandingin string, JANGAN new Date(...) (beda tipe = query diam-diam gak match apa pun).
mongosh "$MONGO_URI" --quiet --eval '
db.getSiblingDB("news_db").articles.aggregate([
  { $match: { posted_on: { $gte: "2026-10-01", $lt: "2026-10-02" } } },
  { $group: { _id: "$source", n: { $sum: 1 } } },
  { $sort: { _id: 1 } }
]).forEach(r => print(r._id + "\t" + r.n))'

# Platform baru (Postgres) -- setara, per scraper_id. Pakai `posted_on` (BUKAN `created_at`) --
# buat scraper yang `date_path=None` (mayoritas) dua-duanya = waktu scrape, jadi field yang
# sebanding; `created_at` di Postgres ngukur waktu insert baris, beda semantik dari `posted_on`
# legacy.
docker compose --env-file docker/stack.env --profile app exec -T postgres \
  psql -U cti -d cti -c "
    SELECT scraper_id, count(*) FROM articles
    WHERE posted_on >= '2026-10-01' AND posted_on < '2026-10-02'
    GROUP BY scraper_id ORDER BY scraper_id;"
```

- [ ] Jalanin tiap hari selama periode banding, bandingin 2 tabel di atas per baris.
- [ ] **Nama `source`/`scraper_id` gak selalu identik** (rebrand, dsb) -- lihat
      `tools/seed/fase10_warm_start.py` (`ALIASES` dict) buat pemetaan label lama -> id baru yang
      udah dikonfirmasi sebelumnya. Kalau nemu source baru yang beda tapi BUKAN di `ALIASES`, itu
      temuan baru, catat.
- [ ] Selisih kecil (1-3 artikel/scraper/hari) WAJAR -- beda waktu polling pas ambil snapshot.
      Selisih besar (scraper ada di satu sisi, nol di sisi lain) = investigasi scraper itu
      (cek `/scrapers` dashboard buat status live-nya).
- [ ] Scraper yang di platform baru statusnya `enabled=False`/dropped/diparkir (trellix,
      vxMalwareDefenseThreat, emailnewsThreat, cyborgHuntingIdea -- lihat `docs/PROGRESS.md`
      10.1c; plus 5 waiver census 10.I: `blackberry`, `koisec`, `google`, `cisa`, `nquiring_minds`)
      **WAJAR nol di platform baru, non-nol di legacy** -- itu bukan bug, udah jadi keputusan
      sadar. Jangan dihitung sebagai gap.
- [ ] **Scope SENGAJA beda dari legacy** (census 10.I, 2026-10-01) -- jumlah artikel per hari boleh
      beda, itu bukan scraper hilang:
      - `cloudflare`: dulu laporan resource-hub, sekarang tag `security` di blog.
      - `intel471`: dulu whitepaper, sekarang blog (dan **belum stabil**: Vercel 429 -- nol artikel di
        sini = cek status run dulu, bukan otomatis bug).
      - `huntress`, `sysdig`, `cymru`: feed SELURUH blog, tanpa filter kategori lama.
      - `sans`: SEMUA white paper, bukan cuma focus-area yang dulu.
      - `landth`: domain jadi `depi.security` (sumber diberi label "Depi (dulu L&H)"); artikel lama
        ada di host berbeda, jadi jangan dicocokkan lewat URL.
      - `sentinel`, `crowdstrike`: taksonomi kategori baru (kategori lama sudah tidak ada di situsnya).
      - `monitor_x`: sekarang gagal keras kalau kredit twitterapi.io habis; legacy diam-diam kosong.
        Jadwal 2026-10-02 disamakan dgn legacy (tiap 3 jam, `8 */3 * * *`); sebelumnya `*/15`, jadi
        data tweet sebelum tanggal itu lebih rapat dari legacy -- jangan dibandingkan per jam.
- [ ] **Perbedaan data yang DIKETAHUI dari QA staging 2026-10-01** (laporan B, `docs/PROGRESS.md`
      10.H) -- catat sebagai kategori sendiri, jangan dikira scraper hilang:
      - Judul artikel masih berupa **nama file** (`2026-09-28-AgtaBackup-RAT-Campaign.txt`, dst) dari
        watcher GitHub (`unit42_github`, `blackorbird_github`) -- legacy kemungkinan sama/beda, cek dulu
        sebelum dianggap bug baru. `posted_on` bisa kosong (`""`) di beberapa artikel.
      - **HTML entity belum ke-decode di judul** (B12) -- judul yang sama bisa kelihatan beda antara
        legacy dan baru kalau dibandingin teks-per-teks (§6).
      - Klasifikasi APAC/Global meleset di beberapa artikel (B14) -- itu beda hasil enrichment, bukan
        beda coverage; jangan dihitung di §1.

## 1a. Kesehatan scheduler (cek harian, SEBELUM percaya angka §1)

Angka coverage cuma valid kalau beat jalan sepanjang hari yang dibandingin. Cek:

```bash
# 1) container beat nyala? (harus Up, bukan Exited)
docker compose --env-file docker/stack.env --profile app ps beat

# 2) run 24 jam terakhir -- seharusnya hampir semuanya `beat` (+ `beat_retry`); kalau yang dominan
#    `manual`, beat gak jalan dan ada yang trigger manual (itulah gejala insiden staging 26-30 Sep)
docker compose --env-file docker/stack.env --profile app exec -T postgres \
  psql -U cti -d cti -c "
    SELECT trigger, count(*) n, max(started_at) last
    FROM scraper_runs WHERE started_at > now() - interval '24 hours'
    GROUP BY trigger ORDER BY n DESC;"

# 3) heartbeat segar? (ada setelah fix 10.H ke-deploy). Nilai JSON {"last_tick": iso, "started_at": iso};
#    `last_tick` harus <5 menit dari `date -u` sekarang. Key kosong = beat belum pernah jalan dgn kode
#    baru; nilai basi TANPA TTL itu disengaja (informasinya justru "terakhir hidup jam segini").
docker compose --env-file docker/stack.env --profile app exec -T redis redis-cli get cti:beat:heartbeat
```

- [ ] Baseline terakhir diverifikasi (2026-10-01 ~07:40 UTC, SEBELUM fix 10.H ke-deploy): beat `Up 14
      hours`, 1837 run/24 jam semuanya `beat`, terakhir 07:38 UTC. Sebelum 30 Sep 17:17 UTC beat
      mati ~97,6 jam dan cuma ada run `manual`.
- [ ] Banner merah "scheduler mati" di `/scrapers` TIDAK muncul, dan thread Telegram `scraper_health`
      tidak ada pesan "Scheduler (beat) MATI/MACET" yang belum ada "PULIH"-nya (butuh fix 10.H).
- [ ] Hari yang beat-nya sempat mati/restart panjang **ditandai dan dikeluarkan** dari hitungan "3 hari
      hijau" di §7 -- bukan dicoret diam-diam, catat tanggalnya.

## 2. CVE tracker

```bash
# `detected_on` (STRING "YYYY-MM-DD HH:MM:SS", diverifikasi dari dump 2026-09-30) = kapan LEGACY
# nge-track CVE ini -- setara `created_at` Postgres. JANGAN pakai `published` (itu tanggal publish
# CVE-nya sendiri dari NVD/vendor, gak ada hubungannya sama kapan sistem kita nge-track).
mongosh "$MONGO_URI" --quiet --eval '
db.getSiblingDB("news_db").cve_tracker.countDocuments({
  detected_on: { $gte: "2026-10-01", $lt: "2026-10-02" }
})'

docker compose --env-file docker/stack.env --profile app exec -T postgres \
  psql -U cti -d cti -c "
    SELECT count(*) FROM cve_tracker
    WHERE created_at >= '2026-10-01' AND created_at < '2026-10-02';"
```

- [ ] Jumlah CVE baru per hari sebanding.
- [ ] False positive flag: sample beberapa CVE yang di-flag FP di satu sisi, cek statusnya di sisi
      lain -- beda logika FP (kalau ada) ketauan dari sini, bukan cuma count.

## 3. IOC

```bash
docker compose --env-file docker/stack.env --profile app exec -T postgres \
  psql -U cti -d cti -c "
    SELECT type, count(*) FROM iocs
    WHERE created_at >= '2026-10-01' AND created_at < '2026-10-02'
    GROUP BY type ORDER BY type;"
```

- [ ] Sisi legacy PERLU dicek dulu koleksi mana yang representasi "IOC baru ke-ekstrak dari
      artikel", BUKAN diasumsikan `threatintel.hash`/`ip`/`domain` (koleksi itu keliatan lebih ke
      reference/allowlist data, bukan log ekstraksi harian -- cek dulu apakah field tanggalnya
      ada dan masuk akal buat query per-hari sebelum jadiin baseline banding). Kalau legacy gak
      punya "IOC baru per hari" yang jelas, bagian ini boleh diskip -- IOC platform baru DIEKSTRAK
      OTOMATIS dari artikel (fitur baru, `cti_enrich`), beda arsitektur dari legacy yang sepertinya
      manual/allowlist-based.

## 4. Twitter/X intel (`monitor_x`)

- [ ] Jumlah tweet yang kecatet per akun yang dipantau, periode yang sama.
- [ ] **Perhatian khusus**: `monitor_x` di platform baru kena rate limit twitterapi.io (sudah
      ada pacing/backoff, lihat `docs/PROGRESS.md`) -- kalau tweet dari akun tertentu SELALU
      lebih sedikit dari legacy secara konsisten (bukan cuma sesekali), itu tanda pacing-nya
      belum cukup, bukan cuma noise.
- [ ] **Kredit twitterapi.io harus ada dulu.** QA 2026-10-01: `monitor_x` kena HTTP 402 "Credits is
      not enough" -- selama kredit habis jumlah tweet platform baru nol dan itu BUKAN gap scraper.
      402 juga belum diklasifikasi terpisah dari `rate_limited` di kode (`_twitterapi.py` gak punya
      penanganan 402), jadi di dashboard keliatannya sama dengan kena rate limit -- cek pesan error
      di detail run, bukan cuma statusnya.

## 5. Laporan terjadwal

Bandingin ISI (bukan cuma "terkirim"), periode yang sama -- daftar lengkap jadwal & topik ada di
`CUTOVER_RUNBOOK.md` 10.7:

- [ ] Counter harian (`debug`) -- angka total artikel/hari sebanding sama hitungan §1.
- [ ] News of the day (`notd`) -- daftar judul yang nongol masuk akal (gak kosong, gak duplikat
      aneh).
- [ ] Logbook 2-mingguan -- isi laporan (jumlah insiden per kategori) sebanding.
- [ ] Top CVE mingguan / tren threat actor -- angka top-N sebanding (urutan boleh beda dikit kalau
      algoritma scoring beda, tapi item TOP harus overlap besar).
- [ ] **Threat actor/Risk Matrix cuma sebanding untuk artikel yang masuk SETELAH seed.** Backfill 10.H
      mencocokkan TA ke **judul** artikel lama saja (ringkasan gak tersimpan), jadi artikel lama dapat
      lebih sedikit TA daripada legacy -- itu keterbatasan yang diketahui, bukan bug. Banding TA pakai
      jendela waktu SETELAH seed jalan. Risk Matrix di-cache 15 menit per proses API: restart `api`
      setelah backfill, atau tunggu.
- [ ] **TTP: jangan banding nama, banding `ttp_id`.** Fix 10.H menormalisasi TTP ke katalog ATT&CK
      (teknik revoked/nama lama dipetakan, nama taktik dibuang, ID vs nama bentrok = nama menang).
      Legacy masih bawa label LLM mentah yang kadang salah (mis. `T1110` dilabel "Credential
      Dumping"), jadi heatmap sengaja gak akan identik -- cukup cek jumlah per `ttp_id` wajar dan gak
      ada kolom ganda.

## 6. Spot-check integritas field

Ambil 5-10 artikel ACAK dari satu scraper yang sama, satu hari yang sama, bandingin field-by-field
(title, url, posted_on) antara Mongo dan Postgres -- bukan cuma count yang cocok, tapi ISINYA juga
bukan hasil kebetulan jumlahnya sama padahal artikelnya beda.

## 7. Kriteria durasi & kapan "aman" matikan legacy

- [ ] Jalan paralel **minimal 1 minggu penuh** (biar kena laporan mingguan/2-mingguan sekali
      putaran, dan variasi hari kerja vs weekend) -- selaras rekomendasi hypercare 10.7.
- [ ] §1-§6 di atas HIJAU (selisih wajar, bukan gap) selama **minimal 3 hari berturut-turut**
      terakhir sebelum keputusan matiin legacy -- sekali hijau doang gak cukup, butuh konsisten.
      Hari yang gagal §1a (beat mati/restart panjang) TIDAK dihitung dan hitungan 3 hari mulai ulang.
- [ ] Tidak ada alert "Scheduler (beat) MATI/MACET" tanpa "PULIH" selama periode banding, dan fix 10.H
      sudah ke-deploy (tanpa itu beat mati lagi = diam-diam, kayak 26-30 Sep).
- [ ] Drill restore Mongo + rollback stack lama ke Rundeck **sudah dites** (lihat
      `docs/PROD_PREP.md` -- per 2026-09-30 restore-nya udah dites di staging, rollback drill di
      PRODUKSI belum) -- kalau keputusan matiin legacy ternyata salah, jalur baliknya harus udah
      kebukti jalan, bukan cuma didokumentasikan.
- [ ] Semua orang yang butuh akses platform baru (analyst, siapa pun yang biasa baca dashboard
      legacy) udah punya akun & sudah coba login beneran -- bukan asumsi "nanti juga bisa".

---

**Setelah semua di atas hijau konsisten:** lanjut ke `CUTOVER_RUNBOOK.md` bagian cutover beneran
(10.3: stop cron lama). Kalau ADA yang merah berulang, JANGAN matiin legacy -- investigasi dulu
gap-nya sampai jelas akar masalahnya (selector rusak / bug beneran / memang keputusan sadar seperti
trellix/vxMalwareDefense yang di atas).
