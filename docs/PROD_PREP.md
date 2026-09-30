# Persiapan produksi (Fase 10.F) -- 4 langkah yang cuma bisa dijalankan di host produksi

Empat item ini butuh akses ke host produksi lama/baru yang tidak dimiliki asisten yang menulis
dokumen ini -- jadi ini panduan langkah-demi-langkah buat DIJALANKAN MANUAL, bukan sesuatu yang
sudah dieksekusi. Urutan pengerjaan bebas, keempatnya independen satu sama lain.

> Aturan main yang sama seperti dokumen lain: jangan pernah menempel/menyalin isi `.env`, `config.yml`,
> atau nilai secret apa pun ke chat/tiket/log. Cek keberadaannya dengan `grep -q "^KEY=." file`, bukan
> dengan mencetak nilainya.

---

## 1. Backup Mongo + drill restore (checklist "Backup Mongo <24 jam, sudah dites restore")

Mongo (`mongod`) jalan LOKAL di host produksi lama (dari `legacy/config.yml`: cluster `threatintel`,
plus database `news_db` yang dipakai `ScraperNewsWeb`). Alat: `mongodump`/`mongorestore` bawaan Mongo --
tidak perlu tool baru, sudah cukup untuk kebutuhan sekali pakai ini.

```bash
# --- di host produksi lama ---
BACKUP_DIR=/var/backups/mongo-cti/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"

# Dump KEDUA database (news_db dipakai ScraperNewsWeb, threatintel dipakai scraper) --
# --uri baca kredensial dari environment/config, JANGAN ditulis di command line (muncul di
# `ps`/history shell kalau ditulis literal).
mongodump --uri="$MONGO_URI" --db=news_db     --out="$BACKUP_DIR"
mongodump --uri="$MONGO_URI" --db=threatintel --out="$BACKUP_DIR"

# Cek ukuran + jumlah koleksi wajar (bandingkan sama hari sebelumnya)
du -sh "$BACKUP_DIR"
ls "$BACKUP_DIR/news_db" | wc -l

# Salin KELUAR host (disk sama = bukan backup) -- sesuaikan tujuan
rsync -a "$BACKUP_DIR" user@host-lain:/backups/mongo-cti/
```

**Drill restore** (buktikan dump-nya beneran bisa dipulihkan, bukan cuma "file-nya ada"):

> ⚠️ **Command di bawah beda dari versi awal dokumen ini** -- ketemu 2 jebakan waktu drill
> beneran dijalankan (2026-09-30, staging), keduanya WAJIB dihindari:
>
> 1. `mongorestore --nsFrom=... --nsTo=... "$BACKUP_DIR/news_db"` (nunjuk LANGSUNG ke folder
>    per-db) **GAK JALAN** -- `mongorestore` gak bisa infer nama db dari folder yang dikasih
>    langsung sebagai `--dir`/posisional, hasilnya "don't know what to do with file", 0 dokumen
>    ke-restore. Harus `--dir="$BACKUP_DIR"` (folder INDUK yang isi `news_db/` + `threatintel/`
>    sekaligus), biar `mongorestore` deteksi nama db dari nama subfolder.
> 2. TAPI kalau `--dir` folder induk itu isinya lebih dari satu database (kasus kita: `news_db`
>    DAN `threatintel` sekaligus) dan cuma nge-set `--nsFrom`/`--nsTo` TANPA `--nsInclude`,
>    `mongorestore` tetap MEMPROSES SEMUA isi folder itu -- yang cocok pola `nsFrom` di-remap ke
>    nama test, yang GAK cocok (database lain di folder yang sama) tetap di-restore ke NAMA
>    ASLINYA. Efeknya restore ke `news_db_restore_test` diam-diam JUGA nulis ke `threatintel`
>    asli (dan sebaliknya di command kedua) -- di staging kebetulan `news_db`/`threatintel` lagi
>    kosong jadi gak ada data ketiban, tapi di produksi (yang isinya database ASLI, bukan
>    kosong) ini bisa nimpa data beneran. **`--nsInclude` WAJIB ada**, bukan opsional.

```bash
# Restore ke database SEMENTARA di instance Mongo yang SAMA (bukan menimpa news_db asli).
# --dir HARUS folder INDUK ($BACKUP_DIR, bukan $BACKUP_DIR/news_db), dan --nsInclude WAJIB
# ada supaya database lain di folder yang sama gak ikut ter-restore ke nama aslinya.
mongorestore --uri="$MONGO_URI" \
    --nsInclude="news_db.*" --nsFrom="news_db.*" --nsTo="news_db_restore_test.*" \
    --dir="$BACKUP_DIR"
mongorestore --uri="$MONGO_URI" \
    --nsInclude="threatintel.*" --nsFrom="threatintel.*" --nsTo="threatintel_restore_test.*" \
    --dir="$BACKUP_DIR"

# Bandingkan jumlah dokumen per collection kunci dengan aslinya (atau, kalau database asli
# kosong/belum ada seperti staging, bandingkan dengan hitungan langsung dari file dump:
# `bsondump --quiet "$BACKUP_DIR/news_db/$col.bson" | wc -l`)
for col in articles cve_tracker iocs scraper_runs; do
  orig=$(mongosh "$MONGO_URI" --quiet --eval "db.getSiblingDB('news_db').$col.countDocuments()")
  test=$(mongosh "$MONGO_URI" --quiet --eval "db.getSiblingDB('news_db_restore_test').$col.countDocuments()")
  echo "$col: asli=$orig restore=$test"
done

# Bersihkan database sementara
mongosh "$MONGO_URI" --quiet --eval "db.getSiblingDB('news_db_restore_test').dropDatabase()"
mongosh "$MONGO_URI" --quiet --eval "db.getSiblingDB('threatintel_restore_test').dropDatabase()"
```

