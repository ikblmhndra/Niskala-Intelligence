"""Scraper konkret. Satu file = satu scraper -- lihat docs/ADDING_A_SCRAPER.md.

`feeds/` = scraper yang nge-yield `ArticleItem` (masuk pipeline enrichment).
`collectors/` = scraper bespoke yang nge-yield tipe item lain (nulis
langsung ke tabelnya sendiri, lewatin enrichment) -- lihat sinks.py.
"""
