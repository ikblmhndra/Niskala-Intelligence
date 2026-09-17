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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from classify import Family, classify_dir
from emit import emit_rss, emit_xpath, legacy_stem_to_id
from extract import extract_rss, extract_xpath
from import_rundeck import build_schedule_map

CTI_PLATFORM_ROOT = Path(__file__).resolve().parents[2]  # .../cti-platform
MONOREPO_ROOT = CTI_PLATFORM_ROOT.parent  # .../cti-revamp (ScraperNews & cti-platform bersebelahan)
SCRAPERS_SRC = MONOREPO_ROOT / "ScraperNews"
RUNDECK_MAP = CTI_PLATFORM_ROOT / "docs" / "legacy" / "rundeck-jobs-map.json"
OUT_DIR = CTI_PLATFORM_ROOT / "scrapers" / "src" / "cti_scrapers" / "feeds"
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
NOT_A_SCRAPER_STEMS = {
    "logbook",
    "sendCounter",
    "offsetAlert",
    "trendingNewsToday",
    "threatactorTrendGraylog",
}

# Job aktif Rundeck yang script-nya di REPO LAIN, gak ada sama sekali di
# checkout ini -- lihat PROGRESS.md "Scope ditunda: 3 codebase di luar
# ScraperNews". techstackGO/NPM/PYPI ADA salinan lokal di ScraperNews/ (makanya
# classify_dir bisa nemuin & sempat ke-tandain "bespoke"), tapi salinan itu
# KEMUNGKINAN FORK BASI -- job Rundeck yang beneran jalan nunjuk ke
# /opt/techstackLibrary, bukan /opt/ScraperNews. Auto-generate dari fork basi
# lebih bahaya daripada di-skip; tunggu isi /opt/techstackLibrary ditarik.
EXTERNAL_REPO_STEMS = {
    "trendingCve",  # /opt/TwitterScrap
    "twitter",  # /opt/TwitterScrap
    "twitter30",  # /opt/TwitterScrap
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


def main() -> int:
    jobs = json.loads(RUNDECK_MAP.read_text())
    active_stems = {
        Path(j["script"]).stem for j in jobs if j["enabled"] and j.get("script")
    }
    out_of_scope = active_stems & (NOT_A_SCRAPER_STEMS | EXTERNAL_REPO_STEMS | PERMANENTLY_BLOCKED)
    active_stems -= NOT_A_SCRAPER_STEMS
    active_stems -= EXTERNAL_REPO_STEMS
    active_stems -= PERMANENTLY_BLOCKED

    schedule_map = build_schedule_map(RUNDECK_MAP)

    classifications = classify_dir(SCRAPERS_SRC, only=active_stems)
    found_stems = {c.path.stem for c in classifications}
    unresolved = sorted(active_stems - found_stems)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    generated: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    review: list[dict[str, object]] = []

    for c in classifications:
        stem = c.path.stem
        schedule = schedule_map.get(stem, "0 * * * *")

        if c.family == Family.RSS:
            ex = extract_rss(c.path)
            candidate_id = legacy_stem_to_id(stem)
            if (OUT_DIR / f"{candidate_id}.py").exists():
                skipped.append({"legacy_script": stem, "scraper_id": candidate_id})
                continue
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
            candidate_id = legacy_stem_to_id(stem)
            if (OUT_DIR / f"{candidate_id}.py").exists():
                skipped.append({"legacy_script": stem, "scraper_id": candidate_id})
                continue
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
            review.append({
                "legacy_script": stem,
                "family": c.family.value,
                "reasons": ["bespoke/selenium -- porting manual, subclass BaseScraper langsung"],
            })

    for stem in unresolved:
        review.append({
            "legacy_script": stem,
            "family": "unresolved",
            "reasons": [
                "stem gak ketemu file .py -- cek path/casing manual (lihat PROGRESS.md Fase 0.2)"
            ],
        })

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
