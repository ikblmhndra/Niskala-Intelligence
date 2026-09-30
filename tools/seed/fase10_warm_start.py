"""Warm start dedup (Fase 10.C, skenario C): isi `scraper_seen` dari dump Mongo
lama supaya run pertama scraper BARU gak mengulang seluruh isi feed.

Tanpa ini tiap scraper mulai "dingin" (nol baris `scraper_seen`) dan cuma
diloloskan `cold_start_max_items` item pertama (Fase 10.A) -- aman, tapi item
yang muncul sejak dump ikut kebuang, dan feed yang isinya sudah pernah dialert
lama bisa ngirim ulang notifikasi. Dengan warm start, scraper yang punya
riwayat di dump dianggap "hangat": gak kena cap, dan cuma item yang BENAR-BENAR
baru sejak dump yang diproses.

Hash-nya harus PERSIS sama dengan yang dihitung `Runner` pas scrape:
`sha256(scraper_id + NUL + raw_key)`, `raw_key` = `Item.dedup_key()`. Karena
itu script ini memakai `compute_dedup_key` + `canonicalize_url` yang sama,
bukan meniru rumusnya.

Sumber (semuanya dipakai, digabung per scraper):
  1. `threatintel.offsets`   -- dedup lama. Kolom `script` dipetakan PERSIS ke
     `ScraperMeta.legacy_script`. `key` = `str(title)+str(url)` mentah (tanpa
     pemisah), jadi URL-nya dicari dari pasangan (title, url) yang dikenal.
  2. `threatintel.nlp_jobs`  -- tiap item baru bikin satu job berisi
     `article.title`/`article.url`, TERMASUK yang akhirnya ditolak klasifikasi
     (gak masuk `articles`). `script_name` dipetakan ke `legacy_label`.
  3. `news_db.articles`      -- label `source` -> `ScraperMeta.source` (+ `ALIASES`).
  4. `news_db.ransomware_victims` -> `offset_key` (formatnya sama persis dengan
     `RansomwareVictimItem.dedup_key`) dan `news_db.tweets` -> `tweet_id`.

  5. File offset lama (`--legacy-dir`): `APTattack_offset.txt` (SHA commit ->
     `apt_ttp_simulation`) dan `techstackLibrary/offset/techstack_*_offset.txt`
     (`AdvisoryID`+`ModifiedDate` -> `techstack_npm/pypi/go`) -- format kunci lama
     SAMA dengan `NoticeItem.key` scraper barunya. Watcher commit lain (`github_ttps`,
     `sophoslabs_github`, `mitre_github`) TIDAK di-seed: offset lama cuma mencatat SHA,
     sedangkan notice barunya per (SHA, file) -- run pertamanya kena cap dingin
     (maks N notice terbaru). `tweet_alerts_*`/`trending_cve` gak perlu: jendela
     pencarian cuma 30 menit - 2 jam.

Scraper yang tipe itemnya bukan artikel dan gak punya sumber di atas
(`new_cve`/`any_run_trends`: dedup dimatikan, upsert idempoten; `github_poc_monitor`,
`deepdark_cti`) tetap dingin dan dilaporkan.

URUTAN DI HARI CUTOVER: stop Rundeck -> mongodump terakhir -> script ini ->
baru nyalakan stack baru (beat). Kalau scraper sudah sempat jalan duluan dia
sudah lewat fase dingin -- baris yang bentrok di-skip (ON CONFLICT DO NOTHING),
jadi aman dijalankan ulang tapi gak menyelamatkan item yang sudah terlanjur di-cap.

    uv run --with pymongo python tools/seed/fase10_warm_start.py --dry-run
    uv run --with pymongo python tools/seed/fase10_warm_start.py
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import typing
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cti_core.db.engine import sync_session
from cti_core.db.models.scraper import ScraperSeen
from cti_core.urlkit import canonicalize_url
from cti_scraper import registry
from cti_scraper.dedup import compute_dedup_key
from cti_scraper.items import ArticleItem
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

if __package__ in (None, ""):  # dijalankan sebagai skrip: `python tools/seed/...`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.seed._dump import DEFAULT_DUMP_DIR, DirDump, Dump, DumpError

ALIASES: dict[str, str | None] = {
    # `articles.source` (label lama, lowercase) -> id scraper baru. Label yang
    # cuma beda tulisan dari `ScraperMeta.source`; `None` = scraper lama yang
    # SENGAJA gak diport (gak ada di registry).
    "cybersecurity news": "cybersecnews",
    "trustwave": "trustwave",  # `meta.source` sekarang "LevelBlue SpiderLabs (dulu Trustwave)"
    # (rebrand, census 2026-09-30) -- dump lama tetap pakai label "trustwave"
    "trendmicro": "trendmicro",
    "f5": "f5",
    "bitdefender": "bitdefender",
    "landth": "landth",
    "ecleticiq": "eclecticiq",
    "detection engineering": None,
    "sekoia": None,
    "validin": None,
    "palo alto net": None,
    "unknown": None,
}

_TAIL_URL = re.compile(r"https?://\S+$")
_LABEL_SUFFIX = re.compile(r"\s*\([^)]*\)$")
_BATCH = 2000


def _default_legacy_dir() -> Path | None:
    """Folder induk repo (`cti-revamp/`) -- tempat `ScraperNews/` dan `techstackLibrary/`.
    `None` di luar checkout (mis. skrip di-mount ke `/tools` dalam container)."""
    parents = Path(__file__).resolve().parents
    return parents[3] if len(parents) > 3 else None


DEFAULT_LEGACY_DIR = _default_legacy_dir()


@dataclass
class Seen:
    """Satu item yang sudah pernah dilihat sistem lama, buat satu scraper."""

    raw_key: str
    seen_at: datetime.datetime | None = None
    sources: set[str] = field(default_factory=set)


@dataclass
class Plan:
    seen: dict[str, dict[str, Seen]] = field(default_factory=lambda: defaultdict(dict))
    """scraper_id -> {dedup_key -> Seen}"""
    unresolved: Counter[str] = field(default_factory=Counter)
    """scraper_id -> jumlah key offsets yang URL-nya gak bisa ditemukan"""
    unresolved_samples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    dropped: Counter[str] = field(default_factory=Counter)
    """label/script lama yang gak punya scraper di registry (sengaja gak diport)"""
    legacy_notes: list[str] = field(default_factory=list)
    """ringkasan sumber file offset lama (dibaca / tidak ketemu)"""

    def add(
        self, scraper_id: str, raw_key: str, source: str, seen_at: datetime.datetime | None
    ) -> None:
        key = compute_dedup_key(scraper_id, raw_key)
        entry = self.seen[scraper_id].get(key)
        if entry is None:
            self.seen[scraper_id][key] = Seen(raw_key, seen_at, {source})
            return
        entry.sources.add(source)
        if seen_at and (entry.seen_at is None or seen_at < entry.seen_at):
            entry.seen_at = seen_at


# scraper_id -> (path relatif dari --legacy-dir, bentuk file)
LEGACY_OFFSETS: dict[str, tuple[str, str]] = {
    "apt_ttp_simulation": ("ScraperNews/offset/APTattack_offset.txt", "lines"),
    "techstack_npm": ("techstackLibrary/offset/techstack_npm_offset.txt", "advisories"),
    "techstack_pypi": ("techstackLibrary/offset/techstack_pypi_offset.txt", "advisories"),
    "techstack_go": ("techstackLibrary/offset/techstack_golang_offset.txt", "advisories"),
}


def legacy_offset_keys_from_entry(entry: dict[str, str]) -> str:
    """Satu entri offset teknologi lama -> kunci mentah (`<AdvisoryID>:<ModifiedDate>`)."""
    return f"{entry['AdvisoryID']}:{entry['ModifiedDate']}"


def legacy_offset_keys(path: Path, kind: str) -> list[str]:
    """Kunci mentah dari file offset lama. `lines`: satu SHA per baris. `advisories`:
    JSON `[{"AdvisoryID", "ModifiedDate"}, ...]` -> `<id>:<tanggal>`, persis
    `LibraryAdvisoryScraper._notice().key`."""
    text = path.read_text(encoding="utf-8")
    if kind == "lines":
        return [line.strip() for line in text.splitlines() if line.strip()]
    entries = json.loads(text)
    return [legacy_offset_keys_from_entry(e) for e in entries]


# --- registry ---------------------------------------------------------------------------


def yields_articles(cls: type) -> bool:
    """Scraper ini nge-yield `ArticleItem` (kunci dedup = URL kanonik)? Dibaca
    dari anotasi return `fetch()` -- family (rss/xpath/html) dan collector
    artikel (cisa_kev) semua menganotasinya; tipe lain (CveItem, TweetItem, ...)
    punya format kunci sendiri dan TIDAK boleh ditebak dari URL."""
    try:
        ret = typing.get_type_hints(cls.fetch).get("return")  # type: ignore[attr-defined]
    except Exception:
        return False

    def walk(t: Any) -> bool:
        return t is ArticleItem or any(walk(a) for a in typing.get_args(t))

    return walk(ret)


@dataclass
class Index:
    by_script: dict[str, str]
    by_label: dict[str, str]
    by_source: dict[str, str | None]
    article_scrapers: set[str]
    ttl_days: dict[str, int]


def build_index() -> Index:
    reg = registry.discover()
    by_script: dict[str, str] = {}
    by_label: dict[str, str] = {}
    by_source: dict[str, str | None] = dict(ALIASES)
    for sid, cls in reg.items():
        meta = cls.meta
        if meta.legacy_script:
            by_script[meta.legacy_script] = sid
        if meta.legacy_label:
            by_label[meta.legacy_label] = sid
        by_source[meta.source.strip().lower()] = sid
    bad = [a for a in ALIASES.values() if a is not None and a not in reg]
    if bad:
        raise RuntimeError(f"ALIASES nunjuk scraper yang gak ada di registry: {bad}")
    return Index(
        by_script=by_script,
        by_label=by_label,
        by_source=by_source,
        article_scrapers={sid for sid, cls in reg.items() if yields_articles(cls)},
        ttl_days={sid: cls.meta.dedup_ttl_days for sid, cls in reg.items()},
    )


# --- perencanaan ---------------------------------------------------------------------------


def _canonical(url: str) -> str | None:
    try:
        return canonicalize_url(url)
    except Exception:
        return None


def _resolve_url(key: str, urls_by_title: dict[str, str], by_concat: dict[str, str]) -> str | None:
    """`key` lama = title + url tanpa pemisah. Urutan: (1) cocok persis dengan
    pasangan yang dikenal; (2) diawali judul yang dikenal (untuk key yang
    ekornya BUKAN url apa adanya -- CISA: judul + tanggal, Splunk: judul + path
    relatif) -- judul terpanjang menang; (3) ekor `https://...`."""
    hit = by_concat.get(key)
    if hit:
        return hit
    best = max((t for t in urls_by_title if key.startswith(t)), key=len, default=None)
    if best is not None:
        return urls_by_title[best]
    tail = _TAIL_URL.search(key)
    return tail.group(0) if tail else None


def _base_label(label: Any) -> str:
    """`NEW CISA CATALOG VULNERABILITY (RELATED)` -> `NEW CISA CATALOG VULNERABILITY`:
    job lama yang sama dengan varian sufiks (RELATED)/(INDONESIA) di label."""
    return _LABEL_SUFFIX.sub("", str(label or ""))


def build_plan(dump: Dump, index: Index, legacy_dir: Path | None = None) -> Plan:
    plan = Plan()

    nlp_jobs = dump.docs("threatintel/nlp_jobs")
    articles = dump.docs("news_db/articles")

    # Pasangan (title, url) yang dikenal per scraper -- kamus resolusi buat `offsets`.
    urls_by_title: dict[str, dict[str, str]] = defaultdict(dict)
    by_concat: dict[str, dict[str, str]] = defaultdict(dict)

    def remember(sid: str, title: Any, url: Any) -> None:
        if title and url:
            urls_by_title[sid].setdefault(str(title), str(url))
            by_concat[sid].setdefault(str(title) + str(url), str(url))

    for job in nlp_jobs:
        label = job.get("script_name")
        art = job.get("article") or {}
        sid = index.by_label.get(_base_label(label))
        if sid is None:
            plan.dropped[f"nlp_jobs:{label}"] += 1
            continue
        if sid in index.article_scrapers:
            remember(sid, art.get("title"), art.get("url"))
            if art.get("url") and (url := _canonical(str(art["url"]))):
                plan.add(sid, url, "nlp_jobs", job.get("created_at"))

    for art in articles:
        label = str(art.get("source") or "").strip().lower()
        if label not in index.by_source:
            plan.dropped[f"articles:{art.get('source')}"] += 1
            continue
        sid = index.by_source[label]
        if sid is None:
            plan.dropped[f"articles:{art.get('source')}"] += 1
            continue
        if sid in index.article_scrapers and art.get("url"):
            remember(sid, art.get("title"), art.get("url"))
            if url := _canonical(str(art["url"])):
                plan.add(sid, url, "articles", None)

    for off in dump.docs("threatintel/offsets"):
        sid = index.by_script.get(str(off.get("script")))
        if sid is None:
            plan.dropped[f"offsets:{off.get('script')}"] += 1
            continue
        if sid not in index.article_scrapers:
            continue  # kunci non-URL: ditangani sumber khusus di bawah / dingin
        raw = str(off["key"])
        url = _resolve_url(raw, urls_by_title[sid], by_concat[sid])
        canon = _canonical(url) if url else None
        if canon is None:
            plan.unresolved[sid] += 1
            if len(plan.unresolved_samples[sid]) < 3:
                plan.unresolved_samples[sid].append(raw[:100])
            continue
        plan.add(sid, canon, "offsets", off.get("seen_at"))

    # Sumber khusus: tipe item dengan format kunci sendiri.
    if "ransomware_live" in index.ttl_days:
        for doc in dump.docs("news_db/ransomware_victims"):
            if doc.get("offset_key"):
                plan.add("ransomware_live", str(doc["offset_key"]), "ransomware_victims", None)
    if "monitor_x" in index.ttl_days:
        for doc in dump.docs("news_db/tweets"):
            if doc.get("tweet_id"):
                plan.add("monitor_x", str(doc["tweet_id"]), "tweets", None)

    if legacy_dir is not None:
        for sid, (rel, kind) in LEGACY_OFFSETS.items():
            if sid not in index.ttl_days:
                continue
            path = legacy_dir / rel
            if not path.is_file():
                plan.legacy_notes.append(f"{sid}: {path} TIDAK ADA -> scraper tetap dingin")
                continue
            keys = legacy_offset_keys(path, kind)
            for key in keys:
                plan.add(sid, key, "legacy_offset", None)
            plan.legacy_notes.append(f"{sid}: {len(keys)} kunci dari {path.name}")
    return plan


# --- penulisan -------------------------------------------------------------------------------


def write_plan(
    session: Session, plan: Plan, index: Index, *, now: datetime.datetime
) -> dict[str, int]:
    """Insert `state=done`, `ON CONFLICT DO NOTHING`. Return {scraper_id: baris BARU}."""
    inserted: dict[str, int] = {}
    for sid, entries in sorted(plan.seen.items()):
        expire_at = now + datetime.timedelta(days=index.ttl_days[sid])
        rows = []
        for dedup_key, seen in entries.items():
            first = seen.seen_at or now
            if first.tzinfo is None:
                first = first.replace(tzinfo=datetime.UTC)
            rows.append(
                {
                    "dedup_key": dedup_key,
                    "scraper_id": sid,
                    "state": "done",
                    "lease_until": None,
                    "attempts": 1,
                    "poisoned": False,
                    "first_seen_at": first,
                    "committed_at": now,
                    "expire_at": expire_at,
                }
            )
        new = 0
        for i in range(0, len(rows), _BATCH):
            stmt = (
                pg_insert(ScraperSeen)
                .values(rows[i : i + _BATCH])
                .on_conflict_do_nothing(index_elements=["dedup_key"])
                .returning(ScraperSeen.dedup_key)
            )
            new += len(session.execute(stmt).all())
        inserted[sid] = new
    return inserted


def seen_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(ScraperSeen.scraper_id, func.count()).group_by(ScraperSeen.scraper_id)
    ).all()
    return {sid: n for sid, n in rows}


# --- CLI --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--dump-dir", type=Path, default=DEFAULT_DUMP_DIR)
    ap.add_argument(
        "--legacy-dir",
        type=Path,
        default=DEFAULT_LEGACY_DIR,
        help="folder induk berisi ScraperNews/ dan techstackLibrary/ (file offset lama); "
        "'none' = lewati",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="hitung + tampilkan rencana, tanpa nulis"
    )
    args = ap.parse_args(argv)

    index = build_index()
    try:
        legacy = None if str(args.legacy_dir).lower() in ("none", "") else args.legacy_dir
        plan = build_plan(DirDump(args.dump_dir), index, legacy)
    except DumpError as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1

    now = datetime.datetime.now(datetime.UTC)
    if args.dry_run:
        inserted = {sid: len(entries) for sid, entries in plan.seen.items()}
        before: dict[str, int] = {}
    else:
        with sync_session() as session:
            before = seen_counts(session)
            inserted = write_plan(session, plan, index, now=now)

    mode = "DRY-RUN (tidak ditulis)" if args.dry_run else "DITULIS"
    print(f"== warm start scraper_seen -- {mode} -- dump: {args.dump_dir}")
    print(f"{'scraper':26} {'kunci':>7} {'baru':>7}  sumber")
    for sid, entries in sorted(plan.seen.items()):
        srcs = Counter(s for e in entries.values() for s in e.sources)
        detail = ", ".join(f"{k}={v}" for k, v in sorted(srcs.items()))
        print(f"{sid:26} {len(entries):>7} {inserted.get(sid, 0):>7}  {detail}")
    print(f"total: {sum(len(e) for e in plan.seen.values())} kunci di {len(plan.seen)} scraper")

    for note in plan.legacy_notes:
        print(f"  [offset lama] {note}")
    cold = sorted(sid for sid in index.ttl_days if sid not in plan.seen and before.get(sid, 0) == 0)
    print(f"\n== {len(cold)} scraper TETAP DINGIN (kena cold-start cap di run pertama):")
    print("  " + ", ".join(cold))
    if plan.unresolved:
        print(f"\n== key offsets yang URL-nya gak ketemu ({sum(plan.unresolved.values())}):")
        for sid, n in plan.unresolved.most_common():
            print(f"  {sid:24} {n:>4}  contoh: {plan.unresolved_samples[sid]}")
    if plan.dropped:
        print("\n== data lama tanpa scraper di registry (sengaja gak diport, diabaikan):")
        for name, n in plan.dropped.most_common():
            print(f"  {name:60} {n:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
