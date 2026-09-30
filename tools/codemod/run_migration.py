#!/usr/bin/env python3
"""Orkestrator Fase 4: classify -> extract -> emit buat semua job aktif
Rundeck. Yang "bersih" (needs_review kosong) di-generate ke
scrapers/src/cti_scrapers/feeds/; yang butuh review dicatat di
migration_report.json buat ditangani manual (item 4.9).

WAJIB: tiap file hasil generate tetap lewat dry-run -> verify -> enable
satu-satu (docs/ADDING_A_SCRAPER.md) -- script ini cuma bikin KANDIDAT,
bukan keputusan final.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from classify import Family, classify_dir
from emit import emit_rss, emit_xpath
from extract import extract_rss, extract_xpath
from import_rundeck import build_schedule_map

CTI_PLATFORM_ROOT = Path(__file__).resolve().parents[2]  # .../cti-platform
MONOREPO_ROOT = CTI_PLATFORM_ROOT.parent  # .../cti-revamp (ScraperNews & cti-platform bersebelahan)
SCRAPERS_SRC = MONOREPO_ROOT / "ScraperNews"
RUNDECK_MAP = CTI_PLATFORM_ROOT / "docs" / "legacy" / "rundeck-jobs-map.json"
OUT_DIR = CTI_PLATFORM_ROOT / "scrapers" / "src" / "cti_scrapers" / "feeds"
COLLECTORS_DIR = CTI_PLATFORM_ROOT / "scrapers" / "src" / "cti_scrapers" / "collectors"
REPORT_PATH = CTI_PLATFORM_ROOT / "tools" / "codemod" / "migration_report.json"

# Job aktif Rundeck yang jadwalnya lewat Rundeck tapi BUKAN scraper -- gak
# ada fetch() ke sumber eksternal / push_job(), semuanya utility internal
# (laporan, counter, flush log). Ranahnya Fase 6 (Celery beat task), bukan
# BaseScraper -- sengaja DIKELUARIN dari target migrasi, bukan "gagal
# ke-resolve". Diverifikasi satu-satu waktu triage 4.10:
#   - logbook, sendCounter, trendingNewsToday (supportFile/) -- laporan/
#     counter dikirim ke Telegram, gak nyentuh dedup/push_job sama sekali
#   - offsetAlert (supportFile/) -- detektor scraper mati yang udah rusak
#     diam-diam, lihat KNOWN_BROKEN.md
#   - threatactorTrendGraylog -- baca supportFile/ThreatActorName.txt lokal,
#     flush ke Graylog; bukan scraper (gak ada request keluar buat data baru)
#
# Triage 4.10 ronde ke-2 nemuin 5 lagi kategori sama persis:
#   - githubSophoslab, githubTTPs, mitreGithub, githubAptTTPSimulation --
#     "GitHub commit watcher": poll api.github.com/.../commits, alert
#     Telegram (send_alert_report/send_report_file) kalau ada commit baru.
#     Diverifikasi: NOL panggilan dbMongo/push_job di keempatnya -- gak
#     pernah nulis apa pun ke DB, murni notifikasi sepihak. (Beda dari
#     blackorbirdGithub & githubUnit42, family sama tapi KEDUANYA manggil
#     dbMongo.upsert_article() -- itu tetap bespoke, lihat needs_review.)
#   - topCve -- "sumber data"-nya collection cve_tracker LOKAL (baca lewat
#     dbMongo, bukan fetch ke luar), agregat + kirim digest Telegram. Gak
#     ada langkah "scrape" sama sekali, ini laporan atas hasil scraper lain.
#
# TwitterScrap ditarik user dari produksi (dulu EXTERNAL_REPO_STEMS, "gak
# ada di checkout") -- setelah beneran dibaca, `trendingCve`/`twitter`/
# `twitter30` (aktif di Rundeck) sama-sama Telegram-only: API Twitter
# RESMI (bearer token), daftar akun dari file teks statis
# (`supportFile/usernames_*.txt`), NOL panggilan dbMongo/upsert di
# ketiganya -- pindah ke sini, bukan EXTERNAL_REPO_STEMS lagi. Dua file
# lain di repo itu (`investigateScenario.py` nonaktif, `newTwitter.py`
# malah gak ada di Rundeck sama sekali, Selenium peninggalan lama) gak
# masuk himpunan manapun, gak pernah nyampe filter job aktif.
NOT_A_SCRAPER_STEMS = {
    "logbook",
    "sendCounter",
    "offsetAlert",
    "trendingNewsToday",
    "threatactorTrendGraylog",
    "githubSophoslab",
    "githubTTPs",
    "mitreGithub",
    "githubAptTTPSimulation",
    "topCve",
    "trendingCve",
    "twitter",
    "twitter30",
}

# Job aktif Rundeck yang script-nya di REPO LAIN, gak ada sama sekali di
# checkout ini -- lihat PROGRESS.md "Scope ditunda: 3 codebase di luar
# ScraperNews". techstackGO/NPM/PYPI ADA salinan lokal di ScraperNews/ (makanya
# classify_dir bisa nemuin & sempat ke-tandain "bespoke"), tapi salinan itu
# KEMUNGKINAN FORK BASI -- job Rundeck yang beneran jalan nunjuk ke
# /opt/techstackLibrary, bukan /opt/ScraperNews. Auto-generate dari fork basi
# lebih bahaya daripada di-skip; tunggu isi /opt/techstackLibrary ditarik.
# (TwitterScrap UDAH ditarik & dicek -- pindah ke NOT_A_SCRAPER_STEMS di
# atas, bukan di sini lagi. BreachForums masih di luar checkout tapi
# dua-duanya nonaktif, gak masuk himpunan job aktif sama sekali.)
EXTERNAL_REPO_STEMS = {
    "techstackGO",  # /opt/techstackLibrary -- salinan ScraperNews/ diduga basi
    "techstackNPM",  # /opt/techstackLibrary -- salinan ScraperNews/ diduga basi
    "techstackPYPI",  # /opt/techstackLibrary -- salinan ScraperNews/ diduga basi
}

# Diblokir PERMANEN -- kredensial hardcoded di source, lihat
# SECRETS_ROTATION.md. Jangan pernah otomatis digenerate/dijalanin.
# "threatactorTrendTelegram" itu nama job Rundeck buat script yang SAMA
# (beda ejaan doang dari "threatActorTrendTele.py" asli) -- masuk sini,
# bukan entry terpisah.
PERMANENTLY_BLOCKED = {"threatActorTrendTele", "threatactorTrendTelegram"}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(CTI_PLATFORM_ROOT))
    except ValueError:
        return str(p)


_LEGACY_SCRIPT_RE = re.compile(r'legacy_script\s*=\s*"([^"]+)"')


def _find_already_covered(*dirs: Path) -> set[str]:
    """Scan `legacy_script="..."` di semua file scraper yang UDAH ada (baik
    hasil generate `feeds/` maupun bespoke tulisan tangan `collectors/`),
    balikin himpunan stem yang udah ke-cover. Dulu skip-check cuma ngecek
    `feeds/` lewat nama file hasil `legacy_stem_to_id()` -- itu gak nangkep
    scraper bespoke Fase 3 (`ransomware_live.py`, `cisa_kev.py`) yang
    filenya gak ngikut konvensi id otomatis, jadi keduanya kebaca terus
    "butuh review" padahal udah lengkap. Scan berbasis `legacy_script` field
    langsung, bukan nebak nama file, jadi bener buat family manapun."""
    covered: set[str] = set()
    for d in dirs:
        if not d.exists():
            continue
        for path in d.glob("*.py"):
            match = _LEGACY_SCRIPT_RE.search(path.read_text())
            if match:
                covered.add(match.group(1))
    return covered


def main() -> int:
    jobs = json.loads(RUNDECK_MAP.read_text())
    active_stems = {Path(j["script"]).stem for j in jobs if j["enabled"] and j.get("script")}
    out_of_scope = active_stems & (NOT_A_SCRAPER_STEMS | EXTERNAL_REPO_STEMS | PERMANENTLY_BLOCKED)
    active_stems -= NOT_A_SCRAPER_STEMS
    active_stems -= EXTERNAL_REPO_STEMS
    active_stems -= PERMANENTLY_BLOCKED

    schedule_map = build_schedule_map(RUNDECK_MAP)

    classifications = classify_dir(SCRAPERS_SRC, only=active_stems)
    found_stems = {c.path.stem for c in classifications}
    unresolved = sorted(active_stems - found_stems)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    already_covered = _find_already_covered(OUT_DIR, COLLECTORS_DIR)

    generated: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    review: list[dict[str, object]] = []

    for c in classifications:
        stem = c.path.stem
        schedule = schedule_map.get(stem, "0 * * * *")

        if stem in already_covered:
            skipped.append({"legacy_script": stem, "scraper_id": "(udah ada -- cek legacy_script)"})
            continue

        if c.family == Family.RSS:
            ex = extract_rss(c.path)
            if ex.needs_review:
                review.append(
                    {"legacy_script": stem, "family": c.family.value, "reasons": ex.needs_review}
                )
                continue
            out = emit_rss(legacy_script=stem, extraction=ex, schedule=schedule, out_dir=OUT_DIR)
            generated.append({"legacy_script": stem, "family": c.family.value, "output": _rel(out)})

        elif c.family in (Family.XPATH_STATIC, Family.XPATH_BROWSER):
            runtime = "browser" if c.family == Family.XPATH_BROWSER else "light"
            ex = extract_xpath(c.path, runtime=runtime)
            if ex.needs_review:
                review.append(
                    {"legacy_script": stem, "family": c.family.value, "reasons": ex.needs_review}
                )
                continue
            out = emit_xpath(
                legacy_script=stem,
                extraction=ex,
                schedule=schedule,
                runtime=runtime,
                out_dir=OUT_DIR,
            )
            generated.append({"legacy_script": stem, "family": c.family.value, "output": _rel(out)})

        else:
            review.append(
                {
                    "legacy_script": stem,
                    "family": c.family.value,
                    "reasons": [
                        "bespoke/selenium -- porting manual, subclass BaseScraper langsung"
                    ],
                }
            )

    for stem in unresolved:
        review.append(
            {
                "legacy_script": stem,
                "family": "unresolved",
                "reasons": [
                    "stem gak ketemu file .py -- cek path/casing manual "
                    "(lihat PROGRESS.md Fase 0.2)"
                ],
            }
        )

    report = {
        "total_active_jobs": len(active_stems),
        "out_of_scope_count": len(out_of_scope),
        "generated_count": len(generated),
        "skipped_existing_count": len(skipped),
        "needs_review_count": len(review),
        "out_of_scope": sorted(out_of_scope),
        "generated": sorted(generated, key=lambda x: x["legacy_script"]),
        "skipped_existing": sorted(skipped, key=lambda x: x["legacy_script"]),
        "needs_review": sorted(review, key=lambda x: x["legacy_script"]),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"job aktif Rundeck (raw): {len(active_stems) + len(out_of_scope)}")
    print(f"di luar scope Fase 4  : {len(out_of_scope)} (bukan scraper / repo lain / diblokir)")
    print(f"job aktif target      : {len(active_stems)}")
    print(f"di-generate otomatis  : {len(generated)}")
    print(f"di-skip (udah ada)    : {len(skipped)}")
    print(f"butuh review manual   : {len(review)}")
    print(f"laporan               : {_rel(REPORT_PATH)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
