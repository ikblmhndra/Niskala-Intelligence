"""Baca (bukan tulis) data referensi IOC -- `ioc_allowlist_entries` dan
`threat_feed_entries` (lihat `db/models/ioc_reference.py`). Bentuk balik
dataset PERSIS yang `iocExtractor._filter_iocs()`/`nlp.py::_check_c2_hit()`
lama harapkan (`dict[str, set[str]]`) -- caller (`cti_enrich.stages.
extract_iocs`, dan nanti `cti_scraper`'s reference_data resolver buat
scraper `deepdarkCTI`) gak perlu tau bentuk tabel, cuma pasang set ini ke
fungsi lama yang udah ada."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from cti_core.db.models.ioc_reference import IocAllowlistEntry, ThreatFeedEntry


def get_ioc_allowlist(session: Session) -> dict[str, set[str]]:
    rows = session.execute(select(IocAllowlistEntry.type, IocAllowlistEntry.value)).all()
    result: dict[str, set[str]] = {"url_domains": set(), "email_domains": set(), "ips": set()}
    _key = {"url_domain": "url_domains", "email_domain": "email_domains", "ip": "ips"}
    for type_, value in rows:
        key = _key.get(type_)
        if key:
            result[key].add(value.lower() if key != "ips" else value)
    return result


def get_c2_feed(session: Session, *, feed: str = "deepdarkcti_c2") -> dict[str, set[str]]:
    rows = session.execute(
        select(ThreatFeedEntry.type, ThreatFeedEntry.value).where(ThreatFeedEntry.feed == feed)
    ).all()
    result: dict[str, set[str]] = {"ips": set(), "domains": set()}
    for type_, value in rows:
        if type_ == "ip":
            result["ips"].add(value)
        else:
            result["domains"].add(value.lower())
    return result
