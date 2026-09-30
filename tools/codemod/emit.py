"""Render scraper baru dari hasil ekstraksi (extract.py) + jadwal Rundeck
(import_rundeck.py) lewat template Jinja. Satu file per scraper, ditulis
ke `scrapers/src/cti_scrapers/feeds/<scraper_id>.py` -- kontrak yang sama
kayak nambah scraper manual (docs/ADDING_A_SCRAPER.md), bukan bentuk lain.
"""

from __future__ import annotations

import re
from pathlib import Path

from extract import RssExtraction, XPathExtraction
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)


def legacy_stem_to_id(stem: str) -> str:
    """ "bitdefenderThreat" -> "bitdefender", "asecAhnThreat" -> "asec_ahn".
    Buang akhiran "Threat"/"threat", lalu camelCase -> snake_case."""
    base = re.sub(r"[Tt]hreat$", "", stem)
    # sisipin _ di batas huruf-kecil->huruf-besar, lalu lowercase semua
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    return snake.strip("_") or stem.lower()


def id_to_class_name(scraper_id: str) -> str:
    return "".join(part.capitalize() for part in scraper_id.split("_"))


def derive_source(legacy_label: str | None, scraper_id: str) -> str:
    """ "NEW ARTICLE FROM BITDEFENDER" -> "Bitdefender". Fallback ke id
    title-case kalau label gak ada atau gak punya "FROM"."""
    if legacy_label and "FROM" in legacy_label.upper():
        idx = legacy_label.upper().rindex("FROM")
        tail = legacy_label[idx + 4 :].strip()
        if tail:
            return tail.title()
    return scraper_id.replace("_", " ").title()


def _py_repr(value: object) -> str:
    return repr(value)


def emit_rss(
    *, legacy_script: str, extraction: RssExtraction, schedule: str, out_dir: Path
) -> Path:
    scraper_id = legacy_stem_to_id(legacy_script)
    class_name = id_to_class_name(scraper_id)
    source = derive_source(extraction.legacy_label, scraper_id)

    template = _env.get_template("rss.py.jinja")
    content = template.render(
        class_name=class_name,
        scraper_id=scraper_id,
        source=source,
        schedule=schedule,
        legacy_label=extraction.legacy_label,
        legacy_script=legacy_script,
        feeds_repr=", ".join(_py_repr(f) for f in extraction.feeds),
        item_path=extraction.item_path,
        title_path=extraction.title_path,
        link_path=extraction.link_path,
        date_path=extraction.date_path,
        xml_fixups=extraction.xml_fixups,
        xml_fixups_repr=", ".join(_py_repr(fx) for fx in extraction.xml_fixups),
        html_unescape=extraction.html_unescape,
    )
    out_path = out_dir / f"{scraper_id}.py"
    out_path.write_text(content)
    return out_path


def emit_xpath(
    *,
    legacy_script: str,
    extraction: XPathExtraction,
    schedule: str,
    runtime: str,
    out_dir: Path,
) -> Path:
    scraper_id = legacy_stem_to_id(legacy_script)
    class_name = id_to_class_name(scraper_id)
    source = derive_source(extraction.legacy_label, scraper_id)

    template = _env.get_template("xpath.py.jinja")
    content = template.render(
        class_name=class_name,
        scraper_id=scraper_id,
        source=source,
        schedule=schedule,
        runtime=runtime,
        max_items=extraction.max_items,
        legacy_label=extraction.legacy_label,
        legacy_script=legacy_script,
        url_repr=_py_repr(extraction.url),
        title_xpath_repr=_py_repr(extraction.title_xpath),
        link_xpath_repr=_py_repr(extraction.link_xpath),
        base_url=extraction.base_url,
    )
    out_path = out_dir / f"{scraper_id}.py"
    out_path.write_text(content)
    return out_path
