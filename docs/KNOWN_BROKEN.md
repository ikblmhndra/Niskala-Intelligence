# Script Lama yang Rusak

Script yang terbukti rusak **sebelum** rewrite. Penting karena:

- Script rusak **gak butuh golden test** — gak ada perilaku benar yang mau
  dipertahankan, jadi gak usah jadi gate cutover.
- Bug-nya **jangan ikut ke-port** ke plugin baru.
- Sebagian mungkin lebih baik dibuang daripada ditulis ulang.

Status: `CONFIRMED` = diverifikasi langsung dari source atau dari eksekusi.

---

## Crash total

### `securityaffairsThreat.py` — `CONFIRMED`
```
NameError: name 'html' is not defined
```
Pakai `html.fromstring()` tapi gak pernah `from lxml import html`.
`requestsTemplate.py:4` punya import itu; file ini menghilangkannya waktu
di-copy. **Crash tiap kali cron jalan, diam-diam, selamanya.**

Framework baru ngilangin seluruh kelas bug ini — `XPathScraper` yang import
`lxml.html`, bukan file scraper-nya.

### `theRecordThreat.py` — `CONFIRMED` (temuan baru)
```
5 item ke-push, lalu: NameError: name 'message_list' is not defined
```
Jalan **separuh**: berhasil push 5 artikel terus crash. Karena
`is_new_and_mark` udah nandain semua key sebelum crash, artikel yang gagal
gak akan pernah dicoba ulang. Ini persis kegagalan "mark sebelum proses" yang
dibenerin dedup two-phase.

---

## Rusak diam-diam (jalan, tapi salah)

### `cisacatalogThreat.py` — `CONFIRMED`
Ngeluarin label tanpa kata literal `"FROM"`:
- `"NEW CISA CATALOG VULNERABILITY"`
- `"NEW CISA CATALOG VULNERABILITY (RELATED)"`

`nlp.py:341` ngelakuin `str(script_name).upper().split("FROM")[1]` → `IndexError`
→ **tiap job dari scraper ini mati di worker.** 3 dari 198 label kena.

Juga ada cabang mati di L40-51: kedua sisi if/else identik kecuali string label.

### `nlp.py:421` — `CONFIRMED`
```python
zero_day_list = re.findall(r"\\b(zero|0)[-.]day\\b", ...)
```
Raw string, jadi `\\b` dibaca literal backslash+`b`, bukan word boundary.
**Deteksi zero-day gak pernah cocok.**

> Diverifikasi: L35/396/400/414 pakai f-string **non-raw** di mana `"\\b"`
> jadi `\b` yang benar. **Jangan ikut diubah.**

### `articleValidator.py:141-146` — `CONFIRMED`
Parse output LLM lewat `.replace("\n","").replace("```","").replace("json","")`
lalu `json.loads` **dua kali**. Artikel yang judulnya mengandung kata "json"
bikin parsing rusak.

### `supportFile/offsetAlert.py` — `CONFIRMED`
Satu-satunya detektor scraper mati yang pernah ada. Shell out ke
`find offset/ -mtime +30`. **Rusak diam-diam** waktu dedup pindah ke Mongo —
file offset berhenti disentuh, jadi semua scraper kelihatan mati. Juga pakai
`stat --format` (GNU) dan hardcode `+0700`.

---

## Gak bisa jalan di host deploy

### 8 scraper Selenium — `CONFIRMED`
```python
CHROMEDRIVERLOC = "./chromedriver_mac64_arm64/chromedriver"
```
Binary **macOS ARM64**, di repo yang deploy ke Linux `/opt`. Kedelapan scraper
ini **gak pernah bisa jalan di produksi**.

Artinya waktu ditulis ulang jadi `XPathScraper(render=True)`, itu **pekerjaan
baru, bukan migrasi** — gak ada baseline buat dibandingin, jadi gak bisa
di-golden-test. Perlakukan sebagai fitur baru dengan penerimaan manual.

### `supportFile/nlp_worker.service` — `CONFIRMED`
`ExecStart` nunjuk ke `supportFile/nlp_worker.py`, padahal file-nya di root
repo. Dengan `Restart=always`, unit ini **crash-loop selamanya**.

---

## Cara nambah ke daftar ini

Perekam fixture nyari yang beginian otomatis. Setelah tiap run:

```bash
python3 -c "
import json,sys
for r in json.load(open(sys.argv[1])):
    if r['status'] not in ('ok',): print(r['scraper'], r['status'], (r.get('error') or '')[:80])
" fixture_report.<tanggal>.json
```

