"""Orkestrasi stage -- port alur kontrol `nlp_scan()` (`nlp.py:144-729`),
BUKAN logikanya sendiri (itu semua udah di `stages/*.py` + `routing.py`).
Urutan: `classify -> fetch_text -> summarize -> extract_iocs -> [ttp+score+
routing, DI-SKIP kalau security_tech_best_practice] -> persist -> alert`.

Dua short-circuit dipertahankan APA ADANYA dari kode lama:

1. `related_cyber == False` -> return lebih awal, gak ada fetch/summarize/
   enrichment PENUH yang jalan (nlp.py:280-288, port apa adanya). BEDA dari
   kode lama di satu hal (Fase 7.3, keputusan eksplisit user): sekarang
   `persist_rejected()` TETAP nyatet baris ringan ke `rejected_articles`
   sebelum return -- Fase 5 awal artikel yang ditolak diam-diam ilang
   (gak ke-log di mana pun yang bisa di-query), sekarang bisa direview/
   di-restore manual lewat router `filtered_articles.py`.
2. `security_tech_best_practice == True` -> LEWATIN `extract_ttps`
   (hemat 1 panggilan LLM) DAN `score` (gak ada NER/regex group-country
   matching) sama sekali, nlp.py:343-367 `return` sebelum Phase 4-6 mulai.
   `extract_iocs` TETAP jalan (udah kepanggil sebelum percabangan ini di
   kode lama, line 314 vs 343).

Belum termasuk di sini (dicatat, bukan lupa): `update_cve_mention` (tracking
mention CVE per bulan, `nlp.py:721-726`) -- itu makan buat fitur laporan
mingguan CVE (`cveEmailAutomation`) yang udah di-scope keluar Fase 5 (lihat
docstring `cveValidator` di plan investigasi), gak ada tabel Postgres buat
ini belum. `_trackingNews`/`_counterNews` (file `.txt` counter lokal) juga
gak diport -- itu artefak operasional proses tunggal, `scraper_runs`
(Fase 2) udah gantiin fungsinya secara lebih baik lintas-proses."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cti_enrich import routing
from cti_enrich.stages import extract_iocs as extract_iocs_stage
from cti_enrich.stages import score as score_stage
from cti_enrich.stages.alert import build_message_base, route_alerts
from cti_enrich.stages.classify import ClassifyResult, classify, resolve_industries
from cti_enrich.stages.extract_ttps import TtpResult, extract_ttps
from cti_enrich.stages.fetch_text import fetch_text
from cti_enrich.stages.persist import persist, persist_rejected
from cti_enrich.stages.summarize import summarize


@dataclass
class PipelineOutcome:
    accepted: bool
    """False kalau `related_cyber == False` -- artikel gak lanjut ke
    fetch/summarize/enrichment penuh, tapi TETAP di-log ke
    `rejected_articles` (Fase 7.3, `persist_rejected()`) buat review manual
    lewat router `filtered_articles.py` -- bukan diam-diam ilang kayak
    Fase 5 awal."""
    article_id: int | None = None
    news_type: str | None = None
    classify_result: ClassifyResult | None = None


def run_pipeline(
    *,
    title: str,
    url: str,
    posted_on: datetime.date | None,
    source: str,
    scraper_id: str | None,
    session: Session,
) -> PipelineOutcome:
    classify_result = classify(title)
    if not classify_result.related_cyber:
        persist_rejected(
            session=session,
            url=url,
            title=title,
            source=source,
            scraper_id=scraper_id,
            posted_on=posted_on,
            classify_result=classify_result,
        )
        return PipelineOutcome(accepted=False, classify_result=classify_result)

    text = fetch_text(url)
    summary = summarize(text)
    ioc_data = extract_iocs_stage.extract_iocs(text or summary, url, session)
    c2_indicator = extract_iocs_stage.check_c2_hit(ioc_data, session)

    industries_display = resolve_industries(classify_result.industries_impacted)
    msg_base = build_message_base(
        script_name=source,
        title=title,
        posted_on=str(posted_on or ""),
        url=url,
        industries_string=" || ".join(industries_display),
        funding_keyword=None,
    )

    if classify_result.security_tech_best_practice:
        result = routing.RoutingResult(
            news_type="Security Technology & Best Practices",
            alert_topics=["best_practice"],
            msg_data=msg_base,
        )
        article = persist(
            session=session,
            url=url,
            title=title,
            source=source,
            scraper_id=scraper_id,
            posted_on=posted_on,
            classify_result=classify_result,
            score_result=None,
            routing_result=result,
            ttp_result=None,
            ioc_data=ioc_data,
            c2_indicator=c2_indicator,
        )
        route_alerts(result)
        return PipelineOutcome(
            accepted=True,
            article_id=article.id,
            news_type=result.news_type,
            classify_result=classify_result,
        )

    ttp_result: TtpResult = (
        extract_ttps(summary[:2000]) if summary else TtpResult(has_techniques=False)
    )
    ttp_string = ""
    if ttp_result.has_techniques:
        ttp_string = ", ".join(
            f"{t.technique_name} ({t.technique_id})" for t in ttp_result.techniques
        )

    score_result = score_stage.score(title, summary, session)

    # Funding line ikut nempel di msg_data (kode lama nambahinnya di Phase 4
    # scoring, SEBELUM cascade -- lihat nlp.py:429-432), bukan di
    # `build_message_base` di atas (yang dipanggil sebelum funding_keyword
    # kehitung).
    if score_result.funding_keyword:
        msg_base += f"<b>Funding Related Article</b>: True ({score_result.funding_keyword})\n"

    routing_input = routing.RoutingInput(
        msg_data_base=msg_base,
        industries_impacted=classify_result.industries_impacted,
        mentioned_group=score_result.mentioned_group,
        mentioned_countries=score_result.mentioned_countries,
        mentioned_apac_people=score_result.mentioned_apac_people,
        cve_list_title=score_result.cve_list_title,
        report_status=score_result.report_status,
        ot_status=score_result.ot_status,
        related_tech_status=score_result.related_tech_status,
        related_tech_cve_status=score_result.related_tech_cve_status,
        databreach_list=score_result.databreach_list,
        zero_day_list=score_result.zero_day_list,
        ttp_string=ttp_string,
    )
    result = routing.route(routing_input)

    article = persist(
        session=session,
        url=url,
        title=title,
        source=source,
        scraper_id=scraper_id,
        posted_on=posted_on,
        classify_result=classify_result,
        score_result=score_result,
        routing_result=result,
        ttp_result=ttp_result,
        ioc_data=ioc_data,
        c2_indicator=c2_indicator,
    )
    route_alerts(result)

    return PipelineOutcome(
        accepted=True,
        article_id=article.id,
        news_type=result.news_type,
        classify_result=classify_result,
    )
