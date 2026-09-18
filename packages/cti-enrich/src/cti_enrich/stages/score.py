"""Stage: hitung semua sinyal yang `routing.route()` butuh -- port
`nlp.py:144-493` (keyword list + regex title/body + NER spaCy) plus
`cveValidator.checkCVE`/`checkTechStack` (`ScraperNews/modules/cveValidator.
py:12-57`, HTTP ke MITRE). BUKAN pure function (beda dari `routing.py`) --
butuh `Session` (baca `techstack`/`threat_actor_groups`/`monitored_people`)
dan HTTP (MITRE), itu sebabnya sinyal-sinyal ini dihitung DI SINI baru
diteruskan sebagai data polos ke `routing.route()`.

Butuh extra `nlp` (`en_core_web_sm`) -- modul ini import `spacy` di level
atas, jangan diimport dari kode yang jalan di image API/scrape ringan.

Perubahan yang DISENGAJA dari sumber lama (bukan bug, bukan port apa
adanya -- lihat penjelasan tiap satu):

- `country_list` = `pycountry.countries` (seluruh negara ISO 3166-1),
  GANTIIN Mongo `apac-country`+`global-country` (~150 nama kuratif). Dua
  alasan sekaligus: (1) `ArticleCountry.country_code` (Fase 2) minta kode
  ISO alpha-2, jadi konversi nama->kode WAJIB ada di suatu titik --
  `pycountry` ngasih itu gratis dari sumber yang sama; (2) daftar lama gak
  pernah di-port ke Postgres (lihat `db/models/threat_reference.py`), jadi
  ini bukan "ganti yang udah ada" tapi "isi kekosongan referensi negara"
  dengan sumber kanonik, superset dari daftar kuratif lama.
- `group_list` (`threat_actor_groups`) dan `apac_people_list`
  (`monitored_people`) baca dari tabel BARU yang kosong sampai di-seed --
  lihat docstring `db/models/threat_reference.py`. `mentioned_group`/
  `mentioned_apac_people` bakal selalu `[]` sampai data itu ada, ini
  cold-start, BUKAN pipeline yang salah.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field

import httpx
import pycountry
import spacy
from cti_core.db.models.techstack import TechStackEntry
from cti_core.db.repositories.threat_reference import (
    list_monitored_people,
    list_threat_actor_groups,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

_NLP = spacy.load("en_core_web_sm")

_OT_LIST = [
    "ics vulnerabilities",
    "industrial espionage",
    "scada",
    "supervisory control and data acquisitions?",
    "plc",
    "programmable logic controller",
    "dcs",
    "distributed control systems?",
    "mes",
    "manufacturing execution systems?",
    "iiot",
    "industrial internet of things?",
    "mcc",
    "Motor Control Center",
    "sis",
    "esd",
    "pneumatics?",
    "hydraulics?",
    "safety instrumented",
    "emergency shutdown systems?",
    "ot resilience",
    "ot security standards?",
    "ot environments?",
    "ot infrastructures?",
    "industrial attacks?",
    "industrial networks?",
    "industrial automations?",
    "industrial safety regulation updates?",
    "ics",
    "industrial control systems?",
    "ot networks?",
]

_FUNDING_LIST = [
    "funding round",
    "venture capital",
    "seed funding",
    "serie[s] a",
    "serie[s] b",
    "serie[s] c",
    "equity financing",
    "fundraising",
    "capital raise",
    "private equity",
    "crowdfunding",
    "startup funding",
    "acquisition funding",
    "strategic investment",
]

_KEYWORD_LIST = [
    "report[s]?",
    "trend[s]?",
    "landscape",
    "Q[1-4]",
    "threat[s]?",
    "prediction[s]?",
    "threatscape",
    "roundup",
    "whitepaper[s]?",
    "analysis",
    "case study",
    "insight[s]?",
    "overview",
    "annual report",
    "quarterly report",
    "forecast[s]?",
    "security bulletin",
    "cybersecurity report",
    "research paper[s]?",
    "executive summary",
    "write-up",
    "publication",
    "threat report",
    "threat intelligence report",
    "case study",
    "security update",
]

_DATABREACH_KEYWORD = [
    "(?:data|security) breach",
    "data leaks?",
    "customer data exposed",
    "alleged(?:ly)? (?:breach(?:ed|es)|leak(?:ed|s)|sale|leak)",
    "records leak(?:ed|s)",
]

_FLAGS_LIST = [
    ("🇦🇫", "Afghanistan"),
    ("🇦🇺", "Australia"),
    ("🇧🇩", "Bangladesh"),
    ("🇧🇹", "Bhutan"),
    ("🇧🇳", "Brunei"),
    ("🇰🇭", "Cambodia"),
    ("🇨🇳", "China"),
    ("🇫🇯", "Fiji"),
    ("🇮🇩", "Indonesia"),
    ("🇮🇳", "India"),
    ("🇯🇵", "Japan"),
    ("🇰🇿", "Kazakhstan"),
    ("🇰🇮", "Kiribati"),
    ("🇰🇵", "North Korea"),
    ("🇰🇷", "South Korea"),
    ("🇱🇦", "Laos"),
    ("🇲🇾", "Malaysia"),
    ("🇲🇻", "Maldives"),
    ("🇲🇳", "Mongolia"),
    ("🇲🇲", "Myanmar"),
    ("🇳🇵", "Nepal"),
    ("🇳🇿", "New Zealand"),
    ("🇵🇰", "Pakistan"),
    ("🇵🇬", "Papua New Guinea"),
    ("🇵🇭", "Philippines"),
    ("🇸🇧", "Solomon Islands"),
    ("🇸🇬", "Singapore"),
    ("🇱🇰", "Sri Lanka"),
    ("🇹🇭", "Thailand"),
    ("🇹🇱", "Timor-Leste"),
    ("🇹🇴", "Tonga"),
    ("🇹🇻", "Tuvalu"),
    ("🇻🇺", "Vanuatu"),
    ("🇻🇳", "Vietnam"),
    ("🇺🇸", "United States"),
    ("🇨🇦", "Canada"),
    ("🇲🇽", "Mexico"),
    ("🇧🇷", "Brazil"),
    ("🇦🇷", "Argentina"),
    ("🇨🇴", "Colombia"),
    ("🇨🇱", "Chile"),
    ("🇵🇪", "Peru"),
    ("🇻🇪", "Venezuela"),
    ("🇪🇨", "Ecuador"),
    ("🇧🇴", "Bolivia"),
    ("🇵🇾", "Paraguay"),
    ("🇺🇾", "Uruguay"),
    ("🇨🇺", "Cuba"),
    ("🇩🇴", "Dominican Republic"),
    ("🇬🇹", "Guatemala"),
    ("🇭🇳", "Honduras"),
    ("🇸🇻", "El Salvador"),
    ("🇨🇷", "Costa Rica"),
    ("🇵🇦", "Panama"),
    ("🇯🇲", "Jamaica"),
    ("🇹🇹", "Trinidad and Tobago"),
    ("🇭🇹", "Haiti"),
    ("🇬🇾", "Guyana"),
    ("🇬🇧", "United Kingdom"),
    ("🇩🇪", "Germany"),
    ("🇫🇷", "France"),
    ("🇮🇹", "Italy"),
    ("🇪🇸", "Spain"),
    ("🇳🇱", "Netherlands"),
    ("🇧🇪", "Belgium"),
    ("🇸🇪", "Sweden"),
    ("🇳🇴", "Norway"),
    ("🇩🇰", "Denmark"),
    ("🇫🇮", "Finland"),
    ("🇵🇱", "Poland"),
    ("🇺🇦", "Ukraine"),
    ("🇷🇺", "Russia"),
    ("🇨🇭", "Switzerland"),
    ("🇦🇹", "Austria"),
    ("🇵🇹", "Portugal"),
    ("🇨🇿", "Czech Republic"),
    ("🇷🇴", "Romania"),
    ("🇭🇺", "Hungary"),
    ("🇬🇷", "Greece"),
    ("🇹🇷", "Turkey"),
    ("🇸🇰", "Slovakia"),
    ("🇧🇬", "Bulgaria"),
    ("🇭🇷", "Croatia"),
    ("🇷🇸", "Serbia"),
    ("🇮🇪", "Ireland"),
    ("🇱🇹", "Lithuania"),
    ("🇱🇻", "Latvia"),
    ("🇪🇪", "Estonia"),
    ("🇧🇾", "Belarus"),
    ("🇲🇩", "Moldova"),
    ("🇦🇱", "Albania"),
    ("🇲🇰", "North Macedonia"),
    ("🇧🇦", "Bosnia and Herzegovina"),
    ("🇲🇪", "Montenegro"),
    ("🇮🇸", "Iceland"),
    ("🇱🇺", "Luxembourg"),
    ("🇦🇪", "United Arab Emirates"),
    ("🇸🇦", "Saudi Arabia"),
    ("🇮🇱", "Israel"),
    ("🇮🇷", "Iran"),
    ("🇮🇶", "Iraq"),
    ("🇶🇦", "Qatar"),
    ("🇰🇼", "Kuwait"),
    ("🇧🇭", "Bahrain"),
    ("🇯🇴", "Jordan"),
    ("🇱🇧", "Lebanon"),
    ("🇴🇲", "Oman"),
    ("🇾🇪", "Yemen"),
    ("🇸🇾", "Syria"),
    ("🇵🇸", "Palestine"),
    ("🇨🇾", "Cyprus"),
    ("🇬🇪", "Georgia"),
    ("🇦🇲", "Armenia"),
    ("🇦🇿", "Azerbaijan"),
    ("🇿🇦", "South Africa"),
    ("🇳🇬", "Nigeria"),
    ("🇰🇪", "Kenya"),
    ("🇪🇹", "Ethiopia"),
    ("🇪🇬", "Egypt"),
    ("🇬🇭", "Ghana"),
    ("🇲🇦", "Morocco"),
    ("🇹🇳", "Tunisia"),
    ("🇩🇿", "Algeria"),
    ("🇱🇾", "Libya"),
    ("🇹🇿", "Tanzania"),
    ("🇸🇩", "Sudan"),
    ("🇺🇬", "Uganda"),
    ("🇷🇼", "Rwanda"),
    ("🇦🇴", "Angola"),
    ("🇲🇿", "Mozambique"),
    ("🇸🇳", "Senegal"),
    ("🇿🇼", "Zimbabwe"),
    ("🇨🇲", "Cameroon"),
    ("🇨🇮", "Ivory Coast"),
    ("🇿🇲", "Zambia"),
    ("🇲🇱", "Mali"),
    ("🇧🇫", "Burkina Faso"),
    ("🇲🇬", "Madagascar"),
    ("🇸🇴", "Somalia"),
    ("🇸🇸", "South Sudan"),
    ("🇳🇪", "Niger"),
    ("🇲🇼", "Malawi"),
    ("🇹🇩", "Chad"),
    ("🇬🇳", "Guinea"),
    ("🇺🇿", "Uzbekistan"),
    ("🇹🇲", "Turkmenistan"),
    ("🇰🇬", "Kyrgyzstan"),
    ("🇹🇯", "Tajikistan"),
    ("🇹🇼", "Taiwan"),
]

_RE_CVE_MENTION = re.compile(r"cve-\d{4}-\d{4,}")


def _country_list() -> list[str]:
    """Lihat catatan "Perubahan yang disengaja" di docstring modul."""
    names = {c.name for c in pycountry.countries}
    names.update(
        name for _, name in _FLAGS_LIST
    )  # "North Korea" dst gak selalu match nama resmi pycountry
    return sorted(names)


def _hit(keywords: list[str], text: str) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{kw.lower()}\b", lowered) for kw in keywords)


def _find_hits(keywords: list[str], text: str) -> list[str]:
    lowered = text.lower()
    return [kw for kw in keywords if re.search(rf"\b{kw.lower()}\b", lowered)]


@dataclass
class ScoreResult:
    mentioned_group: list[str] = field(default_factory=list)
    mentioned_countries: list[str] = field(default_factory=list)
    mentioned_apac_people: list[str] = field(default_factory=list)
    cve_list_title: list[str] = field(default_factory=list)
    cve_list_body: list[str] = field(default_factory=list)
    report_status: bool = False
    ot_status: bool = False
    related_tech_status: bool = False
    related_tech_cve_status: bool = False
    databreach_list: list[str] = field(default_factory=list)
    zero_day_list: list[str] = field(default_factory=list)
    funding_keyword: str | None = None


def check_tech_stack(tech_name: str, techstack: list[str]) -> bool:
    """Port `cveValidator.checkTechStack`."""
    lowered = tech_name.lower()
    return any(re.search(re.escape(tech.lower().strip()), lowered) for tech in techstack)


def _check_cve_vendor(cve_id: str, techstack: list[str]) -> bool:
    """Port `cveValidator.checkCVE` -- HTTP ke MITRE, cek vendor CVE lawan
    techstack (di-passing langsung, bukan query Postgres lagi -- `score()`
    udah baca techstack sekali di awal)."""
    try:
        resp = httpx.get(f"https://cveawg.mitre.org/api/cve/{cve_id}", timeout=30)
        data = resp.json()
    except Exception:
        return False

    vendor_name = ""
    try:
        for d in data["containers"]["adp"]:
            for affected in d["affected"]:
                for _version in affected["versions"]:
                    vendor_name = str(affected["vendor"]).lower()
    except Exception:
        pass
    try:
        for affected in data["containers"]["cna"]["affected"]:
            for _version in affected["versions"]:
                if len(vendor_name) == 0 or vendor_name == "n/a":
                    vendor_name = affected["vendor"]
    except Exception:
        pass
    if not vendor_name:
        vendor_name = "Unknown"

    return check_tech_stack(vendor_name, techstack)


def score(title: str, body: str, session: Session) -> ScoreResult:
    """Wrapper session -- resolve 3 daftar referensi (techstack/group/people)
    dari Postgres, lalu delegasi ke `score_with_lists()` (murni, gak
    nyentuh Session). Dipanggil `pipeline.py` (`cti_enrich`, punya Session
    beneran). Scraper bespoke (mis. `monitorX`, `scrapers/`) TIDAK boleh
    manggil fungsi ini -- `fetch()` gak boleh pegang Session (lihat
    docstring `ScrapeContext`) -- panggil `score_with_lists()` langsung
    dengan daftar dari `ctx.reference` (resolusi lewat `reference_data`,
    Fase 4)."""
    techstack = sorted(session.execute(select(TechStackEntry.name).distinct()).scalars().all())
    group_list = list_threat_actor_groups(session)
    apac_people_list = list_monitored_people(session)
    return score_with_lists(
        title, body, techstack=techstack, group_list=group_list, apac_people_list=apac_people_list
    )


def score_with_lists(
    title: str,
    body: str,
    *,
    techstack: list[str],
    group_list: list[str],
    apac_people_list: list[str],
) -> ScoreResult:
    """Inti scoring, PURE -- gak ada I/O Postgres (MITRE tetap HTTP, lihat
    `_check_cve_vendor`). `country_list` gak perlu di-passing -- dari
    `pycountry`, gak berubah per-caller (lihat `_country_list()`)."""
    country_list = _country_list()

    result = ScoreResult()

    mentioned_group: list[str] = []
    mentioned_countries: list[str] = []
    mentioned_apac_people: list[str] = []

    # --- Title ---
    for group in group_list:
        if group.startswith("[") or not group:
            continue
        if re.search(rf"\b{group.lower()}\b", title.lower()):
            mentioned_group.append(group.replace("\\-", "-"))

    for country in country_list:
        if re.search(rf"\b{country.lower()}\b", title.lower()):
            mentioned_countries.append(country)
    for flag, country in _FLAGS_LIST:
        if flag in title.lower():
            mentioned_countries.append(country)
    for person in apac_people_list:
        if re.search(rf"\b{person.lower()}\b", title.lower()):
            mentioned_apac_people.append(person)

    result.cve_list_title = re.findall(_RE_CVE_MENTION, title.lower())

    for tech in techstack:
        if re.search(rf"\b{tech.lower()}\b", title.lower()):
            result.related_tech_status = True

    result.databreach_list = _find_hits(_DATABREACH_KEYWORD, title)
    result.zero_day_list = re.findall(r"\b(zero|0)[-.]day\b", title.lower())

    report_status_count = sum(
        1 for kw in _KEYWORD_LIST if re.search(rf"\b{kw.lower()}\b", title.lower())
    )
    if report_status_count >= 5:
        result.report_status = True

    for kw in _FUNDING_LIST:
        if re.search(rf"\b{kw.lower()}\b", title.lower()):
            result.funding_keyword = kw
            break

    ot_status_count = sum(1 for kw in _OT_LIST if re.search(rf"\b{kw.lower()}\b", title.lower()))
    if ot_status_count >= 1:
        result.ot_status = True

    # --- Body (regex + NER) ---
    if body:
        for group in group_list:
            if group.startswith("[") or not group:
                continue
            if re.search(rf"\b{group.lower()}\b", body.lower()):
                mentioned_group.append(group.replace("\\-", "-"))

        for country in country_list:
            if re.search(rf"\b{country.lower()}\b", body.lower()):
                mentioned_countries.append(country)
        for flag, country in _FLAGS_LIST:
            if flag in body.lower():
                mentioned_countries.append(country)
        for person in apac_people_list:
            if re.search(rf"\b{person.lower()}\b", body.lower()):
                mentioned_apac_people.append(person)

        result.cve_list_body = re.findall(_RE_CVE_MENTION, body.lower())

        report_status_count += sum(
            1 for kw in _KEYWORD_LIST if re.search(rf"\b{kw.lower()}\b", body.lower())
        )
        if report_status_count >= 5:
            result.report_status = True

        ot_status_count += sum(
            1 for kw in _OT_LIST if re.search(rf"\b{kw.lower()}\b", body.lower())
        )
        if ot_status_count >= 1:
            result.ot_status = True

        doc = _NLP(body[:1_000_000])
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PERSON", "GPE"):
                for group in group_list:
                    if group.startswith("[") or not group:
                        continue
                    if re.search(rf"\b{group.lower()}\b", str(ent).lower()):
                        mentioned_group.append(group)
            if ent.label_ in ("NORP", "GPE"):
                for country in country_list:
                    if re.search(rf"\b{country.lower()}\b", str(ent).lower()):
                        mentioned_countries.append(country)
                for flag, country in _FLAGS_LIST:
                    if flag in str(ent).lower():
                        mentioned_countries.append(country)
                for person in apac_people_list:
                    if re.search(rf"\b{person.lower()}\b", str(ent).lower()):
                        mentioned_apac_people.append(person)

    result.mentioned_group = list(OrderedDict.fromkeys(mentioned_group))
    result.mentioned_countries = list(OrderedDict.fromkeys(mentioned_countries))
    result.mentioned_apac_people = list(OrderedDict.fromkeys(mentioned_apac_people))

    # `related_tech_cve_status` CUMA dihitung buat "Global Article" (semua
    # mention kosong) -- port persis kondisi nlp.py:565-568, lihat catatan
    # di routing.py docstring soal kenapa ini bukan tanggung jawab route().
    if (
        not result.mentioned_group
        and not result.mentioned_apac_people
        and not result.mentioned_countries
    ):
        for cve_id in result.cve_list_title:
            result.related_tech_cve_status = _check_cve_vendor(cve_id.upper(), techstack)
            if result.related_tech_cve_status:
                break

    return result
