# Nambah Scraper

Dokumen ini **satu jalur buat dua hal**:

- Nambah scraper baru ke platform
- Migrasi scraper lama di Fase 4

Sengaja disamain. Kalau migrasi 91 scraper lama lewat jalur ini kerasa ribet,
berarti nambah scraper baru nanti juga ribet — dan itu masalah utama yang mau
dibenerin revamp ini. **Migrasi = 91 kali uji coba jalur ini.**

Aturannya: **satu scraper = satu file.** Gak ada file lain yang perlu diedit.
Gak ada registry buat didaftarin, gak ada jadwal terpusat, gak ada entri
`pyproject.toml`. Taruh file, selesai.

---

## Alurnya

```
scaffold  ->  isi  ->  dry-run  ->  verify  ->  enable
```

### 1. Scaffold

```bash
cti-scraper new bitdefender --kind rss
```

Bikin `scrapers/feeds/bitdefender.py` yang udah bisa jalan, isinya metadata
minimum. `--kind`: `rss` | `xpath` | `api`.

### 2. Isi

Buat RSS, biasanya cuma segini:

```python
class Bitdefender(RssScraper):
    meta = ScraperMeta(
        id="bitdefender",
        source="Bitdefender",
        schedule="30 * * * *",
        tags=("vendor",),
    )
    feeds = ("https://www.bitdefender.com/blog/api/rss/labs/",)
```

Buat XPath, tambahin `url` + dua selector. Buat API, override `fetch()`.

### 3. Dry-run — jalanin beneran, gak nulis apa-apa

```bash
cti-scraper dry-run bitdefender
```

Ngambil dari sumber aslinya, nampilin item yang kebaca, **gak nyentuh
database, gak ngirim alert, gak nandain dedup**. Ini yang dipakai buat
mastiin selector-nya bener sebelum dinyalain.

Ini juga yang sekarang gak ada sama sekali. Dulu satu-satunya cara nguji
scraper adalah nyalain di produksi dan nungguin.

### 4. Verify — bandingin sama baseline

```bash
cti-scraper verify bitdefender
```

Ngasih plugin baru **byte HTTP yang sama persis** dari fixture Fase 0, lalu
bandingin item yang dihasilkan sama `expected_items.json`.

- **Scraper hasil migrasi**: wajib lolos. Ini gate-nya.
- **Scraper baru**: belum ada fixture, jadi `verify` bakal ngerekamnya sebagai
  baseline pertama. Mulai run berikutnya, dia ikut ke-regression-test.

URL dibandingin pakai `canonicalize_url`, bukan string mentah — kode baru
sengaja ngenormalisasi. Judul dibandingin persis.

### 5. Enable

```bash
cti-scraper enable bitdefender
```

Nyalain di control plane. Beat langsung ngambil jadwalnya tanpa perlu deploy
ulang — `MongoScheduler` baca ulang tiap 60 detik.

---

## Yang ditangani framework

Jangan tulis ini di file scraper. Semua udah dihandle:

| | Ditangani di mana |
|---|---|
| Dedup | `runner` — reserve sebelum proses, commit setelah sukses |
| Retry + backoff | task Celery, cuma buat error transient |
| Rate limit | token bucket Redis, **per-domain** (bukan per-scraper) |
| Heartbeat per-run | `runner` — `items_found`, `items_new`, status, traceback |
| Logging | structlog, udah ke-bind `scraper_id` + `run_id` |
| Simpan | sink registry, dipilih dari tipe item yang di-`yield` |
| Alert | terpisah dari simpan, task Celery sendiri |
| Jadwal | `meta.schedule`, beat baca dari registry |

Yang lu tulis cuma `fetch()`. Itu doang.

**Jangan nulis `try`/`except` buat nutupin error.** 166 dari 241 scraper lama
gak punya penanganan error sama sekali, dan yang punya kebanyakan malah
`except Exception: pass` — bikin scraper rusak gak bisa dibedain dari yang
sehat. Framework yang nangkep, ngeklasifikasi, dan nyatet. Lempar
`ParseError` kalau dokumennya kebaca tapi strukturnya gak sesuai — itu berarti
situsnya berubah, dan orang harus lihat, bukan di-retry tiga kali.

---

## Kasus yang gak standar

Scraper yang nulis bentuk dokumen sendiri (ransomware.live, NVD) **gak
perlu jalan keluar khusus** — dia cukup `yield` tipe item yang beda:

```python
def fetch(self, ctx):
    yield RansomwareVictimItem(group_name=..., victim=...)
```

Sink registry yang nentuin tujuannya dari tipe item. Gak ada
`if scraper.is_special` di mana pun. Kalau butuh tujuan yang belum ada,
daftarin `@sink_for(ItemKu)` di file yang sama — tetap satu file.

---

## Definisi selesai

Scraper dianggap beres kalau:

- [ ] `cti-scraper dry-run` ngeluarin item yang bener
- [ ] `cti-scraper verify` lolos (migrasi) atau bikin baseline (baru)
- [ ] `meta.schedule` sesuai jadwal Rundeck aslinya (`rundeck-jobs-map.json`)
- [ ] `meta.runtime` cocok sama caranya ngambil (`browser` kalau butuh render)
- [ ] Contract test lolos: `pytest tests/contract -k <id>`
- [ ] Gak ada `try`/`except` yang nelen error
- [ ] Gak ada file lain yang diedit

Kalau langkah mana pun kerasa maksa waktu migrasi, **itu bug framework, bukan
bug scraper.** Benerin framework-nya, jangan diakalin di file scraper — file
ke-92 bakal kena masalah yang sama.