**Sudah dijalankan & lolos (2026-09-30, staging, container `cti-mongo`):** dump `20260930T120307Z`
(58 MB `news_db` + 22 MB `threatintel`, dari `/home/nameless/backups/mongo-cti/`). Restore kedua
db total **2 detik** (205.446 dokumen). Semua 9 collection kunci dicek cocok PERSIS dengan hitungan
langsung dari file dump (`bsondump`, karena `news_db`/`threatintel` di staging kosong, gak ada
"asli" buat dibandingin): `articles` 8834, `cve_tracker` 667, `iocs` 23956, `scraper_runs` 9330,
`users` 7, `clients` 2, `techstack` 32, `groups` 3995, `hash` 398 -- nol selisih. Database test
sudah dibersihkan (`dropDatabase`, 2 kali dijalankan manual oleh user karena classifier otomatis
nolak `dropDatabase()` berturut-turut sebagai "mass delete" meski sudah dikonfirmasi di chat).
**Catatan:** drill ini di STAGING (bukan host produksi lama yang sebenarnya jadi target dokumen
ini) -- membuktikan MEKANISME restore-nya benar dan `mongorestore`-nya terpasang lengkap, bukan
pengganti drill di produksi. Ini juga sekaligus SUMBER dump yang dipakai warm start cutover
(runbook 3, langkah 4) -- jangan buang.

**Cara masukin dump ke container kalau `docker cp` gagal** (ketemu di staging: mount
`docker-entrypoint-initdb.d/init.js` di `cti-mongo` nyangkut jadi direktori kosong -- bukan file
seperti seharusnya -- bikin `docker cp` APAPUN ke container ini gagal dengan error mount, walau
container-nya sendiri jalan sehat. Belum diperbaiki di sumbernya, gak disentuh sesi ini karena
di luar scope drill restore): pakai `tar` streaming lewat `docker exec -i` sebagai gantinya, gak
kena pengecekan mount yang sama --
```bash
tar -C "$BACKUP_DIR" -cf - news_db threatintel | docker exec -i cti-mongo tar -C /tmp/restore-drill -xf -
```

---

## 2. Snapshot Rundeck (H-1, bukan drill -- baca-doang, aman dijalankan kapan saja)

Sudah ada alatnya (`tools/ops/rundeck_schedule.py`, lihat docstring-nya) dan sudah didokumentasikan di
`docs/CUTOVER_RUNBOOK.md` bagian 2.3. Ringkasannya di sini biar tidak perlu bolak-balik:

```bash
export RD_URL=http://10.8.20.78:4440       # IP dari legacy/config.yml, bukan secret
export RD_PROJECT=Threat-Information
read -s RD_TOKEN                            # token API Rundeck -- diketik interaktif, TIDAK di history shell
export RD_TOKEN

python3 tools/ops/rundeck_schedule.py snapshot --out rundeck-before-cutover.json
python3 tools/ops/rundeck_schedule.py status   --snapshot rundeck-before-cutover.json   # harus N/N
```

Simpan `rundeck-before-cutover.json` di luar host produksi DAN di luar repo (isinya nama job, bukan
secret, tapi tetap jangan di-commit). Ini yang dipakai `disable`/`enable` di hari cutover (runbook 3)
dan rollback ke stack lama (bagian 3 di bawah). **Ambil snapshot BARU tepat H-1** -- yang ada di
`docs/legacy/rundeck-jobs-map.json` itu rekaman Fase 0, sudah bisa basi.

Belum pernah diuji terhadap Rundeck ASLI (cuma API palsu di test unit) -- langkah 2 di bawah ini
sekaligus jadi uji coba pertamanya terhadap Rundeck produksi.

---

## 3. Latihan rollback ke stack lama <5 menit (di PRODUKSI, minimal sekali sebelum go-live)

Ini DRILL, bukan cuma baca dokumen -- runbook bagian 7.3 menjelaskan APA yang dilakukan; langkah di
bawah ini yang benar-benar MENJALANKANNYA dengan stopwatch, di jam yang sepi (bukan jam kerja), TANPA
niat sungguhan cutover (stack baru belum tentu perlu jalan sama sekali untuk latihan ini -- cukup
buktikan stack LAMA bisa mati-nyala lewat prosedur ini).