---

## Hasil final perekaman Fase 0.5 (2026-09-16 & 17)

**53 dari 96 job aktif (55%) punya baseline valid** (`ada_item`). Di bawah
target awal (≥85), tapi sesuai keputusan: sisanya **gak ngeblok** — masuk
alur `dry-run`/`verify` satu-per-satu pas gilirannya di Fase 4
(lihat [ADDING_A_SCRAPER.md](ADDING_A_SCRAPER.md) — `verify` ngerekam
baseline live kalau belum ada).

| Kategori | Jumlah | Tindakan |
|---|---|---|
| Ada item, baseline valid | **53** | Siap jadi gate golden-test |
| Ada direktori, 0 item kedua hari | 38 | Cek satu-satu pas Fase 4 (tabel di bawah) |
| Gak ada direktori sama sekali | 5 | Rekam pas Fase 4, gak ada yang aneh, cuma belum kebagian giliran |

### Butuh kredensial ASLI — ditunda ke waktu testing (keputusan user)

9 scraper gak bisa dikasih baseline valid dengan config dummy — dites pakai
token kosong, semuanya kena block/error dari API-nya (GitHub 401/403, NVD
kosong, twitterapi.io butuh key berbayar). **User akan buat token baru nanti
pas mau testing scraper ini, bukan sekarang:**

| Scraper | Butuh | Hasil dgn token kosong |
|---|---|---|
| `githubTTPs`, `mitreGithub`, `blackorbirdGithub`, `githubAptTTPSimulation`, `githubSophoslab`, `deepdarkCTI`, `githubUnit42` | GitHub PAT | Diblokir 401/403 (rate limit anonim) |
| `githubPOCMonitor` | GitHub PAT + akses baca `cve_tracker` (buat filter FP) | Diblokir + `ConnectionError` |
| `newCveThreat` | NVD API key | `TypeError: NoneType` (respons kosong) |
| `monitorX` | Key twitterapi.io | `TypeError` (respons bukan JSON yang diharap) |

⚠️ **`newCveThreat.py` dan `githubPOCMonitor.py` bikin `MongoClient` langsung
dari config — JANGAN kasih config asli ke harness perekam.** `pymongo.MongoClient`
udah ditambal jadi inert di `record_fixtures.py`, jadi aman walau dua file
ini dites — tapi kalau nanti diverifikasi manual di luar harness (bukan lewat
`record_fixtures.py`), pastikan tetap lewat `dry-run` yang frameworknya
nyediain sink aman, bukan jalanin script mentahnya langsung.

### Error asli, bukan dependency — cek satu-satu

| Scraper | Error | Dugaan |
|---|---|---|
| `landthThreat` | `IndexError: list index out of range` | Kemungkinan bug beneran — pola sama kayak `securityaffairsThreat` |
| `techstackGO`, `techstackNPM`, `techstackPYPI` | `ValueError: time data '...571293679Z' does not match format` | **Bug asli.** `%f` di `strptime` cuma baca 6 digit mikrodetik, API balikin 9 digit (nanodetik). Perlu ganti ke `datetime.fromisoformat` atau potong presisinya. |
| `groupibThreat`, `cisThreat`, `cymruThreat`, `anyrunTrendThreat`, `k7securityThreat` | `TimeoutError: Page.goto 30000ms` | Bisa situs lambat, bisa juga efek `--jobs 8` (8 Chromium bareng di laptop) — coba serial dulu sebelum simpulin situsnya emang lambat |
| `intel471Threat` | timeout (90s) | Sama kemungkinannya |
| `prodraftThreat` | `TargetClosedError` (Playwright) | Browser crash di tengah run; coba ulang dulu |

### Nol item, belum jelas sah atau rusak

Satu udah kebukti **sah**: `crowdstrikeThreat` nyaring kategori
`"Counter Adversary Operations"` — feed-nya punya 1 item hari itu, cuma gak
lolos filter. Bukan bug. `threatActorTrendGraylog` juga kemungkinan sah (baca
`supportFile/ThreatActorName.txt` yang bisa aja lagi kosong).

Sisanya belum dicek: `anyrunTrendThreat`, `doyensecThreat`, `googleThreat`,
`huntressThreat`, `abnormalsecurityThreat`, `aquasecThreat`,
`nquiringMindsThreat`, `dragosThreat`, `blackberryThreat`, `huntioThreat`,
`sysdigThreat`, `trustwaveThreat`, `splunkThreat`, `koisecThreat`,
`proofpointThreat`, `sansThreat`.