```bash
# 0. Prasyarat: snapshot Rundeck (bagian 2) sudah ada dan masih akurat (job aktif belum berubah
#    sejak snapshot diambil -- kalau ragu, ambil snapshot baru)
python3 tools/ops/rundeck_schedule.py status --snapshot rundeck-before-cutover.json   # catat N/N

# 1. Catat waktu mulai
date -u

# 2. MATIKAN jadwal (persis prosedur cutover langkah 2)
python3 tools/ops/rundeck_schedule.py disable --snapshot rundeck-before-cutover.json
python3 tools/ops/rundeck_schedule.py status  --snapshot rundeck-before-cutover.json   # harus 0/N

# 3. (simulasi "platform baru dibatalkan" -- untuk drill ini boleh skip stop/start unit
#    cti-web/nlp_worker/iocSyncer beneran kalau stack lama MEMANG masih yang aktif;
#    kalau platform baru sedang jalan paralel, matikan dulu: docker compose ... stop
#    beat worker worker-browser worker-nlp nginx)

# 4. NYALAKAN LAGI jadwal (ini yang diukur -- "rollback ke stack lama")
python3 tools/ops/rundeck_schedule.py enable --snapshot rundeck-before-cutover.json
python3 tools/ops/rundeck_schedule.py status --snapshot rundeck-before-cutover.json   # harus N/N lagi

# 5. Catat waktu selesai
date -u
```

**Setelah drill:** tulis hasilnya di `docs/CUTOVER_RUNBOOK.md` bagian 7.3, baris
"tulis waktunya: `____ menit` (target <5)" -- ganti dengan angka sungguhan. Kalau lebih dari 5 menit atau
ada job yang gagal enable/disable, itu temuan yang harus diperbaiki SEBELUM go-live, bukan sesuatu yang
diabaikan.

---

## 4. Backup Postgres terjadwal + salinan off-host (host PRODUKSI BARU)

### 4a. Timer systemd (unit file sudah ada, belum dipasang)

```bash
# Di host produksi baru, working directory = tempat docker-compose.yml + docker/stack.env berada
sudo cp docker/ops/cti-pg-backup.service docker/ops/cti-pg-backup.timer /etc/systemd/system/
# Sesuaikan WorkingDirectory di cti-pg-backup.service kalau lokasinya bukan /opt/cti-platform
sudo systemctl daemon-reload
sudo systemctl enable --now cti-pg-backup.timer

# Verifikasi jadwal terpasang
systemctl list-timers cti-pg-backup.timer

# Uji sekali secara manual (jangan tunggu jam 02:30)
sudo systemctl start cti-pg-backup.service
journalctl -u cti-pg-backup -n 30 --no-pager
ls -la /var/backups/cti      # dump baru harus muncul, chmod 600
```

Kegagalan memicu alarm Telegram topik `debug` otomatis (`--on-failure-cmd` di unit file) -- uji ini
juga sekaligus membuktikan jalur alarmnya, bukan cuma backup-nya.

### 4b. Salinan off-host (BELUM diotomasi -- ini yang masih kosong)

Backup di disk yang sama dengan Postgres-nya bukan backup (kalau disk/host itu rusak, backup ikut
hilang). Dua opsi, pilih salah satu:

**Opsi A -- cron `rsync` ke host lain** (paling sederhana, butuh SSH key one-way dari host produksi ke
host penyimpanan, read-write HANYA ke direktori backup):

```bash
# Di host produksi, crontab root (atau user yang punya akses baca /var/backups/cti)
# Jalan 15 menit setelah timer backup (02:30 + buffer)
crontab -e
# tambahkan:
45 2 * * * rsync -a --delete /var/backups/cti/ backup-host:/backups/cti-platform/ 2>&1 | logger -t cti-backup-offhost
```

**Opsi B -- `rclone` ke object storage** (S3-compatible dkk, kalau tidak ada host kedua yang cocok):

```bash
rclone config          # sekali, interaktif -- isi kredensial provider storage
# lalu cron yang sama pola-nya:
45 2 * * * rclone sync /var/backups/cti/ remote:cti-platform-backups/ 2>&1 | logger -t cti-backup-offhost
```

**Setelah dipasang (opsi A atau B):** verifikasi sekali dengan menjalankan cron entry-nya manual, cek
filenya benar-benar muncul di sisi tujuan, lalu update `docs/CUTOVER_RUNBOOK.md` bagian 6 -- baris
"Off-host: ... belum diotomasi" diganti jadi cara yang dipakai + jadwalnya.

---

## Setelah keempatnya selesai

Update checklist cutover di `docs/PROGRESS.md` ("Checklist cutover") dan baris terkait di
`docs/CUTOVER_RUNBOOK.md` bagian 10 ("Yang BELUM terbukti") -- jangan biarkan dua dokumen itu bilang
"belum" kalau di sini sudah "selesai".
